# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Reply evidence is checked before staging/writes, preserving diagnostic-only errors (c0219)."""

from __future__ import annotations

import dataclasses
import importlib
from pathlib import Path
from typing import Any

import pytest
from _checkcli import run
from _cliexamples import folder_snapshot

from fenolite.cli.api import NO_CLAIM, PlannedWrite, Result
from fenolite.cli.errors import CliError
from fenolite.cli.output import InputRef, evidence_issues
from fenolite.core.errors import Issue
from fenolite.core.evidence import Evidence, Level

ROOT = Path(__file__).resolve().parents[3]


def test_conservative_pin_input_has_a_complete_existing_receipt(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("FENOLITE_CONTRACT_CHECK", "1")
    evidence = Evidence(Level.UNVERIFIED, hypotheses=("H-G-PIN-SOLVE-DETERMINISTIC",))
    result = {
        "devices": [{"id": "Example:MCU", "evidence": "UNVERIFIED", "sha256": "a" * 64, "parts": ["mcu"]}],
        "pins": [
            {
                "key": "mcu/i2c",
                "kind": "i2c",
                "option": "I2C1",
                "alternative": 0,
                "pins": {"sda": "P1", "scl": "P2"},
                "source": "solved",
            }
        ],
    }
    assert evidence_issues("build", evidence, (), no_claim=False, result=result) == ()
    for changed in ({**result, "pins": []}, {**result, "devices": []}):
        with pytest.raises(CliError):
            evidence_issues("build", evidence, (), no_claim=False, result=changed)
    with pytest.raises(CliError):
        evidence_issues("fmt", evidence, (), no_claim=False, result=result)


@pytest.mark.parametrize("limited", ("missing", "device"))
def test_conservative_circuit_rows_preserve_actual_scope(
    monkeypatch: pytest.MonkeyPatch, limited: str
) -> None:
    monkeypatch.setenv("FENOLITE_CONTRACT_CHECK", "1")
    requirement = (
        {"status": "unknown", "value": None, "missing": "voltage of SIG"}
        if limited == "missing"
        else {
            "status": "pass",
            "limit": {
                "source": "device",
                "evidence": "UNVERIFIED",
                "basis": "Example:TVS abs_max",
                "range": {"unit": "volt"},
            },
        }
    )
    issues = (Issue("circuit.value-unknown", "info", "one unjudged row"),) if limited == "missing" else ()
    stage = {
        "name": "circuit.rules",
        "status": "ok",
        "evidence": {"level": "UNVERIFIED", "hypotheses": ["H-G-CIRCUIT-RULES"]},
        "summary": {"requirements": [requirement]},
    }
    evidence = Evidence(Level.UNVERIFIED, hypotheses=("H-G-CIRCUIT-RULES",))
    assert evidence_issues("check", evidence, issues, no_claim=False, result={"stages": [stage]}) == issues
    stage["summary"] = {"requirements": [{"status": "pass", "missing": "", "value": 1}]}
    with pytest.raises(CliError):
        evidence_issues("check", evidence, issues, no_claim=False, result={"stages": [stage]})


@pytest.mark.parametrize("attempted_write", (False, True))
def test_primary_failure_with_context_keeps_no_write_diagnostic_boundary(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, attempted_write: bool
) -> None:
    monkeypatch.setenv("FENOLITE_CONTRACT_CHECK", "1")
    _returned(
        monkeypatch,
        "fmt",
        Result(
            result={"lines": 7},
            issues=(Issue("model.corner-ratio", "error", "authored invalid input"),),
            writes=(PlannedWrite("out.txt", b"bad", "file"),) if attempted_write else (),
        ),
    )
    code, reply, error, _ = run(monkeypatch, tmp_path, "fmt", "unused", "--confirm")
    if attempted_write:
        assert code == 1 and error["code"] == "FEN-1001"
    else:
        assert code == 5 and [issue["code"] for issue in reply["issues"]] == ["model.corner-ratio"]
    assert not (tmp_path / "out.txt").exists()


def _returned(monkeypatch: pytest.MonkeyPatch, name: str, result: Result) -> None:
    module = importlib.import_module(f"fenolite.cli.cmd_{name}")
    monkeypatch.setattr(module, "COMMAND", dataclasses.replace(module.COMMAND, run=lambda args, ctx: result))


@pytest.mark.parametrize("level", [Level.INFERRED, Level.KICAD_VERIFIED, Level.UNVERIFIED, Level.UNKNOWN])
def test_unsound_evidence_is_an_internal_error_in_strict_mode(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, level: Level
) -> None:
    monkeypatch.setenv("FENOLITE_CONTRACT_CHECK", "1")
    _returned(monkeypatch, "fmt", Result(result={"lines": 7}, evidence=Evidence(level)))
    code, reply, error, _ = run(monkeypatch, tmp_path, "fmt", "unused")
    assert code == 1 and error["code"] == "FEN-1001" and not reply["ok"]


def test_no_claim_does_not_excuse_inferred_without_a_hypothesis(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("FENOLITE_CONTRACT_CHECK", "1")
    _returned(monkeypatch, "_echo", Result(evidence=Evidence(Level.INFERRED)))
    code, _, error, _ = run(monkeypatch, tmp_path, "_echo")
    assert code == 1 and error["code"] == "FEN-1001"


def test_production_reply_is_preserved_with_one_warning(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.delenv("FENOLITE_CONTRACT_CHECK", raising=False)
    previous = Issue("cli.evidence-unsound", "warning", "old metadata warning")
    _returned(
        monkeypatch,
        "fmt",
        Result(result={"lines": 7}, evidence=Evidence(Level.INFERRED), issues=(previous,)),
    )
    code, reply, _, _ = run(monkeypatch, tmp_path, "fmt", "unused")
    assert code == 0 and reply["result"] == {"lines": 7}
    assert [issue["code"] for issue in reply["issues"]] == ["cli.evidence-unsound"]
    assert "no hypothesis" in reply["issues"][0]["message"]


@pytest.mark.parametrize("flag", ["--confirm", "--dry-run"])
def test_bad_claim_cannot_write_or_stage_a_plan(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, flag: str
) -> None:
    monkeypatch.setenv("FENOLITE_CONTRACT_CHECK", "1")
    state = tmp_path / "state"
    monkeypatch.setenv("FENOLITE_STATE_DIR", str(state))
    (tmp_path / "out.txt").write_bytes(b"original")
    _returned(
        monkeypatch,
        "fmt",
        Result(
            result={"lines": 7},
            writes=(PlannedWrite("out.txt", b"changed", "file"),),
            evidence=Evidence(Level.INFERRED),
        ),
    )
    before = folder_snapshot(tmp_path)
    code, _, error, _ = run(monkeypatch, tmp_path, "fmt", "unused", flag)
    assert code == 1 and error["code"] == "FEN-1001"
    assert folder_snapshot(tmp_path) == before and not list(state.rglob("*.json"))


def test_replayed_unsound_metadata_is_checked_before_committing(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.delenv("FENOLITE_CONTRACT_CHECK", raising=False)
    (tmp_path / "out.txt").write_bytes(b"original")
    _returned(
        monkeypatch,
        "fmt",
        Result(
            result={"lines": 7},
            writes=(PlannedWrite("out.txt", b"changed", "file"),),
            evidence=Evidence(Level.INFERRED),
        ),
    )
    code, planned, _, _ = run(monkeypatch, tmp_path, "fmt", "unused", "--dry-run")
    assert code == 0 and planned["issues"][0]["code"] == "cli.evidence-unsound"
    monkeypatch.setenv("FENOLITE_CONTRACT_CHECK", "1")
    before = folder_snapshot(tmp_path)
    code, _, error, _ = run(
        monkeypatch, tmp_path, "fmt", "unused", "--confirm", "--plan", planned["result"]["plan_id"]
    )
    assert code == 1 and error["code"] == "FEN-1001" and folder_snapshot(tmp_path) == before


def test_strict_check_keeps_primary_format_and_confirmation_errors(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("FENOLITE_CONTRACT_CHECK", "1")
    board = tmp_path / "authored.kicad_pcb"
    source = (ROOT / "tests/data/kicad/board/two_layer.kicad_pcb").read_bytes()
    board.write_bytes(source.replace(b"(kicad_pcb", b"(kicad_pcb  ", 1))
    code, _, error, _ = run(monkeypatch, tmp_path, "fmt", board.name)
    assert code == 4 and error["code"] == "FEN-4001"
    board.write_bytes(b"(kicad_pcb (broken")
    code, _, error, _ = run(monkeypatch, tmp_path, "fmt", board.name, "--confirm")
    assert code == 3 and error["code"] == "FEN-3004"


def test_empty_diagnostic_failure_keeps_its_finding(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("FENOLITE_CONTRACT_CHECK", "1")
    _returned(
        monkeypatch,
        "fmt",
        Result(issues=(Issue("model.corner-ratio", "error", "authored invalid input"),)),
    )
    code, reply, error, _ = run(monkeypatch, tmp_path, "fmt", "unused")
    assert code == 5 and error["code"] == "FEN-5001"
    assert [issue["code"] for issue in reply["issues"]] == ["model.corner-ratio"]


def test_unknown_is_only_allowed_for_unknown_file_detection(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("FENOLITE_CONTRACT_CHECK", "1")
    result = Result(
        result={"kind": "unknown"},
        evidence=Evidence(Level.UNKNOWN),
        input=InputRef("authored.bin", None, "unknown", None),
    )
    _returned(monkeypatch, "inspect", result)
    assert run(monkeypatch, tmp_path, "inspect", "authored.bin")[0] == 0
    _returned(monkeypatch, "fmt", result)
    code, _, error, _ = run(monkeypatch, tmp_path, "fmt", "unused")
    assert code == 1 and error["code"] == "FEN-1001"


def test_only_named_registered_experimental_features_are_eligible(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("FENOLITE_CONTRACT_CHECK", "1")
    issue = Issue("altium.experimental", "info", "Experimental Altium write kinds: altium_pcbdoc")
    assert evidence_issues("build", Evidence(), (issue,), no_claim=False) == (issue,)
    for name, issues in (
        ("inspect", (issue,)),
        ("build", (Issue("fake.experimental", "info", "arbitrary"),)),
    ):
        with pytest.raises(CliError, match="UNVERIFIED evidence") as caught:
            evidence_issues(name, Evidence(), issues, no_claim=False)
        assert caught.value.info().code == "FEN-1001"


def test_no_claim_catalog_keeps_its_supported_evidence_and_discovery(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("FENOLITE_CONTRACT_CHECK", "1")
    code, reply, _, _ = run(monkeypatch, tmp_path, "catalog", "list")
    assert code == 0 and reply["evidence"]["level"] == "INFERRED"
    assert "H-G-CATALOG" in reply["evidence"]["hypotheses"]
    for name in ("catalog", "doctor", "explain", "edit", "mcp"):
        code, reply, _, _ = run(monkeypatch, tmp_path, "capabilities", "--command", name, "--no-tools")
        assert code == 0 and reply["result"]["command"]["claims"] is False
    assert NO_CLAIM == frozenset(
        {
            "capabilities",
            "catalog",
            "doctor",
            "edit",
            "mcp",
            "explain",
            "guide",
            "skill",
            "init",
            "fetch",
            "manifest",
            "restore",
        }
    )
    code, reply, _, _ = run(monkeypatch, tmp_path, "explain", "FEN-2001")
    assert code == 0 and reply["evidence"] == {"level": "UNVERIFIED", "oracle": None, "hypotheses": []}


def _skipped_stage() -> dict[str, Any]:
    return {
        "name": "copper.clearance",
        "status": "skipped",
        "reason": "single-source",
        "evidence": {"level": "UNVERIFIED", "oracle": None, "hypotheses": []},
        "summary": {},
    }


def test_wholly_skipped_check_receipt_is_exactly_preserved(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("FENOLITE_CONTRACT_CHECK", "1")
    result = {"stages": [_skipped_stage()]}
    before = dataclasses.asdict(Result(result=result))
    assert evidence_issues("check", Evidence(), (), no_claim=False, result=result) == ()
    assert dataclasses.asdict(Result(result=result)) == before
    with pytest.raises(CliError):
        evidence_issues("ready", Evidence(), (), no_claim=False, result={"checks": result["stages"]})


@pytest.mark.parametrize(
    "fault",
    ["completed", "reason", "unknown-reason", "name", "summary", "evidence", "duplicate", "empty", "record"],
)
def test_malformed_or_completed_stage_cannot_use_the_skip_exception(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, fault: str
) -> None:
    monkeypatch.setenv("FENOLITE_CONTRACT_CHECK", "1")
    stage = _skipped_stage()
    stages: list[Any] = [stage]
    if fault == "completed":
        stages.append({**stage, "name": "parity", "status": "ok", "reason": ""})
    elif fault == "unknown-reason":
        stage["reason"] = "arbitrary"
    elif fault == "duplicate":
        stages.append(dict(stage))
    elif fault == "empty":
        stages.clear()
    elif fault == "record":
        stages.append("not a stage")
    elif fault == "summary":
        stage["summary"] = {"judged": 1}
    elif fault == "name":
        stage["name"] = "arbitrary.stage"
    else:
        del stage[fault]
    _returned(monkeypatch, "check", Result(result={"stages": stages}))
    code, _, error, _ = run(monkeypatch, tmp_path, "check", "unused")
    assert code == 1 and error["code"] == "FEN-1001"


@pytest.mark.parametrize(
    ("command", "result", "code", "where"),
    [
        ("analyze", {"summary": {"current": {"skipped": 2}}}, "analysis.input-missing", "copper thickness"),
        (
            "analyze",
            {"summary": {"distances": {"missing": {"board thickness": 1}}}},
            "analysis.input-missing",
            "board thickness",
        ),
        ("convert", {"equivalence": None}, "convert.no-verify", ""),
        (
            "convert",
            {
                "report": {
                    "lossy": True,
                    "rows": [
                        {
                            "kind": "pad",
                            "lost": 1,
                            "reasons": [
                                {"outcome": "lost", "count": 1, "reason": "authored unsupported shape"}
                            ],
                        }
                    ],
                }
            },
            "convert.lossy",
            "pad",
        ),
        (
            "pick",
            {"picks": [{"row": "Authored:Part", "evidence": "UNKNOWN"}]},
            "pick.row-unverified",
            "Authored:Part",
        ),
        (
            "pick",
            {"candidates": [{"row": "Authored:Part", "evidence": "UNVERIFIED"}]},
            "pick.row-unverified",
            "Authored:Part",
        ),
        (
            "pick",
            {"proposed": [{"id": "Authored:Part", "file": "devices/proposed/authored.toml"}]},
            "pick.row-unverified",
            "Authored:Part",
        ),
        (
            "library",
            {
                "schema": "fenolite.library-seed.v0",
                "source": "D-0001",
                "evidence": "UNVERIFIED",
                "items": [
                    {"kind": "symbol", "id": "Authored:Part", "version": "1.0.0", "element": "authored-id"}
                ],
            },
            "library.seed-unverified",
            "D-0001",
        ),
        (
            "check",
            {
                "stages": [
                    {
                        "name": "copper.clearance",
                        "status": "ok",
                        "evidence": {"level": "UNVERIFIED"},
                        "summary": {"unset_pairs": 1},
                    }
                ]
            },
            "copper.clearance-unset",
            "",
        ),
        ("family", {"decoded": [{"suffix": "authored opaque suffix"}]}, "family.suffix-opaque", ""),
        (
            "impedance",
            {"counts": {"left_out": 1}, "rows": [{"estimate": {"mohm": None}}]},
            "impedance.no-stackup",
            "",
        ),
    ],
)
def test_incomplete_state_and_its_existing_issue_are_both_required(
    monkeypatch: pytest.MonkeyPatch, command: str, result: dict[str, Any], code: str, where: str
) -> None:
    monkeypatch.setenv("FENOLITE_CONTRACT_CHECK", "1")
    issues = (Issue(code, "warning", "authored limitation", where=where),)
    assert evidence_issues(command, Evidence(), issues, no_claim=False, result=result) == issues
    for state, markers in ((result, ()), ({"complete": True}, issues)):
        with pytest.raises(CliError, match="UNVERIFIED evidence"):
            evidence_issues(command, Evidence(), markers, no_claim=False, result=state)


@pytest.mark.parametrize("fault", ["lossy-only", "zero", "reason", "kind", "marker"])
def test_conversion_loss_marker_cannot_replace_reported_losses(
    monkeypatch: pytest.MonkeyPatch, fault: str
) -> None:
    monkeypatch.setenv("FENOLITE_CONTRACT_CHECK", "1")
    row = {"kind": "pad", "lost": 1, "reasons": [{"outcome": "lost", "count": 1, "reason": "authored"}]}
    report = {"lossy": True, "rows": [row]}
    issues = (Issue("convert.lossy", "warning", "authored loss", where="pad"),)
    if fault == "lossy-only":
        report["rows"] = []
    elif fault == "zero":
        row["lost"] = 0
    elif fault == "reason":
        row["reasons"] = []
    elif fault == "kind":
        row["kind"] = "track"
    else:
        issues = (Issue("convert.changed", "info", "authored change", where="pad"),)
    with pytest.raises(CliError, match="UNVERIFIED evidence"):
        evidence_issues("convert", Evidence(), issues, no_claim=False, result={"report": report})


@pytest.mark.parametrize(
    "fault", ["schema", "evidence", "source", "items", "item", "marker-source", "unmarked-empty"]
)
def test_seed_limitation_requires_its_actual_source_and_state(
    monkeypatch: pytest.MonkeyPatch, fault: str
) -> None:
    monkeypatch.setenv("FENOLITE_CONTRACT_CHECK", "1")
    result: dict[str, Any] = {
        "schema": "fenolite.library-seed.v0",
        "source": "D-0001",
        "evidence": "UNVERIFIED",
        "items": [{"kind": "symbol", "id": "Authored:Part", "version": "1.0.0", "element": "authored-id"}],
    }
    issues = (Issue("library.seed-unverified", "info", "authored seed limitation", where="D-0001"),)
    if fault == "marker-source":
        issues = (dataclasses.replace(issues[0], where="D-0002"),)
    elif fault == "item":
        result["items"] = [{"kind": "symbol"}]
    elif fault == "unmarked-empty":
        result["items"] = []
    else:
        del result[fault]
    with pytest.raises(CliError, match="UNVERIFIED evidence"):
        evidence_issues("library", Evidence(), issues, no_claim=False, result=result)


def test_unset_clearance_marker_requires_positive_unset_pairs(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("FENOLITE_CONTRACT_CHECK", "1")
    stage = {**_skipped_stage(), "status": "ok", "reason": "", "summary": {"unset_pairs": 0}}
    issues = (Issue("copper.clearance-unset", "info", "authored no-clearance limitation"),)
    with pytest.raises(CliError, match="UNVERIFIED evidence"):
        evidence_issues("check", Evidence(), issues, no_claim=False, result={"stages": [stage]})


def test_pick_limitation_requires_the_matching_actual_row(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("FENOLITE_CONTRACT_CHECK", "1")
    issues = (Issue("pick.row-unverified", "info", "authored row limitation", where="Authored:Other"),)
    with pytest.raises(CliError, match="UNVERIFIED evidence"):
        evidence_issues(
            "pick",
            Evidence(),
            issues,
            no_claim=False,
            result={"picks": [{"row": "Authored:Part", "evidence": "UNKNOWN"}]},
        )


@pytest.mark.parametrize(
    "name,hidden,accepted", [("_echo", True, True), ("_echo", False, False), ("_other_private", True, False)]
)
def test_only_exact_hidden_protocol_fixture_is_exempt(
    monkeypatch, tmp_path: Path, name, hidden, accepted
) -> None:
    from fenolite.cli import main as cli_main
    from fenolite.cli.api import discover

    commands = discover()
    source = commands["_echo"]
    command = dataclasses.replace(
        source,
        name=name,
        help=None if hidden else "authored visible command",
        run=lambda args, ctx: Result(result={"authored": True}),
    )
    monkeypatch.setattr(cli_main, "discover", lambda: {**commands, name: command})
    monkeypatch.setenv("FENOLITE_CONTRACT_CHECK", "1")
    code, _, error, _ = run(monkeypatch, tmp_path, name)
    assert code == (0 if accepted else 1)
    if not accepted:
        assert error["code"] == "FEN-1001"


@pytest.mark.parametrize(
    "state,code,where",
    [
        (
            {"connections": {"after": 1}, "open": [{"net": "AUTH", "connections": [{"length": 1}]}]},
            "route.unrouted",
            "AUTH",
        ),
        ({"selected": ["AUTH"], "not_attempted": ["AUTH"]}, "route.budget-exhausted", "authored"),
        ({"budget": {"exhausted": True, "seconds": 1.0, "spent": 1.0}}, "route.budget-exhausted", "authored"),
    ],
)
def test_route_lower_scope_requires_actual_state_and_matching_issue(monkeypatch, state, code, where) -> None:
    monkeypatch.setenv("FENOLITE_CONTRACT_CHECK", "1")
    issues = (Issue(code, "warning", "authored limitation", where=where),)
    assert evidence_issues("route", Evidence(), issues, no_claim=False, result=state) == issues
    for command, data, markers in (
        ("route", state, ()),
        ("route", {}, issues),
        ("route", {"incomplete": True}, issues),
        ("route", {"budget": {"exhausted": True}}, issues),
        ("fmt", state, issues),
        ("route", {"connections": {"after": 0}, "open": []}, issues),
    ):
        with pytest.raises(CliError, match="UNVERIFIED evidence"):
            evidence_issues(command, Evidence(), markers, no_claim=False, result=data)


def test_missing_board_thickness_requires_its_actual_unmeasured_pair_receipt(monkeypatch) -> None:
    from copy import deepcopy

    monkeypatch.setenv("FENOLITE_CONTRACT_CHECK", "1")
    state = {
        "summary": {"distances": {"pairs": 1}},
        "inputs": {"kinds": ["creepage"], "board_thickness": None, "board_thickness_source": None},
        "distances": [{"net_a": "A", "net_b": "B", "creepage": None}],
    }
    issues = (Issue("analysis.input-missing", "info", "authored missing thickness", where="board thickness"),)
    assert evidence_issues("analyze", Evidence(), issues, no_claim=False, result=state) == issues
    complete = deepcopy(state)
    complete["distances"][0]["creepage"] = {"low": 1, "high": 1}
    supplied = deepcopy(state)
    supplied["inputs"] |= {"board_thickness": 1_600_000, "board_thickness_source": "option"}
    count = deepcopy(state)
    count["summary"]["distances"]["pairs"] = 0
    missing_fields = deepcopy(state)
    missing_fields["inputs"] = {"kinds": ["creepage"]}
    for data, markers in (
        ({}, issues),
        (state, ()),
        (complete, issues),
        (supplied, issues),
        (count, issues),
        (missing_fields, issues),
    ):
        with pytest.raises(CliError, match="UNVERIFIED evidence"):
            evidence_issues("analyze", Evidence(), markers, no_claim=False, result=data)
