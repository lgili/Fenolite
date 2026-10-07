# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The clear area of assembly features (capability design-dsl, "Fiducials in the DSL"; change c0118).

Only the outline is tested here: ``Design.fiducial``, ``Design.test_point`` and ``Design.tooling_hole``
need the generated definitions and the keep-out call of changes c0102 and c0103, which are not on this
base."""

from __future__ import annotations

from fractions import Fraction

import pytest
from hypothesis import given
from hypothesis import strategies as st

from fenolite.core.coords import Point
from fenolite.dsl import Design
from fenolite.dsl.assembly import ASSEMBLY_LIBRARY, clear_outline
from fenolite.exports.testpoints import TOOLING_PREFIX

MM = 1_000_000


def _contains_the_circle(outline: tuple[Point, ...], centre: Point, diameter: int) -> None:
    """Every vertex is outside the circle or on it, and every edge is at a distance of at least
    ``diameter / 2`` from the centre, computed exactly."""
    radius_squared = Fraction(diameter, 2) ** 2
    for a, b in zip(outline, (*outline[1:], outline[0]), strict=True):
        assert Fraction((a.x - centre.x) ** 2 + (a.y - centre.y) ** 2) >= radius_squared
        dx, dy = b.x - a.x, b.y - a.y
        if dx == dy == 0:
            continue  # a diameter of 1 or 2 nm folds two vertices into one
        cross = dx * (centre.y - a.y) - dy * (centre.x - a.x)
        assert Fraction(cross * cross, dx * dx + dy * dy) >= radius_squared
        # the closest point of the edge's line lies on the edge: the octagon is convex around the centre
        along = dx * (centre.x - a.x) + dy * (centre.y - a.y)
        assert 0 <= along <= dx * dx + dy * dy


@given(
    diameter=st.integers(1, 10 * MM),
    x=st.integers(-(10**9), 10**9),
    y=st.integers(-(10**9), 10**9),
)
def test_outline_contains_the_circle(diameter: int, x: int, y: int) -> None:
    outline = clear_outline(x, y, diameter)
    assert len(outline) == 8 and all(type(p.x) is int and type(p.y) is int for p in outline)
    _contains_the_circle(outline, Point(x, y), diameter)


@pytest.mark.parametrize("diameter", [1, 2, 3, 4, 5, 999, MM, 2_200_000, 3_000_001, 10 * MM])
def test_outline_of_small_and_round_diameters(diameter: int) -> None:
    _contains_the_circle(clear_outline(7, -3, diameter), Point(7, -3), diameter)


def test_outline_of_three_millimetres() -> None:
    """Apothem 1.5 mm; the corner offset is ``⌈√2 × 1.5 mm⌉ − 1.5 mm``, rounded up to the nanometre."""
    outline = clear_outline(5 * MM, 5 * MM, 3 * MM)
    a, b = 1_500_000, 621_321
    assert outline[0] == Point(5 * MM + b, 5 * MM - a) and outline[1] == Point(5 * MM + a, 5 * MM - b)
    assert {abs(p.x - 5 * MM) for p in outline} == {a, b} == {abs(p.y - 5 * MM) for p in outline}
    assert (a + b) ** 2 >= 2 * a * a > (a + b - 1) ** 2


def test_outline_is_at_most_about_eight_percent_wider() -> None:
    for diameter in (MM, 3 * MM, 10 * MM):
        outline = clear_outline(0, 0, diameter)
        furthest = max(Fraction(p.x * p.x + p.y * p.y) for p in outline)
        assert furthest <= (Fraction(diameter, 2) * Fraction(1083, 1000)) ** 2


@pytest.mark.parametrize("diameter", [0, -1, 1.5, True, "3mm"])
def test_outline_refuses_other_diameters(diameter: object) -> None:
    with pytest.raises(ValueError, match="diameter"):
        clear_outline(0, 0, diameter)  # type: ignore[arg-type]


def test_library_name() -> None:
    assert ASSEMBLY_LIBRARY == "Fenolite_Assembly"
    assert TOOLING_PREFIX == f"{ASSEMBLY_LIBRARY}:ToolingHole_"


def test_the_script_calls_wait_for_their_prerequisites() -> None:
    """``fiducial()``, ``test_point()`` and ``tooling_hole()`` are built on ``Design.rule_area`` (c0103) and
    on the generated definitions of ``Design.hole`` (c0102). Both prerequisites are on the branch since c0118
    was stacked after them, so tasks 3.2 to 3.6 of change c0118 can be done; this test fails again when the
    three calls land, until it asks for all three."""
    have = [name for name in ("rule_area", "hole") if hasattr(Design, name)]
    calls = [name for name in ("fiducial", "test_point", "tooling_hole") if hasattr(Design, name)]
    assert have == ["rule_area", "hole"]
    assert calls == [] or calls == ["fiducial", "test_point", "tooling_hole"]
