# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Old KiCad inputs upgraded on copies (capability board-to-code, "Old KiCad inputs upgraded on copies").
A fake ``kicad-cli`` stands for the tool: it gives back the board in the current format; the run with the
real tool is ``tests/kicad/importer/test_upgrade_kicad.py``."""

from __future__ import annotations

import hashlib
from pathlib import Path

import pytest
from _importcode import BOARD, OLD_VERSION, imported, old

from fenolite.cli import cmd_import
from fenolite.importer import upgrade


class _FakeCli:
    def __init__(self, path: Path, *, timeout: float = 120) -> None:
        self.path = path

    def version(self) -> str:
        return "10.0.6"

    def upgrade_board(self, board: Path, *, files: object = None) -> bytes:
        assert board.read_text(encoding="utf-8").count(f"(version {OLD_VERSION})") == 1
        return BOARD.read_bytes()


def test_kicad_7_board(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    source = old(tmp_path)
    before = source.read_bytes()
    monkeypatch.setattr(upgrade, "cli_for", _FakeCli)
    monkeypatch.setattr(cmd_import, "find_kicad_cli", lambda: Path("kicad-cli"))
    reply = imported(tmp_path, source, "--confirm")
    assert reply.exit_code == 0, reply.error
    (row,) = reply.result["upgrade"]
    assert row["from_version"] == OLD_VERSION and row["to_version"] == 20260206
    assert row["sha256_before"] == hashlib.sha256(before).hexdigest()
    assert row["sha256_after"] == hashlib.sha256(BOARD.read_bytes()).hexdigest()
    assert source.read_bytes() == before
    codes = [i["code"] for i in (reply.envelope or {})["issues"]]
    assert "import.upgraded" in codes
    assert '"tool_version": "10.0.6"' in (tmp_path / "out" / "PROVENANCE.json").read_text(encoding="utf-8")


def test_no_kicad_cli(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(cmd_import, "find_kicad_cli", lambda: None)
    reply = imported(tmp_path, old(tmp_path))
    assert reply.exit_code == 6
    assert reply.error is not None and reply.error["code"] == "FEN-6001"
    assert "--no-upgrade" in reply.error["hint"]


def test_no_upgrade_refuses(tmp_path: Path) -> None:
    reply = imported(tmp_path, old(tmp_path), "--no-upgrade")
    assert reply.exit_code == 3
    assert reply.error is not None and reply.error["code"] == "FEN-3003"
