# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Exact retained-piece predicate versus mandatory exact whole-loss values."""

from fractions import Fraction as F

import pytest

from fenolite.geometry.boolean import _exact_realization as realization
from fenolite.geometry.boolean._exact_noding import Budget
from fenolite.geometry.errors import GeometryError

WIDE = tuple(F(1, (1 << p) - 1) for p in (1013, 1019, 1021, 1031, 1033))


def test_retained_piece_sign_avoids_only_the_global_denominator():
    with pytest.raises(GeometryError, match="bit budget"):
        realization.sum_areas(WIDE, Budget())
    assert realization._piece_exact_area(WIDE, True, Budget()) is None


@pytest.mark.parametrize("eligible", [False])
def test_whole_loss_never_gets_a_surrogate_area(eligible):
    with pytest.raises(GeometryError, match="whole-piece exact area"):
        realization._piece_exact_area(WIDE, eligible, Budget())


@pytest.mark.parametrize("values", [tuple(-a for a in WIDE), WIDE + (F(1, 3), -F(1, 3) + F(1, 1 << 100))])
def test_negative_or_ambiguous_sign_refuses(values):
    with pytest.raises(GeometryError, match="nonnegative"):
        realization._piece_exact_area(values, True, Budget())


def test_scalar_zero_and_loss_value_are_the_original_exact_fractions():
    assert realization._piece_exact_area((F(1, 3), -F(1, 3)), False, Budget()) == 0
    assert realization._piece_exact_area((F(1, 3), F(2, 7)), False, Budget()) == F(13, 21)


@pytest.mark.parametrize(
    "values,message",
    [
        (WIDE + (F(1 << 4080),), "product bit"),
        (WIDE + (F(1 << 4063), F(1 << 4063)), "sum bit"),
        ((F(1, 1 << 4097),), "arithmetic bit"),
    ],
)
def test_local_product_and_sum_bit_limits_refuse(values, message):
    with pytest.raises(GeometryError, match=message):
        realization._piece_exact_area(values, True, Budget())


def test_enclosure_shares_work_storage_and_deadline():
    from dataclasses import replace

    from fenolite.geometry.boolean._exact_noding import Limits

    for field in ("faces", "winding_visits"):
        with pytest.raises(GeometryError, match="budget"):
            realization._piece_exact_area(WIDE, True, Budget(replace(Limits(), **{field: 0})))
    now = [0.0]
    budget = Budget(clock=lambda: now[0])
    now[0] = 241
    with pytest.raises(GeometryError, match="deadline"):
        realization._piece_exact_area(WIDE, True, budget)
