# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""``fenolite silk --designators`` on dense boards (change c0493): rings of places, height steps, the two
clearance models, the unplaced kinds and the clip rows. Authored benches, ink estimated, no subprocess.

``SMALL`` is a two-pad part of 0402 size whose courtyard hugs its pads: ``dense`` puts two rows of eight at a
pitch of 1.2 mm along x and 0.64 mm along y, so the courtyards touch and the ring at ``--gap`` comes within
0.15 mm of the part's own pads. Before this change no designator of that grid was placed (every cheapest
place met a neighbour's courtyard)."""

from __future__ import annotations

import dataclasses
import io
import json
import subprocess
import time
from pathlib import Path
from typing import Any

import pytest
from _silkbench import BOXED, CHIP, SilkBoard, clipped, dense
from _ties import MM

from fenolite.backends.kicad.pcb import write_board
from fenolite.backends.kicad.pro import synthesize_project
from fenolite.cli import main as cli_main
from fenolite.core.coords import Point
from fenolite.dsl import Footprint, mm
from fenolite.model.board import Graphic
from fenolite.model.design import Design
from fenolite.silk.board import field_rect, kind_of
from fenolite.silk.extents import TextKey, estimate
from fenolite.silk.layout import Rect, gap_floor

DEG = 1_000_000


@pytest.fixture(autouse=True)
def no_subprocess(monkeypatch: pytest.MonkeyPatch) -> None:
    def refuse(*args: object, **kwargs: object) -> None:
        raise AssertionError("a subprocess was started")

    monkeypatch.setattr(subprocess, "run", refuse)
    monkeypatch.setattr(subprocess, "Popen", refuse)


def _write(folder: Path, design: Design) -> Path:
    folder.mkdir(parents=True, exist_ok=True)
    board = folder / "silk.kicad_pcb"
    board.write_text(write_board(design, target=10).text, encoding="utf-8", newline="\n")
    project = synthesize_project(design, target=10, board_name="silk")
    board.with_suffix(".kicad_pro").write_text(project, encoding="utf-8", newline="\n")
    return board


def silk(
    monkeypatch: pytest.MonkeyPatch, folder: Path, design: Design, *args: str
) -> tuple[int, dict[str, Any]]:
    _write(folder, design)
    monkeypatch.chdir(folder)
    out = io.StringIO()
    monkeypatch.setattr("sys.stdout", out)
    monkeypatch.setattr("sys.stderr", io.StringIO())
    code = cli_main.main(["silk", "silk.kicad_pcb", "--measure", "estimate", "--dry-run", "--json", *args])
    return code, json.loads(out.getvalue() or "{}")


def _rect(row: dict[str, Any]) -> Rect:
    """The ink rectangle of a placed row, centred, as the search wrote it."""
    box = estimate(TextKey(row["ref"], row["height"], row["height"], row["stroke"]))
    assert box is not None
    return field_rect(box, row["angle"] * DEG, row["side"] == "bottom").moved(row["x"], row["y"])


def _boxes(design: Design) -> dict[str, Rect]:
    assert design.board is not None
    refs = {c.id: c.ref for c in design.circuit.components}
    found: dict[str, Rect] = {}
    for fp in design.board.footprints:
        pads = [(p.position.x, p.position.y) for p in fp.pads]
        found[refs[fp.component_id]] = Rect(
            min(x for x, _ in pads), min(y for _, y in pads), max(x for x, _ in pads), max(y for _, y in pads)
        )
    return found


@pytest.mark.parametrize("model", ["kicad", "altium"])
def test_a_dense_grid_of_small_parts(monkeypatch: pytest.MonkeyPatch, tmp_path: Path, model: str) -> None:
    """Scenario "A dense grid of small parts": every designator is placed, nearer to its own part than to
    any other, the same way twice."""
    design = dense()
    start = time.perf_counter()
    code, reply = silk(monkeypatch, tmp_path / "a", design, "--designators", "--model", model)
    elapsed = time.perf_counter() - start
    assert code == 0, reply
    result = reply["result"]
    assert result["placed"] == 16 and result["unplaced"] == {}
    assert result["settings"]["model"] == model
    assert elapsed < 30, elapsed  # task 1.4: the dense bench stays within the silk tests' budget
    boxes = _boxes(design)
    for row in result["placements"]:
        rect = _rect(row)
        own = gap_floor(rect, boxes[row["ref"]])
        assert all(own <= gap_floor(rect, box) for ref, box in boxes.items() if ref != row["ref"]), row
    _, again = silk(monkeypatch, tmp_path / "b", design, "--designators", "--model", model)
    assert again["result"]["placements"] == result["placements"]
    if model == "altium":
        assert "H-A-SILK-DRC-MODEL" in reply["evidence"]["hypotheses"]


def test_rings_and_height_steps(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """With one ring (``--reach 0mm``) and no smaller height the grid is not placed; the reply counts the
    unplaced parts by the kind of their blocker, and a height below the board's least exits 2."""
    code, reply = silk(
        monkeypatch,
        tmp_path,
        dense(),
        "--designators",
        "--reach",
        "0mm",
        "--min-size",
        "1mm",
        "--angles",
        "0",
    )
    assert code == 0
    unplaced = reply["result"]["unplaced"]
    assert sum(unplaced.values()) == 16 - reply["result"]["placed"] > 0
    assert set(unplaced) <= {"pad", "mask", "hole", "silk", "text", "courtyard", "edge", "outside"}
    issues = [i for i in reply["issues"] if i["code"] == "silk.no-place"]
    assert len(issues) == sum(unplaced.values())
    code, _ = silk(monkeypatch, tmp_path / "low", dense(), "--designators", "--min-size", "0.1mm")
    assert code == 2


def _surround(design: Design, centre: Point, half_x: int, half_y: int) -> Design:
    """``design`` with a board silkscreen rectangle of 0.1 mm around ``centre``."""
    assert design.board is not None
    x0, y0, x1, y1 = centre.x - half_x, centre.y - half_y, centre.x + half_x, centre.y + half_y
    ring = Graphic(
        id="gfx_c0493_ring",
        kind="rect",
        layer="F.SilkS",
        points=(Point(x0, y0), Point(x1, y1)),
        width=100_000,
    )
    return dataclasses.replace(design, board=dataclasses.replace(design.board, graphics=(ring,)))


def _outlined() -> Any:
    footprint = Footprint("Silk", "OUTLINED", kind="smd")
    footprint.pad("1", at=(mm(-2.5), mm(0)), size=(mm(0.6), mm(0.6)))
    footprint.pad("2", at=(mm(2.5), mm(0)), size=(mm(0.6), mm(0.6)))
    footprint.rect((mm(-3), mm(-1)), (mm(3), mm(1)), layer="F.CrtYd", width=mm(0.05))
    footprint.rect((mm(-2), mm(-0.3)), (mm(2), mm(0.3)), layer="F.SilkS", width=mm(0.1))
    return footprint.definition


def test_a_text_over_its_own_outline(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Scenario "A text over its own outline": hemmed in by a board stroke, the designator fits only over
    the part, across its own outline: placed with ``--model altium``, unplaced with ``--model kicad``."""
    board = SilkBoard()
    centre = Point(20 * MM, 15 * MM)
    board.place("U1", centre, defn=_outlined())
    design = _surround(board.build(), centre, 3_200_000, 1_200_000)
    args = ("--designators", "--reach", "0mm", "--over-body", "--angles", "0")
    code, reply = silk(monkeypatch, tmp_path / "altium", design, *args, "--model", "altium")
    assert code == 0
    (row,) = reply["result"]["placements"]
    assert row["status"] == "placed" and row["where"] == "over"
    code, reply = silk(monkeypatch, tmp_path / "kicad", design, *args, "--model", "kicad")
    (row,) = reply["result"]["placements"]
    assert row["status"] == "unplaced" or row["where"] != "over"


def test_each_pads_own_mask_expansion(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Scenario "Each pad's own mask expansion": no placed text comes within the mask clearance of either
    pad's own opening (0.05 mm and 0.2 mm)."""
    definition = CHIP
    pads = (
        dataclasses.replace(definition.pads[0], mask_margin=50_000),
        dataclasses.replace(definition.pads[1], mask_margin=200_000),
    )
    board = SilkBoard()
    centre = Point(20 * MM, 15 * MM)
    board.place("R1", centre, defn=dataclasses.replace(definition, pads=pads))
    code, reply = silk(
        monkeypatch, tmp_path, board.build(), "--designators", "--model", "altium", "--gap", "0mm"
    )
    assert code == 0
    (row,) = reply["result"]["placements"]
    assert row["status"] == "placed"
    rect = _rect(row)
    half = row["stroke"] // 2
    shown = Rect(rect.x0 + half, rect.y0 + half, rect.x1 - half, rect.y1 - half)
    for x, grow in ((-800_000, 50_000), (800_000, 200_000)):  # CHIP's pads: 0.9 mm x 1 mm at x = -+0.8 mm
        opening = Rect(
            centre.x + x - 450_000 - grow,
            centre.y - 500_000 - grow,
            centre.x + x + 450_000 + grow,
            centre.y + 500_000 + grow,
        )
        assert gap_floor(shown, opening) >= 100_000 - 1, (x, row)


def _bar() -> Any:
    footprint = Footprint("Silk", "BAR", kind="smd")
    footprint.pad("1", at=(mm(0), mm(0)), size=(mm(8), mm(1.2)))
    footprint.rect((mm(-4.1), mm(-0.7)), (mm(4.1), mm(0.7)), layer="F.CrtYd", width=mm(0.05))
    return footprint.definition


def test_a_part_with_no_room(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Scenario "A part with no room": enclosed by other parts' pads, the part gets one ``silk.no-place``
    of kind ``pad``."""
    board = SilkBoard()
    centre = Point(20 * MM, 15 * MM)
    board.place("R1", centre, defn=CHIP)
    for n, (dx, dy, turn) in enumerate(
        ((0, -1_800_000, 0), (0, 1_800_000, 0), (-2_300_000, 0, 90), (2_300_000, 0, 90))
    ):
        board.place(f"B{n + 1}", Point(centre.x + dx, centre.y + dy), rotation=turn, defn=_bar())
    code, reply = silk(
        monkeypatch, tmp_path, board.build(), "--designators", "--refs", "R1", "--reach", "0mm"
    )
    assert code == 0
    assert reply["result"]["unplaced"] == {"pad": 1}
    (found,) = [i for i in reply["issues"] if i["code"] == "silk.no-place"]
    assert found["where"] == "R1" and "(pad)" in found["message"]
    assert kind_of("pad B1-1") == "pad" and kind_of("the board edge") == "outside"


def test_clip_then_place(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Scenario "Clip then place": the clip runs first and lists one row per cut footprint; the search sees
    the cut outline and places every designator."""
    design = clipped(("top",))
    code, reply = silk(monkeypatch, tmp_path, design, "--designators", "--clip")
    assert code == 0, reply
    rows = reply["result"]["clip"]["footprints"]
    assert {row["ref"] for row in rows} >= {"U1", "U2", "U3", "U4"}
    assert all(row["strokes_cut"] >= 1 and row["pieces"] >= 0 for row in rows)
    assert reply["result"]["unplaced"] == {} and reply["result"]["placed"] == len(
        reply["result"]["placements"]
    )
    assert BOXED.lib_id.endswith("BOXED")
