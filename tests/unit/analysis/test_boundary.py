# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The board boundary (capability board-analyses, "Board boundary"; change c0047)."""

from __future__ import annotations

import dataclasses

from _analysis import at, box, with_outline
from _coppercheck import Copper, ident

from fenolite.analysis.boundary import board_boundary
from fenolite.core.coords import Point
from fenolite.geometry import DEFAULT_TOL
from fenolite.model.board import Board, Graphic, StackLayer, Stackup
from fenolite.model.design import Design


def bare() -> Design:
    return Copper().build()


def edges(design: Design, *graphics: tuple[str, tuple[Point, ...]]) -> Board:
    assert design.board is not None
    drawn = tuple(
        Graphic(id=ident("gfx", i + 1), kind=kind, layer="Edge.Cuts", points=points)  # type: ignore[arg-type]
        for i, (kind, points) in enumerate(graphics)
    )
    return dataclasses.replace(design.board, graphics=drawn)


def lines(ring: tuple[Point, ...]) -> list[tuple[str, tuple[Point, ...]]]:
    return [("line", (p, q)) for p, q in zip(ring, (*ring[1:], ring[0]), strict=True)]


def test_outline_from_the_model() -> None:
    design = with_outline(bare(), box(0, 0, 20, 10), (box(4, 2, 6, 8),))
    assert design.board is not None
    found = board_boundary(design.board, thickness=1_600_000)
    assert (found.source, found.band, len(found.cutouts), found.thickness) == ("model", 0, 1, 1_600_000)
    assert found.outer == box(0, 0, 20, 10)


def test_outline_from_edge_graphics() -> None:
    board = edges(bare(), *lines(box(0, 0, 20, 10)), *lines(box(4, 2, 6, 8)))
    found = board_boundary(board)
    assert (found.source, len(found.outer), len(found.cutouts)) == ("edge", 4, 1)
    assert found.thickness is None and found.band == 0
    assert set(found.cutouts[0]) == set(box(4, 2, 6, 8))


def test_open_contour() -> None:
    ring = box(0, 0, 20, 10)
    board = edges(bare(), *lines(ring)[:3])
    found = board_boundary(board)
    assert found.source == "none" and found.outer == () and found.cutouts == ()


def test_no_edge_content() -> None:
    assert bare().board is not None
    assert board_boundary(bare().board).source == "none"  # type: ignore[arg-type]


def test_curved_edges_have_a_band() -> None:
    board = edges(bare(), ("rect", (at(0, 0), at(20, 10))), ("circle", (at(10, 5), at(12, 5))))
    found = board_boundary(board)
    assert found.source == "edge" and found.band == DEFAULT_TOL + 1
    assert len(found.outer) == 4 and len(found.cutouts) == 1 and len(found.cutouts[0]) > 8
    arc = edges(bare(), ("arc", (at(0, 0), at(5, -5), at(10, 0))), ("line", (at(10, 0), at(0, 0))))
    assert board_boundary(arc, arc_tol=2_000).band == 2_001


def test_ring_outside_the_outline_is_not_a_cutout() -> None:
    board = edges(bare(), *lines(box(0, 0, 20, 10)), *lines(box(30, 0, 32, 2)))
    found = board_boundary(board)
    assert found.outer == board_boundary(edges(bare(), *lines(box(0, 0, 20, 10)))).outer
    assert found.cutouts == ()


def test_thickness_from_the_stackup_and_never_assumed() -> None:
    design = with_outline(bare(), box(0, 0, 20, 10))
    assert design.board is not None
    assert board_boundary(design.board).thickness is None
    layers = tuple(
        StackLayer(id=ident("stk", i + 1), name=name, kind=kind, thickness=thickness)  # type: ignore[arg-type]
        for i, (name, kind, thickness) in enumerate(
            (("F.Cu", "copper", 35_000), ("core", "dielectric", 1_530_000), ("B.Cu", "copper", 35_000))
        )
    )
    board = dataclasses.replace(design.board, stackup=Stackup(id=ident("stu", 1), layers=layers))
    assert board_boundary(board).thickness == 1_600_000
    assert board_boundary(board, thickness=800_000).thickness == 800_000


def test_outline_from_the_model_arcs() -> None:
    """Scenario "Model outline with a round cut-out" (change c0102): the arcs of ``Outline.arcs`` are
    polygonised and give the band of curved edges."""
    from fenolite.core.ids import derived_id
    from fenolite.geometry import DEFAULT_TOL
    from fenolite.model.board import Outline, OutlineArc

    mm = 1_000_000
    outline = Outline(
        id=derived_id("out", "boundary", "arcs"),
        points=(Point(0, 0), Point(20 * mm, 0), Point(20 * mm, 10 * mm), Point(0, 10 * mm)),
        cutouts=((Point(11 * mm, 5 * mm), Point(9 * mm, 5 * mm)),),
        arcs=(OutlineArc(1, 0, Point(10 * mm, 4 * mm)), OutlineArc(1, 1, Point(10 * mm, 6 * mm))),
    )
    board = Board(id=derived_id("brd", "boundary", "arcs"), outline=outline)
    found = board_boundary(board)
    assert found.source == "model" and found.band == DEFAULT_TOL + 1
    assert found.outer == outline.points and len(found.cutouts) == 1
    (ring,) = found.cutouts
    assert len(ring) > 2
    for point in ring:
        distance2 = (point.x - 10 * mm) ** 2 + (point.y - 5 * mm) ** 2
        assert (mm - 1) ** 2 <= distance2 <= (mm + 1) ** 2
    coarse = board_boundary(board, arc_tol=50_000)
    assert coarse.band == 50_001 and len(coarse.cutouts[0]) < len(ring)
    # an outline without arcs keeps its band of 0, and a round board of two arcs is a boundary
    plain = board_boundary(Board(id=board.id, outline=Outline(id=outline.id, points=outline.points)))
    assert plain.band == 0 and plain.source == "model"
    disc = Outline(
        id=outline.id,
        points=(Point(20 * mm, 10 * mm), Point(0, 10 * mm)),
        arcs=(OutlineArc(0, 0, Point(10 * mm, 0)), OutlineArc(0, 1, Point(10 * mm, 20 * mm))),
    )
    round_board = board_boundary(Board(id=board.id, outline=disc))
    assert (
        round_board.source == "model" and len(round_board.outer) > 8 and round_board.band == DEFAULT_TOL + 1
    )
