# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The ``length.rules`` stage (capability verification-loop, "Length rules stage" and "Length stage issue
codes"; hypothesis H-K-NETLEN-RULES; change c0106). The benches are the rules bench of
``tests/_lengthbench.py`` with the rules texts of its cases; no tool runs."""

from __future__ import annotations

import dataclasses
import subprocess
from pathlib import Path
from typing import Any

import _lengthbench as lb
import pytest
from _checkcli import hide_kicad, run
from _projects import authored_project
from fakes import READ_EVIDENCE, FakeValidator, validation

from fenolite.backends.base import DesignRules, LengthFacts, NetLength, ProjectSet
from fenolite.checks import DEFAULT_STAGES, ORACLE_STAGES, STAGE_ORDER, run_checks
from fenolite.checks.codes import ISSUE_CODES
from fenolite.checks.documents import ALL_DOCUMENT_STAGES, DOCUMENT_STAGES, OPT_IN_DOCUMENT_STAGES
from fenolite.checks.length import (
    EVIDENCE,
    STAGE,
    governing,
    judge_lengths,
    length_stage,
    present_nets,
    routed_lengths,
)
from fenolite.core.errors import Issue
from fenolite.core.evidence import Evidence, Level
from fenolite.model.circuit import Interface
from fenolite.model.design import Design
from fenolite.model.rules import Rule, RuleSet, Selector

ROOT = Path(__file__).resolve().parents[3]
MM = lb.MM
BLINK = ROOT / "tests" / "data" / "altium" / "blink" / "blink.PrjPcb"


def _no_tool(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """No ``kicad-cli`` anywhere, and any subprocess fails the test."""
    hide_kicad(monkeypatch, tmp_path)

    def refuse(*args: object, **kwargs: object) -> None:
        raise AssertionError("a subprocess was started")

    monkeypatch.setattr(subprocess, "run", refuse)
    monkeypatch.setattr(subprocess, "Popen", refuse)


def _bench(tmp_path: Path, *cases: str, target: int = 10) -> Path:
    folder = tmp_path / "bench"
    folder.mkdir()
    rules = "(version 1)\n" + lb.scoped_canary() + "".join(lb.RULES_TEXTS[case] for case in cases)
    lb.write_case("rules", target, folder, rules=rules)
    return folder


def _stage(envelope: dict[str, Any]) -> dict[str, Any]:
    (stage,) = envelope["result"]["stages"]
    assert stage["name"] == STAGE
    return stage  # type: ignore[no-any-return]


def _length_issues(envelope: dict[str, Any]) -> list[dict[str, Any]]:
    return [i for i in envelope["issues"] if i["code"].startswith("length.")]


# --- "Length rules stage", through the command ------------------------------------------------------


def test_pair_skew_without_kicad_cli(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Scenario "Pair skew without kicad-cli"."""
    root = _bench(tmp_path, "skew-pair")
    _no_tool(monkeypatch, tmp_path)
    code, env, err, _ = run(monkeypatch, tmp_path, "check", str(root), "--stages", STAGE)
    assert code == 5 and err["code"] == "FEN-5001"
    (found,) = _length_issues(env)
    assert (found["code"], found["severity"], found["where"]) == ("length.skew-out-of-range", "error", "SK_P")
    for text in ("SK_P", "-1 mm", "SK_N at 21 mm", "0.1 mm"):
        assert text in found["message"], found["message"]
    stage = _stage(env)
    assert stage["status"] == "errors"
    assert stage["summary"] == {
        "rules": {"length": 0, "skew": 1}, "nets": 2, "major": 10, "stackup": "default",
    }  # fmt: skip
    assert stage["evidence"]["level"] == "INFERRED"
    assert "H-K-NETLEN-RULES" in stage["evidence"]["hypotheses"]


def test_minimum_on_a_short_net_and_on_a_net_of_pads_only(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Scenario "Minimum on a short net and on a net of pads only": ``opt`` is not judged."""
    root = _bench(tmp_path, "length-range", "length-opt")
    _no_tool(monkeypatch, tmp_path)
    code, env, _, _ = run(monkeypatch, tmp_path, "check", str(root), "--stages", STAGE)
    assert code == 5
    found = {i["where"]: i for i in _length_issues(env)}
    assert sorted(found) == ["NOTRK", "SHORT"]
    assert all(i["code"] == "length.out-of-range" and i["severity"] == "error" for i in found.values())
    assert "length 2.4 mm is below the minimum 5 mm of rule range" in found["SHORT"]["message"]
    assert "routed 2.4 mm, vias 0 mm, die 0 mm" in found["SHORT"]["message"]
    assert "length 0 mm" in found["NOTRK"]["message"]
    assert _stage(env)["summary"]["rules"] == {"length": 2, "skew": 0}


def test_skew_of_a_bus(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """A ``skew`` rule groups every net it governs: −3 mm on ``BUS0``, −2 mm on ``BUS1``, nothing on the
    longest net ``BUS2`` (measurement 4 of the design)."""
    root = _bench(tmp_path, "skew-bus")
    _no_tool(monkeypatch, tmp_path)
    code, env, _, _ = run(monkeypatch, tmp_path, "check", str(root), "--stages", STAGE)
    assert code == 5
    found = {i["where"]: i["message"] for i in _length_issues(env)}
    assert sorted(found) == ["BUS0", "BUS1"]
    assert "a skew of -3 mm" in found["BUS0"] and "a skew of -2 mm" in found["BUS1"]
    assert "BUS2 at 23 mm" in found["BUS0"]


@pytest.mark.parametrize("case", ["length-opt", "length-opt-max"])
def test_opt_is_not_judged(monkeypatch: pytest.MonkeyPatch, tmp_path: Path, case: str) -> None:
    root = _bench(tmp_path, case)
    _no_tool(monkeypatch, tmp_path)
    code, env, _, _ = run(monkeypatch, tmp_path, "check", str(root), "--stages", STAGE)
    assert code == 0 and _length_issues(env) == [] and _stage(env)["status"] == "ok"


@pytest.mark.parametrize("case", sorted(lb.RULES_EXPECTED))
def test_findings_name_the_nets_kicad_reports(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, case: str
) -> None:
    """The stage names the nets that ``H-K-NETLEN-RULES`` predicts KiCad reports, on both majors."""
    kinds = {"length.out-of-range": "length_out_of_range", "length.skew-out-of-range": "skew_out_of_range"}
    for target in (9, 10):
        root = tmp_path / f"t{target}"
        root.mkdir()
        lb.write_case("rules", target, root, rules=lb.rules_case_text(case))
        _no_tool(monkeypatch, tmp_path)
        _, env, _, _ = run(monkeypatch, tmp_path, "check", str(root), "--stages", STAGE)
        found = tuple(sorted((kinds[i["code"]], i["where"]) for i in _length_issues(env)))
        assert found == tuple(sorted(lb.RULES_EXPECTED[case])), (target, env["issues"])


def test_no_length_rule(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Scenario "No length rule"."""
    root = authored_project(tmp_path, major=10, built=True)
    _no_tool(monkeypatch, tmp_path)
    code, env, _, _ = run(monkeypatch, tmp_path, "check", str(root), "--stages", STAGE)
    stage = _stage(env)
    assert code == 0 and stage["status"] == "ok" and _length_issues(env) == []
    assert stage["summary"]["rules"] == {"length": 0, "skew": 0}
    assert stage["summary"]["nets"] == 0


def test_document_input_has_no_length_stage(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Scenario "Altium input has no length stage"."""
    _no_tool(monkeypatch, tmp_path)
    code, env, _, _ = run(monkeypatch, tmp_path, "check", str(BLINK))
    names = [stage["name"] for stage in env["result"]["stages"]]
    assert code == 0 and names == list(DOCUMENT_STAGES) and STAGE not in names
    assert STAGE not in ALL_DOCUMENT_STAGES and STAGE not in OPT_IN_DOCUMENT_STAGES
    code, _, err, _ = run(monkeypatch, tmp_path, "check", str(BLINK), "--stages", STAGE)
    assert code == 2 and err["code"] == "FEN-2001"


# --- the stage list ---------------------------------------------------------------------------------


def test_stage_place_in_the_order() -> None:
    order = list(STAGE_ORDER)
    assert order.index(STAGE) == order.index("copper.clearance") + 1
    assert order.index(STAGE) < order.index("zone.fill") < order.index("drc.kicad")
    assert STAGE in DEFAULT_STAGES and STAGE not in ORACLE_STAGES


def test_codes_and_module_evidence() -> None:
    assert ISSUE_CODES["length.out-of-range"] == ("error", "warning")
    assert ISSUE_CODES["length.skew-out-of-range"] == ("error", "warning")
    assert ISSUE_CODES["length.input-missing"] == ("warning",)
    assert EVIDENCE == Evidence(Level.INFERRED, hypotheses=("H-K-NETLEN-RULES",))


# --- the stage function with fakes ------------------------------------------------------------------


def _rule(name: str, kind: str, selector: Selector, **values: Any) -> Rule:
    return Rule(id=f"rul_{name}", name=name, kind=kind, selector_a=selector, **values)  # type: ignore[arg-type]


def _design(*rules: Rule) -> Design:
    design = lb.bench("rules", 10)
    return dataclasses.replace(design, rules=RuleSet(id="rls_1", rules=rules))


def _project(tmp_path: Path) -> ProjectSet:
    board = tmp_path / "bench.kicad_pcb"
    return ProjectSet(tmp_path, board.name, {board.name: board}, has_project=False, has_rules=False)


class _Rules:
    def __init__(self, design: Design) -> None:
        self.design = design

    def design_rules(
        self, design: Design, project: ProjectSet, *, issues: list[Issue] | None = None
    ) -> DesignRules:
        return DesignRules(self.design, evidence=Evidence(Level.KICAD_VERIFIED))


class _Facts:
    def __init__(self, extra: int = 0) -> None:
        self.asked: list[object] = []
        self.extra = extra

    def length_facts(
        self, design: Design, *, project: ProjectSet | None = None, major: int | None = None,
        nets: object = None, issues: list[Issue] | None = None,
    ) -> LengthFacts:  # fmt: skip
        self.asked.append(tuple(nets) if nets is not None else None)  # type: ignore[call-overload]
        lengths = routed_lengths(design, tuple(nets or ()))  # type: ignore[call-overload]
        found = {
            name: NetLength(name, n.routed, self.extra, 0, n.routed + self.extra, n.via_count)
            for name, n in lengths.items()
        }
        return LengthFacts(found, {}, {}, 9, "board", True, Evidence(Level.KICAD_VERIFIED))


def test_stage_without_sources_judges_the_model_with_warnings(tmp_path: Path) -> None:
    design = _design(_rule("short", "length", Selector("net", "SHORT"), min=5 * MM))
    result = length_stage(design, project=_project(tmp_path), rules_source=None, facts_source=None,
                          evidence=READ_EVIDENCE)  # fmt: skip
    codes = sorted(i.code for i in result.issues)
    assert codes == ["length.input-missing", "length.input-missing", "length.out-of-range"]
    assert {i.where for i in result.issues if i.code == "length.input-missing"} == {"rules", "lengths"}
    assert result.evidence.level is Level.UNVERIFIED and result.status == "errors"
    assert result.summary["major"] is None and result.summary["stackup"] is None


def test_stage_uses_the_rules_and_the_facts_of_its_sources(tmp_path: Path) -> None:
    """The rules come from the rules source (not the model), and the facts are asked for the governed nets
    only; the via part of the facts counts in the total."""
    rules = _design(_rule("short", "length", Selector("net", "SHORT"), max=2_500_000))
    facts = _Facts(extra=200_000)
    result = length_stage(_design(), project=_project(tmp_path), rules_source=_Rules(rules),
                          facts_source=facts, evidence=READ_EVIDENCE)  # fmt: skip
    assert facts.asked == [("SHORT",)]
    (found,) = result.issues
    assert found.code == "length.out-of-range" and "2.6 mm is above the maximum 2.5 mm" in found.message
    assert "vias 0.2 mm" in found.message
    assert result.summary == {"rules": {"length": 1, "skew": 0}, "nets": 1, "major": 9, "stackup": "board"}
    assert result.evidence.level is Level.INFERRED


def test_stage_skipped_when_the_read_was_refused(tmp_path: Path) -> None:
    result = length_stage(None, project=_project(tmp_path), rules_source=None, facts_source=None,
                          evidence=READ_EVIDENCE)  # fmt: skip
    assert (result.status, result.reason) == ("skipped", "read-refused")


def test_run_checks_passes_the_validator_as_both_sources(tmp_path: Path) -> None:
    """A validator that is no rules source and no length source: the stage runs on the read model."""
    design = _design(_rule("short", "length", Selector("net", "SHORT"), min=5 * MM))
    validator = FakeValidator(validation(design))
    report = run_checks(project=_project(tmp_path), stages=(STAGE,), model=None, built=False,
                        validator=validator, oracle=None)  # fmt: skip
    (stage,) = report.stages
    assert stage.name == STAGE and stage.status == "errors"
    assert any(i.code == "length.out-of-range" and i.where == "SHORT" for i in stage.issues)


def _lengths(**totals: int) -> dict[str, NetLength]:
    """Every net of the rules bench at 30 mm, but those of ``totals``."""
    every = {name: 30 * MM for name in present_nets(lb.bench("rules", 10))} | totals
    return {name: NetLength(name, value, 0, 0, value, 0) for name, value in every.items()}


def test_last_rule_governs_and_ignore_judges_nothing() -> None:
    wide = _rule("a_wide", "length", Selector("net", "*"), min=5 * MM)
    quiet = _rule("b_quiet", "length", Selector("net", "SHORT"), min=5 * MM, severity="ignore")
    governed = governing(_design(wide, quiet))
    assert governed.length["SHORT"] is quiet and governed.length["NOTRK"] is wide
    issues = judge_lengths(_lengths(SHORT=2_400_000, NOTRK=0, OPTONLY=2_400_000), governed)
    assert sorted(i.where for i in issues if i.code == "length.out-of-range") == ["NOTRK", "OPTONLY"]
    # an explicit priority 1 is written last, so it governs
    first = dataclasses.replace(wide, name="z_first", id="rul_z", priority=1, min=1 * MM, severity="warning")
    governed = governing(_design(wide, first))
    assert governed.length["SHORT"] is first
    assert (
        judge_lengths(_lengths(SHORT=2_400_000, NOTRK=0, OPTONLY=2_400_000), governed)[0].severity
        == "warning"
    )


def test_skew_and_pair_skew_are_one_constraint() -> None:
    """The last matching rule of the two skew kinds together governs; a ``diff_pair_skew`` rule groups each
    pair apart, a ``skew`` rule every net it governs. Letter case of a net name does not count."""
    bus = _rule("a_bus", "skew", Selector("net", "*"), max=100_000)
    pair = _rule("b_pair", "diff_pair_skew", Selector("diff_pair", "SK"), max=100_000)
    governed = governing(_design(bus, pair))
    assert governed.skew["SK_P"] is pair and governed.skew["BUS0"] is bus
    lengths = _lengths(SK_P=20 * MM, SK_N=21 * MM, BUS0=20 * MM, BUS1=21 * MM, BUS2=23 * MM,
                       SHORT=2_400_000, NOTRK=0, OPTONLY=2_400_000)  # fmt: skip
    issues = judge_lengths(lengths, governed)
    reported = sorted(i.where for i in issues)
    # the bus rule groups every net but the pair; CANARY_A is the first of the longest, CANARY_B ties it
    assert reported == ["BUS0", "BUS1", "BUS2", "NOTRK", "OPTONLY", "SHORT", "SK_P"]
    folded = governing(_design(_rule("lower", "skew", Selector("net", "bus*"), max=100_000)))
    assert folded.skew["BUS0"] is not None


def test_ties_go_to_the_first_net_name() -> None:
    rule = _rule("bus", "skew", Selector("net", "BUS*"), max=100_000)
    lengths = {name: NetLength(name, value, 0, 0, value, 0) for name, value in
               (("BUS0", 21 * MM), ("BUS1", 21 * MM), ("BUS2", 20 * MM))}  # fmt: skip
    issues = judge_lengths(lengths, governing(_design(rule)))
    assert [(i.where, "BUS0 at 21 mm" in i.message) for i in issues] == [("BUS2", True)]


def test_pair_interface_is_not_needed_and_bases_come_from_names() -> None:
    """A board read from a file holds no interface: the pair of a ``diff_pair_skew`` rule comes from the
    name rule (``model.pairs.net_bases``)."""
    design = _design(_rule("pair", "diff_pair_skew", Selector("diff_pair", "*"), max=100_000))
    assert not design.circuit.interfaces or all(isinstance(i, Interface) for i in design.circuit.interfaces)
    governed = governing(design)
    assert governed.bases == {"SK_P": "SK_", "SK_N": "SK_"}
    assert {name for name, rule in governed.skew.items() if rule is not None} == {"SK_N", "SK_P"}
