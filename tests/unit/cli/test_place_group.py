# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""``fenolite place --turn``, ``--shift`` and ``--pose-search`` (change c0227; capability layout-reuse,
"Group moves", "Copper of a moved group" and "Pose search"), on the authored module of
``tests/_groupbench.py`` written as KiCad files with its library. Hermetic: no tool runs."""

from __future__ import annotations

import dataclasses
import subprocess
from pathlib import Path
from typing import Any

import pytest
from _checkcli import run
from _groundties import _box, _zone
from _groupbench import GROUP, module
from _projects import tree_snapshot
from _reusebench import project_files
from _ties import MM

from fenolite.backends.kicad.frame import board_pads
from fenolite.backends.kicad.pcb import read_board
from fenolite.checks.copper import check_copper
from fenolite.cli.place_group import turn_about
from fenolite.core.coords import Point
from fenolite.model.design import Design

TURN = ("--turn", ",".join(GROUP), "--about", "20mm,20mm")


@pytest.fixture(autouse=True)
def isolated(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("KICAD_CONFIG_HOME", str(tmp_path / "kicad-config"))
    for name in ("KICAD10_FOOTPRINT_DIR", "KICAD9_FOOTPRINT_DIR"):
        monkeypatch.delenv(name, raising=False)

    def refuse(*args: object, **kwargs: object) -> None:
        raise AssertionError("a subprocess was started")

    monkeypatch.setattr(subprocess, "run", refuse)
    monkeypatch.setattr(subprocess, "Popen", refuse)


def _project(tmp_path: Path, design: Design) -> Path:
    for name, text in project_files(design, name="board").items():
        path = tmp_path / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8", newline="\n")
    return tmp_path / "board.kicad_pcb"


def place(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, *args: str, outside: bool = False
) -> tuple[int, dict[str, Any], dict[str, Any], Design]:
    """``fenolite place board.kicad_pcb ARGS`` on the module, and the board as read before."""
    board = _project(tmp_path, module(outside=outside))
    before = read_board(board)
    code, env, err, _ = run(monkeypatch, tmp_path, "place", board.name, *args)
    return code, env, err, before


def _pads(design: Design) -> dict[tuple[str, str], Point]:
    return {(record.ref, record.number): record.position for record in board_pads(design)}


def _findings(design: Design) -> int:
    return len(check_copper(design, pads=board_pads(design)).findings)


def test_a_module_turned_with_its_satellites(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Scenario "A module turned with its satellites": every pad lies on its old position turned by 90°
    about the point, the tracks and vias among the group's pads turn with them, and the copper check
    finds nothing new."""
    code, env, _, before = place(monkeypatch, tmp_path, *TURN, "--angle", "90", "--confirm")
    assert code == 0, env["issues"]
    assert env["result"]["strategy"] == "group"
    group = env["result"]["group"]
    assert group["kind"] == "turn" and group["residual"] == 0
    assert group["copper"] == {"items": 8, "zones": 0}
    assert group["copper_check"]["new"] == 0
    assert "H-G-GROUP-MOVE" in env["evidence"]["hypotheses"]
    after = read_board(tmp_path / "board.kicad_pcb")
    turn = turn_about(Point(20 * MM, 20 * MM), 90_000_000)
    old, new = _pads(before), _pads(after)
    assert all(new[key] == turn.apply(at) for key, at in old.items())
    assert after.board is not None and before.board is not None
    assert {(t.start, t.end) for t in after.board.tracks} == {
        (turn.apply(t.start), turn.apply(t.end)) for t in before.board.tracks
    }
    assert {v.position for v in after.board.vias} == {turn.apply(v.position) for v in before.board.vias}
    sides = {(record.ref, record.side) for record in board_pads(after)}
    assert ("C3", "bottom") in sides and ("C1", "top") in sides
    assert _findings(after) == _findings(before) == 0
    assert [row["ref"] for row in env["result"]["moved"]] == sorted(GROUP)


def test_a_track_to_a_part_outside_the_group_stays_shift(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Scenario "A track to a part outside the group stays": the track from ``C1`` to ``R9`` stays with
    one ``place.copper-left``, and the tracks among the group move by 1 mm."""
    code, env, _, before = place(
        monkeypatch, tmp_path, "--shift", ",".join(GROUP), "--by", "1mm,0mm", "--confirm", outside=True
    )
    assert code == 0, env["issues"]
    assert [(found["code"], found["where"]) for found in env["issues"]] == [("place.copper-left", "C1")]
    after = read_board(tmp_path / "board.kicad_pcb")
    assert after.board is not None and before.board is not None
    ends = {(t.start, t.end) for t in after.board.tracks}
    e = next(t for t in before.board.tracks if t.start == Point(21 * MM, 15 * MM))
    assert (e.start, e.end) in ends
    shifted = {(Point(t.start.x + MM, t.start.y), Point(t.end.x + MM, t.end.y)) for t in before.board.tracks}
    assert len(ends & shifted) == 6
    assert env["result"]["group"]["transform"] == {"rotation": 0, "x": MM, "y": 0}


def test_a_zone_on_the_group_turns_with_it(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """A filled zone of ``C`` over ``C2-1`` joins pads of the group only, so it turns with the group and
    its fill is reported stale."""
    design = module()
    assert design.board is not None
    net = next(net.id for net in design.circuit.nets if net.name == "C")
    zone = _zone(1, net, _box(24.4, 21.4, 25.6, 22.6))
    design = dataclasses.replace(design, board=dataclasses.replace(design.board, zones=(zone,)))
    board = _project(tmp_path, design)
    code, env, _, _ = run(monkeypatch, tmp_path, "place", board.name, *TURN, "--angle", "90", "--confirm")
    assert code == 0, env["issues"]
    assert env["result"]["group"]["copper"] == {"items": 8, "zones": 1}
    assert [found["code"] for found in env["issues"]] == ["place.fill-stale"]
    after = read_board(board)
    assert after.board is not None
    turn = turn_about(Point(20 * MM, 20 * MM), 90_000_000)
    assert set(after.board.zones[0].outline) == {turn.apply(point) for point in zone.outline}


def test_a_dry_run_of_a_turn_writes_nothing(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    _project(tmp_path, module())
    snapshot = tree_snapshot(tmp_path)
    code, env, _, _ = run(
        monkeypatch, tmp_path, "place", "board.kicad_pcb", *TURN, "--angle", "45", "--dry-run"
    )
    assert code == 0, env["issues"]
    assert [entry["path"] for entry in env["result"]["plan"]] == ["board.kicad_pcb"]
    assert env["result"]["group"]["residual"] <= 1_000
    assert tree_snapshot(tmp_path) == snapshot


def test_a_shift_onto_copper_is_refused(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """``C2`` shifted onto ``R9`` and the track of ``E``: the copper check finds a new short, so nothing
    is written."""
    code, env, _, _ = place(
        monkeypatch, tmp_path, "--shift", "C2", "--by", "8mm,-11mm", "--dry-run", outside=True
    )
    assert code == 5 and "plan" not in env["result"]
    assert "place.group-failed" in {found["code"] for found in env["issues"]}


def test_poses_of_a_module_pose(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Scenario "Poses of a module": 36 poses are tried, the best come sorted by demand, and nothing is
    written."""
    _project(tmp_path, module(outside=True))
    snapshot = tree_snapshot(tmp_path)
    code, env, _, _ = run(
        monkeypatch, tmp_path, "place", "board.kicad_pcb", *TURN, "--pose-search", "--within", "1mm",
        "--pitch", "1mm", "--confirm",
    )  # fmt: skip
    assert code == 0, env["issues"]
    search = env["result"]["group"]["search"]
    assert search["tried"] == 36 and search["nets"] == ["E"] and len(search["poses"]) == 10
    demands = [pose["demand"] for pose in search["poses"]]
    assert demands == sorted(demands) and demands[0] < search["current"]
    best = search["poses"][0]
    # R9-1 lies at (33, 10) mm: the best pose shifts C1-2 from (21, 15) mm towards it, unturned
    assert best == {"rotation": 0, "dx": MM, "dy": -MM, "demand": demands[0]}
    assert env["result"]["moved"] == [] and "plan" not in env["result"]
    assert tree_snapshot(tmp_path) == snapshot


@pytest.mark.parametrize(
    "args",
    [
        ("--turn", "U1", "--angle", "90"),
        ("--turn", "U1", "--about", "1mm,1mm"),
        ("--turn", "U1,U1", "--about", "1mm,1mm", "--angle", "90"),
        ("--turn", "U1", "--about", "1mm", "--angle", "90"),
        ("--turn", "U1", "--about", "1mm,1mm", "--angle", "90", "--pose-search", "--within", "1mm"),
        ("--turn", "U1", "--about", "1mm,1mm", "--pose-search"),
        ("--turn", "U1", "--about", "1mm,1mm", "--angle", "90", "--within", "1mm"),
        ("--turn", "U1", "--about", "1mm,1mm", "--angle", "90", "--by", "1mm,1mm"),
        ("--turn", "U1", "--shift", "C1", "--by", "1mm,1mm"),
        ("--shift", "U1"),
        ("--shift", "U1", "--by", "1mm,1mm", "--angle", "90"),
        ("--shift", "U1", "--by", "1mm,1mm", "--pose-search"),
        ("--shift", "U1", "--by", "1mm,1mm", "--strategy", "grid"),
        ("--about", "1mm,1mm"),
        ("--turn", "U1", "--about", "1mm,1mm", "--pose-search", "--within", "1m", "--pitch", "0.01mm"),
    ],
)
def test_usage_errors_shift(monkeypatch: pytest.MonkeyPatch, tmp_path: Path, args: tuple[str, ...]) -> None:
    code, _, err, _ = place(monkeypatch, tmp_path, *args, "--dry-run")
    assert code == 2 and err["code"] == "FEN-2001", args
