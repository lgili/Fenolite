# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Three-point arcs, circles and deterministic polygonisation (capability geometry-kernel)."""

from __future__ import annotations

import hashlib
import math
from fractions import Fraction

import pytest
from hypothesis import assume, given, settings
from hypothesis import strategies as st
from strategies import arcs

from fenolite.geometry import (
    DEFAULT_TOL,
    MAX_BISECTION_DEPTH,
    Arc,
    BBox,
    Circle,
    GeometryError,
    Location,
    Point,
    Polygon,
    orient2d,
)

P = Point
STORED = Arc(P(0, 26500000), P(-707107, 26207107), P(-1000000, 25500000))
HALF = Arc(P(1000, 0), P(0, 1000), P(-1000, 0))
# SHA-256 of the r = 1 mm circle's 32 vertices, one "x,y\n" line each (see the spec).
GOLDEN_CIRCLE_1MM = "f018b253c48500869354284ab28959cbfea687f66ce46e8d21dc1e366754c77d"


def _centre(arc: Arc) -> tuple[Fraction, Fraction]:
    assert arc.centre is not None
    return arc.centre


def _within_one_nm_of_circle(p: Point, c: tuple[Fraction, Fraction], r2: Fraction) -> bool:
    """| |p − c| − r | ≤ 1, decided exactly: (r − 1)² ≤ d² ≤ (r + 1)² with r = √r2."""
    d2 = (p.x - c[0]) ** 2 + (p.y - c[1]) ** 2
    # d² ≤ r² + 2r + 1  ⇔  d² − r² − 1 ≤ 2r ; d² ≥ r² − 2r + 1 ⇔ r² + 1 − d² ≤ 2r
    upper = d2 - r2 - 1
    lower = r2 + 1 - d2
    ok_upper = upper <= 0 or upper * upper <= 4 * r2
    ok_lower = lower <= 0 or lower * lower <= 4 * r2
    return ok_upper and ok_lower


def _sagitta_ok(u: Point, v: Point, c: tuple[Fraction, Fraction], r2: Fraction, tol: int) -> bool:
    """The chord u–v is within tol of the circle on the arc side (exact, centre opposite the arc)."""
    if u == v:
        return True
    wx, wy = v.x - u.x, v.y - u.y
    cr = wx * (c[1] - u.y) - wy * (c[0] - u.x)
    h2 = cr * cr / (wx * wx + wy * wy)
    a = r2 - h2 - tol * tol  # √r2 − √h2 ≤ tol  ⇔  r2 − h2 − tol² ≤ 2·tol·√h2
    return a <= 0 or a * a <= 4 * tol * tol * h2


# --- construction and exact values ---------------------------------------------------------------


def test_exact_centre_of_a_stored_arc() -> None:
    assert STORED.centre == (Fraction(-309449, 414214), Fraction(10562457309449, 414214))


def test_outward_rounded_bbox() -> None:
    assert STORED.bbox() == BBox(-1000001, 25500000, 0, 26500001)


def test_half_circle() -> None:
    assert HALF.centre == (0, 0)
    assert HALF.radius2 == 1000000
    assert HALF.orientation == 1
    assert HALF.bbox() == BBox(-1000, 0, 1000, 1000)
    assert HALF.reversed().orientation == -1
    assert HALF.reversed().bbox() == BBox(-1000, 0, 1000, 1000)


def test_closed_arc_rejected() -> None:
    with pytest.raises(GeometryError, match="Circle") as info:
        Arc(P(0, 0), P(5, 5), P(0, 0))
    assert info.value.code == "geometry.degenerate"


def test_mid_on_endpoint_rejected() -> None:
    with pytest.raises(GeometryError) as info:
        Arc(P(0, 0), P(0, 0), P(10, 0))
    assert info.value.code == "geometry.degenerate"


def test_collinear_arcs() -> None:
    straight = Arc(P(0, 0), P(5, 0), P(10, 0))
    assert straight.is_straight and straight.centre is None and straight.radius2 is None
    assert straight.orientation == 0
    assert straight.bbox() == BBox(0, 0, 10, 0)
    assert straight.polygonize() == (P(0, 0), P(5, 0), P(10, 0))
    assert straight.contains_point_on_circle(P(7, 0)) and not straight.contains_point_on_circle(P(11, 0))
    with pytest.raises(GeometryError) as info:
        Arc(P(0, 0), P(15, 0), P(10, 0))
    assert info.value.code == "geometry.degenerate"


def test_points_kept_unchanged() -> None:
    assert (STORED.start, STORED.mid, STORED.end) == (
        P(0, 26500000),
        P(-707107, 26207107),
        P(-1000000, 25500000),
    )


def test_point_on_arc() -> None:
    assert HALF.contains_point_on_circle(P(0, 1000))
    assert HALF.contains_point_on_circle(P(1000, 0))
    assert not HALF.contains_point_on_circle(P(0, -1000))
    assert HALF.contains_point_on_circle(P(600, 800)) and not HALF.contains_point_on_circle(P(600, -800))


def test_shallow_arc_centre_is_ill_conditioned() -> None:
    # r = 10 mm, sweep 0.1°: moving mid by 1 nm moves the derived centre by more than 0.1 mm.
    r = 10_000_000
    half_chord = 8727  # r·sin(0.05°) ≈ 8726.6
    sag_y = r - math.isqrt(r * r - half_chord * half_chord)
    arc = Arc(P(-half_chord, 0), P(0, sag_y), P(half_chord, 0))
    moved = Arc(P(-half_chord, 0), P(0, sag_y + 1), P(half_chord, 0))
    dy = _centre(arc)[1] - _centre(moved)[1]
    assert abs(dy) > 100_000


DIRECTIONS = [
    (round(1000 * math.cos(2 * math.pi * k / 1000)), round(1000 * math.sin(2 * math.pi * k / 1000)))
    for k in range(1000)
]


def _sign_plus_sqrt(a: Fraction, b: Fraction | int, q: Fraction) -> int:
    """sign(a + b·√q), q ≥ 0, exactly."""
    sa = (a > 0) - (a < 0)
    sb = ((b > 0) - (b < 0)) if q > 0 else 0
    if sb == 0:
        return sa
    if sa == 0 or sa == sb:
        return sb
    diff = a * a - b * b * q
    return sa if diff > 0 else sb if diff < 0 else 0


@settings(max_examples=25, deadline=None)
@given(arcs(coords=st.integers(-(10**6), 10**6)))
def test_bbox_contains_extremes(arc: Arc) -> None:
    """For 1000 rational directions s, the circle's extreme c + r·s/|s|, when it lies on the arc, is
    inside the bbox; every comparison is exact (squares of rationals)."""
    assume(not arc.is_straight)
    box = arc.bbox()
    cx, cy = _centre(arc)
    r2 = arc.radius2
    assert r2 is not None
    for p in (arc.start, arc.mid, arc.end):
        assert box.contains_point(p)
    s, e = arc.start, arc.end
    k = (e.x - s.x) * (cy - s.y) - (e.y - s.y) * (cx - s.x)  # orient2d(start, end, centre)
    mid_side = 1 if orient2d(s, e, arc.mid) > 0 else -1
    for dx, dy in DIRECTIONS:
        q = r2 / (dx * dx + dy * dy)  # the extreme is c + √q·(dx, dy)
        lin = (e.x - s.x) * dy - (e.y - s.y) * dx
        if _sign_plus_sqrt(k, lin, q) != mid_side:
            continue  # not on the arc (or an endpoint, already checked)
        assert _sign_plus_sqrt(cx - box.x0, dx, q) >= 0  # x0 ≤ cx + √q·dx
        assert _sign_plus_sqrt(box.x1 - cx, -dx, q) >= 0  # cx + √q·dx ≤ x1
        assert _sign_plus_sqrt(cy - box.y0, dy, q) >= 0
        assert _sign_plus_sqrt(box.y1 - cy, -dy, q) >= 0


def test_bbox_is_tight() -> None:
    # The box is no larger than the polygonised arc's box plus the 1 nm rounding of the vertices.
    for arc in (STORED, HALF, HALF.reversed(), Arc(P(0, 0), P(7, 3), P(10, -5))):
        box = arc.bbox()
        vertices = arc.polygonize(1)
        assert min(v.x for v in vertices) - 1 <= box.x0 and box.x1 <= max(v.x for v in vertices) + 1
        assert min(v.y for v in vertices) - 1 <= box.y0 and box.y1 <= max(v.y for v in vertices) + 1


def test_circle_from_kicad_irrational_radius() -> None:
    circle = Circle.from_kicad(P(0, 0), P(1, 1))
    assert circle.radius2 == 2
    assert circle.bbox() == BBox(-2, -2, 2, 2)


def test_circle_rejections() -> None:
    with pytest.raises(ValueError):
        Circle.from_radius(P(0, 0), -1)
    with pytest.raises(GeometryError):
        Circle.from_kicad(P(3, 3), P(3, 3))
    assert Circle.from_radius(P(5, 5), 10).bbox() == BBox(-5, -5, 15, 15)


# --- polygonisation -------------------------------------------------------------------------------


def test_polygonize_contains_the_three_points() -> None:
    vertices = STORED.polygonize()
    assert vertices[0] == STORED.start and vertices[-1] == STORED.end and STORED.mid in vertices
    assert all(vertices[i] != vertices[i + 1] for i in range(len(vertices) - 1))


@settings(max_examples=40, deadline=None)
@given(
    st.integers(100_000, 50_000_000),
    st.integers(1_000, 50_000),
    st.integers(1, 359_000),
    st.integers(0, 359_999),
    st.booleans(),
)
def test_polygonize_bound_holds(r: int, tol: int, sweep_mdeg: int, start_mdeg: int, negative: bool) -> None:
    """Arcs with radii 0.1–50 mm and tol 1–50 µm: vertices within 1 nm, chords within tol."""
    cx, cy = 12345, -6789

    def at(mdeg: int) -> Point:
        # integer points near the circle from an exact-enough rational angle (test data only)
        theta = math.radians(mdeg / 1000)
        return P(cx + round(r * math.cos(theta)), cy + round(r * math.sin(theta)))

    sign = -1 if negative else 1
    start, mid, end = (
        at(start_mdeg),
        at(start_mdeg + sign * sweep_mdeg // 2),
        at(start_mdeg + sign * sweep_mdeg),
    )
    try:
        arc = Arc(start, mid, end)
    except GeometryError:
        assume(False)
        raise
    assume(not arc.is_straight)
    vertices = arc.polygonize(tol)
    c = _centre(arc)
    r2 = arc.radius2
    assert r2 is not None
    assert vertices[0] == start and vertices[-1] == end and mid in vertices
    assert all(_within_one_nm_of_circle(v, c, r2) for v in vertices)
    assert all(_sagitta_ok(vertices[i], vertices[i + 1], c, r2, tol) for i in range(len(vertices) - 1))


def test_platform_independence() -> None:
    vertices = Circle(P(0, 0), 10**12).polygonize()
    assert len(vertices) == 32
    text = "".join(f"{v.x},{v.y}\n" for v in vertices)
    assert hashlib.sha256(text.encode("utf-8")).hexdigest() == GOLDEN_CIRCLE_1MM
    assert vertices[0] == P(1000000, 0)
    assert Polygon(vertices).area2 > 0


def test_tiny_radius_terminates() -> None:
    vertices = Circle.from_radius(P(0, 0), 3).polygonize(1)
    assert len(vertices) >= 4
    assert all(vertices[i] != vertices[(i + 1) % len(vertices)] for i in range(len(vertices)))
    assert all(_within_one_nm_of_circle(v, (Fraction(0), Fraction(0)), Fraction(9)) for v in vertices)


def test_invalid_tolerance() -> None:
    with pytest.raises(ValueError):
        HALF.polygonize(0)
    with pytest.raises(ValueError):
        Circle.from_radius(P(0, 0), 10).polygonize(0)


def test_outer_polygon_contains_the_circle() -> None:
    vertices = Circle.from_radius(P(0, 0), 1_000_000).polygonize(5000, outer=True)
    assert all(1005000**2 <= v.x * v.x + v.y * v.y <= 1005002**2 for v in vertices)
    poly = Polygon(vertices)
    for x in range(-1_000_000, 1_000_001, 7919):
        y = math.isqrt(10**12 - x * x)
        for p in (P(x, y), P(x, -y), P(y, x), P(-y, x)):
            assert poly.locate(p) in (Location.INSIDE, Location.BOUNDARY)


@settings(max_examples=40, deadline=None)
@given(st.integers(1_000, 10**7), st.integers(100, 100_000))
def test_outer_polygon_chords_stay_outside(r: int, tol: int) -> None:
    vertices = Circle.from_radius(P(0, 0), r).polygonize(tol, outer=True)
    n = len(vertices)
    for i in range(n):
        u, v = vertices[i], vertices[(i + 1) % n]
        wx, wy = v.x - u.x, v.y - u.y
        cr = wx * (0 - u.y) - wy * (0 - u.x)
        assert cr * cr > r * r * (wx * wx + wy * wy)  # every chord at distance > r from the centre


def test_outer_is_circle_only() -> None:
    with pytest.raises(TypeError):
        HALF.polygonize(5000, outer=True)  # type: ignore[call-arg]


def test_constants() -> None:
    assert DEFAULT_TOL == 5000
    assert MAX_BISECTION_DEPTH == 32


def test_large_arc_over_180_degrees() -> None:
    arc = Arc(P(1000, 0), P(-1000, 0), P(0, 1000))  # 270°: through (−1000, 0) to (0, 1000)
    vertices = arc.polygonize(10)
    c = _centre(arc)
    r2 = arc.radius2
    assert r2 is not None
    assert all(_within_one_nm_of_circle(v, c, r2) for v in vertices)
    assert P(0, -1000) in vertices or any(v.y < -990 for v in vertices)
    assert all(v.x < 0 or v.y < 0 or v in (P(1000, 0), P(0, 1000)) for v in vertices[1:-1])
