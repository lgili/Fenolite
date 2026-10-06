# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Board-wide rules of the new hole and ring kinds below the template's board-setup minimums (capability
kicad-oracle, "New rule kinds are enforced by kicad-cli"; hypothesis H-K-PRO-MIN-RULE-3; change c0071).

The bench holds an item between each rule's ``min`` and the minimum of its kind (0.25 mm for both hole
distances, 0.1 mm for the annular ring), on the project template. Without the rules KiCad reports each item;
with them it reports none, so the rule governs and ``lowering.MINIMUM_KEYS`` needs no key for these kinds.
``silk_clearance`` has no such run: the template's ``min_silk_clearance`` is 0."""

from __future__ import annotations

import _kindcases as kc
import _rulebench as rb
import pytest
from _probes import major, run

from fenolite.backends.kicad import lowering

pytestmark = pytest.mark.needs_kicad


def targets() -> tuple[int, ...]:
    """A 10.0 ``kicad-cli`` judges both board formats; a 9.0 one judges its own."""
    return (10, 9) if major() >= 10 else (9,)


@pytest.mark.parametrize("kind", kc.FLOOR_KINDS)
def test_rule_governs_below_minimum(kind: str) -> None:
    types = kc.VIOLATION_TYPES[kind]
    for board_target in targets():
        ruled, plain = kc.floor(board_target, True), kc.floor(board_target, False)
        for result in (ruled, plain):
            rb.require_canary(result.report, result.bench)
        label = kind if kind == "annular_width" else None
        without = plain.of(kind, types) if label else plain.between(kind, types)
        with_rule = ruled.of(kind, types) if label else ruled.between(kind, types)
        assert without, f"{kind}, target {board_target}: the template minimum does not report the item"
        assert not with_rule, f"{kind}, target {board_target}: the minimum governs over the rule"
        assert run(f"pro-min-rule-{kind}-t{board_target}") == "present"


def test_minimum_keys_need_no_new_kind() -> None:
    """Every floor probe of the running major is ``present``, so no key was added for the new kinds."""
    for board_target in targets():
        assert not set(kc.FLOOR_KINDS) & set(lowering.MINIMUM_KEYS[board_target])
