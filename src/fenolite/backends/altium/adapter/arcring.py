# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The ring of an Altium polygon record whose outline holds arc vertices (change c0463; ``pcb-pour.md``,
"Outline arcs", S-2221): each arc turned into the fewest equal chords within the polygon's
``ARCRESOLUTION``, their ends on the arc. The import gives a zone this ring as its outline, the computed pour
pours it, and the conversion back to Altium compares a KiCad zone's outline with it (``convert.zonearcs``).
Pure integer geometry: no optional dependency."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from fractions import Fraction
from typing import Final

from fenolite.backends.altium.read.pcbstack import OutlineVertex
from fenolite.backends.altium.read.proptext import parse_length
from fenolite.core.coords import Point
from fenolite.core.units import Nm

ARC_END_NM: Final = 10_000
"""How far the ends of an outline arc, computed from its centre, radius and angles, may lie from the two
vertices it joins (as ``adapter.copper.OUTLINE_VERTEX_NM`` for the board outline); farther, the arc cannot
be placed and the polygon is refused ``outline-arc``."""
MAX_CHORDS: Final = 1 << 16


def _chord_count(radius: Fraction, turn: int, d: Nm) -> int:
    """The fewest equal chords of an arc of ``radius`` units sweeping ``turn`` microdegrees whose sagitta
    ``r·(1 − cos(step/2))`` is at most ``d`` nanometres: the largest step within ``d`` (S-2221)."""
    from fenolite.backends.altium.adapter.units import NM_PER_UNIT
    from fenolite.core.trig import ONE, cos_sin_fixed

    r = radius * NM_PER_UNIT
    if r <= d:
        return max(1, -(-turn // 180_000_000))  # a half turn at most per chord

    def within(n: int) -> bool:
        half = -(-turn // (2 * n))  # rounded up: the computed sagitta is never below the true one
        cos, _ = cos_sin_fixed(half)
        return r * (ONE - cos) <= d * ONE

    if not within(MAX_CHORDS):
        return MAX_CHORDS
    low, high = 1, MAX_CHORDS  # the sagitta falls as n grows: the fewest n within d, by halving
    while low < high:
        mid = (low + high) // 2
        if within(mid):
            high = mid
        else:
            low = mid + 1
    return low


def record_outline(vertices: Sequence[OutlineVertex], d: Nm) -> tuple[Point, ...]:
    """The ring of a polygon record in the frame of the import, each arc vertex turned into equal chords by
    ``d`` (its ``ARCRESOLUTION``, S-2221): vertex k runs to vertex k + 1, a line for ``KIND=0`` and else the
    arc of the vertex's centre, radius and angles, counter-clockwise from its start angle to its end angle,
    walked from the end nearer to vertex k. The chord ends lie on the arc, rounded to the nanometre; the two
    vertices stand for the arc's ends. A repeated vertex is kept once. Empty when an arc has no radius or
    its ends lie farther than ``ARC_END_NM`` from the two vertices."""
    from fenolite.backends.altium.adapter import units

    count = len(vertices)
    corners = [Point(units.units_length(v.x)[0], -units.units_length(v.y)[0]) for v in vertices]
    points: list[Point] = []
    for k, vertex in enumerate(vertices):
        a, b = corners[k], corners[(k + 1) % count]
        points.append(a)
        if vertex.kind == 0 or a == b:
            continue
        if vertex.radius <= 0:
            return ()
        start, _ = units.angle(vertex.start_angle)
        end, _ = units.angle(vertex.end_angle)
        turn = units.sweep(start, end)
        first, _, last = units.arc_points(vertex.cx, vertex.cy, vertex.radius, start, end)
        forward = _near(first, a) <= _near(first, b)
        if not forward:
            first, last = last, first
        if _near(first, a) > ARC_END_NM**2 or _near(last, b) > ARC_END_NM**2:
            return ()
        n = _chord_count(vertex.radius, turn, d)
        inner = [units.arc_points(vertex.cx, vertex.cy, vertex.radius, start, start + turn * i // n)[2]
                 for i in range(1, n)]  # fmt: skip
        points.extend(inner if forward else reversed(inner))
    return once(points)


def once(points: Sequence[Point]) -> tuple[Point, ...]:
    """``points`` as a ring with each run of a repeated vertex kept once, the closing vertex included
    (S-2222: Altium fills such an outline as the ring without the repeat)."""
    ring: list[Point] = []
    for point in points:
        if not ring or point != ring[-1]:
            ring.append(point)
    while len(ring) > 1 and ring[-1] == ring[0]:
        ring.pop()
    return tuple(ring)


def _near(p: Point, q: Point) -> int:
    return (p.x - q.x) ** 2 + (p.y - q.y) ** 2


@dataclass(frozen=True, slots=True)
class ArcPolygon:
    """The outline of a source polygon record that holds arc vertices (change c0463, task 1.3): its
    vertices as read (the closing vertex included, as the record holds it) and its ``ARCRESOLUTION`` text.
    ``ring`` is the outline the model and KiCad hold; the Altium writer writes these vertices back for a
    zone whose outline is that ring moved by a translation (``matches``)."""

    vertices: tuple[OutlineVertex, ...]
    arc_resolution: str

    def ring(self) -> tuple[Point, ...]:
        """``record_outline`` of the vertices by the polygon's ``ARCRESOLUTION``; empty when it cannot be
        read."""
        d = parse_length(self.arc_resolution)
        return record_outline(self.vertices, d) if d is not None and d > 0 else ()

    def matches(self, outline: Sequence[Point]) -> Point | None:
        """The translation that moves ``ring`` onto ``outline`` (each run of a repeated vertex kept once),
        or ``None`` when no translation does: the outline was edited."""
        ring, found = self.ring(), once(outline)
        if not ring or len(ring) != len(found):
            return None
        dx, dy = found[0].x - ring[0].x, found[0].y - ring[0].y
        if all(p.x - q.x == dx and p.y - q.y == dy for p, q in zip(found, ring, strict=True)):
            return Point(dx, dy)
        return None


__all__ = ["ARC_END_NM", "MAX_CHORDS", "ArcPolygon", "once", "record_outline"]
