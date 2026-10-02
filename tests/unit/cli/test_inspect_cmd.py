# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""``fenolite inspect`` (capability cli-contract, "Inspect command"; change c0013). Hermetic."""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest
from _checkcli import run

from fenolite.backends.kicad.pcb import opaque_count, read_board

DATA = Path(__file__).resolve().parents[2] / "data"
TWO_LAYER = DATA / "kicad" / "board" / "two_layer.kicad_pcb"
FOOTPRINT = DATA / "libs" / "Mini.pretty" / "Mini_R_0603.kicad_mod"
SYMBOLS = DATA / "libs" / "Mini.kicad_sym"
SHEET = DATA / "kicad" / "sheets" / "all_items.kicad_wks"


def test_authored_board_summary(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    code, env, _, _ = run(monkeypatch, tmp_path, "inspect", str(TWO_LAYER))
    result = env["result"]
    assert code == 0
    assert (result["kind"], result["format_version"], result["major"]) == ("kicad_pcb", 20241229, 9)
    assert result["counts"] == {"footprints": 2, "pads": 4, "nets": 3, "tracks": 3, "arcs": 1, "vias": 1,
                                "zones": 1, "fills": 2, "keepouts": 1, "graphics": 6, "texts": 1}  # fmt: skip
    assert result["opaque_count"] == opaque_count(read_board(TWO_LAYER))
    assert env["input"]["path"] == "two_layer.kicad_pcb"
    assert env["evidence"]["hypotheses"] == ["H-K-PCB-READ"]
    assert set(result) == {"kind", "format_version", "major", "status", "generator", "generator_version",
                           "counts", "opaque_count", "model_findings"}  # fmt: skip


def test_model_findings_are_counted(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    board = tmp_path / "dup.kicad_pcb"
    board.write_text(TWO_LAYER.read_text(encoding="utf-8").replace('"Reference" "D1"', '"Reference" "R1"'))
    code, env, _, _ = run(monkeypatch, tmp_path, "inspect", str(board), "--summary")
    assert code == 0
    assert env["result"]["model_findings"].get("error", 0) >= 1
    assert not any(i["code"].startswith("model.") for i in env["issues"])


def test_unreadable_and_deferred_files(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    unbalanced = DATA / "kicad" / "sexpr" / "mirror" / "unbalanced.kicad_pcb"
    code, _, err, _ = run(monkeypatch, tmp_path, "inspect", str(unbalanced))
    assert code == 3 and err["code"] == "FEN-3004"
    project = tmp_path / "p.kicad_pro"
    project.write_text("{}\n", encoding="utf-8")
    code, _, err, _ = run(monkeypatch, tmp_path, "inspect", str(project))
    assert code == 2 and err["code"] == "FEN-2001"
    notes = tmp_path / "notes.txt"
    notes.write_text("x\n", encoding="utf-8")
    assert run(monkeypatch, tmp_path, "inspect", str(notes))[0] == 2
    code, _, err, _ = run(monkeypatch, tmp_path, "inspect", str(tmp_path / "missing.kicad_pcb"))
    assert code == 3 and err["code"] == "FEN-3001"


def test_footprint_file(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    code, env, _, _ = run(monkeypatch, tmp_path, "inspect", str(FOOTPRINT))
    assert code == 0 and env["result"]["kind"] == "kicad_mod"
    assert set(env["result"]["counts"]) == {"pads", "graphics", "models"}
    assert env["result"]["counts"]["pads"] == 2 and env["result"]["opaque_count"] is None


def test_symbol_library_file_and_folder(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    code, env, _, _ = run(monkeypatch, tmp_path, "inspect", str(SYMBOLS))
    counts = env["result"]["counts"]
    assert code == 0 and env["result"]["kind"] == "kicad_sym" and counts["symbols"] >= 1
    folder = tmp_path / "Mini.kicad_symdir"
    folder.mkdir()
    shutil.copyfile(SYMBOLS, folder / "Mini.kicad_sym")
    code, env, err, _ = run(monkeypatch, tmp_path, "inspect", str(folder))
    assert code == 0, err
    assert env["result"]["kind"] == "kicad_sym" and env["input"]["path"] == "Mini.kicad_symdir"


def test_drawing_sheet_header_only(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    code, env, _, _ = run(monkeypatch, tmp_path, "inspect", str(SHEET))
    result = env["result"]
    assert code == 0 and result["kind"] == "kicad_wks" and result["format_version"] == 20231118
    assert result["counts"]["setup"] == 1 and result["opaque_count"] is None
    assert env["evidence"]["level"] == "INFERRED" and env["evidence"]["hypotheses"] == ["H-K-TOK-CONSTANTS"]
