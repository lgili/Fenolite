# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The practice checks of ``fenolite analyze``: connectivity with every pour in its state, dead copper,
decoupling distances, copper under part bodies and the width of thermal reliefs (change c0204; capability
board-analyses, "Practice checks"; user guide ``docs/analyses.md``, "Practice checks").

Each check reports facts. An error is reported only against a row of the user's requirements file; the
warnings of ``connectivity`` and ``dead`` name copper that is open or joined to nothing, a fact whatever the
requirements. Every row says which copper it used (``analysis.pour``: ``saved_fill``, ``simulated`` or
``outline``).
"""

from __future__ import annotations

import fnmatch
import heapq
import re
from collections import defaultdict
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from decimal import localcontext
from math import isqrt

from fenolite.analysis.codes import issue
from fenolite.analysis.copper import CopperShape, net_copper
from fenolite.analysis.crossings import DIGITS, Cut, CutLine
from fenolite.analysis.current import capacity_ma
from fenolite.analysis.pour import DEFAULT_GRID_NM, Cell, PourCopper, covers, layer_matches, ring_cells
from fenolite.analysis.requirements import NetSelector, Requirements
from fenolite.backends.base import BoardPad, PlacedExtent
from fenolite.core.coords import Point
from fenolite.core.errors import Issue
from fenolite.core.evidence import Evidence, Level
from fenolite.core.units import Nm
from fenolite.geometry import SpatialIndex, Thick, thick_bbox, thick_gap_floor, thick_touch, touch_groups
from fenolite.geometry.transform import Transform
from fenolite.model.board import Board
from fenolite.model.design import Design

CONNECTIVITY_EVIDENCE = Evidence(Level.INFERRED, hypotheses=("H-G-PRACTICE-POUR", "H-G-PRACTICE-GROUPS"))
DEAD_EVIDENCE = Evidence(Level.INFERRED, hypotheses=("H-G-PRACTICE-POUR", "H-G-PRACTICE-DEAD"))
DECOUPLING_EVIDENCE = Evidence(Level.INFERRED, hypotheses=("H-G-PRACTICE-DECOUPLING",))
BODIES_EVIDENCE = Evidence(Level.INFERRED, hypotheses=("H-G-PRACTICE-POUR", "H-G-PRACTICE-BODIES"))
RELIEF_EVIDENCE = Evidence(Level.INFERRED, hypotheses=("H-G-PRACTICE-RELIEF",))
CAPACITOR = re.compile(r"C[0-9]")
"""A capacitor is a part whose reference is ``C`` followed by a digit (``H-G-PRACTICE-DECOUPLING``)."""

_Key = tuple[str, str, str]
"""An item of the copper: ``(kind, entity_id, where)``; an island of a simulated pour is ``("island", "",
"<n>")``."""


@dataclass(frozen=True, slots=True)
class PracticeReport:
    rows: tuple[object, ...] = ()
    issues: tuple[Issue, ...] = ()
    evidence: Evidence = CONNECTIVITY_EVIDENCE
    summary: Mapping[str, int] = field(default_factory=lambda: {})


def _level(pour: PourCopper, pads: Sequence[BoardPad] | None, evidence: Evidence) -> Evidence:
    unsure = bool(pour.copper.unsupported) or pads is None
    return Evidence(Level.UNVERIFIED, hypotheses=evidence.hypotheses) if unsure else evidence


# --- groups of copper -----------------------------------------------------------------------------------


@dataclass(slots=True)
class _Item:
    key: _Key
    shapes: list[tuple[str, Thick]]


def fill_names(shapes: Sequence[CopperShape]) -> dict[int, str]:
    """The name of each fill shape by its index: the zone's locator, ``#`` and the fill's number in the zone
    among the fills that stand."""
    count: dict[str, int] = defaultdict(int)
    names: dict[int, str] = {}
    for number, shape in enumerate(shapes):
        if shape.kind == "fill":
            names[number] = f"{shape.where}#{count[shape.entity_id]}"
            count[shape.entity_id] += 1
    return names


def _items(shapes: Sequence[CopperShape]) -> list[_Item]:
    """The items of a net: the shapes of one pad, via, track or arc joined; one item per fill polygon."""
    grouped: dict[_Key, _Item] = {}
    out: list[_Item] = []
    names = fill_names(shapes)
    for number, shape in enumerate(shapes):
        if shape.kind == "fill":
            out.append(_Item(("fill", shape.entity_id, names[number]), [(shape.layer, shape.shape)]))
            continue
        key = (shape.kind, shape.entity_id, shape.where)
        if key not in grouped:
            grouped[key] = _Item(key, [])
        grouped[key].shapes.append((shape.layer, shape.shape))
    return [grouped[key] for key in sorted(grouped)] + out


def _groups(pour: PourCopper, net: str) -> list[tuple[list[_Item], list[int]]]:
    """The groups of the copper of ``net``: the items joined where they touch on a layer, and the islands of
    the simulated pours joined to the items that cover one of their cells. Each group lists its items and
    the indexes of its islands."""
    items = _items(pour.copper.by_net.get(net, ()))
    roots = touch_groups([item.shapes for item in items])
    parent = list(range(len(items)))

    def find(index: int) -> int:
        while parent[index] != index:
            parent[index] = parent[parent[index]]
            index = parent[index]
        return index

    for index, root in enumerate(roots):
        a, b = find(index), find(root)
        if a != b:
            parent[max(a, b)] = min(a, b)
    position = {item.key: index for index, item in enumerate(items)}
    islands = [i for i, island in enumerate(pour.islands) if island.net == net]
    island_root: dict[int, int] = {}
    for number in islands:
        joined = sorted(position[key] for key in pour.islands[number].joins if key in position)
        if not joined:
            continue
        first = find(joined[0])
        for other in joined[1:]:
            a, b = find(first), find(other)
            if a != b:
                parent[max(a, b)] = min(a, b)
        island_root[number] = joined[0]
    by_root: dict[int, tuple[list[_Item], list[int]]] = {}
    for index, item in enumerate(items):
        by_root.setdefault(find(index), ([], []))[0].append(item)
    for number, member in island_root.items():
        by_root[find(member)][1].append(number)
    return [by_root[root] for root in sorted(by_root)]


@dataclass(frozen=True, slots=True)
class NetGroups:
    """A net and the pads of each group of its copper, the groups sorted; ``copper`` holds the states of its
    zone layers and ``split`` is true with two or more groups that hold pads."""

    net: str
    groups: tuple[tuple[str, ...], ...]
    split: bool
    copper: tuple[str, ...]


def analyze_groups(design: Design, *, pads: Sequence[BoardPad] | None, pour: PourCopper) -> PracticeReport:
    """The kind ``connectivity``: one row per net that owns a zone or whose copper falls into more than one
    group of pads; ``analysis.net-split`` (warning) for each split net."""
    zoned = {z.net for z in pour.zones}
    rows: list[NetGroups] = []
    issues: list[Issue] = []
    for net in sorted(pour.copper.by_net):
        groups = tuple(
            sorted(
                found
                for items, _ in _groups(pour, net)
                if (found := tuple(sorted(item.key[2] for item in items if item.key[0] == "pad")))
            )
        )
        split = len(groups) > 1
        if not split and net not in zoned:
            continue
        states = pour.states_of(net)
        rows.append(NetGroups(net, groups, split, states))
        if split:
            alone = min(groups, key=lambda g: (len(g), g))
            issues.append(
                issue(
                    "analysis.net-split",
                    f"the copper of {net} falls into {len(groups)} groups of pads"
                    f"{' (' + ', '.join(states) + ')' if states else ''}; {', '.join(alone)} is apart",
                    where=net,
                    hint="join the groups with a track, or move the cut-out or keep-out that separates them",
                )
            )
    summary = {
        "nets": len(rows),
        "split": sum(1 for row in rows if row.split),
        "simulated": sum(1 for z in pour.zones if z.state == "simulated"),
        "outline": sum(1 for z in pour.zones if z.state == "outline"),
    }
    return PracticeReport(tuple(rows), tuple(issues), _level(pour, pads, CONNECTIVITY_EVIDENCE), summary)


# --- dead copper ----------------------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class DeadRow:
    """Copper joined to nothing useful: ``reason`` is ``island`` (a fill polygon whose group holds no pad) or
    ``far`` (an item farther than the distance from every pad of its net; ``distance`` is ``None`` when the
    net has no pad); ``copper`` is the state of the zone layer of a fill."""

    net: str
    kind: str
    where: str
    layer: str
    reason: str
    distance: int | None = None
    copper: str | None = None


def analyze_dead(
    design: Design, *, pads: Sequence[BoardPad] | None, pour: PourCopper, distance: Nm | None = None
) -> PracticeReport:
    """The kind ``dead``: fill islands whose group holds no pad (``analysis.copper-dead``, warning), and with
    ``distance`` every track, arc, via and fill polygon farther than it from every pad of its net
    (``analysis.copper-far``, warning). Islands of a simulated pour joined to nothing are dropped by the
    simulation and counted on its zone layer."""
    rows: list[DeadRow] = []
    issues: list[Issue] = []
    for net in sorted(pour.copper.by_net):
        for items, islands in _groups(pour, net):
            if islands or any(item.key[0] == "pad" for item in items):
                continue
            for item in items:
                if item.key[0] != "fill":
                    continue
                layer = item.shapes[0][0]
                state = pour.state_of(item.key[1], layer)
                rows.append(DeadRow(net, "fill", item.key[2], layer, "island", copper=state))
                issues.append(
                    issue(
                        "analysis.copper-dead",
                        f"a fill island of {net} on {layer} ({item.key[2]}) is joined to no pad of its net",
                        where=item.key[2],
                        hint="remove the island (refill with island removal), or join it with a via",
                    )
                )
        if distance is None:
            continue
        shapes = pour.copper.by_net[net]
        pad_shapes = [s.shape for s in shapes if s.kind == "pad"]
        seen: set[tuple[str, str]] = set()
        names = fill_names(shapes)
        for number, shape in enumerate(shapes):
            if shape.kind == "pad":
                continue
            where = names[number] if shape.kind == "fill" else shape.where
            if (where, shape.layer) in seen or (shape.kind == "via" and (where, "") in seen):
                continue
            seen.add((where, "" if shape.kind == "via" else shape.layer))
            gap = min((thick_gap_floor(shape.shape, p) for p in pad_shapes), default=None)
            if gap is not None and gap <= distance:
                continue
            state = pour.state_of(shape.entity_id, shape.layer) if shape.kind == "fill" else None
            rows.append(DeadRow(net, shape.kind, where, shape.layer, "far", gap, state))
            far = "no pad" if gap is None else f"{gap} nm from the nearest pad"
            issues.append(
                issue(
                    "analysis.copper-far",
                    f"the {shape.kind} {where} of {net} on {shape.layer} has {far}, beyond {distance} nm",
                    where=where,
                    hint="remove the copper or bring it to the pads it serves",
                )
            )
    summary = {
        "islands": sum(1 for row in rows if row.reason == "island"),
        "far": sum(1 for row in rows if row.reason == "far"),
        "dropped": sum(z.dropped for z in pour.zones),
    }
    return PracticeReport(tuple(rows), tuple(issues), _level(pour, pads, DEAD_EVIDENCE), summary)


# --- decoupling -----------------------------------------------------------------------------------------


def _round_distance(a: Point, b: Point) -> int:
    d2 = (a.x - b.x) ** 2 + (a.y - b.y) ** 2
    return (isqrt(4 * d2) + 1) // 2


def _anchors(design: Design, pads: Sequence[BoardPad]) -> dict[_Key, tuple[Point, ...]]:
    board = design.board
    assert board is not None
    found: dict[_Key, tuple[Point, ...]] = {}
    for track in board.tracks:
        found["track", track.id, ""] = (track.start, track.end)
    for arc in board.arcs:
        found["arc", arc.id, ""] = (arc.start, arc.end)
    for via in board.vias:
        found["via", via.id, ""] = (via.position,)
    for record in pads:
        found["pad", record.pad_id, ""] = (record.position,)
    return found


def _steps(
    design: Design, pour: PourCopper, pads: Sequence[BoardPad], net: str
) -> dict[Point, dict[Point, int]]:
    """The straight steps between the anchors of the copper of ``net`` that lie on one item."""
    anchors = _anchors(design, pads)
    items = _items(pour.copper.by_net.get(net, ()))
    points: dict[int, set[Point]] = defaultdict(set)
    own: list[tuple[Point, int]] = []
    for index, item in enumerate(items):
        for point in anchors.get((item.key[0], item.key[1], ""), ()):
            points[index].add(point)
            own.append((point, index))
    boxes = SpatialIndex[int].build(
        (thick_bbox(shape), i) for i, item in enumerate(items) for _, shape in item.shapes
    )
    for point, index in own:
        layers = {layer for layer, _ in items[index].shapes}
        probe = Thick((point,), 1)
        for other in set(boxes.query(thick_bbox(probe))):
            if other != index and any(
                layer in layers and covers(shape, point) for layer, shape in items[other].shapes
            ):
                points[other].add(point)
    edges: dict[Point, dict[Point, int]] = defaultdict(dict)
    for held in points.values():
        ordered = sorted(held)
        for i, a in enumerate(ordered):
            for b in ordered[i + 1 :]:
                d = _round_distance(a, b)
                if d < edges[a].get(b, d + 1):
                    edges[a][b] = edges[b][a] = d
    return edges


def _walk(
    edges: Mapping[Point, Mapping[Point, int]], start: Point, goal: Point | None = None
) -> tuple[dict[Point, int], dict[Point, Point]]:
    best: dict[Point, int] = {start: 0}
    before: dict[Point, Point] = {}
    queue = [(0, start)]
    while queue:
        d, at = heapq.heappop(queue)
        if d > best.get(at, d):
            continue
        if at == goal:
            break
        for nxt, step in edges.get(at, {}).items():
            if d + step < best.get(nxt, d + step + 1) or (
                d + step == best.get(nxt) and nxt in before and at < before[nxt]
            ):
                best[nxt] = d + step
                before[nxt] = at
                heapq.heappush(queue, (d + step, nxt))
    return best, before


def copper_distances(
    design: Design, pour: PourCopper, pads: Sequence[BoardPad], net: str, start: Point
) -> dict[Point, int]:
    """The distance along the copper of ``net`` from ``start`` to every anchor it reaches: the shortest chain
    of straight steps between points that lie on one copper item (the anchors of the items: a pad's position,
    a via's, the ends of a track or an arc). Exact along a straight track, a lower bound through a pad, an
    arc or a pour."""
    return _walk(_steps(design, pour, pads, net), start)[0]


def copper_path(
    design: Design, pour: PourCopper, pads: Sequence[BoardPad], net: str, start: Point, goal: Point
) -> tuple[tuple[Point, ...], int] | None:
    """The points of the shortest chain of ``copper_distances`` from ``start`` to ``goal``, both included,
    and its length; ``None`` when no copper of ``net`` joins them (change c0213)."""
    best, before = _walk(_steps(design, pour, pads, net), start, goal)
    if goal not in best:
        return None
    points = [goal]
    while points[-1] != start:
        points.append(before[points[-1]])
    return tuple(reversed(points)), best[goal]


@dataclass(frozen=True, slots=True)
class DecouplingRow:
    """A supply pin (``REF-PIN``, a pin of type power input) and its nearest capacitor pad on the same net:
    ``capacitor`` (``REF-PIN`` or ``None``), ``distance`` along copper (``None`` when no copper joins them),
    ``straight`` (the straight distance), ``ret`` (the part's pad on the net of the capacitor's other pad)
    and ``loop_area_nm2`` (the area of the polygon pin, capacitor, capacitor's other pad, return pad)."""

    pin: str
    net: str
    capacitor: str | None
    distance: int | None
    straight: int | None
    ret: str | None = None
    loop_area_nm2: int | None = None
    limit: int | None = None


def _pad_name(record: BoardPad) -> str:
    holder = record.ref or record.footprint_id
    return f"{holder}-{record.number}" if record.number else holder


def analyze_decoupling(
    design: Design,
    *,
    pads: Sequence[BoardPad] | None,
    pour: PourCopper | None = None,
    requirements: Requirements | None = None,
) -> PracticeReport:
    """The kind ``decoupling``: one row per pad of a power-input pin. A ``[[decoupling]]`` row that matches
    the part makes a distance beyond ``max_distance_nm``, or no capacitor, ``analysis.decoupling-far``
    (error). Without ``pour`` the stored fills are the copper of the zones."""
    issues: list[Issue] = []
    if pour is None:
        pour = PourCopper(DEFAULT_GRID_NM, net_copper(design, pads=pads))
    if pads is None or design.board is None:
        issues.append(
            issue("analysis.input-missing", "no pad records: the decoupling is not measured", where="pads")
        )
        return PracticeReport(
            (), tuple(issues), Evidence(Level.UNVERIFIED, hypotheses=DECOUPLING_EVIDENCE.hypotheses)
        )
    by_ref: dict[str, list[BoardPad]] = defaultdict(list)
    for record in pads:
        if record.ref:
            by_ref[record.ref].append(record)
    rows: list[DecouplingRow] = []
    caps = {ref: held for ref, held in by_ref.items() if CAPACITOR.match(ref)}
    rules = requirements.decoupling if requirements is not None else ()
    for component in sorted(design.circuit.components, key=lambda c: c.ref):
        supply = [pin for pin in component.pins if pin.etype == "power_in"]
        if not supply or component.ref not in by_ref:
            continue
        own = by_ref[component.ref]
        limits = [rule.max_distance_nm for rule in rules if fnmatch.fnmatchcase(component.ref, rule.parts)]
        limit = min(limits) if limits else None
        for pin in sorted(supply, key=lambda p: p.number):
            numbers = component.pads_of(pin.number)
            for record in sorted((r for r in own if r.number in numbers), key=_pad_name):
                if record.net is None:
                    continue
                reach = copper_distances(design, pour, pads, record.net, record.position)
                candidates: list[tuple[int, int, str, BoardPad]] = []
                for held in caps.values():
                    for cap in held:
                        if cap.net != record.net:
                            continue
                        along = reach.get(cap.position)
                        straight = _round_distance(record.position, cap.position)
                        rank = along if along is not None else 1 << 62
                        candidates.append((rank, straight, _pad_name(cap), cap))
                row = _decoupling_row(
                    record, sorted(candidates, key=lambda c: (c[0], c[1], c[2])), own, by_ref, limit
                )
                rows.append(row)
                if limit is not None and (row.distance is None or row.distance > limit):
                    found = (
                        "no capacitor joined by copper"
                        if row.distance is None
                        else f"its nearest capacitor {row.capacitor} {row.distance} nm away along copper"
                    )
                    issues.append(
                        issue(
                            "analysis.decoupling-far",
                            f"the supply pin {row.pin} ({row.net}) has {found}, beyond {limit} nm",
                            where=row.pin,
                            hint="place the capacitor next to the pin and route the pin to it first",
                        )
                    )
    summary = {"pins": len(rows), "far": sum(1 for i in issues if i.code == "analysis.decoupling-far")}
    return PracticeReport(tuple(rows), tuple(issues), _level(pour, pads, DECOUPLING_EVIDENCE), summary)


def _decoupling_row(
    record: BoardPad,
    candidates: Sequence[tuple[int, int, str, BoardPad]],
    own: Sequence[BoardPad],
    by_ref: Mapping[str, Sequence[BoardPad]],
    limit: int | None,
) -> DecouplingRow:
    name, net = _pad_name(record), record.net or ""
    if not candidates:
        return DecouplingRow(name, net, None, None, None, limit=limit)
    rank, straight, cap_name, cap = candidates[0]
    along = None if rank == 1 << 62 else rank
    others = [p for p in by_ref.get(cap.ref, ()) if p.pad_id != cap.pad_id and p.net and p.net != net]
    for other in sorted(others, key=_pad_name):
        back = next((p for p in sorted(own, key=_pad_name) if p.net == other.net), None)
        if back is None:
            continue
        ring = (record.position, cap.position, other.position, back.position)
        twice = sum(ring[k].x * ring[(k + 1) % 4].y - ring[(k + 1) % 4].x * ring[k].y for k in range(4))
        return DecouplingRow(name, net, cap_name, along, straight, _pad_name(back), abs(twice) // 2, limit)
    return DecouplingRow(name, net, cap_name, along, straight, limit=limit)


# --- copper under bodies --------------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class BodyRow:
    """The copper of the class of a ``[[body_copper]]`` row inside the plan view of one part on one layer:
    ``plan`` is ``body`` (the outlines of the part's bodies) or ``courtyard``."""

    requirement: str
    part: str
    plan: str
    layer: str
    nets: tuple[str, ...]
    items: tuple[str, ...]
    copper: tuple[str, ...] = ()


def plan_views(
    board: Board, extents: Sequence[PlacedExtent] | None
) -> dict[str, tuple[str, list[tuple[Point, ...]]]]:
    """The plan view of each footprint by id: the outlines of its bodies placed on the board (``body``), else
    its courtyard on its own side (``courtyard``)."""
    found: dict[str, tuple[str, list[tuple[Point, ...]]]] = {}
    courtyards = {extent.footprint_id: extent.own for extent in extents or ()}
    for footprint in board.footprints:
        frame = Transform.placement(footprint.position, footprint.rotation)
        rings = [
            tuple(frame.apply(p) for p in body.outline) for body in footprint.bodies if len(body.outline) >= 3
        ]
        if rings:
            found[footprint.id] = ("body", rings)
        elif courtyards.get(footprint.id):
            found[footprint.id] = (
                "courtyard",
                [tuple(ring) for ring in courtyards[footprint.id] if len(ring) >= 3],
            )
    return found


def analyze_bodies(
    design: Design,
    *,
    pads: Sequence[BoardPad] | None,
    pour: PourCopper,
    extents: Sequence[PlacedExtent] | None,
    requirements: Requirements | None,
) -> PracticeReport:
    """The kind ``bodies``: for each ``[[body_copper]]`` row, each part it names and each layer it forbids,
    the copper of the nets of its class inside the part's plan view, the part's own pads left out; copper
    found is ``analysis.body-copper`` (error)."""
    board = design.board
    rules = requirements.body_copper if requirements is not None else ()
    issues: list[Issue] = []
    if board is None or not rules:
        issues.append(
            issue(
                "analysis.input-missing",
                "no [[body_copper]] row in the requirements: no class and no part is selected",
                where="body_copper",
                hint="add a [[body_copper]] row with netclass, parts and layers",
            )
        )
        return PracticeReport((), tuple(issues), BODIES_EVIDENCE)
    views = plan_views(board, extents)
    pad_ids = {fp.id: {pad.id for pad in fp.pads} for fp in board.footprints}
    refs = {c.id: c.ref for c in design.circuit.components}
    nets = {net.name: net for net in design.circuit.nets}
    rows: list[BodyRow] = []
    for number, rule in enumerate(rules):
        selector = NetSelector(netclass=rule.netclass)
        chosen = sorted(name for name, net in nets.items() if selector.matches(net, design.circuit))
        layers = [layer for layer in pour.copper.layers if layer_matches(rule.layers, layer)]
        parts = sorted(
            (refs.get(fp.component_id, ""), fp.id)
            for fp in board.footprints
            if fnmatch.fnmatchcase(refs.get(fp.component_id, ""), rule.parts)
        )
        for ref, footprint_id in parts:
            if footprint_id not in views:
                issues.append(
                    issue(
                        "analysis.input-missing",
                        f"{ref} has no body outline and no courtyard: its plan view is unknown",
                        where=ref,
                    )
                )
                continue
            plan, rings = views[footprint_id]
            own = pad_ids[footprint_id]
            regions = [Thick(ring, 0, filled=True) for ring in rings]
            cells: set[Cell] = set()
            for ring in rings:
                cells |= ring_cells(ring, pour.grid)
            for layer in layers:
                found_items: list[str] = []
                found_nets: set[str] = set()
                for name in chosen:
                    for shape in pour.copper.by_net.get(name, ()):
                        if shape.entity_id in own or shape.layer != layer:
                            continue
                        if any(thick_touch(shape.shape, r) for r in regions):
                            found_items.append(shape.where)
                            found_nets.add(name)
                    for island in pour.islands:
                        if island.net == name and island.layer == layer and island.cells & cells:
                            found_items.extend(island.zones)
                            found_nets.add(name)
                if not found_items:
                    continue
                states = tuple(sorted({s for n in found_nets for s in pour.states_of(n)}))
                row = BodyRow(
                    f"body_copper[{number}]",
                    ref,
                    plan,
                    layer,
                    tuple(sorted(found_nets)),
                    tuple(sorted(set(found_items))),
                    states,
                )
                rows.append(row)
                issues.append(
                    issue(
                        "analysis.body-copper",
                        f"copper of the class {rule.netclass} ({', '.join(row.nets)}) lies under {ref} on "
                        f"{layer}: {', '.join(row.items)} ({plan})",
                        where=ref,
                        hint=f"route the class around {ref} on {layer}, or move the part",
                    )
                )
    summary = {"rows": len(rows)}
    return PracticeReport(tuple(rows), tuple(issues), _level(pour, pads, BODIES_EVIDENCE), summary)


# --- thermal reliefs ------------------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class ReliefRow:
    """A pad joined to a zone by thermal relief: the ring at the pad's edge (its copper box grown by half the
    thermal gap), the ``spokes`` of copper that cross it and their total ``width``, both ``None`` when the
    zone layer is not ``saved_fill``; the current and the capacity of that width when a ``[[current]]`` row
    and a copper thickness give them."""

    pad: str
    net: str
    zone: str
    layer: str
    copper: str
    spokes: int | None
    width: int | None
    milliamps: int | None = None
    capacity_ma: int | None = None


def _thickness(board: Board, layer: str, given: Mapping[str, Nm] | None) -> Nm | None:
    if given is not None:
        if layer in given:
            return given[layer]
        if "*" in given:
            return given["*"]
    if board.stackup is not None:
        for entry in board.stackup.layers:
            if entry.kind == "copper" and entry.name == layer and entry.thickness > 0:
                return entry.thickness
    return None


def _ring(record: BoardPad, layer: str, grow: int) -> tuple[Point, ...] | None:
    boxes = [
        thick_bbox(Thick(entry.core, entry.width, entry.filled))
        for entry in record.copper
        if entry.layer == layer
    ]
    if not boxes:
        return None
    x0, y0 = min(b.x0 for b in boxes) - grow, min(b.y0 for b in boxes) - grow
    x1, y1 = max(b.x1 for b in boxes) + grow, max(b.y1 for b in boxes) + grow
    return (Point(x0, y0), Point(x1, y0), Point(x1, y1), Point(x0, y1))


def _crossing(ring: tuple[Point, ...], fills: Sequence[tuple[Point, ...]]) -> tuple[int, int]:
    """The number of spans of fill copper along the four sides of ``ring`` and their total length."""
    spokes = width = 0
    sides: list[tuple[list[tuple[int, int]], int]] = []
    with localcontext() as context:
        context.prec = DIGITS
        for k in range(4):
            line = CutLine(Cut("", ring[k], ring[(k + 1) % 4]))
            spans: list[tuple[int, int]] = []
            for fill in fills:
                for span in line.inside(fill):
                    placed = line.along(span)
                    if placed is not None and placed[1] > placed[0]:
                        spans.append(placed)
            merged: list[tuple[int, int]] = []
            for start, end in sorted(spans):
                if merged and start <= merged[-1][1]:
                    merged[-1] = (merged[-1][0], max(merged[-1][1], end))
                else:
                    merged.append((start, end))
            spokes += len(merged)
            width += sum(end - start for start, end in merged)
            sides.append((merged, line.length))
    # a span that reaches a corner goes on along the next side: it is one spoke
    for k, (merged, length) in enumerate(sides):
        following = sides[(k + 1) % 4][0]
        if merged and merged[-1][1] == length and following and following[0][0] == 0 and spokes > 1:
            spokes -= 1
    return spokes, width


def analyze_relief(
    design: Design,
    *,
    pads: Sequence[BoardPad] | None,
    pour: PourCopper,
    requirements: Requirements | None = None,
    copper_thickness: Mapping[str, Nm] | None = None,
) -> PracticeReport:
    """The kind ``relief``: one row per pad joined by thermal relief to a zone of its net. A ``[[current]]``
    row of the pad's net and a copper thickness give the capacity of the spokes; a capacity below the row's
    current is ``analysis.relief-exceeded`` (error)."""
    board = design.board
    issues: list[Issue] = []
    if board is None or pads is None:
        return PracticeReport((), (), Evidence(Level.UNVERIFIED, hypotheses=RELIEF_EVIDENCE.hypotheses))
    model_pads = {pad.id: pad for fp in board.footprints for pad in fp.pads}
    zones = {zone.id: zone for zone in board.zones}
    nets = {net.name: net for net in design.circuit.nets}
    outer = pour.copper.outer or ()
    rows: list[ReliefRow] = []
    missing = False
    for state in sorted(pour.zones, key=lambda z: (z.where, z.layer)):
        zone = zones[state.zone_id]
        for record in sorted(pads, key=_pad_name):
            if record.net != state.net or not any(e.layer == state.layer for e in record.copper):
                continue
            if not covers(Thick(tuple(zone.outline), 0, filled=True), record.position):
                continue
            pad = model_pads.get(record.pad_id)
            connection = (pad.zone_connection if pad is not None else None) or zone.settings.connection
            if connection == "thru_hole_only":
                connection = "thermal" if record.kind == "thru_hole" else "solid"
            if connection != "thermal":
                continue
            ring = _ring(record, state.layer, zone.settings.thermal_gap // 2)
            if ring is None:
                continue
            spokes: int | None = None
            width: int | None = None
            if state.state == "saved_fill":
                fills = [f.polygon for f in zone.fills if f.layer == state.layer and len(f.polygon) >= 3]
                spokes, width = _crossing(ring, fills)
            milliamps = capacity = None
            net = nets.get(state.net)
            current = requirements.current_for(net, design.circuit) if requirements and net else None
            if current is not None:
                milliamps = current.milliamps
                thickness = _thickness(board, state.layer, copper_thickness)
                if thickness is None:
                    missing = True
                elif width:
                    capacity = capacity_ma(
                        width * thickness, current.temp_rise_mk, external=state.layer in outer
                    )
            row = ReliefRow(
                _pad_name(record),
                state.net,
                state.where,
                state.layer,
                state.state,
                spokes,
                width,
                milliamps,
                capacity,
            )
            rows.append(row)
            if milliamps is not None and (width == 0 or (capacity is not None and capacity < milliamps)):
                issues.append(
                    issue(
                        "analysis.relief-exceeded",
                        f"the thermal relief of {row.pad} on {row.layer} ({row.spokes} spokes, {row.width} "
                        f"nm wide) carries {capacity or 0} mA, below the {milliamps} mA of {row.net}",
                        where=row.pad,
                        hint="widen the spokes, add spokes, or join the pad solidly",
                    )
                )
    if missing:
        issues.append(
            issue(
                "analysis.input-missing",
                "no copper thickness: the capacity of the reliefs is not computed",
                where="copper thickness",
                hint="--copper-thickness 35um, or a stack-up in the board",
            )
        )
    summary = {
        "pads": len(rows),
        "simulated": sum(1 for row in rows if row.copper != "saved_fill"),
    }
    return PracticeReport(tuple(rows), tuple(issues), _level(pour, pads, RELIEF_EVIDENCE), summary)


__all__ = [
    "BODIES_EVIDENCE",
    "CAPACITOR",
    "CONNECTIVITY_EVIDENCE",
    "DEAD_EVIDENCE",
    "DECOUPLING_EVIDENCE",
    "RELIEF_EVIDENCE",
    "BodyRow",
    "DeadRow",
    "DecouplingRow",
    "NetGroups",
    "PracticeReport",
    "ReliefRow",
    "analyze_bodies",
    "analyze_dead",
    "analyze_decoupling",
    "analyze_groups",
    "analyze_relief",
    "copper_distances",
    "copper_path",
    "fill_names",
    "plan_views",
]
