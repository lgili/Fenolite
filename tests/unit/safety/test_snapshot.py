# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""``fenolite snapshot`` (change c0201; capability file-safety, "Stable snapshot")."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from _checkcli import run
from _safetyproject import project

from fenolite.cli import cmd_snapshot
from fenolite.core.io import sha256_of
from fenolite.safety.files import RETRIES, companions, project_files, read_stable


def test_companions_of_a_board(tmp_path: Path) -> None:
    """The documents of the stem, the table beside it and the library folder it names; not the other
    board, not the notes."""
    board = project(tmp_path)
    assert [rel.as_posix() for rel in companions(board)] == [
        "Local.pretty/R.kicad_mod", "board.kicad_pcb", "board.kicad_pro", "fp-lib-table",
    ]  # fmt: skip
    assert "other.kicad_pcb" in {rel.as_posix() for rel in project_files(board.parent)}


def test_a_file_saved_during_the_copy(tmp_path: Path) -> None:
    """Scenario "A file saved during the copy": the board is saved once after its first read."""
    board = project(tmp_path)
    saved = b"(kicad_pcb (version 20240108))\n"

    def save_once(path: Path, attempt: int) -> None:
        if path == board and attempt == 0:
            path.write_bytes(saved)

    read = read_stable(board.parent, companions(board), hook=save_once)
    held = {item.path: item for item in read.files}
    assert read.retries == 1 and read.unstable == () and held["board.kicad_pcb"].data == saved


def test_a_file_that_never_settles(tmp_path: Path) -> None:
    board = project(tmp_path)
    count = iter(range(100))

    def keep_saving(path: Path, attempt: int) -> None:
        if path == board:
            path.write_bytes(f"(kicad_pcb {next(count)})\n".encode())

    read = read_stable(board.parent, companions(board), hook=keep_saving)
    assert read.unstable == ("board.kicad_pcb",) and read.retries == RETRIES


def test_snapshot_command(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    board = project(tmp_path)
    code, env, err, _ = run(
        monkeypatch, tmp_path, "snapshot", "proj/board.kicad_pcb", "--out", "snap", "--confirm"
    )
    assert code == 0, err
    manifest = json.loads((tmp_path / "snap" / "snapshot.json").read_text(encoding="utf-8"))
    assert manifest["schema"] == "fenolite.snapshot.v0" and manifest["source"] == "proj"
    assert {row["path"]: row["sha256"] for row in manifest["files"]}["board.kicad_pcb"] == sha256_of(board)
    assert (tmp_path / "snap" / "Local.pretty" / "R.kicad_mod").is_file()
    assert env["result"]["count"] == 4 and env["result"]["retries"] == 0


def test_unstable_writes_nothing(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    board = project(tmp_path)
    count = iter(range(100))

    def keep_saving(path: Path, attempt: int) -> None:
        if path == board:
            path.write_bytes(f"(kicad_pcb {next(count)})\n".encode())

    monkeypatch.setattr(cmd_snapshot, "HOOK", keep_saving)
    code, env, _, _ = run(monkeypatch, tmp_path, "snapshot", "proj", "--out", "snap", "--confirm")
    assert code == 5 and [i["code"] for i in env["issues"]] == ["safety.unstable"]
    assert not (tmp_path / "snap").exists()


def test_out_inside_the_project(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    project(tmp_path)
    code, _, err, _ = run(monkeypatch, tmp_path, "snapshot", "proj", "--out", "proj/snap", "--dry-run")
    assert code == 2 and err["code"] == "FEN-2001"


def test_online_only_stops_before_reading(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    board = project(tmp_path)
    monkeypatch.setattr(cmd_snapshot, "online_only", lambda paths: tuple(p for p in paths if p == board))
    code, _, err, _ = run(monkeypatch, tmp_path, "snapshot", "proj", "--out", "snap", "--dry-run")
    assert code == 3 and err["code"] == "FEN-3007" and err["retryable"] is True
