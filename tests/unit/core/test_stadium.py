# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The stadium of a slot and the fixed-point trigonometry it uses (capability design-model, "Board slots";
change c0167)."""

from __future__ import annotations

from fractions import Fraction

import pytest

from fenolite.core.coords import Point
from fenolite.core.stadium import check_size, stadium
from fenolite.core.trig import FULL_TURN, ONE, angle_of, cos_sin_fixed
from fenolite.geometry import transform

MM = 1_000_000


def test_the_stadium_of_a_turned_slot() -> None:
    ring = stadium(Point(0, 0), 12 * MM, 2 * MM, 90_000_000)
    assert ring.points == (
        Point(-MM, 5 * MM),
        Point(-MM, -5 * MM),
        Point(MM, -5 * MM),
        Point(MM, 5 * MM),
    )
    assert set(ring.mids) == {Point(0, 6 * MM), Point(0, -6 * MM)}
    assert all(abs(p.x) == MM for p in ring.points)  # 1 mm from the axis x = 0


def test_a_horizontal_slot_is_the_ring_of_shape_slot() -> None:
    ring = stadium(Point(115 * MM, 110 * MM), 12 * MM, 2 * MM, 0)
    assert ring.points == (
        Point(110 * MM, 109 * MM),
        Point(120 * MM, 109 * MM),
        Point(120 * MM, 111 * MM),
        Point(110 * MM, 111 * MM),
    )
    assert ring.mids == (Point(121 * MM, 110 * MM), Point(109 * MM, 110 * MM))
    assert ring.arcs() == ((1, Point(121 * MM, 110 * MM)), (3, Point(109 * MM, 110 * MM)))


def _axis_distance2(p: Point, centre: Point, udeg: int) -> Fraction:
    c, s = cos_sin_fixed(udeg)
    # the distance of p from the axis through centre along (c, −s): the component along n = (s, c)
    along = Fraction((p.x - centre.x) * s + (p.y - centre.y) * c, ONE)
    return along * along


@pytest.mark.parametrize("udeg", [30_000_000, 45_000_000, 123_456_789, 179_999_999])
def test_every_vertex_lies_half_the_width_from_the_axis(udeg: int) -> None:
    centre = Point(15 * MM, 10 * MM)
    ring = stadium(centre, 12 * MM, 2 * MM, udeg)
    for p in ring.points:
        assert abs(_axis_distance2(p, centre, udeg) - MM * MM) <= 2 * MM + 2  # within 1 nm
    # the mids lie on the axis, half the length from the centre
    for mid in ring.mids:
        assert _axis_distance2(mid, centre, udeg) <= 1
        assert abs((mid.x - centre.x) ** 2 + (mid.y - centre.y) ** 2 - (6 * MM) ** 2) <= 12 * MM + 2


def test_rotation_is_taken_modulo_a_half_turn() -> None:
    a = stadium(Point(0, 0), 12 * MM, 2 * MM, 30_000_000)
    b = stadium(Point(0, 0), 12 * MM, 2 * MM, 210_000_000)
    assert a == b


@pytest.mark.parametrize(
    ("length", "width"), [(2 * MM, 2 * MM), (MM, 2 * MM), (4 * MM, 3), (4 * MM, 0), (4 * MM, -2)]
)
def test_refused_sizes(length: int, width: int) -> None:
    assert check_size(length, width) is not None
    with pytest.raises(ValueError):
        stadium(Point(0, 0), length, width, 0)


def test_the_table_moved_without_a_change() -> None:
    assert transform.cos_sin_fixed is cos_sin_fixed
    assert cos_sin_fixed(30_000_000)[1] == ONE // 2
    assert cos_sin_fixed(90_000_000) == (0, ONE)


@pytest.mark.parametrize(
    "udeg", [0, 1, 30_000_000, 89_999_999, 90_000_000, 135_000_000, 180_000_000, 271_234_567, 359_999_999]
)
def test_angle_of_inverts_the_table(udeg: int) -> None:
    c, s = cos_sin_fixed(udeg)
    # a direction of 1 m along the unit vector (cos θ, −sin θ), rounded to the nanometre
    dx, dy = (c * 10**9) >> 128, (-s * 10**9) >> 128
    found = angle_of(dx, dy)
    assert min((found - udeg) % FULL_TURN, (udeg - found) % FULL_TURN) <= 1


def test_angle_of_axes_is_exact() -> None:
    assert angle_of(5, 0) == 0
    assert angle_of(0, -5) == 90_000_000
    assert angle_of(-5, 0) == 180_000_000
    assert angle_of(0, 5) == 270_000_000
    with pytest.raises(ValueError):
        angle_of(0, 0)
