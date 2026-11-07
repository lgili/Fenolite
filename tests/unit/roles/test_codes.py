# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The issue codes of the net roles and their severities (change c0222; capability net-roles, "Role issue
codes" and "Finding severities")."""

from __future__ import annotations

from pathlib import Path

import pytest
from _roleboards import build, read

from fenolite.cli import explain
from fenolite.model.canonical import load_dir
from fenolite.roles.codes import ISSUE_CODES, TOPOLOGICAL, issue, severity
from fenolite.roles.judge import run

SEVENTEEN = {
    "roles.loop-area", "roles.loop-open", "roles.gate-loop", "roles.gate-return-shared", "roles.kelvin-outer",
    "roles.kelvin-shared", "roles.kelvin-apart", "roles.near-switching", "roles.width-current",
    "roles.section-current", "roles.via-current", "roles.return-gap", "roles.limit-missing",
    "roles.current-missing", "roles.ambiguous", "roles.unconfirmed", "roles.declared-differs",
}  # fmt: skip


COPPER = {
    "roles.copper-skipped", "roles.copper-blocked", "roles.copper-extra", "roles.copper-kept",
    "roles.copper-worse", "roles.copper-placement", "roles.copper-narrow", "roles.corridor-blocked",
}  # fmt: skip
"""The eight codes of the role copper (change c0243, decision 14)."""


def test_codes_in_the_table() -> None:
    assert set(ISSUE_CODES) == SEVENTEEN | COPPER and len(ISSUE_CODES) == 25
    assert ISSUE_CODES["roles.kelvin-outer"] == ("warning", "error")
    assert "roles.input-missing" not in ISSUE_CODES
    codes = explain.all_codes()
    for code, severities in ISSUE_CODES.items():
        assert severities and set(severities) <= {"error", "warning", "info"}
        found = explain.explain(code)
        assert found is not None and found.kind == "issue" and found.meaning and found.fix, code
        assert set(codes[code]) == set(severities)


def test_an_issue_outside_the_table_is_refused() -> None:
    with pytest.raises(ValueError, match="not a roles issue code"):
        issue("roles.input-missing", "x")
    with pytest.raises(ValueError, match="no severity"):
        issue("roles.unconfirmed", "x", severity="error")
    assert issue("roles.loop-area", "x").severity == "warning"


@pytest.mark.parametrize("code", sorted(SEVENTEEN))  # the findings; the copper codes take no severity rule
def test_severity_rule(code: str) -> None:
    for limit in ("profile", "override", "requirements", "rule"):
        assert severity(code, source="inferred", limit_source=limit) != "error"
    expected = "error" if "error" in ISSUE_CODES[code] else ISSUE_CODES[code][0]
    for source in ("confirmed", "declared"):
        assert severity(code, source=source, limit_source="override") == expected
        assert severity(code, source=source, limit_source="requirements") == expected
        stated_default = severity(code, source=source, limit_source="profile")
        assert stated_default == (expected if code in TOPOLOGICAL else ISSUE_CODES[code][0])


def test_unconfirmed_roles_warn_only(tmp_path: Path) -> None:
    built = build("buck_shunt", "bad", tmp_path / "out")
    design, pads = read(built)
    model = load_dir(built.out / ".fenolite")
    judged = run(design, pads, circuit=model.circuit, currents={"VOUT": 2000, "VL": 2000, "SW": 2000})
    roles = [found for found in judged.issues if found.code.startswith("roles.")]
    assert roles and all(found.severity in ("warning", "info") for found in roles)
    (unconfirmed,) = [found for found in roles if found.code == "roles.unconfirmed"]
    count = len(judged.resolved.roles.nets) + len(judged.resolved.roles.loops)
    count += len(judged.resolved.roles.gates) + len(judged.resolved.roles.kelvins)
    assert unconfirmed.message.startswith(f"{count} inferred role(s) and group(s)")


def test_copper_codes_in_the_table() -> None:
    """Scenario "Copper codes in the table" (change c0243)."""
    assert ISSUE_CODES["roles.copper-worse"] == ("error",)
    assert ISSUE_CODES["roles.copper-skipped"] == ("info", "warning")
    for code in COPPER:
        found = explain.explain(code)
        assert found is not None and found.meaning and found.fix, code
