# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Review findings (capability board-viewer, "Review findings"; change c0193): authored items added to the
KiCad board of the test data, one per finding, and the findings that each adds."""

from __future__ import annotations

import dataclasses
import math
from pathlib import Path

from fenolite.backends import registry
from fenolite.backends.base import BoardFrame
from fenolite.core.coords import Point, Size
from fenolite.model.board import Graphic, Text, Track, Via
from fenolite.model.design import Design
from fenolite.view.findings import GROUPS, Review, review

ROOT = Path(__file__).resolve().parents[3]
BOARD = ROOT / "tests" / "data" / "kicad" / "board" / "two_layer.kicad_pcb"
MM = 1_000_000


def _id(prefix: str, n: int) -> str:
    return f"{prefix}_00000000-0000-0000-0000-{n:012x}"


def _read() -> tuple[Design, BoardFrame]:
    backend = registry.for_path(BOARD)
    assert isinstance(backend, BoardFrame)
    return backend.read(BOARD).design, backend


def _counts(found: Review) -> dict[str, int]:
    return {g["id"]: g["n"] for g in found.groups}


def _track(n: int, a: tuple[float, float], b: tuple[float, float]) -> Track:
    return Track(
        id=_id("trk", n),
        start=Point(round(a[0] * MM), round(a[1] * MM)),
        end=Point(round(b[0] * MM), round(b[1] * MM)),
        width=250_000,
        layer="F.Cu",
    )


def test_corners() -> None:
    """Scenario "Corners of authored tracks"."""
    design, frame = _read()
    board = design.board
    assert board is not None
    pad = next(p for p in frame.board_pads(design) if p.ref == "R1" and p.number == "1")
    px, py = pad.position.x / MM, pad.position.y / MM
    tracks = (
        _track(1, (5, 5), (10, 5)),
        _track(2, (10, 5), (10, 10)),  # 90°
        _track(3, (15, 5), (20, 5)),
        _track(4, (20, 5), (17, 8)),  # 135°: acute
        _track(5, (25, 5), (30, 5)),
        _track(6, (30, 5), (33, 8)),  # 45°: passes
        _track(7, (px - 3, py), (px, py)),
        _track(8, (px, py), (px, py + 3)),  # 90° inside the pad
        _track(9, (5, 20), (5 + 5 * math.cos(math.radians(30)), 20 - 5 * math.sin(math.radians(30)))),
    )
    edited = dataclasses.replace(design, board=dataclasses.replace(board, tracks=tracks))
    found = review(edited, frame)
    counts = _counts(found)
    assert counts["corner_90"] == 1 and counts["corner_acute"] == 1 and counts["corner_mid"] == 0
    angled = [item["label"] for item in found.items if item["group"] == "track_angle"]
    assert len(angled) == 1 and angled[0].startswith("track 9 ")
    assert [g["id"] for g in found.groups] == list(GROUPS)


def test_silk_and_outside() -> None:
    """Scenario "Silkscreen and copper outside the board"."""
    design, frame = _read()
    board = design.board
    assert board is not None
    before = _counts(review(design, frame, silk_gap=150_000))
    pad = next(p for p in frame.board_pads(design) if p.ref == "R1" and p.number == "1")
    over = Graphic(
        id=_id("gfx", 1),
        kind="line",
        layer="F.SilkS",
        points=(
            Point(pad.position.x - 300_000, pad.position.y),
            Point(pad.position.x + 300_000, pad.position.y),
        ),
        width=150_000,
    )
    outside = Graphic(
        id=_id("gfx", 2),
        kind="line",
        layer="F.SilkS",
        points=(Point(5 * MM, -5 * MM), Point(10 * MM, -5 * MM)),
        width=150_000,
    )
    texts = tuple(
        Text(
            id=_id("txt", k),
            text="AB",
            position=Point(40 * MM + k * 500_000, 25 * MM),
            layer="F.SilkS",
            size=Size(MM, MM),
            thickness=150_000,
        )
        for k in (1, 2)
    )
    via = Via(
        id=_id("via", 1),
        position=Point(60 * MM, 15 * MM),
        diameter=600_000,
        drill=300_000,
        layers=("F.Cu", "B.Cu"),
    )
    edited = dataclasses.replace(
        design,
        board=dataclasses.replace(
            board,
            graphics=(*board.graphics, over, outside),
            texts=(*board.texts, *texts),
            vias=(*board.vias, via),
        ),
    )
    after = _counts(review(edited, frame, silk_gap=150_000))
    added = {g: after[g] - before[g] for g in GROUPS}
    assert added["silk_mask"] == 1 and added["silk_silk"] == 1 and added["silk_edge"] == 1
    assert added["copper_out"] == 1
    assert set(after) == set(GROUPS)


def test_the_gap_comes_from_the_rule_or_the_option() -> None:
    design, frame = _read()
    notes = {g["id"]: g["note"] for g in review(design, frame).groups}
    assert "0.000 mm" in notes["silk_mask"]
    notes = {
        g["id"]: g["note"] for g in review(design, frame, silk_gap=150_000, mask_expansion=50_000).groups
    }
    assert "0.150 mm (--silk-gap)" in notes["silk_mask"] and "--mask-expansion" in notes["silk_mask"]
