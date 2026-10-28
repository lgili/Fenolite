# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""``fenolite library`` (change c0223; capability design-conversion, "Library made from a board" and
"Library command result"), on the authored two-layer board and copies edited by ``tests/unit/library``."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest
from _checkcli import run

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "tests" / "unit" / "library"))

from test_derive import SILK, board_text, with_second_resistor  # noqa: E402


def _board(tmp_path: Path, text: str) -> Path:
    path = tmp_path / "board.kicad_pcb"
    path.write_text(text, encoding="utf-8", newline="\n")
    return path


def _tree(folder: Path) -> list[str]:
    return sorted(p.relative_to(folder).as_posix() for p in folder.rglob("*") if p.is_file())


def test_dry_run_plans_one_file_per_footprint(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Scenario "Two instances that differ"."""
    _board(tmp_path, with_second_resistor(board_text(), moved=True))
    code, env, _, _ = run(
        monkeypatch, tmp_path, "library", "board.kicad_pcb", "--out", "lib.pretty", "--dry-run"
    )
    assert code == 0
    paths = [write["path"] for write in env["result"]["plan"]]
    assert paths == [
        "lib.pretty/LED_THT_3mm.kicad_mod",
        "lib.pretty/R_0603.kicad_mod",
        "lib.pretty/R_0603_2.kicad_mod",
    ]
    assert [row["name"] for row in env["result"]["footprints"]] == ["LED_THT_3mm", "R_0603", "R_0603_2"]
    assert [issue["code"] for issue in env["issues"]] == ["library.instances-differ"]
    assert _tree(tmp_path) == ["board.kicad_pcb"]


def test_confirm_writes_the_library(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    _board(tmp_path, board_text())
    code, env, _, _ = run(
        monkeypatch, tmp_path, "library", "board.kicad_pcb", "--out", "lib.pretty", "--confirm"
    )
    assert code == 0, env
    assert _tree(tmp_path / "lib.pretty") == ["LED_THT_3mm.kicad_mod", "R_0603.kicad_mod"]
    code, env, _, _ = run(monkeypatch, tmp_path, "library", "board.kicad_pcb", "--diff", "lib.pretty")
    assert code == 0 and env["result"]["drift"] == []


def test_silkscreen_edited_on_the_board(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Scenario "Silkscreen edited on the board": the library holds the unclipped silkscreen."""
    _board(tmp_path, board_text())
    assert (
        run(monkeypatch, tmp_path, "library", "board.kicad_pcb", "--out", "old.pretty", "--confirm")[0] == 0
    )
    path = tmp_path / "old.pretty" / "R_0603.kicad_mod"
    path.write_text(path.read_text(encoding="utf-8").rstrip().removesuffix(")") + SILK, encoding="utf-8")
    before = _tree(tmp_path)
    code, env, _, _ = run(
        monkeypatch, tmp_path, "library", "board.kicad_pcb", "--out", "lib.pretty", "--diff", "old.pretty"
    )
    assert code == 5
    assert env["result"]["drift"] == [{"name": "R_0603", "kinds": ["silkscreen"]}]
    assert [issue["code"] for issue in env["issues"]] == ["library.drift"]
    assert _tree(tmp_path) == before


def test_usage(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    _board(tmp_path, board_text())
    assert run(monkeypatch, tmp_path, "library", "board.kicad_pcb")[0] == 2
    assert run(monkeypatch, tmp_path, "library", "board.kicad_pcb", "--out", "lib")[0] == 2
