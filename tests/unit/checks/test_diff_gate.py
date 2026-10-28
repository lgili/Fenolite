# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Gated differences (capability file-safety, "Gated differences"; change c0207): each change of a kind
outside the allowed set is one ``diff.not-allowed`` error. Hermetic: the authored two-layer board, with a
track moved and a rule changed in memory, round invented values."""

from __future__ import annotations

import dataclasses
from pathlib import Path

import pytest

from fenolite.backends.kicad.pcb import read_board
from fenolite.checks.diff import diff_designs
from fenolite.checks.diffgate import ISSUE_CODES, KINDS, gate, kind_of, parse_kinds
from fenolite.core.coords import Point
from fenolite.model.design import Design
from fenolite.model.rules import Rule, RuleSet, Selector

TWO_LAYER = Path(__file__).resolve().parents[2] / "data" / "kicad" / "board" / "two_layer.kicad_pcb"
MM = 1_000_000


def _with_rule(design: Design, minimum: int) -> Design:
    rule = Rule(id="rul_1", name="power", kind="track_width", selector_a=Selector("net", "VCC"), min=minimum)
    return dataclasses.replace(design, rules=RuleSet(id="rst_1", rules=(rule,)))


def _pair() -> tuple[Design, Design]:
    base = _with_rule(read_board(TWO_LAYER), MM // 4)
    assert base.board is not None
    track = base.board.tracks[0]
    moved = dataclasses.replace(track, end=Point(track.end.x + MM, track.end.y))
    board = dataclasses.replace(base.board, tracks=(moved, *base.board.tracks[1:]))
    return base, _with_rule(dataclasses.replace(base, board=board), MM // 2)


def test_a_change_outside_the_allowed_set() -> None:
    base, edited = _pair()
    report = diff_designs(base, edited)
    assert {kind_of(change.path) for change in report.changes} == {"track", "rule"}
    issues = gate(report, parse_kinds("track"))
    assert [issue.code for issue in issues] == ["diff.not-allowed", "diff.not-allowed"]
    assert {issue.where for issue in issues} == {"/rule/0"}  # removed and added: a rule has no name key
    assert all(issue.severity == "error" and "rule" in issue.message for issue in issues)
    assert gate(report, parse_kinds("track,rule")) == ()
    assert len(gate(report, parse_kinds(""))) == len(report.changes)  # nothing allowed: every change


def test_kinds() -> None:
    assert parse_kinds(" track , via ,") == {"track", "via"}
    assert {"track", "rule", "footprint", "pad", "design", "symbol"} <= KINDS
    with pytest.raises(ValueError, match="'tracks'"):
        parse_kinds("tracks")
    assert ISSUE_CODES == {"diff.not-allowed": "error", "diff.conflict": "error", "diff.unmergeable": "error"}
