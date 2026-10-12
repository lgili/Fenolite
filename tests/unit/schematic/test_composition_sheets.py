# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Fixed paper, reserved regions and bounded block packing."""

import pytest

from fenolite.schematic.composition import GRID, Box, CompositionError, Unit, compose_sheet
from fenolite.schematic.intent import BlockIntent, CompositionIntent


def units():
    return tuple(
        Unit(f"U{i}#1", f"U{i}", 1, "root", f"U{i}", "Core", Box(0, 0, 2 * GRID, 2 * GRID), ())
        for i in range(3)
    )


def test_block_order_and_reserved_region():
    members = units()
    intent = CompositionIntent(
        blocks=tuple(
            BlockIntent(f"b{i}", (u.component,), f"Block {i}", after=f"b{i - 1}" if i else None)
            for i, u in enumerate(members)
        )
    )
    region = Box(0, 0, 100 * GRID, 100 * GRID)
    reserved = (Box(0, 0, 10 * GRID, 12 * GRID),)
    plan = compose_sheet(members, intent, sheet="root", region=region, reserved=reserved)
    assert [b.key for b in plan.blocks] == ["b0", "b1", "b2"]
    assert all(not p.bounds.overlaps(reserved[0]) for p in plan.placements)
    assert plan == compose_sheet(
        tuple(reversed(members)), intent, sheet="root", region=region, reserved=reserved
    )


def test_overflow_and_budget_exhaustion_are_actionable():
    with pytest.raises(CompositionError) as error:
        compose_sheet(units(), CompositionIntent(), sheet="root", region=Box(0, 0, GRID, GRID))
    assert error.value.issues[0].code == "composition.overflow"
    with pytest.raises(CompositionError) as error:
        compose_sheet(
            units(), CompositionIntent(), sheet="root", region=Box(0, 0, 100 * GRID, 100 * GRID), budget=0
        )
    assert error.value.issues[0].code == "composition.budget-exhausted"


def test_empty_sheet_and_vertical_composition():
    region = Box(0, 0, 100 * GRID, 100 * GRID)
    assert compose_sheet((), CompositionIntent(), sheet="root", region=region).placements == ()
    plan = compose_sheet(units(), CompositionIntent(flow="top-to-bottom"), sheet="root", region=region)
    assert len(plan.placements) == 3
