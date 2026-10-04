# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The ``copper.clearance`` stage (capability verification-loop, "Copper clearance stage" and "Stages added
for findings and round trips"; change c0029). The stage tests use fakes; the command tests run
``fenolite check`` without any ``kicad-cli``."""

from __future__ import annotations

import dataclasses
import subprocess
from pathlib import Path

import pytest
from _checkcli import hide_kicad, run
from _coppercheck import Copper, bridged_project, mm, rect_entry
from _projects import authored_project
from fakes import READ_EVIDENCE, FakeRulesValidator, FakeValidator, validation

from fenolite.backends.base import BoardFrame, DesignRules, DesignRulesSource, ProjectSet
from fenolite.checks import DEFAULT_STAGES, ORACLE_STAGES, run_checks
from fenolite.checks.copper import EVIDENCE, STAGE, copper_stage
from fenolite.checks.stages import StageResult
from fenolite.core.coords import Point
from fenolite.core.errors import FormatError
from fenolite.core.evidence import Evidence, Level
from fenolite.model.design import Design

RULES_EVIDENCE = Evidence(Level.INFERRED, hypotheses=("H-K-PRO-PATTERNS",))


def project(tmp: Path = Path("/nonexistent")) -> ProjectSet:
    return ProjectSet(root=tmp, board="board.kicad_pcb", files={"board.kicad_pcb": tmp / "board.kicad_pcb"})


def two_tracks(edge_gap: int) -> Copper:
    made = Copper()
    made.track("A", Point(0, 0), Point(mm(10), 0))
    made.track("B", Point(0, 250_000 + edge_gap), Point(mm(10), 250_000 + edge_gap))
    return made


def stage_of(design: Design, validator: FakeValidator) -> StageResult:
    validator.result = validation(design)
    report = run_checks(
        project=project(), stages=(STAGE,), model=None, built=False, validator=validator, oracle=None
    )
    (stage,) = report.stages
    assert len(validator.calls) == 1
    return stage


def codes(stage: StageResult) -> list[str]:
    return [issue.code for issue in stage.issues]


def test_stage_is_a_default_stage_without_a_tool() -> None:
    assert STAGE in DEFAULT_STAGES and STAGE not in ORACLE_STAGES
    assert DEFAULT_STAGES.index("erc.lite") + 1 == DEFAULT_STAGES.index(STAGE)
    assert DEFAULT_STAGES.index(STAGE) + 1 == DEFAULT_STAGES.index("drc.kicad")


def test_refused_read() -> None:
    """Scenario "Refused read": the stage is skipped and gives no issue."""
    validator = FakeRulesValidator(error=FormatError("bad board", file="board.kicad_pcb"))
    report = run_checks(
        project=project(), stages=(STAGE,), model=None, built=False, validator=validator, oracle=None
    )
    (stage,) = report.stages
    assert (stage.status, stage.reason, stage.issues) == ("skipped", "read-refused", ())
    assert [i.code for i in report.issues] == ["check.read-refused"] and validator.asked == []
    direct = copper_stage(None, project=project(), rules_source=None, frame=None, evidence=Evidence())
    assert (direct.status, direct.reason) == ("skipped", "read-refused")


def test_no_source() -> None:
    """Scenario "Validator without a rules source": the rules and the pads are reported as unjudged."""
    made = Copper()
    made.pad("R1", "1", "A", rect_entry(0, 0, mm(1), mm(1)))
    made.pad("R1", "2", "B", rect_entry(mm(2), 0, mm(3), mm(1)))
    plain = FakeValidator()
    assert not isinstance(plain, DesignRulesSource) and not isinstance(plain, BoardFrame)
    stage = stage_of(made.build(), plain)
    assert codes(stage) == ["copper.item-unsupported", "copper.rules-incomplete"]
    assert all(issue.severity == "warning" for issue in stage.issues)
    unsupported, incomplete = stage.issues
    assert "2 pad item(s)" in unsupported.message and "no rules source" in incomplete.message
    assert stage.status == "ok" and stage.evidence.level is Level.UNVERIFIED
    assert stage.summary["rules"] == {"min_clearance": None, "opaque_clearance_rules": 0, "unread": []}
    assert stage.summary["unsupported"] == {"pad": 2}


def test_rules_and_pads_come_from_the_validator() -> None:
    made = two_tracks(mm(0.15))
    made.pad("R1", "1", "A", rect_entry(0, mm(3), mm(1), mm(4)))
    design = made.build()
    checked = dataclasses.replace(design)  # the design the rules source gives back
    validator = FakeRulesValidator(
        rules=DesignRules(checked, min_clearance=mm(0.2), evidence=RULES_EVIDENCE), pads=tuple(made.pads)
    )
    assert isinstance(validator, DesignRulesSource) and isinstance(validator, BoardFrame)
    stage = stage_of(design, validator)
    assert [kind for kind, _ in validator.asked] == ["rules", "pads"]
    assert validator.asked[1][1] is checked  # the pads are those of the checked design
    assert codes(stage) == ["copper.clearance"] and stage.status == "errors"
    assert "floor" in stage.issues[0].message
    assert stage.summary["rules"] == {"min_clearance": mm(0.2), "opaque_clearance_rules": 0, "unread": []}
    assert stage.summary["items"] == {"pad": 1, "track": 2} and stage.summary["clearance"] == 1
    assert stage.evidence.level is Level.INFERRED
    assert set(stage.evidence.hypotheses) == {*EVIDENCE.hypotheses, "H-K-PCB-READ", "H-K-PRO-PATTERNS"}


def test_switches_come_from_the_rules_source() -> None:
    made = two_tracks(mm(0.15))
    made.rule("tight", mm(0.1))
    design = made.build()
    lowered = DesignRules(design, min_clearance=mm(0.2), evidence=RULES_EVIDENCE)
    assert codes(stage_of(design, FakeRulesValidator(rules=lowered))) == []
    raised = dataclasses.replace(lowered, floor_over_rules=True)
    assert codes(stage_of(design, FakeRulesValidator(rules=raised))) == ["copper.clearance"]


def test_incomplete_rules_lower_the_stage() -> None:
    design = two_tracks(mm(1)).build()
    rules = DesignRules(
        design,
        opaque_clearance_rules=2,
        unread=(("board.kicad_dru", "line 3: bad"), ("board.kicad_pro", "not JSON")),
        evidence=RULES_EVIDENCE,
    )
    stage = stage_of(design, FakeRulesValidator(rules=rules))
    assert codes(stage) == ["copper.rules-incomplete"] * 3 and stage.status == "ok"
    messages = sorted(issue.message for issue in stage.issues)
    assert messages[0].startswith("2 clearance rule(s)")
    assert "board.kicad_dru was not read: line 3: bad" in messages
    assert "board.kicad_pro was not read: not JSON" in messages
    assert stage.evidence.level is Level.UNVERIFIED
    assert stage.summary["rules"] == {
        "min_clearance": None,
        "opaque_clearance_rules": 2,
        "unread": ["board.kicad_dru", "board.kicad_pro"],
    }


def test_clean_stage_evidence_is_the_lowest_input() -> None:
    design = two_tracks(mm(1)).build()
    stage = stage_of(design, FakeRulesValidator())
    assert stage.status == "ok" and stage.evidence.level is Level.INFERRED and codes(stage) == []
    without_files = FakeRulesValidator(rules=DesignRules(design))  # neither file was read
    assert stage_of(design, without_files).evidence.level is Level.UNVERIFIED
    assert READ_EVIDENCE.level is Level.INFERRED


def test_stage_issues_are_sorted_and_json_ready() -> None:
    made = two_tracks(-mm(0.1))
    made.track("C", Point(0, mm(5)), Point(mm(10), mm(5)))
    made.track("D", Point(0, mm(5.1)), Point(mm(10), mm(5.1)))
    stage = stage_of(made.build(), FakeRulesValidator())
    keys = [(i.code, i.where, i.message) for i in stage.issues]
    assert keys == sorted(keys) and codes(stage) == ["copper.short", "copper.short"]
    data = stage.to_json()
    assert data["name"] == STAGE and data["status"] == "errors"
    assert data["summary"]["shorts"] == 2  # type: ignore[index]


# --- the command, without any kicad-cli -----------------------------------------------------------

TWO_LAYER = Path(__file__).resolve().parents[2] / "data" / "kicad" / "board" / "two_layer.kicad_pcb"


def _no_tool(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """No ``kicad-cli`` anywhere, and any subprocess fails the test."""
    hide_kicad(monkeypatch, tmp_path)

    def refuse(*args: object, **kwargs: object) -> None:
        raise AssertionError("a subprocess was started")

    monkeypatch.setattr(subprocess, "run", refuse)
    monkeypatch.setattr(subprocess, "Popen", refuse)


def _copper(envelope: dict[str, object]) -> dict[str, object]:
    (stage,) = envelope["result"]["stages"]  # type: ignore[index]
    assert stage["name"] == STAGE
    return stage  # type: ignore[no-any-return]


def test_bridging_track_caught_without_kicad(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Scenario "Bridging track caught without KiCad"."""
    root = bridged_project(tmp_path, major=10)
    _no_tool(monkeypatch, tmp_path)
    code, env, err, _ = run(monkeypatch, tmp_path, "check", str(root), "--stages", STAGE)
    assert code == 5 and err["code"] == "FEN-5001"
    shorts = [i for i in env["issues"] if i["code"] == "copper.short"]
    (short,) = [i for i in shorts if "R1-2" in i["where"]]
    assert short["severity"] == "error" and "VIN" in short["message"] and "F.Cu" in short["message"]
    # the added track also meets the LED_A track that leaves pad 2: one more short, between two tracks
    assert len(shorts) == 2 and all("segment" in i["where"] for i in shorts)
    stage = _copper(env)
    assert stage["status"] == "errors" and stage["summary"]["shorts"] == 2  # type: ignore[index]


def test_clean_authored_project(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Scenario "Clean authored project": the template's ``Default`` class and the project's rule are in
    force, every pad is shaped, and nothing is too close."""
    root = authored_project(tmp_path, major=10, built=True)
    _no_tool(monkeypatch, tmp_path)
    code, env, _, _ = run(monkeypatch, tmp_path, "check", str(root), "--stages", STAGE)
    stage = _copper(env)
    assert code == 0 and stage["status"] == "ok", env["issues"]
    assert not [i for i in env["issues"] if i["code"] in ("copper.short", "copper.clearance")]
    summary = stage["summary"]
    assert summary["unsupported"] == {} and summary["max_clearance"] > 0  # type: ignore[index,operator]
    assert summary["rules"]["unread"] == [] and summary["rules"]["opaque_clearance_rules"] == 0  # type: ignore[index]
    assert stage["evidence"]["level"] == "INFERRED"  # type: ignore[index]


def test_copper_stage_needs_no_kicad_cli(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Scenario "Copper stage needs no kicad-cli": the authored ``GND_B`` fill of ``two_layer.kicad_pcb``
    covers pad 2 of ``D1``, which is on ``LED_A``."""
    _no_tool(monkeypatch, tmp_path)
    code, env, err, _ = run(monkeypatch, tmp_path, "check", str(TWO_LAYER), "--stages", STAGE)
    assert code == 5 and err["code"] == "FEN-5001"  # findings, not FEN-6001: the stage needs no tool
    stage = _copper(env)
    assert stage["status"] == "errors"
    (short,) = [i for i in env["issues"] if i["code"] == "copper.short"]
    assert "D1-2" in short["where"]
    for text in ("GND", "LED_A", "B.Cu"):
        assert text in short["message"]


def test_stage_output_is_repeatable(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    from _checkcli import without_elapsed

    _no_tool(monkeypatch, tmp_path)
    first = run(monkeypatch, tmp_path, "check", str(TWO_LAYER), "--stages", STAGE)[3]
    second = run(monkeypatch, tmp_path, "check", str(TWO_LAYER), "--stages", STAGE)[3]
    assert without_elapsed(first) == without_elapsed(second)
