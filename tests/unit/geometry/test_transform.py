# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Fixed-point microdegree rotation and placement transforms (capability geometry-kernel)."""

from __future__ import annotations

import decimal
import math
from fractions import Fraction
from pathlib import Path

import pytest
from hypothesis import example, given, settings
from hypothesis import strategies as st
from strategies import transforms

import fenolite.geometry.transform as transform_module
from fenolite.core.units import round_half_even_div
from fenolite.geometry import (
    FULL_TURN,
    TRIG_BITS,
    Arc,
    BBox,
    GeometryError,
    Point,
    Polygon,
    Segment,
    Transform,
    cos_sin_fixed,
    rotate_point,
)

P = Point
ONE = 1 << TRIG_BITS
LIMIT = 2**31
GOLDEN: dict[int, tuple[int, int]] = {
    0: (340282366920938463463374607431768211456, 0),
    1: (340282366920938411635406302246611496695, 5939047689249814964364216002651),
    1_000_000: (340230540268261750956743264373121785153, 5938746170945056723073406927607666420),
    15_000_000: (328687526439707402833014108162414875017, 88071557271702891287980335684789818090),
    30_000_000: (294693174213430241384087455685767077317, 170141183460469231731687303715884105728),
    45_000_000: (240615969168004511545033772477625056927, 240615969168004511545033772477625056927),
    60_000_000: (170141183460469231731687303715884105728, 294693174213430241384087455685767077317),
    90_000_000: (0, 340282366920938463463374607431768211456),
    123_456_789: (-187600368416579124993302632859074527616, 283898205361146967836380899857446725173),
    180_000_000: (-340282366920938463463374607431768211456, 0),
    270_000_001: (5939047689249814964364216002651, -340282366920938411635406302246611496695),
    359_999_999: (340282366920938411635406302246611496695, -5939047689249814964364216002651),
}


# --- the table ------------------------------------------------------------------------------------


def test_table_golden_values() -> None:
    for udeg, expected in GOLDEN.items():
        assert cos_sin_fixed(udeg) == expected, udeg
        assert cos_sin_fixed(udeg + FULL_TURN) == expected
        assert cos_sin_fixed(udeg - 3 * FULL_TURN) == expected


def test_table_exact_entries() -> None:
    assert cos_sin_fixed(60_000_000)[0] == 2**127
    assert cos_sin_fixed(30_000_000)[1] == 2**127
    assert cos_sin_fixed(90_000_000) == (0, 2**128)
    assert cos_sin_fixed(150_000_000)[1] == 2**127
    assert cos_sin_fixed(240_000_000)[0] == -(2**127)
    assert cos_sin_fixed(330_000_000)[1] == -(2**127)
    # sin 45° · 2**128 = √(2**255), rounded half to even: exact integer reference.
    root = math.isqrt(2**255)
    assert cos_sin_fixed(45_000_000)[0] == (root + 1 if 2**255 > root * root + root else root)


def test_table_context_has_no_effect() -> None:
    saved = decimal.getcontext().copy()
    try:
        decimal.getcontext().prec = 5
        decimal.getcontext().rounding = decimal.ROUND_FLOOR
        transform_module._table.cache_clear()  # pyright: ignore[reportPrivateUsage]
        transform_module._pi.cache_clear()  # pyright: ignore[reportPrivateUsage]
        for udeg, expected in GOLDEN.items():
            assert cos_sin_fixed(udeg) == expected, udeg
        assert decimal.getcontext().prec == 5
    finally:
        decimal.setcontext(saved)


def test_table_type_error() -> None:
    with pytest.raises(TypeError, match="udeg"):
        cos_sin_fixed(1.5)  # type: ignore[arg-type]


def test_module_uses_no_float_trigonometry() -> None:
    source = Path(transform_module.__file__).read_text(encoding="utf-8")
    for name in ("math.sin", "math.cos", "math.tan", "math.radians", "from math import"):
        assert name not in source


# --- rotate_point ---------------------------------------------------------------------------------


def test_rotate_quarter_turn() -> None:
    assert rotate_point(P(1000, 0), 90_000_000) == P(0, -1000)


def test_rotate_ties_round_half_to_even() -> None:
    assert rotate_point(P(0, 3), 30_000_000) == P(2, 3)
    assert rotate_point(P(1, 0), 60_000_000) == P(0, -1)


def test_rotate_type_errors() -> None:
    with pytest.raises(TypeError, match="udeg"):
        rotate_point(P(1, 0), 90.0)  # type: ignore[arg-type]
    with pytest.raises(TypeError, match=r"\bp\b"):
        rotate_point(P(1.0, 0), 90)  # type: ignore[arg-type]


def _reference(p: Point, udeg: int) -> Point:
    """80-digit decimal rotation rounded half to even (independent of the module's table)."""
    with decimal.localcontext(decimal.Context(prec=80)):

        def atan_inv(n: int) -> decimal.Decimal:
            x = decimal.Decimal(1) / n
            x2, term, total, k = x * x, x, x, 1
            while True:
                term *= -x2
                step = term / (2 * k + 1)
                if total + step == total:
                    return total
                total += step
                k += 1

        pi = 16 * atan_inv(5) - 4 * atan_inv(239)
        theta = decimal.Decimal(udeg % FULL_TURN) * pi / 180_000_000
        c, s = decimal.Decimal(0), decimal.Decimal(0)
        tc, ts, i = decimal.Decimal(1), theta, 0
        while True:
            nc, ns = c + tc, s + ts
            if nc == c and ns == s:
                break
            c, s, i = nc, ns, i + 1
            tc = -tc * theta * theta / ((2 * i - 1) * (2 * i))
            ts = -ts * theta * theta / ((2 * i) * (2 * i + 1))
        x = p.x * c + p.y * s
        y = -p.x * s + p.y * c
        return P(
            int(x.to_integral_value(rounding=decimal.ROUND_HALF_EVEN)),
            int(y.to_integral_value(rounding=decimal.ROUND_HALF_EVEN)),
        )


@settings(max_examples=150, deadline=None)
@given(st.integers(-LIMIT, LIMIT), st.integers(-LIMIT, LIMIT), st.integers(-FULL_TURN, 2 * FULL_TURN))
def test_agreement_with_a_high_precision_reference(x: int, y: int, udeg: int) -> None:
    assert rotate_point(P(x, y), udeg) == _reference(P(x, y), udeg)


@given(st.integers(-LIMIT, LIMIT), st.integers(-LIMIT, LIMIT))
def test_four_quarter_turns_are_the_identity(x: int, y: int) -> None:
    p = P(x, y)
    q = p
    for _ in range(4):
        q = rotate_point(q, 90_000_000)
    assert q == p


# --- Transform ------------------------------------------------------------------------------------


def test_footprint_placement() -> None:
    assert Transform.placement(P(1000, 2000), 90_000_000).apply(P(0, 100)) == P(1100, 2000)


def test_mirror_first() -> None:
    assert Transform.placement(P(0, 0), 0, mirror=True).apply(P(5, 7)) == P(5, -7)
    assert Transform.mirror_x_axis().apply(P(5, 7)) == P(5, -7)


def test_relative_to_absolute_angle() -> None:
    assert Transform.placement(P(0, 0), 90_000_000, mirror=True).apply_angle(30_000_000) == 60_000_000
    assert Transform.placement(P(0, 0), 90_000_000).apply_angle(300_000_000) == 30_000_000


def test_angle_normalisation() -> None:
    assert Transform.rotation(-90_000_000).rot_udeg == 270_000_000


def test_composition_adds_angles() -> None:
    assert Transform.rotation(30_000_000).compose(Transform.rotation(60_000_000)) == Transform.rotation(
        90_000_000
    )
    mirrored = Transform.mirror_x_axis().compose(Transform.rotation(30_000_000))
    assert mirrored == Transform(330_000_000, True)


def test_translation_properties() -> None:
    t = Transform.placement(P(1000, -2000), 30_000_000)
    assert (t.dx, t.dy) == (Fraction(1000), Fraction(-2000))
    assert t.apply(P(0, 0)) == P(1000, -2000)
    assert Transform.translation(3, 4).apply(P(1, 1)) == P(4, 5)
    assert Transform.identity().apply(P(7, -9)) == P(7, -9)


def test_exact_inverse_for_quarter_turns() -> None:
    t = Transform.placement(P(1000, 2000), 90_000_000)
    assert t.inverse().apply(P(1100, 2000)) == P(0, 100)
    for rot in (0, 90_000_000, 180_000_000, 270_000_000):
        for mirror in (False, True):
            t = Transform.placement(P(123, -456), rot, mirror)
            assert t.inverse().compose(t) == Transform.identity()
            assert t.compose(t.inverse()) == Transform.identity()


@settings(max_examples=200)
@given(
    st.integers(-(2**30), 2**30),
    st.integers(-(2**30), 2**30),
    st.integers(0, FULL_TURN - 1).filter(lambda a: a % 90_000_000 != 0),
    st.booleans(),
    st.integers(-(2**30), 2**30),
    st.integers(-(2**30), 2**30),
)
def test_inverse_round_trip_at_other_angles(tx: int, ty: int, rot: int, mirror: bool, x: int, y: int) -> None:
    t = Transform.placement(P(tx, ty), rot, mirror)
    back = t.inverse().apply(t.apply(P(x, y)))
    assert abs(back.x - x) <= 1 and abs(back.y - y) <= 1


@given(transforms, transforms, st.integers(-(10**8), 10**8), st.integers(-(10**8), 10**8))
@example(Transform.rotation(315_000_000), Transform.rotation(30_000_000), 0, 1_386_483)  # 1.2061 nm off
def test_composition_rounds_once(a: Transform, b: Transform, x: int, y: int) -> None:
    """One rounding or two, per axis, against the exact composed map ``A(B(p))``.

    ``compose(a, b).apply(p)`` rounds once: within 0.5 nm (+2**-100).
    ``a.apply(b.apply(p))`` rounds twice: the first error (up to 0.5 nm per axis) passes through the
    linear part of ``a`` before the second rounding, so one coordinate is off by at most
    ``(1 + |cos θa| + |sin θa|) / 2`` nm, which is at most ``(1 + √2) / 2 ≈ 1.2071`` nm, not 1 nm.
    """
    composed = a.compose(b).apply(P(x, y))
    exact = _exact_apply(a, _exact_apply(b, (Fraction(x), Fraction(y))))
    eps = Fraction(1, 2**100)
    assert abs(composed.x - exact[0]) <= Fraction(1, 2) + eps
    assert abs(composed.y - exact[1]) <= Fraction(1, 2) + eps
    bound = _two_rounding_bound(a)
    error = _two_apply_error(a, b, P(x, y))
    assert error[0] <= bound and error[1] <= bound
    # bound ≤ (1 + √2) / 2 for the fixed-point table too: (|c| + |s|)² ≤ 2, in integers.
    c, s = cos_sin_fixed(a.rot_udeg)
    assert (abs(c) + abs(s)) ** 2 <= 2 * ONE * ONE


def _two_rounding_bound(a: Transform) -> Fraction:
    """``(1 + |cos θa| + |sin θa|) / 2`` nm with the fixed-point values ``a`` uses (exact)."""
    c, s = cos_sin_fixed(a.rot_udeg)
    return Fraction(ONE + abs(c) + abs(s), 2 * ONE)


def _two_apply_error(a: Transform, b: Transform, p: Point) -> tuple[Fraction, Fraction]:
    """Per-axis distance between ``a.apply(b.apply(p))`` and the exact composed map."""
    exact = _exact_apply(a, _exact_apply(b, (Fraction(p.x), Fraction(p.y))))
    twice = a.apply(b.apply(p))
    return abs(twice.x - exact[0]), abs(twice.y - exact[1])


def test_diagonal_table_entries_stay_below_sqrt2() -> None:
    # |cos θ| + |sin θ| is largest on the diagonals; the rounded table stays below √2 there.
    for udeg in (45_000_000, 135_000_000, 225_000_000, 315_000_000):
        c, s = cos_sin_fixed(udeg)
        assert abs(c) == abs(s)
        assert (abs(c) + abs(s)) ** 2 < 2 * ONE * ONE
        assert (abs(c) + abs(s) + 1) ** 2 > 2 * ONE * ONE  # and within 2**-128 of it


def test_two_applies_reach_the_bound() -> None:
    # Both roundings are ties that go the same way: the bound is reached exactly.
    b = Transform(0, False, ONE // 2, ONE // 2)  # +0.5 nm on each axis
    assert b.apply(P(1, 1)) == P(2, 2)  # (1.5, 1.5) rounds half to even: first error (+0.5, +0.5)
    c, s = cos_sin_fixed(45_000_000)
    a = Transform(45_000_000, False, 3 * ONE + ONE // 2 - 2 * (c + s), 0)  # A((2, 2)).x == 3.5
    assert a.apply(P(2, 2)).x == 4  # 3.5 rounds half to even: second error +0.5
    error = _two_apply_error(a, b, P(1, 1))
    assert error[0] == _two_rounding_bound(a) == Fraction(1, 2) + Fraction(c + s, 2 * ONE)
    assert error[0] > Fraction(12071067811865475, 10**16)  # (1 + √2) / 2 = 1.20710678118654752…

    # Integer translations only: still well above the 1 nm that was claimed before.
    a, b = Transform.rotation(315_000_000), Transform.rotation(30_000_000)
    error = _two_apply_error(a, b, P(0, 1_386_483))
    assert Fraction(1206, 1000) < max(error) <= _two_rounding_bound(a)


def _exact_apply(t: Transform, p: tuple[Fraction, Fraction]) -> tuple[Fraction, Fraction]:
    c, s = (Fraction(v, ONE) for v in cos_sin_fixed(t.rot_udeg))
    x, y = p[0], (-p[1] if t.mirror else p[1])
    return x * c + y * s + t.dx, -x * s + y * c + t.dy


@settings(max_examples=100)
@given(st.integers(-1000, 1000), st.integers(-1000, 1000), st.sampled_from([0, 90, 180, 270]), st.booleans(),
       st.sampled_from([0, 90, 180, 270]), st.booleans())  # fmt: skip
def test_quarter_turn_compositions_are_exact(dx: int, dy: int, r1: int, m1: bool, r2: int, m2: bool) -> None:
    a = Transform.placement(P(dx, dy), r1 * 1_000_000, m1)
    b = Transform.placement(P(dy, dx), r2 * 1_000_000, m2)
    composed = a.compose(b)
    assert composed.dx.denominator == 1 and composed.dy.denominator == 1
    for p in (P(0, 0), P(17, -5), P(-1000, 999)):
        assert composed.apply(p) == a.apply(b.apply(p))


def test_mirror_reverses_orientation() -> None:
    square = Polygon((P(0, 0), P(10, 0), P(10, 10), P(0, 10)))
    assert square.area2 == 200
    mirrored = Transform.placement(P(0, 0), 0, mirror=True).apply_polygon(square)
    assert mirrored.area2 == -200
    assert mirrored.normalize() == Polygon((P(0, -10), P(10, -10), P(10, 0), P(0, 0)))


def test_degenerate_after_rounding() -> None:
    rot = Transform.rotation(30_000_000)
    with pytest.raises(GeometryError) as info:
        rot.apply_arc(Arc(P(0, 0), P(1, 0), P(1, 1)))
    assert info.value.code == "geometry.degenerate"
    with pytest.raises(GeometryError) as info:
        rot.apply_polygon(Polygon((P(0, 0), P(0, 1), P(-1, 1))))
    assert info.value.code == "geometry.degenerate"


def test_apply_segment_and_bbox() -> None:
    t = Transform.placement(P(100, 100), 90_000_000)
    assert t.apply_segment(Segment(P(0, 0), P(10, 0))) == Segment(P(100, 100), P(100, 90))
    assert t.apply_bbox(BBox(0, 0, 10, 20)) == BBox(100, 90, 120, 100)
    tilted = Transform.rotation(45_000_000).apply_bbox(BBox(0, 0, 10, 10))
    # corners rotate to (0,0), (7.07,−7.07), (14.14,0), (7.07,7.07): rounded outward
    assert tilted == BBox(0, -8, 15, 8)


@given(transforms, st.integers(-(10**6), 10**6), st.integers(-(10**6), 10**6), st.integers(0, 10**6))
def test_apply_bbox_contains_images(t: Transform, x: int, y: int, size: int) -> None:
    box = BBox(x, y, x + size, y + size)
    image = t.apply_bbox(box)
    for corner in (P(box.x0, box.y0), P(box.x1, box.y0), P(box.x1, box.y1), P(box.x0, box.y1)):
        exact = _exact_apply(t, (Fraction(corner.x), Fraction(corner.y)))
        assert image.x0 <= exact[0] <= image.x1 and image.y0 <= exact[1] <= image.y1


def test_round_half_even_used() -> None:
    assert round_half_even_div(ONE // 2, ONE) == 0
