# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""``fenolite tidy`` judged by the running ``kicad-cli`` (changes c0208 and c0214; capability copper-tidy,
"Tidy command"; hypothesis ``H-K-TIDY-DRC``), on the authored benches of ``tests/_tidybench.py`` written for
the tool's major with a project that holds the benches' 0.3 mm clearance."""

from __future__ import annotations

import dataclasses
import io
import json
from collections import Counter
from pathlib import Path
from typing import Any

import pytest
from _groundties import _box, _zone
from _probes import major, runner
from _tidybench import bench, staircase

from fenolite.backends.kicad.frame import board_pads
from fenolite.backends.kicad.pcb import write_board
from fenolite.backends.kicad.pro import synthesize_project
from fenolite.cli import main as cli_main
from fenolite.model.design import Design
from fenolite.tidy import apply_corners, find_corners

pytestmark = pytest.mark.needs_kicad


def _write(folder: Path, name: str, design: Design) -> Path:
    board = folder / f"{name}.kicad_pcb"
    board.write_text(write_board(design, target=major()).text, encoding="utf-8", newline="\n")
    project = synthesize_project(design, target=major(), board_name=name)
    board.with_suffix(".kicad_pro").write_text(project, encoding="utf-8", newline="\n")
    return board


def _drc(board: Path) -> Counter[str]:
    report = runner().drc(
        board, files={board.with_suffix(".kicad_pro").name: board.with_suffix(".kicad_pro")}
    )
    assert report.report is not None
    found = (*report.report.violations, *report.report.unconnected_items)
    return Counter(item.type for item in found if not item.excluded)


def tidy(
    monkeypatch: pytest.MonkeyPatch, folder: Path, board: Path, *args: str
) -> tuple[int, dict[str, Any]]:
    monkeypatch.chdir(folder)
    out = io.StringIO()
    monkeypatch.setattr("sys.stdout", out)
    monkeypatch.setattr("sys.stderr", io.StringIO())
    cli = str(runner().path)
    code = cli_main.main(["tidy", board.name, "--drc", "--kicad-cli", cli, *args, "--json"])
    return code, json.loads(out.getvalue() or "{}")


def test_a_tidy_adds_no_drc_finding(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """The stub, the lead and its via go, the L of ``SIG`` is straightened and the T-joint of ``BUS`` gets
    its 45° entry: KiCad finds one dangling track (the stub) and one dangling via fewer, and nothing new;
    ``k`` of ``BUS``, kept, still dangles."""
    board = _write(tmp_path, "tidy", bench())
    before = _drc(board)
    code, env = tidy(monkeypatch, tmp_path, board, "--confirm")
    assert code == 0, env
    assert env["evidence"]["level"] == "KICAD-VERIFIED" and env["result"]["drc"]["new"] == []
    assert env["result"]["counts"] == {
        "chamfer.t-joint": 1,
        "prune.free-end": 2,
        "prune.via-under-two-layers": 1,
        "straighten.fewer-turns": 1,
    }
    after = _drc(board)
    assert all(after[kind] <= before[kind] for kind in after), (before, after)
    assert (
        before["track_dangling"] - after["track_dangling"] == 1
    )  # KiCad counts the lead as joined to its via
    assert before["via_dangling"] - after["via_dangling"] == 1


def test_an_undone_chamfer_is_one_kicad_refuses(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """The chamfer next to ``V1-1`` is undone, and KiCad agrees: the same chamfer forced gives a clearance
    violation that the board without it lacks."""
    design = bench(stub=False, lead=False, bus=False, intruder=True)
    board = _write(tmp_path, "tidy", design)
    code, env = tidy(monkeypatch, tmp_path, board, "--chamfer", "--dry-run")
    assert code == 0 and env["result"]["changed"] is False
    assert [found["code"] for found in env["issues"]] == ["tidy.chamfer-undone"]
    forced = apply_corners(design, find_corners(design, pads=board_pads(design))[0])
    assert _drc(_write(tmp_path, "forced", forced))["clearance"] > _drc(board)["clearance"]


def test_a_straightened_staircase_adds_no_drc_finding(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """The staircase of eight steps becomes one 45° corner, and KiCad finds nothing new."""
    board = _write(tmp_path, "tidy", staircase())
    before = _drc(board)
    code, env = tidy(monkeypatch, tmp_path, board, "--straighten", "--confirm")
    assert code == 0, env
    assert env["evidence"]["level"] == "KICAD-VERIFIED" and env["result"]["counts"] == {
        "straighten.fewer-turns": 1
    }
    after = _drc(board)
    assert all(after[kind] <= before[kind] for kind in after), (before, after)


def test_cut_zone_corners_add_no_drc_finding(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """An unfilled zone of ``SIG`` with its four corners cut is read by KiCad, which finds nothing new."""
    design = bench(lead=False, bus=False)
    assert design.board is not None
    zone = _zone(1, design.circuit.nets[0].id, _box(40, 30, 50, 38), fill=False)
    design = dataclasses.replace(design, board=dataclasses.replace(design.board, zones=(zone,)))
    board = _write(tmp_path, "tidy", design)
    before = _drc(board)
    code, env = tidy(monkeypatch, tmp_path, board, "--chamfer", "--zones", "--confirm")
    assert code == 0, env
    assert env["result"]["counts"]["chamfer.zone-corner"] == 4
    after = _drc(board)
    assert all(after[kind] <= before[kind] for kind in after), (before, after)
