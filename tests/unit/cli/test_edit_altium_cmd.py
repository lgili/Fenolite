# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""``fenolite edit PATH.PcbDoc --ops-file FILE`` with an edit plan (change c0502, D5), on the Part J kit
board. The "newer save" is the board changed by the test itself."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from fenolite.backends.altium import edit
from fenolite.backends.altium.read.pcb import read_pcbdoc
from fenolite.backends.altium.read.pcbprims import TrackRecord
from fenolite.cli.main import main
from tests.unit.backends.altium.edit.conftest import OPEN, mm
from tests.unit.backends.altium.test_part_j import build_board

PROBE = {"kind": "track", "start": ["10mm", "5mm"], "end": ["20mm", "5mm"], "net": "GND"}
MOVE = {"op": "move", "item": PROBE, "dx": 0, "dy": "1mm"}
OTHER = edit.Track((mm(2), mm(2)), (mm(12), mm(2)), None)


@pytest.fixture(scope="module")
def kit(tmp_path_factory: pytest.TempPathFactory) -> bytes:
    folder = tmp_path_factory.mktemp("kit") / "board"
    build_board(folder)
    return (folder / "edit.PcbDoc").read_bytes()


@pytest.fixture
def folder(monkeypatch: pytest.MonkeyPatch, tmp_path: Path, kit: bytes) -> Path:
    monkeypatch.setenv("FENOLITE_STATE_DIR", str(tmp_path / "state"))
    work = tmp_path / "work"
    work.mkdir()
    monkeypatch.chdir(work)
    (work / "board.PcbDoc").write_bytes(kit)
    return work


def run(capsys: Any, *argv: str) -> tuple[int, Any, Any]:
    code = main([*argv, "--json"])
    captured = capsys.readouterr()
    out = json.loads(captured.out) if captured.out.strip() else None
    err = json.loads(captured.err.strip().splitlines()[-1]) if captured.err.strip() else None
    return code, out, err


def _resave(board: Path, session_edit: Any) -> None:
    """A newer save of ``board``, made by an edit session in place."""
    session = edit.open(board, gates=OPEN)
    assert isinstance(session, edit.Session)
    assert session_edit(session).commit(board, backup=False).written


def _tracks(data: bytes) -> list[tuple[int, int, int, int, int]]:
    return sorted(
        (t.x1, t.y1, t.x2, t.y2, t.width) for t in read_pcbdoc(data).tracks if isinstance(t, TrackRecord)
    )


def test_a_plan_confirmed_after_a_newer_save(capsys: Any, folder: Path) -> None:
    """Scenario "A plan confirmed after a newer save"."""
    board = folder / "board.PcbDoc"
    (folder / "ops.json").write_text(json.dumps([MOVE]), encoding="utf-8")
    code, out, _ = run(
        capsys, "edit", "board.PcbDoc", "--ops-file", "ops.json", "--gate", "move", "--dry-run"
    )
    assert code == 0, out
    plan = out["result"]["edit_plan"]
    assert plan["schema"] == "fenolite.altium-edit-plan.v0" and plan["document"] == "board.PcbDoc"
    (folder / "plan.json").write_text(json.dumps(plan), encoding="utf-8")
    first_id = out["result"]["plan_id"]
    _resave(board, lambda s: s.move(OTHER, 0, mm(2)))
    newer = board.read_bytes()
    edit_move = ("edit", "board.PcbDoc", "--gate", "move", "--ops-file")
    code, _, err = run(capsys, *edit_move, "ops.json", "--confirm", "--plan", first_id)
    assert code == 4 and err["code"] == "FEN-4002" and board.read_bytes() == newer
    code, out, _ = run(
        capsys, "edit", "board.PcbDoc", "--ops-file", "plan.json", "--gate", "move", "--dry-run"
    )
    assert code == 0, out
    result = out["result"]
    assert result["rebased"] is True and result["base_sha256"] == plan["base_sha256"]
    assert result["operations"] == [{"label": plan["operations"][0]["label"], "status": "applied"}]
    code, out, _ = run(capsys, *edit_move, "plan.json", "--confirm", "--plan", result["plan_id"])
    assert code == 0, out
    tracks = _tracks(board.read_bytes())
    assert tracks != _tracks(newer) and len(tracks) == len(_tracks(newer))
    moved = set(_tracks(newer)) - set(tracks)
    assert len(moved) == 1  # the plan's move, on top of the user's


def test_a_conflict_plans_no_write(capsys: Any, folder: Path) -> None:
    """Scenario "A conflict plans no write"."""
    board = folder / "board.PcbDoc"
    width = {"op": "set_property", "item": MOVE["item"], "key": "width", "value": 500000, "old": 250000}
    (folder / "ops.json").write_text(json.dumps([width]), encoding="utf-8")
    code, out, _ = run(capsys, "edit", "board.PcbDoc", "--ops-file", "ops.json", "--dry-run")
    plan = out["result"]["edit_plan"]
    assert code == 5 and plan is not None  # the gate is closed; the plan is made all the same
    (folder / "plan.json").write_text(json.dumps(plan), encoding="utf-8")
    track = edit.Track((mm(10), mm(5)), (mm(20), mm(5)), "GND")
    _resave(board, lambda s: s.set_property(track, "width", mm(0.3), old=mm(0.25)))
    code, out, _ = run(capsys, "edit", "board.PcbDoc", "--ops-file", "plan.json", "--gate", "set_property",
                       "--dry-run")  # fmt: skip
    assert code == 5
    assert "altium.edit.rebase-conflict" in [i["code"] for i in out["issues"]]
    [row] = out["result"]["operations"]
    assert row["status"] == "conflict" and [f["field"] for f in row["fields"]] == ["width"]
    assert not out["result"].get("plan", {}).get("writes")


def test_a_plan_that_does_not_read(capsys: Any, folder: Path) -> None:
    (folder / "plan.json").write_text('{"schema": "fenolite.altium-edit-plan.v0"}', encoding="utf-8")
    code, _, err = run(capsys, "edit", "board.PcbDoc", "--ops-file", "plan.json", "--dry-run")
    assert code == 3 and err["code"] == "FEN-3004"
