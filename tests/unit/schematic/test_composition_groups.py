# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Authored grouping examples exclude shared power and retain all units."""

from dataclasses import replace

import pytest

from fenolite.schematic.composition import Box, CompositionError, Pin, Unit, group_units
from fenolite.schematic.intent import BlockIntent, CompositionIntent


def unit(key, net=None, power=False, sheet="root", part=1):
    return Unit(
        f"{key}#{part}",
        key,
        part,
        sheet,
        key,
        "",
        Box(0, 0, 10, 10),
        (Pin("1", "", (0, 0), (0, 0), 2, net, power),),
    )


def test_signal_groups_ignore_power_and_high_fanout():
    power = tuple(unit(f"U{i}", "SUPPLY", True) for i in range(4))
    assert len(group_units(power, CompositionIntent())) == 4
    fanout = tuple(unit(f"U{i}", "CLOCK") for i in range(9))
    assert len(group_units(fanout, CompositionIntent())) == 9
    assert len(group_units((unit("U1", "SIGNAL"), unit("R1", "SIGNAL")), CompositionIntent())) == 1


def test_explicit_blocks_keep_units_and_order_under_permutation():
    units = (unit("U1", part=2), unit("U1"), unit("J1"))
    intent = CompositionIntent(
        blocks=(BlockIntent("core", ("U1",), "Core", after="input"), BlockIntent("input", ("J1",), "Input"))
    )
    blocks = group_units(units, intent)
    assert [b.key for b in blocks] == ["input", "core"]
    assert [u.key for b in blocks for u in b.units] == ["J1#1", "U1#1", "U1#2"]
    assert (
        group_units(tuple(reversed(units)), replace(intent, blocks=tuple(reversed(intent.blocks)))) == blocks
    )


def test_modules_group_within_sheets_and_board_only_members_are_excluded():
    units = (unit("a/U1"), unit("a/R1"), unit("b/U1"))
    assert len(group_units(units, CompositionIntent())) == 2
    intent = CompositionIntent(blocks=(BlockIntent("board", ("H1",), "Hardware"),))
    assert group_units((), intent, component_sheets={"H1": "root"}) == ()


@pytest.mark.parametrize("problem", ["cross-sheet", "duplicate", "cycle", "unknown", "predecessor"])
def test_conflicting_membership_is_refused(problem):
    units = (unit("U1"), unit("J1", sheet="child" if problem == "cross-sheet" else "root"))
    if problem == "cross-sheet":
        blocks = (BlockIntent("a", ("U1", "J1"), "a"),)
    elif problem == "duplicate":
        blocks = (BlockIntent("a", ("U1",), "a"), BlockIntent("b", ("U1",), "b"))
    elif problem == "unknown":
        blocks = (BlockIntent("a", ("missing",), "a"),)
    else:
        blocks = (
            BlockIntent("a", ("U1",), "a", after="b"),
            BlockIntent("b", ("J1",), "b", after="a" if problem == "cycle" else "missing"),
        )
    with pytest.raises(CompositionError):
        group_units(units, CompositionIntent(blocks=blocks))
