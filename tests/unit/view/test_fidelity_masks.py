# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Rendered layer masks and level 8 (capability fidelity-proof, "Rendered layer masks"; capability
design-equivalence, "Level 8 compares rendered presentation"; change c0278)."""

from __future__ import annotations

import dataclasses
from pathlib import Path

from fenolite.backends import registry
from fenolite.backends.kicad.pcb import read_board, write_board
from fenolite.core.coords import Point
from fenolite.model.design import Design
from fenolite.view.fidelity import (
    Capsule,
    Grid,
    Polygon,
    board_scene,
    compare_masks,
    compare_scenes,
    grid_for,
    rasterise,
    render_masks,
)

ROOT = Path(__file__).resolve().parents[3]
TWO_LAYER = ROOT / "tests" / "data" / "kicad" / "board" / "two_layer.kicad_pcb"
PITCH = 50_000


def _design() -> Design:
    return read_board(TWO_LAYER.read_text(encoding="utf-8"), file=TWO_LAYER.name)


def _scene(design: Design) -> dict[str, object]:
    frame = registry.for_path(TWO_LAYER)
    return board_scene(design, frame, name="board", backend="kicad")  # type: ignore[arg-type]


def _moved_graphic(design: Design, layer: str, dx: int) -> Design:
    assert design.board is not None
    graphics = list(design.board.graphics)
    index = next(k for k, g in enumerate(graphics) if g.layer == layer)
    graphics[index] = dataclasses.replace(
        graphics[index], points=tuple(Point(p.x + dx, p.y) for p in graphics[index].points)
    )
    return dataclasses.replace(design, board=dataclasses.replace(design.board, graphics=tuple(graphics)))


def test_a_square_fills_its_pixel_centres() -> None:
    grid = Grid(Point(0, 0), 10, 10, 10)
    square = Polygon(((Point(20, 20), Point(60, 20), Point(60, 60), Point(20, 60)),))
    mask = rasterise([square], grid)
    assert mask.rows[2] == ((2, 6),) and mask.rows[1] == () and mask.rows[6] == ()
    assert mask.inked == 16
    disc = rasterise([Capsule(Point(50, 50), Point(50, 50), 10)], grid)
    assert disc.rows[4] == ((4, 6),) and disc.inked == 4


def test_grid_shared() -> None:
    """A board and a copy moved by half a pixel: one grid, and no difference within one pixel."""
    source = _design()
    assert source.board is not None
    shifted = [
        dataclasses.replace(
            t, start=Point(t.start.x + PITCH // 2, t.start.y), end=Point(t.end.x + PITCH // 2, t.end.y)
        )
        for t in source.board.tracks
    ]
    copy = dataclasses.replace(source, board=dataclasses.replace(source.board, tracks=tuple(shifted)))
    one, other = _scene(source), _scene(copy)
    grid = grid_for((one, other), PITCH)
    size = (grid.columns, grid.rows)
    masks_a = render_masks(one, pitch_nm=PITCH, origin=grid.origin, size=size)
    masks_b = render_masks(other, pitch_nm=PITCH, origin=grid.origin, size=size)
    assert set(masks_a) == set(masks_b) and "F.Cu" in masks_a
    for layer, mask in masks_a.items():
        assert mask.grid == masks_b[layer].grid == grid
        assert not compare_masks(mask, masks_b[layer]).exceeds, layer
    assert compare_scenes({"board": one}, {"board": other}).findings == ()


def test_same_board_no_difference() -> None:
    source = _design()
    copy = read_board(write_board(source, target=10).text, file="copy.kicad_pcb")
    found = compare_scenes({"board": _scene(source)}, {"board": _scene(copy)})
    assert found.findings == () and found.compared > 5


def test_zone_fills_are_not_drawn() -> None:
    source = _design()
    assert source.board is not None and source.board.zones[0].fills
    unfilled = tuple(dataclasses.replace(z, fills=()) for z in source.board.zones)
    copy = dataclasses.replace(source, board=dataclasses.replace(source.board, zones=unfilled))
    assert compare_scenes({"board": _scene(source)}, {"board": _scene(copy)}).findings == ()


def test_moved_logo_on_silkscreen() -> None:
    source = _design()
    copy = _moved_graphic(source, "F.SilkS", 2_000_000)
    found = compare_scenes({"board": _scene(source)}, {"board": _scene(copy)})
    assert [(f.kind, f.where.split(":")[0]) for f in found.findings] == [("render-pixels", "F.SilkS")]
    box = [int(v) for part in found.findings[0].where.split(":")[1].split("-") for v in part.split(",")]
    assert box[2] - box[0] >= 2_000_000
    assert found.summary["changes"] == {
        "board": ["graphic 5 added on F.SilkS", "graphic 5 removed from F.SilkS"]
    }


def test_located_change() -> None:
    """A silkscreen line removed: the layer and a box around the line, and the removed primitive named."""
    source = _design()
    assert source.board is not None
    graphics = tuple(g for g in source.board.graphics if not (g.layer == "F.SilkS"))
    copy = dataclasses.replace(source, board=dataclasses.replace(source.board, graphics=graphics))
    found = compare_scenes({"board": _scene(source)}, {"board": _scene(copy)})
    (finding,) = found.findings
    assert finding.kind == "render-pixels" and finding.where.startswith("F.SilkS:")
    assert finding.b.startswith("0/")
    assert any("removed from F.SilkS" in text for text in found.summary["changes"]["board"])  # type: ignore[index]


def test_a_layer_drawn_on_one_side() -> None:
    source = _design()
    assert source.board is not None
    graphics = tuple(g for g in source.board.graphics if g.layer != "F.Fab")
    copy = dataclasses.replace(source, board=dataclasses.replace(source.board, graphics=graphics))
    kinds = {
        (f.kind, f.where) for f in compare_scenes({"board": _scene(source)}, {"board": _scene(copy)}).findings
    }
    assert ("render-missing", "board") not in kinds
    single = compare_scenes({"board": _scene(source)}, {})
    assert [(f.kind, f.where, f.a, f.b) for f in single.findings] == [
        ("render-missing", "board", "board", "")
    ]
