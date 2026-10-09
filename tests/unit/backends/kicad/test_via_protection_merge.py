# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The via protection default across rebuilds (capability layout-lens, "Via protection defaults across
rebuilds"; change c0112): ``merge_default``, its codes, ``not_exported`` and ``summary``."""

from __future__ import annotations

import dataclasses

import pytest
from _boards import bare_board, mm

from fenolite.backends.kicad import via_protection as vp
from fenolite.cli import explain
from fenolite.core.ids import derived_id
from fenolite.lens import build, preserve
from fenolite.model.board import Via, ViaProtection
from fenolite.model.design import Design

P = ViaProtection
OPEN = P(tenting_front=False, tenting_back=False)
TENTED = P(tenting_front=True, tenting_back=True)


def test_without_a_script_default_the_boards_is_kept() -> None:
    assert vp.merge_default(None, None, locked=False) == vp.DefaultMerge(None, None)
    assert vp.merge_default(None, OPEN, locked=True) == vp.DefaultMerge(OPEN, "board")


def test_a_board_without_a_default_takes_the_scripts() -> None:
    for locked in (False, True):
        assert vp.merge_default(OPEN, None, locked=locked) == vp.DefaultMerge(OPEN, "script")


def test_equal_in_effect_keeps_the_boards() -> None:
    resaved = vp.KICAD_DEFAULT
    decided = vp.merge_default(P(tenting_front=True), resaved, locked=True)
    assert decided == vp.DefaultMerge(resaved, "board") and decided.default is resaved


def test_an_unlocked_script_default_is_overridden() -> None:
    decided = vp.merge_default(TENTED, P(tenting_front=True, tenting_back=False), locked=False)
    assert decided.default == P(tenting_front=True, tenting_back=False) and decided.source == "board"
    (issue,) = decided.issues
    assert (issue.code, issue.severity) == ("kicad.via.protection-overridden", "info")
    assert "tenting_back is True in the script and False on the board" in issue.message
    assert issue.hint == (
        "lock the default in the script, edit it in KiCad's Board Setup, or re-run with --discard-layout"
    )


def test_a_locked_script_default_is_forced() -> None:
    decided = vp.merge_default(P(filling=True), OPEN, locked=True)
    assert decided.default == P(filling=True) and decided.source == "script"
    (issue,) = decided.issues
    assert (issue.code, issue.severity) == ("kicad.via.protection-forced", "warning")
    assert "tenting_front is True in the script and False on the board" in issue.message


@pytest.mark.parametrize("locked", [False, True])
@pytest.mark.parametrize("script", [None, OPEN, TENTED, P(filling=True)])
@pytest.mark.parametrize("board", [None, OPEN, vp.KICAD_DEFAULT, P(capping=True)])
def test_merge_is_idempotent(script: P | None, board: P | None, locked: bool) -> None:
    first = vp.merge_default(script, board, locked=locked)
    again = vp.merge_default(script, first.default, locked=locked)
    assert again.default == first.default
    # an unlocked default that differs is reported at every build, as an overridden zone is
    assert again.issues == (first.issues if not locked else ())


def test_codes_are_a_closed_table() -> None:
    assert dict(vp.ISSUE_CODES) == {
        "kicad.via.protection-forced": "warning",
        "kicad.via.protection-overridden": "info",
        "kicad.via.protection-not-exported": "info",
    }
    known = explain.entries()
    assert all(code in known for code in (*vp.ISSUE_CODES, *vp.WRITE_ISSUE_CODES))
    assert not set(vp.ISSUE_CODES) & (set(preserve.PRESERVE_ISSUE_CODES) | set(build.BUILD_ISSUE_CODES))


def design_with(default: P | None, *protections: P) -> Design:
    design = bare_board(2)
    assert design.board is not None
    vias = tuple(
        Via(id=derived_id("via", "sum", str(k)), position=mm(5 + 2 * k, 20), diameter=800_000, drill=400_000,
            layers=("F.Cu", "B.Cu"), protection=protection)
        for k, protection in enumerate(protections)
    )  # fmt: skip
    return dataclasses.replace(
        design, board=dataclasses.replace(design.board, vias=vias, via_protection=default)
    )


def test_summary_counts_effective_values() -> None:
    design = design_with(P(tenting_back=False, filling=True), P(), P(tenting_back=True), P(filling=False))
    found = vp.summary(design)
    assert found["default"] == {
        "source": "board", "tenting_front": True, "tenting_back": False, "covering_front": False,
        "covering_back": False, "plugging_front": False, "plugging_back": False, "capping": False,
        "filling": True,
    }  # fmt: skip
    zero = dict.fromkeys(vp.FIELDS, 0)
    assert found["effective"] == {**zero, "tenting_front": 3, "tenting_back": 1, "filling": 2}
    assert found["by_default"] == {**zero, "tenting_front": 3, "filling": 2}
    plain = vp.summary(design_with(None, P()))
    assert plain["default"]["source"] == "kicad"  # type: ignore[index]
    assert plain["effective"] == {**zero, "tenting_front": 1, "tenting_back": 1} == plain["by_default"]


def test_not_exported_names_fields_and_vias() -> None:
    assert vp.not_exported(design_with(None, P(), P(filling=True))) is None
    assert vp.not_exported(design_with(P(tenting_front=False), P())) is None
    assert vp.not_exported(design_with(P(filling=True), P(filling=True), P(filling=False))) is None
    issue = vp.not_exported(design_with(P(filling=True, capping=True), P(), P(capping=True), P()))
    assert issue is not None and (issue.code, issue.severity) == (vp.NOT_EXPORTED, "info")
    assert "3 via(s)" in issue.message and "capping, filling" in issue.message
    assert "10.0.6" in issue.message and "protection=" in issue.hint
