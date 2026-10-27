# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""``fenolite analyze --kinds crossings`` (change c0199; capability board-analyses, "Crossings kind in the
analyze command"), on the authored benches of ``tests/_crossbench.py`` written as KiCad boards. Hermetic:
the command runs no tool and writes no file."""

from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Any

import _crossbench as cb
import pytest
from _checkcli import run
from _projects import tree_snapshot

from fenolite.backends.kicad.pcb import write_board
from fenolite.model.design import Design

CUT = "10mm,20mm,27.78mm,20mm"


@pytest.fixture(autouse=True)
def no_subprocess(monkeypatch: pytest.MonkeyPatch) -> None:
    def refuse(*args: object, **kwargs: object) -> None:
        raise AssertionError("a subprocess was started")

    monkeypatch.setattr(subprocess, "run", refuse)
    monkeypatch.setattr(subprocess, "Popen", refuse)


def analyze(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, *args: str
) -> tuple[int, dict[str, Any], dict[str, Any]]:
    code, env, err, _ = run(monkeypatch, tmp_path, "analyze", *args)
    return code, env, err


def written(tmp_path: Path, design: Design) -> Path:
    path = tmp_path / "row.kicad_pcb"
    path.write_text(write_board(design, target=10).text, encoding="utf-8", newline="\n")
    return path


def test_row_through_the_command(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Scenario "Ways counted by hand", through the command: --clearance gives the class's 0.2 mm."""
    board = written(tmp_path, cb.row())
    before = tree_snapshot(tmp_path)
    code, env, err = analyze(
        monkeypatch, tmp_path, str(board), "--kinds", "crossings", "--cut", CUT, "--width", "0.25mm",
        "--clearance", "0.2mm",
    )  # fmt: skip
    assert code == 0, err
    (row,) = env["result"]["crossings"]
    assert row["cut"] == CUT and row["supply"] == 28 and row["length"] == 7 * cb.PITCH
    assert [[way["tracks"] for way in layer["ways"]] for layer in row["layers"]] == [[2] * 7, [2] * 7]
    assert env["result"]["summary"]["crossings"] == {"cuts": 1, "short": 0}
    assert env["result"]["inputs"]["width"] == cb.WIDTH and env["evidence"]["level"] == "INFERRED"
    assert tree_snapshot(tmp_path) == before


def test_short_is_a_warning(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Scenario "More nets than ways": a warning, so the exit code stays 0."""
    board = written(tmp_path, cb.row(links=20, top_only=True))
    code, env, _ = analyze(
        monkeypatch, tmp_path, str(board), "--kinds", "crossings", "--cut", CUT, "--width", "0.25mm",
        "--clearance", "0.2mm",
    )  # fmt: skip
    assert code == 0
    assert [found["code"] for found in env["issues"]] == ["analysis.crossings-short"]
    (row,) = env["result"]["crossings"]
    assert (row["open"], row["supply"]) == (20, 14)


@pytest.mark.parametrize(
    "args",
    [
        ("--kinds", "crossings"),
        ("--kinds", "current", "--cut", CUT),
        ("--kinds", "crossings", "--cut", "10mm,20mm,27mm"),
        ("--kinds", "crossings", "--cut", "10,20,27,20"),
        ("--kinds", "crossings", "--cut", "1mm,1mm,1mm,1mm"),
        ("--kinds", "current", "--width", "0.25mm"),
    ],
)
def test_usage_errors(monkeypatch: pytest.MonkeyPatch, tmp_path: Path, args: tuple[str, ...]) -> None:
    board = written(tmp_path, cb.row())
    code, _, err = analyze(monkeypatch, tmp_path, str(board), *args)
    assert code == 2 and err["code"] == "FEN-2001"
