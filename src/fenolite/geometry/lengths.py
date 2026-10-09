# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Path lengths: the centre-line length of a segment, of a three-point arc and of a part of one.

Integers and ``Fraction`` only. A length is rounded once to the nearest nanometre: the square root of an
integer is never a half, and ``r·θ`` is computed in fixed point with ``BITS`` fractional bits and rounded
half to even. Inputs that form no arc follow one rule everywhere: three distinct points on a line with
``mid`` between the ends give the two straight parts, and every input the arc shape refuses (two equal
points, or ``mid`` outside the ends on their line) gives the distance of the ends. See
``docs/geometry.md``, "Path lengths".
"""

from __future__ import annotations

from fractions import Fraction
from math import isqrt

from fenolite.core.units import round_half_even_div
from fenolite.geometry.errors import GeometryError
from fenolite.geometry.shapes import Arc
from fenolite.geometry.vector import Point

BITS = 160
"""The fractional bits of the fixed-point angle and radius."""
_ONE = 1 << BITS


def _round_sqrt(n: int) -> int:
    """``√n`` rounded to the nearest integer (a square root of an integer is never a half)."""
    return (isqrt(4 * n) + 1) // 2


def segment_length(a: Point, b: Point) -> int:
    """The distance between two points, rounded to the nearest integer nanometre."""
    return _round_sqrt((a.x - b.x) ** 2 + (a.y - b.y) ** 2)


def _atan_fixed(t: int) -> int:
    """``atan(t)`` for ``0 ≤ t ≤ 1``, both scaled by ``2**BITS``: three halvings of the angle
    (``tan(x/2) = t / (1 + √(1 + t²))``), then the power series, whose terms then shrink by a factor
    above 100."""
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
    """The angle in ``[0, 2π)``, scaled by ``2**BITS``, of a turn whose sine and cosine are proportional
    to ``cross`` and ``dot`` (not both zero)."""
    a, b = abs(cross), abs(dot)
    if a <= b:
        ratio = a / b
        angle = _atan_fixed((ratio.numerator << BITS) // ratio.denominator)
    else:
        ratio = b / a
        angle = _PI // 2 - _atan_fixed((ratio.numerator << BITS) // ratio.denominator)
    if dot < 0:
        angle = _PI - angle
    return angle if cross >= 0 else 2 * _PI - angle


_Spoke = tuple[Fraction, Fraction]


def _spoke(centre: tuple[Fraction, Fraction], point: Point) -> _Spoke:
    return Fraction(point.x) - centre[0], Fraction(point.y) - centre[1]


def _between(way: int, a: _Spoke, b: _Spoke) -> int:
    """The fixed-point angle from spoke ``a`` to spoke ``b``, turning the way the arc turns."""
    return _turn(way * (a[0] * b[1] - a[1] * b[0]), a[0] * b[0] + a[1] * b[1])


def _radius(radius2: Fraction) -> int:
    return isqrt((radius2.numerator << (2 * BITS)) // radius2.denominator)


def _sweep(shape: Arc) -> tuple[int, int]:
    """The way and the fixed-point sweep of a true arc: the turns start → mid and mid → end."""
    centre = shape.centre
    assert centre is not None
    way = shape.orientation
    spokes = [_spoke(centre, p) for p in (shape.start, shape.mid, shape.end)]
    return way, _between(way, spokes[0], spokes[1]) + _between(way, spokes[1], spokes[2])


def arc_length(start: Point, mid: Point, end: Point) -> int:
    """The centre-line length in nm of the arc from ``start`` through ``mid`` to ``end``, rounded half to
    even: ``r·θ``; the two straight parts for a straight arc; the distance of the ends for points that
    form no arc."""
    try:
        shape = Arc(start, mid, end)
    except GeometryError:
        return segment_length(start, end)
    radius2 = shape.radius2
    if radius2 is None:
        return segment_length(start, mid) + segment_length(mid, end)
    _, angle = _sweep(shape)
    return round_half_even_div(_radius(radius2) * angle, 1 << (2 * BITS))


def segment_length_to(a: Point, b: Point, at: Point) -> int:
    """The length from ``a`` to the point of the segment ``a``–``b`` nearest to ``at``, rounded to the
    nearest nanometre (half to even)."""
    dx, dy = b.x - a.x, b.y - a.y
    len2 = dx * dx + dy * dy
    if len2 == 0:
        return 0
    dot = (at.x - a.x) * dx + (at.y - a.y) * dy
    if dot <= 0:
        return 0
    if dot >= len2:
        return segment_length(a, b)
    # dot / √len2, rounded: the root of the rational dot² / len2
    return _round_sqrt_fraction(Fraction(dot * dot, len2))


def _round_sqrt_fraction(value: Fraction) -> int:
    """``√value`` rounded to the nearest integer, a tie (which needs a perfect square) going to even."""
    floor = isqrt(value.numerator // value.denominator)
    # floor ≤ √value < floor + 1; compare value with (floor + 1/2)²
    half = Fraction(2 * floor + 1, 2)
    square = half * half
    if value > square:
        return floor + 1
    if value < square:
        return floor
    return floor if floor % 2 == 0 else floor + 1


def arc_length_to(start: Point, mid: Point, end: Point, at: Point) -> int:
    """The length, computed as ``arc_length`` computes it, of the part of the arc from ``start`` to the
    point of the arc nearest to ``at``. ``at == end`` gives ``arc_length(start, mid, end)``; a point as
    near to both ends as to no other point of the arc gives the nearer end, ``start`` on a tie."""
    if at == end:
        return arc_length(start, mid, end)
    if at == start:
        return 0
    try:
        shape = Arc(start, mid, end)
    except GeometryError:
        return segment_length_to(start, end, at)
    centre, radius2 = shape.centre, shape.radius2
    if centre is None or radius2 is None:
        first = segment_length(start, mid)
        dx, dy = end.x - start.x, end.y - start.y
        if (at.x - mid.x) * dx + (at.y - mid.y) * dy <= 0:
            return segment_length_to(start, mid, at)
        return first + segment_length_to(mid, end, at)
    way, angle = _sweep(shape)
    toward = _spoke(centre, at)
    if toward != (0, 0):
        partial = _between(way, _spoke(centre, start), toward)
        if partial <= angle:
            return round_half_even_div(_radius(radius2) * partial, 1 << (2 * BITS))
    to_start = (at.x - start.x) ** 2 + (at.y - start.y) ** 2
    to_end = (at.x - end.x) ** 2 + (at.y - end.y) ** 2
    return 0 if to_start <= to_end else arc_length(start, mid, end)


__all__ = ["BITS", "arc_length", "arc_length_to", "segment_length", "segment_length_to"]
