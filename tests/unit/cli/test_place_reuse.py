# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""``fenolite place --strategy reuse`` (change c0210; capability layout-reuse, "Reuse strategy of place"),
on the authored boards of ``tests/_reusebench.py`` written as KiCad files with their library. Hermetic:
``--drc`` runs against a fake tool."""

from __future__ import annotations

import subprocess
from math import isqrt
from pathlib import Path
from typing import Any

import pytest
from _checkcli import hide_kicad, run
from _projects import tree_snapshot
from _reusebench import WIDE, project_files, reference, target, with_zones
from _ties import MM

from fenolite.backends.base import DrcReport, DrcViolation
from fenolite.backends.kicad.cli import CliRun, DrcRun
from fenolite.backends.kicad.frame import board_pads
from fenolite.backends.kicad.pcb import read_board, write_board
from fenolite.cli import place_reuse
from fenolite.cli.errors import CliError
from fenolite.model.design import Design

BLOCK = "U1,R1,R2,R3,R4"


@pytest.fixture(autouse=True)
def isolated(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("KICAD_CONFIG_HOME", str(tmp_path / "kicad-config"))
    for name in ("KICAD10_FOOTPRINT_DIR", "KICAD9_FOOTPRINT_DIR"):
        monkeypatch.delenv(name, raising=False)

    def refuse(*args: object, **kwargs: object) -> None:
        raise AssertionError("a subprocess was started")

    monkeypatch.setattr(subprocess, "run", refuse)
    monkeypatch.setattr(subprocess, "Popen", refuse)


def _project(tmp_path: Path, design: Design | None = None, *, library: bool = True) -> Path:
    """The target project and ``reference.kicad_pcb`` in ``tmp_path``."""
    files = {
        **project_files(design if design is not None else target()),
        "reference.kicad_pcb": write_board(reference(), target=10).text,
    }
    for name, text in files.items():
        if not library and (name == "fp-lib-table" or name.startswith("Reuse.pretty")):
            continue
        path = tmp_path / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8", newline="\n")
    return tmp_path / "target.kicad_pcb"


def reuse(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, *args: str, design: Design | None = None
) -> tuple[int, dict[str, Any], dict[str, Any]]:
    board = _project(tmp_path, design)
    code, env, err, _ = run(
        monkeypatch, tmp_path, "place", board.name, "--from", "reference.kicad_pcb", *args
    )
    return code, env, err


def codes(env: dict[str, Any]) -> list[str]:
    return [found["code"] for found in env["issues"]]


def test_dry_run_of_a_block(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Scenario "Dry run of a block": exit 0, the plan names the target board, and nothing is written."""
    _project(tmp_path)
    snapshot = tree_snapshot(tmp_path)
    code, env, _, _ = run(
        monkeypatch,
        tmp_path,
        "place",
        "target.kicad_pcb",
        "--from",
        "reference.kicad_pcb",
        "--only",
        "U1,R1,R2",
        "--copper",
        "--dry-run",
    )
    assert code == 0, env["issues"]
    assert [entry["path"] for entry in env["result"]["plan"]] == ["target.kicad_pcb"]
    assert tree_snapshot(tmp_path) == snapshot
    result = env["result"]["reuse"]
    assert result["anchor"] == "U1" and [row["ref"] for row in env["result"]["moved"]] == ["R1", "R2"]
    assert env["result"]["strategy"] == "reuse"
    assert result["transform"] == {"rotation": 90_000_000, "mirror": False, "x": 22 * MM, "y": 38 * MM}
    assert result["copper"]["copied"] == 2 and result["copper"]["counts"] == {"free-end": 1}
    assert env["schema"] == "fenolite.place.v0" and env["evidence"]["level"] == "INFERRED"
    assert "H-G-REUSE-FIT" in env["evidence"]["hypotheses"]


def test_confirm_writes_the_block(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """The written board holds every pad of the block on its goal and the copied tracks, locked."""
    code, env, _ = reuse(monkeypatch, tmp_path, "--only", BLOCK, "--copper", "--confirm")
    assert code == 0, env["issues"]
    assert codes(env) == ["reuse.copper-dropped", "reuse.copper-dropped"]
    written = read_board(tmp_path / "target.kicad_pcb")
    assert written.board is not None
    rows = {row["ref"]: row for row in env["result"]["reuse"]["parts"]}
    assert rows["R4"]["to"] == {"x": 42 * MM, "y": 24 * MM, "rotation": 180_000_000, "side": "bottom"}
    assert all(row["matched"] == row["within"] and row["residual"] == 0 for row in rows.values())
    copied = {item["uuid"] for item in env["result"]["reuse"]["copper"]["items"]}
    tracks = [track for track in written.board.tracks if track.native_ids["kicad"] in copied]
    assert len(tracks) == 2 and all(track.locked for track in tracks)
    pads = {(record.ref, record.number): record.position for record in board_pads(written)}
    assert {tracks[0].start, tracks[0].end} == {pads[("U1", "1")], pads[("R1", "1")]}
    assert pads[("R4", "1")].y == 24 * MM and pads[("R4", "1")].x in (41 * MM, 43 * MM)
    # a second run finds every part where the block wants it and moves nothing
    code, env, _, _ = run(
        monkeypatch, tmp_path, "place", "target.kicad_pcb", "--from", "reference.kicad_pcb", "--only", BLOCK,
        "--dry-run",
    )  # fmt: skip
    assert code == 0 and env["result"]["moved"] == [] and "plan" not in env["result"]


def test_confirm_writes_the_zone_of_the_block(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """With ``--copper`` the pour of the block is written, locked, with its fill; the strip that reaches
    ``TP1`` is dropped as ``zone-beyond-block``, and the fills are reported stale."""
    _project(tmp_path)
    (tmp_path / "reference.kicad_pcb").write_text(
        write_board(with_zones(reference()), target=10).text, encoding="utf-8", newline="\n"
    )
    code, env, _, _ = run(
        monkeypatch, tmp_path, "place", "target.kicad_pcb", "--from", "reference.kicad_pcb", "--only", BLOCK,
        "--copper", "--confirm",
    )  # fmt: skip
    assert code == 0, env["issues"]
    assert "reuse.fill-stale" in codes(env)
    copper = env["result"]["reuse"]["copper"]
    assert [item["kind"] for item in copper["items"]] == ["track", "track", "zone"]
    assert copper["counts"]["zone-beyond-block"] == 1
    written = read_board(tmp_path / "target.kicad_pcb")
    assert written.board is not None
    (zone,) = written.board.zones
    assert zone.locked and zone.layers == ("F.Cu",) and len(zone.fills) == 1 and len(zone.outline) == 6


def test_a_part_without_a_fit_writes_nothing(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    code, env, err = reuse(monkeypatch, tmp_path, "--only", BLOCK, "--dry-run", design=target(r3=WIDE))
    assert code == 5 and err["code"] == "FEN-5001" and "plan" not in env["result"]
    assert codes(env) == ["reuse.no-fit"] and env["issues"][0]["where"] == "R3"
    r3 = next(row for row in env["result"]["reuse"]["parts"] if row["ref"] == "R3")
    assert (r3["placed"], r3["to"], r3["within"], r3["residual"]) == (False, None, 0, MM // 2)


def test_a_locked_anchor_stays(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    code, env, _ = reuse(
        monkeypatch, tmp_path, "--only", BLOCK, "--dry-run", design=target(locked_anchor=True)
    )
    assert code == 0, env["issues"]
    assert [row["ref"] for row in env["result"]["moved"]] == ["R1", "R2", "R3", "R4"]


def test_a_turn_needs_the_library(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    _project(tmp_path, library=False)
    code, env, _, _ = run(
        monkeypatch, tmp_path, "place", "target.kicad_pcb", "--from", "reference.kicad_pcb", "--only", BLOCK,
        "--dry-run",
    )  # fmt: skip
    assert code == 5 and set(codes(env)) == {"place.no-definition"}
    assert sorted(found["where"] for found in env["issues"]) == ["R1", "R2", "R3", "R4"]


def test_placement_onto_copper_is_refused(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """``X1`` of another net lies where the copied ``in`` runs and next to ``R1``'s place: the copy of
    ``in`` is left out, and the courtyards that overlap refuse the write."""
    code, env, _ = reuse(
        monkeypatch, tmp_path, "--only", BLOCK, "--copper", "--dry-run", design=target(intruder=True)
    )
    assert code == 5 and "plan" not in env["result"]
    assert "place.courtyard-overlap" in codes(env)
    dropped = {row["reason"] for row in env["result"]["reuse"]["copper"]["dropped"]}
    assert dropped & {"copper.short", "copper.clearance"}


def test_a_part_moved_onto_copper(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """A track of another net under the place of ``R1-1``: the moved part shorts it, so nothing is
    written."""
    code, env, _ = reuse(monkeypatch, tmp_path, "--only", BLOCK, "--dry-run", design=target(across=True))
    assert code == 5 and "plan" not in env["result"]
    (found,) = (found for found in env["issues"] if found["code"] == "reuse.check-failed")
    assert "copper.short" in found["message"] and env["result"]["reuse"]["copper_check"]["new"] == 1


def test_usage_errors(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    for args in (
        ("--only", BLOCK, "--anchor", "R9"),
        ("--only", "U1,U1"),
        ("--only", BLOCK, "--map", "R1"),
        ("--only", BLOCK, "--map", "R9=R1"),
        ("--only", BLOCK, "--tolerance", "0mm"),
        ("--only", BLOCK, "--tolerance", "5"),
        ("--only", BLOCK, "--force"),
        ("--only", BLOCK, "--strategy", "grid"),
        ("--move", "R1=10mm,10mm"),
        (),
    ):
        code, _, err = reuse(monkeypatch, tmp_path, *args, "--dry-run")
        assert code == 2 and err["code"] == "FEN-2001", args
    code, _, err, _ = run(monkeypatch, tmp_path, "place", "target.kicad_pcb", "--copper", "--dry-run")
    assert code == 2 and "--strategy reuse" in err["message"]


def test_parse_helpers() -> None:
    assert place_reuse.parse_parts(" U1, R1 ") == ["U1", "R1"]
    assert place_reuse.parse_map(["R11=R1", "U11 = U1"]) == {"R11": "R1", "U11": "U1"}
    with pytest.raises(CliError):
        place_reuse.parse_map(["R11=R1", "R11=R2"])
    with pytest.raises(CliError):
        place_reuse.parse_parts("U1,,R1")


class FakeTool:
    """A ``kicad-cli`` stand-in whose DRC reports ``counts[i]`` clearance violations on its ``i``-th run."""

    def __init__(self, counts: tuple[int, int]) -> None:
        self.counts = list(counts)
        self.boards: list[object] = []

    def version(self) -> str:
        return "10.0.7"

    def drc(self, board: Path, *, files: dict[str, object]) -> DrcRun:
        self.boards.append(files.get(board.name))
        count = self.counts.pop(0)
        report = DrcReport(
            "target.kicad_pcb",
            "",
            "10.0.7",
            "mm",
            violations=tuple(DrcViolation("clearance", "too close", "error") for _ in range(count)),
        )
        return DrcRun(CliRun("exit", 0, "", "", {}), report)


def test_drc_confirms(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    tool = FakeTool((1, 1))
    monkeypatch.setattr(place_reuse, "preflight", lambda *args, **kwargs: tool)
    code, env, _ = reuse(monkeypatch, tmp_path, "--only", BLOCK, "--copper", "--drc", "--dry-run")
    assert code == 0 and env["result"]["reuse"]["drc"] == {
        "tool_version": "10.0.7",
        "before": 1,
        "after": 1,
        "new": [],
    }
    assert "H-K-REUSE-DRC" in env["evidence"]["hypotheses"]
    assert tool.boards[0] is None and isinstance(tool.boards[1], bytes)


def test_drc_finds_something_new(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr(place_reuse, "preflight", lambda *args, **kwargs: FakeTool((0, 2)))
    code, env, err = reuse(monkeypatch, tmp_path, "--only", BLOCK, "--drc", "--dry-run")
    assert code == 5 and err["code"] == "FEN-5001" and "plan" not in env["result"]
    (found,) = (found for found in env["issues"] if found["code"] == "reuse.drc-new")
    assert found["where"] == "clearance"


def test_drc_without_the_tool(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    hide_kicad(monkeypatch, tmp_path)
    code, _, err = reuse(monkeypatch, tmp_path, "--only", BLOCK, "--drc", "--dry-run")
    assert code == 6 and err["code"] == "FEN-6001"


def test_pads_land_on_their_goals(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Every pad of the written block lies within 1 nm of where the reference puts it through the reported
    transform."""
    code, env, _ = reuse(monkeypatch, tmp_path, "--only", BLOCK, "--confirm")
    assert code == 0
    written = read_board(tmp_path / "target.kicad_pcb")
    source = {(record.ref, record.number): record.position for record in board_pads(reference())}
    found = {(record.ref, record.number): record.position for record in board_pads(written)}
    turn = env["result"]["reuse"]["transform"]
    assert turn["rotation"] == 90_000_000 and turn["mirror"] is False
    for (ref, number), at in found.items():
        if ref not in BLOCK.split(","):
            continue
        sx, sy = source[(ref, number)].x, source[(ref, number)].y
        goal = (sy + turn["x"], -sx + turn["y"])  # x' = y, y' = -x at 90°
        assert isqrt((at.x - goal[0]) ** 2 + (at.y - goal[1]) ** 2) <= 1, (ref, number)
