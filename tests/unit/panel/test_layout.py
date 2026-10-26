# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The panel layout (capability board-panels, "Panel layout" and "Panel separations"; capability
design-dsl, "Panel fit rule"; change c0173)."""

from __future__ import annotations

import runpy
from pathlib import Path

from fenolite.core.coords import Point, Size
from fenolite.core.ids import derived_id
from fenolite.dsl import Design, Panel, mm, to_model
from fenolite.model.panel import Panel as ModelPanel
from fenolite.panel.layout import BoardShape, PanelLayout, Rect, board_shape, layout, rings

MM = 1_000_000
BOARD = BoardShape(Rect(100 * MM, 100 * MM, 140 * MM, 130 * MM), True)
"""The 40 × 30 mm fixture board as the DSL writes it (its top-left corner at (100, 100) mm)."""
FIXTURE = Path(__file__).resolve().parents[2] / "data" / "panels" / "board.py"


def _grid_2x2() -> ModelPanel:
    panel = Panel("p", board="board.kicad_pcb")
    panel.grid(2, 2)
    panel.rails(top=mm(5), bottom=mm(5))
    for between in ("columns", "rows", "rails"):
        panel.separate("tabs", between=between)
    return to_model(panel)


def test_grid_of_2_by_2_tabbed() -> None:
    laid = layout(_grid_2x2(), BOARD)
    assert laid.issues == ()
    assert laid.size == Size(82 * MM, 76 * MM)
    copies = {(c.row, c.col): c for c in laid.copies}
    assert copies[(1, 1)].origin == Point(0, 7 * MM)
    assert copies[(2, 2)].origin == Point(42 * MM, 39 * MM)
    between = [tab for tab in laid.tabs if len(tab.copies) == 2]
    assert between and all(len(tab.holes) == 10 and tab.drill == 600_000 for tab in between)
    to_rail = [tab for tab in laid.tabs if len(tab.copies) == 1]
    assert to_rail and all(len(tab.holes) == 5 for tab in to_rail)


def test_grid_copy_ids_are_stable() -> None:
    first, second = layout(_grid_2x2(), BOARD), layout(_grid_2x2(), BOARD)
    assert first == second
    copy = next(c for c in first.copies if (c.row, c.col) == (1, 2))
    assert copy.id == derived_id("pcy", "panel", "copy:1.2") and copy.k == 2


def test_grid_holes_tangent_to_the_board_edge() -> None:
    laid = layout(_grid_2x2(), BOARD)
    tab = next(t for t in laid.tabs if t.edge == "x1.1")
    left, right = laid.copies[0].rect, laid.copies[1].rect
    xs = sorted({hole.x for hole in tab.holes})
    assert xs == [left.x1 + 300_000, right.x0 - 300_000]
    ys = sorted({hole.y for hole in tab.holes})
    assert [b - a for a, b in zip(ys, ys[1:], strict=False)] == [MM] * 4
    assert (ys[0] + ys[-1]) // 2 == (left.y0 + left.y1) // 2


def test_mixed_separations() -> None:
    panel = Panel("p", board="board.kicad_pcb")
    panel.grid(2, 4)
    panel.separate("vscore", between="rows")
    panel.separate("tabs", between="columns")
    laid = layout(to_model(panel), BOARD)
    copies = {(c.row, c.col): c for c in laid.copies}
    assert copies[(2, 1)].rect.y0 == copies[(1, 1)].rect.y1, "the gap between rows is not 0"
    assert len(laid.score_lines) == 1
    line = laid.score_lines[0]
    assert (line.axis, line.at, line.start, line.end) == ("y", 30 * MM, 0, laid.size.w)
    assert {t.edge.split(".")[0] for t in laid.tabs} == {"x1", "x2", "x3"}
    assert not any(line.axis == "x" for line in laid.score_lines)


def test_fit_to_a_panel_size() -> None:
    panel = Panel("p", board="board.kicad_pcb")
    panel.fit(mm(100), mm(100), rot="auto")
    panel.rails(top=mm(5), bottom=mm(5))
    laid = layout(to_model(panel), BOARD)
    assert (laid.cols, laid.rows, laid.rotation, len(laid.copies)) == (3, 2, 90_000_000, 6)
    assert laid.size == Size(94 * MM, 96 * MM)
    assert laid.unused == Size(6 * MM, 4 * MM)
    unturned = Panel("p", board="board.kicad_pcb")
    unturned.fit(mm(100), mm(100))
    unturned.rails(top=mm(5), bottom=mm(5))
    assert len(layout(to_model(unturned), BOARD).copies) == 4


def test_fit_nothing_fits() -> None:
    panel = Panel("p", board="board.kicad_pcb")
    panel.fit(mm(30), mm(30))
    laid = layout(to_model(panel), BOARD)
    assert [i.code for i in laid.issues] == ["panel.no-fit"] and laid.copies == ()


def test_a_turned_copy_maps_exactly() -> None:
    panel = Panel("p", board="board.kicad_pcb")
    panel.grid(1, 1, rot=90)
    laid = layout(to_model(panel), BOARD)
    copy = laid.copies[0]
    assert copy.rect == Rect(0, 0, 30 * MM, 40 * MM)
    corners = {copy.place(p) for p in BOARD.box.corners()}
    assert corners == set(copy.rect.corners())
    for p in BOARD.box.corners():
        assert copy.unplace(copy.place(p)) == p


def test_rings_of_a_framed_panel() -> None:
    panel = Panel("p", board="board.kicad_pcb")
    panel.grid(2, 4)
    panel.rails(top=mm(5), bottom=mm(5), left=mm(5), right=mm(5))
    laid = layout(to_model(panel), BOARD)
    assert laid.frame_ring == tuple(Rect(0, 0, laid.size.w, laid.size.h).corners())
    # the same rings, traced the other way round
    assert laid.gap_rings and {frozenset(r) for r in laid.routes} == {frozenset(r) for r in laid.gap_rings}


def test_rings_are_exact() -> None:
    outline, routes = rings(
        Rect(0, 0, 10, 10), [Rect(0, 0, 10, 2), Rect(0, 8, 10, 10), Rect(0, 2, 2, 8), Rect(8, 2, 10, 8)]
    )
    assert outline[0] == (Point(0, 0), Point(10, 0), Point(10, 10), Point(0, 10))
    assert outline[1] == (Point(2, 2), Point(2, 8), Point(8, 8), Point(8, 2))
    assert routes == ((Point(2, 2), Point(8, 2), Point(8, 8), Point(2, 8)),)


def test_fiducials_and_tooling_holes_on_the_rails() -> None:
    panel = Panel("p", board="board.kicad_pcb")
    panel.grid(2, 2)
    panel.rails(top=mm(5), bottom=mm(5))
    panel.fiducials()
    panel.tooling_holes()
    laid: PanelLayout = layout(to_model(panel), BOARD)
    assert [f.ref for f in laid.fiducials] == ["PFID1", "PFID2", "PFID3"]
    assert {f.at.y for f in laid.fiducials} == {3_850_000, laid.size.h - 3_850_000}
    assert [h.ref for h in laid.tooling_holes] == ["PTH1", "PTH2", "PTH3", "PTH4"]
    assert {h.at.y for h in laid.tooling_holes} == {2_500_000, laid.size.h - 2_500_000}


def test_board_shape_of_the_fixture() -> None:
    design = runpy.run_path(str(FIXTURE))["design"]
    assert isinstance(design, Design)
    shape = board_shape(to_model(design))
    assert shape == BoardShape(
        Rect(100 * MM, 100 * MM, 140 * MM, 130 * MM), True, 0, shape.thickness if shape else None
    )


def test_a_board_that_is_no_rectangle() -> None:
    laid = layout(_grid_2x2(), BoardShape(Rect(0, 0, MM, MM), False))
    assert [i.code for i in laid.issues] == ["panel.board-outline"]
