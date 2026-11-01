# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The contract half of the stage ``circuit.rules`` (change c0253; capabilities verification-loop,
"Contracts in the circuit stage" and "Device records injected into the circuit stage", and
electrical-contracts, "Contract judge on the model", "Device records of the judgement" and "Contract
evidence")."""

from __future__ import annotations

import ast
import json
import subprocess
from pathlib import Path

import pytest
from _contracts import ROOT, built_sensor, cli, device, sensor, sensor_model

from fenolite.backends.base import ProjectSet
from fenolite.catalog.devices import device_digest as catalog_digest
from fenolite.checks import run_checks
from fenolite.checks.circuit import circuit_stage, judge_circuit
from fenolite.checks.circuit.table import device_digest
from fenolite.cli._contracts import classes_of
from fenolite.dsl import Design, Net, connect, ohm, to_model, value_of, within

CIRCUIT = ROOT / "src" / "fenolite" / "checks" / "circuit"
DESIGNED = [
    "circuit.expect-unsure",
    "circuit.rating-current",
    "circuit.rating-power",
    "circuit.rating-voltage",
]


def stage(env: dict[str, object]) -> dict[str, object]:
    return next(s for s in env["result"]["stages"] if s["name"] == "circuit.rules")  # type: ignore[index, union-attr]


def test_gate_a_failing_rating_gates_the_check(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Scenario "A failing rating gates the check"."""
    out = built_sensor(monkeypatch, tmp_path, "bad")
    code, env = cli(monkeypatch, "check", str(out), "--stages", "model.validate,circuit.rules")
    found = stage(env)
    assert code == 5 and found["status"] == "errors" and "requirements" in found["summary"]
    assert any(i["code"] == "circuit.rating-voltage" and i["severity"] == "error" for i in env["issues"])


def test_contracts_alone_run_the_stage() -> None:
    """Scenario "Contracts alone run the stage"."""
    d = Design("t")
    r1 = d.part("R1", device="Fenolite:R_0603", value=ohm("1k").pct(1))
    connect(Net("A"), r1.P1)
    connect(Net("B"), r1.P2)
    d.expect(within(value_of(r1), ohm("1k").pct(5)), "a resistor within 5 %")
    model = to_model(d)
    result = circuit_stage(model, built=True, devices={}, classes=classes_of(model))
    assert result.status == "ok" and result.summary["halves"] == {
        "contracts": "ran",
        "rails": "no-parameters",
    }
    rows = result.summary["requirements"]
    assert [r["id"] for r in rows if r["id"].startswith("circuit.expect")] == [
        "circuit.expect:design/expect#1"
    ]  # type: ignore[index, union-attr]


def test_a_board_without_a_model_is_unchanged(monkeypatch: pytest.MonkeyPatch) -> None:
    """Scenario "A board without a model is unchanged"."""
    board = ROOT / "tests" / "data" / "kicad" / "board" / "two_layer.kicad_pcb"
    code, env = cli(monkeypatch, "check", str(board), "--stages", "circuit.rules")
    assert code == 0 and (stage(env)["status"], stage(env)["reason"]) == ("skipped", "no-model")


def test_injected_a_fake_mapping(tmp_path: Path) -> None:
    """Scenario "A fake mapping": with the resolved records the four designed findings; with none, no
    rating finding and one ``circuit.rating-missing`` info."""
    folder = sensor(tmp_path)
    model, devices = sensor_model(folder, "bad")
    project = ProjectSet(root=folder, board="x.kicad_pcb", files={"x.kicad_pcb": folder / "x.kicad_pcb"})
    with_records = run_checks(
        project=project, stages=("circuit.rules",), model=model, built=True, validator=None, oracle=None,
        circuit_inputs=lambda m: (devices, classes_of(m)),
    )  # fmt: skip
    without = run_checks(
        project=project, stages=("circuit.rules",), model=model, built=True, validator=None, oracle=None
    )
    found = [i.code for i in with_records.stages[0].issues if i.severity != "info"]
    assert sorted(found) == DESIGNED
    rest = without.stages[0].issues
    assert not [
        i for i in rest if i.code.startswith("circuit.rating-") and i.code != "circuit.rating-missing"
    ]
    assert [(i.code, i.severity) for i in rest if i.code == "circuit.rating-missing"] == [
        ("circuit.rating-missing", "info")
    ]


def test_device_changed_after_the_build(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Scenario "A device edited after the build"."""
    out = built_sensor(monkeypatch, tmp_path)
    record = out.parent / "devices" / "example_cap_50v.toml"
    record.write_text(record.read_text(encoding="utf-8").replace('"50V"', '"40V"'), encoding="utf-8")
    code, env = cli(monkeypatch, "check", str(out), "--stages", "circuit.rules")
    (changed,) = [i for i in env["issues"] if i["code"] == "circuit.device-changed"]
    assert changed["severity"] == "warning" and changed["where"] == "C1" and changed["message"].count(" ") > 5
    (cap,) = [
        r for r in stage(env)["summary"]["requirements"] if r["id"] == "circuit.rating-voltage:C1:voltage"
    ]  # type: ignore[index, union-attr]
    assert cap["limit"]["range"]["high"] == {"m": 2, "e": 1}  # 50 % of 40 V
    assert code == 0


def test_deterministic_and_tool_free(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Scenario "Deterministic and tool-free"."""
    folder = sensor(tmp_path)
    model, devices = sensor_model(folder, "bad")

    def refuse(*args: object, **kwargs: object) -> None:
        raise AssertionError("no process may start")

    monkeypatch.setattr(subprocess, "run", refuse)
    monkeypatch.setattr(subprocess, "Popen", refuse)
    first = judge_circuit(model, devices=devices, classes=classes_of(model))
    second = judge_circuit(model, devices=devices, classes=classes_of(model))

    def dump(result: object) -> str:
        issues = [[i.code, i.message] for i in result.issues]  # type: ignore[attr-defined]
        return json.dumps([issues, result.summary["requirements"]], sort_keys=True)  # type: ignore[attr-defined]

    assert dump(first) == dump(second)


def test_layering_holds() -> None:
    """Scenario "Layering holds": no module of ``checks/circuit/`` imports the catalog, the roles or the
    analyses."""
    for path in CIRCUIT.glob("*.py"):
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            names = [a.name for a in node.names] if isinstance(node, ast.Import) else []
            if isinstance(node, ast.ImportFrom) and node.module:
                names = [node.module]
            for name in names:
                assert not name.startswith(("fenolite.catalog", "fenolite.roles", "fenolite.analysis")), path


def test_an_unverified_device_lowers_the_stage_evidence(tmp_path: Path) -> None:
    """Scenario "An unverified device lowers the stage evidence"."""
    folder = sensor(tmp_path)
    model, devices = sensor_model(folder, "bad")
    result = circuit_stage(model, built=True, devices=devices, classes=classes_of(model))
    assert result.evidence.level.value == "UNVERIFIED" and "H-G-CIRCUIT-EXAMPLE" in result.evidence.hypotheses
    (cap,) = [r for r in result.summary["requirements"] if r["id"] == "circuit.rating-voltage:C1:voltage"]  # type: ignore[index, union-attr]
    assert cap["limit"]["evidence"] == "UNVERIFIED"


def test_digest_equals_the_catalogs() -> None:
    record = device(
        'id = "Test:X"\nsymbol = "Fenolite:Resistor"\nfootprint = "Fenolite:Chip_0603"\n[pins]\nP1 = "1"\n'
    )
    assert device_digest(record) == catalog_digest(record)
