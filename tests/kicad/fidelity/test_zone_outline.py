# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Prepare H-K-FID-ZONE-OUTLINE's native upgrade/refill proof; no evidence promotion by this test alone."""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest
from _fidelity import snapshot
from _probes import runner

from fenolite.backends.kicad.pcb import read_board
from fenolite.checks.equivalence import compare_designs

ROOT = Path(__file__).resolve().parents[3]
ORIGINAL = ROOT / "tests/data/fidelity/sensor"
pytestmark = [pytest.mark.needs_kicad, pytest.mark.kicad_min_major(10)]


def test_upgrade_and_refill_keep_exact_level7_geometry(tmp_path: Path) -> None:
    before = snapshot(ORIGINAL)
    project = tmp_path / "project"
    shutil.copytree(ORIGINAL, project)
    board = project / "sensor.kicad_pcb"
    a = read_board(board)
    assert a.board is not None and a.board.zones
    files = {p.name: p for p in project.iterdir() if p.is_file() and p != board}
    cli = runner()
    board.write_bytes(cli.upgrade_board(board, files=files))
    filled = cli.refill(board, files=files)
    assert filled.run.returncode == 0 and filled.board is not None, filled.run.stderr
    b = read_board(filled.board.decode("utf-8"), file="sensor.kicad_pcb")
    assert b.board is not None and any(zone.fills for zone in b.board.zones)
    report = compare_designs(a, b, level=7, strict=True)
    geometry = next(level for level in report.levels if level.level == 7)
    assert geometry.differences == (), geometry.differences
    assert snapshot(ORIGINAL) == before
