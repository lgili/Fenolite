# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The ``placement.rules`` stage of ``fenolite check`` (capability verification-loop, "Placement rules
stage"; change c0113). The stage tests use fakes; the command tests run ``fenolite check`` without any
``kicad-cli``."""

from __future__ import annotations

import dataclasses
import subprocess
from pathlib import Path

import pytest
from _buildhelp import blink_variant
from _checkcli import hide_kicad, run
from _placecheck import MM, Layout
from fakes import (
    PCB,
    READ_EVIDENCE,
    SCH,
    FakeDocumentValidator,
    FakeRulesValidator,
    FakeValidator,
    document_set,
    reading,
    validation,
)

from fenolite.backends.base import BoardPad, PlacedExtent, ProjectSet
from fenolite.checks import DEFAULT_STAGES, ORACLE_STAGES, STAGE_ORDER, run_checks
from fenolite.checks.documents import DOCUMENT_STAGES, run_document_checks
from fenolite.checks.placement import EVIDENCE, STAGE, default_pitch, placement_stage
from fenolite.checks.stages import OPT_IN_STAGES, StageResult
from fenolite.core.errors import FormatError, Issue
from fenolite.core.evidence import Evidence, Level
from fenolite.model.design import Design
from fenolite.model.rules import PadSelection, ProximityRule, RuleSet

ROOT = Path(__file__).resolve().parents[3]
TWO_LAYER = ROOT / "tests" / "data" / "kicad" / "board" / "two_layer.kicad_pcb"
ROUTED_PCBDOC = ROOT / "tests" / "data" / "altium" / "routed" / "routed.PcbDoc"
NEAR = '\ndesign.near("led", d1, r1.pad(2), within=mm(5))\n'
ZERO = {"near": {"judged": 0, "failed": 0, "skipped": 0}}


def project(tmp: Path = Path("/nonexistent")) -> ProjectSet:
    return ProjectSet(root=tmp, board="board.kicad_pcb", files={"board.kicad_pcb": tmp / "board.kicad_pcb"})


def layout(c1_x: float = 30) -> Layout:
    made = Layout()
    made.part("U1", ("1", 10, 10, "A"), ("2", 10, 12, "B"), path="U1")
    made.part("C1", ("1", c1_x, 10, "A"), ("2", c1_x, 12, "B"), path="C1")
    return made


def with_rule(design: Design, *, severity: str = "error") -> Design:
    rule = ProximityRule("dec", (PadSelection("C1", "1"),), (PadSelection("U1", "1"),), 2 * MM, severity)  # type: ignore[arg-type]
    assert design.rules is not None
    return dataclasses.replace(design, rules=RuleSet(id=design.rules.id, proximity=(rule,)))


def stage_of(
    validator: FakeValidator, *, model: Design | None, built: bool, cache_error: str = ""
) -> StageResult:
    report = run_checks(
        project=project(),
        stages=(STAGE,),
        model=model,
        built=built,
        validator=validator,
        oracle=None,
        cache_error=cache_error,
    )
    (stage,) = report.stages
    assert len(validator.calls) == 1
    return stage


def test_stage_is_a_default_stage_without_a_tool() -> None:
    assert STAGE == "placement.rules"
    assert STAGE in DEFAULT_STAGES and STAGE not in ORACLE_STAGES and STAGE not in OPT_IN_STAGES
    assert STAGE_ORDER.index("copper.clearance") + 1 == STAGE_ORDER.index(STAGE)
    assert STAGE_ORDER.index(STAGE) + 1 == STAGE_ORDER.index("zone.fill")
    assert DOCUMENT_STAGES.index("copper.clearance") + 1 == DOCUMENT_STAGES.index(STAGE)
    assert DOCUMENT_STAGES.index(STAGE) + 1 == DOCUMENT_STAGES.index("parity")
    assert EVIDENCE.level is Level.INFERRED


def test_built_project_rule_fails_and_measures_are_given() -> None:
    design, pads = layout().build()
    made = layout()
    made.default_class(200_000, 200_000)
    classed, _ = made.build()
    validator = FakeRulesValidator(pads=pads)
    validator.result = validation(classed)
    stage = stage_of(validator, model=with_rule(design), built=True)
    assert stage.status == "errors" and stage.reason == ""
    assert [(i.code, i.severity, i.where) for i in stage.issues] == [("placement.too-far", "error", "C1")]
    assert stage.summary["rules"] == {"near": {"judged": 1, "failed": 1, "skipped": 0}}
    measures = stage.summary["measures"]
    assert isinstance(measures, dict)
    assert measures["nets"] == 2 and measures["hpwl"] == 40 * MM
    assert measures["congestion"]["pitch"] == 400_000 and measures["congestion"]["tracks_per_layer"] == 5
    # a judged rule is Fenolite's own definition: the stage is never above INFERRED
    assert stage.evidence == Evidence.combine(EVIDENCE, READ_EVIDENCE)
    assert [kind for kind, _ in validator.asked] == ["pads", "rules"]


def test_built_project_rule_met_and_a_warning_rule_keeps_the_stage_ok() -> None:
    design, pads = layout(c1_x=11).build()
    validator = FakeRulesValidator(pads=pads)
    validator.result = validation(design)
    stage = stage_of(validator, model=with_rule(design), built=True)
    assert (stage.status, stage.issues) == ("ok", ())
    assert stage.summary["rules"] == {"near": {"judged": 1, "failed": 0, "skipped": 0}}
    far, far_pads = layout().build()
    validator = FakeRulesValidator(pads=far_pads)
    validator.result = validation(far)
    stage = stage_of(validator, model=with_rule(far, severity="warning"), built=True)
    assert stage.status == "ok" and [i.severity for i in stage.issues] == ["warning"]


def test_native_input_is_measured_only() -> None:
    design, pads = layout().build()
    validator = FakeRulesValidator(pads=pads)
    validator.result = validation(design)
    # the rules of a model are not judged on native input, even when one is handed in
    stage = stage_of(validator, model=with_rule(design), built=False)
    assert (stage.status, stage.issues) == ("ok", ())
    assert stage.summary["rules"] == ZERO
    measures = stage.summary["measures"]
    assert isinstance(measures, dict) and measures["nets"] == 2
    assert measures["congestion"]["pitch"] is None and measures["congestion"]["layers_needed"] is None
    assert stage.evidence == READ_EVIDENCE  # the measures lower nothing


def test_skips() -> None:
    """Scenario "Skips": a refused read, an unreadable cache, and a validator that is no board frame."""
    design, pads = layout().build()
    refused = FakeRulesValidator(error=FormatError("bad", file="board.kicad_pcb"))
    stage = stage_of(refused, model=None, built=False)
    assert (stage.status, stage.reason, stage.issues) == ("skipped", "read-refused", ())
    cached = FakeRulesValidator(pads=pads)
    cached.result = validation(design)
    stage = stage_of(cached, model=None, built=True, cache_error="circuit.json: invalid JSON")
    assert (stage.status, stage.reason, stage.issues) == ("skipped", "cache-unreadable", ())
    plain = FakeValidator()
    plain.result = validation(design)
    stage = stage_of(plain, model=with_rule(design), built=True)
    assert (stage.status, stage.reason, stage.issues) == ("skipped", "no-frame", ())


def test_stage_function_without_a_rules_source_has_no_pitch() -> None:
    design, pads = layout().build()
    frame = FakeRulesValidator(pads=pads)
    stage = placement_stage(
        design,
        model=with_rule(design),
        built=True,
        frame=frame,
        rules_source=None,
        project=project(),
        evidence=READ_EVIDENCE,
    )
    measures = stage.summary["measures"]
    assert isinstance(measures, dict) and measures["congestion"]["pitch"] is None
    assert stage.status == "errors"
    none = placement_stage(
        None,
        model=None,
        built=False,
        frame=frame,
        rules_source=None,
        project=project(),
        evidence=READ_EVIDENCE,
    )
    assert (none.status, none.reason) == ("skipped", "read-refused")


def test_default_pitch_needs_both_values_of_the_class() -> None:
    for width, clearance, wanted in (
        (200_000, 200_000, 400_000),
        (None, 200_000, None),
        (250_000, None, None),
    ):
        made = Layout()
        made.default_class(width, clearance)
        assert default_pitch(made.build()[0]) == wanted
    assert default_pitch(Layout().build()[0]) is None


# --- document input -------------------------------------------------------------------------------------


@dataclasses.dataclass
class FrameDocuments(FakeDocumentValidator):
    """A document validator that is also a board frame, as the Altium backend is."""

    pads: tuple[BoardPad, ...] = ()

    def board_pads(self, design: Design, *, issues: list[Issue] | None = None) -> tuple[BoardPad, ...]:
        return self.pads

    def placed_extents(
        self, design: Design, *, issues: list[Issue] | None = None
    ) -> tuple[PlacedExtent, ...]:
        return ()


def document_stage(validator: FakeDocumentValidator, *, model: Design | None, built: bool) -> StageResult:
    report = run_document_checks(
        documents=validator.documents_result, stages=(STAGE,), model=model, built=built, validator=validator
    )
    (stage,) = report.stages
    return stage


def test_document_input_judges_the_rules_of_a_built_project() -> None:
    design, pads = layout().build()
    validator = FrameDocuments(documents_result=document_set(PCB), pcb=reading(design), pads=pads)
    stage = document_stage(validator, model=with_rule(design), built=True)
    assert stage.status == "errors"
    assert [(i.code, i.where) for i in stage.issues] == [("placement.too-far", "C1")]
    assert stage.summary["rules"] == {"near": {"judged": 1, "failed": 1, "skipped": 0}}
    assert stage.evidence.level is Level.INFERRED
    native = document_stage(validator, model=None, built=False)
    assert (native.status, native.issues, native.summary["rules"]) == ("ok", (), ZERO)


def test_document_input_skips() -> None:
    design, _ = layout().build()
    alone = FakeDocumentValidator(documents_result=document_set(SCH))
    stage = document_stage(alone, model=None, built=False)
    assert (stage.status, stage.reason) == ("skipped", "single-source")
    no_frame = FakeDocumentValidator(documents_result=document_set(PCB), pcb=reading(design))
    stage = document_stage(no_frame, model=None, built=False)
    assert (stage.status, stage.reason) == ("skipped", "no-frame")


# --- the command, without kicad-cli ---------------------------------------------------------------------


@pytest.fixture
def no_tool(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("KICAD_CONFIG_HOME", str(tmp_path / "kicad-config"))
    for name in ("KICAD10_FOOTPRINT_DIR", "KICAD10_SYMBOL_DIR", "KICAD9_FOOTPRINT_DIR", "KICAD9_SYMBOL_DIR"):
        monkeypatch.delenv(name, raising=False)
    hide_kicad(monkeypatch, tmp_path)

    def refuse(*args: object, **kwargs: object) -> None:
        raise AssertionError("a subprocess was started")

    monkeypatch.setattr(subprocess, "run", refuse)
    monkeypatch.setattr(subprocess, "Popen", refuse)


@pytest.mark.usefixtures("no_tool")
def test_a_rule_fails_without_kicad_cli(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Scenario "A rule fails without kicad-cli": the nearest pad of ``D1`` lies about 12.2 mm from pad 2
    of ``R1``, and the rule allows 5 mm."""
    script = blink_variant(tmp_path / "src", append=NEAR)
    out = tmp_path / "built"
    code, env, err, _ = run(monkeypatch, tmp_path, "build", str(script), "--out", str(out), "--confirm")
    assert code == 0, (env.get("issues"), err)
    code, env, _, _ = run(monkeypatch, tmp_path, "check", str(out), "--stages", STAGE)
    assert code == 5
    (stage,) = env["result"]["stages"]
    assert (stage["name"], stage["status"]) == (STAGE, "errors")
    found = [i for i in env["issues"] if i["code"].startswith("placement.")]
    assert [(i["code"], i["severity"], i["where"]) for i in found] == [("placement.too-far", "error", "D1")]
    assert "R1-2" in found[0]["message"] and "5 mm" in found[0]["message"]
    assert stage["summary"]["rules"]["near"] == {"judged": 1, "failed": 1, "skipped": 0}
    assert stage["summary"]["measures"]["nets"] > 0
    assert stage["evidence"]["level"] == "INFERRED"
    again = run(monkeypatch, tmp_path, "check", str(out), "--stages", STAGE)[1]
    assert again["result"]["stages"] == env["result"]["stages"] and again["issues"] == env["issues"]


@pytest.mark.usefixtures("no_tool")
def test_native_board_measured(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    code, env, _, _ = run(monkeypatch, tmp_path, "check", str(TWO_LAYER), "--stages", STAGE)
    assert code == 0, env["issues"]
    (stage,) = env["result"]["stages"]
    assert (stage["name"], stage["status"], stage["reason"]) == (STAGE, "ok", "")
    assert not [i for i in env["issues"] if i["code"].startswith("placement.")]
    assert stage["summary"]["rules"] == ZERO
    measures = stage["summary"]["measures"]
    assert measures["nets"] > 0 and measures["hpwl"] >= measures["ratsnest"] > 0
    assert set(measures) == {"nets", "hpwl", "ratsnest", "longest", "left_out", "congestion"}


@pytest.mark.usefixtures("no_tool")
def test_altium_documents_without_a_script(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    code, env, _, _ = run(monkeypatch, tmp_path, "check", str(ROUTED_PCBDOC), "--stages", STAGE)
    assert code == 0, env["issues"]
    (stage,) = env["result"]["stages"]
    assert (stage["name"], stage["status"]) == (STAGE, "ok")
    assert stage["summary"]["rules"] == ZERO and stage["summary"]["measures"]["nets"] > 0
