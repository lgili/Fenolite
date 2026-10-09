# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The direction from KiCad to KiCad (capability design-conversion, "KiCad to KiCad direction" and "KiCad
downgrade refused"; change c0159)."""

from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest
from _convert import BLINK_T9, BLINK_T10, TWO_LAYER

from fenolite.api.conversion import convert
from fenolite.convert import LossyConversionError, convert_project

ROOT = Path(__file__).resolve().parents[3]
WITH_SHEET = ROOT / "tests" / "data" / "kicad" / "parity" / "agree"
TOKENS = ROOT / "tests" / "data" / "kicad" / "tokens"


def test_downgrade_needs_consent_for_design_rows() -> None:
    """Change c0162 (it replaces c0159's "Older target refused"): a board of KiCad 10 is written for 9, and
    the keys every KiCad 10 project holds (component classes, tuning profiles) are ``design`` rows of the
    resolver, a loss that needs consent."""
    with pytest.raises(LossyConversionError) as refused:
        convert_project(BLINK_T10, to="kicad", kicad_version=9)
    assert set(refused.value.report.refused) == {
        "downgrade:project:/component_class_settings",
        "downgrade:project:/net_settings/classes/*/tuning_profile",
        "downgrade:project:/tuning_profiles",
    }


def test_downgrade_rows_per_resolver_id() -> None:
    """Scenario "Rows per resolver id" on the blink example: one row per resolver id, the project's
    libraries written for the target, and the verification under the profile ``kicad-downgrade``."""
    conversion = convert_project(BLINK_T10, to="kicad", kicad_version=9, allow_lossy=True)
    assert conversion.profile == "kicad-downgrade" and conversion.direction.downgrade
    files = sorted(conversion.files)
    assert "fp-lib-table" in files and "lib/Mini.pretty/Mini_R_0603.kicad_mod" in files
    board = conversion.files["blink.kicad_pcb"].decode("utf-8")
    assert "(version 20241229)" in board.splitlines()[1]
    for key in files:
        if key.endswith(".kicad_mod"):
            assert "(version 20241229)" in conversion.files[key].decode("utf-8"), key
    nets = conversion.report.row("downgrade:net-by-name")
    assert nets is not None and nets.changed > 0 and nets.lost == 0 and nets.loss == "report"
    version = conversion.report.row("downgrade:project:/net_settings/meta/version")
    assert version is not None and version.changed == 1
    lost = conversion.report.row("downgrade:project:/tuning_profiles")
    assert lost is not None and lost.lost == 1 and lost.loss == "refuse"
    assert lost.reasons[0].ids == ("blink.kicad_pro:/tuning_profiles",)
    project = json.loads(conversion.files["blink.kicad_pro"])
    assert "tuning_profiles" not in project and project["net_settings"]["meta"]["version"] == 4


def test_downgrade_verified() -> None:
    result = convert(BLINK_T10, to="kicad", kicad_version=9, allow_lossy=True)
    assert result.equivalence is not None and result.equivalence.report is not None
    assert result.unexplained == () and result.equivalence.report.equivalent


def test_downgrade_of_a_schematic(tmp_path: Path) -> None:
    """A schematic of KiCad 10 is re-targeted with the board (change c0162)."""
    folder = tmp_path / "blink"
    shutil.copytree(BLINK_T10, folder)
    sheet = (TOKENS / "skeleton.kicad_sch").read_text(encoding="utf-8")
    sheet = sheet.replace("(version 20231120)", "(version 20260306)").replace(
        "\t\t(unit 1)\n", "\t\t(unit 1)\n\t\t(body_style 1)\n\t\t(in_pos_files yes)\n", 1
    )
    (folder / "blink.kicad_sch").write_text(sheet, encoding="utf-8")
    conversion = convert_project(folder, to="kicad", kicad_version=9, allow_lossy=True)
    written = conversion.files["blink.kicad_sch"].decode("utf-8")
    assert "(version 20250114)" in written and "(convert 1)" in written and "in_pos_files" not in written
    assert conversion.schematic == "blink.kicad_sch"
    row = conversion.report.row("downgrade:sch-symbol-body-style")
    assert row is not None and row.changed == 1
    schematic = conversion.report.row("schematic")
    assert schematic is not None and (schematic.source, schematic.written, schematic.lost) == (1, 1, 0)


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
