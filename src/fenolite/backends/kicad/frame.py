# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Board-frame geometry of a KiCad design: every pad and every footprint's courtyard where it lies on the
board (capability board-frame; user guide ``docs/copper.md``; facts: ``docs/formats/kicad/frame.md``).

The board frame is the KiCad file frame: X to the right, Y down, integer nanometres, angles in
microdegrees. A placed footprint stores its children in its own frame, already mirrored on the bottom
side, so everything here is ``at + R(θ)·stored`` with no further mirror (``H-G-BOTTOM-PLACE``).

A copper entry is the set of points within ``width / 2`` of an integer core, so circles, ovals and rounded
rectangles are exact. Coordinates are computed with rationals and rounded half to even once.
"""

from __future__ import annotations

import dataclasses
from collections.abc import Iterable, Mapping, Sequence
from fractions import Fraction
from types import MappingProxyType

from fenolite.backends.base import BoardPad, PadCopper, PlacedExtent
from fenolite.backends.kicad.layers import expand_layers
from fenolite.backends.kicad.pcb import pad_angle_to_board
from fenolite.backends.kicad.sexpr import Atom, AtomKind, Node
from fenolite.backends.kicad.slots import from_ext, opaque_child
from fenolite.core.coords import Point
from fenolite.core.errors import Issue, Severity
from fenolite.core.evidence import Evidence, Level
from fenolite.core.units import Nm, Udeg
from fenolite.geometry import (
    DEFAULT_TOL,
    Arc,
    Circle,
    GeometryError,
    Polygon,
    Segment,
    Transform,
    assemble_rings,
    ceil_sqrt,
    convex_hull,
    cos_sin_fixed,
    floor_sqrt,
    normalize_polygons,
    round_point,
)
from fenolite.geometry.transform import TRIG_BITS
from fenolite.model.base import Opaque
from fenolite.model.board import FootprintInstance, Graphic, Pad, PadShape, Size
from fenolite.model.design import Design
from fenolite.model.library import FootprintDef

EVIDENCE = Evidence(
    Level.INFERRED,
    hypotheses=(
        "H-G-ROT-DIR",
        "H-G-BOTTOM-PLACE",
        "H-G-PAD-ANGLE-ABS",
        "H-G-FRAME-SHAPE",
        "H-G-FRAME-CRTYD-2",
    ),
)
"""``INFERRED``: positions and rotations rest on the three verified rows; the shape and courtyard rows cover
the bench footprints, not every pad token or courtyard."""
COURTYARD_LAYERS = ("F.CrtYd", "B.CrtYd")
FRAME_ISSUE_CODES: Mapping[str, Severity] = MappingProxyType(
    {
        "kicad.frame.courtyard-malformed": "warning",
        "kicad.frame.no-courtyard": "info",
        "kicad.frame.shape-approximated": "info",
    }
)
PATH_PROPERTY = "fenolite.path"
CURVE_GROWTH = 2 * DEFAULT_TOL + 2
"""What a polygonised curve adds to its stroke width, so the polyline still contains the curve."""
_ONE = 1 << TRIG_BITS
_DEFAULT_RATIO = Fraction(1, 4)
_BOXED_SHAPES = frozenset({"roundrect", "custom", "trapezoid"})
_GRAPHIC_HEADS = {
    "fp_line": "line", "fp_rect": "rect", "fp_circle": "circle", "fp_arc": "arc", "fp_poly": "polygon",
    "gr_line": "line", "gr_rect": "rect", "gr_circle": "circle", "gr_arc": "arc", "gr_poly": "polygon",
    "gr_curve": "curve",
}  # fmt: skip
Frac = tuple[Fraction, Fraction]


def _issue(code: str, message: str, where: str) -> Issue:
    return Issue(code, FRAME_ISSUE_CODES[code], message, where=where)


# --- exact placement ------------------------------------------------------------------------------


@dataclasses.dataclass(frozen=True, slots=True)
class _Placement:
    """``p ↦ at + R(θ)·p`` for rational ``p``, rounded half to even once (``H-G-ROT-DIR``)."""

    at: Point
    udeg: Udeg

    def exact(self, p: Frac) -> Frac:
        c, s = cos_sin_fixed(self.udeg)
        x, y = p
        return self.at.x + (x * c + y * s) / _ONE, self.at.y + (-x * s + y * c) / _ONE

    def apply(self, p: Frac) -> Point:
        return round_point(*self.exact(p))

    def points(self, points: Iterable[Frac]) -> tuple[Point, ...]:
        return tuple(self.apply(p) for p in points)


def _frac(p: Point) -> Frac:
    return Fraction(p.x), Fraction(p.y)


def _half_even(value: Fraction) -> int:
    return round_point(value, 0).x


def _dedupe(points: Iterable[Point]) -> tuple[Point, ...]:
    """A ring without consecutive duplicates and without its first point repeated at the end."""
    out: list[Point] = []
    for point in points:
        if not out or out[-1] != point:
            out.append(point)
    while len(out) > 1 and out[0] == out[-1]:
        out.pop()
    return tuple(out)


def _normal_ring(points: Sequence[Point]) -> tuple[Point, ...]:
    """The ring in the kernel's normal form; a ring ``Polygon`` refuses is kept as it is."""
    try:
        return tuple(Polygon(tuple(points)).normalize().outer)
    except (GeometryError, ValueError):
        return tuple(points)


# --- tokens ---------------------------------------------------------------------------------------


def _opaque_nodes(entity: object) -> list[Node]:
    """The opaque children of an entity's own node, as parsed nodes, in file order."""
    bag = getattr(entity, "ext", {}).get("kicad")
    if bag is None:
        return []
    nodes: list[Node] = []
    for slot in from_ext(bag):
        if isinstance(slot, Opaque):
            child = opaque_child(slot)
            if isinstance(child, Node):
                nodes.append(child)
    return nodes


def _numbers(node: Node) -> list[Atom]:
    return [a for a in node.atoms() if a.kind == AtomKind.NUMBER]


def _nm(atom: Atom) -> int:
    return atom.to_nm(exact=False)


def _xy(node: Node | None) -> Point | None:
    if node is None:
        return None
    numbers = _numbers(node)
    return Point(_nm(numbers[0]), _nm(numbers[1])) if len(numbers) >= 2 else None


def _stroke(node: Node) -> int:
    """The stroke width of a graphic: ``(width W)`` or ``(stroke (width W) …)``, else 0."""
    stroke = node.find("stroke")
    width = (stroke if stroke is not None else node).find("width")
    numbers = _numbers(width) if width is not None else []
    return _nm(numbers[0]) if numbers else 0


def _filled(node: Node, *, default: bool) -> bool:
    fill = node.find("fill")
    if fill is None:
        return default
    atoms = fill.atoms()
    if not atoms:
        inner = fill.find("type")  # the newer ``(fill (type solid))`` form
        atoms = inner.atoms() if inner is not None else ()
    return bool(atoms) and atoms[0].text not in ("no", "none")


@dataclasses.dataclass(frozen=True, slots=True)
class _Shape:
    """A graphic in its stored frame: its kind, its points and arcs in order, its stroke and its fill."""

    kind: str
    points: tuple[Point, ...]
    width: int = 0
    filled: bool = False
    arcs: tuple[tuple[int, Point, Point, Point], ...] = ()
    """For a polygon: ``(index among the points, start, mid, end)`` of each arc of its ``pts``."""
    layer: str = ""


def _shape(node: Node, *, default_fill: bool) -> _Shape | None:
    """A ``fp_*`` or ``gr_*`` node as a shape, or ``None`` for a head or form this module does not know."""
    kind = _GRAPHIC_HEADS.get(node.name)
    if kind is None:
        return None
    layer_node = node.find("layer")
    layer = layer_node.atoms()[0].value if layer_node is not None and layer_node.atoms() else ""
    width, filled = _stroke(node), _filled(node, default=default_fill)
    if kind in ("polygon", "curve"):
        pts = node.find("pts")
        if pts is None:
            return None
        points: list[Point] = []
        arcs: list[tuple[int, Point, Point, Point]] = []
        for child in pts.nodes():
            if child.name == "xy":
                point = _xy(child)
                if point is None:
                    return None
                points.append(point)
            elif child.name == "arc":
                ends = [_xy(child.find(name)) for name in ("start", "mid", "end")]
                if None in ends:
                    return None
                start, mid, end = (p for p in ends if p is not None)
                arcs.append((len(points), start, mid, end))
                points += [start, end]
        return _Shape(kind, tuple(points), width, filled, tuple(arcs), layer)
    names = {"line": ("start", "end"), "rect": ("start", "end"), "circle": ("center", "end")}.get(
        kind, ("start", "mid", "end")
    )
    found = [_xy(node.find(name)) for name in names]
    if None in found:
        return None
    return _Shape(kind, tuple(p for p in found if p is not None), width, filled, (), layer)


def _graphic_shape(graphic: Graphic) -> _Shape:
    return _Shape(graphic.kind, tuple(graphic.points), graphic.width, graphic.filled, (), graphic.layer)


# --- pad copper -----------------------------------------------------------------------------------

_Entry = tuple[tuple[Frac, ...], Fraction | int, bool, bool]
"""``(core in the pad frame, width, filled, exact)`` before placement."""


def _box(w: Fraction | int, h: Fraction | int) -> tuple[Frac, ...]:
    x, y = Fraction(w) / 2, Fraction(h) / 2
    return ((-x, -y), (x, -y), (x, y), (-x, y))


def _basic(shape: PadShape, size: Size, ratio: Fraction | None, delta: Point | None) -> list[_Entry]:
    """The entries of a ``circle``, ``rect``, ``oval``, ``roundrect`` or ``trapezoid`` of ``size``."""
    w, h = size.w, size.h
    origin = (Fraction(0), Fraction(0))
    if shape == "circle" or (shape == "oval" and w == h):
        return [((origin,), w, False, True)]
    if shape == "oval":
        half = Fraction(abs(w - h), 2)
        ends = (
            ((-half, Fraction(0)), (half, Fraction(0))) if w > h else ((origin[0], -half), (origin[0], half))
        )
        return [(ends, min(w, h), False, True)]
    if shape == "roundrect":
        q = min(max(_DEFAULT_RATIO if ratio is None else ratio, Fraction(0)), Fraction(1, 2))
        r = _half_even(q * min(w, h))
        inner_w, inner_h = w - 2 * r, h - 2 * r
        if r == 0:
            return [(_box(w, h), 0, True, True)]
        if inner_w > 0 and inner_h > 0:
            return [(_box(inner_w, inner_h), 2 * r, True, True)]
        if inner_w > 0:
            return [
                (((Fraction(-inner_w, 2), origin[1]), (Fraction(inner_w, 2), origin[1])), 2 * r, False, True)
            ]
        if inner_h > 0:
            return [
                (((origin[0], Fraction(-inner_h, 2)), (origin[0], Fraction(inner_h, 2))), 2 * r, False, True)
            ]
        return [((origin,), 2 * r, False, True)]
    if shape == "trapezoid":
        grow = 0 if delta is None else abs(delta.x) + abs(delta.y)
        return [(_box(w + 2 * grow, h + 2 * grow), 0, True, grow == 0)]
    return [(_box(w, h), 0, True, shape == "rect")]


def _pad_tokens(pad: Pad) -> dict[str, Node]:
    return {node.name: node for node in _opaque_nodes(pad)}


def _ratio(tokens: Mapping[str, Node]) -> Fraction | None:
    node = tokens.get("roundrect_rratio")
    numbers = _numbers(node) if node is not None else []
    return Fraction(numbers[0].text) if numbers else None


def _chamfered(tokens: Mapping[str, Node]) -> bool:
    corners = tokens.get("chamfer")
    return "chamfer_ratio" in tokens and corners is not None and bool(corners.atoms())


def _anchor(tokens: Mapping[str, Node]) -> PadShape:
    options = tokens.get("options")
    anchor = options.find("anchor") if options is not None else None
    atoms = anchor.atoms() if anchor is not None else ()
    return "circle" if atoms and atoms[0].text == "circle" else "rect"


def _own_entries(pad: Pad, tokens: Mapping[str, Node]) -> list[_Entry]:
    """The entries of the pad's own shape and size, in the pad frame, primitives left out."""
    if pad.shape == "custom":
        return _basic(_anchor(tokens), pad.size, None, None)
    entries = _basic(pad.shape, pad.size, _ratio(tokens), _xy(tokens.get("rect_delta")))
    if _chamfered(tokens):
        entries = [(core, width, filled, False) for core, width, filled, _ in entries]
    return entries


def _layer_entries(
    pad: Pad, layer: str, inner: bool, tokens: Mapping[str, Node]
) -> tuple[list[_Entry], bool]:
    """``(entries, own)`` for ``layer``: the pad's own shape, or a padstack layer's (``own`` false)."""
    stack = pad.padstack
    if stack is None or layer == "F.Cu":
        return _own_entries(pad, tokens), True
    named = {entry.layer: entry for entry in stack.layers[1:]}
    entry = named.get(layer) or (named.get("Inner") if inner else None)
    if entry is None:
        return _own_entries(pad, tokens), True
    if entry.shape in _BOXED_SHAPES:
        return [(_box(entry.size.w, entry.size.h), 0, True, False)], False
    return _basic(entry.shape, entry.size, None, None), False


def _primitive_entries(
    shape: _Shape, placement: _Placement
) -> list[tuple[tuple[Point, ...], int, bool, bool]]:
    """The placed entries of one custom primitive: ``(core, width, filled, exact)``."""
    moved = placement.points(_frac(p) for p in shape.points)
    if shape.kind == "line":
        return [(moved, shape.width, False, True)]
    if shape.kind == "rect":
        (x0, y0), (x1, y1) = _frac(shape.points[0]), _frac(shape.points[1])
        ring = placement.points(((x0, y0), (x1, y0), (x1, y1), (x0, y1)))
        return (
            [(ring, shape.width, True, True)]
            if shape.filled
            else [((*ring, ring[0]), shape.width, False, True)]
        )
    if shape.kind == "circle":
        dx, dy = shape.points[1].x - shape.points[0].x, shape.points[1].y - shape.points[0].y
        radius2 = dx * dx + dy * dy
        if radius2 == 0:
            return []
        if shape.filled:
            radius = ceil_sqrt(radius2)
            return [((moved[0],), 2 * radius + shape.width, False, floor_sqrt(radius2) == radius)]
        circle = Circle(moved[0], radius2).polygonize(DEFAULT_TOL)
        return [((*circle, circle[0]), shape.width + CURVE_GROWTH, False, False)]
    if shape.kind == "arc":
        try:
            polyline = Arc(*moved).polygonize(DEFAULT_TOL)
        except GeometryError:
            polyline = moved
        return [(polyline, shape.width + CURVE_GROWTH, False, False)]
    if shape.kind == "curve":
        hull = convex_hull(moved)
        return [(hull, shape.width, True, False)] if len(hull) >= 3 else [(hull, shape.width, False, False)]
    if not shape.arcs:  # a polygon of xy points
        if len(moved) < 3:
            return []
        if shape.filled:
            return [(moved, shape.width, True, True)]
        return [((*moved, moved[0]), shape.width, False, True)]
    mixed: list[Point] = []
    starts = {index: (start, mid, end) for index, start, mid, end in shape.arcs}
    index = 0
    while index < len(shape.points):
        if index in starts:
            arc = placement.points(_frac(p) for p in starts[index])
            try:
                mixed += Arc(*arc).polygonize(DEFAULT_TOL)
            except GeometryError:
                mixed += arc
            index += 2
        else:
            mixed.append(moved[index])
            index += 1
    width = shape.width + CURVE_GROWTH
    ring = _dedupe(mixed)
    if len(ring) < 3:
        return []
    return [(ring, width, True, False)] if shape.filled else [((*ring, ring[0]), width, False, False)]


def _copper(
    pad: Pad, layers: Sequence[str], inner: frozenset[str], placement: _Placement, tokens: Mapping[str, Node]
) -> tuple[PadCopper, ...]:
    if pad.kind == "np_thru_hole":
        return ()
    primitives: list[_Shape] = []
    if pad.shape == "custom" and "primitives" in tokens:
        shapes = (_shape(node, default_fill=True) for node in tokens["primitives"].nodes())
        primitives = [s for s in shapes if s is not None]
    found: list[PadCopper | None] = []
    for layer in layers:
        entries, own = _layer_entries(pad, layer, layer in inner, tokens)
        for core, width, filled, exact in entries:
            points = placement.points(core)
            if len(points) == 2 and not filled:
                points = tuple(sorted(points))
            found.append(_entry(layer, points, int(width), filled, exact))
        if own:
            for shape in primitives:
                for points, width, filled, exact in _primitive_entries(shape, placement):
                    found.append(_entry(layer, points, width, filled, exact))
    return tuple(entry for entry in found if entry is not None)


def _entry(layer: str, core: Sequence[Point], width: int, filled: bool, exact: bool) -> PadCopper | None:
    """A ``PadCopper`` with a filled core in the normal form; ``None`` for a core the record refuses."""
    points = _normal_ring(core) if filled else tuple(core)
    if filled and len(points) < 3:
        filled = False
    try:
        return PadCopper(layer, points, width, filled, exact)
    except ValueError:
        return None


def _hole(pad: Pad, placement: _Placement, tokens: Mapping[str, Node]) -> tuple[tuple[Point, ...], Nm | None]:
    """The drilled hole in the board frame: a point, or the two ends of a slot, and the drill size."""
    stack = pad.padstack
    if (
        stack is not None
        and stack.hole_shape == "slot"
        and pad.drill is not None
        and stack.hole_length is not None
    ):
        half = Fraction(stack.hole_length - pad.drill, 2)
        relative_rotation = stack.hole_rotation - pad.rotation
        c, s = cos_sin_fixed(relative_rotation)
        dx, dy = half * c / _ONE, -half * s / _ONE
        x, y = 0, 0
        ends = ((x - dx, y - dy), (x + dx, y + dy))
        return tuple(sorted(placement.points(ends))), pad.drill
    node = tokens.get("drill")
    if node is None:
        if pad.drill is None:
            return (), None
        return (placement.at,), pad.drill
    sizes = [_nm(a) for a in _numbers(node)]
    if not sizes:
        return (), None
    offset = _xy(node.find("offset")) or Point(0, 0)
    ox, oy = _frac(offset)
    oval = any(a.text == "oval" for a in node.atoms())
    w, h = sizes[0], sizes[1] if oval and len(sizes) > 1 else sizes[0]
    if w == h:
        return (placement.apply((ox, oy)),), w
    half = Fraction(abs(w - h), 2)
    ends = ((ox - half, oy), (ox + half, oy)) if w > h else ((ox, oy - half), (ox, oy + half))
    return tuple(sorted(placement.points(ends))), min(w, h)


def _copper_layers(design: Design) -> tuple[str, ...]:
    layers = design.board.layers if design.board is not None else ()
    return tuple(la.name for la in sorted(layers, key=lambda la: la.ordinal) if la.kind == "copper")


def _pad_record(
    design_nets: Mapping[str, str],
    footprint: FootprintInstance,
    ref: str,
    path: str,
    pad: Pad,
    copper_layers: Sequence[str],
    issues: list[Issue],
) -> BoardPad:
    position = Transform.placement(footprint.position, footprint.rotation).apply(pad.position)
    rotation = pad_angle_to_board(pad.rotation, footprint.rotation)
    placement = _Placement(position, rotation)
    tokens = _pad_tokens(pad)
    known = set(copper_layers)
    layers = [name for name in expand_layers(pad.layers, copper_layers) if name in known]
    inner = frozenset(copper_layers[1:-1])
    copper = _copper(pad, layers, inner, placement, tokens)
    if any(not entry.exact for entry in copper):
        issues.append(
            _issue(
                "kicad.frame.shape-approximated",
                f"the copper of pad {pad.number!r} of {ref or footprint.lib_ref} is a conservative superset "
                f"of its {pad.shape} shape",
                f"{ref or footprint.id}:{pad.number}",
            )
        )
    hole, drill = _hole(pad, placement, tokens)
    return BoardPad(
        footprint_id=footprint.id,
        ref=ref,
        path=path,
        pad_id=pad.id,
        number=pad.number,
        kind=pad.kind,
        position=position,
        rotation=rotation,
        side=footprint.side,
        layers=tuple(pad.layers),
        net_id=pad.net_id,
        net=design_nets.get(pad.net_id) if pad.net_id is not None else None,
        copper=copper,
        hole=hole,
        drill=drill,
    )


def _footprint_pads(
    design: Design, footprint: FootprintInstance, issues: list[Issue]
) -> tuple[BoardPad, ...]:
    component = next((c for c in design.circuit.components if c.id == footprint.component_id), None)
    ref = component.ref if component is not None else ""
    path = component.properties.get(PATH_PROPERTY, "") if component is not None else ""
    nets = {net.id: net.name for net in design.circuit.nets}
    layers = _copper_layers(design)
    return tuple(_pad_record(nets, footprint, ref, path, pad, layers, issues) for pad in footprint.pads)


def board_pads(design: Design, *, issues: list[Issue] | None = None) -> tuple[BoardPad, ...]:
    """One record per pad of every footprint of the board, footprints in board order and pads in footprint
    order: board-frame position and rotation, layers, net, copper entries and hole."""
    found: list[Issue] = []
    footprints = design.board.footprints if design.board is not None else ()
    pads = tuple(pad for footprint in footprints for pad in _footprint_pads(design, footprint, found))
    if issues is not None:
        issues.extend(found)
    return pads


def find_pads(design: Design, component: str, number: str | int) -> tuple[BoardPad, ...]:
    """The pads numbered ``number`` of the footprints of ``component`` (a component path first, else a
    reference), every pad sharing the number included, in board order and pad order."""
    wanted = str(number)
    pads = board_pads(design)
    matched = [pad for pad in pads if pad.path and pad.path == component]
    if not matched:
        matched = [pad for pad in pads if pad.ref == component]
    if not matched:
        known = sorted({pad.path or pad.ref for pad in pads if pad.path or pad.ref})
        raise KeyError(
            f"no footprint of the component {component!r} on the board (components: {', '.join(known)})"
        )
    found = tuple(pad for pad in matched if pad.number == wanted)
    if not found:
        numbers = ", ".join(dict.fromkeys(pad.number for pad in matched if pad.number))
        raise KeyError(f"{component} has no pad {wanted!r} (pads: {numbers})")
    return found


# --- placed extents -------------------------------------------------------------------------------


def _has_slots(footprint: FootprintInstance) -> bool:
    return "kicad" in footprint.ext


def _courtyard_shapes(footprint: FootprintInstance) -> list[_Shape]:
    shapes = (_shape(node, default_fill=False) for node in _opaque_nodes(footprint))
    return [s for s in shapes if s is not None and s.layer in COURTYARD_LAYERS]


def _face(
    shapes: Sequence[_Shape], move: Transform, tol: int
) -> tuple[tuple[tuple[Point, ...], ...], bool, bool]:
    """``(rings, exact, closed)`` of the shapes of one face, moved to the board frame."""
    rings: list[tuple[Point, ...]] = []
    pieces: list[Segment | Arc] = []
    loose: list[Point] = []
    exact = True
    for shape in shapes:
        moved = tuple(move.apply(p) for p in shape.points)
        loose += moved
        if shape.kind == "rect":
            a, b = shape.points[0], shape.points[1]
            corners = (a, Point(b.x, a.y), b, Point(a.x, b.y))
            rings.append(tuple(move.apply(p) for p in corners))
        elif shape.kind == "circle":
            dx, dy = shape.points[1].x - shape.points[0].x, shape.points[1].y - shape.points[0].y
            disc = Circle(moved[0], dx * dx + dy * dy).polygonize(tol, outer=True)
            rings.append(disc)
            loose += disc
            exact = False
        elif shape.kind == "polygon" and not shape.arcs:
            rings.append(moved)
        elif shape.kind == "polygon":
            starts = {index: (start, mid, end) for index, start, mid, end in shape.arcs}
            ring: list[Point] = []
            index = 0
            while index < len(shape.points):
                if index in starts:
                    ring += Arc(*(move.apply(p) for p in starts[index])).polygonize(tol)
                    index += 2
                else:
                    ring.append(moved[index])
                    index += 1
            rings.append(_dedupe(ring))
            loose += ring
            exact = False
        elif shape.kind == "line" and moved[0] != moved[1]:
            pieces.append(Segment(moved[0], moved[1]))
        elif shape.kind == "arc":
            arc = Arc(*moved)
            pieces.append(arc)
            loose += arc.polygonize(tol)
            exact = False
    closed = True
    if pieces:
        try:
            for path in assemble_rings(pieces):
                rings.append(path.polygonize(tol))
        except GeometryError:
            closed = False
    if not closed:
        hull = convex_hull(loose)
        return ((hull,) if len(hull) >= 3 else ()), False, False
    try:
        normal = tuple(poly.outer for poly in normalize_polygons(Polygon(ring) for ring in rings))
    except (GeometryError, ValueError):
        hull = convex_hull(loose)
        return ((hull,) if len(hull) >= 3 else ()), False, False
    return normal, exact, True


def _pad_hull(pads: Sequence[BoardPad]) -> tuple[Point, ...]:
    corners: list[Point] = []
    for pad in pads:
        for entry in pad.copper:
            grow = -(-entry.width // 2)
            xs, ys = [p.x for p in entry.core], [p.y for p in entry.core]
            x0, y0, x1, y1 = min(xs) - grow, min(ys) - grow, max(xs) + grow, max(ys) + grow
            corners += [Point(x0, y0), Point(x1, y0), Point(x1, y1), Point(x0, y1)]
    hull = convex_hull(corners)
    return hull if len(hull) >= 3 else ()


def placed_extent(
    footprint: FootprintInstance,
    *,
    definition: FootprintDef | None = None,
    tol: int = DEFAULT_TOL,
    issues: list[Issue] | None = None,
    _pads: Sequence[BoardPad] | None = None,
) -> PlacedExtent:
    """The courtyard of a placed footprint in the board frame, front and back.

    The pieces come from the footprint's own children (a read or built board); an instance without KiCad
    slots uses ``definition``. Without a courtyard the extent is the hull of its pads' copper.
    """
    found: list[Issue] = []
    name = footprint.lib_ref or footprint.id
    if _has_slots(footprint):
        shapes, source = _courtyard_shapes(footprint), "courtyard"
        move = Transform.placement(footprint.position, footprint.rotation)
        faces = {layer: [s for s in shapes if s.layer == layer] for layer in COURTYARD_LAYERS}
    elif definition is not None:
        source = "definition"
        bottom = footprint.side == "bottom"
        move = Transform.placement(footprint.position, footprint.rotation, mirror=bottom)
        front = [_graphic_shape(g) for g in definition.graphics_on("F.CrtYd")]
        back = [_graphic_shape(g) for g in definition.graphics_on("B.CrtYd")]
        faces = {"F.CrtYd": back if bottom else front, "B.CrtYd": front if bottom else back}
    else:
        source, move = "courtyard", Transform.identity()
        faces = {layer: list[_Shape]() for layer in COURTYARD_LAYERS}
    rings: dict[str, tuple[tuple[Point, ...], ...]] = {}
    exact = True
    for layer in COURTYARD_LAYERS:
        if not faces[layer]:
            rings[layer] = ()
            continue
        rings[layer], face_exact, closed = _face(faces[layer], move, tol)
        exact = exact and face_exact
        if not closed:
            found.append(
                _issue(
                    "kicad.frame.courtyard-malformed",
                    f"the courtyard of {name} on {layer} does not close; its convex hull is used",
                    f"{name}:{layer}",
                )
            )
    if any(faces.values()):
        extent = PlacedExtent(footprint.id, footprint.side, rings["F.CrtYd"], rings["B.CrtYd"], source, exact)  # type: ignore[arg-type]
    else:
        pads = _pads if _pads is not None else _instance_pads(footprint)
        hull = _pad_hull(pads)
        own = (hull,) if hull else ()
        top = footprint.side == "top"
        extent = PlacedExtent(
            footprint.id,
            footprint.side,
            front=own if top else (),
            back=() if top else own,
            source="pads" if hull else "none",
            exact=not hull,
        )
        what = "the hull of its pads is used" if hull else "it has no pad copper either"
        found.append(_issue("kicad.frame.no-courtyard", f"{name} has no courtyard; {what}", name))
    if issues is not None:
        issues.extend(found)
    return extent


def _instance_pads(footprint: FootprintInstance) -> tuple[BoardPad, ...]:
    """The pad records of a lone instance: its pads' own layers stand for the copper layers."""
    names = [name for pad in footprint.pads for name in pad.layers if name.endswith(".Cu")]
    layers = ("F.Cu", *sorted({n for n in names if n not in ("F.Cu", "B.Cu", "*.Cu")}), "B.Cu")
    scratch: list[Issue] = []
    return tuple(_pad_record({}, footprint, "", "", pad, layers, scratch) for pad in footprint.pads)


def placed_extents(
    design: Design,
    *,
    definitions: Mapping[str, FootprintDef] | None = None,
    tol: int = DEFAULT_TOL,
    issues: list[Issue] | None = None,
) -> tuple[PlacedExtent, ...]:
    """One extent per footprint of the board, in board order; ``definitions`` maps a ``lib_ref`` to its
    definition, for instances without KiCad slots."""
    footprints = design.board.footprints if design.board is not None else ()
    known = definitions or {}
    extents: list[PlacedExtent] = []
    for footprint in footprints:
        scratch: list[Issue] = []
        pads = _footprint_pads(design, footprint, scratch)
        extents.append(
            placed_extent(
                footprint, definition=known.get(footprint.lib_ref), tol=tol, issues=issues, _pads=pads
            )
        )
    return tuple(extents)


# --- polygons -------------------------------------------------------------------------------------


def copper_polygon(entry: PadCopper, *, tol: int = DEFAULT_TOL) -> Polygon:
    """A polygon that contains the copper of ``entry``: exact for a filled ring of width 0, an outer polygon
    for a disc, a segment or a convex ring with a width. Other entries raise ``ValueError``."""
    core = entry.core
    if entry.filled and entry.width == 0:
        return Polygon(core)
    if entry.width == 0:
        raise ValueError("a point or polyline of width 0 has no area to give a polygon")
    if entry.filled and not Polygon(core).is_convex():
        raise ValueError("a non-convex ring with a width has no convex outer polygon")
    if not entry.filled and len(core) > 2:
        raise ValueError("a polyline of more than two points has no convex outer polygon")
    radius = -(-entry.width // 2)
    around: list[Point] = []
    for point in core:
        around += Circle.from_radius(point, radius).polygonize(tol, outer=True)
    return Polygon(convex_hull(around))


__all__ = [
    "COURTYARD_LAYERS",
    "CURVE_GROWTH",
    "EVIDENCE",
    "FRAME_ISSUE_CODES",
    "board_pads",
    "copper_polygon",
    "find_pads",
    "placed_extent",
    "placed_extents",
]
