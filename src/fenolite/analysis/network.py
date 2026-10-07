# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The copper network of a net between two sets of pads, and its active part (capability board-analyses,
"Power path network"; ``docs/analyses.md``, "Power paths").

Pieces are the net's tracks and arcs, vias, pads and fill regions, shaped as ``net_copper`` shapes them.
Pieces whose copper touches on a layer are joined. A joint is an ideal contact: a pad, a point of a
track's centre line, a via on a layer. The elements between the joints are the parts of tracks and arcs,
the via groups and the fill regions:

- a track or arc is cut where its centre line enters or leaves a region of its net on its layer (the
  part inside is the region's copper and becomes one port of the region), at the point nearest to the
  position of a pad or a via that touches it, at the point nearest to an end of another track or arc
  that touches it, and where two centre lines cross;
- vias joined to the same joints and regions on each of their layers form one via group;
- each joint that touches a region is one port of it, with the copper of its pieces on that layer.

An element is active when it lies on a path from a start pad to an end pad that passes each joint and each
element once, and in series when every such path passes it. Both are read from the graph of joints and
elements: with an edge added between the two pad sets, the active part is the biconnected component of
that edge, and an element is in series when the two sets fall apart without it.

Nothing is guessed: a pad name that no pad holds, pads of several nets and copper that does not join the
two sets are reported, and graphics on a copper layer are counted, not used.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass, replace
from fractions import Fraction
from typing import Literal

from fenolite.analysis.codes import issue
from fenolite.analysis.copper import ARC_TOL_NM, CopperShape, copper_layers, net_copper
from fenolite.analysis.fills import FillRegion, fill_regions
from fenolite.analysis.report import sorted_issues
from fenolite.analysis.section import N, Port, Q, closest, cuts, located, nearest, sq_dist
from fenolite.backends.base import BoardPad
from fenolite.core.coords import Point
from fenolite.core.errors import Issue
from fenolite.core.units import Nm
from fenolite.geometry import (
    BBox,
    Location,
    SpatialIndex,
    Thick,
    ceil_sqrt,
    floor_sqrt,
    round_point,
    thick_bbox,
    thick_touch,
)
from fenolite.model.design import Design

Kind = Literal["track", "arc", "via-group", "fill"]
_Pos = tuple[int, Fraction]  # a point of a polyline: the index of a segment and the parameter on it
_Key = tuple[object, ...]
_Mark = tuple[str, int | str]  # what a via is joined to on a layer: a region by index, a piece by name
_ZERO = Fraction(0)
_ONE = Fraction(1)


@dataclass(frozen=True, slots=True)
class Element:
    """One element of the network. ``ends`` are the joints it joins: two for a part of a track or arc,
    one per layer for a via group, one per port for a fill. ``length_nm`` is the centre-line length of a
    part, rounded down, and ``length_band`` how far the true length may exceed it; both are ``None`` and 0
    for a via group and a fill. ``layer`` names the two outer layers of a via group joined by ``/``."""

    kind: Kind
    where: str
    entity_ids: tuple[str, ...]
    layer: str
    length_nm: int | None
    width: Nm | None
    ends: tuple[int, ...]
    active: bool = False
    series: bool = False
    length_band: int = 0


@dataclass(frozen=True, slots=True)
class ViaGroup:
    """Vias joined to the same joints and regions on each of their layers: the ids of the vias, the
    layers on which the group is joined to something, and the ``where`` of what it is joined to."""

    where: str
    vias: tuple[str, ...]
    layers: tuple[str, ...]
    pieces: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class RegionUse:
    """A fill region of the net with its ports; ``nodes`` are the joints of the ports, in order, and
    ``active_ports`` the indices of the ports that join the region to active copper."""

    region: FillRegion
    ports: tuple[Port, ...] = ()
    active_ports: tuple[int, ...] = ()
    nodes: tuple[int, ...] = ()


@dataclass(frozen=True, slots=True)
class PathNetwork:
    """The network of one power path. ``elements`` hold the parts of tracks and arcs, then one element
    per group of ``groups`` and one per region of ``regions``, in their order; ``start_nodes`` and
    ``end_nodes`` are the joints of the two sets of pads."""

    net: str
    start: tuple[str, ...]
    end: tuple[str, ...]
    elements: tuple[Element, ...] = ()
    regions: tuple[RegionUse, ...] = ()
    groups: tuple[ViaGroup, ...] = ()
    issues: tuple[Issue, ...] = ()
    start_nodes: tuple[int, ...] = ()
    end_nodes: tuple[int, ...] = ()


# --- helpers --------------------------------------------------------------------------------------


class _Joints:
    """Union-find over the keys of the joints."""

    def __init__(self) -> None:
        self.parent: dict[_Key, _Key] = {}

    def find(self, key: _Key) -> _Key:
        parent = self.parent
        root = key
        while parent.setdefault(root, root) != root:
            root = parent[root]
        while parent[key] != root:
            parent[key], key = root, parent[key]
        return root

    def union(self, first: _Key, second: _Key) -> None:
        a, b = self.find(first), self.find(second)
        if a != b:
            self.parent[b] = a


def _box_of(shape: Thick) -> BBox:
    return thick_bbox(shape)


class _Region:
    """A region with what the contact tests need: its copper as thick shapes and its ring edges."""

    def __init__(self, region: FillRegion) -> None:
        self.region = region
        self.outer = Thick(region.outer, 0, filled=True)
        self.box = thick_bbox(self.outer)
        self.holes = [(Thick(h, 0, filled=True), Thick((*h, h[0]), 0)) for h in region.holes]
        self.hole_index = SpatialIndex[int].build(
            (thick_bbox(solid), i) for i, (solid, _) in enumerate(self.holes)
        )
        edges: list[tuple[Point, Point]] = []
        for ring in (region.outer, *region.holes):
            edges += [(p, ring[(i + 1) % len(ring)]) for i, p in enumerate(ring)]
        self.edges = edges
        self.edge_index = SpatialIndex[int].build(
            (BBox(min(u.x, v.x), min(u.y, v.y), max(u.x, v.x), max(u.y, v.y)), i)
            for i, (u, v) in enumerate(edges)
        )

    def touches(self, shape: Thick) -> bool:
        """Whether the shape's copper meets the region's: it touches the outer ring's area and does not
        lie strictly inside a hole."""
        if not thick_touch(shape, self.outer):
            return False
        for i in self.hole_index.query(_box_of(shape)):
            solid, rim = self.holes[i]
            if thick_touch(shape, solid) and not thick_touch(shape, rim) and _within(shape, solid):
                return False
        return True

    def holds(self, point: Q) -> bool:
        """Whether the point lies on the region's copper, its boundary included."""
        if located(point, self.region.outer) is Location.OUTSIDE:
            return False
        spot = round_point(point[0], point[1])
        for i in self.hole_index.query(BBox(spot.x - 1, spot.y - 1, spot.x + 1, spot.y + 1)):
            if located(point, self.region.holes[i]) is Location.INSIDE:
                return False
        return True


def _within(shape: Thick, solid: Thick) -> bool:
    """Whether a shape that touches the area of a hole and not its rim lies inside the hole (and not
    around it): one of its core points does."""
    return thick_touch(Thick((shape.core[0],), 1), solid)


@dataclass(slots=True)
class _Line:
    """A track or an arc: its copper shape, its centre line, the parts inside regions and its stops."""

    copper: CopperShape
    points: tuple[Point, ...]
    inside: list[tuple[_Pos, _Pos, int]]  # from, to, index of the region
    stops: set[_Pos]

    @property
    def last(self) -> _Pos:
        return (len(self.points) - 2, _ONE)


def _norm(line: _Line, pos: _Pos) -> _Pos:
    """One name per point: the end of a segment is the start of the next."""
    k, t = pos
    if t == 1 and k < len(line.points) - 2:
        return (k + 1, _ZERO)
    return (k, t)


def _at(line: _Line, pos: _Pos) -> Q:
    k, t = pos
    a, b = line.points[k], line.points[k + 1]
    return (a.x + t * (b.x - a.x), a.y + t * (b.y - a.y))


def _near(line: _Line, point: Q) -> tuple[N, _Pos]:
    """The squared distance from ``point`` to the centre line and the position of the nearest point."""
    best: tuple[N, _Pos] | None = None
    for k in range(len(line.points) - 1):
        a, b = line.points[k], line.points[k + 1]
        qa: Q = (a.x, a.y)
        qb: Q = (b.x, b.y)
        foot = nearest(point, qa, qb)
        found = sq_dist(point, foot)
        if best is None or found < best[0]:
            dx, dy = b.x - a.x, b.y - a.y
            t = Fraction((foot[0] - a.x) * dx + (foot[1] - a.y) * dy, dx * dx + dy * dy)
            best = (found, _norm(line, (k, t)))
    assert best is not None
    return best


def _length(line: _Line, first: _Pos, second: _Pos) -> tuple[int, int]:
    """The length of the centre line between two positions, rounded down and rounded up."""
    low = high = 0
    for k in range(first[0], second[0] + 1):
        start = first[1] if k == first[0] else _ZERO
        stop = second[1] if k == second[0] else _ONE
        if stop <= start:
            continue
        a, b = line.points[k], line.points[k + 1]
        squared = (stop - start) ** 2 * ((b.x - a.x) ** 2 + (b.y - a.y) ** 2)
        low += floor_sqrt(squared)
        high += ceil_sqrt(squared)
    return low, high


def _arc_slack(line: _Line, first: _Pos, second: _Pos, arc_tol: int) -> int:
    """How far the arc between two positions may be longer than its chords. A chord of length ``c`` whose
    sagitta is at most ``s`` spans an arc of at most ``c + 4·s²/c`` (for a chord angle up to a half turn,
    ``2u / sin 2u − 1 ≤ tan² u`` with ``u`` a quarter of the angle and ``tan u = 2·s/c``); every chord that
    the part touches counts whole. Fenolite's own derivation: hypothesis ``H-G-AN-ARCLEN``."""
    slack = 0
    for k in range(first[0], second[0] + 1):
        a, b = line.points[k], line.points[k + 1]
        chord = max(1, floor_sqrt((b.x - a.x) ** 2 + (b.y - a.y) ** 2))
        slack += min(2 * arc_tol, 4 * arc_tol * arc_tol // chord + 1)
    return slack


def _cut_by_regions(line: _Line, regions: Sequence[tuple[int, _Region]]) -> None:
    """Find the parts of the centre line that lie inside a region of its layer."""
    box = thick_bbox(line.copper.shape)
    for index, region in regions:
        if not (
            box.x0 <= region.box.x1
            and region.box.x0 <= box.x1
            and box.y0 <= region.box.y1
            and region.box.y0 <= box.y1
        ):
            continue
        stops: set[_Pos] = {(k, _ZERO) for k in range(len(line.points) - 1)} | {line.last}
        for k in range(len(line.points) - 1):
            a, b = line.points[k], line.points[k + 1]
            reach = BBox(min(a.x, b.x), min(a.y, b.y), max(a.x, b.x), max(a.y, b.y))
            for e in region.edge_index.query(reach):
                u, v = region.edges[e]
                stops.update(_norm(line, (k, t)) for t in cuts(a, b, u, v))
        ordered = sorted(stops)
        for first, second in zip(ordered, ordered[1:], strict=False):
            # two neighbours lie on one segment: the second is on it or is the start of the next
            until = second[1] if second[0] == first[0] else _ONE
            if not region.holds(_at(line, (first[0], (first[1] + until) / 2))):
                continue
            if line.inside and line.inside[-1][2] == index and line.inside[-1][1] == first:
                line.inside[-1] = (line.inside[-1][0], second, index)
            else:
                line.inside.append((first, second, index))
    line.inside.sort()


def _blocks(adjacent: Sequence[Sequence[int]], root: int) -> list[set[int]]:
    """The vertex sets of the biconnected components of a simple graph that are reachable from ``root``
    (an iterative depth-first search with a stack of edges)."""
    count = len(adjacent)
    found_at = [0] * count
    low = [0] * count
    cursor = [0] * count
    clock = 1
    found_at[root] = low[root] = clock
    stack: list[tuple[int, int]] = [(root, -1)]
    edges: list[tuple[int, int]] = []
    blocks: list[set[int]] = []
    while stack:
        vertex, parent = stack[-1]
        if cursor[vertex] < len(adjacent[vertex]):
            other = adjacent[vertex][cursor[vertex]]
            cursor[vertex] += 1
            if other == parent:
                continue
            if found_at[other] == 0:
                clock += 1
                found_at[other] = low[other] = clock
                edges.append((vertex, other))
                stack.append((other, vertex))
            elif found_at[other] < found_at[vertex]:
                edges.append((vertex, other))
                low[vertex] = min(low[vertex], found_at[other])
            continue
        stack.pop()
        if not stack:
            break
        above = stack[-1][0]
        low[above] = min(low[above], low[vertex])
        if low[vertex] >= found_at[above]:
            block: set[int] = set()
            while True:
                edge = edges.pop()
                block.update(edge)
                if edge == (above, vertex):
                    break
            blocks.append(block)
    return blocks


def _reaches(
    adjacent: Sequence[Sequence[int]], source: int, sink: int, without: int, among: set[int]
) -> list[int]:
    """A path from ``source`` to ``sink`` through the vertices of ``among`` less ``without``; empty when
    there is none."""
    before: dict[int, int] = {source: source}
    queue = [source]
    for vertex in queue:
        if vertex == sink:
            path = [sink]
            while path[-1] != source:
                path.append(before[path[-1]])
            return path[::-1]
        for other in adjacent[vertex]:
            if other not in before and other != without and other in among:
                before[other] = vertex
                queue.append(other)
    return []


# --- the network ----------------------------------------------------------------------------------


def _graphics(design: Design) -> int:
    """Graphics on a copper layer, those of a footprint instance included: counted, not used."""
    board = design.board
    assert board is not None
    copper = set(copper_layers(board))
    count = sum(1 for graphic in board.graphics if graphic.layer in copper)
    for footprint in board.footprints:
        for graphic in getattr(footprint, "graphics", ()):
            count += getattr(graphic, "layer", None) in copper
    return count


def graphic_issue(design: Design, what: str) -> Issue | None:
    """The ``analysis.item-unsupported`` warning for the copper graphics of the board, when it has any."""
    count = _graphics(design) if design.board is not None else 0
    if not count:
        return None
    return issue(
        "analysis.item-unsupported",
        f"{count} graphic(s) on a copper layer are not read as copper and are left out of {what}",
        where="graphic",
        hint="draw the copper as tracks, pads or zones; a graphic has no net",
    )


def net_pieces(shapes: Sequence[CopperShape]) -> tuple[CopperShape, ...]:
    """The shapes of ``net_copper`` that the network uses as pieces: all but the fills, which it reads as
    regions with holes."""
    return tuple(shape for shape in shapes if shape.kind != "fill")


def _pad_name(pad: BoardPad) -> str:
    holder = pad.ref or pad.footprint_id
    return f"{holder}-{pad.number}" if pad.number else holder


def path_network(
    design: Design,
    *,
    pads: Sequence[BoardPad] | None,
    start: Sequence[str],
    end: Sequence[str],
    arc_tol: int = ARC_TOL_NM,
) -> PathNetwork:
    """The copper network of the net that holds the pads named in ``start`` and ``end`` (``REF-PIN``),
    with its active part marked."""
    start, end = tuple(start), tuple(end)
    names = "/".join((",".join(start), ",".join(end)))
    empty = PathNetwork("", start, end)
    board = design.board
    by_name: dict[str, list[BoardPad]] = {}
    for pad in pads or ():
        by_name.setdefault(_pad_name(pad), []).append(pad)
    unknown = [name for name in (*start, *end) if name not in by_name]
    if board is None or unknown or not start or not end:
        what = (
            "the backend gives no board-frame pads" if pads is None else "no pad of the board has that name"
        )
        found = issue(
            "analysis.path-unmatched",
            f"power path {names}: {', '.join(unknown) or 'no pad'}: {what}",
            where=names,
        )
        return replace(empty, issues=(found,))
    net_ids = {pad.net_id for name in (*start, *end) for pad in by_name[name]}
    if len(net_ids) != 1 or None in net_ids:
        found = issue(
            "analysis.path-unmatched",
            f"power path {names}: its pads belong to {len(net_ids - {None})} net(s)"
            + (" and to none" if None in net_ids else "")
            + "; a path lies on one net",
            where=names,
        )
        return replace(empty, issues=(found,))
    (net_id,) = net_ids
    net = {item.id: item.name for item in design.circuit.nets}.get(net_id or "", net_id or "")
    copper = net_copper(design, pads=pads, arc_tol=arc_tol)
    issues: list[Issue] = []
    for kind, count in copper.unsupported.items():
        issues.append(
            issue(
                "analysis.item-unsupported",
                f"{count} {kind}(s) could not be shaped and are left out of the power path analysis",
                where=kind,
            )
        )
    graphics = graphic_issue(design, "the power path analysis")
    if graphics is not None:
        issues.append(graphics)
    all_regions, left_out = fill_regions(design)
    if left_out:
        issues.append(
            issue(
                "analysis.item-unsupported",
                f"{left_out} fill(s) do not chain into rings and are left out of the power path analysis",
                where="fill",
                hint="refill the zones",
            )
        )
    regions = [_Region(region) for region in all_regions if region.net == net]
    by_layer: dict[str, list[tuple[int, _Region]]] = {}
    for index, region in enumerate(regions):
        by_layer.setdefault(region.region.layer, []).append((index, region))

    shapes = list(net_pieces(copper.by_net.get(net, ())))
    joints = _Joints()
    lines: list[_Line] = []
    line_of: dict[int, int] = {}
    positions = {pad.pad_id: pad.position for pad in pads or ()}
    positions.update({via.id: via.position for via in board.vias})
    for index, shape in enumerate(shapes):
        if shape.kind in ("track", "arc") and len(shape.shape.core) >= 2:
            line = _Line(shape, shape.shape.core, [], set())
            _cut_by_regions(line, by_layer.get(shape.layer, ()))
            line_of[index] = len(lines)
            lines.append(line)

    def key_on(number: int, pos: _Pos) -> _Key:
        """The joint of a position of a line: the port of the inside part that holds it, else itself."""
        line = lines[number]
        for i, (first, second, _) in enumerate(line.inside):
            if first <= pos <= second:
                return ("in", number, i)
        line.stops.add(pos)
        return ("pos", number, pos)

    def key_of(index: int) -> _Key:
        shape = shapes[index]
        return ("pad", shape.entity_id) if shape.kind == "pad" else ("via", shape.entity_id, shape.layer)

    # ports: region, joint key -> the shapes and the names of the pieces
    ports: dict[tuple[int, _Key], tuple[list[Thick], set[str], int]] = {}

    def port(region: int, key: _Key, shape: Thick, where: str, band: int = 0) -> None:
        held = ports.setdefault((region, key), ([], set(), 0))
        held[0].append(shape)
        held[1].add(where)
        ports[(region, key)] = (held[0], held[1], max(held[2], band))

    per_layer: dict[str, list[int]] = {}
    for index, shape in enumerate(shapes):
        per_layer.setdefault(shape.layer, []).append(index)
    touched: dict[tuple[str, str], set[_Mark]] = {}  # via id, layer -> what it is joined to
    for layer, members in per_layer.items():
        boxes = [thick_bbox(shapes[index].shape) for index in members]
        tree = SpatialIndex[int].build((box, i) for i, box in enumerate(boxes))
        for i, index in enumerate(members):
            shape = shapes[index]
            for region_index, region in by_layer.get(layer, ()):
                if shape.kind in ("pad", "via") and region.touches(shape.shape):
                    port(region_index, key_of(index), shape.shape, shape.where, shape.band)
                    if shape.kind == "via":
                        touched.setdefault((shape.entity_id, layer), set()).add(("region", region_index))
            for j in tree.query(boxes[i]):
                other_index = members[j]
                other = shapes[other_index]
                if j <= i or other.entity_id == shape.entity_id:
                    continue
                if not thick_touch(shape.shape, other.shape):
                    continue
                first, second = line_of.get(index), line_of.get(other_index)
                if first is None and second is None:
                    joints.union(key_of(index), key_of(other_index))
                    for one, two in ((shape, other), (other, shape)):
                        if one.kind == "via":
                            touched.setdefault((one.entity_id, layer), set()).add(("piece", two.where))
                elif first is not None and second is not None:
                    _join_lines(lines, first, second, key_on, joints)
                else:
                    number, piece_index = (first, other_index) if first is not None else (second, index)
                    assert number is not None
                    piece = shapes[piece_index]
                    at = positions.get(piece.entity_id, piece.shape.core[0])
                    key = key_on(number, _near(lines[number], (at.x, at.y))[1])
                    joints.union(key, key_of(piece_index))
                    if piece.kind == "via":
                        touched.setdefault((piece.entity_id, layer), set()).add(
                            ("piece", lines[number].copper.where)
                        )

    # the ends of a line that touch a region without the centre line entering it, and the inside parts
    for number, line in enumerate(lines):
        shape = line.copper
        for i, (first, second, region_index) in enumerate(line.inside):
            core = _rounded(line, first, second)
            if len(core) >= 2 or shape.shape.width > 0:
                port(region_index, ("in", number, i), Thick(core, shape.shape.width), shape.where, shape.band)
        for pos in ((0, _ZERO), line.last):
            key = key_on(number, pos)
            if key[0] == "in":
                continue
            spot = round_point(*_at(line, pos))
            if shape.shape.width <= 0:
                continue
            disc = Thick((spot,), shape.shape.width)
            for region_index, region in by_layer.get(shape.layer, ()):
                if region.touches(disc):
                    port(region_index, key, disc, shape.where, shape.band)

    # via groups: vias joined to the same joints and regions on each of their layers
    via_layers: dict[str, list[str]] = {}
    via_where: dict[str, str] = {}
    for shape in shapes:
        if shape.kind == "via":
            via_layers.setdefault(shape.entity_id, []).append(shape.layer)
            via_where[shape.entity_id] = shape.where
    signature: dict[tuple[object, ...], list[str]] = {}
    for via_id, layers in via_layers.items():
        marks: list[object] = []
        for layer in layers:
            joined = touched.get((via_id, layer))
            if not joined:
                marks.append(None)
                continue
            root = joints.find(("via", via_id, layer))
            alone = all(item[0] == "region" for item in joined)
            marks.append(
                (
                    None if alone else root,
                    tuple(sorted(str(item[1]) for item in joined if item[0] == "region")),
                )
            )
        if any(mark is not None for mark in marks):
            signature.setdefault((tuple(layers), *marks), []).append(via_id)
    groups: list[ViaGroup] = []
    group_keys: list[list[tuple[str, _Key]]] = []
    for members_of in signature.values():
        head = members_of[0]
        layers = [layer for layer in via_layers[head] if touched.get((head, layer))]
        keys: list[tuple[str, _Key]] = []
        pieces: set[str] = set()
        for layer in layers:
            for via_id in members_of[1:]:
                joints.union(("via", head, layer), ("via", via_id, layer))
            keys.append((layer, ("via", head, layer)))
            for via_id in members_of:
                for _, value in touched.get((via_id, layer), ()):
                    pieces.add(regions[value].region.where if isinstance(value, int) else value)
        ordered = sorted(members_of, key=lambda via_id: via_where[via_id])
        where = via_where[ordered[0]] + (f"+{len(ordered) - 1}" if len(ordered) > 1 else "")
        groups.append(ViaGroup(where, tuple(ordered), tuple(layers), tuple(sorted(pieces))))
        group_keys.append(keys)
    order = sorted(range(len(groups)), key=lambda i: groups[i].where)
    groups = [groups[i] for i in order]
    group_keys = [group_keys[i] for i in order]

    # number the joints, then list the elements
    numbers: dict[_Key, int] = {}

    def node(key: _Key) -> int:
        return numbers.setdefault(joints.find(key), len(numbers))

    elements: list[Element] = []
    for number, line in enumerate(lines):
        shape = line.copper
        stops = sorted(line.stops | {(0, _ZERO), line.last} | {p for a, b, _ in line.inside for p in (a, b)})
        parts: list[tuple[_Pos, _Pos]] = []
        for first, second in zip(stops, stops[1:], strict=False):
            if any(a <= first and second <= b for a, b, _ in line.inside):
                continue
            parts.append((first, second))
        for i, (first, second) in enumerate(parts):
            low, high = _length(line, first, second)
            slack = high - low + (_arc_slack(line, first, second, arc_tol) if shape.kind == "arc" else 0)
            ends = (node(key_on(number, first)), node(key_on(number, second)))
            where = shape.where if len(parts) == 1 else f"{shape.where}[{i}]"
            part: Kind = "arc" if shape.kind == "arc" else "track"
            elements.append(
                Element(
                    part,
                    where,
                    (shape.entity_id,),
                    shape.layer,
                    low,
                    shape.shape.width,
                    ends,
                    False,
                    False,
                    slack,
                )
            )
    elements.sort(key=lambda item: (item.layer, item.kind, item.where))
    all_layers = copper.layers
    for group, keys in zip(groups, group_keys, strict=True):
        ends = tuple(dict.fromkeys(node(key) for _, key in keys))
        spanned = sorted(group.layers, key=lambda name: all_layers.index(name) if name in all_layers else 0)
        layer = "/".join(dict.fromkeys((spanned[0], spanned[-1]))) if spanned else ""
        elements.append(Element("via-group", group.where, group.vias, layer, None, None, ends))
    uses: list[RegionUse] = []
    for index, region in enumerate(regions):
        own = sorted(
            ((key, held) for (region_index, key), held in ports.items() if region_index == index),
            key=lambda item: sorted(item[1][1]),
        )
        merged: dict[int, tuple[list[Thick], set[str], int]] = {}
        for key, (thick, wheres, band) in own:
            held = merged.setdefault(node(key), ([], set(), 0))
            merged[node(key)] = (held[0] + thick, held[1] | wheres, max(held[2], band))
        nodes = tuple(merged)
        made = tuple(Port("+".join(sorted(w)), tuple(t), band) for t, w, band in merged.values())
        uses.append(RegionUse(region.region, made, (), nodes))
        elements.append(
            Element(
                "fill", region.region.where, (region.region.zone_id,), region.region.layer, None, None, nodes
            )
        )

    start_nodes = tuple(dict.fromkeys(node(("pad", pad.pad_id)) for name in start for pad in by_name[name]))
    end_nodes = tuple(dict.fromkeys(node(("pad", pad.pad_id)) for name in end for pad in by_name[name]))

    # the active part and the elements in series
    joint_count = len(numbers)
    source, sink = joint_count + len(elements), joint_count + len(elements) + 1
    adjacent: list[list[int]] = [[] for _ in range(sink + 1)]
    for e, element in enumerate(elements):
        for end_node in dict.fromkeys(element.ends):
            adjacent[joint_count + e].append(end_node)
            adjacent[end_node].append(joint_count + e)
    for extra, nodes_of in ((source, start_nodes), (sink, end_nodes)):
        for end_node in nodes_of:
            adjacent[extra].append(end_node)
            adjacent[end_node].append(extra)
    everything = set(range(sink + 1))
    active: set[int] = set()
    series: set[int] = set()
    path = _reaches(adjacent, source, sink, -1, everything)
    if not path:
        issues.append(
            issue(
                "analysis.path-open",
                f"power path {names} on net {net}: the copper read from the board does not join the start "
                "pads to the end pads",
                where=names,
                hint="route or fill the connection; graphics and copper the model does not hold are not read",
            )
        )
    else:
        adjacent[source].append(sink)
        adjacent[sink].append(source)
        for block in _blocks(adjacent, source):
            if source in block and sink in block:
                active = block - {source, sink}
        adjacent[source].pop()
        adjacent[sink].pop()
        for vertex in path[1:-1]:
            if not _reaches(adjacent, source, sink, vertex, everything):
                series.add(vertex)
    final: list[Element] = []
    for e, element in enumerate(elements):
        vertex = joint_count + e
        final.append(replace(element, active=vertex in active, series=vertex in series))
    for i, use in enumerate(uses):
        vertex = joint_count + len(elements) - len(uses) + i
        if vertex in active:
            uses[i] = replace(use, active_ports=tuple(k for k, n in enumerate(use.nodes) if n in active))
    return PathNetwork(
        net,
        start,
        end,
        tuple(final),
        tuple(uses),
        tuple(groups),
        sorted_issues(issues),
        start_nodes,
        end_nodes,
    )


def _rounded(line: _Line, first: _Pos, second: _Pos) -> tuple[Point, ...]:
    """The centre line between two positions as stored points, without equal neighbours."""
    points = [round_point(*_at(line, first))]
    for k in range(first[0] + 1, second[0] + 1):
        points.append(line.points[k])
    points.append(round_point(*_at(line, second)))
    out: list[Point] = []
    for point in points:
        if not out or out[-1] != point:
            out.append(point)
    return tuple(out)


def _join_lines(
    lines: Sequence[_Line], first: int, second: int, key_on: Callable[[int, _Pos], _Key], joints: _Joints
) -> None:
    """Join two lines whose copper touches: where their centre lines cross, and at the point of each
    nearest to an end of the other that touches its body."""
    a, b = lines[first], lines[second]
    reach2 = (a.copper.shape.width + b.copper.shape.width) ** 2  # four times the squared reach
    for i in range(len(a.points) - 1):
        for j in range(len(b.points) - 1):
            p, q, r, s = a.points[i], a.points[i + 1], b.points[j], b.points[j + 1]
            squared, x, y = closest((p.x, p.y), (q.x, q.y), (r.x, r.y), (s.x, s.y))
            if squared == 0:
                joints.union(key_on(first, _near(a, x)[1]), key_on(second, _near(b, y)[1]))
    for one, number, other, other_number in ((a, first, b, second), (b, second, a, first)):
        for pos in ((0, _ZERO), one.last):
            point = _at(one, pos)
            squared, at = _near(other, point)
            if 4 * squared <= reach2:
                joints.union(key_on(number, pos), key_on(other_number, at))


__all__ = ["Element", "PathNetwork", "RegionUse", "ViaGroup", "graphic_issue", "net_pieces", "path_network"]
