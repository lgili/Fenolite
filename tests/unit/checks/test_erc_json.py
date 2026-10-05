# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""ERC violations as issues (capability verification-loop, "ERC findings as issues" and "ERC stage issue
codes"; change c0062)."""

from __future__ import annotations

import ast
import dataclasses
from pathlib import Path

import pytest
from fakes import erc_report, erc_violation

from fenolite.checks import codes, drc_json, erc_json
from fenolite.checks.codes import ERC_FINDING, ISSUE_CODES, issue, table_key, type_suffix
from fenolite.checks.erc_json import finding_issues, finding_types, type_code

MM = 1_000_000


def test_ref_pin_location() -> None:
    report = erc_report(erc_violation("pin_not_connected", where="U1-2", description="Pin not connected"))
    (found,) = finding_issues(report, oracle="kicad")
    assert (found.code, found.severity, found.where) == ("kicad.erc.pin-not-connected", "error", "U1-2")
    assert found.message == "pin_not_connected: Pin not connected"


def test_item_without_a_location() -> None:
    at = (139_700_000, 59_690_000)
    (root,) = finding_issues(erc_report(erc_violation("x", at=at)), oracle="kicad")
    assert root.where == "/@139.7,59.69"
    (child,) = finding_issues(erc_report(erc_violation("x", at=at, sheet="/Child/")), oracle="kicad")
    assert child.where == "/Child/@139.7,59.69"


def test_several_items_in_report_order() -> None:
    first = erc_violation("multiple_net_names", where="LED_A", severity="warning")
    second = erc_violation("multiple_net_names", where="", at=(2 * MM, 3 * MM), uid="e2")
    both = dataclasses.replace(first, items=(*first.items, *second.items))
    (found,) = finding_issues(erc_report(both), oracle="kicad")
    assert found.where == "LED_A, /@2,3" and found.severity == "warning"


def test_excluded_and_unknown_severities() -> None:
    report = erc_report(
        erc_violation("a", severity="error", excluded=True),
        erc_violation("b", severity="fatal"),
        erc_violation("c", severity="warning"),
    )
    assert [i.severity for i in finding_issues(report, oracle="kicad")] == ["info", "error", "warning"]


def test_one_issue_per_violation_in_report_order() -> None:
    report = erc_report(erc_violation("b"), erc_violation("a"), erc_violation("b", uid="e2"))
    assert [i.code for i in finding_issues(report, oracle="fake")] == [
        "fake.erc.b",
        "fake.erc.a",
        "fake.erc.b",
    ]
    assert finding_issues(erc_report(), oracle="fake") == ()


def test_codes_and_types() -> None:
    assert type_code("kicad", "pin_not_connected") == "kicad.erc.pin-not-connected"
    assert type_code("kicad", "Lib Symbol__Issues!") == "kicad.erc.lib-symbol-issues"
    assert type_code("kicad", "") == "kicad.erc.unknown"
    assert type_code("kicad", "position_unscaled") == "kicad.erc.type-position-unscaled"
    report = erc_report(erc_violation("pin_not_driven"), erc_violation("lib_symbol_issues"))
    assert finding_types(report, oracle="kicad") == {
        "kicad.erc.lib-symbol-issues": "lib_symbol_issues",
        "kicad.erc.pin-not-driven": "pin_not_driven",
    }


def test_codes_share_the_suffix_rule_with_drc() -> None:
    for raw in ("shorting_items", "A  b", "--x--", "", "ÜBER", "net_conflict"):
        suffix = type_suffix(raw)
        assert drc_json.type_code("kicad", raw) == f"kicad.drc.{suffix}"
        assert type_code("kicad", raw) == f"kicad.erc.{suffix}"
    assert type_suffix("--x--") == "x" and type_suffix("") == "unknown" and type_suffix("ÜBER") == "ber"
    assert drc_json.type_code("kicad", "parity_unchecked") == "kicad.drc.type-parity-unchecked"
    assert "parity-unchecked" in drc_json.RESERVED_SUFFIXES


def test_codes_table_rows() -> None:
    assert ISSUE_CODES[ERC_FINDING] == ("error", "warning", "info") and ERC_FINDING == "<oracle>.erc.<type>"
    assert ISSUE_CODES["<oracle>.drc.parity-unchecked"] == ("warning",)
    assert table_key("kicad.erc.pin-not-connected") == ERC_FINDING
    assert table_key("kicad.drc.parity-unchecked") == "<oracle>.drc.parity-unchecked"
    assert table_key("erc.lite.floating-pin") == "erc.lite.floating-pin"
    for severity in ("error", "warning", "info"):
        made = issue("kicad.erc.pin-not-connected", "m", severity=severity)  # type: ignore[arg-type]
        assert (made.code, made.severity) == ("kicad.erc.pin-not-connected", severity)
    assert issue("kicad.drc.parity-unchecked", "m").severity == "warning"
    with pytest.raises(ValueError):
        issue("kicad.drc.parity-unchecked", "m", severity="error")
    for rule in ("output-conflict", "power-undriven", "floating-pin"):
        assert f"erc.lite.{rule}" in ISSUE_CODES  # the three rules keep their codes


def test_codes_no_literal_in_the_mapping_module() -> None:
    tree = ast.parse(Path(erc_json.__file__).read_text(encoding="utf-8"))
    literals = [n.value for n in ast.walk(tree) if isinstance(n, ast.Constant) and isinstance(n.value, str)]
    assert not [text for text in literals if ".erc." in text and " " not in text and "<" not in text]
    assert codes.erc_code("kicad", "x") == "kicad.erc.x"


def test_paths_removed_from_messages() -> None:
    home = str(Path.home())
    report = erc_report(
        erc_violation("lib_symbol_issues", description=f"library /tmp/fenolite-kicad-x/lib and {home}/libs"),
        source="/tmp/fenolite-kicad-x/board.kicad_sch",
    )
    (found,) = finding_issues(report, oracle="kicad")
    assert "<tmp>/lib" in found.message and "~/libs" in found.message
    assert "/tmp/fenolite" not in found.message and home not in found.message
