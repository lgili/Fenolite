# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""``fenolite bom`` (capability cli-contract, "Bom command"; change c0064). Hermetic: the ``model`` source
runs no tool, and the tests of the ``kicad`` source (their names hold ``kicad``) run a fake ``kicad-cli``
that writes an authored bill."""

from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
from pathlib import Path

import _asmcli
import _schema
import pytest
from _asmcli import COLUMNS, FIXTURE, INVALID, R1, built, isolate
from _checkcli import hide_kicad, run, without_elapsed
from _fakecli import calls, fake_kicad_cli
from _projects import tree_snapshot

from fenolite.cli.cmd_bom import COMMAND

WITH_BIN = R1.replace(")", ', properties={"Bin": "A7"})')
"""The blink's resistor with a made-up user property."""


EXPORT = (
    (Path(_asmcli.__file__).resolve().parents[2] / "data" / "assembly" / "bom_export.csv")
    .read_bytes()
    .decode("utf-8")
)
"""The authored bill, with the fields the template ``columns.toml`` makes the command ask for."""


@pytest.fixture(autouse=True)
def isolated(request: pytest.FixtureRequest, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    isolate(monkeypatch, tmp_path)
    if "kicad" in request.node.name:  # these run the fake tool, and never the machine's own
        hide_kicad(monkeypatch, tmp_path)
        return

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
    # a project Fenolite built, with its schematic: the one case where the model was compared with KiCad
    assert env["evidence"] == {"level": "KICAD-VERIFIED", "oracle": None, "hypotheses": ["H-K-BOM-MODEL"]}
    code, _, _, _ = run(monkeypatch, second, *args)
    assert code == 0 and (second / "bom.csv").read_bytes() == data
    assert tree_snapshot(folder) == before


def test_a_built_project_without_its_schematic_is_inferred(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    folder = built(monkeypatch, tmp_path)
    (folder / "blink.kicad_sch").unlink()
    code, env, _, _ = run(monkeypatch, tmp_path, "bom", str(folder), "--source", "model")
    assert code == 0
    assert env["evidence"] == {"level": "INFERRED", "oracle": None, "hypotheses": ["H-K-BOM-MODEL"]}


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


def _with_schematic(tmp_path: Path) -> Path:
    """The authored board in a folder of its own, with a schematic file next to it (the fake reads none)."""
    folder = tmp_path / "project"
    (folder / "sub").mkdir(parents=True)
    board = folder / "two_layer.kicad_pcb"
    shutil.copyfile(FIXTURE, board)
    board.with_suffix(".kicad_sch").write_text("(kicad_sch)\n", encoding="utf-8", newline="\n")
    (folder / "sub" / "child.kicad_sch").write_text("(kicad_sch)\n", encoding="utf-8", newline="\n")
    return board


def test_from_kicad_cli(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    board = _with_schematic(tmp_path)
    fake = fake_kicad_cli(tmp_path / "bin", bom=EXPORT)
    before = tree_snapshot(board.parent)
    code, env, err, _ = run(
        monkeypatch, tmp_path, "bom", str(board), "--template", COLUMNS, "--kicad-cli", str(fake)
    )
    assert code == 0, err
    result = env["result"]
    assert (result["source"], result["columns"]) == ("kicad", ["Parts", "Count", "Marking", "Shape", "Bin"])
    assert result["lines"] == [
        {"Parts": "D1", "Count": "1", "Marking": "LED", "Shape": "Mini_LED_THT_3mm", "Bin": ""},
        {"Parts": "R1", "Count": "1", "Marking": "10k", "Shape": "Mini_R_0603", "Bin": "A"},
    ]  # R10 is DNP and the template leaves DNP parts out
    assert result["counts"] == {"parts": 2, "lines": 2, "dnp": 1, "left_out": None}
    assert env["evidence"]["oracle"] == "kicad-cli 10.0.6"
    assert env["evidence"]["hypotheses"] == ["H-K-BOM-CSV"]
    (call,) = [c["args"] for c in calls(fake) if c["args"][:3] == ["sch", "export", "bom"]]
    fields = call[call.index("--fields") + 1]
    assert fields == "Reference,Value,Footprint,Datasheet,Description,${DNP},Bin"
    assert call[call.index("--labels") + 1] == fields and call[-1] == "two_layer.kicad_sch"
    assert tree_snapshot(board.parent) == before  # the tool ran on a copy


MIXED_EXPORT = (
    '"Reference","Value","Footprint","Datasheet","Description","${DNP}"\n'
    '"R2","4,7 kΩ","Mini:Mini_R_0603","","","DNP"\n'
    '"R1","4,7 kΩ","Mini:Mini_R_0603","","",""\n'
    '"R3","4,7 kΩ","Mini:Mini_R_0603","","",""\n'
)
"""A made-up bill as ``kicad-cli`` writes it: three resistors of one value, ``R2`` marked DNP. The value
is not ASCII, so the fake tool's file must be UTF-8 bytes."""


def _mixed_template(tmp_path: Path, exclude_dnp: bool) -> str:
    """A template that groups by value and footprint, without ``dnp`` in ``group_by``."""
    path = tmp_path / f"mixed-{exclude_dnp}.toml"
    path.write_text(
        "[bom]\n"
        "columns = [\n"
        '  { name = "Parts", field = "refs" },\n'
        '  { name = "Count", field = "quantity" },\n'
        '  { name = "Marking", field = "value" },\n'
        '  { name = "Fit", field = "dnp" },\n'
        "]\n"
        'group_by = ["value", "footprint"]\n'
        f"exclude_dnp = {str(exclude_dnp).lower()}\n",
        encoding="utf-8",
        newline="\n",
    )
    return str(path)


def test_kicad_source_keeps_dnp_parts_on_their_own_line(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Capability assembly-outputs, "DNP parts never share a line with fitted parts" (change c0094)."""
    board = _with_schematic(tmp_path)
    fake = fake_kicad_cli(tmp_path / "bin", bom=MIXED_EXPORT)
    args = ("bom", str(board), "--kicad-cli", str(fake), "--template")
    code, env, err, _ = run(monkeypatch, tmp_path, *args, _mixed_template(tmp_path, False))
    assert code == 0, err
    assert env["result"]["lines"] == [
        {"Parts": "R1,R3", "Count": "2", "Marking": "4,7 kΩ", "Fit": ""},
        {"Parts": "R2", "Count": "1", "Marking": "4,7 kΩ", "Fit": "DNP"},
    ]
    assert env["result"]["counts"] == {"parts": 3, "lines": 2, "dnp": 1, "left_out": None}
    code, env, err, _ = run(monkeypatch, tmp_path, *args, _mixed_template(tmp_path, True))
    assert code == 0, err
    assert env["result"]["lines"] == [{"Parts": "R1,R3", "Count": "2", "Marking": "4,7 kΩ", "Fit": ""}]
    assert env["result"]["counts"] == {"parts": 2, "lines": 1, "dnp": 1, "left_out": None}


def test_model_source_keeps_dnp_parts_on_their_own_line(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """The authored board with both parts given one value and footprint name in the template's eyes
    (grouped by value alone) and ``R1`` marked DNP: two lines, and one when DNP parts are left out."""
    text = FIXTURE.read_bytes().decode("utf-8")
    edits = (('(property "Value" "LED"', '(property "Value" "330"'), ("(attr smd)", "(attr smd dnp)"))
    for old, new in edits:
        assert text.count(old) == 1, old
        text = text.replace(old, new)
    board = tmp_path / "mixed.kicad_pcb"
    board.write_text(text, encoding="utf-8", newline="\n")
    template = Path(_mixed_template(tmp_path, False))
    template.write_text(
        template.read_text(encoding="utf-8").replace('["value", "footprint"]', '["value"]'),
        encoding="utf-8",
        newline="\n",
    )
    args = ("bom", str(board), "--source", "model", "--template", str(template))
    code, env, err, _ = run(monkeypatch, tmp_path, *args)
    assert code == 0, err
    assert env["result"]["lines"] == [
        {"Parts": "D1", "Count": "1", "Marking": "330", "Fit": ""},
        {"Parts": "R1", "Count": "1", "Marking": "330", "Fit": "DNP"},
    ]
    assert env["result"]["counts"] == {"parts": 2, "lines": 2, "dnp": 1, "left_out": 0}
    template.write_text(
        template.read_text(encoding="utf-8").replace("exclude_dnp = false", "exclude_dnp = true"),
        encoding="utf-8",
        newline="\n",
    )
    code, env, err, _ = run(monkeypatch, tmp_path, *args)
    assert code == 0, err
    assert env["result"]["lines"] == [{"Parts": "D1", "Count": "1", "Marking": "330", "Fit": ""}]
    assert env["result"]["counts"] == {"parts": 1, "lines": 1, "dnp": 1, "left_out": 0}


def test_kicad_source_writes_the_same_file_twice(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    board = _with_schematic(tmp_path)
    fake = fake_kicad_cli(tmp_path / "bin", bom=EXPORT)
    args = ("bom", str(board), "--template", COLUMNS, "--kicad-cli", str(fake), "--out", "bom.csv")
    first, second = tmp_path / "a", tmp_path / "b"
    first.mkdir()
    second.mkdir()
    code, env, _, _ = run(monkeypatch, first, *args, "--confirm")
    assert code == 0 and env["receipt"]["written"][0]["path"] == "bom.csv"
    data = (first / "bom.csv").read_bytes()
    assert data.decode("utf-8").splitlines()[0] == "Parts,Count,Marking,Shape,Bin"
    code, _, _, _ = run(monkeypatch, second, *args, "--confirm")
    assert code == 0 and (second / "bom.csv").read_bytes() == data


def test_kicad_source_against_another_project(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    board = _with_schematic(tmp_path)
    fake = fake_kicad_cli(tmp_path / "bin", bom=EXPORT)
    code, env, _, _ = run(
        monkeypatch, tmp_path, "bom", str(board), "--template", COLUMNS, "--kicad-cli", str(fake),
        "--against", str(board),
    )  # fmt: skip
    assert code == 0 and env["result"]["changes"] == []
    assert len([c for c in calls(fake) if c["args"][:3] == ["sch", "export", "bom"]]) == 2


def test_kicad_source_without_a_tool(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    board = _with_schematic(tmp_path)
    code, env, err, _ = run(monkeypatch, tmp_path, "bom", str(board))
    assert code == 6 and err["code"] == "FEN-6001" and env["result"] == {}


def test_kicad_source_when_the_tool_writes_nothing(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    board = _with_schematic(tmp_path)
    fake = fake_kicad_cli(tmp_path / "bin")  # exits 3 and writes no bill
    code, _, err, _ = run(monkeypatch, tmp_path, "bom", str(board), "--kicad-cli", str(fake))
    assert code == 3 and err["code"] == "FEN-3004" and err["where"] == "two_layer.kicad_sch"
    assert "exited with 3" in err["message"] and "--source model" in err["hint"]
    assert str(tmp_path) not in err["message"]


def test_kicad_source_refuses_another_header(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """The default template asks for the six base fields; a bill with one more column is not read."""
    board = _with_schematic(tmp_path)
    fake = fake_kicad_cli(tmp_path / "bin", bom=EXPORT)
    code, _, err, _ = run(monkeypatch, tmp_path, "bom", str(board), "--kicad-cli", str(fake))
    assert code == 3 and err["code"] == "FEN-3004" and "'Bin'" in err["message"]


def test_kicad_source_refuses_a_property_with_a_comma(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    board = _with_schematic(tmp_path)
    fake = fake_kicad_cli(tmp_path / "bin", bom=EXPORT)
    template = tmp_path / "odd.toml"
    template.write_text(
        '[bom]\ncolumns = [{ name = "Parts", field = "refs" }, { name = "Odd", field = "property:a,b" }]\n',
        encoding="utf-8",
        newline="\n",
    )
    code, env, err, _ = run(
        monkeypatch, tmp_path, "bom", str(board), "--template", str(template), "--kicad-cli", str(fake)
    )
    assert code == 3 and err["code"] == "FEN-3004"
    assert [(i["code"], i["where"]) for i in env["issues"]] == [("bom.field-unsupported", "property:a,b")]
    assert calls(fake) == []
    code, env, _, _ = run(
        monkeypatch, tmp_path, "bom", str(board), "--template", str(template), "--source", "model"
    )
    assert code == 0 and env["result"]["columns"] == ["Parts", "Odd"]  # the model source reads it


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
