# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Authored exact circular-distance benches for c0282 (no third-party fixture data)."""

from __future__ import annotations

import math
import random
from fractions import Fraction

import pytest

from fenolite.core.coords import Point
from fenolite.geometry import (
    Arc,
    BBox,
    Thick,
    Transform,
    _curved,
    thick_bbox,
    thick_closer_than,
    thick_gap_floor,
    thick_touch,
    thick_witness,
)
from fenolite.geometry._radical import Real


def curve(start: Point, mid: Point, end: Point, width: int = 0) -> Thick:
    arc = Arc(start, mid, end)
    return Thick((start, mid, end), width, arc=arc)


HALF = curve(Point(-10, 0), Point(0, 10), Point(10, 0), 2)


@pytest.mark.parametrize(
    ("expression", "sign"),
    [
        (Real.root(8) - Real.root(2, 2), 0),
        (Real.root(2) + Real.root(8) - Real.root(18), 0),
        (Real.root(3) + Real.root(2) - Real.root(10), -1),
        (Real.root(3) - Real.root(2) - Fraction(3, 10), 1),
        (Real.root(3) - Real.root(2) - Fraction(32, 100), -1),
        (Real.root(Fraction(1, 4)) - Fraction(1, 2), 0),
    ],
)
def test_exact_radical_sign(expression: Real, sign: int) -> None:
    assert expression.sign() == sign
    assert (-expression).sign() == -sign


@pytest.mark.parametrize(
    ("constant", "rounded"), [(Fraction(1, 2), 0), (Fraction(3, 2), 2), (Fraction(-3, 2), -2)]
)
def test_radical_integer_rounding(constant: Fraction, rounded: int) -> None:
    value = Real.root(8) - Real.root(2, 2) + constant
    assert value.rounded() == rounded
    assert (Real.root(2) - 2).floor() == -1


@pytest.mark.parametrize(("y", "gap", "touch"), [(12, 0, True), (13, 1, False), (15, 3, False)])
def test_arc_line_tangent_boundary(y: int, gap: int, touch: bool) -> None:
    line = Thick((Point(-20, y), Point(20, y)), 2)
    assert thick_touch(HALF, line) is touch
    assert thick_gap_floor(HALF, line) == gap
    assert not thick_closer_than(HALF, line, gap)
    assert thick_closer_than(HALF, line, gap + 1)


def test_circle_line_through_centre_and_tangent_crossing() -> None:
    centre_line = Thick((Point(-20, 0), Point(20, 0)), 0)
    tangent = Thick((Point(-1, 10), Point(1, 10)), 0)
    assert thick_touch(HALF, centre_line)
    assert thick_touch(HALF, tangent)
    # The upper quarter's only perpendicular radius is its far side from the line.
    quarter = curve(Point(10, 0), Point(6, 8), Point(0, 10))
    below = Thick((Point(4, -4), Point(6, -4)), 0)
    assert thick_gap_floor(quarter, below) == 5


def test_fractional_centre_and_half_width() -> None:
    arc = curve(Point(0, 0), Point(1, 0), Point(1, 1))
    disc = Thick((Point(3, 3),), 1)
    assert arc.arc is not None and arc.arc.centre == (Fraction(1, 2), Fraction(1, 2))
    assert thick_gap_floor(arc, disc) == 2  # 2√2 - 1/2
    assert not thick_closer_than(arc, disc, 2)
    assert thick_closer_than(arc, disc, 3)
    assert thick_witness(arc, disc) == thick_witness(disc, arc)


def test_true_box_covers_extrema_between_stored_points() -> None:
    arc = curve(Point(-10, 0), Point(6, 8), Point(10, 0), 1)
    assert thick_bbox(arc) == BBox(-11, -1, 11, 11)
    assert thick_touch(arc, Thick((Point(0, 11),), 1))


@pytest.mark.parametrize(
    ("other", "gap", "touch"),
    [
        (curve(Point(-10, 25), Point(0, 15), Point(10, 25), 2), 3, False),
        (curve(Point(-10, 22), Point(0, 12), Point(10, 22), 2), 0, True),
        (curve(Point(-10, 10), Point(0, 0), Point(10, 10), 2), 0, True),
        (curve(Point(-15, 0), Point(0, 15), Point(15, 0), 2), 3, False),
        (curve(Point(-10, 0), Point(0, -10), Point(10, 0), 2), 0, True),
    ],
)
def test_arc_arc_stationary_intersections_and_concentric(other: Thick, gap: int, touch: bool) -> None:
    assert thick_gap_floor(HALF, other) == gap
    assert thick_touch(HALF, other) is touch
    assert thick_closer_than(HALF, other, gap + 1)
    if not touch:
        assert not thick_closer_than(HALF, other, gap)


def test_major_shallow_and_straight_arcs() -> None:
    major = curve(Point(10, 0), Point(-10, 0), Point(0, 10))
    assert thick_touch(major, Thick((Point(0, -11),), 2))
    assert not thick_touch(major, Thick((Point(6, 8),), 1))
    shallow = curve(Point(-1_000_000_000, 1), Point(0, 0), Point(1_000_000_000, 1))
    line = Thick((Point(-10, -5), Point(10, -5)), 0)
    assert thick_gap_floor(shallow, line) == 5
    assert not thick_closer_than(shallow, line, 5)
    straight = curve(Point(0, 0), Point(3, 0), Point(9, 0), 1)
    assert straight.arc is None
    assert thick_gap_floor(straight, Thick((Point(0, 5), Point(9, 5)), 1)) == 4


def test_filled_ring_containment_crossing_and_keyhole() -> None:
    ring = Thick((Point(-20, -20), Point(20, -20), Point(20, 20), Point(-20, 20)), 0, filled=True)
    assert thick_touch(HALF, ring)
    assert thick_gap_floor(HALF, ring) == 0
    small = Thick((Point(-1, 9), Point(1, 9), Point(1, 11), Point(-1, 11)), 0, filled=True)
    assert thick_touch(HALF, small)
    far = Thick((Point(-1, 15), Point(1, 15), Point(1, 20), Point(-1, 20)), 0, filled=True)
    assert thick_gap_floor(HALF, far) == 4
    # Same outer with a clockwise hole and a bridge traversed in both directions.
    hole = Thick(
        (
            Point(-20, -20),
            Point(-20, 0),
            Point(-15, 0),
            Point(-15, -15),
            Point(15, -15),
            Point(15, 15),
            Point(-15, 15),
            Point(-15, 0),
            Point(-20, 0),
            Point(-20, 20),
            Point(20, 20),
            Point(20, -20),
        ),
        0,
        filled=True,
    )
    assert not thick_touch(HALF, hole)
    assert thick_gap_floor(HALF, hole) == 4


def mapped(shape: Thick, transform: Transform, *, reverse: bool = False) -> Thick:
    core = tuple(transform.apply(p) for p in shape.core)
    if reverse:
        core = tuple(reversed(core))
    arc = Arc(*core) if shape.arc is not None else None
    return Thick(core, shape.width, shape.filled, arc)


@pytest.mark.parametrize("angle", [0, 90_000_000, 180_000_000, 270_000_000])
@pytest.mark.parametrize("mirror", [False, True])
def test_reversal_rotation_reflection_invariance(angle: int, mirror: bool) -> None:
    transform = Transform.placement(Point(31, -27), angle, mirror)
    other = curve(Point(-10, 25), Point(0, 15), Point(10, 25), 1)
    a, b = mapped(HALF, transform, reverse=True), mapped(other, transform)
    assert thick_touch(a, b) == thick_touch(b, a) == thick_touch(HALF, other)
    assert thick_gap_floor(a, b) == thick_gap_floor(b, a) == thick_gap_floor(HALF, other)
    for limit in (3, 4, 5):
        assert thick_closer_than(a, b, limit) == thick_closer_than(HALF, other, limit)
    assert thick_witness(a, b) == thick_witness(b, a)


def sampled_point_line_distance(x: float, y: float, start: Point, end: Point) -> float:
    dx, dy = end.x - start.x, end.y - start.y
    t = max(0, min(1, ((x - start.x) * dx + (y - start.y) * dy) / (dx * dx + dy * dy)))
    return math.hypot(x - start.x - t * dx, y - start.y - t * dy)


def test_independent_sampled_arc_line_distances() -> None:
    """An independent dense parameter sampling brackets each exact decision away from boundaries."""
    randomizer = random.Random(282)
    arc = curve(Point(1000, 0), Point(-1000, 0), Point(0, 1000))  # major clockwise arc
    samples = [
        (1000 * math.cos(-k * 1.5 * math.pi / 4096), 1000 * math.sin(-k * 1.5 * math.pi / 4096))
        for k in range(4097)
    ]
    for _ in range(30):
        start = Point(randomizer.randrange(-2000, 2000), randomizer.randrange(-2000, 2000))
        end = Point(randomizer.randrange(-2000, 2000), randomizer.randrange(-2000, 2000))
        sampled = min(sampled_point_line_distance(x, y, start, end) for x, y in samples)
        line = Thick((start, end), 0)
        floor = thick_gap_floor(arc, line)
        assert floor <= sampled < floor + 2
        assert thick_closer_than(arc, line, math.ceil(sampled) + 1)
        if sampled >= 2:
            assert not thick_closer_than(arc, line, max(0, math.floor(sampled) - 1))


def test_invalid_arc_core() -> None:
    assert HALF.arc is not None
    with pytest.raises(ValueError, match="three stored"):
        Thick((HALF.arc.start, HALF.arc.end), 2, arc=HALF.arc)
    with pytest.raises(ValueError, match="filled=False"):
        Thick(HALF.core, 2, filled=True, arc=HALF.arc)


def test_large_straight_core_keeps_its_piece_index(monkeypatch: pytest.MonkeyPatch) -> None:
    calls = []
    original = _curved._arc_segment

    def counted(arc, start, end):  # noqa: ANN001, ANN202
        calls.append((start, end))
        yield from original(arc, start, end)

    monkeypatch.setattr(_curved, "_arc_segment", counted)
    line = Thick(tuple(Point(x, 20) for x in range(-1000, 1001, 10)), 0)
    assert thick_gap_floor(HALF, line) == 9
    assert 0 < len(calls) < 20  # nearby pieces only, rather than the 200-piece polyline
    assert thick_witness(HALF, line) == Point(0, 15)


def test_independent_sampled_arc_arc_distances() -> None:
    geometry = pytest.importorskip("shapely.geometry")
    rng = random.Random(28201)
    directions = (
        (5, 0),
        (4, 3),
        (3, 4),
        (0, 5),
        (-3, 4),
        (-4, 3),
        (-5, 0),
        (-4, -3),
        (-3, -4),
        (0, -5),
        (3, -4),
        (4, -3),
    )
    nonzero = 0
    for _ in range(30):
        shapes, sampled = [], []
        for _ in range(2):
            cx, cy, scale = rng.randrange(-5000, 5000), rng.randrange(-5000, 5000), rng.randrange(10, 400)
            chosen = rng.sample(directions, 3)
            points = tuple(Point(cx + x * scale, cy + y * scale) for x, y in chosen)
            shape = curve(*points)
            start, mid, end = (math.atan2(y, x) for x, y in chosen)
            sweep = (end - start) % math.tau
            if (mid - start) % math.tau > sweep:
                sweep -= math.tau
            sampled.append(
                geometry.LineString(
                    (
                        cx + 5 * scale * math.cos(start + sweep * k / 8192),
                        cy + 5 * scale * math.sin(start + sweep * k / 8192),
                    )
                    for k in range(8193)
                )
            )
            shapes.append(shape)
        distance = sampled[0].distance(sampled[1])
        floor = thick_gap_floor(*shapes)
        assert floor - 0.001 <= distance < floor + 1.001
        assert thick_gap_floor(*reversed(shapes)) == floor
        if floor:
            nonzero += 1
    assert nonzero >= 15
