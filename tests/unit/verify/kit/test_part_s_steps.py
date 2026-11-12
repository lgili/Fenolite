# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Part S's additive formal mapping; every run here is synthetic, never native evidence."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from _simulate import simulate, simulated_judge

from fenolite.cli._kit import judge_document
from fenolite.verify.kit.manifest import load_kit
from fenolite.verify.kit.record import refusal
from fenolite.verify.kit.results import verify_results
from fenolite.verify.kit.steps import STEPS

H = "H-A-SLOT-KIT"
IDS = tuple(f"K5.{n}" for n in range(6, 14))


def _verdict(folder: Path):
    return verify_results(folder, judge=simulated_judge)


def test_eight_part_s_steps_are_additive_and_source_bound() -> None:
    steps = [s for s in STEPS if H in s.hypotheses]
    assert tuple(s.id for s in steps) == IDS
    assert all(s.sample == "slots" and s.hypotheses == (H,) for s in steps)
    assert all(f"S{i}" in s.instruction for i, s in enumerate(steps, 1))
    assert all(not s.scripted and not s.pending for s in steps)
    assert steps[6].kind == "file" and steps[6].checks == ("slots-readback",)
    assert steps[6].document == "slots/regions/slots.PcbDoc"


@pytest.mark.parametrize("ident", IDS)
def test_any_missing_case_prevents_the_hypothesis_pass(kit: Path, ident: str) -> None:
    simulate(kit, skip=(ident,))
    found = next(h for h in _verdict(kit).hypotheses if h.id == H)
    assert found.outcome != "pass"


@pytest.mark.parametrize("ident", tuple(i for i in IDS if i != "K5.12"))
def test_any_false_native_observation_fails_the_hypothesis(kit: Path, ident: str) -> None:
    simulate(kit)
    path = kit / "results/form.json"
    form = json.loads(path.read_text(encoding="utf-8"))
    form["values"][ident] = False
    path.write_text(json.dumps(form), encoding="utf-8")
    assert next(h for h in _verdict(kit).hypotheses if h.id == H).outcome == "fail"


def test_all_simulated_cases_pass_but_cannot_create_a_real_record(kit: Path) -> None:
    simulate(kit)
    verdict = _verdict(kit)
    found = next(h for h in verdict.hypotheses if h.id == H)
    assert found.outcome == "pass" and found.steps == IDS and found.form
    assert "synthetic" in refusal(verdict)
    own = kit / "slots/regions/slots.PcbDoc"
    assert judge_document("slots-readback", own, own) == []
    assert load_kit(kit).samples["slots"]


@pytest.mark.parametrize(
    "relative",
    [
        "regions/slots.PrjPcb",
        "regions/slots.SchDoc",
        "clearance/slots.PcbDoc",
        "clearance/slots.PcbLib",
        "clearance/slots.SchLib",
        "gate-off/build-report.json",
        "recipe.py",
    ],
)
def test_changed_source_input_cannot_qualify_any_part_s_case(kit: Path, relative: str) -> None:
    simulate(kit)
    path = kit / "slots" / relative
    path.write_bytes(path.read_bytes() + b"\nchanged source\n")
    verdict = _verdict(kit)
    assert next(h for h in verdict.hypotheses if h.id == H).outcome != "pass"
    assert all(s.outcome != "pass" for s in verdict.steps if s.id in IDS)
    assert refusal(verdict)


def test_part_s_can_be_checked_without_requalifying_old_native_cases(kit: Path) -> None:
    old_ids = tuple(s.id for s in STEPS if H not in s.hypotheses)
    simulate(kit, skip=old_ids)
    verdict = _verdict(kit)
    assert next(h for h in verdict.hypotheses if h.id == H).outcome == "pass"
    assert all(s.outcome == "skipped" for s in verdict.steps if s.id in old_ids)
    assert all(h.outcome != "pass" for h in verdict.hypotheses if h.id != H)
    assert "synthetic" in refusal(verdict)


@pytest.mark.parametrize(
    "check",
    [
        "resave",
        "netlist",
        "parity",
        "poured",
        "copper.clearance",
        "messages",
        "listing",
        "present",
        "repoured",
        "pour-match",
        "pour-same",
        "pour-kept",
        "pour-drc",
        "slots-readback",
    ],
)
@pytest.mark.parametrize("version", ["v0", "v1"])
def test_existing_and_added_check_validate_under_the_same_schema(kit: Path, check: str, version: str) -> None:
    from _result_contract import document_problems

    from fenolite.cli.api import PlannedWrite

    body = json.loads((kit / "kit.json").read_text(encoding="utf-8"))
    body["schema"] = f"fenolite.altium-kit.{version}"
    body["steps"][0]["checks"] = [check]
    assert document_problems((PlannedWrite("kit.json", json.dumps(body).encode(), "kit"),)) == []


@pytest.mark.parametrize("checks", [["unknown-part-s-check"], [42], "slots-readback"])
def test_unknown_or_malformed_check_remains_refused(kit: Path, checks: object) -> None:
    from _result_contract import document_problems

    from fenolite.cli.api import PlannedWrite

    body = json.loads((kit / "kit.json").read_text(encoding="utf-8"))
    body["steps"][0]["checks"] = checks
    assert document_problems((PlannedWrite("kit.json", json.dumps(body).encode(), "kit"),))


@pytest.mark.parametrize("version", ["AD 24.5 + AD 26.5", ["AD 24.5", "AD 26.5"], "AD 24.5.2.23"])
def test_part_s_keeps_the_existing_single_version_form(version: object) -> None:
    from fenolite.verify.kit.manifest import blank_form
    from fenolite.verify.kit.results import form_problems

    form = blank_form()
    form.update(altium_version="AD 24.5", os_family="Windows", date="2026-11-03", synthetic=True)
    assert form_problems(form, STEPS) == []
    form["altium_version"] = version
    assert form_problems(form, STEPS)
