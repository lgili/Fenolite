# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The opt-in stage ``altium.integrity`` of ``fenolite check`` (change c0241, task 2.1)."""

from __future__ import annotations

import io
import json
import sys
from pathlib import Path
from typing import Any

import pytest

import fenolite.cli.main as cli_main
from fenolite.backends.altium.edit import records as rec
from fenolite.backends.altium.edit.state import State
from fenolite.checks.documents import DOCUMENT_STAGES, OPT_IN_DOCUMENT_STAGES


def _check(monkeypatch: pytest.MonkeyPatch, *args: str) -> tuple[int, dict[str, Any]]:
    out, err = io.StringIO(), io.StringIO()
    with monkeypatch.context() as patch:
        patch.setattr(sys, "stdout", out)
        patch.setattr(sys, "stderr", err)
        code = cli_main.main(["check", *args, "--json"])
    return code, json.loads(out.getvalue())


def _stage(env: dict[str, Any]) -> dict[str, Any]:
    [stage] = [s for s in env["result"]["stages"] if s["name"] == "altium.integrity"]
    return stage


def test_the_stage_is_opt_in() -> None:
    assert "altium.integrity" in OPT_IN_DOCUMENT_STAGES and "altium.integrity" not in DOCUMENT_STAGES


def test_the_stage_on_the_kit_board(monkeypatch: pytest.MonkeyPatch, board: Path) -> None:
    code, env = _check(monkeypatch, str(board), "--stages", "altium.integrity")
    stage = _stage(env)
    assert code == 0 and stage["status"] == "ok" and stage["summary"]["documents"] == ["edit.PcbDoc"]
    assert stage["evidence"]["level"] == "INFERRED"


def test_a_planted_fault_is_a_warning_with_its_document(monkeypatch: pytest.MonkeyPatch, board: Path) -> None:
    state = State.of(board.read_bytes())
    state.replace("Polygons6", 1, rec.set_property(state.get("Polygons6")[1], {"POURINDEX": "0"}))
    board.write_bytes(state.data())
    code, env = _check(monkeypatch, str(board), "--stages", "altium.integrity")
    issues = [i for i in env["issues"] if i["code"].startswith("altium.integrity.")]
    assert code == 0 and [i["code"] for i in issues] == ["altium.integrity.pour-index-twice"]
    assert issues[0]["severity"] == "warning" and issues[0]["where"] == "edit.PcbDoc:Polygons6/Data#1"


def test_the_stage_does_not_run_by_default(monkeypatch: pytest.MonkeyPatch, board: Path) -> None:
    _, env = _check(monkeypatch, str(board), "--stages", "roundtrip.rta0")
    assert "altium.integrity" not in {s["name"] for s in env["result"]["stages"]}


def test_board_drawing_stage(monkeypatch: pytest.MonkeyPatch, ops_board: Any, board: Path) -> None:
    """Change c0497: the opt-in stage ``altium.board-drawing``."""
    assert "altium.board-drawing" in OPT_IN_DOCUMENT_STAGES
    code, env = _check(monkeypatch, str(ops_board("drawn")), "--stages", "altium.board-drawing")
    [stage] = [s for s in env["result"]["stages"] if s["name"] == "altium.board-drawing"]
    assert code == 0 and stage["status"] == "ok" and env["issues"] == []
    code, env = _check(monkeypatch, str(board), "--stages", "altium.board-drawing")
    assert [i["code"] for i in env["issues"]] == ["altium.board-drawing.none"]
