# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""``fenolite view`` (capability cli-contract, "View command")."""

from __future__ import annotations

import json
import shutil
import threading
from pathlib import Path

import pytest
from _checkcli import run

from fenolite.cli import cmd_view
from fenolite.view.export import embedded

ROOT = Path(__file__).resolve().parents[3]
BOARD = ROOT / "tests" / "data" / "kicad" / "board" / "two_layer.kicad_pcb"
ALTIUM = ROOT / "tests" / "data" / "altium" / "blink" / "blink.PrjPcb"
HIER = ROOT / "tests" / "data" / "altium" / "hier" / "altium_hier.PrjPcb"


def test_summary(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Scenario "Summary of a board"."""
    code, envelope, _, _ = run(monkeypatch, tmp_path, "view", str(BOARD))
    assert code == 0
    result = envelope["result"]
    docs = result["project"]["groups"][0]["documents"]
    assert docs[0]["viewable"] is True and result["document"] == "doc1"
    assert result["summary"]["counts"]["tracks"] == 3
    assert list(tmp_path.iterdir()) == []


def test_altium_project(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    code, envelope, _, _ = run(monkeypatch, tmp_path, "view", str(ALTIUM))
    assert code == 0 and envelope["result"]["summary"]["counts"]["pads"] > 0
    code, envelope, _, _ = run(monkeypatch, tmp_path, "view", str(HIER), "--doc", "altium_hier_flash.Harness")
    assert code == 0 and envelope["result"]["summary"] is None
    assert "no viewer" in envelope["result"]["notes"][0]


def test_schematic_summary(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Scenario "Summary of a sheet" (c0177)."""
    code, envelope, _, _ = run(monkeypatch, tmp_path, "view", str(HIER), "--doc", "altium_hier.SchDoc")
    assert code == 0
    summary = envelope["result"]["summary"]
    assert summary["kind"] == "schematic" and summary["counts"]["components"] == 1
    assert summary["counts"]["sheet_symbols"] == 2 and envelope["evidence"]["level"] == "INFERRED"
    assert list(tmp_path.iterdir()) == []
    code, envelope, _, _ = run(monkeypatch, tmp_path, "view", str(HIER), "--export", "view.html", "--confirm")
    assert code == 0
    data = embedded((tmp_path / "view.html").read_text(encoding="utf-8"))
    assert data is not None
    kinds = sorted(scene["kind"] for scene in data["scenes"].values())
    assert kinds == ["library", "schematic", "schematic", "schematic"]


def test_export_follows_the_protocol(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Scenario "Export follows the protocol"."""
    code, _, error, _ = run(monkeypatch, tmp_path, "view", str(BOARD), "--export", "view.html")
    assert code == 4 and error["code"] == "FEN-4001" and not (tmp_path / "view.html").exists()
    code, envelope, _, _ = run(
        monkeypatch, tmp_path, "view", str(BOARD), "--export", "view.html", "--confirm"
    )
    assert code == 0
    data = embedded((tmp_path / "view.html").read_text(encoding="utf-8"))
    assert data is not None and list(data["scenes"]) == ["doc1"]
    assert envelope["result"]["export"]["documents"] == ["doc1"]


def test_usage_errors(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    code, _, error, _ = run(monkeypatch, tmp_path, "view", str(BOARD), "--serve", "--export", "x.html")
    assert code == 2 and error["code"] == "FEN-2001"
    code, _, error, _ = run(monkeypatch, tmp_path, "view", str(tmp_path / "missing.kicad_pcb"))
    assert code == 3 and error["code"] == "FEN-3001"
    (tmp_path / "notes.txt").write_text("x", encoding="utf-8")
    code, _, error, _ = run(monkeypatch, tmp_path, "view", "notes.txt")
    assert code == 2 and error["code"] == "FEN-2001"
    code, _, error, _ = run(monkeypatch, tmp_path, "view", str(BOARD), "--port", "70000")
    assert code == 2


def test_overlay_of_an_analyze_reply(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    code, envelope, _, out = run(
        monkeypatch, tmp_path, "analyze", str(BOARD), "--kinds", "clearance", "--pair", "GND", "VCC"
    )
    assert code == 0
    (tmp_path / "a.json").write_text(out, encoding="utf-8")
    code, envelope, _, _ = run(
        monkeypatch, tmp_path, "view", str(BOARD), "--overlay", "a.json", "--export", "v.html", "--confirm"
    )
    assert code == 0
    data = embedded((tmp_path / "v.html").read_text(encoding="utf-8"))
    assert data is not None
    overlays = data["scenes"]["doc1"]["overlays"]
    assert overlays and overlays[0]["kind"] == "clearance" and "GND × VCC" in overlays[0]["label"]
    (tmp_path / "bad.json").write_text(json.dumps({"result": {}}), encoding="utf-8")
    code, _, error, _ = run(monkeypatch, tmp_path, "view", str(BOARD), "--overlay", "bad.json")
    assert code == 3 and error["code"] == "FEN-3004"


def test_serve_until_stopped(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    stop = threading.Event()
    stop.set()
    monkeypatch.setattr(cmd_view, "SERVE_STOP", stop)
    code, envelope, _, _ = run(
        monkeypatch, tmp_path, "view", str(BOARD), "--serve", "--no-browser", "--port", "0"
    )
    assert code == 0
    assert envelope["result"]["serve"]["url"].startswith("http://127.0.0.1:")


def test_theme(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Scenario "A theme file on a KiCad board" (c0178)."""
    theme = tmp_path / "mine.json"
    theme.write_text(json.dumps({"board": {"copper": {"f": "rgb(1, 2, 3)"}}}), encoding="utf-8")
    code, envelope, _, _ = run(monkeypatch, tmp_path, "view", str(BOARD), "--theme", "mine.json")
    assert code == 0 and envelope["result"]["theme"] == "kicad:mine.json"
    code, envelope, _, _ = run(monkeypatch, tmp_path, "view", str(BOARD))
    assert code == 0 and envelope["result"]["theme"] == "kicad"
    code, envelope, _, _ = run(monkeypatch, tmp_path, "view", str(ALTIUM))
    assert code == 0 and envelope["result"]["theme"] == "altium"
    code, _, error, _ = run(monkeypatch, tmp_path, "view", str(BOARD), "--theme", "no-such-theme-anywhere")
    assert code == 3 and error["code"] == "FEN-3001"
    (tmp_path / "bad.json").write_text("[1]", encoding="utf-8")
    code, _, error, _ = run(monkeypatch, tmp_path, "view", str(BOARD), "--theme", "bad.json")
    assert code == 3 and error["code"] == "FEN-3004"


def test_kicad_sheet_summary(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    sheet = ROOT / "tests" / "data" / "kicad" / "schematic" / "flat.kicad_sch"
    code, envelope, _, _ = run(monkeypatch, tmp_path, "view", str(sheet))
    assert code == 0
    summary = envelope["result"]["summary"]
    assert summary["kind"] == "schematic" and summary["counts"]["components"] == 5
    assert envelope["result"]["theme"] == "kicad"


def test_library_summary(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Scenario "Summary of a footprint library" (c0179)."""
    code, envelope, _, _ = run(monkeypatch, tmp_path, "view", str(ALTIUM), "--doc", "blink.PcbLib")
    assert code == 0
    summary = envelope["result"]["summary"]
    assert summary["kind"] == "library" and summary["lib"] == "pcb" and summary["counts"]["items"] == 3
    assert envelope["result"]["theme"] == "altium"
    code, envelope, _, _ = run(
        monkeypatch, tmp_path, "view", str(ROOT / "tests" / "data" / "libs" / "Mini_v9.kicad_sym")
    )
    assert code == 0 and envelope["result"]["summary"]["lib"] == "schematic"
    assert envelope["result"]["theme"] == "kicad"


def test_drawing_summary(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Scenario "Summary of a drawing" (c0180)."""
    from _draftsman import DOCUMENT, stored

    path = tmp_path / "authored.PCBDwf"
    path.write_bytes(stored(DOCUMENT))
    code, envelope, _, _ = run(monkeypatch, tmp_path, "view", str(path), "--json")
    assert code == 0
    summary = envelope["result"]["summary"]
    assert summary["kind"] == "drawing" and summary["counts"]["sheets"] == 1
    assert summary["counts"]["BoardAssemblyViewData"] == 1 and not summary["panel"]


CACHE_BOARD = ROOT / "tests" / "data" / "altium" / "blink" / "blink.PcbDoc"


def test_second_open_reads_the_cache(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    board = tmp_path / "blink.PcbDoc"
    shutil.copy(CACHE_BOARD, board)
    folder = tmp_path / "cache"
    monkeypatch.setenv("FENOLITE_CACHE_DIR", str(folder))
    code, first, _, _ = run(monkeypatch, tmp_path, "view", str(board), "--json")
    assert code == 0 and first["result"]["cache"] == {"where": "user", "hits": 0, "misses": 1}
    code, second, _, _ = run(monkeypatch, tmp_path, "view", str(board), "--json")
    assert (
        second["result"]["cache"]["hits"] == 1 and second["result"]["summary"] == first["result"]["summary"]
    )
    data = bytearray(board.read_bytes())
    data[-1] ^= 0xFF  # one byte of the file changes, so its digest does
    board.write_bytes(bytes(data))
    code, third, _, _ = run(monkeypatch, tmp_path, "view", str(board), "--json")
    assert third["result"]["cache"]["misses"] == 1
    assert len(list((folder / "view").glob("*.json.gz"))) == 2


def test_off_and_project(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    board = tmp_path / "blink.PcbDoc"
    shutil.copy(CACHE_BOARD, board)
    code, reply, _, _ = run(monkeypatch, tmp_path, "view", str(board), "--cache", "off", "--json")
    assert code == 0 and reply["result"]["cache"] == {"where": "off", "hits": 0, "misses": 0}
    run(monkeypatch, tmp_path, "view", str(board), "--cache", "project", "--json")
    assert list((tmp_path / ".fenolite" / "view-cache").glob("*.json.gz"))


def test_export_docs(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Scenario "Export of one document" (c0182)."""
    code, envelope, _, _ = run(
        monkeypatch,
        tmp_path,
        "view",
        str(ALTIUM),
        "--export",
        str(tmp_path / "p.html"),
        "--docs",
        "blink.PcbDoc",
        "--json",
    )
    assert code in (0, 4)
    documents = envelope["result"]["export"]["documents"]
    assert len(documents) == 1
    code, envelope, _, _ = run(
        monkeypatch, tmp_path, "view", str(ALTIUM), "--export", "x.html", "--docs", "nope", "--json"
    )
    assert code == 2


def test_compare(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Scenario "Compare counts" (c0184): a board against its copy with one part moved."""
    old = tmp_path / "old.kicad_pcb"
    shutil.copy(BOARD, old)
    text = BOARD.read_text(encoding="utf-8")
    start = text.index("(footprint ")
    at = text.index("(at ", start)
    end = text.index(")", at)
    x, y, *rest = text[at + 4 : end].split()
    new = tmp_path / "new.kicad_pcb"
    new.write_text(text[: at + 4] + " ".join([str(float(x) + 1), y, *rest]) + text[end:], encoding="utf-8")
    code, envelope, _, _ = run(monkeypatch, tmp_path, "view", str(new), "--compare", str(old), "--json")
    assert code == 0 and envelope["result"]["compare"]["moved"] == 1
    code, envelope, _, _ = run(
        monkeypatch, tmp_path, "view", str(new), "--compare", str(ALTIUM_SHEET), "--json"
    )
    assert code == 2


ALTIUM_SHEET = ROOT / "tests" / "data" / "altium" / "blink" / "blink.SchDoc"


def test_variant(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Scenario "Unknown variant" (c0186), and the counts of a known one."""
    from _variants import variant_text

    folder = tmp_path / "blink"
    shutil.copytree(ALTIUM.parent, folder)
    sheet = cmd_view.scene_of(folder / "blink.SchDoc")
    uid = next(c["uid"] for c in sheet["comps"] if c["ref"] == "R1")
    project = folder / "blink.PrjPcb"
    project.write_bytes(project.read_bytes() + b"\r\n" + variant_text(uid).encode())
    code, envelope, _, _ = run(
        monkeypatch, tmp_path, "view", str(project), "--doc", "blink.SchDoc", "--variant", "Lite", "--json"
    )
    assert code == 0 and envelope["result"]["variant"] == {"name": "Lite", "fitted": 2, "not_fitted": 1}
    code, envelope, _, _ = run(monkeypatch, tmp_path, "view", str(project), "--variant", "Nope", "--json")
    assert code == 2


def test_check_reply(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Scenario "Not a check reply" (c0188), and the counts of a check reply drawn on the board."""
    code, envelope, _, _ = run(
        monkeypatch, tmp_path, "check", str(BOARD), "--stages", "model.validate,copper.clearance", "--json"
    )
    reply = tmp_path / "check.json"
    reply.write_text(json.dumps(envelope), encoding="utf-8")
    code, envelope, _, _ = run(monkeypatch, tmp_path, "view", str(BOARD), "--check", str(reply), "--json")
    assert code == 0
    found = envelope["result"]["check"]
    assert found["total"] == len(json.loads(reply.read_text(encoding="utf-8"))["issues"]) > 0
    analyze = tmp_path / "analyze.json"
    analyze.write_text(json.dumps({"command": "analyze", "result": {"distances": []}, "issues": []}))
    code, _, err, _ = run(monkeypatch, tmp_path, "view", str(BOARD), "--check", str(analyze), "--json")
    assert code == 3 and err["code"] == "FEN-3004"
    code, _, err, _ = run(monkeypatch, tmp_path, "view", str(BOARD), "--check", "missing.json", "--json")
    assert code == 3 and err["code"] == "FEN-3001"


def test_check_run_on_altium(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """`--check run` checks the project in the same process and writes nothing (c0188)."""
    folder = tmp_path / "blink"
    shutil.copytree(ALTIUM.parent, folder)
    before = sorted(p.name for p in folder.iterdir())
    code, envelope, _, _ = run(
        monkeypatch,
        tmp_path,
        "view",
        str(folder / "blink.PrjPcb"),
        "--doc",
        "blink.PcbDoc",
        "--check",
        "run",
        "--json",
    )
    assert code == 0 and set(envelope["result"]["check"]) == {"error", "warning", "info", "total", "placed"}
    assert sorted(p.name for p in folder.iterdir()) == before


def test_marks(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Scenario "Marks for an agent" (c0189): `result.marks` lists the marks of an authored review file."""
    review = tmp_path / "review.json"
    marks = [
        {
            "id": "m1",
            "doc": BOARD.name,
            "x_nm": 12_500_000,
            "y_nm": 3_250_000,
            "note": "gap too small",
            "select": "R1",
        },
        {"id": "m2", "doc": "other.kicad_sch", "x_nm": 0, "y_nm": 0, "note": "label?"},
    ]
    review.write_text(json.dumps({"schema": "fenolite.review.v0", "marks": marks}), encoding="utf-8")
    code, envelope, _, _ = run(monkeypatch, tmp_path, "view", str(BOARD), "--marks", str(review), "--json")
    assert code == 0
    first, second = envelope["result"]["marks"]
    assert (first["doc"], first["x_mm"], first["y_mm"], first["note"]) == (
        BOARD.name,
        12.5,
        3.25,
        "gap too small",
    )
    assert second["note"] == "label?"
    review.write_text(json.dumps({"schema": "fenolite.review.v0", "marks": [{"id": "m1"}]}), encoding="utf-8")
    code, _, err, _ = run(monkeypatch, tmp_path, "view", str(BOARD), "--marks", str(review), "--json")
    assert code == 3 and err["code"] == "FEN-3004"
    code, _, err, _ = run(monkeypatch, tmp_path, "view", str(BOARD), "--marks", "none.json", "--json")
    assert code == 3 and err["code"] == "FEN-3001"


def test_select(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """`--select` opens the page at a part or net (c0189): the reply says whether the document holds it, and
    an exported page carries it."""
    code, envelope, _, _ = run(monkeypatch, tmp_path, "view", str(BOARD), "--select", "R1", "--json")
    assert code == 0 and envelope["result"]["select"] == {"name": "R1", "found": True}
    code, envelope, _, _ = run(monkeypatch, tmp_path, "view", str(BOARD), "--select", "net:GND", "--json")
    assert envelope["result"]["select"]["found"] is True
    code, envelope, _, _ = run(monkeypatch, tmp_path, "view", str(BOARD), "--select", "U99", "--json")
    assert envelope["result"]["select"]["found"] is False and "U99" in envelope["result"]["notes"][-1]
    out = tmp_path / "view.html"
    code, envelope, _, _ = run(
        monkeypatch,
        tmp_path,
        "view",
        str(BOARD),
        "--select",
        "R1",
        "--export",
        str(out),
        "--dry-run",
        "--json",
    )
    plan = envelope["result"]["plan_id"]
    code, _, _, _ = run(
        monkeypatch,
        tmp_path,
        "view",
        str(BOARD),
        "--select",
        "R1",
        "--export",
        str(out),
        "--confirm",
        "--plan",
        plan,
    )
    data = embedded(out.read_text(encoding="utf-8"))
    assert code == 0 and data is not None and data["select"] == "R1" and data["marks"] == []
