# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The ``drc.kicad`` stage with a fake oracle (capability verification-loop, "DRC stage and the rules
canary"; change c0013)."""

from __future__ import annotations

from fakes import FakeOracle, outcome, project, report, violation

from fenolite.backends.base import SkippedFile
from fenolite.checks.drc import drc_stage
from fenolite.core.evidence import Level

SUMMARY_KEYS = {
    "tool_version",
    "canary",
    "canary_reason",
    "canary_removed",
    "violations",
    "by_type",
    "by_severity",
    "unconnected",
    "excluded",
    "tool_writes",
    "violations_judged",
}


def test_drc_stage_fired_counts_and_summary() -> None:
    drc = report(
        violation("clearance"),
        violation("track_dangling", "warning"),
        violation("clearance", uid="u2"),
        unconnected=(violation("unconnected_items"),),
    )
    result = drc_stage(FakeOracle(outcome("fired", drc=drc)), project(), built=True)
    assert result.status == "ok" and result.issues == ()
    assert set(result.summary) == SUMMARY_KEYS
    assert result.summary["violations"] == 3 and result.summary["unconnected"] == 1
    assert result.summary["by_type"] == {"clearance": 2, "track_dangling": 1}
    assert result.summary["by_severity"] == {"error": 2, "warning": 1}
    assert result.summary["tool_writes"] == ["a.kicad_prl", "z.kicad_prl"]
    assert result.summary["violations_judged"] is False
    assert result.evidence.level == Level.KICAD_VERIFIED


def test_drc_stage_absent_built_is_an_error() -> None:
    result = drc_stage(FakeOracle(outcome("absent")), project(), built=True)
    assert [(i.code, i.severity) for i in result.issues] == [("fake.drc.rules-not-loaded", "error")]
    assert result.status == "errors" and result.evidence.level == Level.UNVERIFIED


def test_drc_stage_absent_native_is_info() -> None:
    result = drc_stage(FakeOracle(outcome("absent")), project(), built=False)
    assert [(i.code, i.severity) for i in result.issues] == [("fake.drc.rules-not-loaded", "info")]
    assert result.status == "ok" and result.evidence.level == Level.UNVERIFIED


def test_drc_stage_rules_without_project() -> None:
    result = drc_stage(FakeOracle(outcome("not-applicable")), project(has_project=False), built=False)
    assert [i.code for i in result.issues] == ["fake.drc.rules-not-loaded"]
    assert result.summary["canary"] == "not-applicable"


def test_drc_stage_not_applicable_without_rules() -> None:
    result = drc_stage(FakeOracle(outcome("not-applicable")), project(has_rules=False), built=True)
    assert result.issues == () and result.evidence.level == Level.KICAD_VERIFIED


def test_drc_stage_verdicts_named_by_the_oracle() -> None:
    result = drc_stage(FakeOracle(outcome("inconclusive", "selector-unproven")), project(), built=True)
    (found,) = result.issues
    assert (found.code, found.severity) == ("fake.drc.rules-unchecked", "warning")
    assert "selector-unproven" in found.message
    assert result.evidence.level == Level.UNVERIFIED


def test_drc_stage_skipped_copy_does_not_lower_evidence() -> None:
    skipped = (SkippedFile("../Other.pretty", "outside-root"),)
    result = drc_stage(FakeOracle(outcome("fired")), project(skipped=skipped), built=True)
    (found,) = result.issues
    assert (found.code, found.severity, found.where) == ("check.copy-skipped", "info", "../Other.pretty")
    assert result.evidence.level == Level.KICAD_VERIFIED


def test_drc_stage_missing_report() -> None:
    result = drc_stage(FakeOracle(outcome("inconclusive", "no-report", missing=True)), project(), built=True)
    assert [i.code for i in result.issues] == ["check.oracle-failed"]
    assert "no board" in result.issues[0].message and not result.issues[0].retryable
    assert result.summary["violations"] == 0 and result.evidence.level == Level.UNVERIFIED


def test_drc_stage_timeout_is_retryable() -> None:
    result = drc_stage(FakeOracle(outcome("inconclusive", "no-report", timeout=True)), project(), built=False)
    (found,) = result.issues
    assert found.code == "check.oracle-failed" and found.retryable and "timed out" in found.message
