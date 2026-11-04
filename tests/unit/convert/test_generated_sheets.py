# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The sheets and pages of the schematic that an Altium to KiCad conversion generates (capability
design-conversion, "Source sheets and pages of a generated schematic"; change c0372). Authored variants of
the public Altium blink, made in memory."""

from __future__ import annotations

import pytest
from _gensheets import BLINK, refusing_more_than, sheets, two_sheets

from fenolite.api.conversion import verify_conversion
from fenolite.convert import convert_project
from fenolite.convert.sources import read_source


def test_one_source_sheet_keeps_one_kicad_sheet() -> None:
    conversion = convert_project(read_source(BLINK), to="kicad", allow_lossy=True)
    assert sheets(conversion.files) == ["blink.kicad_sch"]


def test_each_source_sheet_gets_a_kicad_sheet() -> None:
    """Scenario "A flat project of several sheets"."""
    conversion = convert_project(two_sheets(), to="kicad", allow_lossy=True)
    assert sheets(conversion.files) == ["blink.kicad_sch", "sheets/Logic.kicad_sch", "sheets/Power.kicad_sch"]
    assert b'"D1"' in conversion.files["sheets/Power.kicad_sch"]
    assert b'"R1"' in conversion.files["sheets/Logic.kicad_sch"]
    assert not verify_conversion(conversion).unexplained


def test_a_sheet_too_large_spreads_over_pages(monkeypatch: pytest.MonkeyPatch) -> None:
    """Scenario "A circuit larger than one page": the flat blink on pages of at most two units."""
    refusing_more_than(monkeypatch, 2)
    conversion = convert_project(read_source(BLINK), to="kicad", allow_lossy=True)
    assert sheets(conversion.files) == [
        "blink.kicad_sch",
        "sheets/page-1.kicad_sch",
        "sheets/page-2.kicad_sch",
    ]
    assert not conversion.report.row("schematic").lost
    assert not [issue for issue in conversion.issues if issue.severity == "error"]
    assert not verify_conversion(conversion).unexplained


def test_a_source_sheet_too_large_spreads_over_its_own_pages(monkeypatch: pytest.MonkeyPatch) -> None:
    refusing_more_than(monkeypatch, 1)
    conversion = convert_project(two_sheets(), to="kicad", allow_lossy=True)
    assert sheets(conversion.files) == [
        "blink.kicad_sch",
        "sheets/Logic-1.kicad_sch",
        "sheets/Logic-2.kicad_sch",
        "sheets/Power.kicad_sch",
    ]


def test_conversions_repeat_byte_for_byte(monkeypatch: pytest.MonkeyPatch) -> None:
    refusing_more_than(monkeypatch, 2)
    first = convert_project(two_sheets(), to="kicad", allow_lossy=True)
    second = convert_project(two_sheets(), to="kicad", allow_lossy=True)
    assert first.files == second.files
