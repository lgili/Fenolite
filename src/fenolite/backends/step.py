# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""A STEP writer of component bodies (changes c0260, decision 13, and c0423; ``docs/formats/step/part21.md``).

``write_bodies(name, bodies)`` writes one ISO 10303-21 exchange file in the schema ``AUTOMOTIVE_DESIGN``
(AP214): one product named ``name`` and one closed planar B-rep solid (``MANIFOLD_SOLID_BREP``) per extruded
body, a vertical prism over the body's outline from ``z_min`` to ``z_max``, in millimetres, coloured by body
name (``body`` dark, leads, pins and tabs light). Standard library only; no float is formatted: every number
is printed exactly from integer nanometres, so equal arguments give equal bytes. The model frame is the
footprint's with Y up (the board's -Y), as KiCad places a footprint's 3D model.

``write_solids(name, solids)`` (change c0423) writes prisms, cylinders (prisms over a regular polygon) and
faceted spheres given in the model frame, every face planar, every facet within ``SAGITTA`` of the surface.
"""

from __future__ import annotations

import math
from collections.abc import Callable, Sequence
from dataclasses import dataclass

from fenolite.model.board import ComponentBody

SCHEMA = "AUTOMOTIVE_DESIGN { 1 0 10303 214 3 1 1 }"
"""The schema of the file: AP214's name with its third-edition object identifier (S-0992)."""
DEFAULT_TIMESTAMP = "1970-01-01T00:00:00"
DARK = ("0.2", "0.2", "0.2")
LIGHT = ("0.8", "0.8", "0.8")


def mm(nm: int) -> str:
    """``1270000`` → ``1.27``, ``5000000`` → ``5.``, ``-500`` → ``-0.0005``: an exact decimal of mm."""
    sign = "-" if nm < 0 else ""
    whole, part = divmod(abs(nm), 1_000_000)
    frac = f"{part:06d}".rstrip("0")
    return f"{sign}{whole}.{frac}"


def _string(text: str) -> str:
    if any(ord(c) < 32 or ord(c) > 126 for c in text):
        raise ValueError(
            f"{text!r} holds a character a STEP string here does not take (printable ASCII only)"
        )
    return "'" + text.replace("'", "''") + "'"


class _File:
    """The DATA section under construction: instances numbered in the order they are added."""

    def __init__(self) -> None:
        self.lines: list[str] = []
        self.shared: dict[str, int] = {}

    def add(self, text: str) -> int:
        self.lines.append(text)
        return len(self.lines)

    def once(self, text: str) -> int:
        """An instance written once per file, for every equal text (directions, contexts)."""
        found = self.shared.get(text)
        if found is None:
            found = self.shared[text] = self.add(text)
        return found

    def point(self, x: int, y: int, z: int) -> int:
        return self.add(f"CARTESIAN_POINT('',({mm(x)},{mm(y)},{mm(z)}))")

    def direction(self, x: int, y: int, z: int) -> int:
        """A direction from integer ratios (any length; readers normalize it)."""
        return self.once(f"DIRECTION('',({x}.,{y}.,{z}.))")

    def axis(
        self, origin: tuple[int, int, int], normal: tuple[int, int, int], ref: tuple[int, int, int]
    ) -> int:
        return self.add(
            f"AXIS2_PLACEMENT_3D('',#{self.point(*origin)},#{self.direction(*normal)},#{self.direction(*ref)})"
        )


def _ring(points: Sequence[tuple[int, int]], name: str) -> list[tuple[int, int]]:
    """``points`` (model frame) without repeated neighbours or a repeated last point, counter-clockwise."""
    ring: list[tuple[int, int]] = []
    for mapped in points:
        if not ring or ring[-1] != mapped:
            ring.append(mapped)
    while len(ring) > 1 and ring[-1] == ring[0]:
        ring.pop()
    if len(ring) < 3:
        raise ValueError(f"the body {name!r} has fewer than three distinct outline points")
    twice_area = sum(a[0] * b[1] - b[0] * a[1] for a, b in zip(ring, ring[1:] + ring[:1], strict=True))
    if twice_area == 0:
        raise ValueError(f"the outline of the body {name!r} encloses no area")
    return ring if twice_area > 0 else ring[::-1]


def _outline(body: ComponentBody) -> list[tuple[int, int]]:
    """The outline in the model frame (Y up), without a repeated last point, counter-clockwise."""
    return _ring([(point.x, -point.y) for point in body.outline], body.name)


@dataclass(frozen=True, slots=True)
class Prism:
    """A vertical prism over ``ring`` (model frame, Y up, nm) from ``z_min`` to ``z_max``; a cylinder is the
    prism over a regular polygon (``cylinder``). ``name`` names the solid and chooses its colour."""

    ring: tuple[tuple[int, int], ...]
    z_min: int
    z_max: int
    name: str = "body"


@dataclass(frozen=True, slots=True)
class Sphere:
    """A faceted sphere of ``radius`` nm about ``centre`` (model frame, Y up, nm): ``sides(radius)``
    meridians and half as many bands of planar faces, every vertex on the sphere to the nanometre."""

    centre: tuple[int, int, int]
    radius: int
    name: str = "body"


Solid = Prism | Sphere
SAGITTA = 10_000
"""The largest distance, in nm, between a facet and the true surface of a faceted cylinder or sphere."""
MIN_SIDES = 24
MAX_SIDES = 96


def sides(radius: int) -> int:
    """The even number of sides of a faceted circle of ``radius`` nm: the smallest from ``MIN_SIDES`` whose
    sagitta ``r·(1 − cos(π/n))`` is at most ``SAGITTA``, at most ``MAX_SIDES``."""
    n = MIN_SIDES
    while n < MAX_SIDES and radius * (1 - math.cos(math.pi / n)) > SAGITTA:
        n += 2
    return n


def _on_circle(cx: int, cy: int, radius: int, n: int, k: int) -> tuple[int, int]:
    angle = 2 * math.pi * k / n
    return (cx + round(radius * math.cos(angle)), cy + round(radius * math.sin(angle)))


def cylinder(centre: tuple[int, int], radius: int, z_min: int, z_max: int, name: str = "body") -> Prism:
    """The prism over the regular polygon of ``sides(radius)`` vertices on the circle of ``radius`` about
    ``centre`` (model frame, Y up), the first vertex on +X."""
    n = sides(radius)
    ring = tuple(_on_circle(centre[0], centre[1], radius, n, k) for k in range(n))
    return Prism(ring, z_min, z_max, name)


def _prism(out: _File, name: str, ring: list[tuple[int, int]], lo: int, hi: int) -> int:
    """One ``MANIFOLD_SOLID_BREP``: a prism with outward faces, each edge used once in each sense."""
    if hi <= lo:
        raise ValueError(f"the body {name!r} has no height ({lo} to {hi} nm)")
    n = len(ring)
    bottom = [out.add(f"VERTEX_POINT('',#{out.point(x, y, lo)})") for x, y in ring]
    top = [out.add(f"VERTEX_POINT('',#{out.point(x, y, hi)})") for x, y in ring]

    def edge(start: int, end: int, at: tuple[int, int, int], towards: tuple[int, int, int]) -> int:
        vector = out.add(f"VECTOR('',#{out.direction(*towards)},1.)")
        line = out.add(f"LINE('',#{out.point(*at)},#{vector})")
        return out.add(f"EDGE_CURVE('',#{start},#{end},#{line},.T.)")

    low_edges: list[int] = []
    high_edges: list[int] = []
    rising: list[int] = []
    for i, (x, y) in enumerate(ring):
        nx, ny = ring[(i + 1) % n]
        low_edges.append(edge(bottom[i], bottom[(i + 1) % n], (x, y, lo), (nx - x, ny - y, 0)))
        high_edges.append(edge(top[i], top[(i + 1) % n], (x, y, hi), (nx - x, ny - y, 0)))
        rising.append(edge(bottom[i], top[i], (x, y, lo), (0, 0, hi - lo)))

    def face(oriented: list[tuple[int, bool]], axis: int) -> int:
        refs = [out.add(f"ORIENTED_EDGE('',*,*,#{e},{'.T.' if s else '.F.'})") for e, s in oriented]
        edges = ",".join(f"#{r}" for r in refs)
        loop = out.add(f"EDGE_LOOP('',({edges}))")
        bound = out.add(f"FACE_OUTER_BOUND('',#{loop},.T.)")
        plane = out.add(f"PLANE('',#{axis})")
        return out.add(f"ADVANCED_FACE('',(#{bound}),#{plane},.T.)")

    faces: list[int] = []
    x0, y0 = ring[0]
    # Bottom (normal -Z): the ring walked backwards; top (normal +Z): the ring forwards.
    faces.append(
        face(
            [(low_edges[i], False) for i in reversed(range(n))], out.axis((x0, y0, lo), (0, 0, -1), (1, 0, 0))
        )
    )
    faces.append(
        face([(high_edges[i], True) for i in range(n)], out.axis((x0, y0, hi), (0, 0, 1), (1, 0, 0)))
    )
    for i, (x, y) in enumerate(ring):
        nx, ny = ring[(i + 1) % n]
        dx, dy = nx - x, ny - y
        sides = [
            (low_edges[i], True),
            (rising[(i + 1) % n], True),
            (high_edges[i], False),
            (rising[i], False),
        ]
        faces.append(face(sides, out.axis((x, y, lo), (dy, -dx, 0), (dx, dy, 0))))
    shell = out.add(f"CLOSED_SHELL('',({','.join(f'#{f}' for f in faces)}))")
    return out.add(f"MANIFOLD_SOLID_BREP({_string(name)},#{shell})")


def _solid(out: _File, body: ComponentBody) -> int:
    """The prism of an extruded ``body`` with signed bounds."""
    if body.kind != "extruded" or body.z_min is None or body.z_max is None:
        raise ValueError(f"the body {body.name!r} is not an extruded body with signed bounds")
    if body.z_max <= body.z_min:
        raise ValueError(f"the body {body.name!r} has no height ({body.z_min} to {body.z_max} nm)")
    return _prism(out, body.name, _outline(body), body.z_min, body.z_max)


def _sphere(out: _File, sphere: Sphere) -> int:
    """One ``MANIFOLD_SOLID_BREP`` of a faceted sphere: two poles, ``n/2 − 1`` rings of ``n`` vertices,
    triangles at the poles and planar quadrilaterals between the rings, each face counter-clockwise seen
    from outside."""
    cx, cy, cz = sphere.centre
    r = sphere.radius
    if r <= 0:
        raise ValueError(f"the sphere {sphere.name!r} has no radius")
    n = sides(r)
    bands = n // 2
    points: list[tuple[int, int, int]] = [(cx, cy, cz + r)]
    for k in range(1, bands):
        polar = math.pi * k / bands
        ring_radius, height = r * math.sin(polar), r * math.cos(polar)
        for j in range(n):
            angle = 2 * math.pi * j / n
            points.append(
                (cx + round(ring_radius * math.cos(angle)), cy + round(ring_radius * math.sin(angle)),
                 cz + round(height))
            )  # fmt: skip
    points.append((cx, cy, cz - r))
    south = len(points) - 1

    def at(k: int, j: int) -> int:
        return 1 + (k - 1) * n + j % n

    faces: list[list[int]] = [[0, at(1, j), at(1, j + 1)] for j in range(n)]
    for k in range(1, bands - 1):
        faces.extend([at(k, j), at(k + 1, j), at(k + 1, j + 1), at(k, j + 1)] for j in range(n))
    faces.extend([south, at(bands - 1, j + 1), at(bands - 1, j)] for j in range(n))
    return _polyhedron(out, sphere.name, points, faces)


def _reduced(x: int, y: int, z: int) -> tuple[int, int, int]:
    divisor = math.gcd(math.gcd(x, y), z) or 1
    return (x // divisor, y // divisor, z // divisor)


def _polyhedron(out: _File, name: str, points: list[tuple[int, int, int]], faces: list[list[int]]) -> int:
    """One ``MANIFOLD_SOLID_BREP`` of planar ``faces`` (vertex indices, counter-clockwise seen from outside)
    over ``points``: one edge per pair of neighbouring vertices, used once in each sense."""
    vertices = [out.add(f"VERTEX_POINT('',#{out.point(*p)})") for p in points]
    edges: dict[tuple[int, int], int] = {}

    def edge(a: int, b: int) -> tuple[int, bool]:
        key = (min(a, b), max(a, b))
        if key not in edges:
            (x0, y0, z0), (x1, y1, z1) = points[key[0]], points[key[1]]
            vector = out.add(f"VECTOR('',#{out.direction(*_reduced(x1 - x0, y1 - y0, z1 - z0))},1.)")
            line = out.add(f"LINE('',#{out.point(x0, y0, z0)},#{vector})")
            edges[key] = out.add(f"EDGE_CURVE('',#{vertices[key[0]]},#{vertices[key[1]]},#{line},.T.)")
        return edges[key], a < b

    built: list[int] = []
    for face in faces:
        refs: list[int] = []
        for a, b in zip(face, face[1:] + face[:1], strict=True):
            curve, sense = edge(a, b)
            refs.append(out.add(f"ORIENTED_EDGE('',*,*,#{curve},{'.T.' if sense else '.F.'})"))
        loop = out.add(f"EDGE_LOOP('',({','.join(f'#{r}' for r in refs)}))")
        bound = out.add(f"FACE_OUTER_BOUND('',#{loop},.T.)")
        p0, p1, p2 = (points[i] for i in face[:3])
        u = (p1[0] - p0[0], p1[1] - p0[1], p1[2] - p0[2])
        v = (p2[0] - p0[0], p2[1] - p0[1], p2[2] - p0[2])
        normal = (u[1] * v[2] - u[2] * v[1], u[2] * v[0] - u[0] * v[2], u[0] * v[1] - u[1] * v[0])
        axis = out.axis(p0, _reduced(*normal), _reduced(*u))
        plane = out.add(f"PLANE('',#{axis})")
        built.append(out.add(f"ADVANCED_FACE('',(#{bound}),#{plane},.T.)"))
    shell = out.add(f"CLOSED_SHELL('',({','.join(f'#{f}' for f in built)}))")
    return out.add(f"MANIFOLD_SOLID_BREP({_string(name)},#{shell})")


def _colour(out: _File, solid: int, name: str) -> int:
    red, green, blue = DARK if name == "body" else LIGHT
    colour = out.once(f"COLOUR_RGB('',{red},{green},{blue})")
    fill = out.add(f"FILL_AREA_STYLE_COLOUR('',#{colour})")
    area = out.add(f"FILL_AREA_STYLE('',(#{fill}))")
    surface = out.add(f"SURFACE_STYLE_FILL_AREA(#{area})")
    side = out.add(f"SURFACE_SIDE_STYLE('',(#{surface}))")
    usage = out.add(f"SURFACE_STYLE_USAGE(.BOTH.,#{side})")
    assignment = out.add(f"PRESENTATION_STYLE_ASSIGNMENT((#{usage}))")
    return out.add(f"STYLED_ITEM('',(#{assignment}),#{solid})")


def _document(
    name: str, build: Callable[[_File], list[tuple[int, str]]], *, timestamp: str, description: str
) -> bytes:
    out = _File()
    app = out.add("APPLICATION_CONTEXT('automotive design')")
    out.add(f"APPLICATION_PROTOCOL_DEFINITION('international standard','automotive_design',2000,#{app})")
    context = out.add(f"PRODUCT_CONTEXT('',#{app},'mechanical')")
    product = out.add(f"PRODUCT({_string(name)},{_string(name)},'',(#{context}))")
    formation = out.add(f"PRODUCT_DEFINITION_FORMATION('','',#{product})")
    definition_context = out.add(f"PRODUCT_DEFINITION_CONTEXT('part definition',#{app},'design')")
    definition = out.add(f"PRODUCT_DEFINITION('design','',#{formation},#{definition_context})")
    shape = out.add(f"PRODUCT_DEFINITION_SHAPE('','',#{definition})")
    length = out.add("( LENGTH_UNIT() NAMED_UNIT(*) SI_UNIT(.MILLI.,.METRE.) )")
    angle = out.add("( NAMED_UNIT(*) PLANE_ANGLE_UNIT() SI_UNIT($,.RADIAN.) )")
    solid_angle = out.add("( NAMED_UNIT(*) SI_UNIT($,.STERADIAN.) SOLID_ANGLE_UNIT() )")
    uncertainty = out.add(
        f"UNCERTAINTY_MEASURE_WITH_UNIT(LENGTH_MEASURE(0.0001),#{length},'distance_accuracy_value','')"
    )
    geometry = out.add(
        f"( GEOMETRIC_REPRESENTATION_CONTEXT(3) GLOBAL_UNCERTAINTY_ASSIGNED_CONTEXT((#{uncertainty})) "
        f"GLOBAL_UNIT_ASSIGNED_CONTEXT((#{length},#{angle},#{solid_angle})) REPRESENTATION_CONTEXT('','3D') )"
    )
    origin = out.axis((0, 0, 0), (0, 0, 1), (1, 0, 0))
    solids = build(out)
    items = ",".join(f"#{item}" for item in (origin, *(s for s, _ in solids)))
    representation = out.add(f"ADVANCED_BREP_SHAPE_REPRESENTATION({_string(name)},({items}),#{geometry})")
    out.add(f"SHAPE_DEFINITION_REPRESENTATION(#{shape},#{representation})")
    styled = [_colour(out, solid, solid_name) for solid, solid_name in solids]
    out.add(
        "MECHANICAL_DESIGN_GEOMETRIC_PRESENTATION_REPRESENTATION('',"
        f"({','.join(f'#{s}' for s in styled)}),#{geometry})"
    )
    header = [
        "ISO-10303-21;",
        "HEADER;",
        f"FILE_DESCRIPTION(({_string(description)}),'2;1');",
        f"FILE_NAME({_string(name + '.step')},{_string(timestamp)},(''),(''),'Fenolite','Fenolite','');",
        f"FILE_SCHEMA(('{SCHEMA}'));",
        "ENDSEC;",
        "DATA;",
    ]
    data = [f"#{i}={text};" for i, text in enumerate(out.lines, start=1)]
    return ("\n".join([*header, *data, "ENDSEC;", "END-ISO-10303-21;"]) + "\n").encode("ascii")


def write_bodies(name: str, bodies: Sequence[ComponentBody], *, timestamp: str = DEFAULT_TIMESTAMP) -> bytes:
    """The bytes of one STEP file holding ``bodies`` as one product named ``name``. ``ValueError`` for no
    body, a body that is not extruded with signed bounds and a height, an outline without area, or a name
    outside printable ASCII."""
    if not bodies:
        raise ValueError("a STEP model needs at least one body")
    return _document(
        name,
        lambda out: [(_solid(out, body), body.name) for body in bodies],
        timestamp=timestamp,
        description="Fenolite extruded component bodies",
    )


def write_solids(name: str, solids: Sequence[Solid], *, timestamp: str = DEFAULT_TIMESTAMP) -> bytes:
    """The bytes of one STEP file holding ``solids`` (prisms, faceted cylinders and spheres, in the model
    frame) as one product named ``name`` (change c0423). ``ValueError`` for no solid, a prism without height
    or area, a sphere without radius, or a name outside printable ASCII."""
    if not solids:
        raise ValueError("a STEP model needs at least one body")

    def build(out: _File) -> list[tuple[int, str]]:
        built: list[tuple[int, str]] = []
        for solid in solids:
            if isinstance(solid, Prism):
                ring = _ring(solid.ring, solid.name)
                built.append((_prism(out, solid.name, ring, solid.z_min, solid.z_max), solid.name))
            else:
                built.append((_sphere(out, solid), solid.name))
        return built

    return _document(name, build, timestamp=timestamp, description="Fenolite component bodies")


__all__ = [
    "DEFAULT_TIMESTAMP",
    "MAX_SIDES",
    "MIN_SIDES",
    "SAGITTA",
    "SCHEMA",
    "Prism",
    "Solid",
    "Sphere",
    "cylinder",
    "mm",
    "sides",
    "write_bodies",
    "write_solids",
]
