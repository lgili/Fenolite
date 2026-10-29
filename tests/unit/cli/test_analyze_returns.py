# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""``fenolite analyze --kinds returns`` (change c0202; capability board-analyses, "Returns kind in the analyze
command"), on the bench of ``tests/_returnbench.py`` written as a KiCad board. Hermetic."""

from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Any

import pytest
from _checkcli import run
from _projects import tree_snapshot
from _returnbench import GAP, bench

from fenolite.backends.kicad.pcb import write_board


@pytest.fixture(autouse=True)
def no_subprocess(monkeypatch: pytest.MonkeyPatch) -> None:
    def refuse(*args: object, **kwargs: object) -> None:
        raise AssertionError("a subprocess was started")

    monkeypatch.setattr(subprocess, "run", refuse)
    monkeypatch.setattr(subprocess, "Popen", refuse)


def analyze(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, *args: str
) -> tuple[int, dict[str, Any], dict[str, Any]]:
    board = tmp_path / "returns.kicad_pcb"
    board.write_text(write_board(bench(), target=10).text, encoding="utf-8", newline="\n")
    code, env, err, _ = run(monkeypatch, tmp_path, "analyze", str(board), *args)
    return code, env, err


def test_a_track_across_a_split_plane(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Scenario "A track across a split plane", through the command: a warning, so exit 0."""
    code, env, err = analyze(monkeypatch, tmp_path, "--kinds", "returns", "--net", "SIG1")
    before = tree_snapshot(tmp_path)
    assert code == 0, err
    (row,) = env["result"]["returns"]
    (span,) = row["spans"]
    assert span["kind"] == "split" and GAP <= span["length"] <= GAP + 2
    assert [i["code"] for i in env["issues"]] == ["analysis.return-split"]
    assert env["result"]["summary"]["returns"] == {"nets": 1, "split": 1, "edge": 0}
    assert env["result"]["inputs"]["nets"] == ["SIG1"] and tree_snapshot(tmp_path) == before


def test_via_distance(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    code, env, _ = analyze(
        monkeypatch, tmp_path, "--kinds", "returns", "--net", "SIG4", "--via-distance", "0.5mm"
    )
    assert code == 0 and [i["code"] for i in env["issues"]] == ["analysis.return-via"]


@pytest.mark.parametrize(
    "args",
    [
        ("--kinds", "returns"),
        ("--kinds", "current", "--reference", "GND"),
        ("--kinds", "current", "--via-distance", "1mm"),
        ("--kinds", "current", "--net", "SIG1"),
    ],
)
def test_usage_errors(monkeypatch: pytest.MonkeyPatch, tmp_path: Path, args: tuple[str, ...]) -> None:
    code, _, err = analyze(monkeypatch, tmp_path, *args)
    assert code == 2 and err["code"] == "FEN-2001"
