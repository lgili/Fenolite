# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""A STEP writer of extruded component bodies (change c0260, decision 13; ``docs/formats/step/part21.md``).

``write_bodies(name, bodies)`` writes one ISO 10303-21 exchange file in the schema ``AUTOMOTIVE_DESIGN``
(AP214): one product named ``name`` and one closed planar B-rep solid (``MANIFOLD_SOLID_BREP``) per extruded
body, a vertical prism over the body's outline from ``z_min`` to ``z_max``, in millimetres, coloured by body
name (``body`` dark, leads, pins and tabs light). Standard library only; no float is formatted: every number
is printed exactly from integer nanometres, so equal arguments give equal bytes. The model frame is the
footprint's with Y up (the board's -Y), as KiCad places a footprint's 3D model.
"""

from __future__ import annotations

from collections.abc import Sequence

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


def _outline(body: ComponentBody) -> list[tuple[int, int]]:
    """The outline in the model frame (Y up), without a repeated last point, counter-clockwise."""
    points: list[tuple[int, int]] = []
    for point in body.outline:
        mapped = (point.x, -point.y)
        if not points or points[-1] != mapped:
            points.append(mapped)
    while len(points) > 1 and points[-1] == points[0]:
        points.pop()
    if len(points) < 3:
        raise ValueError(f"the body {body.name!r} has fewer than three distinct outline points")
    twice_area = sum(a[0] * b[1] - b[0] * a[1] for a, b in zip(points, points[1:] + points[:1], strict=True))
    if twice_area == 0:
        raise ValueError(f"the outline of the body {body.name!r} encloses no area")
    return points if twice_area > 0 else points[::-1]


def _solid(out: _File, body: ComponentBody) -> int:
    """One ``MANIFOLD_SOLID_BREP``: a prism with outward faces, each edge used once in each sense."""
    if body.kind != "extruded" or body.z_min is None or body.z_max is None:
        raise ValueError(f"the body {body.name!r} is not an extruded body with signed bounds")
    if body.z_max <= body.z_min:
        raise ValueError(f"the body {body.name!r} has no height ({body.z_min} to {body.z_max} nm)")
    ring = _outline(body)
    n = len(ring)
    lo, hi = body.z_min, body.z_max
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
    return out.add(f"MANIFOLD_SOLID_BREP({_string(body.name)},#{shell})")


def _colour(out: _File, solid: int, body: ComponentBody) -> int:
    red, green, blue = DARK if body.name == "body" else LIGHT
    colour = out.once(f"COLOUR_RGB('',{red},{green},{blue})")
    fill = out.add(f"FILL_AREA_STYLE_COLOUR('',#{colour})")
    area = out.add(f"FILL_AREA_STYLE('',(#{fill}))")
    surface = out.add(f"SURFACE_STYLE_FILL_AREA(#{area})")
    side = out.add(f"SURFACE_SIDE_STYLE('',(#{surface}))")
    usage = out.add(f"SURFACE_STYLE_USAGE(.BOTH.,#{side})")
    assignment = out.add(f"PRESENTATION_STYLE_ASSIGNMENT((#{usage}))")
    return out.add(f"STYLED_ITEM('',(#{assignment}),#{solid})")


def write_bodies(name: str, bodies: Sequence[ComponentBody], *, timestamp: str = DEFAULT_TIMESTAMP) -> bytes:
    """The bytes of one STEP file holding ``bodies`` as one product named ``name``. ``ValueError`` for no
    body, a body that is not extruded with signed bounds and a height, an outline without area, or a name
    outside printable ASCII."""
    if not bodies:
        raise ValueError("a STEP model needs at least one body")
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
    solids = [(_solid(out, body), body) for body in bodies]
    items = ",".join(f"#{item}" for item in (origin, *(s for s, _ in solids)))
    representation = out.add(f"ADVANCED_BREP_SHAPE_REPRESENTATION({_string(name)},({items}),#{geometry})")
    out.add(f"SHAPE_DEFINITION_REPRESENTATION(#{shape},#{representation})")
    styled = [_colour(out, solid, body) for solid, body in solids]
    out.add(
        "MECHANICAL_DESIGN_GEOMETRIC_PRESENTATION_REPRESENTATION('',"
        f"({','.join(f'#{s}' for s in styled)}),#{geometry})"
    )
    header = [
        "ISO-10303-21;",
        "HEADER;",
        "FILE_DESCRIPTION(('Fenolite extruded component bodies'),'2;1');",
        f"FILE_NAME({_string(name + '.step')},{_string(timestamp)},(''),(''),'Fenolite','Fenolite','');",
        f"FILE_SCHEMA(('{SCHEMA}'));",
        "ENDSEC;",
        "DATA;",
    ]
    data = [f"#{i}={text};" for i, text in enumerate(out.lines, start=1)]
    return ("\n".join([*header, *data, "ENDSEC;", "END-ISO-10303-21;"]) + "\n").encode("ascii")


__all__ = ["DEFAULT_TIMESTAMP", "SCHEMA", "mm", "write_bodies"]
