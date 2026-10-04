# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Refilled fixtures, stage verdict and kept blink fill against KiCad 10.0.6."""

from __future__ import annotations

from pathlib import Path

import pytest
from _fillcases import FIXTURES, fills, refill
from _probes import run, runner
from _projects import authored_project

from fenolite.backends.kicad.fill import fill_board
from fenolite.backends.kicad.oracle import KicadOracle
from fenolite.backends.kicad.pcb import read_board
from fenolite.backends.kicad.projectset import project_set
from fenolite.checks.fill import fill_stage

pytestmark = [pytest.mark.needs_kicad, pytest.mark.kicad_min_major(10)]


def test_fixture_is_current(tmp_path: Path) -> None:
    root = authored_project(tmp_path, major=9, decoys=False)
    board = root / "board.kicad_pcb"
    assert board.read_bytes() == (FIXTURES / "triad_t9.kicad_pcb").read_bytes()
    saved = refill(runner(), board)
    assert saved is not None
    pinned_saved = (FIXTURES / "triad_t9_refilled.kicad_pcb").read_text(encoding="utf-8")
    assert fills(read_board(saved.decode("utf-8"))) == fills(read_board(pinned_saved))
    written = fill_board(board.read_text(encoding="utf-8"), saved.decode("utf-8"))
    assert written.text == (FIXTURES / "triad_t9_filled.kicad_pcb").read_text(encoding="utf-8")


def test_stage_unfilled_then_current(tmp_path: Path) -> None:
    root = authored_project(tmp_path, major=10, decoys=False)
    board = root / "board.kicad_pcb"
    oracle = KicadOracle(runner())
    before = fill_stage(oracle, project_set(board), read_board(board))
    assert [issue.code for issue in before.issues] == ["zone.unfilled"]
    saved = refill(runner(), board)
    assert saved is not None
    filled = fill_board(board.read_text(encoding="utf-8"), saved.decode("utf-8"))
    assert filled.text is not None
    board.write_text(filled.text, encoding="utf-8")
    after = fill_stage(oracle, project_set(board), read_board(board))
    assert after.status == "ok" and after.issues == () and after.summary["current"] == 1


def test_deterministic(tmp_path: Path) -> None:
    root = authored_project(tmp_path, major=9, decoys=False)
    board = root / "board.kicad_pcb"
    saved = refill(runner(), board)
    assert saved is not None
    first = fill_board(board.read_text(encoding="utf-8"), saved.decode("utf-8"))
    assert first.text is not None
    second = fill_board(first.text, saved.decode("utf-8"))
    assert first.text == second.text and second.changed == ()


def test_kept_fill_matches_refill() -> None:
    assert run("fill-kept") == "equal"
