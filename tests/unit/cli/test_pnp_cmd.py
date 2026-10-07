# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""``fenolite pnp`` (capability cli-contract, "Pnp command"; change c0064; "Manifest option of producing
commands"; change c0065). Hermetic: no tool runs."""

from __future__ import annotations

import hashlib
import json
import subprocess
from pathlib import Path

import _schema
import pytest
from _asmcli import COLUMNS, FEATURES, FIXTURE, INVALID, LAST_LINE, ROTATED, built, isolate
from _boards import board, footprint
from _checkcli import run, without_elapsed
from _projects import tree_snapshot

from fenolite.backends.kicad.pcb import read_board
from fenolite.backends.kicad.replace import footprint_ref
from fenolite.cli.cmd_pnp import COMMAND
from fenolite.exports.assembly import format_length


@pytest.fixture(autouse=True)
def isolated(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    isolate(monkeypatch, tmp_path)

    def refuse(*args: object, **kwargs: object) -> None:
        raise AssertionError("a subprocess was started")

    monkeypatch.setattr(subprocess, "run", refuse)
    monkeypatch.setattr(subprocess, "Popen", refuse)


def test_rows_of_the_authored_board(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    code, env, _, _ = run(monkeypatch, tmp_path, "pnp", str(FIXTURE))
    assert code == 0 and list(tmp_path.iterdir()) == []
    result = env["result"]
    assert result["columns"] == ["ref", "value", "footprint_name", "x", "y", "rotation", "side"]
    assert (result["template"], result["units"], result["origin"], result["y_axis"]) == (
        "default", "mm", "page", "up",
    )  # fmt: skip
    assert result["rows"] == [
        {"ref": "D1", "value": "LED", "footprint_name": "LED_THT_3mm", "x": "35.0000", "y": "-15.0000",
         "rotation": "30.00", "side": "bottom"},
        {"ref": "R1", "value": "330", "footprint_name": "R_0603", "x": "20.0000", "y": "-15.0000",
         "rotation": "90.00", "side": "top"},
    ]  # fmt: skip
    assert result["counts"] == {"rows": 2, "top": 1, "bottom": 1, "dnp": 0, "left_out": 0}
    assert "plan" not in result and env["receipt"] is None
    assert env["evidence"] == {
        "level": "INFERRED",
        "oracle": None,
        "hypotheses": ["H-K-PCB-POS", "H-K-PCB-READ", "H-K-POS-ROWS"],
    }
    assert env["input"]["path"] == "two_layer.kicad_pcb"


def test_one_side(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    folder = built(monkeypatch, tmp_path)
    code, env, _, _ = run(monkeypatch, tmp_path, "pnp", str(folder), "--side", "bottom")
    assert code == 0
    assert [row["ref"] for row in env["result"]["rows"]] == ["D1"]
    assert env["result"]["counts"] == {"rows": 1, "top": 0, "bottom": 1, "dnp": 0, "left_out": 2}
    code, env, _, _ = run(monkeypatch, tmp_path, "pnp", str(folder / "blink.kicad_pro"), "--side", "top")
    assert code == 0 and [row["ref"] for row in env["result"]["rows"]] == ["R1", "U1"]


def test_file_with_rotation_rules(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    folder = built(monkeypatch, tmp_path)
    before = tree_snapshot(folder)
    args = ("pnp", str(folder), "--template", ROTATED, "--out", "pnp.csv", "--confirm")
    first, second = tmp_path / "a", tmp_path / "b"
    first.mkdir()
    second.mkdir()
    code, env, _, _ = run(monkeypatch, first, *args)
    assert code == 0, env["issues"]
    data = (first / "pnp.csv").read_bytes()
    assert env["receipt"]["written"] == [{"path": "pnp.csv", "sha256": hashlib.sha256(data).hexdigest()}]
    lines = data.decode("utf-8").split("\r\n")
    assert lines[0] == '"Part";"Shape";"Across";"Up";"Turn";"Face"' and lines[-1] == ""
    # The build puts the outline's corner at (100 mm, 100 mm): U1 lies 14 mm across and 15 mm up from the
    # lower-left corner, and its stored rotation 0 becomes 0 + 90 by the made-up footprint offset.
    assert lines[1:4] == [
        '"D1";"Mini_LED_THT_3mm";"1496.1";"393.7";"180.0";"lower"',
        '"R1";"Mini_R_0603";"1259.8";"826.8";"337.5";"upper"',
        '"U1";"Mini_QFP-32_7x7mm_P0.8mm";"551.2";"590.6";"90.0";"upper"',
    ]
    assert env["result"]["template"] == "rotated.toml" and env["result"]["units"] == "mil"
    code, _, _, _ = run(monkeypatch, second, *args)
    assert code == 0 and (second / "pnp.csv").read_bytes() == data
    assert tree_snapshot(folder) == before


def test_confirmation_required(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    work = tmp_path / "work"
    work.mkdir()
    code, env, err, _ = run(monkeypatch, work, "pnp", str(FIXTURE), "--template", COLUMNS, "-o", "pnp.csv")
    assert code == 4 and err["code"] == "FEN-4001"
    assert [(p["path"], p["kind"]) for p in env["result"]["plan"]] == [("pnp.csv", "pnp")]
    assert env["result"]["columns"] == ["Part", "Across", "Up", "Face", "Turn"]
    assert list(work.iterdir()) == []


def test_no_outline(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    bare = tmp_path / "bare.kicad_pcb"
    bare.write_text(board(footprint(1, ref="R1")), encoding="utf-8", newline="\n")
    code, env, err, _ = run(
        monkeypatch, tmp_path, "pnp", str(bare), "--template", ROTATED, "--out", "pnp.csv", "--confirm"
    )
    assert code == 5 and err["code"] == "FEN-5001"
    assert [(i["code"], i["severity"]) for i in env["issues"]] == [("pnp.no-outline", "error")]
    assert env["result"]["rows"] == [] and "plan" not in env["result"]
    assert env["receipt"] is None and not (tmp_path / "pnp.csv").exists()
    code, env, _, _ = run(monkeypatch, tmp_path, "pnp", str(bare))  # the page origin needs no outline
    assert code == 0 and [row["ref"] for row in env["result"]["rows"]] == ["R1"]


def test_template_errors(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    code, env, err, _ = run(monkeypatch, tmp_path, "pnp", str(FIXTURE), "--template", INVALID)
    assert code == 3 and err["code"] == "FEN-3004"
    assert err["where"] == "invalid.toml:bom.columns[1].field"
    assert [i["code"] for i in env["issues"]] == ["assembly.template-invalid"] * 3
    code, _, err, _ = run(monkeypatch, tmp_path, "pnp", str(FIXTURE), "--template", "missing.toml")
    assert code == 3 and err["code"] == "FEN-3001" and err["where"] == "missing.toml"


def test_usage_and_input_errors(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    code, _, err, _ = run(monkeypatch, tmp_path, "pnp", str(tmp_path / "none.kicad_pcb"))
    assert code == 3 and err["code"] == "FEN-3001"
    code, _, err, _ = run(monkeypatch, tmp_path, "pnp", str(FIXTURE), "--side", "left")
    assert code == 2 and err["code"] == "FEN-2001"


def test_the_board_is_read_not_the_model(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """``place`` writes the board and leaves ``.fenolite/`` as it was, so the placement table must come
    from the board: after a move, the row of ``R1`` is where the board has it."""
    folder = built(monkeypatch, tmp_path)
    code, env, _, _ = run(monkeypatch, tmp_path, "pnp", str(folder))
    before = {row["ref"]: row for row in env["result"]["rows"]}
    code, env, err, _ = run(monkeypatch, tmp_path, "place", str(folder), "--move", "R1=12mm,8mm", "--confirm")
    assert code == 0, (env.get("issues"), err)
    code, env, _, _ = run(monkeypatch, tmp_path, "pnp", str(folder))
    after = {row["ref"]: row for row in env["result"]["rows"]}
    design = read_board(folder / "blink.kicad_pcb")
    assert design.board is not None
    r1 = next(fp for fp in design.board.footprints if footprint_ref(design, fp) == "R1")
    assert after["R1"]["x"] == format_length(r1.position.x, "mm", 4)
    assert after["R1"]["y"] == format_length(-r1.position.y, "mm", 4)
    assert after["R1"] != before["R1"] and after["U1"] == before["U1"]


def test_two_runs_are_identical(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    outputs = [run(monkeypatch, tmp_path, "pnp", str(FIXTURE), "--template", COLUMNS)[3] for _ in range(2)]
    assert without_elapsed(outputs[0]) == without_elapsed(outputs[1])
    assert str(tmp_path) not in outputs[0] and str(FIXTURE.parent) not in outputs[0]


def test_command_declaration() -> None:
    assert COMMAND.mutates and COMMAND.example_tools == ()
    assert COMMAND.example_args[1:] == () and COMMAND.mutation_example_args is not None
    assert COMMAND.mutation_example_args[1:] == ("--out", "pnp.csv")


def _listed(folder: Path) -> dict[str, dict[str, object]]:
    manifest = json.loads((folder / "fenolite-artifacts.json").read_text(encoding="utf-8"))
    assert _schema.validate(manifest, _schema.load("fenolite.artifacts.v0.json")) == []
    assert manifest["tool"]["name"] == "fenolite" and manifest["check"] is None
    return {e["path"]: e for e in manifest["artifacts"]}


def test_manifest_tables_join_the_manifest(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    folder = built(monkeypatch, tmp_path)
    board = hashlib.sha256(next(folder.glob("*.kicad_pcb")).read_bytes()).hexdigest()
    code, env, _, _ = run(
        monkeypatch, tmp_path, "bom", str(folder), "--source", "model", "--out", "out/bom.csv", "--manifest",
        "--confirm",
    )  # fmt: skip
    assert code == 0, env
    assert [w["path"] for w in env["receipt"]["written"]] == ["out/bom.csv", "out/fenolite-artifacts.json"]
    code, env, _, _ = run(
        monkeypatch, tmp_path, "pnp", str(folder), "--out", "out/pnp.csv", "--manifest", "--confirm"
    )
    assert code == 0, env
    listed = _listed(tmp_path / "out")
    assert list(listed) == ["bom.csv", "pnp.csv"]
    for name, kind in (("bom.csv", "bom"), ("pnp.csv", "pnp")):
        item = listed[name]
        data = (tmp_path / "out" / name).read_bytes()
        assert (item["kind"], item["layer"], item["state"], item["stale"]) == (kind, None, "generated", False)
        assert item["sha256"] == hashlib.sha256(data).hexdigest() and item["bytes"] == len(data)
        assert item["from"] == {"board": board} and str(item["tool"]).startswith("fenolite ")
    assert listed["pnp.csv"]["evidence"] == env["evidence"]["level"]
    text = (tmp_path / "out" / "fenolite-artifacts.json").read_text(encoding="utf-8")
    assert str(tmp_path) not in text


def test_manifest_needs_a_folder(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    for command in (("pnp",), ("bom", "--source", "model")):
        code, _, err, _ = run(monkeypatch, tmp_path, *command, str(FIXTURE), "--manifest")
        assert code == 2 and err["code"] == "FEN-2001" and "--out" in err["hint"]
    assert list(tmp_path.iterdir()) == []


def test_manifest_in_the_working_folder_and_refusals(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    args = ("pnp", str(FIXTURE), "--out", "pnp.csv", "--manifest")
    code, env, _, _ = run(monkeypatch, tmp_path, *args, "--dry-run")
    assert code == 0 and [p["path"] for p in env["result"]["plan"]] == ["pnp.csv", "fenolite-artifacts.json"]
    assert list(tmp_path.iterdir()) == []
    (tmp_path / "fenolite-artifacts.json").write_text("[]", encoding="utf-8")
    code, env, _, _ = run(monkeypatch, tmp_path, *args, "--confirm")
    assert code == 5 and [i["code"] for i in env["issues"]] == ["manifest.unreadable"]
    assert sorted(p.name for p in tmp_path.iterdir()) == ["fenolite-artifacts.json"]
    code, env, _, _ = run(monkeypatch, tmp_path, *args[:-1], "--confirm")  # without --manifest: as before
    assert code == 0 and [w["path"] for w in env["receipt"]["written"]] == ["pnp.csv"]


def test_fiducial_rows_of_a_build(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Scenarios "Fiducials kept by default" and "A template drops them" (assembly-outputs, change c0118), on
    a build whose fiducials are authored parts with a marked pad."""
    folder = built(monkeypatch, tmp_path, (LAST_LINE, FEATURES))
    code, env, _, _ = run(monkeypatch, tmp_path, "pnp", str(folder))
    assert code == 0
    assert [row["ref"] for row in env["result"]["rows"]] == ["D1", "FID1", "FID2", "R1", "TP1", "U1"]
    marked = tmp_path / "marked.toml"
    marked.write_text(
        '[placement]\nfiducials = true\ncolumns = [{ name = "Ref", field = "ref" }, '
        '{ name = "Fid", field = "fiducial" }]\n',
        encoding="utf-8",
    )
    code, env, _, _ = run(monkeypatch, tmp_path, "pnp", str(folder), "--template", str(marked))
    assert code == 0
    assert {row["Ref"]: row["Fid"] for row in env["result"]["rows"]} == {
        "D1": "", "FID1": "yes", "FID2": "yes", "R1": "", "TP1": "", "U1": "",
    }  # fmt: skip
    dropped = tmp_path / "dropped.toml"
    dropped.write_text("[placement]\nfiducials = false\n", encoding="utf-8")
    code, env, _, _ = run(monkeypatch, tmp_path, "pnp", str(folder), "--template", str(dropped))
    assert code == 0
    assert [row["ref"] for row in env["result"]["rows"]] == ["D1", "R1", "TP1", "U1"]
