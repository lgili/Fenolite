# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Exact predicates on integer points: orientation, segment relations, point location, distances.

Frame: X to the right, Y down (the KiCad file frame). ``orient2d(a, b, c)`` is
``(b.x−a.x)·(c.y−a.y) − (b.y−a.y)·(c.x−a.x)``; a positive value is called *positive orientation*
(a left turn in a Y-up frame, which displays clockwise in the Y-down frame). Everything is computed
with Python integers or ``Fraction``; no result is a ``float``.
"""

from __future__ import annotations

from collections.abc import Sequence
from enum import StrEnum
from fractions import Fraction
from math import isqrt

from fenolite.core.units import round_half_even_div
from fenolite.geometry.vector import Point, require_int, require_point


class SegmentRelation(StrEnum):
    DISJOINT = "disjoint"
    PROPER = "proper"  # the interiors cross at one point
    TOUCHING = "touching"  # one point in common, an endpoint lies on the other segment
    COLLINEAR_OVERLAP = "collinear-overlap"  # collinear, sharing a piece of positive length
    COLLINEAR_TOUCH = "collinear-touch"  # collinear, sharing exactly one endpoint


class Location(StrEnum):
    INSIDE = "inside"
    OUTSIDE = "outside"
    BOUNDARY = "boundary"


class FillRule(StrEnum):
    NONZERO = "nonzero"
    EVENODD = "evenodd"


def _orient(ax: int, ay: int, bx: int, by: int, cx: int, cy: int) -> int:
    return (bx - ax) * (cy - ay) - (by - ay) * (cx - ax)


def orient2d(a: Point, b: Point, c: Point) -> int:
    """Twice the signed area of the triangle ``a, b, c`` (exact)."""
    require_point(a, "a")
    require_point(b, "b")
    require_point(c, "c")
    return _orient(a.x, a.y, b.x, b.y, c.x, c.y)


def _on_segment(p: Point, a: Point, b: Point) -> bool:
    """``p`` on the closed segment ``a–b`` (``a == b`` allowed)."""
    if _orient(a.x, a.y, b.x, b.y, p.x, p.y) != 0:
        return False
    return min(a.x, b.x) <= p.x <= max(a.x, b.x) and min(a.y, b.y) <= p.y <= max(a.y, b.y)


def _sign(v: int) -> int:
    return (v > 0) - (v < 0)


def _classify(a: Point, b: Point, c: Point, d: Point) -> tuple[SegmentRelation, Point | None]:
    """The relation and, for a collinear touch or a degenerate segment, the common point."""
    if a == b or c == d:
        point, (s, t) = (a, (c, d)) if a == b else (c, (a, b))
        if _on_segment(point, s, t):
            return SegmentRelation.TOUCHING, point
        return SegmentRelation.DISJOINT, None
    o1 = _sign(_orient(a.x, a.y, b.x, b.y, c.x, c.y))
    o2 = _sign(_orient(a.x, a.y, b.x, b.y, d.x, d.y))
    if o1 == 0 and o2 == 0:
        # Collinear: lexicographic order is monotone along a line.
        s0, s1 = min(a, b), max(a, b)
        t0, t1 = min(c, d), max(c, d)
        lo, hi = max(s0, t0), min(s1, t1)
        if lo > hi:
            return SegmentRelation.DISJOINT, None
        if lo == hi:
            return SegmentRelation.COLLINEAR_TOUCH, lo
        return SegmentRelation.COLLINEAR_OVERLAP, None
    if o1 == o2:
        return SegmentRelation.DISJOINT, None
    o3 = _sign(_orient(c.x, c.y, d.x, d.y, a.x, a.y))
    o4 = _sign(_orient(c.x, c.y, d.x, d.y, b.x, b.y))
    if o3 == o4:  # both non-zero here: o3 == o4 == 0 would make all four points collinear
        return SegmentRelation.DISJOINT, None
    if o1 and o2 and o3 and o4:
        return SegmentRelation.PROPER, None
    return SegmentRelation.TOUCHING, None


def classify_segments(a: Point, b: Point, c: Point, d: Point) -> SegmentRelation:
    """Relation between the closed segments ``a–b`` and ``c–d`` (a degenerate segment is a point)."""
    for name, p in (("a", a), ("b", b), ("c", c), ("d", d)):
        require_point(p, name)
    return _classify(a, b, c, d)[0]


def _line_intersection(a: Point, b: Point, c: Point, d: Point) -> tuple[Fraction, Fraction]:
    rx, ry = b.x - a.x, b.y - a.y
    sx, sy = d.x - c.x, d.y - c.y
    denom = rx * sy - ry * sx
    t = Fraction((c.x - a.x) * sy - (c.y - a.y) * sx, denom)
    return a.x + t * rx, a.y + t * ry


def intersection_point(a: Point, b: Point, c: Point, d: Point) -> tuple[Fraction, Fraction] | None:
    """The exact common point for ``PROPER``, ``TOUCHING`` and ``COLLINEAR_TOUCH``; ``None`` otherwise."""
    for name, p in (("a", a), ("b", b), ("c", c), ("d", d)):
        require_point(p, name)
    relation, point = _classify(a, b, c, d)
    if relation in (SegmentRelation.DISJOINT, SegmentRelation.COLLINEAR_OVERLAP):
        return None
    if point is not None:
        return Fraction(point.x), Fraction(point.y)
    return _line_intersection(a, b, c, d)


def round_point(x: Fraction | int, y: Fraction | int) -> Point:
    """Round an exact rational point to nanometres, half to even per axis (error ≤ 0.5 nm per axis)."""
    fx, fy = Fraction(x), Fraction(y)
    return Point(
        round_half_even_div(fx.numerator, fx.denominator), round_half_even_div(fy.numerator, fy.denominator)
    )


def _winding(px: int, py: int, ring: Sequence[Point]) -> int | None:
    """Winding number of ``ring`` around ``(px, py)``; ``None`` when the point is on the ring."""
    wn = 0
    n = len(ring)
    for i in range(n):
        a = ring[i]
        b = ring[(i + 1) % n]
        o = _orient(a.x, a.y, b.x, b.y, px, py)
        if o == 0 and min(a.x, b.x) <= px <= max(a.x, b.x) and min(a.y, b.y) <= py <= max(a.y, b.y):
            return None
        # Half-open crossing rule: an edge counts when it crosses the horizontal line through p
        # with exactly one endpoint at or below p.y.
        if a.y <= py:
            if b.y > py and o > 0:
                wn += 1
        elif b.y <= py and o < 0:
            wn -= 1
    return wn


def point_in_ring(p: Point, ring: Sequence[Point], rule: FillRule = FillRule.NONZERO) -> Location:
    """Exact location of ``p`` relative to the closed ring (``BOUNDARY`` on any edge or vertex)."""
    require_point(p, "p")
    for i, v in enumerate(ring):
        require_point(v, f"ring[{i}]")
    wn = _winding(p.x, p.y, ring)
    if wn is None:
        return Location.BOUNDARY
    inside = wn != 0 if rule == FillRule.NONZERO else wn % 2 == 1
    return Location.INSIDE if inside else Location.OUTSIDE


def _dist2_point_segment(px: int, py: int, a: Point, b: Point) -> Fraction:
    dx, dy = b.x - a.x, b.y - a.y
    ex, ey = px - a.x, py - a.y
    length2 = dx * dx + dy * dy
    t = ex * dx + ey * dy
    if length2 == 0 or t <= 0:
        return Fraction(ex * ex + ey * ey)
    if t >= length2:
        fx, fy = px - b.x, py - b.y
        return Fraction(fx * fx + fy * fy)
    cr = dx * ey - dy * ex
    return Fraction(cr * cr, length2)


def dist2_point_segment(p: Point, a: Point, b: Point) -> Fraction:
    """Exact squared distance from ``p`` to the closed segment ``a–b``."""
    for name, q in (("p", p), ("a", a), ("b", b)):
        require_point(q, name)
    return _dist2_point_segment(p.x, p.y, a, b)


def dist2_segment_segment(a: Point, b: Point, c: Point, d: Point) -> Fraction:
    """Exact squared distance between two closed segments (0 when they meet in any way)."""
    for name, q in (("a", a), ("b", b), ("c", c), ("d", d)):
        require_point(q, name)
    if _classify(a, b, c, d)[0] != SegmentRelation.DISJOINT:
        return Fraction(0)
    return min(
        _dist2_point_segment(a.x, a.y, c, d),
        _dist2_point_segment(b.x, b.y, c, d),
        _dist2_point_segment(c.x, c.y, a, b),
        _dist2_point_segment(d.x, d.y, a, b),
    )


def _point_segment_closer(px: int, py: int, a: Point, b: Point, limit2: int) -> bool:
    dx, dy = b.x - a.x, b.y - a.y
    ex, ey = px - a.x, py - a.y
    length2 = dx * dx + dy * dy
    t = ex * dx + ey * dy
    if length2 == 0 or t <= 0:
        return ex * ex + ey * ey < limit2
    if t >= length2:
        fx, fy = px - b.x, py - b.y
        return fx * fx + fy * fy < limit2
    cr = dx * ey - dy * ex
    return cr * cr < limit2 * length2


def segments_closer_than(a: Point, b: Point, c: Point, d: Point, limit: int) -> bool:
    """``distance(a–b, c–d) < limit``, decided with integers only (no fraction is formed)."""
    for name, q in (("a", a), ("b", b), ("c", c), ("d", d)):
        require_point(q, name)
    require_int(limit, "limit")
    if limit <= 0:
        return False
    if _classify(a, b, c, d)[0] != SegmentRelation.DISJOINT:
        return True
    limit2 = limit * limit
    return (
        _point_segment_closer(a.x, a.y, c, d, limit2)
        or _point_segment_closer(b.x, b.y, c, d, limit2)
        or _point_segment_closer(c.x, c.y, a, b, limit2)
        or _point_segment_closer(d.x, d.y, a, b, limit2)
    )


def _as_fraction(q: Fraction | int, name: str) -> Fraction:
    if isinstance(q, bool) or not isinstance(q, (int, Fraction)):  # pyright: ignore[reportUnnecessaryIsInstance]
        raise TypeError(f"{name} must be an int or a Fraction, got {q!r}")
    value = Fraction(q)
    if value < 0:
        raise ValueError(f"square root of a negative number: {q}")
    return value


def floor_sqrt(q: Fraction | int) -> int:
    """Exact ``⌊√q⌋`` for a non-negative ``int`` or ``Fraction``."""
    value = _as_fraction(q, "q")
    n, d = value.numerator, value.denominator
    return isqrt(n * d) // d


def ceil_sqrt(q: Fraction | int) -> int:
    """Exact ``⌈√q⌉`` for a non-negative ``int`` or ``Fraction``."""
    value = _as_fraction(q, "q")
    k = isqrt(value.numerator * value.denominator) // value.denominator
    return k if k * k * value.denominator == value.numerator else k + 1


__all__ = [
    "FillRule",
    "Location",
    "SegmentRelation",
    "ceil_sqrt",
    "classify_segments",
    "dist2_point_segment",
    "dist2_segment_segment",
    "floor_sqrt",
    "intersection_point",
    "orient2d",
    "point_in_ring",
    "round_point",
    "segments_closer_than",
]
