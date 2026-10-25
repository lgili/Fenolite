# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Keep-outs, dimensions and placement marks in the board scene (capability board-annotations-view, change
c0183)."""

from __future__ import annotations

import dataclasses
from pathlib import Path
from typing import Any

from fenolite.backends import registry
from fenolite.backends.base import PlacedExtent
from fenolite.cli.cmd_view import _placement, scene_of  # pyright: ignore[reportPrivateUsage]
from fenolite.core.coords import Point
from fenolite.model.design import Design
from fenolite.view.scene import CHECKS, build_scene

ROOT = Path(__file__).resolve().parents[3]
BOARDS = ROOT / "tests" / "data" / "kicad" / "board"


def test_keepout() -> None:
    """Scenario "An authored keep-out": the rule area of `two_layer.kicad_pcb` forbids tracks and vias on
    F.Cu."""
    hatched = [p for p in scene_of(BOARDS / "two_layer.kicad_pcb")["prims"] if p[1] == "h"]
    assert [p[0] for p in hatched] == ["F.Cu"]
    assert "no tracks, vias" in hatched[0][5]


def test_dimension() -> None:
    scene = scene_of(BOARDS / "dimension.kicad_pcb")
    lines = [p for p in scene["prims"] if p[5].startswith("dimension 1")]
    assert len(lines) == 3 and {p[0] for p in lines} == {"Dwgs.User"}
    assert [t[10] for t in scene["texts"]] == ["30.0000 mm"]


class _Courtyards:
    """The backend's frame with exact square courtyards of 2 mm around each part (so two parts at one place
    overlap)."""

    def __init__(self, backend: Any) -> None:
        self.backend = backend

    def __getattr__(self, name: str) -> Any:
        return getattr(self.backend, name)

    def placed_extents(self, design: Design, **_: Any) -> tuple[PlacedExtent, ...]:
        assert design.board is not None
        out: list[PlacedExtent] = []
        for fp in design.board.footprints:
            x, y, h = fp.position.x, fp.position.y, 1_000_000
            ring = (Point(x - h, y - h), Point(x + h, y - h), Point(x + h, y + h), Point(x - h, y + h))
            out.append(PlacedExtent(fp.id, fp.side, front=(ring,), source="courtyard"))
        return tuple(out)


def test_overlap() -> None:
    """Scenario "Two overlapping parts": a part moved onto another is marked on the Checks layer."""
    path = BOARDS / "two_layer.kicad_pcb"
    backend: Any = registry.for_path(path)
    design = backend.read(path).content
    assert isinstance(design, Design) and design.board is not None
    first, second, *rest = design.board.footprints
    moved = dataclasses.replace(second, position=first.position, side=first.side)
    design = dataclasses.replace(
        design, board=dataclasses.replace(design.board, footprints=(first, moved, *rest))
    )
    frame = _Courtyards(backend)
    extents, checks = _placement(design, frame)
    assert len(checks) == 1 and "overlap" in checks[0][0] and len(checks[0][1]) == 2
    scene = build_scene(design, frame, name="moved", checks=checks, extents=extents)
    marks = [p for p in scene["prims"] if p[0] == CHECKS]
    assert {scene["comps"][p[4]]["ref"] for p in marks} == set(checks[0][1])
    assert any(layer["id"] == CHECKS for layer in scene["layers"])


def test_approximate_overlap_is_a_note() -> None:
    """Courtyards made from pad copper: the overlap is stated, not marked."""
    path = BOARDS / "two_layer.kicad_pcb"
    backend: Any = registry.for_path(path)
    design = backend.read(path).content
    assert isinstance(design, Design) and design.board is not None
    first, second, *rest = design.board.footprints
    moved = dataclasses.replace(second, position=first.position, side=first.side)
    design = dataclasses.replace(
        design, board=dataclasses.replace(design.board, footprints=(first, moved, *rest))
    )
    extents, checks = _placement(design, backend)
    scene = build_scene(design, backend, name="moved", checks=checks, extents=extents)
    assert not [p for p in scene["prims"] if p[0] == CHECKS]
    assert any("without a courtyard" in note for note in scene["meta"]["notes"])
