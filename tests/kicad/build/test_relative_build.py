# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Placement in code read back through ``kicad-cli`` (change c0255; capability placement-in-code, "Recorded
resolutions", scenario "Read back what was resolved"; ``H-G-REL-RESOLVE``): the examples of
``examples/relative/`` are built for the target of the job, KiCad reads each board and writes its position
file (``pcb export pos``, positions to the nanometre), and every footprint lies at the ``at`` of its record,
every relation holding within 1 nm on the read-back positions. On KiCad 10 the board KiCad saves again
(``pcb upgrade``) keeps the copied copper of the block reuse."""

from __future__ import annotations

import csv
import io
import json
import shutil
from pathlib import Path
from typing import Any

import pytest
from _probes import major, runner

import fenolite.cli.main as cli_main
from fenolite.backends.kicad.embed import footprint_extent
from fenolite.backends.kicad.pcb import read_board
from fenolite.catalog import get_footprint
from fenolite.core.coords import Point
from fenolite.dsl.convert import BOARD_ORIGIN
from fenolite.geometry.shapes import BBox
from fenolite.geometry.transform import Transform
from fenolite.model.board import FootprintInstance

pytestmark = pytest.mark.needs_kicad
EXAMPLE = Path(__file__).resolve().parents[3] / "examples" / "relative"
MM = 1_000_000


def _build(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, script: str, name: str
) -> tuple[dict[str, Any], bytes]:
    monkeypatch.setenv("KICAD_CONFIG_HOME", str(tmp_path / "kicad-config"))
    for variable in (
        "KICAD10_FOOTPRINT_DIR",
        "KICAD10_SYMBOL_DIR",
        "KICAD9_FOOTPRINT_DIR",
        "KICAD9_SYMBOL_DIR",
    ):
        monkeypatch.delenv(variable, raising=False)
    folder = tmp_path / "ex"
    folder.mkdir()
    for path in EXAMPLE.iterdir():
        if path.is_file():
            shutil.copy(path, folder / path.name)
    out = tmp_path / "out"
    stdout, stderr = io.StringIO(), io.StringIO()
    with monkeypatch.context() as patch:
        patch.setattr("sys.stdout", stdout)
        patch.setattr("sys.stderr", stderr)
        args = ["--kicad-version", str(major()), "build", str(folder / script), "--out", str(out)]
        code = cli_main.main([*args, "--confirm", "--json"])
    assert code == 0, stderr.getvalue()
    return json.loads(stdout.getvalue()), (out / f"{name}.kicad_pcb").read_bytes()


def _read_back(board: bytes) -> dict[str, tuple[Point, int, str]]:
    """Reference → position, rotation and side as KiCad reads the board (its position file, Y up)."""
    args = ["pcb", "export", "pos", "--format", "csv", "--units", "mm", "--side", "both", "-o", "pos.csv"]
    run = runner().run([*args, "board.kicad_pcb"], files={"board.kicad_pcb": board})
    assert run.ok, run.stderr
    rows = csv.DictReader(io.StringIO(run.outputs["pos.csv"].decode("utf-8")))
    return {
        row["Ref"]: (
            Point(round(float(row["PosX"]) * MM), -round(float(row["PosY"]) * MM)),
            round(float(row["Rot"]) * 1_000_000) % 360_000_000,
            row["Side"],
        )
        for row in rows
    }


def _placed(board: bytes) -> dict[str, tuple[FootprintInstance, tuple[Point, int, str]]]:
    """Component path → the written footprint and its placement as KiCad read it."""
    design = read_board(board.decode("utf-8"))
    assert design.board is not None
    paths = {c.id: (c.properties.get("fenolite.path", c.ref), c.ref) for c in design.circuit.components}
    kicad = _read_back(board)
    return {
        paths[fp.component_id][0]: (fp, kicad[paths[fp.component_id][1]]) for fp in design.board.footprints
    }


def _box(entry: tuple[FootprintInstance, tuple[Point, int, str]]) -> BBox:
    fp, (at, rotation, side) = entry
    turn = Transform.placement(at, rotation, side == "bottom")
    return turn.apply_bbox(footprint_extent(get_footprint(fp.lib_ref)))


def _records_hold(
    env: dict[str, Any], placed: dict[str, tuple[FootprintInstance, tuple[Point, int, str]]]
) -> None:
    for record in env["result"]["placement"]["relative"]:
        entry = placed.get(record["path"])
        if entry is None:  # a block pose: its parts are checked through their own placements
            continue
        at = Point(BOARD_ORIGIN.x + record["at"][0], BOARD_ORIGIN.y + record["at"][1])
        assert entry[1] == (at, record["rotation"], record["side"]), record


def test_pads_read_back(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    env, board = _build(tmp_path, monkeypatch, "pads.py", "relative_pads")
    placed = _placed(board)
    _records_hold(env, placed)
    u1, c2, r1, d1, j1 = (_box(placed[k]) for k in ("U1", "C2", "R1", "D1", "J1"))
    assert abs(c2.x0 - (u1.x1 + MM)) <= 1 and abs((c2.y0 + c2.y1) // 2 - (u1.y0 + u1.y1) // 2) <= 1
    assert abs(r1.y0 - (c2.y1 + MM)) <= 1 and abs(r1.x0 - c2.x0) <= 1
    assert abs(d1.x0 - (r1.x1 + MM // 2)) <= 1
    assert abs(j1.x0 - (BOARD_ORIGIN.x + 2 * MM)) <= 1


def test_blocks_read_back(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    env, board = _build(tmp_path, monkeypatch, "blocks.py", "relative_blocks")
    placed = _placed(board)
    _records_hold(env, placed)
    boxes = {path: _box(entry) for path, entry in placed.items()}

    def union(prefix: str) -> BBox:
        found = [box for path, box in boxes.items() if path.startswith(prefix)]
        box = found[0]
        for other in found[1:]:
            box = box.union(other)
        return box

    ch0, ch1, ch2 = union("ch0/"), union("ch1/"), union("ch2/")
    assert abs(ch1.y0 - (ch0.y1 + 3 * MM)) <= 1 and abs(ch1.x0 - ch0.x0) <= 1
    assert abs(ch2.x0 - (ch0.x1 + 6 * MM)) <= 1 and abs(ch2.y0 - ch0.y0) <= 1


@pytest.mark.kicad_min_major(10)
def test_reused_copper_survives_a_kicad_save(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _env, board = _build(tmp_path, monkeypatch, "blocks.py", "relative_blocks")
    saved = runner().run(["pcb", "upgrade", "--force", "board.kicad_pcb"], files={"board.kicad_pcb": board})
    assert saved.ok, saved.stderr
    design = read_board(saved.outputs.get("board.kicad_pcb", board).decode("utf-8"))
    assert design.board is not None and len(design.board.tracks) == 6
    assert all(track.locked for track in design.board.tracks)
