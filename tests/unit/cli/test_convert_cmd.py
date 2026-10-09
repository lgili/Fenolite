# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""``fenolite convert`` (capability design-conversion, "Convert command", "Convert output folder" and
"Convert result and exit codes"; change c0159). Hermetic: no tool runs."""

from __future__ import annotations

import dataclasses
import shutil
from pathlib import Path

import _schema
import pytest
from _checkcli import run
from _convert import BLINK_T10, TWO_LAYER, read_as, two_layer, with_pads

import fenolite.convert as convert_package
from fenolite.convert import to_altium
from fenolite.convert.direction import Options, Written
from fenolite.convert.sources import SourceProject
from fenolite.core.coords import Point

KEYS = ["source", "target", "files", "report", "equivalence", "experimental", "plan", "plan_id"]


def test_plan_of_a_conversion(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Scenario "Plan of a conversion"."""
    code, envelope, error, _ = run(
        monkeypatch, tmp_path, "convert", str(TWO_LAYER), "--to", "altium", "--out", "out", "--dry-run"
    )
    assert code == 0, error
    result = envelope["result"]
    assert list(result) == KEYS
    planned = [row["path"] for row in result["plan"]]
    assert {"out/two_layer.PcbDoc", "out/two_layer.PrjPcb"} <= set(planned)
    assert result["experimental"] is True and result["equivalence"]["equivalent"] is True
    assert result["source"] == {
        "path": "two_layer.kicad_pcb", "backend": "kicad", "kind": "kicad_pcb", "format_version": 20241229,
    }  # fmt: skip
    assert result["target"] == {"backend": "altium", "major": None}
    assert envelope["input"]["path"] == "two_layer.kicad_pcb" and envelope["evidence"]["level"] == "INFERRED"
    assert _schema.validate(result, _schema.load("fenolite.convert.v0.json")) == []
    assert not (tmp_path / "out").exists()


def test_output_over_the_source_refused(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Scenario "Output over the source refused": the source's folder, and a folder that holds it."""
    project = tmp_path / "project"
    shutil.copytree(BLINK_T10, project)
    for out in (str(project), str(tmp_path)):
        code, envelope, error, _ = run(
            monkeypatch, tmp_path, "convert", str(project), "--to", "altium", "--out", out, "--dry-run"
        )
        assert code == 2 and error["code"] == "FEN-2001" and error["where"] == "--out"
        assert "plan" not in envelope.get("result", {})


def test_existing_output_folder(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Scenario "Existing output folder": an earlier file is kept as ``.bak``."""
    out = tmp_path / "out"
    out.mkdir()
    (out / "two_layer.PcbDoc").write_bytes(b"earlier")
    code, envelope, error, _ = run(
        monkeypatch, tmp_path, "convert", str(TWO_LAYER), "--to", "altium", "--out", "out", "--confirm"
    )
    assert code == 0, error
    assert (out / "two_layer.PcbDoc.bak").read_bytes() == b"earlier"
    assert (out / "two_layer.PcbDoc").read_bytes()[:8] != b"earlier"
    written = {Path(row["path"]).name for row in envelope["receipt"]["written"]}
    assert {"two_layer.PcbDoc", "two_layer.PrjPcb", "two_layer.SchDoc", "two_layer.SchLib"} <= written


def test_exit_7_without_consent(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Scenario "Exit 7 without consent", hermetic: a lost pad and a lost fitted flag."""
    design, _, _ = with_pads(two_layer(), {"shape": "custom"})
    first = dataclasses.replace(design.circuit.components[0], dnp=True)
    circuit = dataclasses.replace(design.circuit, components=(first, *design.circuit.components[1:]))
    read_as(monkeypatch, dataclasses.replace(design, circuit=circuit))
    argv = ["convert", str(TWO_LAYER), "--to", "altium", "--out", "out", "--dry-run"]
    code, envelope, error, _ = run(monkeypatch, tmp_path, *argv)
    assert code == 7 and error["code"] == "FEN-7001"
    assert {i["where"] for i in envelope["issues"]} == {"pad", "dnp"}
    code, envelope, error, _ = run(monkeypatch, tmp_path, "--allow-lossy", *argv)
    assert code == 0, error
    assert envelope["result"]["plan"]
    assert sorted(i["where"] for i in envelope["issues"] if i["code"] == "convert.lossy") == ["dnp", "pad"]


def test_downgrade_plan(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Change c0162 (it replaces c0159's "Older target refused"): a KiCad 10 project converted for KiCad 9
    needs --allow-lossy for its design rows, and is then planned with one report row per resolver id."""
    argv = ["--kicad-version", "9", "convert", str(BLINK_T10), "--to", "kicad", "--out", "out", "--dry-run"]
    code, _, error, _ = run(monkeypatch, tmp_path, *argv)
    assert code == 7 and error["code"] == "FEN-7001"
    code, envelope, error, _ = run(monkeypatch, tmp_path, "--allow-lossy", *argv)
    assert code == 0, error
    result = envelope["result"]
    assert result["target"] == {"backend": "kicad", "major": 9}
    kinds = {row["kind"]: row for row in result["report"]["rows"]}
    assert kinds["downgrade:project:/tuning_profiles"]["group"] == "downgrade"
    assert kinds["downgrade:project:/tuning_profiles"]["loss"] == "refuse"
    assert result["equivalence"]["equivalent"] is True
    assert _schema.validate(result, _schema.load("fenolite.convert.v0.json")) == []


def test_kicad_retarget_plan(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    argv = ["convert", str(BLINK_T10), "--to", "kicad", "--out", "out", "--dry-run", "--name", "board"]
    code, envelope, error, _ = run(monkeypatch, tmp_path, *argv)
    assert code == 0, error
    result = envelope["result"]
    assert [row["path"] for row in result["plan"]] == [
        "out/board.kicad_dru", "out/board.kicad_pcb", "out/board.kicad_pro",
    ]  # fmt: skip
    assert result["target"] == {"backend": "kicad", "major": 10} and result["experimental"] is False


def _moving(source: SourceProject, options: Options) -> Written:
    board = source.design.board
    assert board is not None
    first = board.footprints[0]
    moved = dataclasses.replace(first, position=Point(first.position.x + 1_000_000, first.position.y))
    edited = dataclasses.replace(
        source.design, board=dataclasses.replace(board, footprints=(moved, *board.footprints[1:]))
    )
    return dataclasses.replace(
        to_altium.write(dataclasses.replace(source, design=edited), options), design=source.design
    )


def test_unexplained_exits_5_and_plans_nothing(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    direction = dataclasses.replace(to_altium.DIRECTION, write=_moving)
    monkeypatch.setitem(convert_package.DIRECTIONS, ("kicad", "altium"), direction)
    argv = ["convert", str(TWO_LAYER), "--to", "altium", "--out", "out", "--dry-run"]
    code, envelope, error, _ = run(monkeypatch, tmp_path, *argv)
    assert code == 5 and error["code"] == "FEN-5001"
    assert [i["code"] for i in envelope["issues"] if i["severity"] == "error"] == ["convert.unexplained"]
    assert "plan" not in envelope["result"] and envelope["result"]["equivalence"]["unexplained"] == 1


def test_no_verify_and_report_ids(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    argv = ["convert", str(TWO_LAYER), "--to", "altium", "--out", "out", "--dry-run", "--no-verify"]
    code, envelope, error, _ = run(monkeypatch, tmp_path, *argv, "--report-ids")
    assert code == 0, error
    result = envelope["result"]
    assert result["equivalence"] is None and envelope["evidence"]["level"] == "UNVERIFIED"
    assert [i["code"] for i in envelope["issues"] if i["severity"] == "warning"] == ["convert.no-verify"]
    fill = next(row for row in result["report"]["rows"] if row["kind"] == "zone-fill")
    assert fill["reasons"][0]["ids"]
    assert _schema.validate(result, _schema.load("fenolite.convert.v0.json")) == []


def test_bad_name_and_missing_source(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    argv = ["convert", str(TWO_LAYER), "--to", "altium", "--out", "out", "--dry-run", "--name", "a/b"]
    code, _, error, _ = run(monkeypatch, tmp_path, *argv)
    assert code == 2 and error["where"] == "--name"
    code, _, error, _ = run(
        monkeypatch, tmp_path, "convert", "nope.kicad_pcb", "--to", "altium", "--out", "o"
    )
    assert code == 3 and error["code"] == "FEN-3001"
