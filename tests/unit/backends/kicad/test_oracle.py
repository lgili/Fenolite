# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""``KicadOracle`` with a fake ``kicad-cli`` (capability kicad-oracle, "Check canary injection";
backend-protocol, "Oracle protocol"; change c0013). Hermetic: the fake reports the canary pair as KiCad
would."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from _fakecli import calls, fake_kicad_cli, report_with
from _projects import STEM, authored_project, native_project, tree_snapshot

from fenolite.backends.base import Oracle
from fenolite.backends.kicad import canary
from fenolite.backends.kicad import drc as drcmod
from fenolite.backends.kicad import oracle as oraclemod
from fenolite.backends.kicad.canary import CANARY_RULE_NAME, CANARY_UUIDS
from fenolite.backends.kicad.cli import KicadCli
from fenolite.backends.kicad.oracle import KicadOracle
from fenolite.backends.kicad.projectset import project_set
from fenolite.core.evidence import Level, strength


def _oracle(tmp_path: Path, **fake: object) -> tuple[KicadOracle, Path]:
    script = fake_kicad_cli(tmp_path / "bin", **fake)  # type: ignore[arg-type]
    timeout = 3.0 if fake.get("sleep") else 60.0
    return KicadOracle(KicadCli(script, timeout=timeout)), script


def _drc_calls(script: Path) -> list[dict[str, object]]:
    return [c for c in calls(script) if c["args"][:2] == ["pcb", "drc"]]  # type: ignore[index]


def test_kicad_oracle_satisfies_the_protocol(tmp_path: Path) -> None:
    oracle: Oracle = KicadOracle(KicadCli(tmp_path / "kicad-cli"))
    assert oracle.name == "kicad"


def test_staging_outside_the_project(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(canary, "CANARY_TWO_RUN", frozenset())  # one run: the canary run gives the report
    root = authored_project(tmp_path, major=10)
    oracle, script = _oracle(tmp_path, writes=("x.kicad_prl",))
    before = tree_snapshot(root)
    user_rules = (root / f"{STEM}.kicad_dru").read_bytes().decode("utf-8")
    outcome = oracle.drc(project_set(root))
    (call,) = _drc_calls(script)
    files: dict[str, str] = call["files"]  # type: ignore[assignment]
    assert files[f"{STEM}.kicad_dru"].startswith(user_rules)
    assert CANARY_RULE_NAME in files[f"{STEM}.kicad_dru"]
    assert all(u in files[f"{STEM}.kicad_pcb"] for u in CANARY_UUIDS)  # the staged board, not the original
    assert "--exit-code-violations" not in call["args"]  # type: ignore[operator]
    assert tree_snapshot(root) == before
    assert outcome.tool_writes == ("x.kicad_prl",)
    assert outcome.canary == "fired" and outcome.canary_reason == ""
    assert outcome.canary_removed == 1
    assert outcome.report is not None and outcome.report.violations == ()


def test_absent_when_the_report_lacks_the_pair(tmp_path: Path) -> None:
    root = authored_project(tmp_path, major=10)
    user = {"type": "clearance", "description": "user", "severity": "error",
            "items": [{"uuid": "u1", "description": "t", "pos": {"x": 1, "y": 2}}]}  # fmt: skip
    oracle, _ = _oracle(tmp_path, drc_report=report_with(user))
    outcome = oracle.drc(project_set(root))
    assert outcome.canary == "absent"
    assert outcome.report is not None and len(outcome.report.violations) == 1


def test_unproven_major(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(canary, "CANARY_SUPPORT", frozenset())
    root = authored_project(tmp_path, major=10)
    oracle, script = _oracle(tmp_path)
    outcome = oracle.drc(project_set(root))
    assert (outcome.canary, outcome.canary_reason) == ("inconclusive", "placement-unproven")
    (call,) = _drc_calls(script)
    files: dict[str, str] = call["files"]  # type: ignore[assignment]
    assert files[f"{STEM}.kicad_pcb"] == (root / f"{STEM}.kicad_pcb").read_text(encoding="utf-8")
    assert files[f"{STEM}.kicad_dru"] == (root / f"{STEM}.kicad_dru").read_text(encoding="utf-8")


def test_selector_unproven(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(canary, "SELECTOR_SUPPORT", {"net": frozenset({9})})
    oracle, _ = _oracle(tmp_path)
    outcome = oracle.drc(project_set(authored_project(tmp_path, major=10)))
    assert (outcome.canary, outcome.canary_reason) == ("inconclusive", "selector-unproven")


def test_names_already_taken(tmp_path: Path) -> None:
    root = authored_project(tmp_path, major=10)
    board = root / f"{STEM}.kicad_pcb"
    board.write_text(
        board.read_text(encoding="utf-8").replace('"LED_A"', '"FENOLITE_CANARY_A"'), encoding="utf-8"
    )
    oracle, _ = _oracle(tmp_path)
    outcome = oracle.drc(project_set(root))
    assert (outcome.canary, outcome.canary_reason) == ("inconclusive", "names-taken")
    assert outcome.report is not None


def test_clearance_ignored(tmp_path: Path) -> None:
    root = authored_project(tmp_path, major=10)
    path = root / f"{STEM}.kicad_pro"
    data = json.loads(path.read_text(encoding="utf-8"))
    data["board"]["design_settings"].setdefault("rule_severities", {})["clearance"] = "ignore"
    path.write_text(json.dumps(data), encoding="utf-8")
    oracle, _ = _oracle(tmp_path)
    outcome = oracle.drc(project_set(root))
    assert (outcome.canary, outcome.canary_reason) == ("inconclusive", "clearance-ignored")


def test_not_applicable_without_rules(tmp_path: Path) -> None:
    oracle, _ = _oracle(tmp_path)
    outcome = oracle.drc(project_set(native_project(tmp_path, rules=None)))
    assert outcome.canary == "not-applicable" and outcome.report is not None


def test_board_unparsed(tmp_path: Path) -> None:
    root = authored_project(tmp_path, major=10)
    board = root / f"{STEM}.kicad_pcb"
    board.write_bytes(board.read_bytes() + b" trailing")
    oracle, _ = _oracle(tmp_path)
    assert oracle.drc(project_set(root)).canary_reason == "board-unparsed"


def test_missing_report(tmp_path: Path) -> None:
    oracle, _ = _oracle(tmp_path, drc_report="")
    outcome = oracle.drc(project_set(authored_project(tmp_path, major=10)))
    assert outcome.report is None
    assert (outcome.canary, outcome.canary_reason) == ("inconclusive", "no-report")
    assert outcome.returncode == 3 and outcome.message == "Failed to load board"
    assert outcome.evidence.level == Level.UNVERIFIED


def test_timeout(tmp_path: Path) -> None:
    oracle, _ = _oracle(tmp_path, sleep=10.0)
    outcome = oracle.drc(project_set(authored_project(tmp_path, major=10)))
    assert outcome.outcome == "timeout" and outcome.returncode is None and outcome.report is None
    assert outcome.canary_reason == "no-report"


def test_two_run_path(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(canary, "CANARY_TWO_RUN", frozenset({10}))
    root = authored_project(tmp_path, major=10)
    oracle, script = _oracle(tmp_path)
    outcome = oracle.drc(project_set(root))
    plain, staged = _drc_calls(script)
    assert not any(u in plain["files"][f"{STEM}.kicad_pcb"] for u in CANARY_UUIDS)  # type: ignore[index]
    assert all(u in staged["files"][f"{STEM}.kicad_pcb"] for u in CANARY_UUIDS)  # type: ignore[index]
    assert outcome.canary == "fired" and outcome.canary_removed == 0


def test_evidence_never_above_its_parts(tmp_path: Path) -> None:
    oracle, _ = _oracle(tmp_path)
    outcome = oracle.drc(project_set(authored_project(tmp_path, major=10)))
    assert outcome.evidence.oracle == "kicad-cli 10.0.6"
    for part in (drcmod.EVIDENCE, oraclemod.EVIDENCE):
        assert strength(outcome.evidence.level) <= strength(part.level)
    assert set(outcome.evidence.hypotheses) >= {"H-K-DRC-JSON", "H-K-CHECK-COPYSET", "H-K-CHECK-CANARY-2"}
