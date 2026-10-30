# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The stage ``circuit.rules`` of ``fenolite check`` (capability verification-loop, "Circuit stage"; change
c0252): its place, its skip reasons and the two variants of ``examples/sensor_rails``."""

from __future__ import annotations

import io
import json
from pathlib import Path
from typing import Any

import pytest
from _projects import built_blink_project
from _sensor_rails import copy_example

import fenolite.cli.main as cli_main
from fenolite.checks import STAGE_ORDER
from fenolite.checks.circuit import circuit_stage
from fenolite.checks.documents import DOCUMENT_STAGES
from fenolite.checks.stages import ORACLE_STAGES
from fenolite.cli._script import run_design_script
from fenolite.dsl import to_model
from fenolite.model.design import Design

ROOT = Path(__file__).resolve().parents[3]


@pytest.fixture(autouse=True)
def isolated(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("KICAD_CONFIG_HOME", str(tmp_path / "kicad-config"))


def cli(monkeypatch: pytest.MonkeyPatch, *args: str) -> tuple[int, dict[str, Any]]:
    out, err = io.StringIO(), io.StringIO()
    with monkeypatch.context() as patch:
        patch.setattr("sys.stdout", out)
        patch.setattr("sys.stderr", err)
        code = cli_main.main([*args, "--json"])
    return code, json.loads(out.getvalue() or err.getvalue().splitlines()[-1])


def stage(env: dict[str, Any]) -> dict[str, Any]:
    return next(s for s in env["result"]["stages"] if s["name"] == "circuit.rules")


def test_order_and_place() -> None:
    assert STAGE_ORDER[:2] == ("model.validate", "circuit.rules")
    assert DOCUMENT_STAGES[:2] == ("model.validate", "circuit.rules")
    assert "circuit.rules" not in ORACLE_STAGES


def test_skip_without_parameters_and_without_a_model() -> None:
    assert circuit_stage(None, built=False).reason == "no-model"
    assert circuit_stage(None, built=True).reason == "cache-unreadable"
    assert circuit_stage(Design.new("plain", seed=1), built=True).reason == "no-parameters"


def test_skip_a_board_without_parameters_is_unchanged(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    root = built_blink_project(tmp_path / "blink")
    code, env = cli(monkeypatch, "check", str(root), "--stages", "circuit.rules")
    assert code == 0 and (stage(env)["status"], stage(env)["reason"]) == ("skipped", "no-parameters")


def test_skip_a_native_board_has_no_model(monkeypatch: pytest.MonkeyPatch) -> None:
    board = ROOT / "tests" / "data" / "kicad" / "board" / "two_layer.kicad_pcb"
    code, env = cli(monkeypatch, "check", str(board), "--stages", "circuit.rules")
    assert code == 0 and (stage(env)["status"], stage(env)["reason"]) == ("skipped", "no-model")


def test_good_variant_passes(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    folder = copy_example(tmp_path / "ex")
    out = tmp_path / "out"
    code, env = cli(monkeypatch, "build", str(folder / "good.py"), "--out", str(out), "--confirm")
    assert code == 0, env["issues"]
    code, env = cli(monkeypatch, "check", str(out), "--stages", "model.validate,circuit.rules")
    names = [s["name"] for s in env["result"]["stages"]]
    assert code == 0 and names == ["model.validate", "circuit.rules"]
    found = stage(env)
    assert found["status"] == "ok" and found["summary"]["halves"] == {
        "rails": "ran",
        "contracts": "no-contracts",
    }
    assert found["summary"]["rails"] == found["summary"]["judged"] == 2
    assert found["evidence"]["level"] == "UNVERIFIED"  # the illustrative device records
    assert not [i for i in env["issues"] if i["code"].startswith("circuit.")]


def test_over_budget_bad_variant_model(tmp_path: Path) -> None:
    folder = copy_example(tmp_path / "ex")
    model = to_model(run_design_script(folder / "bad.py").design)
    result = circuit_stage(model, built=True)
    assert result.status == "errors"
    assert [i.code for i in result.issues if i.code == "circuit.rail-current"] == ["circuit.rail-current"]
