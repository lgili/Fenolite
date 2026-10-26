# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The committed boards of the panel fixtures equal a fresh build of ``tests/data/panels/board.py``
(change c0173). ``FENOLITE_PANELS_WRITE=1`` writes them instead."""

from __future__ import annotations

import os
import runpy
from pathlib import Path

import pytest
from _panels import BOARD_SCRIPT, PANELS, SCRIPTS, build_board, committed_board

from fenolite.dsl import Panel

WRITE = os.environ.get("FENOLITE_PANELS_WRITE") == "1"


@pytest.mark.parametrize("major", [9, 10])
def test_committed_board_equals_a_fresh_build(major: int, tmp_path: Path) -> None:
    built = build_board(tmp_path / "b", str(major)).read_bytes()
    target = committed_board(major)
    if WRITE:
        target.write_bytes(built)
    assert target.read_bytes() == built, f"{target.name} differs from a build of {BOARD_SCRIPT.name}"


@pytest.mark.parametrize("name", SCRIPTS)
def test_panel_scripts_bind_a_panel(name: str) -> None:
    panel = runpy.run_path(str(PANELS / f"{name}.py"))["panel"]
    assert isinstance(panel, Panel) and panel.board == "board_t10.kicad_pcb"
