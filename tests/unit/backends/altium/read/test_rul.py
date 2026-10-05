# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Rule files read (capability altium-project-reader, "Rule files read")."""

from __future__ import annotations

from pathlib import Path

import pytest

from fenolite.backends.altium.read.rul import read_rule_file
from fenolite.core.errors import FormatError

DATA = Path(__file__).resolve().parents[4] / "data" / "altium" / "read"
HEAD = "SELECTION=FALSE|LAYER=TOP|LOCKED=FALSE|POLYGONOUTLINE=FALSE|USERROUTED=TRUE|UNIONINDEX=0"


def test_export_form_with_end_marks() -> None:
    """Scenario "Export form with end marks"."""
    data = (DATA / "rules_export.RUL").read_bytes()
    rules = read_rule_file(data, file="rules_export.RUL")
    assert rules.kind == "export" and rules.header == "" and rules.issues == ()
    assert rules.form.encoding == "utf-8"
    assert [r.get("RULEKIND") for r in rules.records] == ["Clearance", "Width", "ShortCircuit"]
    first = rules.records[0]
    assert first.keys()[:7] == (
        "SELECTION",
        "LAYER",
        "LOCKED",
        "POLYGONOUTLINE",
        "USERROUTED",
        "UNIONINDEX",
        "RULEKIND",
    )
    assert first.fields[-1] == ("GAP", "10mil")
    assert not first.text.endswith("¶")
    assert all(line.raw.endswith(b"\xc2\xb6") and line.end == b"\n" for line in rules.form.lines)
    assert rules.to_bytes() == data


def test_export_form_with_the_single_byte_mark() -> None:
    data = (HEAD + "|RULEKIND=Width|NAME=W|MINLIMIT=8mil").encode() + b"\xb6\r\n"
    rules = read_rule_file(data * 2, file="w.RUL")
    assert rules.form.encoding == "latin-1"
    assert [r.fields[-1] for r in rules.records] == [("MINLIMIT", "8mil")] * 2
    assert [i.code for i in rules.issues] == ["altium.text.encoding-assumed"]
    assert rules.to_bytes() == data * 2


def test_export_form_keeps_a_b6_inside_utf8_text() -> None:
    data = (HEAD + "|RULEKIND=Width|NAME=Wö").encode() + b"\n"
    rules = read_rule_file(data)
    assert rules.form.encoding == "utf-8" and rules.records[0].get("NAME") == "Wö"


def test_export_form_without_end_marks_and_empty_lines() -> None:
    data = b"\nRULEKIND=Width|NAME=A\n\nRULEKIND=Clearance|NAME=B"
    rules = read_rule_file(data)
    assert [r.get("NAME") for r in rules.records] == ["A", "B"] and rules.to_bytes() == data


def test_export_malformed_record_is_kept() -> None:
    data = b"RULEKIND=Width|NAME=A\xc2\xb6\nNAME=lost|GAP=1mil\xc2\xb6\n"
    rules = read_rule_file(data, file="m.RUL")
    assert len(rules.records) == 2 and rules.records[1].get("NAME") == "lost"
    assert [(i.code, i.severity, i.where) for i in rules.issues] == [
        ("altium.rule.record-malformed", "warning", "m.RUL:2")
    ]
    assert rules.to_bytes() == data


SUMMARY = (
    b"DRC Rules Export File for PCB: board.PcbDoc\r\n"
    b"RuleKind=Width|RuleName=Width|Scope=Board|Minimum=10.00\r\n"
)


def test_summary_form() -> None:
    """Scenario "Summary form"."""
    rules = read_rule_file(SUMMARY)
    assert rules.kind == "summary" and rules.header == "DRC Rules Export File for PCB: board.PcbDoc"
    (record,) = rules.records
    assert record.keys() == ("RuleKind", "RuleName", "Scope", "Minimum")
    assert record.get("Minimum") == "10.00"
    assert rules.to_bytes() == SUMMARY and rules.issues == ()


def test_summary_fixture() -> None:
    data = (DATA / "rules_summary.RUL").read_bytes()
    rules = read_rule_file(data)
    assert rules.kind == "summary" and len(rules.records) == 3
    assert [r.get("RuleKind") for r in rules.records] == ["Width", "Clearance", "ShortCircuit"]
    assert rules.records[2].get("Allowed") == "0" and rules.to_bytes() == data


def test_unknown_form() -> None:
    """Scenario "Unknown form"."""
    with pytest.raises(FormatError, match="not a rule file"):
        read_rule_file(b"hello\n", file="bad.RUL")


def test_empty_and_binary_data_refused() -> None:
    with pytest.raises(FormatError):
        read_rule_file(b"")
    with pytest.raises(FormatError, match="NUL"):
        read_rule_file(b"RULEKIND=A\0")
