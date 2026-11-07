# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Board form preserved beside library subcommands (c0264)."""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest
from _checkcli import run

from fenolite.cli._examples import EXAMPLE_BOARD


def test_library_board_form_is_unchanged(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    code, reply, error, _ = run(
        monkeypatch, tmp_path, "library", EXAMPLE_BOARD, "--out", "local.pretty", "--dry-run"
    )
    assert code == 0, error
    assert reply["result"]["footprints"] and reply["result"]["plan"]


def test_board_folder_spelled_as_import(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    folder = tmp_path / "import"
    folder.mkdir()
    shutil.copy(EXAMPLE_BOARD, folder / "board.kicad_pcb")
    code, reply, error, _ = run(
        monkeypatch, tmp_path, "library", "./import", "--out", "local.pretty", "--dry-run"
    )
    assert code == 0, error
    assert reply["result"]["board"] == "board.kicad_pcb"
