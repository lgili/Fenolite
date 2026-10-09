# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The direction from KiCad to KiCad (capability design-conversion, "KiCad to KiCad direction" and "KiCad
downgrade refused"; change c0159)."""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest
from _convert import BLINK_T9, BLINK_T10, TWO_LAYER

from fenolite.backends.kicad.versions import DowngradeRefusedError
from fenolite.convert import convert_project

ROOT = Path(__file__).resolve().parents[3]
WITH_SHEET = ROOT / "tests" / "data" / "kicad" / "parity" / "agree"


def test_older_target_refused() -> None:
    """Scenario "Older target refused", without the CLI: a board of KiCad 10 is not written for 9."""
    with pytest.raises(DowngradeRefusedError) as refused:
        convert_project(BLINK_T10, to="kicad", kicad_version=9)
    assert refused.value.cli_code == "FEN-7002"


def test_same_major_gives_the_project_back() -> None:
    """A project converted to its own major is its own files: the board keeps its content, the project
    file is updated to what it holds, and the rules file is written again in its order."""
    conversion = convert_project(BLINK_T10, to="kicad", kicad_version=10)
    assert sorted(conversion.files) == ["blink.kicad_dru", "blink.kicad_pcb", "blink.kicad_pro"]
    for name, data in conversion.files.items():
        assert data == (BLINK_T10 / name).read_bytes(), name
    assert not conversion.report.lossy and not conversion.direction.experimental
    assert conversion.read_back == "blink.kicad_pcb"


def test_nine_to_ten() -> None:
    """A KiCad 9 project written for 10: the board's header is that of 10, the classes and rules of the
    project are kept, and nothing is lost."""
    conversion = convert_project(BLINK_T9, to="kicad", kicad_version=10)
    board = conversion.files["blink.kicad_pcb"].decode("utf-8")
    assert "(version 20260206)" in board.splitlines()[1]
    assert conversion.files["blink.kicad_dru"] == (BLINK_T9 / "blink.kicad_dru").read_bytes()
    netclass = conversion.report.row("netclass")
    assert netclass is not None and netclass.source == netclass.written == 2
    assert not conversion.report.lossy


def test_name_renames_the_triad() -> None:
    conversion = convert_project(TWO_LAYER, to="kicad", name="renamed")
    assert sorted(conversion.files) == ["renamed.kicad_dru", "renamed.kicad_pcb", "renamed.kicad_pro"]


def test_schematic_copied_for_the_same_major(tmp_path: Path) -> None:
    folder = tmp_path / "blink"
    shutil.copytree(WITH_SHEET, folder)
    conversion = convert_project(folder, to="kicad", kicad_version=10)
    assert conversion.files["blink.kicad_sch"] == (WITH_SHEET / "blink.kicad_sch").read_bytes()
    row = conversion.report.row("schematic")
    assert row is not None and (row.source, row.written, row.lost) == (1, 1, 0)


def test_schematic_of_another_major_is_reported(tmp_path: Path) -> None:
    """A schematic is not re-targeted (change c0162): converting a board of 9 that has one to 10 reports
    the sheet as lost, a ``report`` kind that needs no consent."""
    folder = tmp_path / "blink"
    shutil.copytree(BLINK_T9, folder)
    shutil.copy(WITH_SHEET / "blink.kicad_sch", folder / "blink.kicad_sch")
    conversion = convert_project(folder, to="kicad", kicad_version=10)
    assert "blink.kicad_sch" not in conversion.files
    row = conversion.report.row("schematic")
    assert row is not None and row.lost == 1 and row.loss == "report"
    assert "not re-targeted" in row.reasons[0].reason and conversion.report.refused == ()
