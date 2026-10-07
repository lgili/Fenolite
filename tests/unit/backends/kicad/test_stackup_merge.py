# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The stack-up of a rebuild (capability layout-lens, "Stack-up across rebuilds"; change c0101): the five
cases of ``merge_stackup``, the first difference named, purity."""

from __future__ import annotations

import dataclasses

from _boards import stack_entry, stack_of

from fenolite.backends.kicad import stackup
from fenolite.backends.kicad.layers import created_layers
from fenolite.backends.kicad.stackup import MERGE_ISSUE_CODES, StackupMerge, complete, merge_stackup, values
from fenolite.lens.build import BUILD_ISSUE_CODES
from fenolite.lens.preserve import PRESERVE_ISSUE_CODES
from fenolite.model.board import Stackup

LAYERS = created_layers(2)


def script(core: int = 1_500_000, finish: str = "ENIG") -> Stackup:
    return stack_of(
        stack_entry("F.Mask", "soldermask", 10_000),
        stack_entry("F.Cu", "copper", 35_000),
        stack_entry("dielectric 1", "dielectric", core, dielectric_kind="core", material="FR4"),
        stack_entry("B.Cu", "copper", 35_000),
        stack_entry("B.Mask", "soldermask", 10_000),
        finish=finish,
    )


def board(core: int = 1_500_000, finish: str = "ENIG") -> Stackup:
    """What a read gives for the node of ``script(...)``: complete, with other ids."""
    done = complete(script(core, finish), LAYERS)
    return dataclasses.replace(
        done, layers=tuple(dataclasses.replace(e, id=stack_entry(e.name, e.kind, 1).id) for e in done.layers)
    )


def test_no_script_stackup_keeps_the_boards() -> None:
    held = board()
    assert merge_stackup(None, held, layers=LAYERS, locked=False) == StackupMerge(held, "board")
    assert merge_stackup(None, held, layers=LAYERS, locked=True) == StackupMerge(held, "board")
    assert merge_stackup(None, None, layers=LAYERS, locked=False) == StackupMerge(None, None)


def test_equal_stackups_keep_the_boards_entities() -> None:
    held = board()
    found = merge_stackup(script(), held, layers=LAYERS, locked=False)
    assert found.stackup is held and found.source == "script" and found.issues == ()


def test_board_without_a_stackup_takes_the_scripts() -> None:
    found = merge_stackup(script(), None, layers=LAYERS, locked=False)
    assert found.source == "script" and found.issues == ()
    assert values(found.stackup) == values(complete(script(), LAYERS))
    assert found.stackup is not None and len(found.stackup.layers) == 9


def test_board_wins_over_an_unlocked_script() -> None:
    held = board(core=1_400_000)
    found = merge_stackup(script(), held, layers=LAYERS, locked=False)
    assert found.stackup is held and found.source == "board"
    (issue,) = found.issues
    assert (issue.code, issue.severity) == ("kicad.stackup.overridden", "info")
    assert "'dielectric 1'" in issue.message and "thickness" in issue.message
    assert issue.hint == (
        "lock the stack-up in the script, edit it in KiCad's Board Setup, or re-run with --discard-layout"
    )


def test_locked_script_replaces_the_boards() -> None:
    found = merge_stackup(script(), board(finish="HAL lead-free"), layers=LAYERS, locked=True)
    assert found.source == "script" and values(found.stackup) == values(complete(script(), LAYERS))
    (issue,) = found.issues
    assert (issue.code, issue.severity) == ("kicad.stackup.forced", "warning")
    assert "finish" in issue.message and "HAL lead-free" in issue.message


def test_merge_is_pure_and_stable_on_its_own_result() -> None:
    for held, locked in ((board(core=1_400_000), False), (board(core=1_400_000), True), (None, False)):
        built = script()
        before = (values(built), values(held))
        first = merge_stackup(built, held, layers=LAYERS, locked=locked)
        assert (values(built), values(held)) == before
        again = merge_stackup(built, first.stackup, layers=LAYERS, locked=locked)
        assert values(again.stackup) == values(first.stackup)
        if first.source == "script":
            assert again.issues == () and again.source == "script"


def test_first_difference_names_entries_and_values() -> None:
    a = complete(script(), LAYERS)
    assert stackup.first_difference(a, board()) == ""
    fewer = dataclasses.replace(a, layers=a.layers[:-1])
    assert "entries" in stackup.first_difference(a, fewer)
    flagged = dataclasses.replace(a, impedance_controlled=True)
    assert "impedance_controlled" in stackup.first_difference(a, flagged)


def test_codes_pass_the_closed_tables() -> None:
    """``kicad.*`` codes pass through the closed layout and build tables unchanged."""
    assert dict(MERGE_ISSUE_CODES) == {"kicad.stackup.forced": "warning", "kicad.stackup.overridden": "info"}
    assert not set(MERGE_ISSUE_CODES) & (set(PRESERVE_ISSUE_CODES) | set(BUILD_ISSUE_CODES))
