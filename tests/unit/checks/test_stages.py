# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The ``check`` pipeline with fakes (capability verification-loop, "Check stages and statuses" and
"Evidence per check stage", and "Stages added for findings and round trips"; changes c0013 and c0020)."""

from __future__ import annotations

import dataclasses

import pytest
from fakes import (
    VERIFIED,
    FakeFullOracle,
    FakeOracle,
    FakeValidator,
    netlist,
    netlist_outcome,
    outcome,
    project,
    report,
    rt2_outcome,
    validation,
)

from fenolite.checks import STAGE_ORDER, run_checks
from fenolite.checks.stages import DEFAULT_STAGES, OPT_IN_STAGES, ORACLE_STAGES, StageResult
from fenolite.core.errors import FormatError
from fenolite.core.evidence import Evidence, Level
from fenolite.model.design import Design


def test_stage_order() -> None:
    assert STAGE_ORDER == (
        "model.validate",
        "erc.lite",
        "copper.clearance",
        "drc.kicad",
        "netlist.assignment_compare",
        "roundtrip",
        "roundtrip.rt2",
        "render",
    )
    assert OPT_IN_STAGES == ("roundtrip.rt2", "render")
    assert DEFAULT_STAGES == STAGE_ORDER[:-2]
    assert ORACLE_STAGES == ("drc.kicad", "netlist.assignment_compare", "roundtrip.rt2", "render")
    assert "copper.clearance" in DEFAULT_STAGES  # it runs by default and needs no tool (change c0029)


def test_fixed_order() -> None:
    validator = FakeValidator()
    report = run_checks(
        project=project(),
        stages=("roundtrip", "model.validate"),
        model=None,
        built=False,
        validator=validator,
        oracle=FakeOracle(),
    )
    assert [s.name for s in report.stages] == ["model.validate", "roundtrip"]
    assert len(validator.calls) == 1  # validate runs at most once


def test_skipped_by_design_on_native_input() -> None:
    report = run_checks(
        project=project(),
        stages=STAGE_ORDER[:2] + ("roundtrip",),
        model=None,
        built=False,
        validator=FakeValidator(),
        oracle=None,
    )
    erc = next(s for s in report.stages if s.name == "erc.lite")
    assert (erc.status, erc.reason, erc.issues) == ("skipped", "native-input", ())
    assert erc.evidence.level == Level.UNVERIFIED
    assert {s.name: s.status for s in report.stages if s.name != "erc.lite"} == {
        "model.validate": "ok",
        "roundtrip": "ok",
    }


def test_envelope_evidence_lowest_of_the_stages_that_ran() -> None:
    report = run_checks(
        project=project(),
        stages=("erc.lite", "drc.kicad", "roundtrip"),
        model=None,
        built=False,
        validator=FakeValidator(),
        oracle=FakeOracle(),
    )
    levels = {s.name: s.evidence.level for s in report.stages}
    assert levels == {
        "erc.lite": Level.UNVERIFIED,
        "drc.kicad": Level.KICAD_VERIFIED,
        "roundtrip": Level.INFERRED,
    }
    assert report.evidence.level == Level.INFERRED
    assert {"H-K-PCB-READ", "H-FAKE-DRC"} <= set(report.evidence.hypotheses)


def test_no_stage_ran() -> None:
    validator = FakeValidator(error=FormatError("trailing content", file="board.kicad_pcb", offset=12))
    report = run_checks(
        project=project(), stages=("roundtrip",), model=None, built=False, validator=validator, oracle=None
    )
    (stage,) = report.stages
    assert (stage.status, stage.reason) == ("skipped", "read-refused")
    assert report.evidence.level == Level.UNVERIFIED
    assert [i.code for i in report.issues] == ["check.read-refused"]
    assert report.issues[0].message.startswith("FEN-3004: ")
    assert report.issues[0].where == "board.kicad_pcb:@12"
    assert isinstance(report.read_error, FormatError)


def test_refused_envelope() -> None:
    validator = FakeValidator(
        error=FormatError("bad", file="board.kicad_pcb", locator="/kicad_pcb", offset=3)
    )
    oracle = FakeOracle(outcome("not-applicable"))
    report = run_checks(
        project=project(has_rules=False),
        stages=("drc.kicad", "roundtrip"),
        model=None,
        built=False,
        validator=validator,
        oracle=oracle,
    )
    drc, rt = report.stages
    assert drc.evidence.level == Level.KICAD_VERIFIED
    assert (rt.status, rt.reason) == ("skipped", "read-refused")
    assert report.evidence.level == Level.UNVERIFIED
    assert report.issues[0].where == "board.kicad_pcb:/kicad_pcb:@3"
    assert report.drc_reported


def test_unsupported_format_code_in_message() -> None:
    class Old(FormatError):
        cli_code = "FEN-3003"

    validator = FakeValidator(error=Old("too old", file="board.kicad_pcb"))
    report = run_checks(
        project=project(), stages=("roundtrip",), model=None, built=False, validator=validator, oracle=None
    )
    assert report.issues[0].message == "FEN-3003: too old"


def test_cache_unreadable_skips_both_model_stages() -> None:
    report = run_checks(
        project=project(),
        stages=DEFAULT_STAGES,
        model=None,
        built=True,
        validator=FakeValidator(),
        oracle=FakeOracle(),
        cache_error="board.json: Expecting value",
    )
    statuses = {s.name: (s.status, s.reason) for s in report.stages}
    assert statuses["model.validate"] == ("skipped", "cache-unreadable")
    assert statuses["erc.lite"] == ("skipped", "cache-unreadable")
    assert statuses["roundtrip"][0] == "ok" and statuses["drc.kicad"][0] == "ok"
    assert report.issues[0].code == "check.cache-unreadable" and report.issues[0].severity == "warning"
    assert report.evidence.level == Level.UNVERIFIED  # a skipped model stage counts


def test_built_input_uses_the_cache_model() -> None:
    validator = FakeValidator(error=FormatError("bad", file="board.kicad_pcb"))
    model = Design.new("built", seed=0)
    report = run_checks(
        project=project(),
        stages=("model.validate", "erc.lite"),
        model=model,
        built=True,
        validator=validator,
        oracle=None,
    )
    assert [s.status for s in report.stages] == ["ok", "ok"]
    assert validator.calls == []  # neither stage needs the board read on built input


def test_issues_follow_input_then_stage_order() -> None:
    validator = FakeValidator(result=validation(passed=False, difference="/kicad_pcb/segment[0]"))
    oracle = FakeOracle(outcome("inconclusive", "selector-unproven"))
    report = run_checks(
        project=project(), stages=DEFAULT_STAGES, model=None, built=False, validator=validator, oracle=oracle
    )
    # the fake validator is no rules source, so the copper stage says so (change c0029)
    assert [i.code for i in report.issues] == [
        "copper.rules-incomplete",
        "fake.drc.rules-unchecked",
        "check.rt1-failed",
    ]


def test_stage_result_json_and_immutability() -> None:
    result = StageResult("roundtrip", "ok", VERIFIED, summary={"level": "RT1"})
    assert result.to_json() == {
        "name": "roundtrip",
        "status": "ok",
        "reason": "",
        "evidence": {"level": "KICAD-VERIFIED", "oracle": "fake 1.0", "hypotheses": ["H-FAKE-DRC"]},
        "summary": {"level": "RT1"},
    }
    with pytest.raises(dataclasses.FrozenInstanceError):
        result.status = "errors"  # type: ignore[misc]
    assert StageResult("x", "skipped", Evidence()).evidence.level == Level.UNVERIFIED


# -- stages added by c0020


def _full(**kwargs: object) -> FakeFullOracle:
    return FakeFullOracle(**kwargs)  # type: ignore[arg-type]


def test_new_stages_skip_on_a_refused_read() -> None:
    validator = FakeValidator(error=FormatError("bad", file="board.kicad_pcb"))
    oracle = _full()
    checked = run_checks(
        project=project(),
        stages=("netlist.assignment_compare", "roundtrip.rt2"),
        model=None,
        built=False,
        validator=validator,
        oracle=oracle,
    )
    assert [(s.name, s.status, s.reason) for s in checked.stages] == [
        ("netlist.assignment_compare", "skipped", "read-refused"),
        ("roundtrip.rt2", "skipped", "read-refused"),
    ]
    assert [i.code for i in checked.issues] == ["check.read-refused"]
    assert oracle.calls == [] and len(validator.calls) == 1


def test_new_stages_skip_an_oracle_without_the_operation() -> None:
    checked = run_checks(
        project=project(),
        stages=("netlist.assignment_compare", "roundtrip", "roundtrip.rt2"),
        model=None,
        built=False,
        validator=FakeValidator(),
        oracle=FakeOracle(),
    )
    reasons = {s.name: (s.status, s.reason) for s in checked.stages}
    assert reasons["netlist.assignment_compare"] == ("skipped", "unsupported-oracle")
    assert reasons["roundtrip.rt2"] == ("skipped", "unsupported-oracle")
    # only the stage that ran counts in the envelope
    assert checked.evidence.level == Level.INFERRED and checked.issues == ()


def test_new_stages_run_with_one_read() -> None:
    validator = FakeValidator()
    empty = report()
    oracle = _full(
        netlist_result=netlist_outcome(netlist("export")),
        rt2_result=rt2_outcome((empty, empty), empty),
    )
    checked = run_checks(
        project=project(),
        stages=STAGE_ORDER[:-1],  # render needs a plotter (c0024)
        model=None,
        built=False,
        validator=validator,
        oracle=oracle,
    )
    assert [s.name for s in checked.stages] == list(STAGE_ORDER[:-1])
    statuses = {s.name: s.status for s in checked.stages}
    assert statuses["netlist.assignment_compare"] == "ok" and statuses["roundtrip.rt2"] == "ok"
    assert len(validator.calls) == 1
    assert len(oracle.boards) == 1  # the netlist stage got the board model of that one read


def test_drc_stage_gets_the_board_model() -> None:
    validator = FakeValidator()
    checked = run_checks(
        project=project(), stages=("drc.kicad",), model=None, built=False, validator=validator,
        oracle=FakeOracle(),
    )  # fmt: skip
    assert len(validator.calls) == 1 and checked.stages[0].summary["violations_judged"] is True
