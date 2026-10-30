# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The codes of the proposal mode (change c0280; capability routing, "Proposal codes", scenario "Codes
explained")."""

from __future__ import annotations

from pathlib import Path

from fenolite.cli import explain
from fenolite.routing.codes import ISSUE_CODES

PROPOSAL_CODES = {
    "route.proposal-unknown": "error",
    "route.proposal-conflict": "error",
    "route.proposal-open": "warning",
    "route.proposal-findings": "warning",
    "route.proposal-stale": "warning",
    "route.proposal-none": "info",
    "route.proposal-rejected": "info",
    "route.proposal-limit": "info",
}
CONTRACT = Path(__file__).resolve().parents[3] / "docs" / "cli-contract.md"


def test_proposal_codes_explained() -> None:
    """The eight codes have their severities, an ``explain.toml`` entry and a row of the contract."""
    held = {code: severity for code, severity in ISSUE_CODES.items() if code.startswith("route.proposal-")}
    assert held == PROPOSAL_CODES
    page = CONTRACT.read_text(encoding="utf-8")
    entries = explain.entries()
    for code, severity in PROPOSAL_CODES.items():
        assert code in entries and entries[code]["meaning"] and entries[code]["fix"]
        assert f"| `{code}` | {severity} |" in page
