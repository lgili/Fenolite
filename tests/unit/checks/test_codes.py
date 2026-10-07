# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The closed set of check issue codes (capability verification-loop, "Check issue codes", "Findings
stage issue codes" and "Copper stage issue codes"; changes c0013, c0020 and c0029)."""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

from fenolite.checks import STAGE_ORDER, codes
from fenolite.checks.codes import ERC_FINDING, FINDING, ISSUE_CODES, issue, oracle_code, table_key

CHECKS = Path(codes.__file__).resolve().parent
CODE = ("check.", "erc.lite.", "netlist.", "render.", "copper.", "zone.", "parity.", "placement.")
TABLE = {
    "check.read-refused": ("error",),
    "check.cache-unreadable": ("warning",),
    "check.footprint-unresolved": ("error",),
    "check.symbol-unresolved": ("error",),
    "check.rt1-failed": ("error",),
    "check.oracle-failed": ("error",),
    "check.copy-skipped": ("info",),
    "check.report-limit": ("warning",),
    "<oracle>.drc.rules-not-loaded": ("error", "info"),
    "<oracle>.drc.rules-unchecked": ("warning",),
    "<oracle>.drc.parity-unchecked": ("warning",),
    "<oracle>.drc.<type>": ("error", "warning", "info"),
    "<oracle>.erc.<type>": ("error", "warning", "info"),
    "netlist.assignment-differs": ("error",),
    "netlist.uncovered": ("info",),
    "check.rt2-failed": ("error",),
    "check.rt2-unstable": ("info",),
    "erc.lite.output-conflict": ("warning",),
    "erc.lite.power-undriven": ("warning",),
    "erc.lite.floating-pin": ("warning",),
    "render.failed": ("warning",),
    "copper.short": ("error", "info"),
    "copper.clearance": ("error", "warning", "info"),
    "copper.zone-overlap": ("warning", "info"),
    "copper.keepout": ("error",),
    "copper.rules-incomplete": ("warning",),
    "copper.item-unsupported": ("warning",),
    "copper.clearance-unset": ("info",),
    "zone.unfilled": ("warning",),
    "zone.fill-stale": ("warning",),
    "zone.fill-unchecked": ("info",),
    "check.document-missing": ("warning",),
    "check.rta0-failed": ("error",),
    "check.rta1-failed": ("error",),
    "check.rta1-normalised": ("info",),
    "check.rta2-failed": ("error",),
    "check.rta3-failed": ("error",),
    "check.rta3-unwritten": ("info",),
    "check.roundtrip-unjudged": ("info",),
    "parity.missing-footprint": ("error",),
    "parity.extra-footprint": ("error",),
    "parity.duplicate-footprints": ("error",),
    "parity.net-conflict": ("error",),
    "parity.pin-without-pad": ("error", "warning"),
    "parity.footprint-mismatch": ("warning",),
    "parity.oracle-differs": ("warning",),
    "parity.pad-without-pin": ("info",),
    "check.waiver-unmatched": ("warning",),
    "check.exclusion-stale": ("warning",),
    "placement.too-far": ("error", "warning"),
    "placement.rule-unresolved": ("error",),
    "placement.rule-skipped": ("info",),
}


def code_literals(paths: list[Path]) -> set[str]:
    """Every issue-code literal in ``paths``: ``check.*``, ``erc.lite.*`` and ``render.*`` strings, and the
    codes built by ``oracle_code(…, "<suffix>")`` as ``<oracle>.drc.<suffix>``."""
    found: set[str] = set()
    for path in paths:
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            if isinstance(node, ast.Constant) and isinstance(node.value, str):
                text = node.value
                if text in STAGE_ORDER:  # a stage name such as netlist.assignment_compare is no code
                    continue
                if text.startswith(CODE) and " " not in text and text.count(".") >= 1 and text[-1] != ".":
                    found.add(text)
            if (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Name)
                and node.func.id == "oracle_code"
            ):
                suffix = node.args[1] if len(node.args) > 1 else None
                if isinstance(suffix, ast.Constant) and isinstance(suffix.value, str):
                    found.add(f"<oracle>.drc.{suffix.value}")
    return found


def unknown(paths: list[Path]) -> set[str]:
    return {c for c in code_literals(paths) if c not in ISSUE_CODES}


def test_codes_closed_set() -> None:
    sources = sorted(CHECKS.glob("*.py"))
    assert unknown(sources) == set()
    # the finding row is generated from the report's type, never written as a literal
    # ``copper.clearance`` is also a stage name, which ``code_literals`` leaves out
    generated = (FINDING, ERC_FINDING)  # built from the report's type, never written as a literal
    wanted = {
        k for k in TABLE if not k.startswith("erc.lite.") and k not in generated and k not in STAGE_ORDER
    }
    assert code_literals(sources) >= wanted


def test_codes_closed_set_detects_an_unknown_code(tmp_path: Path) -> None:
    module = tmp_path / "rogue.py"
    module.write_text('issue("check.unknown-code", "x")\n', encoding="utf-8")
    assert unknown([module]) == {"check.unknown-code"}


def test_codes_table_severities() -> None:
    assert dict(ISSUE_CODES) == TABLE


def test_codes_oracle_prefix() -> None:
    assert oracle_code("kicad", "rules-unchecked") == "kicad.drc.rules-unchecked"
    assert table_key("kicad.drc.rules-unchecked") == "<oracle>.drc.rules-unchecked"
    assert table_key("check.rt1-failed") == "check.rt1-failed"
    made = issue("kicad.drc.rules-not-loaded", "m", severity="info")
    assert (made.code, made.severity) == ("kicad.drc.rules-not-loaded", "info")


def test_codes_refuse_unknown_codes_and_severities() -> None:
    with pytest.raises(KeyError):
        issue("check.unknown-code", "m")
    with pytest.raises(ValueError):
        issue("check.rt1-failed", "m", severity="warning")


def test_codes_finding_row() -> None:
    assert table_key("kicad.drc.shorting-items") == FINDING == "<oracle>.drc.<type>"
    for severity in ("error", "warning", "info"):
        made = issue("kicad.drc.shorting-items", "m", severity=severity)  # type: ignore[arg-type]
        assert (made.code, made.severity) == ("kicad.drc.shorting-items", severity)
    # a finding code never equals a rules-verdict code
    assert table_key("kicad.drc.type-rules-not-loaded") == FINDING
    assert table_key("kicad.drc.rules-not-loaded") != FINDING
