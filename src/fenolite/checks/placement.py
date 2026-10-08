# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Placement rules and placement measures (capability placement, "Placement rules judged" and "Placement
measures"; capability verification-loop, "Placement rules stage"; change c0113; ``docs/placement.md``).

``judge`` judges the ``near`` rules of a design on the pad positions of a board: each part of a rule keeps
one of its selected pads within the rule's distance of a pad of the anchor, centre to centre, compared on
squared integers. ``measure`` gives the wire length of a placement (half perimeter and a Euclidean minimum
spanning tree per net) and an estimate of its congestion on a grid of square cells. ``placement_stage`` is
the ``placement.rules`` stage of ``fenolite check``, in both pipelines. ``judge_heights`` judges the height
limits of a design (change c0140): a part under a named rule area is at most the limit tall, its height
read by ``fenolite.model.board.outward_height`` and nothing else.

The module lives in ``checks`` because the stage runs it and ``checks`` may import only ``model``,
``geometry`` and ``backends.base``; ``place`` and ``build`` call it from the CLI. Keep-outs are not judged
here: ``placement.legality`` judges them. Nothing here reads a file, uses a clock or a float, and equal
inputs give equal outputs.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field

from fenolite.backends.base import BoardFrame, BoardPad, DesignRulesSource, PlacedExtent, ProjectSet
from fenolite.checks.codes import issue
from fenolite.checks.stages import StageResult, ran, skipped
from fenolite.core.coords import Point
from fenolite.core.errors import Issue
from fenolite.core.evidence import Evidence, Level
from fenolite.core.units import Nm, format_length
from fenolite.geometry import Arc as GeoArc
from fenolite.geometry import BBox, Circle, GeometryError, ceil_sqrt, floor_sqrt
from fenolite.geometry.rings import interiors_intersect
from fenolite.model.board import FootprintInstance, outward_height
from fenolite.model.design import Design
from fenolite.model.rules import HeightLimit, PadSelection, ProximityRule

STAGE = "placement.rules"
EVIDENCE = Evidence(Level.INFERRED)
"""The evidence of a judged placement rule: Fenolite's own definition, which no oracle judges."""
PATH_PROPERTY = "fenolite.path"
"""The component property that holds the component path on a board built by Fenolite."""
DEFAULT_EDGE = "Edge.Cuts"
DEFAULT_CLASS = "Default"
MIN_CELL: Nm = 2_000_000
"""The side of a congestion cell, unless the board is longer than ``MAX_CELLS`` such cells."""
MAX_CELLS = 128
MICROMETRE: Nm = 1_000
LISTED = 5
"""How many nets and how many cells a reply lists, whatever the board."""


def _mm(value: Nm) -> str:
    return f"{format_length(value)[:-2]} mm"


# --- the board ------------------------------------------------------------------------------------------


def board_box(design: Design) -> BBox | None:
    """The box of the board: of ``Board.outline`` when the model holds one, else of the graphics on the
    layers of kind ``edge`` (an arc by its exact box), else ``None``."""
    board = design.board
    if board is None:
        return None
    if board.outline is not None and board.outline.points:
        return BBox.of_points(board.outline.points)
    layers = {layer.name for layer in board.layers if layer.kind == "edge"} or {DEFAULT_EDGE}
    box: BBox | None = None
    for graphic in board.graphics:
        if graphic.layer not in layers or not graphic.points:
            continue
        found = BBox.of_points(graphic.points)
        try:
            if graphic.kind == "arc" and len(graphic.points) == 3:
                found = GeoArc(graphic.points[0], graphic.points[1], graphic.points[2]).bbox()
            elif graphic.kind == "circle" and len(graphic.points) == 2:
                found = Circle.from_kicad(graphic.points[0], graphic.points[1]).bbox()
        except (GeometryError, ValueError):
            pass  # a degenerate arc or circle counts by its points
        box = found if box is None else box.union(found)
    return box


@dataclass(frozen=True)
class _Layout:
    """The footprints of a board as the rules and the measures see them: the component path and the
    reference of each, its pads in the footprint's pad order, and which of them lie off the board."""

    box: BBox | None
    footprints: tuple[FootprintInstance, ...]
    path: Mapping[str, str]
    ref: Mapping[str, str]
    pads: Mapping[str, tuple[BoardPad, ...]]
    off: frozenset[str]

    def by_path(self, path: str) -> list[FootprintInstance]:
        return [fp for fp in self.footprints if self.path[fp.id] == path]


def _layout(design: Design, pads: Sequence[BoardPad]) -> _Layout:
    footprints = design.board.footprints if design.board is not None else ()
    components = {c.id: c for c in design.circuit.components}
    grouped: dict[str, list[BoardPad]] = {}
    for pad in pads:
        grouped.setdefault(pad.footprint_id, []).append(pad)
    order = {fp.id: {pad.id: n for n, pad in enumerate(fp.pads)} for fp in footprints}
    paths: dict[str, str] = {}
    refs: dict[str, str] = {}
    for fp in footprints:
        component = components.get(fp.component_id)
        own = grouped.get(fp.id, [])
        own.sort(key=lambda pad, fp_id=fp.id: order[fp_id].get(pad.pad_id, len(order[fp_id])))
        ref = next((pad.ref for pad in own if pad.ref), component.ref if component is not None else "")
        path = next((pad.path for pad in own if pad.path), "")
        if not path and component is not None:
            path = component.properties.get(PATH_PROPERTY, "") or component.path
        refs[fp.id] = ref or fp.id
        paths[fp.id] = path or ref or fp.id
    box = board_box(design)
    off = frozenset(fp.id for fp in footprints if box is not None and not box.contains_point(fp.position))
    return _Layout(
        box, tuple(footprints), paths, refs, {key: tuple(value) for key, value in grouped.items()}, off
    )


# --- rules ----------------------------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class PlacementRules:
    """The placement rules of a model: its proximity rules and its height limits (change c0140)."""

    proximity: tuple[ProximityRule, ...] = ()
    heights: tuple[HeightLimit, ...] = ()

    def __bool__(self) -> bool:
        return bool(self.proximity or self.heights)


def rules_of(model: Design | None) -> PlacementRules:
    """The placement rules of ``model``, the design that carries the rules layer (the ``.fenolite/`` model
    of a built project, or the built model); none for ``None`` or a model without a rules layer."""
    if model is None or model.rules is None:
        return PlacementRules()
    return PlacementRules(tuple(model.rules.proximity), tuple(model.rules.heights))


def empty_counts() -> dict[str, dict[str, int]]:
    """The counts of a run that judged nothing, by rule family."""
    return {"near": {"judged": 0, "failed": 0, "skipped": 0}}


@dataclass(frozen=True, slots=True)
class RuleReport:
    """What ``judge`` found: the issues, sorted by code, ``where`` and message, and the counts by rule
    family, one count per rule and part path."""

    issues: tuple[Issue, ...] = ()
    counts: Mapping[str, Mapping[str, int]] = field(default_factory=empty_counts)

    @property
    def judged(self) -> int:
        return sum(family.get("judged", 0) for family in self.counts.values())


def _selection_text(selection: PadSelection) -> str:
    if not selection.number:
        return selection.path
    index = "" if selection.index is None else f" (index {selection.index})"
    return f"pad {selection.number} of {selection.path}{index}"


@dataclass(frozen=True)
class _Resolved:
    """One selection on the board: its pads, or why it has none (``missing``), and the references of the
    footprints of its path that lie off the board."""

    pads: tuple[BoardPad, ...] = ()
    missing: str = ""
    off: tuple[str, ...] = ()


def _resolve(layout: _Layout, selection: PadSelection) -> _Resolved:
    footprints = layout.by_path(selection.path)
    if not footprints:
        return _Resolved(missing=f"the board holds no part {selection.path}")
    off = tuple(layout.ref[fp.id] for fp in footprints if fp.id in layout.off)
    found: list[BoardPad] = []
    for fp in footprints:
        own = layout.pads.get(fp.id, ())
        if selection.number:
            own = tuple(pad for pad in own if pad.number == selection.number)
            if not own:
                return _Resolved(missing=f"{layout.ref[fp.id]} has no pad {selection.number}")
            if selection.index is not None:
                if selection.index >= len(own):
                    return _Resolved(
                        missing=f"{layout.ref[fp.id]} has {len(own)} pad(s) numbered {selection.number}, "
                        f"so none at index {selection.index}"
                    )
                own = (own[selection.index],)
        elif not own:
            return _Resolved(missing=f"{layout.ref[fp.id]} has no pad")
        if fp.id not in layout.off:
            found += own
    return _Resolved(tuple(found), off=off)


def _distance2(a: Point, b: Point) -> int:
    return (a.x - b.x) ** 2 + (a.y - b.y) ** 2


def judge(design: Design, rules: PlacementRules, *, pads: Sequence[BoardPad]) -> RuleReport:
    """Judge the ``near`` rules of ``rules`` on the board of ``design``, whose pads in the board frame are
    ``pads`` (``BoardFrame.board_pads``).

    A part of a rule fails with one ``placement.too-far`` of the rule's severity when none of its selected
    pads is within the rule's distance of a selected pad of the anchor; the distance in the message is
    rounded up to the nanometre, so it is above the limit exactly when the rule fails. A selection that the
    board does not hold gives ``placement.rule-unresolved`` and a part off the board
    ``placement.rule-skipped``.
    """
    if not rules.proximity:
        return RuleReport()
    layout = _layout(design, pads)
    issues: list[Issue] = []
    counts = {"judged": 0, "failed": 0, "skipped": 0}

    def unresolved(rule: ProximityRule, selection: PadSelection, why: str) -> None:
        issues.append(
            issue(
                "placement.rule-unresolved",
                f"rule {rule.name}: {_selection_text(selection)} is not on the board: {why}",
                where=selection.path,
                hint="correct the near() call, or build the design again",
            )
        )

    def skipped_part(rule: ProximityRule, ref: str, side: str) -> None:
        issues.append(
            issue(
                "placement.rule-skipped",
                f"rule {rule.name}: {ref} lies off the board, so the rule is not judged for {side}",
                where=ref,
                hint="place the part on the board",
            )
        )

    for rule in rules.proximity:
        anchor: list[BoardPad] = []
        anchor_paths: set[str] = set()
        anchor_ok = True
        anchor_off: list[str] = []
        for selection in rule.anchor:
            found = _resolve(layout, selection)
            if found.missing:
                unresolved(rule, selection, found.missing)
                anchor_ok = False
                continue
            anchor += found.pads
            anchor_paths.add(selection.path)
            anchor_off += [ref for ref in found.off if ref not in anchor_off]
        if not anchor_ok:
            continue  # an unresolved anchor leaves its rule unjudged
        for ref in anchor_off:
            skipped_part(rule, ref, "it as an anchor")
        by_path: dict[str, list[PadSelection]] = {}
        for selection in rule.parts:
            by_path.setdefault(selection.path, []).append(selection)
        for path, selections in by_path.items():
            resolved = [(selection, _resolve(layout, selection)) for selection in selections]
            missing = [(selection, found) for selection, found in resolved if found.missing]
            if missing:
                for selection, found in missing:
                    unresolved(rule, selection, found.missing)
                continue
            off = sorted({ref for _, found in resolved for ref in found.off})
            own = [pad for _, found in resolved for pad in found.pads]
            if off or not own:
                for ref in off:
                    skipped_part(rule, ref, "it")
                counts["skipped"] += 1
                continue
            if not anchor:
                counts["skipped"] += 1  # every anchor part lies off the board, and was reported
                continue
            counts["judged"] += 1
            if path in anchor_paths:
                continue  # a path on both sides is at distance 0
            square, _, _, near_pad, own_pad = min(
                (_distance2(a.position, b.position), b.ref, b.number, b, a) for a in own for b in anchor
            )
            if square <= rule.within * rule.within:
                continue
            counts["failed"] += 1
            issues.append(
                issue(
                    "placement.too-far",
                    f"rule {rule.name}: {path} is {_mm(ceil_sqrt(square))} from {near_pad.ref}-"
                    f"{near_pad.number}, its nearest anchor pad (pad centres); the rule allows "
                    f"{_mm(rule.within)}",
                    severity=rule.severity,
                    where=own_pad.ref or path,
                    hint="move the part nearer, or change the distance of the near() call",
                )
            )
    issues.sort(key=lambda found: (found.code, found.where, found.message))
    return RuleReport(tuple(issues), {"near": counts})


# --- height limits (change c0140) -----------------------------------------------------------------------

HEIGHT_FACES: tuple[tuple[str, str], ...] = (("top", "F.Cu"), ("bottom", "B.Cu"))
"""The side of a footprint and the copper layer whose rule areas limit its height: the face rule of the
keep-outs of ``placement.legality`` (``H-K-PLACE-KEEPOUT``). An area on inner layers only judges no part."""
APPROXIMATE = " (approximate extent)"


def _component_paths(design: Design | None) -> dict[str, str]:
    """The component path of every footprint of ``design``, by footprint id: the path property of a board
    built by Fenolite, else the component's path, else its reference."""
    if design is None or design.board is None:
        return {}
    components = {c.id: c for c in design.circuit.components}
    found: dict[str, str] = {}
    for fp in design.board.footprints:
        component = components.get(fp.component_id)
        if component is not None:
            found[fp.id] = component.properties.get(PATH_PROPERTY, "") or component.path or component.ref
    return found


def heights_of(design: Design, model: Design | None) -> Mapping[str, Nm | None]:
    """The height of every footprint of ``design``, by footprint id (change c0140).

    A footprint that holds a body is measured on the board itself (a reading of Altium documents); one
    without is measured on the footprint of the same component path in ``model``, the ``.fenolite/`` model
    of a built project (a KiCad file holds no body); else its height is ``None``. Each height is
    ``outward_height`` of the one footprint picked: the bodies of the two are never mixed."""
    if design.board is None:
        return {}
    stored: dict[str, FootprintInstance] = {}
    if model is not None and model.board is not None:
        paths = _component_paths(model)
        by_id = {fp.id: fp for fp in model.board.footprints}
        for fp_id, path in sorted(paths.items()):
            stored.setdefault(path, by_id[fp_id])
    own_paths = _component_paths(design)
    found: dict[str, Nm | None] = {}
    for fp in design.board.footprints:
        if fp.bodies:
            found[fp.id] = outward_height(fp)
            continue
        other = stored.get(own_paths.get(fp.id, ""))
        found[fp.id] = outward_height(other) if other is not None else None
    return found


def _judged_when_unknown(fp: FootprintInstance) -> bool:
    """Whether a footprint without a known height is judged: not one marked ``board_only`` (a logo drawn in
    KiCad has no part in the script), nor one whose pads are all non-plated holes (a mounting hole)."""
    if "board_only" in fp.attributes:
        return False
    return not (fp.pads and all(pad.kind == "np_thru_hole" for pad in fp.pads))


def judge_heights(
    design: Design,
    limits: Sequence[HeightLimit],
    heights: Mapping[str, Nm | None],
    *,
    extents: Sequence[PlacedExtent],
) -> RuleReport:
    """Judge the height limits ``limits`` on the board of ``design`` (capability placement, "Height limits
    judged"; change c0140).

    ``heights`` is ``heights_of(design, model)`` and ``extents`` the board's ``BoardFrame.placed_extents``.
    A footprint is under an area named by a limit when the area's layers hold ``F.Cu`` and the footprint is
    on the top side, or ``B.Cu`` and the bottom side, and the interior of a ring of its own face meets the
    interior of the area's outline. A part taller than the limit gives ``placement.too-tall`` with the
    limit's severity, a judged part without a known height ``placement.height-unknown``, and a limit whose
    area the board does not hold ``placement.rule-unresolved``. A footprint marked ``dnp`` or off the board
    is not judged. The counts are those of the family ``height``, one per limit and footprint.
    """
    if not limits:
        return RuleReport((), {})
    board = design.board
    footprints = board.footprints if board is not None else ()
    keepouts = board.keepouts if board is not None else ()
    components = {c.id: c for c in design.circuit.components}
    by_id = {extent.footprint_id: extent for extent in extents}
    box = board_box(design)
    issues: list[Issue] = []
    counts = {"judged": 0, "failed": 0, "unknown": 0}

    def ref(fp: FootprintInstance) -> str:
        component = components.get(fp.component_id)
        return component.ref if component is not None and component.ref else fp.id

    for limit in limits:
        areas = [k for k in keepouts if k.name == limit.area]
        if not areas:
            issues.append(
                issue(
                    "placement.rule-unresolved",
                    f"height limit {limit.area}: the board holds no rule area named {limit.area}",
                    where=limit.area,
                    hint="draw the rule area with design.rule_area() or in KiCad, or correct the name",
                )
            )
            continue
        for fp in footprints:
            extent = by_id.get(fp.id)
            if extent is None or "dnp" in fp.attributes:
                continue
            if box is not None and not box.contains_point(fp.position):
                continue
            layer = dict(HEIGHT_FACES)[fp.side]
            under = any(
                layer in area.layers
                and len(area.outline) >= 3
                and any(interiors_intersect(ring, area.outline) for ring in extent.own)
                for area in areas
            )
            if not under:
                continue
            height = heights.get(fp.id)
            if height is None and not _judged_when_unknown(fp):
                continue
            counts["judged"] += 1
            note = APPROXIMATE if extent.source == "pads" else ""
            if height is None:
                counts["unknown"] += 1
                issues.append(
                    issue(
                        "placement.height-unknown",
                        f"{ref(fp)} lies under the area {limit.area}, limited to {_mm(limit.max)}, and has "
                        f"no known height{note}",
                        where=ref(fp),
                        hint="state the part's height with Part(..., height=...), or move it out of the area",
                    )
                )
            elif height > limit.max:
                counts["failed"] += 1
                issues.append(
                    issue(
                        "placement.too-tall",
                        f"{ref(fp)} is {_mm(height)} tall under the area {limit.area}, which allows "
                        f"{_mm(limit.max)}{note}",
                        severity=limit.severity,
                        where=ref(fp),
                        hint="move the part out of the area, or change the limit of height_limit()",
                    )
                )
    issues.sort(key=lambda found: (found.code, found.where, found.message))
    return RuleReport(tuple(issues), {"height": counts})


# --- measures -------------------------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class Congestion:
    """The congestion estimate of a placement: the cell side, the pitch it was given, how many tracks of
    that pitch one layer of a cell holds, the busiest cells, and how many cells need how many layers
    (``None`` twice without a usable pitch)."""

    cell: Nm
    pitch: Nm | None
    tracks_per_layer: int | None
    busiest: tuple[Mapping[str, int], ...]
    layers_needed: Mapping[int, int] | None

    def to_json(self) -> dict[str, object]:
        layers = self.layers_needed
        return {
            "cell": self.cell,
            "pitch": self.pitch,
            "tracks_per_layer": self.tracks_per_layer,
            "busiest": [dict(cell) for cell in self.busiest],
            "layers_needed": None if layers is None else {str(k): layers[k] for k in sorted(layers)},
        }


@dataclass(frozen=True, slots=True)
class Measures:
    """The wire length and the congestion of a placement, in integers (nanometres and counts)."""

    nets: int = 0
    hpwl: Nm = 0
    ratsnest: Nm = 0
    longest: tuple[Mapping[str, object], ...] = ()
    left_out: Mapping[str, int] = field(
        default_factory=lambda: {"zone_nets": 0, "one_pad_nets": 0, "off_board": 0}
    )
    congestion: Congestion | None = None

    def to_json(self) -> dict[str, object]:
        return {
            "nets": self.nets,
            "hpwl": self.hpwl,
            "ratsnest": self.ratsnest,
            "longest": [dict(entry) for entry in self.longest],
            "left_out": dict(self.left_out),
            "congestion": None if self.congestion is None else self.congestion.to_json(),
        }


def spanning_tree(points: Sequence[Point]) -> Nm:
    """The length of a Euclidean minimum spanning tree of ``points`` (Prim): squared distances are compared
    exactly and each edge is floored to the nanometre, so the sum is a lower bound of the true length.
    Every minimum spanning tree holds the same edge lengths, so the choice among equal trees changes
    nothing."""
    todo = sorted(set(points))
    if len(todo) < 2:
        return 0
    start = todo.pop(0)
    best = [_distance2(start, p) for p in todo]
    total = 0
    while todo:
        k = min(range(len(todo)), key=best.__getitem__)
        total += floor_sqrt(best[k])
        joined = todo.pop(k)
        best.pop(k)
        for i, p in enumerate(todo):
            d = _distance2(joined, p)
            if d < best[i]:
                best[i] = d
    return total


def _cell_side(box: BBox) -> Nm:
    longer = max(box.width, box.height)
    per = -(-longer // MAX_CELLS)
    return max(MIN_CELL, -(-per // MICROMETRE) * MICROMETRE)


def _grown(lo: int, hi: int, cell: Nm) -> tuple[int, int]:
    """The interval grown around the floor of its mid point to at least ``cell``."""
    if hi - lo >= cell:
        return lo, hi
    start = (lo + hi) // 2 - cell // 2
    return start, start + cell


def _congestion(box: BBox, nets: Sequence[tuple[BBox, Nm]], pitch: Nm | None) -> Congestion:
    cell = _cell_side(box)
    columns = max(1, -(-box.width // cell))
    rows = max(1, -(-box.height // cell))
    demand: dict[tuple[int, int], int] = {}
    for net_box, hpwl in nets:
        if hpwl <= 0:
            continue
        x0, x1 = _grown(net_box.x0 - box.x0, net_box.x1 - box.x0, cell)
        y0, y1 = _grown(net_box.y0 - box.y0, net_box.y1 - box.y0, cell)
        area = (x1 - x0) * (y1 - y0)
        for row in range(max(0, y0 // cell), min(rows - 1, (y1 - 1) // cell) + 1):
            high = min(y1, (row + 1) * cell) - max(y0, row * cell)
            if high <= 0:
                continue
            for column in range(max(0, x0 // cell), min(columns - 1, (x1 - 1) // cell) + 1):
                wide = min(x1, (column + 1) * cell) - max(x0, column * cell)
                if wide > 0:
                    share = hpwl * wide * high // area
                    demand[row, column] = demand.get((row, column), 0) + share
    tracks = {key: value // cell for key, value in demand.items() if value >= cell}
    ordered = sorted(tracks.items(), key=lambda item: (-item[1], item[0][0], item[0][1]))
    busiest = tuple(
        {"x": column * cell + cell // 2, "y": row * cell + cell // 2, "tracks": count}
        for (row, column), count in ordered[:LISTED]
    )
    per_layer: int | None = None
    layers: dict[int, int] | None = None
    if pitch is not None and 0 < pitch <= cell:
        per_layer = cell // pitch
        layers = {}
        for count in tracks.values():
            needed = -(-count // per_layer)
            layers[needed] = layers.get(needed, 0) + 1
        layers = dict(sorted(layers.items()))
    return Congestion(cell, pitch, per_layer, busiest, layers)


def measure(design: Design, *, pads: Sequence[BoardPad], pitch: Nm | None = None) -> Measures:
    """The wire length and the congestion of the placement of ``design``, from the pad positions ``pads``.

    The counted pads are those of the footprints on the board. A measured net holds at least two of them
    and no zone of the board. ``hpwl`` sums the half perimeter of each measured net's box and ``ratsnest``
    its spanning tree; ``longest`` lists the five nets of largest half perimeter. The congestion spreads
    each net's half perimeter uniformly over its box on a grid of square cells and counts the cell-long
    tracks a cell must carry; with ``pitch`` (track width plus clearance) it also says how many layers the
    cells need. It is an estimate for comparing placements of one board: the router decides.
    """
    layout = _layout(design, pads)
    board = design.board
    zones = board.zones if board is not None else ()
    zone_ids: set[str] = {zone.net_id for zone in zones if zone.net_id}
    names: dict[str, str] = {net.id: net.name for net in design.circuit.nets}
    points: dict[str, list[Point]] = {}
    for pad in pads:
        if pad.net_id is None:
            continue
        names.setdefault(pad.net_id, pad.net or pad.net_id)
        if pad.net:
            names[pad.net_id] = pad.net
        counted = points.setdefault(pad.net_id, [])
        if pad.footprint_id not in layout.off:
            counted.append(pad.position)
    left_out = {"zone_nets": 0, "one_pad_nets": 0, "off_board": len(layout.off)}
    entries: list[tuple[str, int, Nm, Nm, BBox]] = []
    for net_id, positions in points.items():
        if net_id in zone_ids:
            left_out["zone_nets"] += 1
        elif len(positions) < 2:
            left_out["one_pad_nets"] += 1
        else:
            net_box = BBox.of_points(positions)
            entries.append(
                (
                    names[net_id],
                    len(positions),
                    net_box.width + net_box.height,
                    spanning_tree(positions),
                    net_box,
                )
            )
    entries.sort(key=lambda entry: (entry[0], entry[1], entry[2], entry[3]))
    longest = tuple(
        {"net": name, "pads": count, "hpwl": hpwl, "ratsnest": tree}
        for name, count, hpwl, tree, _ in sorted(entries, key=lambda entry: (-entry[2], entry[0]))[:LISTED]
    )
    congestion = (
        None if layout.box is None else _congestion(layout.box, [(e[4], e[2]) for e in entries], pitch)
    )
    return Measures(
        nets=len(entries),
        hpwl=sum(entry[2] for entry in entries),
        ratsnest=sum(entry[3] for entry in entries),
        longest=longest,
        left_out=left_out,
        congestion=congestion,
    )


# --- the stage ------------------------------------------------------------------------------------------


def default_pitch(design: Design) -> Nm | None:
    """The track width plus the clearance of the net class ``Default`` of ``design``, or ``None`` when the
    design has no such class or the class lacks one of the two."""
    for netclass in design.circuit.netclasses:
        if netclass.name == DEFAULT_CLASS:
            if netclass.track_width is None or netclass.clearance is None:
                return None
            return netclass.track_width + netclass.clearance
    return None


def placement_stage(
    design: Design | None,
    *,
    model: Design | None,
    built: bool,
    frame: BoardFrame | None,
    rules_source: DesignRulesSource | None,
    project: ProjectSet,
    evidence: Evidence,
) -> StageResult:
    """The ``placement.rules`` stage: the ``near`` rules of a built project (``model`` is its ``.fenolite/``
    model) judged on the board model of the run, and the measures of every board. ``frame`` gives the pads
    and ``rules_source`` the class ``Default`` for the pitch; ``evidence`` is the evidence of the reading.
    No tool runs, and nothing is written."""
    if design is None:
        return skipped(STAGE, "read-refused")
    if frame is None:
        return skipped(STAGE, "no-frame")
    pads = frame.board_pads(design)
    pitch = None
    if rules_source is not None:
        pitch = default_pitch(rules_source.design_rules(design, project).design)
    rules = rules_of(model)
    report = judge(design, rules, pads=pads) if built else RuleReport()
    families = {family: dict(counts) for family, counts in report.counts.items()}
    issues = list(report.issues)
    judged = report.judged
    if built and rules.heights:
        # the extents are asked for only when a height limit is judged (change c0140)
        heights = judge_heights(
            design, rules.heights, heights_of(design, model), extents=frame.placed_extents(design)
        )
        families.update({family: dict(counts) for family, counts in heights.counts.items()})
        issues = sorted(
            [*issues, *heights.issues], key=lambda found: (found.code, found.where, found.message)
        )
        judged += heights.judged
    measures = measure(design, pads=pads, pitch=pitch)
    level = Evidence.combine(EVIDENCE, evidence) if judged else evidence
    summary = {"rules": families, "measures": measures.to_json()}
    return ran(STAGE, tuple(issues), level, summary)


__all__ = [
    "EVIDENCE",
    "STAGE",
    "Congestion",
    "Measures",
    "PlacementRules",
    "RuleReport",
    "board_box",
    "default_pitch",
    "empty_counts",
    "heights_of",
    "judge",
    "judge_heights",
    "measure",
    "placement_stage",
    "rules_of",
    "spanning_tree",
]
