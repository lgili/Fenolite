# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The box of a STEP model (change c0449; ``docs/formats/step/part21.md``, "Box of a model").

``model_box(data)`` reads an ISO 10303-21 exchange file and gives the box, in integer nanometres in the
model's own frame, that holds every edge of its shapes: the vertex points, the points of a circular or
elliptic edge where a coordinate is extreme within the edge's span, the control points of a B-spline edge (a
B-spline lies in the hull of its control points), and the points of polylines, poly loops and coordinate
lists. A closed solid lies inside the box of
its edges unless a face bulges between them (a sphere, a torus).

Each point is read in the frame of the shape representation that holds it, scaled by the length unit of that
representation's context, and moved into the root frame through the item-defined transformation of every
representation relationship that places it, the component of each taken from the product structure
(``H-G-STEP-BOX``). Standard library only: the text is split into instances with regular expressions; no
STEP library is used.
"""

from __future__ import annotations

import math
import re
from collections.abc import Iterator, Mapping, Sequence
from dataclasses import dataclass
from typing import cast

from fenolite.core.evidence import Evidence, Level

EVIDENCE = Evidence(Level.INFERRED, hypotheses=("H-G-STEP-BOX",))
NM_PER_MM = 1_000_000
Box = tuple[int, int, int, int, int, int]
"""``(x_min, y_min, z_min, x_max, y_max, z_max)`` in nm."""
Vec = tuple[float, float, float]
Matrix = tuple[Vec, Vec, Vec]
Frame = tuple[Matrix, Vec]
"""A rotation (rows) and a translation in mm: ``p → R·p + t``."""
_IDENTITY: Frame = (((1.0, 0.0, 0.0), (0.0, 1.0, 0.0), (0.0, 0.0, 1.0)), (0.0, 0.0, 0.0))
PREFIX_MM: Mapping[str, float] = {
    "EXA": 1e21, "PETA": 1e18, "TERA": 1e15, "GIGA": 1e12, "MEGA": 1e9, "KILO": 1e6, "HECTO": 1e5,
    "DECA": 1e4, "DECI": 1e2, "CENTI": 10.0, "MILLI": 1.0, "MICRO": 1e-3, "NANO": 1e-6, "PICO": 1e-9,
    "FEMTO": 1e-12, "ATTO": 1e-15,
}  # fmt: skip
"""The SI prefixes (``si_prefix``, S-2082) as the millimetres of a prefixed metre; no prefix is 1000 mm."""
MAX_INSTANCES = 1_000
"""How many placements of one representation in the root frame are followed before the reader gives up."""

_STRING = re.compile(r"'(?:[^']|'')*'")
_COMMENT = re.compile(r"/\*.*?\*/", re.S)
_INSTANCE = re.compile(r"#(\d+)\s*=\s*(.*)", re.S)
_TOKEN = re.compile(
    r"\s*(?:(#\d+)|(\.[A-Za-z_][A-Za-z0-9_]*\.)|([A-Za-z_][A-Za-z0-9_]*)\s*(?=\()|"
    r"([-+]?(?:\d+\.?\d*|\.\d+)(?:[Ee][-+]?\d+)?)|(\$|\*|'')|([(),]))"
)
_REF = re.compile(r"#(\d+)")
_HEAD = re.compile(r"\s*([A-Za-z_][A-Za-z0-9_]*)\s*\(")
_NEEDED = frozenset(
    {
        "CARTESIAN_POINT", "DIRECTION", "AXIS2_PLACEMENT_3D", "VERTEX_POINT", "CIRCLE", "ELLIPSE",
        "B_SPLINE_CURVE", "B_SPLINE_CURVE_WITH_KNOTS", "QUASI_UNIFORM_CURVE", "UNIFORM_CURVE",
        "BEZIER_CURVE", "RATIONAL_B_SPLINE_CURVE", "POLYLINE", "POLY_LOOP", "COORDINATES_LIST",
        "ITEM_DEFINED_TRANSFORMATION", "REPRESENTATION_RELATIONSHIP",
        "REPRESENTATION_RELATIONSHIP_WITH_TRANSFORMATION", "SHAPE_REPRESENTATION_RELATIONSHIP",
        "GLOBAL_UNIT_ASSIGNED_CONTEXT", "SI_UNIT", "CONVERSION_BASED_UNIT", "LENGTH_UNIT",
        "LENGTH_MEASURE_WITH_UNIT", "MEASURE_WITH_UNIT", "SHAPE_DEFINITION_REPRESENTATION",
        "PRODUCT_DEFINITION_SHAPE", "NEXT_ASSEMBLY_USAGE_OCCURRENCE",
        "CONTEXT_DEPENDENT_SHAPE_REPRESENTATION", "EDGE_CURVE", "SURFACE_CURVE", "SEAM_CURVE",
        "TRIMMED_CURVE", "LINE", "VECTOR", "PLANE_ANGLE_MEASURE_WITH_UNIT", "PLANE_ANGLE_UNIT",
    }
)  # fmt: skip
"""The entities whose attributes are parsed; every other instance gives only its references."""
_CURVES = frozenset(
    {"B_SPLINE_CURVE", "B_SPLINE_CURVE_WITH_KNOTS", "QUASI_UNIFORM_CURVE", "UNIFORM_CURVE", "BEZIER_CURVE"}
)

Value = object
Part = tuple[str, list[Value]]


@dataclass(frozen=True, slots=True)
class _Ref:
    id: int


def _items(value: Value) -> list[Value]:
    """``value`` as a list of values; empty for any other value."""
    return cast("list[Value]", value) if isinstance(value, list) else []


def _ids(value: Value) -> list[int]:
    """The references of the list ``value``, in order."""
    return [item.id for item in _items(value) if isinstance(item, _Ref)]


def _xyz(value: Value) -> Vec | None:
    """A list of three reals as a vector; ``None`` for any other value (a 2D point of a parameter space)."""
    reals = [item for item in _items(value) if isinstance(item, float)]
    return (reals[0], reals[1], reals[2]) if len(reals) == 3 and len(_items(value)) == 3 else None


def _parse(tokens: Iterator[re.Match[str]]) -> list[Value]:
    """The values of a parenthesised list whose ``(`` was read; nested lists and typed values recursed."""
    out: list[Value] = []
    for match in tokens:
        ref, enum, keyword, number, other, punct = match.groups()
        if ref is not None:
            out.append(_Ref(int(ref[1:])))
        elif enum is not None:
            out.append(enum.upper())
        elif keyword is not None:
            next(tokens)  # its "("
            out.append((keyword.upper(), _parse(tokens)))
        elif number is not None:
            out.append(float(number))
        elif other is not None:
            out.append(None)
        elif punct == "(":
            out.append(_parse(tokens))
        elif punct == ")":
            return out
    return out


def _parts(body: str) -> list[Part]:
    """The constituents ``(name, attributes)`` of an instance's right-hand side: one for a simple instance,
    several for a complex one."""
    tokens = _TOKEN.finditer(body)
    if body.lstrip().startswith("("):
        next(tokens)  # the "(" that opens the list of constituents
        parsed = _parse(tokens)
    else:
        parsed = [_first(tokens)]
    return [cast("Part", value) for value in parsed if isinstance(value, tuple)]


def _first(tokens: Iterator[re.Match[str]]) -> Value:
    for match in tokens:
        keyword = match.group(3)
        if keyword is not None:
            next(tokens)
            return (keyword.upper(), _parse(tokens))
        return None
    return None


def _data(text: str) -> str:
    start = text.find("DATA;")
    if start < 0:
        return ""
    end = text.find("ENDSEC;", start)
    return text[start + 5 : end if end >= 0 else len(text)]


@dataclass
class _Model:
    parts: dict[int, list[Part]]
    refs: dict[int, list[int]]
    shapes: dict[int, tuple[list[int], int]]
    """Each shape representation: its items and its context."""


def _shape(parts: Sequence[Part]) -> tuple[list[int], int] | None:
    """The items and the context of a shape representation (``representation``: name, items, context)."""
    for name, attributes in parts:
        if name.endswith("SHAPE_REPRESENTATION") and len(attributes) >= 3:
            context = attributes[2]
            if _items(attributes[1]) and isinstance(context, _Ref):
                return _ids(attributes[1]), context.id
    return None


def _read(text: str) -> _Model:
    data = _COMMENT.sub("", _STRING.sub("''", _data(text)))
    parts: dict[int, list[Part]] = {}
    refs: dict[int, list[int]] = {}
    shapes: dict[int, tuple[list[int], int]] = {}
    for statement in data.split(";"):
        found = _INSTANCE.match(statement.strip())
        if found is None:
            continue
        ident, body = int(found.group(1)), found.group(2)
        refs[ident] = [int(r) for r in _REF.findall(body)]
        if body.lstrip().startswith("("):  # a complex instance: few, parsed whole
            parsed = _parts(body)
            names = {name for name, _ in parsed}
        else:
            head = _HEAD.match(body)
            if head is None:
                continue
            kind = head.group(1).upper()
            if kind not in _NEEDED and not kind.endswith("SHAPE_REPRESENTATION"):
                continue
            parsed = _parts(body)
            names = {kind}
        shape = _shape(parsed)
        if shape is not None:
            shapes[ident] = shape
        elif names & _NEEDED:
            parts[ident] = parsed
    return _Model(parts, refs, shapes)


def _part(model: _Model, ident: int, name: str) -> list[Value] | None:
    for part, attributes in model.parts.get(ident, ()):
        if part == name:
            return attributes
    return None


def _point(model: _Model, ident: int) -> Vec | None:
    found = _part(model, ident, "CARTESIAN_POINT")
    return _xyz(found[1]) if found is not None and len(found) >= 2 else None


def _direction(model: _Model, value: Value, default: Vec) -> Vec:
    if not isinstance(value, _Ref):
        return default
    found = _part(model, value.id, "DIRECTION")
    vector = _xyz(found[1]) if found is not None and len(found) >= 2 else None
    if vector is None:
        return default
    x, y, z = vector
    size = math.sqrt(x * x + y * y + z * z)
    return default if size == 0 else (x / size, y / size, z / size)


def _cross(a: Vec, b: Vec) -> Vec:
    return (a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0])


def _axes(model: _Model, ident: int) -> tuple[Vec, Vec, Vec, Vec] | None:
    """``(origin, x, y, z)`` of an ``AXIS2_PLACEMENT_3D``: z its axis (default +Z), x its reference
    direction made normal to z (default +X), y = z × x."""
    found = _part(model, ident, "AXIS2_PLACEMENT_3D")
    if found is None or len(found) < 2 or not isinstance(found[1], _Ref):
        return None
    origin = _point(model, found[1].id)
    if origin is None:
        return None
    z = _direction(model, found[2] if len(found) > 2 else None, (0.0, 0.0, 1.0))
    ref = _direction(model, found[3] if len(found) > 3 else None, (1.0, 0.0, 0.0))
    dot = sum(r * c for r, c in zip(ref, z, strict=True))
    x = tuple(r - dot * c for r, c in zip(ref, z, strict=True))
    size = math.sqrt(sum(v * v for v in x))
    if size < 1e-12:
        x = (1.0, 0.0, 0.0) if abs(z[0]) < 0.9 else (0.0, 1.0, 0.0)
        dot = sum(r * c for r, c in zip(x, z, strict=True))
        x = tuple(r - dot * c for r, c in zip(x, z, strict=True))
        size = math.sqrt(sum(v * v for v in x))
    xn: Vec = (x[0] / size, x[1] / size, x[2] / size)
    return origin, xn, _cross(z, xn), z


def _length_unit(model: _Model, ident: int, depth: int = 0) -> float | None:
    """The millimetres of the length unit ``ident``: an ``SI_UNIT`` of the metre with its prefix, or a
    ``CONVERSION_BASED_UNIT`` whose ``LENGTH_MEASURE_WITH_UNIT`` gives its value in another unit."""
    if depth > 8:
        return None
    si = _part(model, ident, "SI_UNIT")
    if si is not None and len(si) >= 2 and si[-1] == ".METRE.":
        prefix = si[-2]
        return 1000.0 if prefix is None else PREFIX_MM.get(str(prefix).strip("."))
    based = _part(model, ident, "CONVERSION_BASED_UNIT")
    if based is not None and len(based) >= 2 and isinstance(based[1], _Ref):
        measure = _part(model, based[1].id, "LENGTH_MEASURE_WITH_UNIT") or _part(
            model, based[1].id, "MEASURE_WITH_UNIT"
        )
        if measure is None or len(measure) < 2 or not isinstance(measure[1], _Ref):
            return None
        value = measure[0]
        if isinstance(value, tuple):  # a typed value: LENGTH_MEASURE(25.4)
            inner = _items(cast("Part", value)[1])
            value = inner[0] if inner else None
        unit = _length_unit(model, measure[1].id, depth + 1)
        return value * unit if isinstance(value, float) and unit is not None else None
    return None


def _context_mm(model: _Model, context: int) -> float:
    """The millimetres of the length unit of a representation context; 1 when it names none."""
    units = _part(model, context, "GLOBAL_UNIT_ASSIGNED_CONTEXT")
    for unit in _ids(units[0]) if units else []:
        if _part(model, unit, "LENGTH_UNIT") is not None or _part(model, unit, "SI_UNIT") is not None:
            found = _length_unit(model, unit)
            if found is not None:
                return found
    return 1.0


def _angle_unit(model: _Model, ident: int, depth: int = 0) -> float | None:
    """The radians of the plane angle unit ``ident``: an ``SI_UNIT`` of the radian, or a
    ``CONVERSION_BASED_UNIT`` whose ``PLANE_ANGLE_MEASURE_WITH_UNIT`` gives its value in another unit."""
    if depth > 8:
        return None
    si = _part(model, ident, "SI_UNIT")
    if si is not None and len(si) >= 2 and si[-1] == ".RADIAN.":
        return 1.0
    based = _part(model, ident, "CONVERSION_BASED_UNIT")
    if based is not None and len(based) >= 2 and isinstance(based[1], _Ref):
        measure = _part(model, based[1].id, "PLANE_ANGLE_MEASURE_WITH_UNIT") or _part(
            model, based[1].id, "MEASURE_WITH_UNIT"
        )
        if measure is None or len(measure) < 2 or not isinstance(measure[1], _Ref):
            return None
        value = measure[0]
        if isinstance(value, tuple):  # a typed value: PLANE_ANGLE_MEASURE(0.0174…)
            inner = _items(cast("Part", value)[1])
            value = inner[0] if inner else None
        unit = _angle_unit(model, measure[1].id, depth + 1)
        return value * unit if isinstance(value, float) and unit is not None else None
    return None


def _context_radians(model: _Model, context: int) -> float:
    """The radians of the plane angle unit of a representation context; 1 (the radian) when it names
    none (change c0481)."""
    units = _part(model, context, "GLOBAL_UNIT_ASSIGNED_CONTEXT")
    for unit in _ids(units[0]) if units else []:
        if _part(model, unit, "PLANE_ANGLE_UNIT") is not None:
            found = _angle_unit(model, unit)
            if found is not None:
                return found
    return 1.0


def _times(a: Matrix, b: Matrix) -> Matrix:
    rows = [tuple(sum(a[i][k] * b[k][j] for k in range(3)) for j in range(3)) for i in range(3)]
    return (rows[0], rows[1], rows[2])  # type: ignore[return-value]


def _apply(frame: Frame, p: Vec) -> Vec:
    (r0, r1, r2), t = frame
    return (
        r0[0] * p[0] + r0[1] * p[1] + r0[2] * p[2] + t[0],
        r1[0] * p[0] + r1[1] * p[1] + r1[2] * p[2] + t[1],
        r2[0] * p[0] + r2[1] * p[1] + r2[2] * p[2] + t[2],
    )


def _compose(outer: Frame, inner: Frame) -> Frame:
    return (_times(outer[0], inner[0]), _apply(outer, inner[1]))


def _placement_frame(axes: tuple[Vec, Vec, Vec, Vec], scale: float) -> Frame:
    """The frame that takes a point given in the placement's axes into its representation (mm)."""
    origin, x, y, z = axes
    rotation: Matrix = ((x[0], y[0], z[0]), (x[1], y[1], z[1]), (x[2], y[2], z[2]))
    return (rotation, (origin[0] * scale, origin[1] * scale, origin[2] * scale))


def _inverse(frame: Frame) -> Frame:
    (r0, r1, r2), t = frame
    rt: Matrix = ((r0[0], r1[0], r2[0]), (r0[1], r1[1], r2[1]), (r0[2], r1[2], r2[2]))
    moved = _apply((rt, (0.0, 0.0, 0.0)), t)
    return (rt, (-moved[0], -moved[1], -moved[2]))


@dataclass(frozen=True, slots=True)
class _Link:
    """``rep_1`` and ``rep_2`` of a relationship with a transformation, and ``frame``, which takes a point of
    ``rep_1`` into ``rep_2``: ``transform_item_1`` (of ``rep_1``'s context) brought onto ``transform_item_2``
    (of ``rep_2``'s), S-2082."""

    ident: int
    child: int
    parent: int
    frame: Frame

    def reversed(self) -> _Link:
        return _Link(self.ident, self.parent, self.child, _inverse(self.frame))


def _links(model: _Model, scales: Mapping[int, float]) -> tuple[list[_Link], list[tuple[int, int]]]:
    """The relationships with a transformation, each as ``rep_1`` placed in ``rep_2`` (``model_box`` turns
    a link round when ``rep_1`` is the assembly), and the plain relationships, whose two representations
    share one frame."""
    placed: list[_Link] = []
    same: list[tuple[int, int]] = []
    for ident, parts in model.parts.items():
        names = {name for name, _ in parts}
        if "REPRESENTATION_RELATIONSHIP" not in names and "SHAPE_REPRESENTATION_RELATIONSHIP" not in names:
            continue
        base = _part(model, ident, "REPRESENTATION_RELATIONSHIP") or _part(
            model, ident, "SHAPE_REPRESENTATION_RELATIONSHIP"
        )
        if base is None or len(base) < 4 or not isinstance(base[2], _Ref) or not isinstance(base[3], _Ref):
            continue
        rep_1, rep_2 = base[2].id, base[3].id
        moved = _part(model, ident, "REPRESENTATION_RELATIONSHIP_WITH_TRANSFORMATION")
        if not moved or not isinstance(moved[0], _Ref):
            same.append((rep_1, rep_2))
            continue
        item = _part(model, moved[0].id, "ITEM_DEFINED_TRANSFORMATION")
        if item is None or len(item) < 4 or not isinstance(item[2], _Ref) or not isinstance(item[3], _Ref):
            continue
        first, second = _axes(model, item[2].id), _axes(model, item[3].id)
        if first is None or second is None:
            continue
        frame_1 = _placement_frame(first, scales.get(rep_1, 1.0))
        frame_2 = _placement_frame(second, scales.get(rep_2, 1.0))
        placed.append(_Link(ident, rep_1, rep_2, _compose(frame_2, _inverse(frame_1))))
    return placed, same


def _ref(values: Sequence[Value], index: int) -> int | None:
    value = values[index] if len(values) > index else None
    return value.id if isinstance(value, _Ref) else None


def _products(model: _Model) -> tuple[dict[int, set[int]], dict[int, int]]:
    """The product definitions of each representation (``shape_definition_representation``: definition,
    used_representation; ``product_definition_shape``: name, description, definition), and for each
    relationship that a ``context_dependent_shape_representation`` names (representation_relation,
    represented_product_relation) the product definition of the component: the
    ``related_product_definition`` of its ``next_assembly_usage_occurrence`` (id, name, description,
    relating, related, designator), S-2082."""
    shape_of: dict[int, int] = {}
    for ident in model.parts:
        found = _part(model, ident, "PRODUCT_DEFINITION_SHAPE")
        definition = _ref(found, 2) if found is not None else None
        if definition is not None:
            shape_of[ident] = definition
    products: dict[int, set[int]] = {}
    component: dict[int, int] = {}
    for ident in model.parts:
        used = _part(model, ident, "SHAPE_DEFINITION_REPRESENTATION")
        if used is not None:
            shape, rep = _ref(used, 0), _ref(used, 1)
            if shape in shape_of and rep is not None:
                products.setdefault(rep, set()).add(shape_of[shape])
        dependent = _part(model, ident, "CONTEXT_DEPENDENT_SHAPE_REPRESENTATION")
        if dependent is not None:
            relation, shape = _ref(dependent, 0), _ref(dependent, 1)
            usage = (
                _part(model, shape_of[shape], "NEXT_ASSEMBLY_USAGE_OCCURRENCE") if shape in shape_of else None
            )
            related = _ref(usage, 4) if usage is not None else None
            if relation is not None and related is not None:
                component[relation] = related
    return products, component


def _reachable(model: _Model, roots: Sequence[int], stop: set[int]) -> set[int]:
    seen: set[int] = set()
    todo = list(roots)
    while todo:
        ident = todo.pop()
        if ident in seen or ident in stop:
            continue
        seen.add(ident)
        todo.extend(model.refs.get(ident, ()))
    return seen


Axes = tuple[Vec, Vec, Vec, Vec]
"""An ``AXIS2_PLACEMENT_3D``: origin and the unit x, y and z."""


def _conic(model: _Model, ident: int, depth: int = 0) -> tuple[Axes, float, float] | None:
    """The placement and the two semi-axes of the circle or ellipse that the curve ``ident`` is, or that a
    surface curve (name, curve_3d, …) or a trimmed curve (name, basis_curve, …) is drawn on."""
    if depth > 4:
        return None
    circle = _part(model, ident, "CIRCLE")
    ellipse = _part(model, ident, "ELLIPSE")
    found = circle or ellipse
    if found is not None:
        placement = _ref(found, 1)
        axes = _axes(model, placement) if placement is not None else None
        sizes = [v for v in found[2:4] if isinstance(v, float)]
        if axes is None or not sizes:
            return None
        return axes, sizes[0], sizes[1] if ellipse is not None and len(sizes) > 1 else sizes[0]
    for name in ("SURFACE_CURVE", "SEAM_CURVE", "TRIMMED_CURVE"):
        wrapped = _part(model, ident, name)
        basis = _ref(wrapped, 1) if wrapped is not None else None
        if basis is not None:
            return _conic(model, basis, depth + 1)
    return None


def _arc(model: _Model, ident: int) -> list[Vec]:
    """The points whose box holds a circular or elliptic edge (``edge_curve``: name, edge_start, edge_end,
    edge_geometry, same_sense): its two ends and each point of the curve, within the edge's span, where a
    coordinate is extreme. The span runs counter-clockwise about the placement's axis from the start to the
    end when ``same_sense`` holds, from the end to the start otherwise; equal ends make a whole turn."""
    edge = _part(model, ident, "EDGE_CURVE")
    if edge is None or len(edge) < 5:
        return []
    curve = _ref(edge, 3)
    conic = _conic(model, curve) if curve is not None else None
    if conic is None:
        return []
    (origin, x, y, _z), a, b = conic

    def vertex(index: int) -> Vec | None:
        found = _part(model, _ref(edge, index) or 0, "VERTEX_POINT")
        at = _ref(found, 1) if found is not None else None
        return _point(model, at) if at is not None else None

    def angle(p: Vec) -> float:
        d = (p[0] - origin[0], p[1] - origin[1], p[2] - origin[2])
        return math.atan2(sum(d[i] * y[i] for i in range(3)) / b, sum(d[i] * x[i] for i in range(3)) / a)

    start, end = vertex(1), vertex(2)
    if start is None or end is None:
        return []
    if edge[4] == ".F.":
        start, end = end, start
    return [start, end, *_extremes(conic, angle(start), angle(end))]


def _extremes(conic: tuple[Axes, float, float], t0: float, t1: float) -> list[Vec]:
    """The points of a circle or ellipse, counter-clockwise from the angle ``t0`` to ``t1`` (a whole turn
    when they are equal), where a coordinate is extreme."""
    (_origin, x, y, _z), a, b = conic
    sweep = (t1 - t0) % math.tau
    if sweep < 1e-9:
        sweep = math.tau
    out: list[Vec] = []
    for i in range(3):
        extreme = math.atan2(b * y[i], a * x[i])
        out += [_on_conic(conic, t) for t in (extreme, extreme + math.pi) if (t - t0) % math.tau <= sweep]
    return out


def _trimmed(model: _Model, ident: int, radians: float) -> list[Vec]:
    """The points whose box holds a trimmed curve over a line, a circle or an ellipse (``trimmed_curve``:
    name, basis_curve, trim_1, trim_2, sense_agreement, …; change c0481): its two ends and, on a conic,
    each extreme point within its span. A trim is a point, or a parameter: on a line ``point + t ·
    vector``, on a conic an angle in the context's unit (``radians`` per unit). Without
    ``sense_agreement`` the span runs from the second trim to the first."""
    found = _part(model, ident, "TRIMMED_CURVE")
    basis = _ref(found, 1) if found is not None and len(found) >= 5 else None
    if found is None or basis is None:
        return []

    def trim(value: Value) -> tuple[Vec | None, float | None]:
        point = next((_point(model, item.id) for item in _items(value) if isinstance(item, _Ref)), None)
        for item in _items(value):
            if isinstance(item, float):
                return point, item
            if isinstance(item, tuple) and cast("Part", item)[0] == "PARAMETER_VALUE":
                inner = [v for v in _items(cast("Part", item)[1]) if isinstance(v, float)]
                if inner:
                    return point, inner[0]
        return point, None

    (p1, u1), (p2, u2) = trim(found[2]), trim(found[3])
    line = _part(model, basis, "LINE")
    if line is not None:
        origin = _point(model, _ref(line, 1) or 0)
        vector = _part(model, _ref(line, 2) or 0, "VECTOR")
        size = vector[2] if vector is not None and len(vector) >= 3 else None
        if origin is None or vector is None or not isinstance(size, float):
            return [p for p in (p1, p2) if p is not None]
        d = _direction(model, vector[1], (0.0, 0.0, 0.0))

        def on_line(u: float | None) -> Vec | None:
            return None if u is None else tuple(o + u * size * c for o, c in zip(origin, d, strict=True))  # type: ignore[return-value]

        return [p for p in (p1 or on_line(u1), p2 or on_line(u2)) if p is not None]
    conic = _conic(model, basis)
    if conic is None:
        return []
    (centre, x, y, _z), a, b = conic
    if a <= 0 or b <= 0:
        return []

    def angle(p: Vec | None, u: float | None) -> float | None:
        if p is None:
            return None if u is None else u * radians
        d = (p[0] - centre[0], p[1] - centre[1], p[2] - centre[2])
        return math.atan2(sum(d[i] * y[i] for i in range(3)) / b, sum(d[i] * x[i] for i in range(3)) / a)

    t1, t2 = angle(p1, u1), angle(p2, u2)
    if t1 is None or t2 is None:
        return []
    if found[4] == ".F.":
        t1, t2 = t2, t1
    return [_on_conic(conic, t1), _on_conic(conic, t2), *_extremes(conic, t1, t2)]


def _on_conic(conic: tuple[Axes, float, float], t: float) -> Vec:
    (origin, x, y, _z), a, b = conic
    c, s = math.cos(t), math.sin(t)
    return (
        origin[0] + a * c * x[0] + b * s * y[0],
        origin[1] + a * c * x[1] + b * s * y[1],
        origin[2] + a * c * x[2] + b * s * y[2],
    )


def _geometry(model: _Model, idents: set[int], scale: float, radians: float = 1.0) -> list[Vec]:
    """The points, in mm in the representation's frame, whose box holds every edge reached: vertices, the
    extremes of each circular or elliptic edge within its span, curve control points and polygon points.
    A representation that reaches no edge (a surface or wireframe model, change c0481) gives the points of
    its trimmed curves instead (``_trimmed``)."""
    points: list[Vec] = []
    edges = any(_part(model, ident, "EDGE_CURVE") is not None for ident in idents)

    def add(p: Vec | None) -> None:
        if p is not None:
            points.append((p[0] * scale, p[1] * scale, p[2] * scale))

    for ident in idents:
        parts = model.parts.get(ident)
        if not parts:
            continue
        names = {name for name, _ in parts}
        if "VERTEX_POINT" in names:
            found = _part(model, ident, "VERTEX_POINT")
            if found and len(found) >= 2 and isinstance(found[1], _Ref):
                add(_point(model, found[1].id))
        elif "EDGE_CURVE" in names:
            for p in _arc(model, ident):
                add(p)
        elif names & _CURVES:
            # the control points: the first list among the attributes (after the name of a simple
            # instance and its degree; first of a complex instance's B_SPLINE_CURVE, which holds no name)
            empty: list[Value] = []
            curve = next((attrs for name, attrs in parts if name in _CURVES and len(attrs) >= 2), empty)
            none: list[int] = []
            for ref in next((_ids(value) for value in curve[:3] if _items(value)), none):
                add(_point(model, ref))
        elif names & {"POLYLINE", "POLY_LOOP"}:
            found = _part(model, ident, "POLYLINE") or _part(model, ident, "POLY_LOOP")
            for ref in _ids(found[1]) if found and len(found) >= 2 else []:
                add(_point(model, ref))
        elif "TRIMMED_CURVE" in names and not edges:
            for p in _trimmed(model, ident, radians):
                add(p)
        elif "COORDINATES_LIST" in names:
            found = _part(model, ident, "COORDINATES_LIST")
            for row in _items(found[2]) if found and len(found) >= 3 else []:
                add(_xyz(row))
    return points


def _instances(node: int, parents: Mapping[int, list[_Link]], depth: int = 0) -> list[Frame]:
    """Every frame that takes the group ``node`` into a root, through the placements above it."""
    above = parents.get(node)
    if not above or depth > 32:
        return [_IDENTITY]
    out: list[Frame] = []
    for link in above:
        for outer in _instances(link.parent, parents, depth + 1):
            out.append(_compose(outer, link.frame))
            if len(out) > MAX_INSTANCES:
                return out
    return out


def model_box(data: bytes) -> Box | None:
    """The box of the STEP model ``data`` in nm in its root frame, or ``None`` for bytes that are no
    exchange file or hold no edge geometry."""
    if not data.lstrip().startswith(b"ISO-10303-21"):
        return None
    model = _read(data.decode("latin-1"))
    scales = {rep: _context_mm(model, context) for rep, (_items, context) in model.shapes.items()}
    radians = {rep: _context_radians(model, context) for rep, (_items, context) in model.shapes.items()}
    placed, same = _links(model, scales)
    group = {rep: rep for rep in model.shapes}

    def root(rep: int) -> int:
        while group.get(rep, rep) != rep:
            rep = group[rep]
        return rep

    for a, b in same:
        ra, rb = root(a), root(b)
        if ra != rb:
            group[max(ra, rb)] = min(ra, rb)
    products, component = _products(model)
    held: dict[int, set[int]] = {}
    for rep, found in products.items():
        held.setdefault(root(rep), set()).update(found)
    parents: dict[int, list[_Link]] = {}
    for link in placed:
        part = component.get(link.ident)
        if part in held.get(root(link.parent), ()) and part not in held.get(root(link.child), ()):
            link = link.reversed()  # rep_1 is the assembly: the exporter wrote the pair the other way round
        child, parent = root(link.child), root(link.parent)
        parents.setdefault(child, []).append(_Link(link.ident, child, parent, link.frame))
    stop = set(model.shapes)
    lo = [math.inf] * 3
    hi = [-math.inf] * 3
    for rep, (items, _context) in model.shapes.items():
        points = _geometry(model, _reachable(model, items, stop), scales.get(rep, 1.0), radians.get(rep, 1.0))
        if not points:
            continue
        for frame in _instances(root(rep), parents):
            for p in points:
                q = _apply(frame, p)
                for i in range(3):
                    lo[i] = min(lo[i], q[i])
                    hi[i] = max(hi[i], q[i])
    if not all(math.isfinite(v) for v in (*lo, *hi)):
        return None
    nm = [round(v * NM_PER_MM) for v in (*lo, *hi)]
    return (nm[0], nm[1], nm[2], nm[3], nm[4], nm[5])


__all__ = ["EVIDENCE", "Box", "model_box"]
