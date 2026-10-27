# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Open sessions (change c0201; capability file-safety, "Open sessions and placeholders")."""

from __future__ import annotations

from pathlib import Path

import pytest
from _checkcli import run
from _safetyproject import project

from fenolite.safety.sessions import lock_files, lock_path, open_sessions


def test_kicad_lock_name(tmp_path: Path) -> None:
    assert lock_path(tmp_path / "board.kicad_pcb") == tmp_path / "~board.kicad_pcb.lck"


def test_a_board_open_in_kicad(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Scenario "A board open in KiCad": a writing command warns, naming the board and the lock file."""
    board = project(tmp_path)
    lock_path(board).write_text('{"username": "u", "hostname": "h", "token": "t"}', encoding="utf-8")
    assert [s.path for s in open_sessions([board, board.with_name("board.kicad_pro")])] == [board]
    code, env, err, _ = run(monkeypatch, tmp_path, "fmt", "proj/board.kicad_pcb", "--dry-run")
    assert code == 0, err
    found = [i for i in env["issues"] if i["code"] == "safety.open-session"]
    if env["result"].get("plan"):
        assert len(found) == 1 and "~board.kicad_pcb.lck" in found[0]["message"]
        assert found[0]["where"] == "proj/board.kicad_pcb" and found[0]["severity"] == "warning"


def test_open_session_on_any_write(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """The warning comes from the dispatcher, so every planned file is checked: here a snapshot target."""
    project(tmp_path)
    (tmp_path / "snap").mkdir()
    lock_path(tmp_path / "snap" / "board.kicad_pcb").write_text("{}", encoding="utf-8")
    code, env, err, _ = run(monkeypatch, tmp_path, "snapshot", "proj", "--out", "snap", "--dry-run")
    assert code == 0, err
    assert [i["where"] for i in env["issues"] if i["code"] == "safety.open-session"] == [
        "snap/board.kicad_pcb"
    ]


def test_doctor_sessions(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    board = project(tmp_path)
    lock_path(board).write_text("{}", encoding="utf-8")
    lock_path(board.with_name("gone.kicad_sch")).write_text("{}", encoding="utf-8")
    assert [s.path.name for s in lock_files(board.parent)] == ["board.kicad_pcb", "gone.kicad_sch"]
    code, env, err, _ = run(monkeypatch, tmp_path, "doctor", "--sessions", "proj")
    assert code == 0, err
    assert env["result"]["sessions"] == [
        {"path": "board.kicad_pcb", "lock": "~board.kicad_pcb.lck", "tool": "KiCad", "stale": False},
        {"path": "gone.kicad_sch", "lock": "~gone.kicad_sch.lck", "tool": "KiCad", "stale": True},
    ]
    assert env["result"]["online_only"] == [] and len(env["issues"]) == 2
