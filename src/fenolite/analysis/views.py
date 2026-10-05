# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Three compact views of a board: the nets, what a rectangle holds, and what is near a part (capability
board-frame, "Board views"; commands ``net``, ``region`` and ``neighbors``).

Pure functions of a ``Design`` and of the records of the ``BoardFrame`` protocol (pads and placed
extents). Every length is integer nanometres: track lengths come from an exact integer square root, arc
lengths from fixed-point integer arithmetic, and "touches" and distances from the kernel's exact gaps
between thick shapes.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from fractions import Fraction
from math import isqrt

from fenolite.analysis.copper import ARC_TOL_NM, copper_layers
from fenolite.backends.base import BoardPad, PlacedExtent
from fenolite.core.coords import Point
from fenolite.core.units import round_half_even_div
from fenolite.geometry import Arc as GeoArc
from fenolite.geometry import BBox, GeometryError, Thick, thick_bbox, thick_gap_floor, thick_touch
from fenolite.model.base import Entity
from fenolite.model.board import Arc, Board, FootprintInstance, Track, Via
from fenolite.model.design import Design

ALL_KINDS = ("footprint", "pad", "track", "arc", "via", "zone", "text")
"""The kinds of ``region_view``, in the order its items are sorted by."""
_BITS = 160
_ONE = 1 << _BITS
THROUGH = ("thru_hole", "np_thru_hole")


# --- lengths --------------------------------------------------------------------------------------


def _round_sqrt(n: int) -> int:
    """``√n`` rounded to the nearest integer (a square root of an integer is never a half)."""
    return (isqrt(4 * n) + 1) // 2


def _distance(a: Point, b: Point) -> int:
    return _round_sqrt((a.x - b.x) ** 2 + (a.y - b.y) ** 2)


def _atan_fixed(t: int) -> int:
    """``atan(t)`` for ``0 ≤ t ≤ 1``, both scaled by ``2**_BITS``: three halvings of the angle, then the
    power series, whose terms then shrink by a factor above 100."""
    for _ in range(3):
        t = (t * _ONE) // (_ONE + isqrt(_ONE * _ONE + t * t))
    square = t * t // _ONE
    total, term, n, sign = 0, t, 1, 1
    while term:
        total += sign * (term // n)
        term = term * square // _ONE
        n += 2
        sign = -sign
    return total << 3


_PI = 4 * _atan_fixed(_ONE)


def _turn(cross: Fraction, dot: Fraction) -> int:
    """The angle in ``[0, 2π)``, scaled by ``2**_BITS``, of a turn whose sine and cosine are proportional
    to ``cross`` and ``dot``."""
    a, b = abs(cross), abs(dot)
    if a <= b:
        ratio = a / b
        angle = _atan_fixed((ratio.numerator << _BITS) // ratio.denominator)
    else:
        ratio = b / a
        angle = _PI // 2 - _atan_fixed((ratio.numerator << _BITS) // ratio.denominator)
    if dot < 0:
        angle = _PI - angle
    return angle if cross >= 0 else 2 * _PI - angle


def arc_length(arc: Arc) -> int:
    """The centre-line length of an arc in nm, rounded half to even; 0 for points that give no arc."""
    try:
        shape = GeoArc(arc.start, arc.mid, arc.end)
    except GeometryError:
        return _distance(arc.start, arc.end)
    centre, radius2 = shape.centre, shape.radius2
    if centre is None or radius2 is None:
        return _distance(arc.start, arc.mid) + _distance(arc.mid, arc.end)
    way = shape.orientation
    spokes = [(Fraction(p.x) - centre[0], Fraction(p.y) - centre[1]) for p in (arc.start, arc.mid, arc.end)]
    angle = 0
    for (ux, uy), (vx, vy) in zip(spokes, spokes[1:], strict=False):
        angle += _turn(way * (ux * vy - uy * vx), ux * vx + uy * vy)
    radius = isqrt((radius2.numerator << (2 * _BITS)) // radius2.denominator)
    return round_half_even_div(radius * angle, 1 << (2 * _BITS))


# --- shapes ---------------------------------------------------------------------------------------


def _where(entity: Entity) -> str:
    provenance = entity.provenance
    return provenance.locator if provenance is not None and provenance.locator else entity.id


def _point_shape(point: Point) -> Thick:
    return Thick((point, point), 0)


def _track_shape(track: Track) -> Thick:
    if track.start == track.end:
        return Thick((track.start,), track.width) if track.width > 0 else _point_shape(track.start)
    return Thick((track.start, track.end), max(track.width, 0))


def _arc_shape(arc: Arc) -> Thick:
    try:
        return Thick(GeoArc(arc.start, arc.mid, arc.end).polygonize(ARC_TOL_NM), max(arc.width, 0))
    except (GeometryError, ValueError):
        return (
            Thick((arc.start, arc.end), max(arc.width, 0))
            if arc.start != arc.end
            else _point_shape(arc.start)
        )


def _via_shape(via: Via) -> Thick:
    return Thick((via.position,), via.diameter) if via.diameter > 0 else _point_shape(via.position)


def _pad_shapes(pad: BoardPad, layer: str | None = None) -> list[tuple[str, Thick]]:
    """The pad's copper as ``(layer, shape)``; a pad without copper is its position on its first layer."""
    shapes: list[tuple[str, Thick]] = []
    for entry in pad.copper:
        try:
            shapes.append((entry.layer, Thick(entry.core, entry.width, entry.filled)))
        except (GeometryError, ValueError):
            shapes.append((entry.layer, _point_shape(pad.position)))
    if not shapes:
        shapes = [(name, _point_shape(pad.position)) for name in (pad.layers or ("",))]
    return [(name, shape) for name, shape in shapes if layer is None or name == layer]


def _union(boxes: Iterable[BBox]) -> BBox | None:
    found: BBox | None = None
    for box in boxes:
        found = box if found is None else found.union(box)
    return found


def _ring_shapes(rings: Sequence[Sequence[Point]], fallback: Point) -> list[Thick]:
    """The rings of an extent face as filled shapes; a face without a usable ring is ``fallback``."""
    shapes: list[Thick] = []
    for ring in rings:
        try:
            shapes.append(Thick(tuple(ring), 0, filled=True))
        except (GeometryError, ValueError):
            continue
    return shapes or [_point_shape(fallback)]


def _pad_where(pad: BoardPad) -> str:
    return f"{pad.ref}-{pad.number}"


# --- nets -----------------------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class NetRow:
    """One net of the list: its class, the counts of its pads, tracks (arcs included), vias and zones,
    and the summed centre-line length of its tracks and arcs."""

    name: str
    netclass: str | None
    pads: int
    tracks: int
    vias: int
    zones: int
    length: int


@dataclass(frozen=True, slots=True)
class NetPad:
    where: str
    layers: tuple[str, ...]
    position: Point


@dataclass(frozen=True, slots=True)
class LayerCopper:
    """The tracks and arcs of a net on one layer, with their summed length."""

    layer: str
    tracks: int
    arcs: int
    length: int


@dataclass(frozen=True, slots=True)
class NetVia:
    position: Point
    layers: tuple[str, ...]
    diameter: int
    drill: int


@dataclass(frozen=True, slots=True)
class NetZone:
    name: str
    layers: tuple[str, ...]
    filled: bool


@dataclass(frozen=True, slots=True)
class NetView:
    """One net: its class, pads, copper per layer, vias, zones and the box of its pads and copper."""

    name: str
    netclass: str | None
    pads: tuple[NetPad, ...]
    copper: tuple[LayerCopper, ...]
    vias: tuple[NetVia, ...]
    zones: tuple[NetZone, ...]
    box: BBox | None


def _classes(design: Design) -> dict[str, str]:
    return {c.id: c.name for c in design.circuit.netclasses}


def net_list(design: Design) -> tuple[NetRow, ...]:
    """One row per net of the circuit, sorted by name."""
    board = design.board or Board(id="brd_none")
    classes = _classes(design)
    rows: list[NetRow] = []
    for net in design.circuit.nets:
        tracks = [t for t in board.tracks if t.net_id == net.id]
        arcs = [a for a in board.arcs if a.net_id == net.id]
        rows.append(
            NetRow(
                name=net.name,
                netclass=classes.get(net.netclass_id) if net.netclass_id else None,
                pads=sum(1 for fp in board.footprints for pad in fp.pads if pad.net_id == net.id),
                tracks=len(tracks) + len(arcs),
                vias=sum(1 for v in board.vias if v.net_id == net.id),
                zones=sum(1 for z in board.zones if z.net_id == net.id),
                length=sum(_distance(t.start, t.end) for t in tracks) + sum(arc_length(a) for a in arcs),
            )
        )
    return tuple(sorted(rows, key=lambda row: row.name))


def net_view(design: Design, name: str, *, pads: Sequence[BoardPad]) -> NetView:
    """The net called ``name``; ``KeyError`` for a name that the circuit does not hold."""
    net = design.nets_by_name.get(name)
    if net is None:
        raise KeyError(name)
    board = design.board or Board(id="brd_none")
    own = sorted((p for p in pads if p.net_id == net.id), key=lambda p: (_pad_where(p), p.pad_id))
    tracks = [t for t in board.tracks if t.net_id == net.id]
    arcs = [a for a in board.arcs if a.net_id == net.id]
    vias = [v for v in board.vias if v.net_id == net.id]
    layers = [layer for layer in copper_layers(board) if any(i.layer == layer for i in (*tracks, *arcs))]
    layers += sorted({i.layer for i in (*tracks, *arcs)} - set(layers))
    copper = tuple(
        LayerCopper(
            layer=layer,
            tracks=sum(1 for t in tracks if t.layer == layer),
            arcs=sum(1 for a in arcs if a.layer == layer),
            length=sum(_distance(t.start, t.end) for t in tracks if t.layer == layer)
            + sum(arc_length(a) for a in arcs if a.layer == layer),
        )
        for layer in layers
    )
    boxes = [thick_bbox(shape) for pad in own for _, shape in _pad_shapes(pad)]
    boxes += [thick_bbox(_track_shape(t)) for t in tracks]
    boxes += [thick_bbox(_arc_shape(a)) for a in arcs]
    boxes += [thick_bbox(_via_shape(v)) for v in vias]
    classes = _classes(design)
    return NetView(
        name=net.name,
        netclass=classes.get(net.netclass_id) if net.netclass_id else None,
        pads=tuple(NetPad(_pad_where(p), p.layers, p.position) for p in own),
        copper=copper,
        vias=tuple(
            NetVia(v.position, v.layers, v.diameter, v.drill)
            for v in sorted(vias, key=lambda v: (v.position.x, v.position.y, v.id))
        ),
        zones=tuple(
            NetZone(z.name, z.layers, z.filled)
            for z in sorted((z for z in board.zones if z.net_id == net.id), key=lambda z: (z.name, z.layers))
        ),
        box=_union(boxes),
    )


# --- region ---------------------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class RegionItem:
    """One item that touches the rectangle. ``layer`` is the item's layer, or for an item on several the
    first of them that was asked for; ``box`` is the bounding box of what was judged."""

    kind: str
    where: str
    net: str | None
    layer: str
    box: BBox


def _side_layer(board: Board, side: str) -> str:
    copper = copper_layers(board)
    if not copper:
        return "F.Cu" if side == "top" else "B.Cu"
    return copper[0] if side == "top" else copper[-1]


def _via_layers(board: Board, via: Via) -> tuple[str, ...]:
    """The copper layers a via crosses, in table order."""
    copper = copper_layers(board)
    ends = via.layers
    if not copper:
        return tuple(dict.fromkeys(ends))
    if via.via_type == "through" or len(ends) != 2 or ends[0] not in copper or ends[1] not in copper:
        return copper
    first, last = sorted((copper.index(ends[0]), copper.index(ends[1])))
    return copper[first : last + 1]


def _extent_of(extents: Sequence[PlacedExtent]) -> dict[str, PlacedExtent]:
    return {extent.footprint_id: extent for extent in extents}


def _own_shapes(footprint: FootprintInstance, extents: dict[str, PlacedExtent]) -> list[Thick]:
    extent = extents.get(footprint.id)
    return _ring_shapes(extent.own if extent is not None else (), footprint.position)


def region_view(
    design: Design,
    box: BBox,
    *,
    pads: Sequence[BoardPad],
    extents: Sequence[PlacedExtent],
    layer: str | None = None,
    kinds: Sequence[str] = ALL_KINDS,
) -> tuple[RegionItem, ...]:
    """Every item that touches the closed rectangle ``box``, sorted by kind (in the order of
    ``ALL_KINDS``) and then by ``where``. Copper touches when its exact gap to the rectangle is 0; a
    footprint and a zone by their bounding boxes; a text by its position."""
    unknown = sorted(set(kinds) - set(ALL_KINDS))
    if unknown:
        raise ValueError(f"unknown kind {unknown[0]!r}; the kinds are {', '.join(ALL_KINDS)}")
    if box.x0 == box.x1 or box.y0 == box.y1:
        raise ValueError("the rectangle has no area")
    board = design.board
    if board is None:
        return ()
    names = {net.id: net.name for net in design.circuit.nets}
    corners = (Point(box.x0, box.y0), Point(box.x1, box.y0), Point(box.x1, box.y1), Point(box.x0, box.y1))
    window = Thick(corners, 0, filled=True)
    refs = {c.id: c.ref for c in design.circuit.components}
    items: list[RegionItem] = []

    def net(net_id: str | None) -> str | None:
        return names.get(net_id, net_id) if net_id is not None else None

    if "footprint" in kinds:
        by_footprint = _extent_of(extents)
        for footprint in board.footprints:
            on = _side_layer(board, footprint.side)
            if layer is not None and on != layer:
                continue
            found = _union(thick_bbox(shape) for shape in _own_shapes(footprint, by_footprint))
            if found is not None and found.intersects(box):
                ref = refs.get(footprint.component_id, footprint.component_id)
                items.append(RegionItem("footprint", ref, None, on, found))
    if "pad" in kinds:
        for pad in pads:
            shapes = _pad_shapes(pad, layer)
            touching = [(name, shape) for name, shape in shapes if thick_touch(shape, window)]
            if touching:
                found = _union(thick_bbox(shape) for name, shape in shapes if name == touching[0][0])
                assert found is not None
                items.append(RegionItem("pad", _pad_where(pad), pad.net, touching[0][0], found))
    if "track" in kinds:
        for track in board.tracks:
            shape = _track_shape(track)
            if (layer is None or track.layer == layer) and thick_touch(shape, window):
                items.append(
                    RegionItem("track", _where(track), net(track.net_id), track.layer, thick_bbox(shape))
                )
    if "arc" in kinds:
        for arc in board.arcs:
            shape = _arc_shape(arc)
            if (layer is None or arc.layer == layer) and thick_touch(shape, window):
                items.append(RegionItem("arc", _where(arc), net(arc.net_id), arc.layer, thick_bbox(shape)))
    if "via" in kinds:
        for via in board.vias:
            crossed = _via_layers(board, via)
            if layer is not None and layer not in crossed:
                continue
            shape = _via_shape(via)
            if thick_touch(shape, window):
                on = layer if layer is not None else (crossed[0] if crossed else "")
                items.append(RegionItem("via", _where(via), net(via.net_id), on, thick_bbox(shape)))
    if "zone" in kinds:
        for zone in board.zones:
            if not zone.outline or (layer is not None and layer not in zone.layers):
                continue
            found = BBox.of_points(zone.outline)
            if found.intersects(box):
                on = layer if layer is not None else (zone.layers[0] if zone.layers else "")
                items.append(RegionItem("zone", _where(zone), net(zone.net_id), on, found))
    if "text" in kinds:
        for text in board.texts:
            if (layer is None or text.layer == layer) and box.contains_point(text.position):
                at = text.position
                items.append(RegionItem("text", _where(text), None, text.layer, BBox(at.x, at.y, at.x, at.y)))
    order = {kind: index for index, kind in enumerate(ALL_KINDS)}
    return tuple(
        sorted(items, key=lambda item: (order[item.kind], item.where, item.layer, item.box.as_tuple()))
    )


# --- neighbours -----------------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class PartRow:
    """The part whose neighbours are listed; ``box`` is the bounding box of its own extent face."""

    ref: str
    position: Point
    rotation: int
    side: str
    box: BBox


@dataclass(frozen=True, slots=True)
class Neighbor:
    """A footprint near the part: ``distance`` is the gap between the two extents rounded up to a whole
    nm, 0 with ``overlap`` when they touch or overlap."""

    ref: str
    distance: int
    overlap: bool
    side: str
    shared_nets: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class NeighborsView:
    part: PartRow
    neighbors: tuple[Neighbor, ...]


def _gap_ceil(a: Thick, b: Thick) -> int:
    """The gap of two shapes rounded up to a whole nm; 0 when they touch."""
    if thick_touch(a, b):
        return 0
    floor = thick_gap_floor(a, b)
    grown = Thick(a.core, a.width + 2 * floor, a.filled)
    return floor if thick_touch(grown, b) else floor + 1


def neighbors_view(
    design: Design,
    ref: str,
    *,
    extents: Sequence[PlacedExtent],
    pads: Sequence[BoardPad],
    radius: int,
) -> NeighborsView:
    """The footprints whose own extent face lies within ``radius`` of that of the part ``ref``, on a side
    they share, sorted by distance and then reference. ``KeyError`` for an unknown reference."""
    if radius < 0:
        raise ValueError("the radius is at least 0")
    board = design.board
    refs = {c.id: c.ref for c in design.circuit.components}
    placed = [(refs.get(fp.component_id, fp.component_id), fp) for fp in (board.footprints if board else ())]
    part = next((fp for name, fp in placed if name == ref), None)
    if part is None:
        raise KeyError(ref)
    by_footprint = _extent_of(extents)
    sides: dict[str, set[str]] = {}
    nets: dict[str, set[str]] = {}
    for pad in pads:
        sides.setdefault(pad.footprint_id, set()).add(pad.side)
        if pad.kind in THROUGH:
            sides[pad.footprint_id].update(("top", "bottom"))
        if pad.net:
            nets.setdefault(pad.footprint_id, set()).add(pad.net)

    def faces(footprint: FootprintInstance) -> set[str]:
        return sides.get(footprint.id, set()) | {footprint.side}

    own = _own_shapes(part, by_footprint)
    box = _union(thick_bbox(shape) for shape in own)
    assert box is not None
    found: list[Neighbor] = []
    for name, other in placed:
        if other.id == part.id or not faces(part) & faces(other):
            continue
        theirs = _own_shapes(other, by_footprint)
        reach = box.inflate(radius + 1)
        if not any(reach.intersects(thick_bbox(shape)) for shape in theirs):
            continue
        distance = min(_gap_ceil(a, b) for a in own for b in theirs)
        if distance <= radius:
            shared = tuple(sorted(nets.get(part.id, set()) & nets.get(other.id, set())))
            found.append(Neighbor(name, distance, distance == 0, other.side, shared))
    found.sort(key=lambda n: (n.distance, n.ref))
    return NeighborsView(PartRow(ref, part.position, part.rotation, part.side, box), tuple(found))


__all__ = [
    "ALL_KINDS",
    "LayerCopper",
    "Neighbor",
    "NeighborsView",
    "NetPad",
    "NetRow",
    "NetVia",
    "NetView",
    "NetZone",
    "PartRow",
    "RegionItem",
    "arc_length",
    "neighbors_view",
    "net_list",
    "net_view",
    "region_view",
]
