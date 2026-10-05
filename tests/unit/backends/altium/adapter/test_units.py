# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Units and frame of the Altium import (capability altium-import, "Units and frame"; change c0043)."""

from __future__ import annotations

from fractions import Fraction

from fenolite.backends.altium.adapter import units
from fenolite.backends.altium.read.sch import SchLength
from fenolite.core.coords import Point
from fenolite.core.units import u_to_nm
from fenolite.geometry.shapes import Arc

MIL = 10_000


def test_whole_multiples_are_exact() -> None:
    assert units.pcb_point(100_000, 50) == Point(254_000, -127)
    assert SchLength(100_000).nm() == 254_000
    assert units.exact_length(100_000) and units.exact_length(50) and not units.exact_length(25)


def test_ties_round_to_even() -> None:
    assert [u_to_nm(u) for u in (25, 75, -25)] == [64, 190, -64]
    assert [units.pcb_length(u) for u in (25, 75, -25)] == [64, 190, -64]


def test_angle_of_a_quarter_turn() -> None:
    assert units.angle(90.0) == (90_000_000, True)
    assert units.angle(-90.0) == (270_000_000, True)
    assert units.angle(33.3) == (33_300_000, True)
    assert units.angle(1e-7) == (0, False)
    assert units.angle(360.0) == (0, True)
    assert units.angle(float("nan")) == (0, False)


def test_length_text() -> None:
    assert units.text_length("10mil") == (254_000, True)
    assert units.text_length("0.5mil") == (12_700, True)
    assert units.text_length("1.27mm") == (1_270_000, True)
    assert units.text_length(" 19.685mil ") == (499_999, True)
    assert units.text_length("19.6851mil") == (500_002, False)
    assert units.text_length("0.0001mil") == (3, False)  # 2.54 nm
    for bad in ("abc", "10", "10 inch", "", "1e3mil", None):
        assert units.text_length(bad) is None
    assert units.units_length(Fraction(25)) == (64, False)
    assert units.units_length(Fraction(100_000)) == (254_000, True)


def test_arc_points_keep_the_direction_under_the_flip() -> None:
    # A quarter arc of radius 100 mil about (0, 0) from 0 to 90 degrees, counter-clockwise in Altium's frame.
    start, mid, end = units.arc_points(0, 0, 100 * MIL, 0, 90_000_000)
    assert start == Point(2_540_000, 0) and end == Point(0, -2_540_000)
    assert mid == Point(1_796_051, -1_796_051)
    assert Arc(start, mid, end).radius2 is not None
    # The same arc given the other way round runs through the other three quarters.
    start, mid, end = units.arc_points(0, 0, 100 * MIL, 90_000_000, 0)
    assert start == Point(0, -2_540_000) and end == Point(2_540_000, 0)
    assert mid == Point(-1_796_051, 1_796_051)


def test_full_turn_and_circle() -> None:
    assert units.sweep(0, 0) == 360_000_000 and units.sweep(10, 5) == 359_999_995
    centre, edge = units.circle_points(100 * MIL, 50 * MIL, 10 * MIL)
    assert centre == Point(2_540_000, -1_270_000) and edge == Point(2_794_000, -1_270_000)
