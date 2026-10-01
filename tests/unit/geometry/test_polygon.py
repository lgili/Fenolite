# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Polygons, convex hull, convex clip, simplicity and intersection (capability geometry-kernel)."""

from __future__ import annotations

from fractions import Fraction

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st
from strategies import rings, small_points

from fenolite.geometry import (
    FillRule,
    GeometryError,
    Location,
    Point,
    Polygon,
    SegmentRelation,
    area2,
    classify_segments,
    clip_convex,
    convex_hull,
    polygons_intersect,
)

P = Point


def square(x0: int, y0: int, x1: int, y1: int) -> Polygon:
    return Polygon((P(x0, y0), P(x1, y0), P(x1, y1), P(x0, y1)))


def test_doubled_area() -> None:
    assert Polygon((P(0, 0), P(10, 0), P(10, 10), P(0, 10))).area2 == 200
    assert area2((P(0, 0), P(0, 10), P(10, 10), P(10, 0))) == -200


def test_tuples_accepted() -> None:
    assert Polygon(((0, 0), (10, 0), (10, 10), (0, 10))) == square(0, 0, 10, 10)  # type: ignore[arg-type]


def test_normal_form() -> None:
    poly = Polygon((P(0, 10), P(10, 10), P(10, 0), P(0, 0)))
    assert poly.normalize().outer == (P(0, 0), P(10, 0), P(10, 10), P(0, 10))


def test_collinear_vertices_removed() -> None:
    poly = Polygon((P(5, 0), P(10, 0), P(10, 10), P(0, 10), P(0, 0)))
    assert poly.normalize().outer == (P(0, 0), P(10, 0), P(10, 10), P(0, 10))


@pytest.mark.parametrize(
    "ring",
    [
        ((0, 0), (10, 0)),
        ((0, 0), (5, 0), (10, 0)),
        ((0, 0), (10, 0), (10, 10), (0, 0)),
        ((0, 0), (10, 0), (10, 0), (0, 10)),
    ],
)
def test_degenerate_rings_rejected(ring: tuple[tuple[int, int], ...]) -> None:
    with pytest.raises(GeometryError) as info:
        Polygon(tuple(P(*v) for v in ring))
    assert info.value.code == "geometry.degenerate"


def test_pinch_accepted() -> None:
    ring = (P(0, 0), P(10, 0), P(10, 10), P(20, 10), P(20, 20), P(10, 20), P(10, 10), P(0, 10))
    poly = Polygon(ring)
    assert poly.area2 == 400
    assert not poly.is_simple()


def test_holes_sorted() -> None:
    outer = (P(0, 0), P(30, 0), P(30, 30), P(0, 30))
    far = (P(20, 20), P(20, 25), P(25, 25), P(25, 20))
    near = (P(5, 5), P(5, 10), P(10, 10), P(10, 5))
    poly = Polygon(outer, (far, near)).normalize()
    assert poly.holes == (near, far)
    assert poly.area2 == 2 * (900 - 25 - 25)


def test_hole_location() -> None:
    poly = Polygon((P(0, 0), P(30, 0), P(30, 30), P(0, 30)), ((P(10, 10), P(20, 10), P(20, 20), P(10, 20)),))
    assert poly.locate(P(15, 15)) == Location.OUTSIDE
    assert poly.locate(P(10, 15)) == Location.BOUNDARY
    assert poly.locate(P(5, 5)) == Location.INSIDE
    assert poly.locate(P(5, 5), FillRule.EVENODD) == Location.INSIDE


def test_bbox() -> None:
    assert square(1, 2, 3, 4).bbox().as_tuple() == (1, 2, 3, 4)


def test_convex_hull() -> None:
    pts = [P(0, 0), P(10, 0), P(10, 10), P(0, 10), P(5, 5), P(5, 0)]
    assert convex_hull(pts) == (P(0, 0), P(10, 0), P(10, 10), P(0, 10))
    assert convex_hull([P(1, 1), P(1, 1)]) == (P(1, 1),)
    assert convex_hull([P(0, 0), P(5, 5), P(10, 10)]) == (P(0, 0), P(10, 10))


@given(st.lists(small_points, min_size=3, max_size=30))
def test_hull_properties(points: list[Point]) -> None:
    hull = convex_hull(points)
    if len(hull) < 3:
        return
    poly = Polygon(hull)
    assert poly.normalize().outer == hull
    assert poly.is_convex() and poly.is_simple()
    assert all(poly.locate(p) != Location.OUTSIDE for p in points)


def test_is_convex() -> None:
    assert square(0, 0, 10, 10).is_convex()
    l_shape = Polygon((P(0, 0), P(20, 0), P(20, 10), P(10, 10), P(10, 20), P(0, 20)))
    assert not l_shape.is_convex()
    star = Polygon((P(0, -100), P(59, 81), P(-95, -31), P(95, -31), P(-59, 81)))
    assert not star.is_convex()
    assert Polygon((P(0, 0), P(5, 0), P(10, 0), P(10, 10))).is_convex()
    holed = Polygon(square(0, 0, 30, 30).outer, (square(10, 10, 20, 20).outer[::-1],))
    assert not holed.is_convex()


def test_convex_clip() -> None:
    assert clip_convex(square(0, 0, 10, 10), square(5, 5, 15, 15)) == Polygon(
        (P(5, 5), P(10, 5), P(10, 10), P(5, 10))
    )


def test_touching_clip_is_empty() -> None:
    assert clip_convex(square(0, 0, 10, 10), square(10, 0, 20, 10)) is None
    assert clip_convex(square(0, 0, 10, 10), square(20, 0, 30, 10)) is None


def test_sliver_collapses() -> None:
    triangle = Polygon((P(0, 10), P(30, 9), P(30, 20)))
    assert clip_convex(square(0, 0, 10, 10), triangle) is None


def test_concave_clip_operand_rejected() -> None:
    l_shape = Polygon((P(0, 0), P(20, 0), P(20, 10), P(10, 10), P(10, 20), P(0, 20)))
    with pytest.raises(ValueError):
        clip_convex(l_shape, square(0, 0, 5, 5))
    with pytest.raises(ValueError):
        clip_convex(square(0, 0, 5, 5), l_shape)


@settings(max_examples=150)
@given(rings(), rings())
def test_clip_result_inside_both(a: tuple[Point, ...], b: tuple[Point, ...]) -> None:
    result = clip_convex(Polygon(a), Polygon(b))
    if result is None:
        return
    assert result.area2 > 0
    assert result.normalize() == result
    # Each vertex is within 1 nm (per axis) of a point of both operands: check the rounding window.
    for v in result.outer:
        for poly in (Polygon(a), Polygon(b)):
            window = [P(v.x + dx, v.y + dy) for dx in (-1, 0, 1) for dy in (-1, 0, 1)]
            assert any(poly.locate(w) != Location.OUTSIDE for w in window)


def test_self_intersecting_ring_detected() -> None:
    assert not Polygon((P(0, 0), P(10, 10), P(10, 0), P(0, 20))).is_simple()


def test_simple_cases() -> None:
    assert square(0, 0, 10, 10).is_simple()
    assert Polygon((P(0, 0), P(10, 0), P(5, 5))).is_simple()
    holed = Polygon(square(0, 0, 30, 30).outer, (square(10, 10, 20, 20).outer[::-1],))
    assert holed.is_simple()
    touching_hole = Polygon(square(0, 0, 30, 30).outer, ((P(0, 15), P(10, 20), P(10, 10)),))
    assert not touching_hole.is_simple()
    spike = Polygon((P(0, 0), P(10, 0), P(10, 10), P(10, 20), P(10, 5), P(0, 10)))
    assert not spike.is_simple()


def _simple_brute(poly: Polygon) -> bool:
    edges: list[tuple[int, int, int, Point, Point]] = []
    for r, ring in enumerate(poly.rings()):
        n = len(ring)
        edges += [(r, i, n, ring[i], ring[(i + 1) % n]) for i in range(n)]
    for i in range(len(edges)):
        for j in range(i + 1, len(edges)):
            ri, ii, n, a, b = edges[i]
            rj, jj, _, c, d = edges[j]
            relation = classify_segments(a, b, c, d)
            if ri == rj and ((ii + 1) % n == jj or (jj + 1) % n == ii):
                if relation == SegmentRelation.COLLINEAR_OVERLAP:
                    return False
            elif relation != SegmentRelation.DISJOINT:
                return False
    return True


def _polygon_or_none(points: list[Point]) -> Polygon | None:
    try:
        return Polygon(tuple(points))
    except GeometryError:
        return None


GRID = st.builds(Point, st.integers(0, 12), st.integers(0, 12))
random_rings = st.lists(GRID, min_size=3, max_size=8).map(_polygon_or_none).filter(lambda p: p is not None)


@settings(max_examples=300)
@given(random_rings)
def test_is_simple_agrees_with_quadratic_reference(poly: Polygon) -> None:
    assert poly.is_simple() == _simple_brute(poly)


def test_closed_set_intersection() -> None:
    assert polygons_intersect(square(0, 0, 10, 10), square(10, 10, 20, 20)) is True
    assert polygons_intersect(square(0, 0, 10, 10), square(10, 0, 20, 10)) is True
    assert polygons_intersect(square(0, 0, 10, 10), square(11, 0, 20, 10)) is False
    assert polygons_intersect(square(0, 0, 30, 30), square(10, 10, 20, 20)) is True
    assert polygons_intersect(square(10, 10, 20, 20), square(0, 0, 30, 30)) is True
    holed = Polygon(square(0, 0, 30, 30).outer, (square(5, 5, 25, 25).outer,))
    assert polygons_intersect(holed, square(10, 10, 20, 20)) is False
    assert polygons_intersect(holed, square(10, 10, 25, 20)) is True


@settings(max_examples=150)
@given(rings(), rings())
def test_intersect_agrees_with_clip(a: tuple[Point, ...], b: tuple[Point, ...]) -> None:
    pa, pb = Polygon(a), Polygon(b)
    meets = polygons_intersect(pa, pb)
    assert meets == polygons_intersect(pb, pa)
    if clip_convex(pa, pb) is not None:
        assert meets
    # Exact reference for convex operands: a separating edge exists iff they are disjoint.
    separated = False
    for ring, other in ((a, b), (b, a)):
        n = len(ring)
        for i in range(n):
            u, v = ring[i], ring[(i + 1) % n]
            sides = [(v.x - u.x) * (p.y - u.y) - (v.y - u.y) * (p.x - u.x) for p in other]
            if all(s < 0 for s in sides):
                separated = True
    assert meets == (not separated)


def test_area_is_exact_fraction_free() -> None:
    poly = Polygon((P(0, 0), P(3, 0), P(0, 1)))
    assert poly.area2 == 3
    assert Fraction(poly.area2, 2) == Fraction(3, 2)
