# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Check severities in the DSL (capability design-dsl, "Check severities in the DSL"; change c0114)."""

from __future__ import annotations

import pytest

from fenolite.backends.altium import rulemap
from fenolite.dsl import Design, DslError, to_model
from fenolite.model.rules import RuleKind, RuleSeverity


def test_a_severity_reaches_the_model() -> None:
    """Scenario "A severity reaches the model"."""
    design = Design("sev")
    design.rules.severity("kicad.drc.silk-overlap", "ignore")
    rules = to_model(design).rules
    assert rules is not None and rules.severities == {"kicad.drc.silk-overlap": "ignore"}


def test_severities_are_sorted_by_code() -> None:
    design = Design("sev")
    design.rules.severity("kicad.drc.via-dangling", "error")
    design.rules.severity("kicad.drc.clearance", "warning")
    rules = to_model(design).rules
    assert rules is not None and list(rules.severities) == ["kicad.drc.clearance", "kicad.drc.via-dangling"]


def test_no_severity_is_the_default() -> None:
    rules = to_model(Design("sev")).rules
    assert rules is not None and rules.severities == {}


@pytest.mark.parametrize(
    ("code", "level", "message"),
    [
        ("copper.clearance", "warning", r"design\.waive\(\)"),
        ("copper.short", "ignore", r"design\.waive\(\)"),
        ("kicad.drc.silk-overlap", "info", "error, warning, ignore"),
        ("kicad.drc.clearance", "ignore", "clearance-ignored"),
        ("kicad.drc.rules-not-loaded", "ignore", "not the code of a KiCad DRC check"),
        ("kicad.erc.pin-not-connected", "ignore", "not the code of a KiCad DRC check"),
        ("silk_overlap", "ignore", "not the code of a KiCad DRC check"),
        ("kicad.drc.silk_overlap", "ignore", "not the code of a KiCad DRC check"),
    ],
)
def test_refused_severities(code: str, level: str, message: str) -> None:
    """Scenario "Refused severities"."""
    design = Design("sev")
    with pytest.raises(DslError, match=message):
        design.rules.severity(code, level)
    assert design.rules.severities == {}


def test_refused_twice() -> None:
    design = Design("sev")
    design.rules.severity("kicad.drc.via-dangling", "error")
    with pytest.raises(DslError, match="already has the severity 'error'"):
        design.rules.severity("kicad.drc.via-dangling", "error")


def test_clearance_may_be_a_warning() -> None:
    design = Design("sev")
    design.rules.severity("kicad.drc.clearance", "warning")
    assert design.rules.severities == {"kicad.drc.clearance": "warning"}


def test_a_severity_is_no_rule_kind() -> None:
    """The Altium rule table keeps one row per ``RuleKind`` and none for a severity."""
    kinds = set(RuleKind.__args__)  # type: ignore[attr-defined]
    assert sorted(row.neutral for row in rulemap.TABLE) == sorted(kinds)
    assert "severity" not in kinds and set(RuleSeverity.__args__) == {"error", "warning", "ignore"}  # type: ignore[attr-defined]
