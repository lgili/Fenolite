# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""``fenolite place --strategy regions`` (change c0205; capability cli-contract, "Region strategy in the place
command"), on the bench of ``tests/_regionbench.py`` written as a KiCad board. Hermetic: no tool runs."""

from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Any

import pytest
from _checkcli import run
from _projects import tree_snapshot
from _regionbench import MM, bench_text

from fenolite.backends.kicad.pcb import read_board
from fenolite.backends.kicad.replace import footprint_ref
from fenolite.core.coords import Point


@pytest.fixture(autouse=True)
def no_subprocess(monkeypatch: pytest.MonkeyPatch) -> None:
    def refuse(*args: object, **kwargs: object) -> None:
        raise AssertionError("a subprocess was started")

    monkeypatch.setattr(subprocess, "run", refuse)
    monkeypatch.setattr(subprocess, "Popen", refuse)


def place(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, *args: str
) -> tuple[int, dict[str, Any], dict[str, Any], Path]:
    board = tmp_path / "regions.kicad_pcb"
    if not board.exists():
        board.write_text(bench_text(), encoding="utf-8", newline="\n")
    code, env, err, _ = run(monkeypatch, tmp_path, "place", str(board), "--strategy", "regions", *args)
    return code, env, err, board


def positions(board: Path) -> dict[str, Point]:
    design = read_board(board)
    assert design.board is not None
    return {footprint_ref(design, fp): fp.position for fp in design.board.footprints}


def codes(env: dict[str, Any]) -> list[str]:
    return [found["code"] for found in env["issues"]]


def test_domains_from_islands_and_a_barrier_on_the_boundary(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Scenario "Bands by isolation islands": two bands, U5 across their boundary, H1 unassigned."""
    code, env, err, board = place(monkeypatch, tmp_path, "--barrier", "U5", "--confirm")
    assert code == 0, (env.get("issues"), err)
    regions = env["result"]["regions"]
    assert (regions["source"], regions["axis"]) == ("islands", "x")
    d1, d2 = regions["rows"]
    assert (d1["name"], d1["nets"], d1["parts"]) == ("D1", ["A1", "A2", "A3"], ["R1", "R3"])
    assert (d2["name"], d2["nets"], d2["parts"]) == ("D2", ["B1", "B2", "B3"], ["R2", "R4"])
    assert d1["box"] == {"x0": 0, "y0": 0, "x1": 30 * MM, "y1": 40 * MM}
    assert d2["box"] == {"x0": 30 * MM, "y0": 0, "x1": 60 * MM, "y1": 40 * MM}
    assert (d1["placed"], d2["placed"], d1["unplaced"]) == (["R1", "R3"], ["R2", "R4"], [])
    assert d1["used"] == 8 * MM * MM and d1["fill_permille"] == 6
    assert regions["barriers"] == [{"ref": "U5", "sides": ["D1", "D2"], "status": "boundary"}]
    assert regions["unassigned"] == ["H1"] and regions["crossings"] == []
    assert codes(env) == ["place.region-unassigned"] and env["result"]["unplaced"] == ["H1"]
    after = positions(board)
    assert after["U5"].x == 30 * MM  # centred on the boundary: its pads at 28.5 mm and 31.5 mm
    assert all(after[ref].x < 30 * MM for ref in ("R1", "R3"))
    assert all(after[ref].x > 30 * MM for ref in ("R2", "R4"))
    assert env["evidence"]["level"] == "INFERRED"
    assert {"H-G-REGION-PLACE", "H-G-TIES"} <= set(env["evidence"]["hypotheses"])
    assert [row["path"] for row in env["receipt"]["written"]] == ["regions.kicad_pcb"]


def test_dry_run_is_deterministic_and_writes_nothing(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    _, first, _, _ = place(monkeypatch, tmp_path, "--barrier", "U5", "--dry-run")
    snapshot = tree_snapshot(tmp_path)
    code, second, _, _ = place(monkeypatch, tmp_path, "--barrier", "U5", "--dry-run")
    assert code == 0 and tree_snapshot(tmp_path) == snapshot
    assert first["result"]["plan"] == second["result"]["plan"]
    assert first["result"]["moved"] == second["result"]["moved"]


def test_groups_and_crossings(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Scenario "Crossings between groups": R1 and R3 share A2 but sit in two groups."""
    groups = ("--group", "a=R1,R2", "--group", "b=R3,R4")
    code, env, err, _ = place(monkeypatch, tmp_path, *groups, "--split", "y", "--dry-run")
    assert code == 0, err
    regions = env["result"]["regions"]
    assert regions["source"] == "groups" and regions["axis"] == "y"
    assert regions["crossings"] == [{"between": ["a", "b"], "open": 2, "nets": ["A2", "B2"]}]
    crossing = [found for found in env["issues"] if found["code"] == "place.region-crossing"]
    assert [(found["where"], found["severity"]) for found in crossing] == [("a|b", "warning")]
    assert regions["unassigned"] == ["H1", "U5"]


def test_explicit_region_without_room(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Scenario "A region too small": every part stays staged with place.no-room, nothing is planned."""
    region = ("--group", "a=R*", "--region", "a=0mm,0mm,5mm,5mm")
    code, env, _, board = place(monkeypatch, tmp_path, *region, "--dry-run")
    assert code == 0 and not env["result"].get("plan") and env["result"]["moved"] == []
    assert codes(env).count("place.no-room") == 4
    (row,) = env["result"]["regions"]["rows"]
    assert row["box"] == {"x0": 0, "y0": 0, "x1": 5 * MM, "y1": 5 * MM}
    assert row["unplaced"] == ["R1", "R2", "R3", "R4"] and row["fill_permille"] == 0
    assert positions(board)["R1"].y == 60 * MM


def test_barrier_with_pins_in_one_group(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    groups = ("--group", "a=R1,R2", "--group", "b=R3,R4")
    code, env, _, _ = place(monkeypatch, tmp_path, "--barrier", "U5", *groups, "--dry-run")
    assert code == 0
    barrier = [found for found in env["issues"] if found["code"] == "place.region-barrier"]
    assert [found["where"] for found in barrier] == ["U5"]
    first = env["result"]["regions"]["rows"][0]
    assert first["name"] == "a" and "U5" in first["placed"]
    assert env["result"]["regions"]["barriers"] == []


@pytest.mark.parametrize(
    "args",
    [
        ("--group", "a=R1", "--region", "b=0mm,0mm,5mm,5mm"),
        ("--region", "a=0mm,0mm,5mm,5mm"),
        ("--group", "a=R1", "--region", "a=0mm,0mm,5mm"),
        ("--group", "a=R1", "--region", "a=5mm,0mm,1mm,5mm"),
        ("--group", "a=R1", "--region", "a=0mm,0mm,5mm,5mm", "--split", "x"),
        ("--group", "a=R1", "--group", "a=R2"),
        ("--group", "a"),
    ],
)
def test_usage_errors(monkeypatch: pytest.MonkeyPatch, tmp_path: Path, args: tuple[str, ...]) -> None:
    code, _, err, _ = place(monkeypatch, tmp_path, *args, "--dry-run")
    assert code == 2 and err["code"] == "FEN-2001"


def test_region_options_need_the_strategy(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    board = tmp_path / "regions.kicad_pcb"
    board.write_text(bench_text(), encoding="utf-8", newline="\n")
    code, _, err, _ = run(monkeypatch, tmp_path, "place", str(board), "--barrier", "U5", "--dry-run")
    assert code == 2 and err["code"] == "FEN-2001"
