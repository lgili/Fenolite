# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Exact closest pairs involving at least one circular arc core.

On closed pieces a distance minimum is an endpoint, a common point, or an interior stationary
pair. For circle/line pieces stationary radii are perpendicular to the line; for two nonconcentric
circles they follow the line of centres. These are all enumerated with exact arc membership tests.
Concentric arcs with overlapping directions have an endpoint radial projection in common.
"""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass
from fractions import Fraction
from typing import TYPE_CHECKING

from fenolite.geometry._radical import Real
from fenolite.geometry.index import SpatialIndex
from fenolite.geometry.predicates import Location, point_in_ring
from fenolite.geometry.shapes import Arc, BBox
from fenolite.geometry.vector import Point

if TYPE_CHECKING:
    from fenolite.geometry.thick import Thick

_XY = tuple[Real, Real]
_Rational = tuple[Fraction, Fraction]


def _xy(point: Point | _Rational) -> _XY:
    x, y = (point.x, point.y) if isinstance(point, Point) else point
    return Real(Fraction(x)), Real(Fraction(y))


@dataclass(frozen=True, slots=True)
class Closest:
    distance: Real
    a: _XY
    b: _XY

    def reversed(self) -> Closest:
        return Closest(self.distance, self.b, self.a)

    def witness(self) -> Point:
        return Point(
            (self.a[0] + self.b[0]).scaled(Fraction(1, 2)).rounded(),
            (self.a[1] + self.b[1]).scaled(Fraction(1, 2)).rounded(),
        )


def _contains(arc: Arc, point: _XY) -> bool:
    """The arc's closed chord half-plane, for a point known to lie on its circle."""
    s, e = arc.start, arc.end
    cross = (point[1] - s.y).scaled(e.x - s.x) - (point[0] - s.x).scaled(e.y - s.y)
    side = (e.x - s.x) * (arc.mid.y - s.y) - (e.y - s.y) * (arc.mid.x - s.x)
    return cross.sign() * side >= 0


def _point_arc(point: _Rational, arc: Arc) -> Iterator[Closest]:
    assert arc.centre is not None and arc.radius2 is not None
    px, py = point
    for end in (arc.start, arc.end):
        yield Closest(Real.root((px - end.x) ** 2 + (py - end.y) ** 2), _xy(point), _xy(end))
    cx, cy = arc.centre
    dx, dy = px - cx, py - cy
    d2 = dx * dx + dy * dy
    if not d2:
        return  # every point on the circle has the same distance; an endpoint suffices
    scale = Real.root(arc.radius2 / d2)
    radial = Real(cx) + scale.scaled(dx), Real(cy) + scale.scaled(dy)
    if _contains(arc, radial):
        yield Closest(abs(Real.root(d2) - Real.root(arc.radius2)), _xy(point), radial)


def _point_segment(point: Point, start: Point, end: Point) -> Closest:
    dx, dy = end.x - start.x, end.y - start.y
    length2 = dx * dx + dy * dy
    along = Fraction((point.x - start.x) * dx + (point.y - start.y) * dy, length2) if length2 else Fraction(0)
    along = max(Fraction(0), min(Fraction(1), along))
    near = Fraction(start.x) + along * dx, Fraction(start.y) + along * dy
    d2 = (point.x - near[0]) ** 2 + (point.y - near[1]) ** 2
    return Closest(Real.root(d2), _xy(point), _xy(near))


def _arc_segment(arc: Arc, start: Point, end: Point) -> Iterator[Closest]:
    assert arc.centre is not None and arc.radius2 is not None
    for point in (start, end):
        yield from (
            candidate.reversed() for candidate in _point_arc((Fraction(point.x), Fraction(point.y)), arc)
        )
    for point in (arc.start, arc.end):
        yield _point_segment(point, start, end)
    dx, dy = end.x - start.x, end.y - start.y
    length2 = dx * dx + dy * dy
    if not length2:
        return
    cx, cy = arc.centre
    along = Fraction((cx - start.x) * dx + (cy - start.y) * dy, length2)
    foot = Fraction(start.x) + along * dx, Fraction(start.y) + along * dy
    line2 = (foot[0] - cx) ** 2 + (foot[1] - cy) ** 2
    # Circle/line crossings: foot ± direction·sqrt((R² - line_distance²) / length²).
    if line2 <= arc.radius2:
        step = Real.root((arc.radius2 - line2) / length2)
        for sign in (-1, 1):
            position = Real(along) + step.scaled(sign)
            if position.sign() < 0 or (position - 1).sign() > 0:
                continue
            point = Real(foot[0]) + step.scaled(sign * dx), Real(foot[1]) + step.scaled(sign * dy)
            if _contains(arc, point):
                yield Closest(Real(), point, point)
    if 0 <= along <= 1:
        # Both perpendicular radii matter when the arc contains only the far side of the circle.
        radius = Real.root(arc.radius2 / length2)
        for sign in (-1, 1):
            point = Real(cx) + radius.scaled(-sign * dy), Real(cy) + radius.scaled(sign * dx)
            if _contains(arc, point):
                # Dot the signed centre-to-line normal with the selected radius.
                toward = (-dy) * (foot[0] - cx) + dx * (foot[1] - cy)
                radial_sign = sign * (((toward > 0) - (toward < 0)) or 1)
                distance = abs(Real.root(line2) - Real.root(arc.radius2).scaled(radial_sign))
                yield Closest(distance, point, _xy(foot))


def _arc_arc(a: Arc, b: Arc) -> Iterator[Closest]:
    assert a.centre is not None and a.radius2 is not None
    assert b.centre is not None and b.radius2 is not None
    for point in (a.start, a.end):
        yield from _point_arc((Fraction(point.x), Fraction(point.y)), b)
    for point in (b.start, b.end):
        yield from (
            candidate.reversed() for candidate in _point_arc((Fraction(point.x), Fraction(point.y)), a)
        )
    ax, ay = a.centre
    bx, by = b.centre
    dx, dy = bx - ax, by - ay
    d2 = dx * dx + dy * dy
    if not d2:
        return
    along = (a.radius2 - b.radius2 + d2) / (2 * d2)
    cross2 = a.radius2 / d2 - along * along
    if cross2 >= 0:
        height = Real.root(cross2)
        for sign in (-1, 1):
            point = (
                Real(ax + along * dx) + height.scaled(-sign * dy),
                Real(ay + along * dy) + height.scaled(sign * dx),
            )
            if _contains(a, point) and _contains(b, point):
                yield Closest(Real(), point, point)
    for sign_a in (-1, 1):
        radial_a = Real.root(a.radius2 / d2, sign_a)
        point_a = Real(ax) + radial_a.scaled(dx), Real(ay) + radial_a.scaled(dy)
        if not _contains(a, point_a):
            continue
        for sign_b in (-1, 1):
            radial_b = Real.root(b.radius2 / d2, sign_b)
            point_b = Real(bx) + radial_b.scaled(dx), Real(by) + radial_b.scaled(dy)
            if _contains(b, point_b):
                distance = abs(Real.root(d2) + Real.root(b.radius2, sign_b) - Real.root(a.radius2, sign_a))
                yield Closest(distance, point_a, point_b)


def _pieces(shape: Thick) -> Iterator[tuple[Point, Point]]:
    count = len(shape.core)
    if count == 1:
        yield shape.core[0], shape.core[0]
    else:
        for k in range(count if shape.filled else count - 1):
            yield shape.core[k], shape.core[(k + 1) % count]


def _best(candidates: Iterator[Closest]) -> Closest:
    best: Closest | None = None
    for candidate in candidates:
        if best is None or (candidate.distance - best.distance).sign() < 0:
            best = candidate
            if not best.distance.sign():
                break
    assert best is not None
    return best


def closest(a: Thick, b: Thick, index: SpatialIndex[int] | None = None) -> Closest:
    """The first closest exact candidate, in a canonical order, including filled containment."""
    assert a.arc is not None or b.arc is not None
    if a.arc is None:
        return closest(b, a, index).reversed()
    arc = a.arc
    if b.filled and point_in_ring(arc.start, b.core) != Location.OUTSIDE:
        point = _xy(arc.start)
        return Closest(Real(), point, point)
    if b.arc is not None:
        return _best(_arc_arc(arc, b.arc))
    if index is None:
        return _best(candidate for start, end in _pieces(b) for candidate in _arc_segment(arc, start, end))
    # Once a candidate is no farther than reach, segments outside this closed inflated true arc
    # box cannot improve or tie it. Every widening remains an exact integer broad-phase query.
    segments = tuple(_pieces(b))
    box, other = arc.bbox(), BBox.of_points(b.core)
    reach = max(box.x0 - other.x1, other.x0 - box.x1, box.y0 - other.y1, other.y0 - box.y1, 0) + 1
    while True:
        pieces = index.query(box.inflate(reach))
        if pieces:
            best = _best(candidate for k in pieces for candidate in _arc_segment(arc, *segments[k]))
            if (best.distance - reach).sign() <= 0:
                return best
        reach *= 4
