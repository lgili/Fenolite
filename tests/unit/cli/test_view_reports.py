# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Recorded operation/check evidence in summary, offline replay and live review (c0239)."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

import pytest
from _checkcli import run

from fenolite.cli import cmd_view
from fenolite.view.export import embedded

ROOT = Path(__file__).resolve().parents[3]
BOARD = ROOT / "tests/data/kicad/board/two_layer.kicad_pcb"


def recorded(command: str = "convert", **kwargs: Any) -> dict[str, Any]:
    return {
        "command": command,
        "ok": True,
        "issues": [],
        "evidence": {"level": "INFERRED"},
        "input": {"path": BOARD.name, "sha256": hashlib.sha256(BOARD.read_bytes()).hexdigest()},
        "receipt": {"files": [{"path": "converted.kicad_pcb"}]},
        "result": {"equivalence": {"unexplained": 0}, "report": {"lossy": False}, "experimental": False},
        **kwargs,
    }


def write_report(tmp_path: Path, data: dict[str, Any], name: str = "report.json") -> str:
    (tmp_path / name).write_text(json.dumps(data), encoding="utf-8")
    return name


def test_reports_are_embedded_and_replayed_without_reexecution(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    name = write_report(tmp_path, recorded())
    args = ("view", str(BOARD), "--report", name, "--export", "review.html")
    code, env, _, _ = run(monkeypatch, tmp_path, *args, "--dry-run")
    assert code == 0 and not (tmp_path / "review.html").exists()
    cards = {card["id"]: card for card in env["result"]["review"]["cards"]}
    assert cards["convert"]["state"] == "passed" and cards["drc"]["state"] == "not-run"
    digest = env["result"]["export"]["sha256"]
    monkeypatch.setattr(cmd_view, "reports_of", lambda *_: pytest.fail("replay reread the report"))
    code, env, _, _ = run(monkeypatch, tmp_path, *args, "--confirm", "--plan", env["result"]["plan_id"])
    assert code == 0 and hashlib.sha256((tmp_path / "review.html").read_bytes()).hexdigest() == digest
    data = embedded((tmp_path / "review.html").read_text(encoding="utf-8"))
    assert data is not None
    assert data["scenes"]["doc1"]["project_review"]["cards"] == list(cards.values())


@pytest.mark.parametrize("check", (False, True))
def test_changed_report_invalidates_the_reviewed_plan(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, check: bool
) -> None:
    data = recorded()
    if check:
        data |= {"command": "check", "result": {"stages": []}}
    name = write_report(tmp_path, data)
    args = ("view", str(BOARD), "--check" if check else "--report", name, "--export", "review.html")
    code, env, _, _ = run(monkeypatch, tmp_path, *args, "--dry-run")
    assert code == 0
    write_report(tmp_path, data | {"issues": [{"code": "model.changed", "severity": "error"}]})
    code, _, error, _ = run(monkeypatch, tmp_path, *args, "--confirm", "--plan", env["result"]["plan_id"])
    assert code == 4 and error["code"] == "FEN-4002" and not (tmp_path / "review.html").exists()


@pytest.mark.parametrize("kind", ("missing", "malformed", "unsupported", "duplicate"))
def test_bad_reports_write_nothing(monkeypatch: pytest.MonkeyPatch, tmp_path: Path, kind: str) -> None:
    name = "report.json"
    if kind == "malformed":
        (tmp_path / name).write_text("{", encoding="utf-8")
    elif kind != "missing":
        write_report(tmp_path, recorded("analyze" if kind == "unsupported" else "convert"))
    extra = ("--report", name) if kind == "duplicate" else ()
    code, _, error, _ = run(
        monkeypatch,
        tmp_path,
        "view",
        str(BOARD),
        "--report",
        name,
        *extra,
        "--export",
        "review.html",
        "--confirm",
    )
    assert code == (2 if kind == "duplicate" else 3)
    assert error["code"] == (
        "FEN-2001" if kind == "duplicate" else "FEN-3001" if kind == "missing" else "FEN-3004"
    )
    assert not (tmp_path / "review.html").exists()


def test_check_hints_and_stage_scope_are_preserved(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    check = recorded(
        "check",
        result={
            "stages": [
                {"name": "drc.kicad", "status": "errors", "evidence": {"level": "INFERRED"}, "summary": {}}
            ]
        },
        issues=[
            {
                "code": "kicad.drc.clearance",
                "severity": "error",
                "message": "gap",
                "hint": "Review the declared clearance",
                "where": "@10,12",
            }
        ],
    )
    name = write_report(tmp_path, check)
    code, env, _, _ = run(
        monkeypatch, tmp_path, "view", str(BOARD), "--check", name, "--export", "review.html", "--confirm"
    )
    assert code == 0
    assert next(c for c in env["result"]["review"]["cards"] if c["id"] == "drc")["state"] == "failed"
    data = embedded((tmp_path / "review.html").read_text(encoding="utf-8"))
    assert data is not None
    overlay = data["scenes"]["doc1"]["check"]
    assert overlay["findings"][0]["hint"] == "Review the declared clearance"
    assert overlay["source"] == check["input"] and overlay["stages"] == check["result"]["stages"]


def test_live_save_reclassifies_loaded_report(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    board = tmp_path / BOARD.name
    board.write_bytes(BOARD.read_bytes())
    write_report(tmp_path, recorded())
    observed: list[str] = []

    def serve(live: Any, httpd: Any, **_: Any) -> None:
        try:
            for suffix in (b"", b"\n"):
                if suffix:
                    board.write_bytes(board.read_bytes() + suffix)
                    live.check()
                    live.check()
                scene = json.loads(live.scene("doc1"))
                observed.append(
                    next(c for c in scene["project_review"]["cards"] if c["id"] == "convert")["state"]
                )
        finally:
            httpd.server_close()

    monkeypatch.setattr(cmd_view.server, "run", serve)
    monkeypatch.setattr(cmd_view, "_log", lambda _message: None)
    code, _, _, _ = run(
        monkeypatch,
        tmp_path,
        "view",
        str(board),
        "--report",
        "report.json",
        "--serve",
        "--port",
        "0",
        "--no-browser",
        "--no-models",
    )
    assert code == 0 and observed == ["passed", "limited"]


def test_stale_check_markers_keep_a_visible_historical_warning(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    data = recorded(
        "check",
        input={"path": BOARD.name, "sha256": "0" * 64},
        result={"stages": [{"name": "drc.kicad", "status": "ok", "evidence": {"level": "INFERRED"}}]},
    )
    write_report(tmp_path, data)
    code, env, _, _ = run(
        monkeypatch,
        tmp_path,
        "view",
        str(BOARD),
        "--check",
        "report.json",
        "--export",
        "review.html",
        "--confirm",
    )
    assert code == 0 and not env["result"]["review"]["binding"]["matched"]
    doc = embedded((tmp_path / "review.html").read_text(encoding="utf-8"))
    assert doc is not None
    assert any("historical" in note for note in doc["scenes"]["doc1"]["check"]["notes"])
