# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Escape kinds, pitches and requests (capability routing, "Escape requests for routing"; change c0110).

The pad centres are written here for these tests: an 11 × 11 grid of 0.8 mm, a QFN-48 of 0.5 mm with a
centre pad, and a 2 × 20 header of 1.27 mm, each placed at 0°, 45° and 90°.
"""

from __future__ import annotations

import math

import pytest

from fenolite.core.coords import Point
from fenolite.routing.escape import PartPad, escape_kind, parse, pitch, requests

MM = 1_000_000
ANGLES = (0, 45, 90)
ORIGIN = Point(30 * MM, 20 * MM)


def turned(points: list[Point], degrees: int, origin: Point = ORIGIN) -> list[Point]:
    """``points`` turned by ``degrees`` about the part's centre, then moved to ``origin``, rounded to 1 nm."""
    cos, sin = math.cos(math.radians(degrees)), math.sin(math.radians(degrees))
    return [
        Point(origin.x + round(p.x * cos - p.y * sin), origin.y + round(p.x * sin + p.y * cos))
        for p in points
    ]


def bga() -> list[Point]:
    step = 800_000
    return [Point((col - 5) * step, (row - 5) * step) for row in range(11) for col in range(11)]


def qfn() -> list[Point]:
    """12 pads per side, 0.5 mm apart, on a 7 mm body, and the exposed centre pad."""
    step, offset, edge = 500_000, -2_750_000, 3_400_000
    side = [offset + index * step for index in range(12)]
    points = [Point(x, edge) for x in side] + [Point(x, -edge) for x in side]
    points += [Point(edge, y) for y in side] + [Point(-edge, y) for y in side]
    return [*points, Point(0, 0)]


def header() -> list[Point]:
    step = 1_270_000
    return [Point(col * step, row * step) for row in range(2) for col in range(20)]


@pytest.mark.parametrize("degrees", ANGLES)
def test_kind_of_a_bga_and_a_qfn(degrees: int) -> None:
    """Scenario "A BGA and a QFN"."""
    grid = turned(bga(), degrees)
    perimeter = turned(qfn(), degrees)
    assert escape_kind(grid) == "grid"
    assert abs(pitch(grid) - 800_000) <= 1
    assert escape_kind(perimeter) == "perimeter"
    assert abs(pitch(perimeter) - 500_000) <= 1


@pytest.mark.parametrize("degrees", ANGLES)
def test_kind_of_a_two_row_header(degrees: int) -> None:
    """Two rows have neighbours across one way only: not a grid."""
    points = turned(header(), degrees)
    assert escape_kind(points) == "perimeter"
    assert abs(pitch(points) - 1_270_000) <= 1


def test_exact_pitch_at_zero_degrees() -> None:
    assert pitch(bga()) == 800_000 and pitch(qfn()) == 500_000
    assert pitch([Point(0, 0)]) == 0 and escape_kind([]) == "perimeter"


def _parts() -> dict[str, list[PartPad]]:
    qfn_pads = [PartPad(point, "Q01" if index == 0 else "Q02" if index == 1 else "") for index, point in
                enumerate(turned(qfn(), 0))]  # fmt: skip
    bga_pads = [PartPad(point, "B_X") for point in turned(bga(), 0, Point(60 * MM, 20 * MM))]
    return {"U1": qfn_pads, "U2": bga_pads}


def test_patterns() -> None:
    """Scenario "Patterns"."""
    found, issues = requests(_parts(), ("U1", "U2", "J9=grid"), ("Q01", "Q02", "SDA"))
    assert [(item.ref, item.kind, item.pitch, item.nets) for item in found] == [
        ("U1", "perimeter", 500_000, ("Q01", "Q02"))
    ]
    assert [issue.code for issue in issues] == ["route.escape-skipped"] * 2
    assert {issue.where for issue in issues} == {"U2", "J9=grid"}
    assert all(issue.severity == "warning" for issue in issues)


def test_suffix_overrides_the_kind_and_globs_follow_reference_order() -> None:
    found, issues = requests(_parts(), ("U*=grid",), ("Q01", "B_X"))
    assert [(item.ref, item.kind) for item in found] == [("U1", "grid"), ("U2", "grid")]
    assert issues == ()
    assert requests(_parts(), ("U*=grid",), ("Q01", "B_X")) == (found, issues)


def test_unknown_suffix_raises() -> None:
    with pytest.raises(ValueError, match="ring"):
        requests(_parts(), ("U1=ring",), ("Q01",))
    assert parse("U1") == ("U1", None) and parse("U1=perimeter") == ("U1", "perimeter")


def test_through_hole_pads_are_not_escaped() -> None:
    parts = {"J1": [PartPad(point, "S", drill=1_000_000) for point in header()]}
    found, issues = requests(parts, ("J1",), ("S",))
    assert found == () and [issue.where for issue in issues] == ["J1"]
