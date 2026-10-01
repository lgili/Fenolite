# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Exact predicates (capability geometry-kernel)."""

from __future__ import annotations

from fractions import Fraction

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st
from strategies import rings, small_points

from fenolite.geometry import (
    FillRule,
    Location,
    Point,
    SegmentRelation,
    ceil_sqrt,
    classify_segments,
    dist2_point_segment,
    dist2_segment_segment,
    floor_sqrt,
    intersection_point,
    orient2d,
    point_in_ring,
    round_point,
    segments_closer_than,
)

P = Point
LIMIT = 2**31 - 1
big = st.integers(min_value=-LIMIT, max_value=LIMIT)
big_points = st.builds(Point, big, big)


# --- orientation ----------------------------------------------------------------------------------


def test_positive_orientation() -> None:
    assert orient2d(P(0, 0), P(10, 0), P(0, 10)) == 100


def test_exact_at_the_32_bit_limit() -> None:
    a = P(-LIMIT, -LIMIT)
    b = P(LIMIT, LIMIT)
    c = P(LIMIT - 1, LIMIT - 1)
    assert orient2d(a, b, c) == 0


@given(big_points, big_points, big_points)
def test_antisymmetry(a: Point, b: Point, c: Point) -> None:
    assert orient2d(a, b, c) == -orient2d(b, a, c)
    assert orient2d(a, b, c) == orient2d(b, c, a)


def test_type_error_names_argument() -> None:
    with pytest.raises(TypeError, match=r"\bc\b"):
        orient2d(P(0, 0), P(1, 0), P(0.5, 1))  # type: ignore[arg-type]


# --- segments -------------------------------------------------------------------------------------

R = SegmentRelation


@pytest.mark.parametrize(
    ("a", "b", "c", "d", "relation", "point"),
    [
        ((0, 0), (10, 10), (0, 10), (10, 0), R.PROPER, (5, 5)),
        ((0, 0), (10, 0), (5, 0), (5, 10), R.TOUCHING, (5, 0)),
        ((0, 0), (10, 0), (5, 0), (15, 0), R.COLLINEAR_OVERLAP, None),
        ((0, 0), (10, 0), (10, 0), (20, 0), R.COLLINEAR_TOUCH, (10, 0)),
        ((0, 0), (10, 0), (0, 5), (10, 5), R.DISJOINT, None),
        ((0, 0), (10, 0), (11, 0), (20, 0), R.DISJOINT, None),
        ((0, 0), (10, 0), (10, 0), (10, 5), R.TOUCHING, (10, 0)),
        ((0, 0), (10, 0), (3, 0), (3, 0), R.TOUCHING, (3, 0)),
        ((0, 0), (10, 0), (3, 1), (3, 1), R.DISJOINT, None),
        ((4, 4), (4, 4), (4, 4), (4, 4), R.TOUCHING, (4, 4)),
        ((0, 0), (10, 0), (2, 0), (8, 0), R.COLLINEAR_OVERLAP, None),
        ((0, 0), (0, 10), (0, 12), (0, 20), R.DISJOINT, None),
    ],
)
def test_classify(
    a: tuple[int, int],
    b: tuple[int, int],
    c: tuple[int, int],
    d: tuple[int, int],
    relation: SegmentRelation,
    point: tuple[int, int] | None,
) -> None:
    pa, pb, pc, pd = P(*a), P(*b), P(*c), P(*d)
    assert classify_segments(pa, pb, pc, pd) == relation
    assert classify_segments(pc, pd, pa, pb) == relation
    assert classify_segments(pb, pa, pd, pc) == relation
    expected = None if point is None else (Fraction(point[0]), Fraction(point[1]))
    assert intersection_point(pa, pb, pc, pd) == expected


def test_rational_intersection_rounded_half_to_even() -> None:
    exact = intersection_point(P(0, 0), P(3, 1), P(0, 1), P(3, 0))
    assert exact == (Fraction(3, 2), Fraction(1, 2))
    assert round_point(*exact) == P(2, 0)


def test_round_point() -> None:
    assert round_point(Fraction(5, 2), Fraction(-5, 2)) == P(2, -2)
    assert round_point(Fraction(7, 2), 3) == P(4, 3)
    assert round_point(Fraction(-1, 3), Fraction(2, 3)) == P(0, 1)


def _brute_relation(a: Point, b: Point, c: Point, d: Point) -> int:
    """Number of common points (0, 1 or 2 = many) by exact parametric solving."""
    common: set[tuple[Fraction, Fraction]] = set()
    candidates = [a, b, c, d]
    for p in candidates:
        if dist2_point_segment(p, a, b) == 0 and dist2_point_segment(p, c, d) == 0:
            common.add((Fraction(p.x), Fraction(p.y)))
    rx, ry, sx, sy = b.x - a.x, b.y - a.y, d.x - c.x, d.y - c.y
    den = rx * sy - ry * sx
    if den:
        t = Fraction((c.x - a.x) * sy - (c.y - a.y) * sx, den)
        u = Fraction((c.x - a.x) * ry - (c.y - a.y) * rx, den)
        if 0 <= t <= 1 and 0 <= u <= 1:
            common.add((a.x + t * rx, a.y + t * ry))
    return min(len(common), 2)


@settings(max_examples=400)
@given(small_points, small_points, small_points, small_points)
def test_classification_agrees_with_parametric_solution(a: Point, b: Point, c: Point, d: Point) -> None:
    relation = classify_segments(a, b, c, d)
    count = _brute_relation(a, b, c, d)
    if relation == R.DISJOINT:
        assert count == 0
    elif relation == R.COLLINEAR_OVERLAP:
        assert count == 2
    else:
        assert count == 1 or (a == b and c == d)
        point = intersection_point(a, b, c, d)
        assert point is not None
        q = point
        # The point lies on both segments: check with exact rational arithmetic.
        for s, t in ((a, b), (c, d)):
            cr = (t.x - s.x) * (q[1] - s.y) - (t.y - s.y) * (q[0] - s.x)
            assert cr == 0
            assert min(s.x, t.x) <= q[0] <= max(s.x, t.x)
            assert min(s.y, t.y) <= q[1] <= max(s.y, t.y)


# --- point location -------------------------------------------------------------------------------

SQUARE = (P(0, 0), P(10, 0), P(10, 10), P(0, 10))


@pytest.mark.parametrize(
    ("point", "where"),
    [
        ((5, 5), Location.INSIDE),
        ((10, 5), Location.BOUNDARY),
        ((0, 0), Location.BOUNDARY),
        ((11, 5), Location.OUTSIDE),
    ],
)
def test_square(point: tuple[int, int], where: Location) -> None:
    assert point_in_ring(P(*point), SQUARE) == where
    assert point_in_ring(P(*point), tuple(reversed(SQUARE))) == where


def test_fill_rules_differ_on_a_doubly_wound_ring() -> None:
    star = (P(0, -100), P(59, 81), P(-95, -31), P(95, -31), P(-59, 81))
    assert point_in_ring(P(0, 0), star) == Location.INSIDE
    assert point_in_ring(P(0, 0), star, FillRule.EVENODD) == Location.OUTSIDE


def test_ray_through_vertices() -> None:
    diamond = (P(0, -10), P(10, 0), P(0, 10), P(-10, 0))
    assert point_in_ring(P(-20, 0), diamond) == Location.OUTSIDE
    assert point_in_ring(P(0, 0), diamond) == Location.INSIDE
    assert point_in_ring(P(5, -5), diamond) == Location.BOUNDARY


@given(rings(), small_points)
def test_convex_ring_location_matches_orientations(ring: tuple[Point, ...], p: Point) -> None:
    n = len(ring)
    signs = [orient2d(ring[i], ring[(i + 1) % n], p) for i in range(n)]
    if all(s > 0 for s in signs):
        expected = Location.INSIDE
    elif any(s < 0 for s in signs):
        expected = Location.OUTSIDE
    else:
        expected = Location.BOUNDARY
    assert point_in_ring(p, ring) == expected


# --- distances ------------------------------------------------------------------------------------


def test_rational_distance() -> None:
    assert dist2_point_segment(P(1, 1), P(0, 0), P(2, 1)) == Fraction(1, 5)


def test_endpoint_is_nearest() -> None:
    assert dist2_point_segment(P(15, 0), P(0, 0), P(10, 0)) == Fraction(25)


def test_segment_distances() -> None:
    assert dist2_segment_segment(P(0, 0), P(10, 0), P(0, 3), P(10, 3)) == 9
    assert dist2_segment_segment(P(0, 0), P(10, 10), P(0, 10), P(10, 0)) == 0


def test_strict_clearance_comparison() -> None:
    a, b, c, d = P(0, 0), P(10, 0), P(0, 3), P(10, 3)
    assert segments_closer_than(a, b, c, d, limit=3) is False
    assert segments_closer_than(a, b, c, d, limit=4) is True
    assert segments_closer_than(a, b, a, b, limit=0) is False


@settings(max_examples=300)
@given(small_points, small_points, small_points, small_points, st.integers(min_value=0, max_value=3000))
def test_distance_properties(a: Point, b: Point, c: Point, d: Point, limit: int) -> None:
    exact = dist2_segment_segment(a, b, c, d)
    # Brute force on the 8× scaled figure, where points at k/8 along a–b are integer points.
    c8, d8 = P(8 * c.x, 8 * c.y), P(8 * d.x, 8 * d.y)
    samples = [
        dist2_point_segment(P(8 * a.x + (b.x - a.x) * k, 8 * a.y + (b.y - a.y) * k), c8, d8) for k in range(9)
    ]
    assert 64 * exact <= min(samples)
    if classify_segments(a, b, c, d) == R.DISJOINT:
        ends = (dist2_point_segment(a, c, d), dist2_point_segment(b, c, d))
        assert exact == min(*ends, dist2_point_segment(c, a, b), dist2_point_segment(d, a, b))
    else:
        assert exact == 0
    assert segments_closer_than(a, b, c, d, limit) == (exact < limit * limit)


def test_square_roots() -> None:
    assert floor_sqrt(Fraction(1, 5)) == 0
    assert ceil_sqrt(Fraction(1, 5)) == 1
    assert floor_sqrt(25) == 5
    assert ceil_sqrt(25) == 5
    assert ceil_sqrt(26) == 6
    assert floor_sqrt(Fraction(9, 4)) == 1
    assert ceil_sqrt(Fraction(9, 4)) == 2


@given(st.fractions(min_value=0, max_value=10**12, max_denominator=10**6))
def test_square_root_bounds(q: Fraction) -> None:
    lo, hi = floor_sqrt(q), ceil_sqrt(q)
    assert lo * lo <= q < (lo + 1) ** 2
    assert q <= hi * hi
    assert hi == 0 or (hi - 1) ** 2 < q


def test_negative_argument() -> None:
    with pytest.raises(ValueError):
        floor_sqrt(-1)
    with pytest.raises(ValueError):
        ceil_sqrt(Fraction(-1, 2))
