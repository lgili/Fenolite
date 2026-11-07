# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The width of role copper from its current (change c0243, decision 2; capability net-roles, "Copper width
from current", scenario "Both methods")."""

from __future__ import annotations

from fenolite.analysis.current import capacity_ma
from fenolite.roles.copper import fit_width, required_width, rule_of_thumb
from fenolite.roles.profile import DEFAULTS

OUTER_35UM = 35_000
PER_AMP = DEFAULTS["width_per_amp_nm"].value
assert PER_AMP is not None


def test_rule_of_thumb_without_a_rise() -> None:
    found = required_width(2000, per_amp_nm=PER_AMP)
    assert (found.value, found.method, found.temp_rise_mk) == (762_000, "rule-of-thumb", None)
    assert rule_of_thumb(1, PER_AMP) == 381 and rule_of_thumb(3, 333_333) == 1000  # rounded up, never down


def test_fit_with_a_rise() -> None:
    found = required_width(2000, per_amp_nm=PER_AMP, temp_rise_mk=10_000, thickness=OUTER_35UM, external=True)
    assert found.method == "fit" and found.temp_rise_mk == 10_000
    assert capacity_ma(found.value * OUTER_35UM, 10_000, external=True) >= 2000
    assert capacity_ma((found.value - 1) * OUTER_35UM, 10_000, external=True) < 2000
    inner = fit_width(2000, 10_000, OUTER_35UM, external=False)
    assert inner > found.value  # an inner layer carries less at the same section


def test_the_class_width_is_a_floor_and_a_rise_needs_a_thickness() -> None:
    assert required_width(2000, per_amp_nm=PER_AMP, floor=1_000_000).value == 1_000_000
    found = required_width(2000, per_amp_nm=PER_AMP, temp_rise_mk=10_000, thickness=None)
    assert found.method == "rule-of-thumb" and found.value == 762_000
