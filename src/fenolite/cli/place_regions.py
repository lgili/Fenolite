# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The glue of ``fenolite place --strategy regions`` (change c0205; ``docs/placement.md``, "Regions").

``placement.regions`` packs boxes into named regions and knows nothing of nets. This module, on the CLI
layer, decides the domains (the islands of ``analysis.ties.isolation_islands`` once the ``--barrier`` parts
are removed, or the ``--group`` globs of references), the regions (the ``--region`` boxes or one band of the
outline per domain), which two regions each barrier joins, and, after the moves, the open connections of
``analysis.connectivity`` that cross from one region to another.
"""

from __future__ import annotations

import argparse
from collections import defaultdict
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from fnmatch import fnmatchcase
from typing import Any

from fenolite.analysis.connectivity import connectivity
from fenolite.analysis.ties import EVIDENCE as TIES_EVIDENCE
from fenolite.analysis.ties import isolation_islands
from fenolite.backends.base import BoardPad
from fenolite.cli.errors import CliError
from fenolite.core.coords import Point
from fenolite.core.errors import Issue
from fenolite.core.evidence import Evidence
from fenolite.core.units import Nm, parse_length
from fenolite.geometry import BBox
from fenolite.model.board import FootprintInstance
from fenolite.model.design import Design
from fenolite.placement.codes import issue
from fenolite.placement.grid import Box
from fenolite.placement.regions import EVIDENCE as REGION_EVIDENCE
from fenolite.placement.regions import (
    Axis,
    Barrier,
    Region,
    RegionResult,
    band_order,
    place_regions,
    region_of,
    split,
)

REGION_HINT = "write --region NAME=X1,Y1,X2,Y2 with units, for example --region iso=0mm,0mm,20mm,40mm"
GROUP_HINT = "write --group NAME=GLOB[,GLOB...], for example --group primary=U1,R1*"


@dataclass(frozen=True, slots=True)
class RegionOptions:
    """The parsed options of the strategy: barrier references, groups (name → globs, in order), explicit
    regions (name → box relative to the outline's top-left corner) and the split axis."""

    barriers: tuple[str, ...] = ()
    groups: tuple[tuple[str, tuple[str, ...]], ...] = ()
    regions: tuple[tuple[str, BBox], ...] = ()
    axis: Axis | None = None

    @property
    def given(self) -> bool:
        return bool(self.barriers or self.groups or self.regions or self.axis)


@dataclass(slots=True)
class RegionPlan:
    """What the strategy decided and placed; ``issues`` holds its findings before the moves are judged."""

    source: str
    axis: Axis | None
    regions: tuple[Region, ...]
    nets: Mapping[str, tuple[str, ...]]
    parts: Mapping[str, tuple[str, ...]]
    result: RegionResult
    unassigned: tuple[str, ...]
    issues: list[Issue] = field(default_factory=lambda: [])


def _names(values: Sequence[str], option: str) -> tuple[str, ...]:
    names: list[str] = []
    for text in values:
        parts = [name.strip() for name in text.split(",")]
        if not all(parts):
            raise CliError("FEN-2001", f"{option}: empty name in {text!r}", where=option)
        names += parts
    return tuple(dict.fromkeys(names))


def _named(text: str, option: str, hint: str) -> tuple[str, list[str]]:
    name, eq, rest = text.partition("=")
    parts = [part.strip() for part in rest.split(",")]
    if not eq or not name.strip() or not all(parts):
        raise CliError("FEN-2001", f"{option}: cannot read {text!r}", where=option, hint=hint)
    return name.strip(), parts


def _length(text: str) -> Nm:
    try:
        return parse_length(text)
    except ValueError as error:
        raise CliError("FEN-2001", f"--region: {error}", where="--region", hint=REGION_HINT) from None


def parse_options(args: argparse.Namespace) -> RegionOptions:
    """The region options of ``args``; a malformed or inconsistent value is a usage error (``FEN-2001``)."""
    groups: dict[str, tuple[str, ...]] = {}
    for text in args.group:
        name, globs = _named(text, "--group", GROUP_HINT)
        if name in groups:
            raise CliError("FEN-2001", f"--group: {name} is given twice", where="--group", hint=GROUP_HINT)
        groups[name] = tuple(globs)
    regions: dict[str, BBox] = {}
    for text in args.region:
        name, values = _named(text, "--region", REGION_HINT)
        if len(values) != 4 or name in regions:
            raise CliError("FEN-2001", f"--region: cannot read {text!r}", where="--region", hint=REGION_HINT)
        x0, y0, x1, y1 = (_length(value) for value in values)
        if x0 >= x1 or y0 >= y1:
            raise CliError(
                "FEN-2001", f"--region: {name} needs X1 < X2 and Y1 < Y2", where="--region", hint=REGION_HINT
            )
        regions[name] = BBox(x0, y0, x1, y1)
    if regions and not groups:
        raise CliError(
            "FEN-2001", "--region needs --group: a region holds the parts of the group of its name"
        )
    if regions and set(regions) != set(groups):
        raise CliError(
            "FEN-2001",
            "every --group needs a --region of its name, and every --region a --group",
            where="--region",
            hint=f"groups {', '.join(groups)}; regions {', '.join(regions)}",
        )
    if regions and args.split is not None:
        raise CliError("FEN-2001", "--split cuts the default bands; it does not apply with --region")
    axis: Axis | None = "x" if args.split == "x" else "y" if args.split == "y" else None
    return RegionOptions(
        barriers=_names(args.barrier, "--barrier"),
        groups=tuple(groups.items()),
        regions=tuple((name, regions[name]) for name in groups if name in regions),
        axis=axis,
    )


def _component_nets(design: Design) -> dict[str, set[str]]:
    nets: dict[str, set[str]] = defaultdict(set)
    for net in design.circuit.nets:
        for member in net.members:
            nets[member.component_id].add(net.name)
    return nets


def plan_regions(
    design: Design,
    options: RegionOptions,
    *,
    outline: BBox,
    refs: Mapping[str, str],
    boxes: Mapping[str, Box],
    staged: Sequence[FootprintInstance],
    occupied: Sequence[BBox],
    cutouts: Sequence[BBox],
    pitch: Nm,
    gap: Nm,
    margin: Nm,
) -> RegionPlan:
    """The domains, the regions and the packing of the staged parts. ``refs`` maps every footprint id of
    the board to its reference, ``boxes`` every footprint id to its box relative to its position (``path``
    the footprint id), and ``staged`` lists the parts to place, in placing order."""
    assert design.board is not None
    footprints = design.board.footprints
    comp_nets = _component_nets(design)
    nets_of = {fp.id: comp_nets.get(fp.component_id, set()) for fp in footprints}
    barrier_refs = set(options.barriers)
    issues: list[Issue] = [
        issue("place.unknown-ref", f"the board has no part {ref}", ref, "correct --barrier")
        for ref in sorted(barrier_refs - set(refs.values()))
    ]
    is_barrier = {fp.id: refs[fp.id] in barrier_refs for fp in footprints}
    domain_of: dict[str, str] = {}
    domain_nets: dict[str, tuple[str, ...]] = {}
    if options.groups:
        source = "groups"
        names = [name for name, _ in options.groups]
        for fp in footprints:
            if is_barrier[fp.id]:
                continue
            for name, globs in options.groups:
                if any(fnmatchcase(refs[fp.id], glob) for glob in globs):
                    domain_of[fp.id] = name
                    break
        domain_nets = {name: () for name in names}
    else:
        source = "islands"
        report = isolation_islands(design, barriers=sorted(barrier_refs & set(refs.values())))
        island_of = {net: index for index, island in enumerate(report.islands) for net in island.nets}
        provisional: dict[int, str] = {}
        for fp in footprints:
            held = sorted(nets_of[fp.id])
            if is_barrier[fp.id] or not held:
                continue
            index = island_of[held[0]]
            provisional.setdefault(index, f"#{index}")
            domain_of[fp.id] = provisional[index]
        names = [provisional[index] for index in sorted(provisional)]
        domain_nets = {provisional[index]: report.islands[index].nets for index in provisional}
    members_of_net: dict[str, set[str]] = defaultdict(set)
    for fp in footprints:
        if fp.id in domain_of:
            for net in nets_of[fp.id]:
                members_of_net[net].add(domain_of[fp.id])
    sides_of: dict[str, set[str]] = {
        fp.id: {domain for net in nets_of[fp.id] for domain in members_of_net[net]}
        for fp in footprints
        if is_barrier[fp.id]
    }
    if source == "islands":
        links = [tuple(sorted(sides)) for sides in sides_of.values() if len(sides) == 2]
        ordered = band_order(names, [(a, b) for a, b in links])
        rename = {old: f"D{index}" for index, old in enumerate(ordered, start=1)}
        names = [rename[old] for old in ordered]
        domain_of = {fp_id: rename[old] for fp_id, old in domain_of.items()}
        domain_nets = {rename[old]: nets for old, nets in domain_nets.items()}
        sides_of = {fp_id: {rename[old] for old in sides} for fp_id, sides in sides_of.items()}
    rank = {name: index for index, name in enumerate(names)}
    axis: Axis | None = None
    if options.regions:
        regions = tuple(
            Region(
                name, BBox(outline.x0 + box.x0, outline.y0 + box.y0, outline.x0 + box.x1, outline.y0 + box.y1)
            )
            for name, box in options.regions
        )
    else:
        axis = options.axis or ("x" if outline.width >= outline.height else "y")
        weights = [0] * len(names)
        minimums = [0] * len(names)
        staged_ids = {fp.id for fp in staged}
        for fp in footprints:
            if fp.id not in domain_of:
                continue
            index, box = rank[domain_of[fp.id]], boxes[fp.id].bbox
            weights[index] += box.width * box.height
            if fp.id in staged_ids:
                along = box.width if axis == "x" else box.height
                minimums[index] = max(minimums[index], along + 2 * margin)
        regions = tuple(
            Region(name, band)
            for name, band in zip(names, split(outline, weights, axis=axis, minimums=minimums), strict=True)
        )
    members: dict[str, list[Box]] = defaultdict(list)
    barriers: list[Barrier] = []
    unassigned: list[str] = []
    for fp in staged:
        ref = refs[fp.id]
        if is_barrier[fp.id]:
            sides = sorted(sides_of[fp.id], key=rank.__getitem__)
            if len(sides) == 2:
                barriers.append(Barrier(boxes[fp.id], (sides[0], sides[1])))
                continue
            if sides:
                members[sides[0]].append(boxes[fp.id])
                count = "one domain only" if len(sides) == 1 else f"{len(sides)} domains"
                issues.append(
                    issue(
                        "place.region-barrier",
                        f"the barrier {ref} has pins in {count}; it is placed inside {sides[0]}",
                        ref,
                    )
                )
                continue
        elif fp.id in domain_of:
            members[domain_of[fp.id]].append(boxes[fp.id])
            continue
        unassigned.append(ref)
        issues.append(
            issue(
                "place.region-unassigned",
                f"{ref} belongs to no domain (no net, or no --group matches it); it stays where it was",
                ref,
                "add a --group that matches it, or place it with --move",
            )
        )
    result = place_regions(
        regions, members, barriers, occupied=occupied, cutouts=cutouts, pitch=pitch, gap=gap, margin=margin
    )
    for row in result.barriers:
        if row.status == "inside":
            issues.append(
                issue(
                    "place.region-barrier",
                    f"the regions {row.sides[0]} and {row.sides[1]} that the barrier {refs[row.path]} joins "
                    f"do not touch; it is placed inside {row.sides[0]}",
                    refs[row.path],
                    "order the groups so the two domains are neighbouring bands, or give --region boxes "
                    "that touch",
                )
            )
    for row in result.regions:
        for path in row.unplaced:
            issues.append(
                issue(
                    "place.no-room",
                    f"the region {row.name} has no room for {refs[path]}; it stays where it was",
                    refs[path],
                    "enlarge the region, or place the part with --move",
                )
            )
    for row in result.barriers:
        if row.status == "unplaced":
            issues.append(
                issue(
                    "place.no-room",
                    f"no room for the barrier {refs[row.path]} on the boundary between {row.sides[0]} and "
                    f"{row.sides[1]}; it stays where it was",
                    refs[row.path],
                    "place it with --move",
                )
            )
    parts: dict[str, list[str]] = {name: [] for name in names}
    for fp_id, name in domain_of.items():
        parts[name].append(refs[fp_id])
    return RegionPlan(
        source=source,
        axis=axis,
        regions=regions,
        nets=domain_nets,
        parts={name: tuple(sorted(found)) for name, found in parts.items()},
        result=result,
        unassigned=tuple(unassigned),
        issues=issues,
    )


def crossings(
    plan: RegionPlan, design: Design, pads: Sequence[BoardPad]
) -> tuple[list[dict[str, Any]], list[Issue], Evidence]:
    """The open connections of the layout after the moves whose two ends lie in different regions, per
    pair of regions (in region order), and one ``place.region-crossing`` per pair."""
    report = connectivity(design, pads=pads)
    order = {region.name: index for index, region in enumerate(plan.regions)}
    found: dict[tuple[str, str], list[str]] = defaultdict(list)
    for net in report.nets:
        for link in net.open:
            a, b = region_of(plan.regions, link.a.position), region_of(plan.regions, link.b.position)
            if a is None or b is None or a == b:
                continue
            pair = (a, b) if order[a] < order[b] else (b, a)
            found[pair].append(net.name)
    rows: list[dict[str, Any]] = []
    issues: list[Issue] = []
    for pair in sorted(found, key=lambda key: (order[key[0]], order[key[1]])):
        nets = sorted(set(found[pair]))
        rows.append({"between": list(pair), "open": len(found[pair]), "nets": nets})
        issues.append(
            issue(
                "place.region-crossing",
                f"{len(found[pair])} open connection(s) cross between {pair[0]} and {pair[1]}: "
                f"{', '.join(nets)}",
                f"{pair[0]}|{pair[1]}",
                "a part in the wrong region pulls its nets across; check the groups",
            )
        )
    return rows, issues, report.evidence


def to_json(
    plan: RegionPlan, crossing_rows: list[dict[str, Any]], origin: Point, refs: Mapping[str, str]
) -> dict[str, Any]:
    """``result.regions``: boxes relative to the outline's top-left corner, as ``--region`` takes them."""
    rows: list[dict[str, Any]] = []
    by_name = {row.name: row for row in plan.result.regions}
    for region in plan.regions:
        row = by_name[region.name]
        box = region.bbox
        rows.append(
            {
                "name": region.name,
                "box": {
                    "x0": box.x0 - origin.x,
                    "y0": box.y0 - origin.y,
                    "x1": box.x1 - origin.x,
                    "y1": box.y1 - origin.y,
                },
                "nets": list(plan.nets.get(region.name, ())),
                "parts": list(plan.parts.get(region.name, ())),
                "placed": sorted(refs[path] for path in row.placed),
                "unplaced": sorted(refs[path] for path in row.unplaced),
                "area": row.area,
                "used": row.used,
                "fill_permille": row.fill_permille,
            }
        )
    return {
        "source": plan.source,
        "axis": plan.axis,
        "rows": rows,
        "barriers": [
            {"ref": refs[row.path], "sides": list(row.sides), "status": row.status}
            for row in plan.result.barriers
        ],
        "unassigned": sorted(plan.unassigned),
        "crossings": crossing_rows,
    }


def evidence(plan: RegionPlan) -> tuple[Evidence, ...]:
    """The evidence the strategy adds: its own rule, and the islands' when they gave the domains."""
    return (REGION_EVIDENCE, TIES_EVIDENCE) if plan.source == "islands" else (REGION_EVIDENCE,)


__all__ = ["RegionOptions", "RegionPlan", "crossings", "evidence", "parse_options", "plan_regions", "to_json"]
