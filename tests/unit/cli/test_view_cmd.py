# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""``fenolite view`` (capability cli-contract, "View command")."""

from __future__ import annotations

import json
import threading
from pathlib import Path

import pytest
from _checkcli import run

from fenolite.cli import cmd_view
from fenolite.view.export import embedded

ROOT = Path(__file__).resolve().parents[3]
BOARD = ROOT / "tests" / "data" / "kicad" / "board" / "two_layer.kicad_pcb"
ALTIUM = ROOT / "tests" / "data" / "altium" / "blink" / "blink.PrjPcb"


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
    code, envelope, _, _ = run(monkeypatch, tmp_path, "view", str(ALTIUM), "--doc", "blink.SchDoc")
    assert code == 0 and envelope["result"]["summary"] is None
    assert "no viewer" in envelope["result"]["notes"][0]


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
