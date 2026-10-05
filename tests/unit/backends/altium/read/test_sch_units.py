# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Exact lengths, colours and angles (capability altium-schematic-reader, "Lengths and fractions")."""

from __future__ import annotations

from fractions import Fraction

from _altium_sch_build import SHEET, schdoc

from fenolite.backends.altium.read import sch
from fenolite.backends.altium.read.sch.units import FRAC_PER_UNIT, UNIT_NM, Color, SchLength, parse_udeg


def _record(text: bytes) -> sch.SchRecord:
    return sch.read_schematic(schdoc([SHEET, text])).records[1]


def test_whole_units() -> None:
    label = _record(b"|RECORD=4|LOCATION.X=115|LOCATION.Y=76")
    assert isinstance(label, sch.Label)
    x, y = label.location
    assert (x, y) == (SchLength(11_500_000), SchLength(7_600_000))
    assert (x.nm(), y.nm()) == (29_210_000, 19_304_000)
    assert x.exact and y.exact
    assert UNIT_NM == 254_000 and FRAC_PER_UNIT == 100_000


def test_half_a_unit() -> None:
    label = _record(b"|RECORD=4|LOCATION.X=12|LOCATION.X_FRAC=50000")
    assert isinstance(label, sch.Label)
    x = label.location[0]
    assert x.value == 1_250_000
    assert x.mils() == Fraction(125)
    assert x.nm() == 3_175_000
    assert x.exact


def test_a_fraction_that_is_not_a_whole_nanometre() -> None:
    label = _record(b"|RECORD=4|LOCATION.X=12|LOCATION.X_FRAC=1")
    assert isinstance(label, sch.Label)
    x = label.location[0]
    assert x.nm() == 3_048_003
    assert x.exact is False


def test_negative_coordinate() -> None:
    label = _record(b"|RECORD=4|LOCATION.X=-3|LOCATION.X_FRAC=-50000")
    assert isinstance(label, sch.Label)
    x = label.location[0]
    assert x.value == -350_000
    assert (x.units, x.frac) == (-4, 50_000)


def test_rounding_half_to_even() -> None:
    assert SchLength(25).nm() == 64  # 63.5 → 64 (even)
    assert SchLength(75).nm() == 190  # 190.5 → 190 (even)
    assert SchLength(-25).nm() == -64
    assert isinstance(SchLength(3).nm(), int)


def test_sheet_entry_distance() -> None:
    entry = _record(b"|RECORD=16|OWNERINDEX=0|DISTANCEFROMTOP=4|DISTANCEFROMTOP_FRAC1=500000")
    assert isinstance(entry, sch.SheetEntry)
    assert entry.distance.value == 4_500_000
    assert entry.distance.units == 45


def test_polyline_points_use_their_fractions() -> None:
    line = _record(b"|RECORD=6|LOCATIONCOUNT=2|X1=1|X1_FRAC=5|Y1=2|X2=3|Y2=4|Y2_FRAC=-7")
    assert isinstance(line, sch.Polyline)
    assert line.points == (
        (SchLength(100_005), SchLength(200_000)),
        (SchLength(300_000), SchLength(399_993)),
    )


def test_points_left_out_are_at_zero() -> None:
    line = _record(b"|RECORD=6|LOCATIONCOUNT=3|X2=5|Y3=7")
    assert isinstance(line, sch.Polyline)
    assert line.points == (
        (SchLength(0), SchLength(0)),
        (SchLength(500_000), SchLength(0)),
        (SchLength(0), SchLength(700_000)),
    )


def test_angle_without_a_float() -> None:
    arc = _record(b"|RECORD=12|STARTANGLE=45.500|ENDANGLE=270")
    assert isinstance(arc, sch.Arc)
    assert arc.start_angle == 45_500_000 and isinstance(arc.start_angle, int)
    assert arc.end_angle == 270_000_000 and isinstance(arc.end_angle, int)


def test_parse_udeg() -> None:
    assert parse_udeg("-0.000001") == -1
    assert parse_udeg("0.0000005") == 0
    assert parse_udeg("0.0000015") == 2
    assert parse_udeg(".5") == 500_000
    assert parse_udeg("x") is None
    assert parse_udeg("") is None


def test_colour() -> None:
    assert Color.of(8388608) == Color(0, 0, 128)
    assert Color.of(128) == Color(128, 0, 0)
    assert Color.of(0x123456) == Color(0x56, 0x34, 0x12)
