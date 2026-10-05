# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""``fenolite bom`` with the ``model`` source (capability cli-contract, "Bom command"; change c0064).
Hermetic: no tool runs. The ``kicad`` source waits for the schematic writer (c0061); here it only has to
refuse and name the other source."""

from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
from pathlib import Path

import _schema
import pytest
from _asmcli import COLUMNS, FIXTURE, INVALID, R1, built, isolate
from _checkcli import run, without_elapsed
from _projects import tree_snapshot

from fenolite.cli.cmd_bom import COMMAND

WITH_BIN = R1.replace(")", ', properties={"Bin": "A7"})')
"""The blink's resistor with a made-up user property."""


@pytest.fixture(autouse=True)
def isolated(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    isolate(monkeypatch, tmp_path)

    def refuse(*args: object, **kwargs: object) -> None:
        raise AssertionError("a subprocess was started")

    monkeypatch.setattr(subprocess, "run", refuse)
    monkeypatch.setattr(subprocess, "Popen", refuse)


def test_table_as_json(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    code, env, _, _ = run(monkeypatch, tmp_path, "bom", str(FIXTURE), "--source", "model")
    assert code == 0 and list(tmp_path.iterdir()) == []
    result = env["result"]
    assert (result["source"], result["template"]) == ("model", "default")
    assert result["columns"] == ["refs", "quantity", "value", "footprint"]
    assert result["lines"] == [
        {"refs": "D1", "quantity": "1", "value": "LED", "footprint": "Fenolite_Test:LED_THT_3mm"},
        {"refs": "R1", "quantity": "1", "value": "330", "footprint": "Fenolite_Test:R_0603"},
    ]
    assert result["counts"] == {"parts": 2, "lines": 2, "dnp": 0, "left_out": 0}
    assert "changes" not in result and "plan" not in result and env["receipt"] is None
    # a board that Fenolite did not build: the board is read, and nothing is claimed about a schematic
    assert env["evidence"] == {
        "level": "INFERRED",
        "oracle": None,
        "hypotheses": ["H-K-BOM-MODEL", "H-K-PCB-READ"],
    }


def test_file_with_a_template(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    folder = built(monkeypatch, tmp_path, (R1, WITH_BIN))
    before = tree_snapshot(folder)
    args = ("bom", str(folder), "--source", "model", "--template", COLUMNS, "--out", "bom.csv", "--confirm")
    first, second = tmp_path / "a", tmp_path / "b"
    first.mkdir()
    second.mkdir()
    code, env, _, _ = run(monkeypatch, first, *args)
    assert code == 0, env["issues"]
    data = (first / "bom.csv").read_bytes()
    assert data.decode("utf-8").splitlines() == [
        "Parts,Count,Marking,Shape,Bin",
        "D1,1,LED,Mini_LED_THT_3mm,",
        "R1,1,330,Mini_R_0603,A7",
        "U1,1,MCU,Mini_QFP-32_7x7mm_P0.8mm,",
    ]
    assert b"\r" not in data and data.endswith(b"\n")
    assert env["receipt"]["written"] == [{"path": "bom.csv", "sha256": hashlib.sha256(data).hexdigest()}]
    assert env["result"]["template"] == "columns.toml" and env["issues"] == []
    assert env["evidence"] == {"level": "INFERRED", "oracle": None, "hypotheses": ["H-K-BOM-MODEL"]}
    code, _, _, _ = run(monkeypatch, second, *args)
    assert code == 0 and (second / "bom.csv").read_bytes() == data
    assert tree_snapshot(folder) == before


def test_a_property_no_part_has(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    code, env, _, _ = run(
        monkeypatch, tmp_path, "bom", str(FIXTURE), "--source", "model", "--template", COLUMNS
    )
    assert code == 0
    assert [(i["code"], i["severity"], i["where"]) for i in env["issues"]] == [
        ("bom.property-missing", "info", "Bin")
    ]
    assert [line["Bin"] for line in env["result"]["lines"]] == ["", ""]


def test_confirmation_required(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    code, env, err, _ = run(
        monkeypatch, tmp_path, "bom", str(FIXTURE), "--source", "model", "--out", "bom.csv"
    )
    assert code == 4 and err["code"] == "FEN-4001"
    assert [(p["path"], p["kind"]) for p in env["result"]["plan"]] == [("bom.csv", "bom")]
    assert list(tmp_path.iterdir()) == []


def test_no_schematic(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    code, env, err, _ = run(monkeypatch, tmp_path, "bom", str(FIXTURE))
    assert code == 3 and err["code"] == "FEN-3001"
    assert "--source model" in err["hint"] and "two_layer.kicad_sch" in err["message"]
    assert env["ok"] is False and env["result"] == {}


def test_the_kicad_source_never_falls_back(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """With a schematic next to the board, the ``kicad`` source still cannot answer in this version: the
    command says so instead of listing the model's parts under the wrong name."""
    board = tmp_path / "two_layer.kicad_pcb"
    shutil.copyfile(FIXTURE, board)
    board.with_suffix(".kicad_sch").write_text("(kicad_sch)\n", encoding="utf-8", newline="\n")
    for extra in ((), ("--source", "kicad")):
        code, env, err, _ = run(monkeypatch, tmp_path, "bom", str(board), *extra)
        assert code == 2 and err["code"] == "FEN-2001"
        assert "--source model" in err["hint"] and env["result"] == {}


def test_difference_of_two_projects(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    first = built(monkeypatch, tmp_path, name="first")
    second = built(monkeypatch, tmp_path, (R1, R1.replace('"330"', '"470"')), name="second")
    code, env, _, _ = run(
        monkeypatch, tmp_path, "bom", str(second), "--source", "model", "--against", str(first)
    )
    assert code == 0
    assert env["result"]["changes"] == [
        {"key": ["330", "Mini:Mini_R_0603"], "change": "removed", "a_refs": ["R1"], "b_refs": []},
        {"key": ["470", "Mini:Mini_R_0603"], "change": "added", "a_refs": [], "b_refs": ["R1"]},
    ]
    code, env, _, _ = run(
        monkeypatch, tmp_path, "bom", str(first), "--source", "model", "--against", str(first)
    )
    assert code == 0 and env["result"]["changes"] == []


def test_an_unreadable_model(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    folder = built(monkeypatch, tmp_path)
    (folder / ".fenolite" / "circuit.json").write_text("{", encoding="utf-8")
    code, _, err, _ = run(monkeypatch, tmp_path, "bom", str(folder), "--source", "model")
    assert code == 3 and err["code"] == "FEN-3004" and err["where"] == ".fenolite"
    assert str(tmp_path) not in err["message"]


def test_template_errors(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    code, env, err, _ = run(
        monkeypatch, tmp_path, "bom", str(FIXTURE), "--source", "model", "--template", INVALID
    )
    assert code == 3 and err["code"] == "FEN-3004"
    assert [i["where"] for i in env["issues"]] == ["bom.columns[1].field", "bom.colour", "placement.units"]


def test_usage_and_input_errors(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    code, _, err, _ = run(monkeypatch, tmp_path, "bom", str(tmp_path / "none.kicad_pcb"), "--source", "model")
    assert code == 3 and err["code"] == "FEN-3001"
    code, _, err, _ = run(monkeypatch, tmp_path, "bom", str(FIXTURE), "--source", "sheet")
    assert code == 2 and err["code"] == "FEN-2001"
    code, _, err, _ = run(
        monkeypatch, tmp_path, "bom", str(FIXTURE), "--source", "model", "--against", str(tmp_path / "x")
    )
    assert code == 3 and err["code"] == "FEN-3001"


def test_two_runs_are_identical(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    outputs = [run(monkeypatch, tmp_path, "bom", str(FIXTURE), "--source", "model")[3] for _ in range(2)]
    assert without_elapsed(outputs[0]) == without_elapsed(outputs[1])
    assert str(tmp_path) not in outputs[0] and str(FIXTURE.parent) not in outputs[0]


def test_command_declaration() -> None:
    assert COMMAND.mutates and COMMAND.example_tools == ()
    assert COMMAND.example_args[1:] == ("--source", "model")
    assert COMMAND.mutation_example_args is not None
    assert COMMAND.mutation_example_args[1:] == ("--source", "model", "--out", "bom.csv")


def _listed(folder: Path) -> dict[str, dict[str, object]]:
    manifest = json.loads((folder / "fenolite-artifacts.json").read_text(encoding="utf-8"))
    assert _schema.validate(manifest, _schema.load("fenolite.artifacts.v0.json")) == []
    assert manifest["tool"]["name"] == "fenolite" and manifest["check"] is None
    return {e["path"]: e for e in manifest["artifacts"]}


def test_manifest_lists_the_bill(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Capability cli-contract, "Manifest option of producing commands" (change c0065)."""
    args = ("bom", str(FIXTURE), "--source", "model", "--out", "tables/bom.csv", "--manifest")
    code, env, _, _ = run(
        monkeypatch, tmp_path, *args, "--timestamp", "2026-01-02T03:04:05+00:00", "--confirm"
    )
    assert code == 0, env
    listed = _listed(tmp_path / "tables")
    assert list(listed) == ["bom.csv"]
    bill = listed["bom.csv"]
    assert bill["kind"] == "bom" and bill["from"] == {
        "board": hashlib.sha256(FIXTURE.read_bytes()).hexdigest()
    }
    assert bill["evidence"] == env["evidence"]["level"] == "INFERRED"
    first = (tmp_path / "tables" / "fenolite-artifacts.json").read_bytes()
    code, _, _, _ = run(
        monkeypatch, tmp_path, *args, "--timestamp", "2026-01-02T03:04:05+00:00", "--confirm", "--no-backup"
    )
    assert code == 0 and (tmp_path / "tables" / "fenolite-artifacts.json").read_bytes() == first
