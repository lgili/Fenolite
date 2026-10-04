# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The KiCad refill runner keeps the input board outside its temporary copy."""

from __future__ import annotations

from pathlib import Path

import pytest
from _fakecli import calls, fake_kicad_cli

from fenolite.backends.kicad.cli import DRC_REPORT, KicadCli, KicadCliVersionError


def _board(tmp_path: Path) -> Path:
    board = tmp_path / "source" / "board.kicad_pcb"
    board.parent.mkdir()
    board.write_bytes(b"original board\n")
    return board


def test_refill_arguments_saved_board_and_copy(tmp_path: Path) -> None:
    board = _board(tmp_path)
    project = board.with_suffix(".kicad_pro")
    project.write_text("{}", encoding="utf-8")
    script = fake_kicad_cli(tmp_path / "bin", refill_board="saved board\n", writes=("board.kicad_prl",))
    result = KicadCli(script).refill(board, files={project.name: project})
    assert result.board == b"saved board\n"
    assert board.read_bytes() == b"original board\n"
    assert DRC_REPORT in result.run.outputs
    assert "board.kicad_prl" in result.run.outputs
    run_call = calls(script)[-1]
    assert run_call["args"] == [
        "pcb",
        "drc",
        "--format",
        "json",
        "--severity-all",
        "--refill-zones",
        "--save-board",
        "-o",
        DRC_REPORT,
        "board.kicad_pcb",
    ]
    assert run_call["files"]["board.kicad_pro"] == "{}"


def test_no_saved_board(tmp_path: Path) -> None:
    board = _board(tmp_path)
    script = fake_kicad_cli(tmp_path / "bin")
    result = KicadCli(script).refill(board)
    assert result.run.ok
    assert result.board is None


def test_major_nine_makes_no_refill_run(tmp_path: Path) -> None:
    board = _board(tmp_path)
    script = fake_kicad_cli(tmp_path / "bin", version="9.0.9")
    with pytest.raises(KicadCliVersionError) as raised:
        KicadCli(script).refill(board)
    assert raised.value.cli_code == "FEN-6002"
    assert [call["args"] for call in calls(script)] == [["version"]]
