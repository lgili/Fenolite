# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The closed table of import issue codes (capability altium-import, "Import issue codes"; change c0043)."""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from fenolite.backends.altium.adapter import IMPORT_ISSUE_CODES
from fenolite.backends.altium.adapter.codes import Census, issue
from fenolite.backends.altium.read.pcbprops import PCB_READ_ISSUE_CODES
from fenolite.backends.altium.read.sch import ISSUE_CODES as SCH_CODES
from fenolite.core.errors import ISSUE_CODE
from fenolite.lens.altium import ALTIUM_ISSUE_CODES

ROOT = Path(__file__).resolve().parents[5]
SOURCES = sorted((ROOT / "src" / "fenolite" / "backends" / "altium").rglob("*.py"))
ERRORS = {"altium.import.bad-stack", "altium.import.sheet-loop"}
INFOS = {
    "altium.import.inexact", "altium.import.multi-class", "altium.import.zone-arc",
    "altium.import.copper-shape", "altium.import.scope", "altium.import.option-ignored",
    "altium.import.bus-member", "altium.import.harness-entry", "altium.import.extra-board",
    "altium.import.linked-by-designator", "altium.import.pcb-only-net", "altium.import.rule-unmapped",
    "altium.import.unmapped", "altium.import.channels", "altium.import.pin-map",
}  # fmt: skip


def test_every_code_has_one_severity_and_the_prefix() -> None:
    assert len(IMPORT_ISSUE_CODES) == 37
    for code, severity in IMPORT_ISSUE_CODES.items():
        assert code.startswith("altium.import.") and ISSUE_CODE.match(code), code
        expected = "error" if code in ERRORS else ("info" if code in INFOS else "warning")
        assert severity == expected, code
    assert ERRORS | INFOS <= set(IMPORT_ISSUE_CODES)


def test_the_source_gives_only_codes_of_the_table() -> None:
    used: set[str] = set()
    for path in SOURCES:
        used |= set(re.findall(r'"(altium\.import\.[a-z0-9-]+)"', path.read_text(encoding="utf-8")))
    assert used <= set(IMPORT_ISSUE_CODES), sorted(used - set(IMPORT_ISSUE_CODES))
    assert set(IMPORT_ISSUE_CODES) <= used, sorted(set(IMPORT_ISSUE_CODES) - used)


def test_no_code_of_the_build_or_of_a_reader() -> None:
    others = set(ALTIUM_ISSUE_CODES) | set(PCB_READ_ISSUE_CODES) | set(SCH_CODES)
    assert not set(IMPORT_ISSUE_CODES) & others


def test_every_code_is_a_row_of_the_cli_contract() -> None:
    text = (ROOT / "docs" / "cli-contract.md").read_text(encoding="utf-8")
    for code, severity in IMPORT_ISSUE_CODES.items():
        assert re.search(rf"^\| `{re.escape(code)}` \| {severity} \|", text, re.MULTILINE), code


def test_issue_refuses_a_code_outside_the_table() -> None:
    found = issue("altium.import.scope", "the scope is flat", "top.SchDoc")
    assert (found.severity, found.where) == ("info", "top.SchDoc")
    with pytest.raises(KeyError):
        issue("altium.import.nope", "x")


def test_census_adds_up_and_reports_once() -> None:
    census = Census()
    assert census.issues() == []
    census.map("tracks", 3)
    census.skip("tracks", "footprint-graphics", 2)
    census.skip("arcs", "footprint-graphics")
    census.skip("texts", "texts", 0)
    census.note("region-holes", 4)
    census.inexact_lengths = 5
    assert census.total("tracks") == 5 and census.total("arcs") == 1 and census.total("vias") == 0
    assert census.categories() == {"footprint-graphics": 3, "region-holes": 4}
    inexact, unmapped = census.issues("a.PcbDoc")
    assert inexact.code == "altium.import.inexact" and "5 length(s) and 0 angle(s)" in inexact.message
    assert unmapped.code == "altium.import.unmapped"
    assert unmapped.message.endswith("footprint-graphics 3, region-holes 4")
