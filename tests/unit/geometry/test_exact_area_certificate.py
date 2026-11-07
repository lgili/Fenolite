# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Independent rational-area and nested signed-component certificate controls."""

from dataclasses import replace
from fractions import Fraction as F

import pytest

from fenolite.geometry.boolean import _exact_faces as exact
from fenolite.geometry.boolean._exact_noding import Budget, ExactDeadline, Limits
from fenolite.geometry.errors import GeometryError


def fixture(areas):
    loops = tuple(
        ((F(3 * i), F(0)), (F(3 * i + 1), F(0)), (F(3 * i + 1), a / 2), (F(3 * i), a / 2))
        for i, a in enumerate(areas)
    )
    cycles = []
    dual = {}
    selected = {}
    for i, ring in enumerate(loops):
        for face, points in ((2 * i, ring), (2 * i + 1, tuple(reversed(ring)))):
            cycles.append(tuple(zip(points, points[1:] + points[:1], strict=True)))
            dual[face] = [(face ^ 1, (0, 0))]
            selected[face] = face % 2 == 0
    return exact.Frame({}, {}, cycles, {}, list(range(1, len(cycles), 2)), dual), loops, selected


WIDE = tuple(F(1, (1 << p) - 1) for p in (1013, 1019, 1021, 1031, 1033))


def test_original_global_scalar_red_has_exact_bounded_component_certificate():
    total = F(0)
    with pytest.raises(GeometryError, match="bit budget"):
        for value in WIDE:
            total = exact.checked(total + value, 4096)
    frame, loops, selected = fixture(WIDE)
    exact._area_identity(frame, loops, selected, Budget())


def test_nested_signed_negative_contributions_and_scalar_zero_are_preserved():
    for areas in ((F(100), F(-36), F(4)), (F(1, 3), -F(1, 3))):
        frame, loops, selected = fixture(areas)
        exact._area_identity(frame, loops, selected, Budget())


def test_equal_global_area_cannot_hide_cross_component_mismatch():
    frame, loops, selected = fixture(WIDE)
    altered = list(loops)
    other, _, _ = fixture((WIDE[0] + 1, WIDE[1] - 1))
    frame.cycles[0] = other.cycles[0]
    frame.cycles[2] = other.cycles[2]
    with pytest.raises(GeometryError):
        exact._area_identity(frame, tuple(altered), selected, Budget())


@pytest.mark.parametrize("areas", [tuple(-v for v in WIDE), WIDE + (F(1, 3), -F(1, 3) + F(1, 1 << 100))])
def test_negative_or_unresolved_global_interval_refuses(areas):
    frame, loops, selected = fixture(areas)
    with pytest.raises(GeometryError, match="area"):
        exact._area_identity(frame, loops, selected, Budget())


@pytest.mark.parametrize("field,value", [("winding_visits", 0), ("nodes", 0), ("faces", 0)])
def test_decomposed_certificate_shares_resource_guards(field, value):
    frame, loops, selected = fixture(WIDE)
    with pytest.raises(GeometryError, match="budget"):
        exact._area_identity(frame, loops, selected, Budget(replace(Limits(), **{field: value})))


def test_local_bit_overflow_and_expired_budget_refuse():
    frame, loops, selected = fixture((F(1, 1 << 4097),))
    with pytest.raises(GeometryError, match="bit budget"):
        exact._area_identity(frame, loops, selected, Budget())
    frame, loops, selected = fixture(WIDE)
    now = [0.0]
    budget = Budget(clock=lambda: now[0])
    now[0] = 1201
    with pytest.raises(ExactDeadline, match="deadline"):
        exact._area_identity(frame, loops, selected, budget)


@pytest.mark.parametrize("fault", ["unknown-dual", "shared-point", "missing-point"])
def test_component_ownership_is_closed_and_complete(fault):
    frame, loops, selected = fixture(WIDE)
    if fault == "unknown-dual":
        frame.dual[0].append((len(frame.cycles), (0, 0)))
    elif fault == "shared-point":
        frame.cycles[2] = (frame.cycles[0][0],) + frame.cycles[2][1:]
    else:
        loops = (((F(-100), F(-100)),) + loops[0][1:],) + loops[1:]
    with pytest.raises(GeometryError):
        exact._area_identity(frame, loops, selected, Budget())


def test_scalar_success_does_not_visit_component_graph():
    frame, loops, selected = fixture((F(1, 3), -F(1, 3)))
    frame.dual.clear()
    budget = Budget(replace(Limits(), winding_visits=0))
    exact._area_identity(frame, loops, selected, budget)
    assert budget._visits == 0


@pytest.mark.parametrize(
    "extra,message", [((F(1 << 4080),), "enclosure bit"), ((F(1 << 4063), F(1 << 4063)), "sum bit")]
)
def test_enclosure_product_and_cumulative_integer_limits_remain(extra, message):
    frame, loops, selected = fixture(WIDE + extra)
    with pytest.raises(GeometryError, match=message):
        exact._area_identity(frame, loops, selected, Budget())
