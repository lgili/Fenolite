# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Level 7 of a design comparison: the exact geometry (capability design-equivalence, "Level 7 compares
exact geometry" and "Level 7 normalisation"; ``docs/equivalence.md``, "Level 7").

Before matching, geometry is normalised in integer arithmetic: a closed ring starts at its smallest point in
``(x, y)`` order and runs counter-clockwise (by the sign of its doubled area), each edge keeping its arc mid;
a segment's ends are an unordered pair; an arc keeps its mid and its ends in sorted order; a circle is its
centre and its squared radius; a rectangle is its four-point ring.

The items are the outline rings, cut-outs and slots, the zones (by net name, layers and outline; never the
fill), the rule areas, the board graphics, texts, holes and dimensions, and the graphics, texts and fields
of each footprint pair that level 3 compared, in the footprint's own frame. Items without fields of their own
match as multisets by their whole key; zones, rule areas, texts and footprint fields then compare their
fields. Points compare with the length tolerance per coordinate.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Callable, Collection, Mapping, Sequence
from dataclasses import dataclass, replace

from fenolite.checks.equivalence import norm, pairing
from fenolite.checks.equivalence.model import EXACT, Difference, LevelResult, Tolerances
from fenolite.checks.equivalence.rules import Leaf, field_differences, fields
from fenolite.core.coords import Point
from fenolite.model.board import Board, FootprintInstance, Graphic, Keepout, Outline, Text
from fenolite.model.design import Design

LEVEL = 7
LENS_FIELDS = frozenset({"fenolite.path"})
"""Footprint fields a build writes as the lens key of each footprint (change c0281): not design, so level 7
leaves them out."""
Edge = tuple[Point, Point | None]
"""A vertex of a ring and the mid of the arc that starts at it (``None`` for a straight edge)."""
Key = tuple[object, ...]
ORIGIN = Point(0, 0)
"""What an item is matched by: texts and integers, compared with the length tolerance on the integers."""


# --- normalisation ---------------------------------------------------------------------------------


def _clean(points: Sequence[Point]) -> list[Point]:
    out: list[Point] = []
    for point in points:
        if not out or out[-1] != point:
            out.append(point)
    while len(out) > 1 and out[0] == out[-1]:
        out.pop()
    return out


def doubled_area(points: Sequence[Point]) -> int:
    """Twice the signed area of a ring (shoelace formula); positive for a ring that runs counter-clockwise
    in a frame whose y axis points up."""
    n = len(points)
    return sum(points[k].x * points[(k + 1) % n].y - points[(k + 1) % n].x * points[k].y for k in range(n))


def ring(points: Sequence[Point], mids: Mapping[int, Point] | None = None) -> tuple[Edge, ...]:
    """A closed ring normalised: without repeated points or a closing copy, counter-clockwise, starting at
    its smallest point in ``(x, y)`` order. ``mids`` gives the arc mid of edge ``i`` (from vertex ``i`` to
    vertex ``i + 1``); a reversed ring keeps each mid on its edge."""
    given = mids or {}
    if mids:  # with arcs the indices of the edges must stay those of the stored points
        vertices = list(points)
    else:
        vertices = _clean(points)
    edges: list[Edge] = [(vertices[k], given.get(k)) for k in range(len(vertices))]
    if len(edges) < 2:
        return tuple(edges)
    area = doubled_area([vertex for vertex, _ in edges])
    if not area and any(mid is not None for _, mid in edges):  # a circle of two arcs: orient by the mids
        area = doubled_area([p for vertex, mid in edges for p in ((vertex, mid) if mid else (vertex,))])
    if area < 0:
        n = len(edges)
        edges = [(edges[(-k) % n][0], edges[(-k - 1) % n][1]) for k in range(n)]
    start = min(range(len(edges)), key=lambda k: (edges[k][0].x, edges[k][0].y))
    return tuple(edges[start:] + edges[:start])


def segment(a: Point, b: Point) -> tuple[Point, Point]:
    """A segment's ends as an unordered pair: the smaller in ``(x, y)`` order first."""
    return (a, b) if (a.x, a.y) <= (b.x, b.y) else (b, a)


def arc(start: Point, mid: Point, end: Point) -> tuple[Point, Point, Point]:
    """An arc by its ends in sorted order around its mid."""
    first, last = segment(start, end)
    return (first, mid, last)


def circle(centre: Point, edge: Point) -> tuple[Point, int]:
    """A circle by its centre and its squared radius (no root is taken)."""
    return (centre, (edge.x - centre.x) ** 2 + (edge.y - centre.y) ** 2)


def graphic_points(graphic: Graphic) -> tuple[object, ...]:
    """The normalised geometry of a graphic of its kind."""
    pts = graphic.points
    if graphic.kind == "line" and len(pts) == 2:
        return segment(pts[0], pts[1])
    if graphic.kind == "arc" and len(pts) == 3:
        return arc(pts[0], pts[1], pts[2])
    if graphic.kind == "circle" and len(pts) == 2:
        return circle(pts[0], pts[1])
    if graphic.kind == "rect" and len(pts) == 2:
        a, b = pts
        return tuple(vertex for vertex, _ in ring((a, Point(b.x, a.y), b, Point(a.x, b.y))))
    return tuple(vertex for vertex, _ in ring(pts))


# --- texts of locations ----------------------------------------------------------------------------


def _point(p: Point) -> str:
    return f"{p.x},{p.y}"


def ring_text(edges: Sequence[Edge]) -> str:
    """A normalised ring as text: its vertices joined by ``-``, an arc's mid in brackets after its start."""
    return "-".join(_point(v) + (f"({_point(m)})" if m is not None else "") for v, m in edges)


def geometry_text(found: Sequence[object]) -> str:
    parts: list[str] = []
    for item in found:
        parts.append(_point(item) if isinstance(item, Point) else f"r2={item}")
    return "-".join(parts)


# --- matching --------------------------------------------------------------------------------------


def _flat(key: object) -> list[object]:
    if isinstance(key, Point):
        return [key.x, key.y]
    if isinstance(key, tuple):
        out: list[object] = []
        parts: tuple[object, ...] = key  # pyright: ignore[reportUnknownVariableType]
        for part in parts:
            out.append("(")
            out += _flat(part)
            out.append(")")
        return out
    return [key]


def _near(one: Key, other: Key, tolerances: Tolerances) -> bool:
    left, right = _flat(one), _flat(other)
    if len(left) != len(right):
        return False
    for x, y in zip(left, right, strict=True):
        if type(x) is int and type(y) is int:
            if not norm.lengths_equal(x, y, tolerances):
                return False
        elif x != y:
            return False
    return True


@dataclass(frozen=True, slots=True)
class Shape:
    """One item of level 7: its match key, its location and what level 7 compares of it when matched."""

    key: Key
    where: str
    value: Mapping[str, Leaf] | None = None
    partial: bool = False
    """True for an item that states only some of the fields of its kind (a keep-out drawing standing for a
    rule area, change c0421): a pair with it compares only the fields it states."""


def match(
    a: Sequence[Shape], b: Sequence[Shape], tolerances: Tolerances
) -> tuple[list[tuple[Shape, Shape]], list[Shape], list[Shape]]:
    """Equal keys first as a multiset, then each unmatched item of ``a`` (in location order) with the first
    unmatched item of ``b`` whose key lies within the tolerance."""
    waiting: dict[str, list[int]] = defaultdict(list)
    for index, item in enumerate(b):
        waiting[repr(item.key)].append(index)
    taken = [False] * len(b)
    pairs: list[tuple[Shape, Shape]] = []
    left: list[Shape] = []
    for item in sorted(a, key=lambda s: s.where):
        found = waiting.get(repr(item.key))
        if found:
            index = found.pop(0)
            taken[index] = True
            pairs.append((item, b[index]))
        else:
            left.append(item)
    only_a: list[Shape] = []
    for item in left:
        index = None
        if tolerances.length_nm:
            index = next(
                (k for k, o in enumerate(b) if not taken[k] and _near(item.key, o.key, tolerances)), None
            )
        if index is None:
            only_a.append(item)
        else:
            taken[index] = True
            pairs.append((item, b[index]))
    return pairs, only_a, [item for k, item in enumerate(b) if not taken[k]]


Compare = Callable[[Shape, Shape], list[Difference]]


def _compare_set(
    kind: str, field: str, a: Sequence[Shape], b: Sequence[Shape], tolerances: Tolerances,
    compare: Compare | None = None,
) -> tuple[list[Difference], int]:  # fmt: skip
    pairs, only_a, only_b = match(a, b, tolerances)
    found = [Difference(LEVEL, kind, s.where, field, s.where, "") for s in only_a]
    found += [Difference(LEVEL, kind, s.where, field, "", s.where) for s in only_b]
    if compare is not None:
        for one, other in pairs:
            found += compare(one, other)
    return found, len(pairs)


# --- items -----------------------------------------------------------------------------------------


def _moved(key: object, shift: Point) -> object:
    """``key`` with every point moved by minus ``shift``: side ``b`` in the frame of side ``a``."""
    if isinstance(key, Point):
        return Point(key.x - shift.x, key.y - shift.y)
    if isinstance(key, tuple):
        items: tuple[object, ...] = key  # pyright: ignore[reportUnknownVariableType]
        return tuple(_moved(item, shift) for item in items)
    return key


def _key(found: object) -> Key:
    assert isinstance(found, tuple)
    items: Key = found  # pyright: ignore[reportUnknownVariableType]
    return items


def _shape_moved(
    shapes: Sequence[Shape], shift: Point, only: Callable[[Shape], bool] | None = None
) -> list[Shape]:
    """``shapes`` with their keys moved by minus ``shift`` (those ``only`` accepts, when it is given)."""
    if shift == ORIGIN:
        return list(shapes)
    return [
        replace(shape, key=_key(_moved(shape.key, shift))) if only is None or only(shape) else shape
        for shape in shapes
    ]


def _outline(outline: Outline | None) -> list[Shape]:
    if outline is None:
        return []
    shapes: list[Shape] = []
    mids: dict[int, dict[int, Point]] = defaultdict(dict)
    for found in outline.arcs:
        mids[found.ring][found.edge] = found.mid
    for index, points in enumerate((outline.points, *outline.cutouts)):
        if not points:
            continue
        edges = ring(points, mids.get(index))
        name = "board" if index == 0 else "cutout"
        shapes.append(Shape((name, tuple(edges)), f"board:outline:{ring_text(edges)}"))
    for slot in outline.slots:
        turned = slot.rotation % norm.HALF_TURN
        key = ("slot", slot.center, slot.length, slot.width, turned)
        shapes.append(Shape(key, f"board:slot:{_point(slot.center)}"))
    return shapes


def _net_names(design: Design) -> dict[str, str]:
    return {net.id: net.name for net in design.circuit.nets}


def _zones(design: Design, board: Board) -> list[Shape]:
    names = _net_names(design)
    shapes: list[Shape] = []
    for zone in board.zones:
        edges = ring(zone.outline)
        layers = ",".join(sorted(zone.layers))
        net = names.get(zone.net_id, zone.net_id) if zone.net_id is not None else ""
        value = fields(zone, skip=("outline", "layers", "net_id", "fills", "filled", "locked"))
        shapes.append(Shape((net, layers, tuple(edges)), f"board:{layers}:{ring_text(edges)}", value))
    return shapes


def _keepouts(keepouts: Sequence[Keepout], prefix: str) -> list[Shape]:
    """Rule areas keyed by layers and outline: the board's in its frame (``prefix`` ``board``), a footprint's
    in its pad frame and under its reference (change c0411), as KiCad stores them inside the footprint."""
    shapes: list[Shape] = []
    for keepout in keepouts:
        edges = ring(keepout.outline)
        layers = ",".join(sorted(keepout.layers))
        value = fields(keepout, skip=("outline", "layers", "intent"))
        shapes.append(Shape((layers, tuple(edges)), f"{prefix}:{layers}:{ring_text(edges)}", value))
    return shapes


DRAWN_KEEPOUT: Mapping[str, Leaf] = {
    "no_tracks": True,
    "no_vias": True,
    "no_pads": True,
    "no_copper_pour": True,
}
"""What a drawing of a keep-out layer keeps out, on every copper layer (change c0421; S-1710, c0410)."""


def _drawn_keepouts(
    drawn: Sequence[tuple[Graphic, tuple[Point, ...]]], copper: Sequence[str], prefix: str
) -> list[Shape]:
    """A rule-area shape per ring of a keep-out drawing (``pairing.split_keepout_drawings``): keyed as
    ``_keepouts`` keys a rule area, on every copper layer, stating only ``DRAWN_KEEPOUT`` and the drawing's
    ``form`` (``drawn_form``, change c0442), which only another drawing is compared on."""
    layers = ",".join(sorted(copper))
    shapes: list[Shape] = []
    for graphic, points in drawn:
        edges = ring(points)
        value = {**DRAWN_KEEPOUT, DRAWN_FORM: drawn_form(graphic)}
        shapes.append(Shape((layers, tuple(edges)), f"{prefix}:{layers}:{ring_text(edges)}", value,
                            partial=True))  # fmt: skip
    return shapes


DRAWN_FORM = "form"
"""The field of a drawn keep-out that says what was drawn (change c0442): ``stroke`` for a track, an arc, a
circle or an outline drawn with a width, ``area`` for a filled shape. A rule scope tells a track from a
region, so a keep-out line written back as a region is a ``keepout-field`` difference."""


def drawn_form(graphic: Graphic) -> str:
    """``area`` for a filled drawing or an outline of width 0, ``stroke`` for any other (``DRAWN_FORM``)."""
    filled = graphic.kind in ("polygon", "rect") and (graphic.filled or graphic.width <= 0)
    return "area" if filled else "stroke"


def _renamed(board: Board, names: Mapping[str, str]) -> Board:
    """``board`` with the layer names of its level-7 items mapped by ``names`` (layer aliases, c0421)."""
    if not names:
        return board

    def one(name: str) -> str:
        return names.get(name, name)

    def many(layers: Sequence[str]) -> tuple[str, ...]:
        return tuple(one(name) for name in layers)

    def graphics(items: Sequence[Graphic]) -> tuple[Graphic, ...]:
        return tuple(replace(g, layer=one(g.layer)) for g in items)

    def texts(items: Sequence[Text]) -> tuple[Text, ...]:
        return tuple(replace(t, layer=one(t.layer)) for t in items)

    def keepouts(items: Sequence[Keepout]) -> tuple[Keepout, ...]:
        return tuple(replace(k, layers=many(k.layers)) for k in items)

    footprints = tuple(_renamed_footprint(fp, names) for fp in board.footprints)
    return replace(
        board,
        layers=tuple(replace(layer, name=one(layer.name)) for layer in board.layers),
        graphics=graphics(board.graphics),
        texts=texts(board.texts),
        keepouts=keepouts(board.keepouts),
        zones=tuple(replace(z, layers=many(z.layers)) for z in board.zones),
        dimensions=tuple(replace(d, layer=one(d.layer)) for d in board.dimensions),
        footprints=footprints,
    )


def _renamed_footprint(footprint: FootprintInstance, names: Mapping[str, str]) -> FootprintInstance:
    """``footprint`` with the layers of its graphics, texts, rule areas and fields mapped by ``names``."""
    if not names:
        return footprint

    def one(name: str) -> str:
        return names.get(name, name)

    return replace(
        footprint,
        graphics=tuple(replace(g, layer=one(g.layer)) for g in footprint.graphics),
        texts=tuple(replace(t, layer=one(t.layer)) for t in footprint.texts),
        keepouts=tuple(replace(k, layers=tuple(one(n) for n in k.layers)) for k in footprint.keepouts),
        fields=tuple(replace(f, layer=one(f.layer)) for f in footprint.fields),
    )


def _copper(board: Board) -> list[str]:
    return [layer.name for layer in board.layers if layer.kind == "copper"]


def _graphics(graphics: Sequence[Graphic], prefix: str) -> list[Shape]:
    """Graphics keyed by layer, kind, normalised geometry and fill; the width is compared once matched
    (``graphic-field``, change c0281), so a stroke drawn wider is one difference, not two missing items."""
    shapes: list[Shape] = []
    for graphic in graphics:
        found = graphic_points(graphic)
        key = (graphic.layer, graphic.kind, found, graphic.filled)
        value: dict[str, Leaf] = {"width": graphic.width}
        shapes.append(Shape(key, f"{prefix}:{graphic.layer}:{geometry_text(found)}", value))
    return shapes


def _board_graphics(
    a: Sequence[Graphic],
    b: Sequence[Graphic],
    tolerances: Tolerances,
    compare: Compare,
    shift: Point = ORIGIN,
) -> tuple[list[Difference], int]:
    """The board graphics matched as items; then the ``Edge.Cuts`` drawings left on each side, chained into
    closed rings (``pairing.edge_rings``), matched as rings by their normalised edges (change c0421). A
    ring left over is one ``graphic-missing``; a drawing of no closed ring stays an item. The ``Edge.Cuts``
    drawings and rings of side ``b`` are moved by minus ``shift`` (change c0441): the board shape compares
    in the frame of side ``a``."""
    shapes_a = _graphics(a, "board")
    shapes_b = _shape_moved(_graphics(b, "board"), shift, lambda s: s.key[0] == pairing.EDGE_LAYER)
    pairs, only_a, only_b = match(shapes_a, shapes_b, tolerances)
    found: list[Difference] = []
    for one, other in pairs:
        found += compare(one, other)
    by_shape_a = {id(shape): graphic for shape, graphic in zip(shapes_a, a, strict=True)}
    by_shape_b = {id(shape): graphic for shape, graphic in zip(shapes_b, b, strict=True)}
    left_a = [by_shape_a[id(shape)] for shape in only_a]
    left_b = [by_shape_b[id(shape)] for shape in only_b]

    def rings(graphics: Sequence[Graphic]) -> tuple[list[Shape], list[Graphic]]:
        closed, rest = pairing.edge_rings(graphics)
        shapes: list[Shape] = []
        for points, mids in closed:
            edges = ring(points, mids)
            shapes.append(
                Shape(("edge-ring", tuple(edges)), f"board:{pairing.EDGE_LAYER}:{ring_text(edges)}")
            )
        return shapes, rest

    rings_a, rest_a = rings(left_a)
    rings_b, rest_b = rings(left_b)
    rings_b = _shape_moved(rings_b, shift)
    ring_pairs, ring_a, ring_b = match(rings_a, rings_b, tolerances)
    found += [Difference(LEVEL, "graphic-missing", s.where, "graphic", s.where, "") for s in ring_a]
    found += [Difference(LEVEL, "graphic-missing", s.where, "graphic", "", s.where) for s in ring_b]
    found += [Difference(LEVEL, "graphic-missing", s.where, "graphic", s.where, "")
              for s in _graphics(rest_a, "board")]  # fmt: skip
    found += [Difference(LEVEL, "graphic-missing", s.where, "graphic", "", s.where)
              for s in _graphics(rest_b, "board")]  # fmt: skip
    return found, len(pairs) + len(ring_pairs)


def _texts(texts: Sequence[Text], prefix: str) -> list[Shape]:
    ordered = sorted(texts, key=lambda t: (t.layer, t.text, t.position.x, t.position.y))
    return [
        Shape((t.layer, t.text), f"{prefix}:{t.layer}:{t.text}", fields(t, skip=("text", "layer")))
        for t in ordered
    ]


def _text_pairs(
    kind: str, a: Sequence[Shape], b: Sequence[Shape], tolerances: Tolerances
) -> tuple[list[Difference], int]:
    """Texts match by layer and text, the n-th of one key on side ``a`` with the n-th on side ``b``."""
    by_key: dict[str, list[Shape]] = defaultdict(list)
    for item in b:
        by_key[repr(item.key)].append(item)
    found: list[Difference] = []
    compared = 0
    for item in a:
        held = by_key.get(repr(item.key))
        if not held:
            found.append(Difference(LEVEL, "text-missing", item.where, "text", item.where, ""))
            continue
        other = held.pop(0)
        compared += 1
        found += field_differences(
            kind,
            item.where,
            item.value or {},
            other.value or {},
            tolerances,
            LEVEL,
            orientation_paths=("rotation",),
        )
    for held in by_key.values():
        found += [Difference(LEVEL, "text-missing", s.where, "text", "", s.where) for s in held]
    return found, compared


def _holes(board: Board) -> list[Shape]:
    return [
        Shape(
            (hole.position, hole.drill, hole.plated, hole.length or 0, hole.rotation),
            f"board:holes:{_point(hole.position)}",
        )
        for hole in board.holes
    ]


def _dimensions(board: Board) -> list[Shape]:
    shapes: list[Shape] = []
    for dim in board.dimensions:
        value = fields(dim)
        key = tuple(sorted((k, repr(v)) for k, v in value.items() if k not in ("start", "end")))
        ends = segment(dim.start, dim.end)
        shapes.append(Shape((ends, key), f"board:{dim.layer}:{_point(ends[0])}-{_point(ends[1])}"))
    return shapes


def _field_pose(
    ref: str,
    one: FootprintInstance,
    other: FootprintInstance,
    tolerances: Tolerances,
    across: bool = False,
    parameters: tuple[Mapping[str, str], Mapping[str, str]] = ({}, {}),
) -> list[Difference]:
    """The fields of a footprint pair by name. ``across`` (sides of two backends, change c0421): a hidden
    field on one side only is not a difference (one backend declares every footprint's reference and value,
    hidden where the other holds none), nor is a field on one side only that the other side's component
    holds as a parameter of that name, with the value its own component holds if it holds one (``parameters``:
    each side's component properties; one backend places every parameter as a field, the other keeps it on
    the component)."""
    held_a = {f.name: f for f in one.fields if f.name not in LENS_FIELDS}
    held_b = {f.name: f for f in other.fields if f.name not in LENS_FIELDS}
    found: list[Difference] = []
    for name in sorted(set(held_a) | set(held_b)):
        where = f"{ref}:{name}"
        if name not in held_a or name not in held_b:
            if across and not (held_a.get(name) or held_b[name]).visible:
                continue
            mine, theirs = (
                (parameters[0], parameters[1]) if name in held_a else (parameters[1], parameters[0])
            )
            if across and name in theirs and theirs[name] == mine.get(name):
                continue
            found.append(
                Difference(
                    LEVEL,
                    "field-pose",
                    where,
                    "name",
                    name if name in held_a else "",
                    name if name in held_b else "",
                )
            )
            continue
        found += field_differences(
            "field-pose", where, fields(held_a[name], skip=("name",)), fields(held_b[name], skip=("name",)),
            tolerances, LEVEL, orientation_paths=("rotation",),
        )  # fmt: skip
    return found


FootprintPair = tuple[str, FootprintInstance, FootprintInstance]


def level_geometry(
    a: Design,
    b: Design,
    pairs: Sequence[FootprintPair],
    tolerances: Tolerances = EXACT,
    *,
    aliases: Mapping[str, str] | None = None,
    keepout_layers: tuple[Collection[str], Collection[str]] = ((), ()),
    across: bool = False,
    shift: Point = ORIGIN,
) -> LevelResult:
    """Level 7 over the boards of ``a`` and ``b`` and the footprint pairs of level 3. ``aliases`` maps side
    ``b``'s name of a layer paired by user name to side ``a``'s; ``keepout_layers`` names each side's
    layers whose drawings are keep-outs, compared with rule areas, and ``across`` marks sides of two backends
    (``_field_pose``; change c0421). ``shift`` is the translation level 4 removed from side ``b`` (change
    c0441): the board shape of side ``b`` (its outline, cut-outs, slots and ``Edge.Cuts`` drawings) is moved
    back by it, so a board written in another frame compares its shape exactly; every other item keeps its
    place."""
    assert a.board is not None and b.board is not None
    names = aliases or {}
    board_a, board_b = a.board, _renamed(b.board, names)
    keep_a, keep_b = keepout_layers
    keep_b = [names.get(name, name) for name in keep_b]
    found: list[Difference] = []
    counts: dict[str, int] = {}

    def fields_of(kind: str) -> Compare:
        def compare(one: Shape, other: Shape) -> list[Difference]:
            mine, theirs = dict(one.value or {}), dict(other.value or {})
            if one.partial != other.partial:  # a drawing against a rule area: no form to compare (c0442)
                mine.pop(DRAWN_FORM, None)
                theirs.pop(DRAWN_FORM, None)
            if one.partial or other.partial:
                stated = set(mine if one.partial else theirs)
                mine = {k: v for k, v in mine.items() if k in stated}
                theirs = {k: v for k, v in theirs.items() if k in stated}
            return field_differences(kind, one.where, mine, theirs, tolerances, LEVEL)

        return compare

    zone_field, keepout_field = fields_of("zone-field"), fields_of("keepout-field")
    graphic_field = fields_of("graphic-field")
    graphics_a, drawn_a = pairing.split_keepout_drawings(board_a.graphics, keep_a)
    graphics_b, drawn_b = pairing.split_keepout_drawings(board_b.graphics, keep_b)
    keepouts_a = _keepouts(board_a.keepouts, "board") + _drawn_keepouts(drawn_a, _copper(board_a), "board")
    keepouts_b = _keepouts(board_b.keepouts, "board") + _drawn_keepouts(drawn_b, _copper(board_b), "board")
    board_items: tuple[tuple[str, tuple[list[Difference], int]], ...] = (
        ("outline", _compare_set("outline-missing", "ring", _outline(board_a.outline),
                                 _shape_moved(_outline(board_b.outline), shift), tolerances)),
        ("zones", _compare_set("zone-missing", "zone", _zones(a, board_a), _zones(b, board_b), tolerances,
                               zone_field)),
        ("keepouts", _compare_set("keepout-missing", "keepout", keepouts_a, keepouts_b, tolerances,
                                  keepout_field)),
        ("graphics", _board_graphics(graphics_a, graphics_b, tolerances, graphic_field, shift)),
        ("texts", _text_pairs("text-field", _texts(board_a.texts, "board"), _texts(board_b.texts, "board"),
                              tolerances)),
        ("holes", _compare_set("hole-missing", "hole", _holes(board_a), _holes(board_b), tolerances)),
        ("dimensions", _compare_set("dimension-missing", "dimension", _dimensions(board_a),
                                    _dimensions(board_b), tolerances)),
    )  # fmt: skip
    for name, (differences, compared) in board_items:
        found += differences
        counts[name] = compared
    footprint_items = 0
    copper_a, copper_b = _copper(board_a), _copper(board_b)
    props_a = {component.id: component.properties for component in a.circuit.components}
    props_b = {component.id: component.properties for component in b.circuit.components}
    for ref, one, held in pairs:
        other = _renamed_footprint(held, names)
        own_a, fp_drawn_a = pairing.split_keepout_drawings(one.graphics, keep_a)
        own_b, fp_drawn_b = pairing.split_keepout_drawings(other.graphics, keep_b)
        differences, compared = _compare_set(
            "graphic-missing", "graphic", _graphics(own_a, ref), _graphics(own_b, ref), tolerances,
            graphic_field,
        )  # fmt: skip
        found += differences
        footprint_items += compared
        differences, compared = _compare_set(
            "keepout-missing",
            "keepout",
            _keepouts(one.keepouts, ref) + _drawn_keepouts(fp_drawn_a, copper_a, ref),
            _keepouts(other.keepouts, ref) + _drawn_keepouts(fp_drawn_b, copper_b, ref),
            tolerances,
            keepout_field,
        )
        found += differences
        footprint_items += compared
        differences, compared = _text_pairs(
            "text-field", _texts(one.texts, ref), _texts(other.texts, ref), tolerances
        )
        found += differences
        footprint_items += compared
        parameters = (props_a.get(one.component_id, {}), props_b.get(held.component_id, {}))
        found += _field_pose(ref, one, other, tolerances, across, parameters)
        footprint_items += len({f.name for f in one.fields} & {f.name for f in other.fields} - LENS_FIELDS)
    counts["footprint_items"] = footprint_items
    ordered = tuple(sorted(found, key=lambda d: (d.where, d.kind, d.field, d.a, d.b)))
    return LevelResult(LEVEL, sum(counts.values()), ordered, (), counts)


__all__ = [
    "LENS_FIELDS",
    "arc",
    "circle",
    "doubled_area",
    "graphic_points",
    "level_geometry",
    "ring",
    "ring_text",
    "segment",
]
