# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The board outline as rings (capability kicad-file-backend, "Board outline as rings"; change c0022)."""

from __future__ import annotations

import dataclasses
from pathlib import Path

import pytest
from _buildhelp import blink, build

from fenolite.backends.kicad.layers import created_layers
from fenolite.backends.kicad.outline import EVIDENCE, PROBLEMS, BoardOutline, board_outline
from fenolite.backends.kicad.pcb import read_board
from fenolite.core.coords import Point
from fenolite.core.ids import derived_id
from fenolite.geometry import Location, area2, point_in_ring
from fenolite.model.board import Board, Graphic, GraphicKind, Outline
from fenolite.model.design import Design

FIXTURE = Path(__file__).resolve().parents[4] / "tests" / "data" / "kicad" / "board" / "two_layer.kicad_pcb"
MM = 1_000_000


def mm(x: float, y: float) -> Point:
    return Point(round(x * MM), round(y * MM))


def graphic(n: int, kind: GraphicKind, *points: Point, layer: str = "Edge.Cuts") -> Graphic:
    return Graphic(id=derived_id("gfx", "outline", str(n)), kind=kind, layer=layer, points=points)


def design_with(*graphics: Graphic, outline: Outline | None = None) -> Design:
    design = Design.new("outline", seed=0)
    board = Board(
        id=derived_id("brd", "outline", "board"), layers=created_layers(2), graphics=graphics, outline=outline
    )
    return dataclasses.replace(design, board=board)


RECT = (mm(0, 0), mm(50, 0), mm(50, 30), mm(0, 30))


def rect_lines(first: int = 0) -> list[Graphic]:
    ends = (*RECT[1:], RECT[0])
    return [graphic(first + n, "line", a, b) for n, (a, b) in enumerate(zip(RECT, ends, strict=True))]


def test_model_outline() -> None:
    output = build(blink(), 10)
    found = board_outline(output.design)
    assert output.design.board is not None and output.design.board.outline is not None
    assert found.source == "model" and found.problem == "" and found.exact
    assert found.rings == (tuple(output.design.board.outline.points),)


def test_model_outline_with_cutouts() -> None:
    hole = (mm(10, 10), mm(20, 10), mm(20, 20), mm(10, 20))
    outline = Outline(id=derived_id("out", "outline", "o"), points=RECT, cutouts=(hole,))
    found = board_outline(design_with(outline=outline))
    assert found == BoardOutline((RECT, hole), "model")


def test_edge_graphics_with_a_cutout() -> None:
    circle = graphic(9, "circle", mm(10, 15), mm(12, 15))
    found = board_outline(design_with(*rect_lines(), circle))
    assert found.source == "edge" and found.problem == "" and not found.exact
    assert len(found.rings) == 2
    assert set(found.rings[0]) == set(RECT) and area2(found.rings[0]) > 0
    hole = found.rings[1]
    assert len(hole) > 8 and all(
        abs((p.x - 10 * MM) ** 2 + (p.y - 15 * MM) ** 2 - (2 * MM) ** 2) < 10 * MM for p in hole
    )
    assert all(point_in_ring(p, found.rings[0]) is Location.INSIDE for p in hole)


def test_built_board_read_back_gives_edge_rings() -> None:
    output = build(blink(), 10)
    design = read_board(output.files["blink.kicad_pcb"].decode("utf-8"), file="blink.kicad_pcb")
    found = board_outline(design)
    assert found.source == "edge" and found.exact and len(found.rings) == 1
    assert output.design.board is not None and output.design.board.outline is not None
    assert set(found.rings[0]) == set(output.design.board.outline.points)


def test_open_contour_named() -> None:
    found = board_outline(design_with(*rect_lines()[:3], graphic(9, "circle", mm(10, 15), mm(12, 15))))
    assert found.rings == () and found.problem == "open-contour"


def test_branching_contour_named() -> None:
    extra = graphic(8, "line", mm(0, 0), mm(50, 30))
    found = board_outline(design_with(*rect_lines(), extra))
    assert found.rings == () and found.problem == "branching-contour"


def test_arcs_are_approximated() -> None:
    """A stadium: two lines and two half circles."""
    pieces = (
        graphic(0, "line", mm(10, 0), mm(30, 0)),
        graphic(1, "arc", mm(30, 0), mm(35, 5), mm(30, 10)),
        graphic(2, "line", mm(30, 10), mm(10, 10)),
        graphic(3, "arc", mm(10, 10), mm(5, 5), mm(10, 0)),
    )
    found = board_outline(design_with(*pieces))
    assert found.problem == "" and not found.exact and len(found.rings) == 1
    ring = found.rings[0]
    assert {mm(10, 0), mm(30, 0), mm(30, 10), mm(10, 10), mm(35, 5), mm(5, 5)} <= set(ring)
    assert len(ring) > 20 and area2(ring) > 0


def test_rect_and_polygon_items() -> None:
    rect = graphic(0, "rect", mm(0, 0), mm(50, 30))
    slot = graphic(1, "polygon", mm(5, 5), mm(8, 5), mm(8, 9))
    found = board_outline(design_with(rect, slot))
    assert found.exact and found.source == "edge"
    assert set(found.rings[0]) == set(RECT)
    assert set(found.rings[1]) == {mm(5, 5), mm(8, 5), mm(8, 9)}


def test_other_layers_and_zero_length_lines_are_ignored() -> None:
    silk = graphic(7, "line", mm(0, 0), mm(9, 9), layer="F.SilkS")
    dot = graphic(8, "line", mm(3, 3), mm(3, 3))
    found = board_outline(design_with(*rect_lines(), silk, dot))
    assert found.problem == "" and len(found.rings) == 1


def test_no_edge_content() -> None:
    assert board_outline(design_with()).problem == "no-edge-content"
    assert board_outline(design_with(graphic(0, "line", mm(0, 0), mm(1, 1), layer="F.Fab"))).rings == ()
    assert (
        board_outline(dataclasses.replace(Design.new("x", seed=0), board=None)).problem == "no-edge-content"
    )


def test_footprint_edges_only() -> None:
    text = FIXTURE.read_text(encoding="utf-8")
    design = read_board(text, file=FIXTURE.name)
    assert design.board is not None
    assert board_outline(design).source == "edge" and len(board_outline(design).rings) == 1
    line = (
        "\t\t(fp_line\n\t\t\t(start -1 -1)\n\t\t\t(end 1 -1)\n\t\t\t(stroke\n\t\t\t\t(width 0.05)\n"
        '\t\t\t\t(type solid)\n\t\t\t)\n\t\t\t(layer "Edge.Cuts")\n'
        '\t\t\t(uuid "0e0e0e0e-0000-4000-8000-000000000001")\n\t\t)\n'
    )
    marker = '\t\t(pad "1" smd rect'
    assert marker in text
    edited = read_board(text.replace(marker, line + marker, 1), file=FIXTURE.name)
    assert edited.board is not None
    edge = {layer.name for layer in edited.board.layers if layer.kind == "edge"}
    bare = dataclasses.replace(
        edited.board, graphics=tuple(g for g in edited.board.graphics if g.layer not in edge)
    )
    assert board_outline(dataclasses.replace(edited, board=bare)).problem == "footprint-edges-only"
    plain = dataclasses.replace(
        design.board, graphics=tuple(g for g in design.board.graphics if g.layer not in edge)
    )
    assert board_outline(dataclasses.replace(design, board=plain)).problem == "no-edge-content"


def test_outline_holds_rings_or_a_problem() -> None:
    with pytest.raises(ValueError, match="rings or a problem"):
        BoardOutline()
    with pytest.raises(ValueError, match="rings or a problem"):
        BoardOutline((RECT,), problem="open-contour")
    assert set(PROBLEMS) == {"open-contour", "branching-contour", "no-edge-content", "footprint-edges-only"}
    assert EVIDENCE.hypotheses == ("H-G-PLACE-OUTLINE", "H-G-EDGE-EXACT")
