# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""``fenolite inspect`` (capability cli-contract, "Inspect command"; change c0013), and its summary of
Altium files (capability altium-verification, "Altium file summary"; change c0044). Hermetic."""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest
from _altium_pcb_read import read_pcbdoc
from _cfb_build import build
from _checkcli import run

from fenolite.backends.altium.backend import AltiumBackend
from fenolite.backends.kicad.pcb import opaque_count, read_board

DATA = Path(__file__).resolve().parents[2] / "data"
TWO_LAYER = DATA / "kicad" / "board" / "two_layer.kicad_pcb"
FOOTPRINT = DATA / "libs" / "Mini.pretty" / "Mini_R_0603.kicad_mod"
SYMBOLS = DATA / "libs" / "Mini.kicad_sym"
SHEET = DATA / "kicad" / "sheets" / "all_items.kicad_wks"
ALTIUM = DATA / "altium"
BLINK = ALTIUM / "blink"
KEYS = {
    "kind",
    "format_version",
    "major",
    "status",
    "generator",
    "generator_version",
    "counts",
    "opaque_count",
    "model_findings",
    "streams",
}


def test_authored_board_summary(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    code, env, _, _ = run(monkeypatch, tmp_path, "inspect", str(TWO_LAYER))
    result = env["result"]
    assert code == 0
    assert (result["kind"], result["format_version"], result["major"]) == ("kicad_pcb", 20241229, 9)
    assert result["counts"] == {
        "footprints": 2,
        "pads": 4,
        "nets": 3,
        "tracks": 3,
        "arcs": 1,
        "vias": 1,
        "zones": 1,
        "fills": 2,
        "keepouts": 1,
        "graphics": 6,
        "texts": 1,
    }
    assert result["opaque_count"] == opaque_count(read_board(TWO_LAYER))
    assert env["input"]["path"] == "two_layer.kicad_pcb"
    assert env["evidence"]["hypotheses"] == ["H-K-PCB-READ"]
    assert set(result) == {
        "kind",
        "format_version",
        "major",
        "status",
        "generator",
        "generator_version",
        "counts",
        "opaque_count",
        "model_findings",
    }


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


# --- Altium files (capability altium-verification, "Altium file summary"; change c0044) -------------------


@pytest.fixture
def no_subprocess(monkeypatch: pytest.MonkeyPatch) -> None:
    def refuse(*_args: object, **_kwargs: object) -> None:
        raise AssertionError("inspect ran a subprocess")

    monkeypatch.setattr(subprocess, "run", refuse)
    monkeypatch.setattr(subprocess, "Popen", refuse)


def test_altium_pcb_document(monkeypatch: pytest.MonkeyPatch, tmp_path: Path, no_subprocess: None) -> None:
    path = BLINK / "blink.PcbDoc"
    code, env, _, raw = run(monkeypatch, tmp_path, "inspect", str(path))
    result = env["result"]
    assert code == 0 and set(result) == KEYS
    assert (result["kind"], result["format_version"], result["status"]) == (
        "altium_pcbdoc",
        "6.0",
        "supported",
    )
    assert (result["major"], result["generator"], result["generator_version"]) == (None, None, None)
    counts = result["counts"]
    assert counts["footprints"] == 3 and counts["pads"] == len(read_pcbdoc(path.read_bytes()).pads) == 36
    assert set(counts) == {
        "footprints",
        "pads",
        "nets",
        "tracks",
        "arcs",
        "vias",
        "zones",
        "fills",
        "keepouts",
        "graphics",
        "texts",
        "components",
        "rules",
    }
    assert counts["components"] == 3 and counts["nets"] == 4
    assert result["streams"]["typed"] >= 1 and result["streams"]["opaque"] >= 1
    verdict = AltiumBackend().container_roundtrip(path, "RT-A1")
    assert result["opaque_count"] == verdict.opaque_count and result["streams"]["typed"] == verdict.streams
    assert env["input"] == {
        "path": "blink.PcbDoc",
        "sha256": env["input"]["sha256"],
        "kind": "altium_pcbdoc",
        "format_version": "6.0",
    }
    read = AltiumBackend().read(path)
    assert env["evidence"]["level"] == read.evidence.level.value
    assert env["evidence"]["hypotheses"] == list(read.evidence.hypotheses)
    assert all(not issue["code"].startswith("model.") for issue in env["issues"])
    assert result["model_findings"] == {"warning": 1} and str(DATA) not in raw


def test_altium_schematic_in_both_forms(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, no_subprocess: None
) -> None:
    sample = ALTIUM / "sample"
    found = [
        run(monkeypatch, tmp_path, "inspect", str(path))[1]["result"]
        for path in (sample / "altium_sample.SchDoc", sample / "binary" / "altium_sample.SchDoc")
    ]
    assert [r["kind"] for r in found] == ["altium_schdoc_ascii", "altium_schdoc_binary"]
    assert [r["format_version"] for r in found] == ["5.0", "5.0"]
    assert found[0]["counts"] == found[1]["counts"]
    assert set(found[0]["counts"]) == {
        "components",
        "pins",
        "nets",
        "wires",
        "labels",
        "power_ports",
        "ports",
        "sheet_symbols",
        "no_connects",
    }
    assert found[0]["counts"]["components"] == 8 and found[0]["counts"]["wires"] > 0
    assert found[0]["streams"] == {"typed": 1, "opaque": 0} and found[1]["streams"]["typed"] == 2
    code, env, _, _ = run(
        monkeypatch, tmp_path, "inspect", str(ALTIUM / "no_connect" / "altium_no_connect.SchDoc")
    )
    assert code == 0 and env["result"]["counts"]["no_connects"] > 0


def test_altium_libraries(monkeypatch: pytest.MonkeyPatch, tmp_path: Path, no_subprocess: None) -> None:
    code, env, _, _ = run(monkeypatch, tmp_path, "inspect", str(BLINK / "blink.PcbLib"))
    assert code == 0 and env["result"]["kind"] == "altium_pcblib" and env["result"]["format_version"] == "6.0"
    assert env["result"]["counts"] == {"footprints": 3, "pads": 36, "graphics": 27}
    code, env, _, _ = run(monkeypatch, tmp_path, "inspect", str(BLINK / "blink.SchLib"), "--summary")
    assert code == 0 and env["result"]["kind"] == "altium_schlib" and env["result"]["format_version"] == "5.0"
    assert env["result"]["counts"] == {"symbols": 3, "units": 3, "pins": 36}
    assert env["result"]["model_findings"] == {} and env["result"]["opaque_count"] == 0


def test_altium_project_file(monkeypatch: pytest.MonkeyPatch, tmp_path: Path, no_subprocess: None) -> None:
    code, env, _, _ = run(monkeypatch, tmp_path, "inspect", str(BLINK / "blink.PrjPcb"))
    result = env["result"]
    assert code == 0 and set(result) == KEYS | {"documents"}
    assert (result["kind"], result["format_version"]) == ("altium_prjpcb", None)
    assert result["counts"] == {
        "documents": 4,
        "missing": 0,
        "footprint-library": 1,
        "pcb": 1,
        "schematic": 1,
        "symbol-library": 1,
    }
    assert [d["name"] for d in result["documents"]] == [
        "blink.PcbDoc",
        "blink.PcbLib",
        "blink.SchDoc",
        "blink.SchLib",
    ]
    assert all(d["exists"] is True for d in result["documents"])
    assert result["documents"][0] == {
        "name": "blink.PcbDoc",
        "kind": "altium_pcbdoc",
        "role": "pcb",
        "exists": True,
    }
    assert result["streams"] == {"typed": 1, "opaque": 0} and env["input"]["format_version"] is None
    root = Path(shutil.copytree(BLINK, tmp_path / "blink"))
    (root / "blink.PcbLib").unlink()
    code, env, _, _ = run(monkeypatch, tmp_path, "inspect", str(root / "blink.PrjPcb"))
    assert code == 0 and env["result"]["counts"]["missing"] == 1 and env["result"]["counts"]["documents"] == 4
    assert {"name": "blink.PcbLib", "kind": None, "role": None, "exists": False} in env["result"]["documents"]


def test_altium_truncated_and_missing_files(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    cut = tmp_path / "blink.PcbLib"
    cut.write_bytes((BLINK / "blink.PcbLib").read_bytes()[:100])
    code, _, error, _ = run(monkeypatch, tmp_path, "inspect", str(cut))
    assert code == 3 and error["code"] == "FEN-3004"
    code, _, error, _ = run(monkeypatch, tmp_path, "inspect", str(tmp_path / "gone.PcbDoc"))
    assert code == 3 and error["code"] == "FEN-3001"


def test_unknown_compound_file(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Scenario "Compound file that no backend reads": the hint names ``--streams``."""
    unknown = tmp_path / "x.bin"
    unknown.write_bytes(bytes(build([{"path": "Data", "data": b"x"}]).data))
    code, _, error, _ = run(monkeypatch, tmp_path, "inspect", str(unknown))
    assert code == 2 and error["code"] == "FEN-2001" and "--streams" in error["hint"]
    code, env, _, _ = run(monkeypatch, tmp_path, "inspect", str(unknown), "--streams")
    assert code == 0 and env["result"]["kind"] == "compound_file"


def test_altium_two_views(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    board = str(BLINK / "blink.PcbDoc")
    code, _, error, _ = run(monkeypatch, tmp_path, "inspect", board, "--summary", "--streams")
    assert code == 2 and error["code"] == "FEN-2001"
    code, env, _, _ = run(monkeypatch, tmp_path, "inspect", board, "--streams")
    assert code == 0 and env["result"]["kind"] == "compound_file"
    code, env, _, _ = run(monkeypatch, tmp_path, "inspect", board, "--summary")
    assert code == 0 and env["result"]["kind"] == "altium_pcbdoc"
