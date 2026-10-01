# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Reading KiCad DRC reports (capability kicad-file-backend, "DRC report reading", change c0017)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from fenolite.backends.kicad.drc import (
    EVIDENCE,
    LIB_FOOTPRINT_ISSUES,
    LIB_FOOTPRINT_MISMATCH,
    REQUIRED_KEYS,
    read_drc_report,
)
from fenolite.core.coords import Point
from fenolite.core.errors import FormatError
from fenolite.core.evidence import Level

DATA = Path(__file__).resolve().parents[4] / "tests" / "data" / "kicad" / "drc"
MM = (DATA / "report_mm.json").read_text(encoding="utf-8")
MILS = (DATA / "report_mils.json").read_text(encoding="utf-8")


def edited(**changes: object) -> str:
    data = json.loads(MM)
    for key, value in changes.items():
        if value is None:
            del data[key]
        else:
            data[key] = value
    return json.dumps(data)


def test_millimetre_report() -> None:
    report = read_drc_report(MM)
    first = report.violations[0]
    assert first.type == "clearance" and first.severity == "error"
    assert first.items[0].position == Point(12_500_000, 3_250_000)
    assert first.items[0].uuid == "00000000-0000-4000-8000-0000000000d1"
    assert (report.source, report.kicad_version, report.coordinate_units) == (
        "authored.kicad_pcb",
        "10.0.6",
        "mm",
    )


def test_mil_report() -> None:
    report = read_drc_report(MILS)
    first, second = report.violations[0].items
    assert first.position == Point(2_540_000, 0)
    assert second.position == Point(0, -38_100)


def test_rounding_half_to_even() -> None:
    report = read_drc_report(MM)
    assert report.violations[0].items[1].position == Point(13_000_000, -1_000_000)
    assert report.unconnected_items[0].items[0].position == Point(10_000_000, 250_000)


def test_order_and_optional_keys() -> None:
    report = read_drc_report(MM)
    assert [v.type for v in report.violations] == ["clearance", LIB_FOOTPRINT_MISMATCH, "clearance"]
    second = report.violations[1]
    assert second.excluded is True and second.comment == "authored"
    assert report.violations[0].excluded is False and report.violations[0].comment == ""
    assert report.included_severities == ("error", "warning") and report.ignored_checks == ()
    assert [v.type for v in report.of_type("clearance")] == ["clearance", "clearance"]
    assert report.of_type("unconnected_items") == report.unconnected_items


@pytest.mark.parametrize("constant", ["NaN", "Infinity", "-Infinity"])
def test_non_strict_number_rejected(constant: str) -> None:
    with pytest.raises(FormatError, match="strict JSON"):
        read_drc_report(MM.replace('"x": 12.5', f'"x": {constant}'))


def test_trailing_comma_rejected() -> None:
    with pytest.raises(FormatError):
        read_drc_report(MM.replace('"schematic_parity": []', '"schematic_parity": [],'))


@pytest.mark.parametrize("key", REQUIRED_KEYS)
def test_missing_required_key(key: str) -> None:
    with pytest.raises(FormatError, match=key):
        read_drc_report(edited(**{key: None}))


def test_ignored_checks_tolerated() -> None:
    report = read_drc_report(edited(ignored_checks=[{"key": "silk_overlap", "description": "x"}]))
    assert report.ignored_checks == ("silk_overlap",)


def test_unknown_keys_ignored() -> None:
    assert read_drc_report(edited(future_key={"a": 1})) == read_drc_report(MM)


def test_unknown_unit() -> None:
    with pytest.raises(FormatError, match="coordinate_units"):
        read_drc_report(edited(coordinate_units="um"))


def test_wrong_types() -> None:
    with pytest.raises(FormatError):
        read_drc_report(edited(violations={}))
    with pytest.raises(FormatError):
        read_drc_report(MM.replace('"x": 12.5', '"x": "12.5"'))
    with pytest.raises(FormatError):
        read_drc_report(MM.replace('"type": "clearance"', '"type": 3', 1))
    with pytest.raises(FormatError):
        read_drc_report("[]")


def test_constants_and_evidence() -> None:
    assert REQUIRED_KEYS == (
        "source", "date", "kicad_version", "violations", "unconnected_items", "schematic_parity",
        "coordinate_units",
    )  # fmt: skip
    assert (
        LIB_FOOTPRINT_ISSUES == "lib_footprint_issues" and LIB_FOOTPRINT_MISMATCH == "lib_footprint_mismatch"
    )
    assert EVIDENCE.level is Level.KICAD_VERIFIED and EVIDENCE.hypotheses == ("H-K-DRC-JSON",)
