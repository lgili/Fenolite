# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The difference overlay of two revisions (capability visual-diff, change c0184)."""

from __future__ import annotations

import dataclasses
from pathlib import Path
from typing import Any

import pytest

from fenolite.backends import registry
from fenolite.cli.cmd_view import scene_of
from fenolite.core.coords import Point
from fenolite.model.design import Design
from fenolite.view.compare import compare, summary
from fenolite.view.scene import build_scene

ROOT = Path(__file__).resolve().parents[3]
BOARD = ROOT / "tests" / "data" / "kicad" / "board" / "two_layer.kicad_pcb"
SHEET = ROOT / "tests" / "data" / "altium" / "blink" / "blink.SchDoc"


def _scenes() -> tuple[dict[str, Any], dict[str, Any]]:
    backend: Any = registry.for_path(BOARD)
    design = backend.read(BOARD).content
    assert isinstance(design, Design) and design.board is not None
    old = build_scene(design, backend, name="old", backend="kicad")
    first, *rest = design.board.footprints
    moved = dataclasses.replace(first, position=Point(first.position.x + 1_000_000, first.position.y))
    track = dataclasses.replace(
        design.board.tracks[0],
        id="trk-new",
        start=Point(1_000_000, 1_000_000),
        end=Point(3_000_000, 1_000_000),
    )
    board = dataclasses.replace(design.board, footprints=(moved, *rest), tracks=(*design.board.tracks, track))
    new = build_scene(dataclasses.replace(design, board=board), backend, name="new", backend="kicad")
    return new, old


def test_board() -> None:
    """Scenario "A moved part and a new track"."""
    new, old = _scenes()
    diff = compare(new, old)
    assert diff["counts"] == {"added": 1, "removed": 0, "moved": 1, "changed": 0, "zone": 0}
    (move,) = diff["moved"]
    assert move["um"] == 1000 and move["deg"] == 0 and not move["flipped"]
    (added,) = diff["added"]
    assert added[1] == "s" and added[2][:4] == [1000, 1000, 3000, 1000]
    assert summary(diff)["changes"][0].endswith("moved 1.000 mm")


def test_same_board_has_no_change() -> None:
    scene = scene_of(BOARD)
    assert compare(scene, scene_of(BOARD))["changes"] == []


def test_sheet() -> None:
    scene = scene_of(SHEET)
    changed = dict(
        scene, comps=[dict(c, comment="22n") if i == 0 else c for i, c in enumerate(scene["comps"])]
    )
    diff = compare(changed, scene)
    assert diff["kind"] == "sheet" and diff["counts"]["changed"] == 1


def test_two_kinds_are_refused() -> None:
    with pytest.raises(ValueError, match="two boards or two sheets"):
        compare(scene_of(BOARD), scene_of(SHEET))
