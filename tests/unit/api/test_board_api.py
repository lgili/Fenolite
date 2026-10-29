# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The typed reads and analyses of ``fenolite.api`` (capability python-api, "Typed design and board reads"
and "Typed board analyses"; change c0206)."""

from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Any

import pytest
from _projects import tree_snapshot

import fenolite.api.board as api_board
from fenolite.analysis.boundary import OVERLAP_NEEDS_GEO, BoardBoundary
from fenolite.analysis.connectivity import ConnectivityReport
from fenolite.analysis.connectivity import connectivity as net_connectivity
from fenolite.analysis.report import AnalysisReport
from fenolite.api import (
    Board,
    ExtraMissingError,
    ReadSide,
    SideMissingError,
    SideUsageError,
    analyze_current,
    analyze_distances,
    connectivity,
    read_board,
    read_design,
    run,
)
from fenolite.backends.kicad import frame
from fenolite.backends.kicad.pcb import read_board as read_kicad_board
from fenolite.cli.cmd_analyze import _json  # pyright: ignore[reportPrivateUsage]  # the command's JSON form

DATA = Path(__file__).resolve().parents[2] / "data"
BOARD = DATA / "kicad" / "board" / "two_layer.kicad_pcb"
THICK = {"F.Cu": 35_000, "B.Cu": 35_000}


def test_read_board_and_design(tmp_path: Path) -> None:
    """Scenario "Records, not dictionaries"."""
    board = read_board(BOARD)
    assert isinstance(board, Board) and board.name == BOARD.name and board.backend == "kicad"
    assert board.design.board is not None and board.pads
    assert all(issue.severity != "error" for issue in board.issues)
    (tmp_path / BOARD.name).write_bytes(BOARD.read_bytes())
    assert read_board(str(tmp_path)).sha256 == board.sha256  # a folder resolves to its board
    side = read_design(BOARD)
    assert isinstance(side, ReadSide) and side.design.board is not None and side.sha256 == board.sha256


def test_read_faults_are_typed(tmp_path: Path) -> None:
    with pytest.raises(SideMissingError):
        read_board(tmp_path / "missing.kicad_pcb")
    text = tmp_path / "notes.txt"
    text.write_text("no board\n", encoding="utf-8")
    with pytest.raises(SideUsageError) as caught:
        read_board(text)
    assert isinstance(caught.value, ValueError)


def test_connectivity_is_the_analysis() -> None:
    design = read_kicad_board(BOARD.read_text(encoding="utf-8"), file=BOARD.name)
    expected = net_connectivity(design, pads=frame.board_pads(design), nets=None)
    report = connectivity(BOARD)
    assert isinstance(report, ConnectivityReport) and report == expected
    assert connectivity(read_board(BOARD), nets=("GND",)).nets == tuple(
        n for n in expected.nets if n.name == "GND"
    )


def _cli_rows(*args: str) -> dict[str, Any]:
    reply = run("analyze", str(BOARD), *args)
    assert reply.ok, reply.error
    return dict(reply.result)


def test_analyses_equal_the_command() -> None:
    """Scenario "Same measures as analyze": the rows of the typed calls are the command's rows."""
    current = analyze_current(BOARD, temp_rise_mk=10_000, copper_thickness=THICK)
    assert isinstance(current, AnalysisReport) and current.rows
    cli = _cli_rows("--kinds", "current", "--temp-rise", "10", "--copper-thickness", "35um")
    assert [_json(row) for row in current.rows] == cli["current"]
    distances = analyze_distances(read_board(BOARD), within=5_000_000)
    assert distances.rows
    cli = _cli_rows("--kinds", "clearance,creepage", "--within", "5mm")
    without = ("insulation", "sheets")  # the command drops them without the kind insulation
    rows = [{k: v for k, v in _json(row).items() if k not in without} for row in distances.rows]
    assert rows == cli["distances"]


def test_requirements_from_a_path(tmp_path: Path) -> None:
    required = tmp_path / "req.toml"
    required.write_text('schema = "fenolite.requirements.v0"\n', encoding="utf-8")
    assert analyze_current(BOARD, requirements=required).rows == analyze_current(BOARD).rows
    with pytest.raises(SideMissingError):
        analyze_current(BOARD, requirements=tmp_path / "missing.toml")


def test_overlapping_cutouts_without_geo(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        api_board, "board_boundary", lambda *_a, **_k: BoardBoundary(problem=OVERLAP_NEEDS_GEO)
    )
    with pytest.raises(ExtraMissingError) as caught:
        analyze_distances(BOARD)
    assert caught.value.cli_code == "FEN-6001"


def test_hermetic(monkeypatch: pytest.MonkeyPatch) -> None:
    """Scenario "Records, not dictionaries": no process is started and no file is written."""

    def refuse(*_a: object, **_k: object) -> None:
        raise AssertionError("a subprocess was started")

    monkeypatch.setattr(subprocess, "run", refuse)
    monkeypatch.setattr(subprocess, "Popen", refuse)
    before = tree_snapshot(BOARD.parent)
    board = read_board(BOARD)
    connectivity(board)
    analyze_current(board)
    analyze_distances(board)
    assert tree_snapshot(BOARD.parent) == before
