# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The ``drc.kicad`` stage with a fake oracle (capability verification-loop, "DRC stage and the rules
canary", as modified by c0020: findings are mapped whenever a report exists)."""

from __future__ import annotations

from pathlib import Path

from fakes import FakeOracle, outcome, project, report, violation

from fenolite.backends.base import DrcItem, DrcViolation, SkippedFile
from fenolite.backends.kicad.pcb import read_board
from fenolite.checks.drc import drc_stage
from fenolite.core.coords import Point
from fenolite.core.evidence import Level

TWO_LAYER = Path(__file__).resolve().parents[2] / "data" / "kicad" / "board" / "two_layer.kicad_pcb"

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
    "parity",
    "parity_judged",
    "types",
    "limits",
}


def test_drc_stage_fired_counts_and_summary() -> None:
    drc = report(
        violation("clearance"),
        violation("track_dangling", "warning"),
        violation("clearance", uid="u2"),
        unconnected=(violation("unconnected_items"),),
    )
    result = drc_stage(FakeOracle(outcome("fired", drc=drc)), project(), built=True)
    assert result.status == "errors"
    assert sorted((i.code, i.severity, i.where) for i in result.issues) == [
        ("fake.drc.clearance", "error", "@0,0"),
        ("fake.drc.clearance", "error", "@0,0"),
        ("fake.drc.track-dangling", "warning", "@0,0"),
        ("fake.drc.unconnected-items", "error", "@0,0"),
    ]
    assert result.summary["types"] == {
        "fake.drc.clearance": "clearance",
        "fake.drc.track-dangling": "track_dangling",
        "fake.drc.unconnected-items": "unconnected_items",
    }
    assert set(result.summary) == SUMMARY_KEYS
    assert result.summary["violations"] == 3 and result.summary["unconnected"] == 1
    assert result.summary["by_type"] == {"clearance": 2, "track_dangling": 1}
    assert result.summary["by_severity"] == {"error": 2, "warning": 1}
    assert result.summary["tool_writes"] == ["a.kicad_prl", "z.kicad_prl"]
    assert result.summary["violations_judged"] is True
    assert result.evidence.level == Level.KICAD_VERIFIED


def test_drc_stage_empty_report_is_clean() -> None:
    result = drc_stage(FakeOracle(outcome("fired")), project(), built=True)
    assert result.status == "ok" and result.issues == ()
    assert result.summary["violations_judged"] is True and result.summary["types"] == {}


def test_drc_stage_findings_mapped() -> None:
    design = read_board(TWO_LAYER.read_text(encoding="utf-8"), file=TWO_LAYER.name)
    assert design.board is not None
    refs = {c.id: c.ref for c in design.circuit.components}
    r1 = next(fp for fp in design.board.footprints if refs[fp.component_id] == "R1")
    pad = next(p for p in r1.pads if p.number == "2")
    short = DrcViolation(
        "shorting_items", "short", "error", (DrcItem(pad.native_ids["kicad"], "Pad", Point(0, 0)),)
    )
    oracle = FakeOracle(outcome("fired", drc=report(short)), name="kicad")
    result = drc_stage(oracle, project(), built=False, design=design)
    (found,) = result.issues
    assert (found.code, found.severity, found.where) == ("kicad.drc.shorting-items", "error", "R1-2")
    assert result.summary["types"] == {"kicad.drc.shorting-items": "shorting_items"}
    assert result.summary["violations_judged"] is True and result.status == "errors"


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
    assert result.summary["violations_judged"] is False and result.summary["types"] == {}


def test_drc_stage_timeout_is_retryable() -> None:
    result = drc_stage(FakeOracle(outcome("inconclusive", "no-report", timeout=True)), project(), built=False)
    (found,) = result.issues
    assert found.code == "check.oracle-failed" and found.retryable and "timed out" in found.message


# -- parity findings (capability verification-loop, "Parity findings"; change c0062)


def test_drc_stage_parity_entries_are_findings() -> None:
    conflict = violation("net_conflict", "warning", uid="p1")
    drc = report(violation("clearance"), parity=(conflict,))
    oracle = FakeOracle(outcome("fired", drc=drc, parity_judged=True))
    result = drc_stage(oracle, project(schematic=True), built=True)
    assert ("fake.drc.net-conflict", "warning") in [(i.code, i.severity) for i in result.issues]
    assert result.summary["parity"] == 1 and result.summary["parity_judged"] is True
    assert result.summary["violations"] == 1  # the parity entry is counted apart from the violations
    assert result.summary["types"]["fake.drc.net-conflict"] == "net_conflict"  # type: ignore[index]
    assert not [i for i in result.issues if i.code == "fake.drc.parity-unchecked"]
    assert result.evidence.level == Level.KICAD_VERIFIED


def test_drc_stage_parity_asked_for_and_not_judged() -> None:
    line = "Error: Expecting kicad_sch in '<tmp>/board.kicad_sch', line 2, offset 1."
    oracle = FakeOracle(outcome("fired", parity_judged=False, message=line))
    result = drc_stage(oracle, project(schematic=True), built=True)
    (unchecked,) = [i for i in result.issues if i.code == "fake.drc.parity-unchecked"]
    assert unchecked.severity == "warning" and unchecked.where == "board.kicad_sch"
    assert unchecked.message == f"the board was not compared with its schematic: {line}"
    assert result.summary["parity_judged"] is False and result.summary["parity"] == 0
    assert (
        result.status == "ok" and result.evidence.level == Level.KICAD_VERIFIED
    )  # the copper verdict stands


def test_drc_stage_project_without_a_schematic_has_no_parity_verdict() -> None:
    result = drc_stage(FakeOracle(outcome("fired")), project(), built=True)
    assert result.summary["parity_judged"] is False and result.summary["parity"] == 0
    assert not [i for i in result.issues if i.code.endswith("parity-unchecked")]


def test_drc_stage_no_report_gives_no_parity_verdict() -> None:
    result = drc_stage(FakeOracle(outcome(missing=True)), project(schematic=True), built=True)
    assert [i.code for i in result.issues if i.code.startswith("check.")] == ["check.oracle-failed"]
    assert not [i for i in result.issues if i.code.endswith("parity-unchecked")]
    assert result.summary["parity_judged"] is False
