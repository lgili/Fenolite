# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Mechanical plan evidence never substitutes a claim of routing correctness (c0219)."""

from __future__ import annotations

import hashlib
from dataclasses import replace
from pathlib import Path

import pytest
from _checkcli import run

from fenolite.cli import cmd_route
from fenolite.core.evidence import Evidence, Level
from fenolite.routing.direct import DirectRouter

ROOT = Path(__file__).resolve().parents[3]
SOURCE = ROOT / "tests/data/kicad/routing/two_pads.kicad_pcb"


def _args(board: Path) -> tuple[str, ...]:
    return ("route", str(board), "--router", "direct", "--out", "routed.kicad_pcb")


def test_direct_plan_has_only_mechanical_scope_and_replays_reviewed_bytes(
    monkeypatch, tmp_path: Path
) -> None:
    board = tmp_path / "input.kicad_pcb"
    board.write_bytes(SOURCE.read_bytes())
    code, env, error, _ = run(monkeypatch, tmp_path, *_args(board), "--dry-run")
    assert code == 0, error
    assert env["evidence"]["level"] == "INFERRED"
    assert env["evidence"]["hypotheses"] == ["H-G-ROUTE-PLAN"]
    planned = env["result"]["plan"][0]
    assert not (tmp_path / planned["path"]).exists()

    def do_not_reroute(*args, **kwargs):
        raise AssertionError("confirm must replay the reviewed bytes")

    monkeypatch.setattr(cmd_route, "_router", do_not_reroute)
    code, done, error, _ = run(
        monkeypatch, tmp_path, *_args(board), "--confirm", "--plan", env["result"]["plan_id"]
    )
    assert code == 0, error
    data = (tmp_path / planned["path"]).read_bytes()
    assert hashlib.sha256(data).hexdigest() == planned["sha256"]
    assert done["evidence"] == env["evidence"]


@pytest.mark.parametrize("change", ["input", "target"])
def test_changed_plan_input_or_target_refuses_without_writes(
    monkeypatch, tmp_path: Path, change: str
) -> None:
    board = tmp_path / "input.kicad_pcb"
    board.write_bytes(SOURCE.read_bytes())
    code, env, error, _ = run(monkeypatch, tmp_path, *_args(board), "--dry-run")
    assert code == 0, error
    changed = board if change == "input" else tmp_path / "routed.kicad_pcb"
    changed.write_bytes(changed.read_bytes() + b"\n" if changed.exists() else b"authored changed target\n")
    before = changed.read_bytes()
    code, _, error, _ = run(
        monkeypatch, tmp_path, *_args(board), "--confirm", "--plan", env["result"]["plan_id"]
    )
    assert code == 4 and error["code"] == "FEN-4002"
    assert changed.read_bytes() == before
    if change == "input":
        assert not (tmp_path / "routed.kicad_pcb").exists()


@pytest.mark.parametrize("level,complete", [(Level.UNKNOWN, True), (Level.UNVERIFIED, False)])
def test_unknown_or_incomplete_evidence_is_never_promoted(level: Level, complete: bool) -> None:
    original = Evidence(level, hypotheses=("H-G-DSN-INCOMPLETE",))
    result = cmd_route._plan_evidence(original, oracle="authored", complete=complete)
    assert result.level == level and result.hypotheses == original.hypotheses


@pytest.mark.parametrize("level", [Level.INFERRED, Level.UNVERIFIED])
def test_actual_external_hypotheses_are_retained_without_inventing_them(level: Level) -> None:
    source = Evidence(level, hypotheses=("H-G-DSN-UNITS",))
    result = cmd_route._plan_evidence(source, oracle="authored external", complete=True)
    assert result.level == Level.INFERRED
    assert result.hypotheses == ("H-G-DSN-UNITS", "H-G-ROUTE-PLAN")


def test_router_fault_has_no_output_plan(monkeypatch, tmp_path: Path) -> None:
    class FaultRouter(DirectRouter):
        def route(self, job):
            raise RuntimeError("authored route fault")

    monkeypatch.setattr(cmd_route, "_router", lambda *args: FaultRouter())
    code, env, error, _ = run(monkeypatch, tmp_path, *_args(SOURCE), "--dry-run")
    assert code == 1 and error["code"] == "FEN-1001"
    assert not env["result"].get("plan")
    assert not (tmp_path / "routed.kicad_pcb").exists()


def test_unknown_result_scope_stays_unknown_on_actual_direct_output(monkeypatch, tmp_path: Path) -> None:
    class UnknownRouter(DirectRouter):
        def route(self, job):
            return replace(super().route(job), evidence=Evidence(Level.UNKNOWN))

    monkeypatch.setattr(cmd_route, "_router", lambda *args: UnknownRouter())
    code, env, error, _ = run(monkeypatch, tmp_path, *_args(SOURCE), "--dry-run")
    assert code == 0, error
    assert env["evidence"]["level"] == "UNKNOWN"
    assert "H-G-ROUTE-PLAN" not in env["evidence"]["hypotheses"]


def test_incomplete_native_label_cannot_certify_partial_copper() -> None:
    source = Evidence(Level.KICAD_VERIFIED, hypotheses=("H-G-DSN-ROUTE",))
    result = cmd_route._plan_evidence(source, oracle="authored", complete=False)
    assert result.level == Level.UNVERIFIED
    assert result.hypotheses == source.hypotheses
