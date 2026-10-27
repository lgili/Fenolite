# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""``fenolite analyze --kinds ties,domains`` (change c0198; capability board-analyses, "Ties and domains
kinds in the analyze command"), on the authored benches of ``tests/_groundties.py`` written as KiCad
boards. Hermetic: the command runs no tool and writes no file."""

from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Any

import _groundties as gt
import pytest
from _checkcli import run
from _projects import tree_snapshot

from fenolite.backends.kicad.pcb import kicad_uuid, write_board
from fenolite.model.design import Design


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


def written(tmp_path: Path, design: Design, name: str = "bench") -> Path:
    path = tmp_path / f"{name}.kicad_pcb"
    path.write_text(write_board(design, target=10).text, encoding="utf-8", newline="\n")
    return path


def uuid_of(design: Design, track_id: str) -> str:
    board = design.board
    assert board is not None
    return kicad_uuid(next(entity for entity in (*board.tracks, *board.vias) if entity.id == track_id))


def test_single_tie(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Scenario "A single tie splits the net", through the command."""
    design = gt.ground()
    board = written(tmp_path, design)
    before = tree_snapshot(tmp_path)
    code, env, err = analyze(
        monkeypatch, tmp_path, str(board), "--kinds", "ties", "--tie-item", uuid_of(design, gt.T1),
        "--domains", "PWR=Q*,CTL=U*",
    )  # fmt: skip
    assert code == 0, err
    (row,) = env["result"]["ties"]
    assert row["split"] is True and row["groups"] == [["Q1-1", "Q2-1"], ["U1-1"]] and row["zones"] == "filled"
    assert env["issues"] == [] and env["evidence"]["level"] == "INFERRED"
    assert env["result"]["summary"]["ties"]["split"] == 1
    assert env["result"]["inputs"]["domains"] == {"PWR": ["Q*"], "CTL": ["U*"]}
    assert "current" not in env["result"] and tree_snapshot(tmp_path) == before


def test_parallel_tie_exits_5(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Scenario "A parallel tie through a via": exit 5, and the path names the via."""
    design = gt.ground(via=True)
    board = written(tmp_path, design)
    code, env, _ = analyze(
        monkeypatch, tmp_path, str(board), "--kinds", "ties", "--tie-item", uuid_of(design, gt.T1)
    )
    assert code == 5
    assert [found["code"] for found in env["issues"]] == ["analysis.tie-parallel"]
    path = env["result"]["ties"][0]["path"]
    assert [item["kind"] for item in path] == ["fill", "via", "track", "via", "fill"]


def test_tie_part_and_sense(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    board = written(tmp_path, gt.split_nets())
    code, env, err = analyze(monkeypatch, tmp_path, str(board), "--kinds", "ties", "--tie", "NT1")
    assert code == 0, err
    assert env["result"]["ties"][0]["groups"] == [["Q1-1"], ["U1-1"]]
    shunt = written(tmp_path, gt.sense(), "shunt")
    code, env, _ = analyze(
        monkeypatch, tmp_path, str(shunt), "--kinds", "ties", "--sense", "ISENSE_P,ISENSE_N"
    )
    assert code == 5 and [found["code"] for found in env["issues"]] == ["analysis.sense-shared"]
    assert [row["net"] for row in env["result"]["sense"]] == ["ISENSE_P", "ISENSE_N"]


def test_islands(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Scenario "Islands across an isolator", through the command."""
    board = written(tmp_path, gt.isolated())
    code, env, err = analyze(monkeypatch, tmp_path, str(board), "--kinds", "domains", "--barrier", "U5")
    assert code == 0, err
    assert env["result"]["domains"] == [
        {"nets": ["A1", "A2"], "barriers": ["U5"]},
        {"nets": ["B1", "B2"], "barriers": ["U5"]},
    ]
    assert env["result"]["inputs"]["barriers"] == ["U5"]


@pytest.mark.parametrize(
    "args",
    [
        ("--kinds", "current", "--tie", "NT1"),
        ("--kinds", "ties,current", "--barrier", "U5"),
        ("--kinds", "ties"),
        ("--kinds", "domains"),
        ("--kinds", "ties", "--tie", "NT1", "--domains", "PWR=Q*"),
        ("--kinds", "ties", "--tie", "NT1", "--domains", "PWR"),
        ("--kinds", "ties", "--sense", "A,,B"),
    ],
)
def test_usage_errors(monkeypatch: pytest.MonkeyPatch, tmp_path: Path, args: tuple[str, ...]) -> None:
    board = written(tmp_path, gt.split_nets())
    code, _, err = analyze(monkeypatch, tmp_path, str(board), *args)
    assert code == 2 and err["code"] == "FEN-2001"
