# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The layout of a drawing page (capability manufacturing-exports, "Drawing page layout"; change c0117)."""

from __future__ import annotations

import dataclasses

from _drawdesign import bench_design, bench_text

from fenolite.backends.kicad.drawing import default_sheet_obstacles
from fenolite.exports.drawing_layout import (
    AUTO_PAPERS,
    BOARD,
    Box,
    Obstacles,
    Placed,
    apart,
    choose_paper,
    join,
    mirror,
    page_size,
    place,
)
from fenolite.exports.drawing_spec import DEFAULT, FabSpec
from fenolite.exports.drawing_tables import Block, notes_block
from fenolite.exports.drawings import fab_board_box, no_room, side_content

MM = 1_000_000
GAP = 5 * MM


def mm(*values: float) -> tuple[int, ...]:
    return tuple(round(value * MM) for value in values)


def block(name: str, width: float, height: float) -> Block:
    return Block(name, (("",),), (round(width * MM),), (round(height * MM),), 1_500_000)


def default_sheet(width: int, height: int) -> Obstacles:
    margin, boxes = default_sheet_obstacles(width, height)
    return Obstacles(margin, boxes)


def test_paper_of_the_600_part_probe_board() -> None:
    board: Box = mm(89, 89, 258, 279)  # type: ignore[assignment]
    layout = choose_paper(
        [block("drill", 150, 200)], paper="auto", board_box=lambda w: board, obstacles=default_sheet, gap=GAP
    )
    assert layout.problem is None and (layout.paper, layout.portrait) == ("A2", False)
    assert layout.size == AUTO_PAPERS["A2"] == (594_004_400, 419_989_000)
    assert layout.placed == (Placed("drill", mm(263, 17), mm(150, 200)),)  # type: ignore[arg-type]
    for paper in ("A4", "A3"):  # the two smaller papers are refused
        refused = choose_paper(
            [block("drill", 150, 200)], paper=paper, board_box=lambda w: board, obstacles=default_sheet,
            gap=GAP,
        )  # fmt: skip
        assert refused.problem is not None and refused.problem.smallest == "A2"
    assert refused.problem.what == "drill"  # A3 holds the board, not the block beside it


def test_a_fixed_block_over_the_title_block() -> None:
    board: Box = mm(100, 100, 176, 192)  # type: ignore[assignment]
    note = notes_block(("One line.",), 60 * MM, 1_500_000)
    assert note is not None
    fixed = {"notes": mm(310, 260)}
    layout = choose_paper(
        [note], paper="A3", board_box=lambda w: board, obstacles=default_sheet, gap=GAP, fixed=fixed  # type: ignore[arg-type]
    )  # fmt: skip
    assert layout.problem is not None and layout.placed == ()
    assert (layout.problem.what, layout.problem.smallest) == ("notes", "A2")
    assert layout.problem.box is not None and layout.problem.box[:2] == mm(310, 260)
    found = no_room("assembly drawing, top side", layout, "A3")
    assert (found.code, found.severity, found.where) == ("drawing.no-room", "error", "notes")
    assert "notes" in found.message and "A2" in found.message and "310.000" in found.message
    free = {"notes": mm(200, 30)}
    placed = choose_paper(
        [note], paper="A3", board_box=lambda w: board, obstacles=default_sheet, gap=GAP, fixed=free  # type: ignore[arg-type]
    )  # fmt: skip
    assert placed.problem is None and placed.placed[0].at == mm(200, 30)


def test_the_bottom_page_is_mirrored() -> None:
    width = AUTO_PAPERS["A3"][0]
    assert width == 419_989_000
    assert mirror(mm(100, 100, 176, 192), width) == mm(243.989, 100, 319.989, 192)  # type: ignore[arg-type]
    seen: list[int] = []

    def box(page_width: int) -> Box:
        seen.append(page_width)
        return mirror(mm(100, 100, 176, 192), page_width)  # type: ignore[arg-type]

    layout = choose_paper([], paper="A3", board_box=box, obstacles=default_sheet, gap=GAP)
    assert layout.board_box == mm(243.989, 100, 319.989, 192) and seen == [width]


def test_a_board_outside_every_page() -> None:
    board: Box = mm(-20, 100, 56, 192)  # type: ignore[assignment]
    layout = choose_paper(
        [block("drill", 50, 50)], paper="auto", board_box=lambda w: board, obstacles=default_sheet, gap=GAP
    )
    assert layout.problem is not None
    assert (layout.problem.what, layout.problem.smallest, layout.problem.box) == (BOARD, "", board)
    found = no_room("fabrication drawing", layout, "auto")
    assert found.code == "drawing.no-room" and found.where == BOARD
    assert "no paper from A4 to A0 holds the board box" in found.message and "-20.000" in found.message


def test_blocks_go_in_order_and_keep_the_gap() -> None:
    board: Box = mm(100, 100, 176, 192)  # type: ignore[assignment]
    blocks = [block("board", 60, 20), block("drill", 90, 40), block("notes", 120, 10)]
    size = AUTO_PAPERS["A3"]
    placed, missing = place(blocks, page=size, board_box=board, obstacles=default_sheet(*size), gap=GAP)
    assert missing == "" and [item.name for item in placed] == ["board", "drill", "notes"]
    assert placed[0].at == mm(17, 17) and placed[1].at == mm(17, 42)
    boxes = [item.box for item in placed]
    sheet = default_sheet(*size)
    for index, one in enumerate(boxes):
        assert all(apart(one, other, GAP) for other in (*boxes[:index], board, *sheet.boxes))
        assert sheet.margin[0] <= one[0] and one[3] <= sheet.margin[3]
    again, _ = place(blocks, page=size, board_box=board, obstacles=default_sheet(*size), gap=GAP)
    assert again == placed  # deterministic


def test_page_sizes_are_those_kicad_plots() -> None:
    assert list(AUTO_PAPERS) == ["A4", "A3", "A2", "A1", "A0"]
    assert AUTO_PAPERS["A4"] == (297_002_200, 210_007_200)
    assert all(side % 25_400 == 0 for size in AUTO_PAPERS.values() for side in size)  # whole mils
    assert page_size("A4", portrait=True) == (210_007_200, 297_002_200)
    assert page_size("A5") == (210 * MM, 148 * MM)
    assert join(None, mm(1, 2, 3, 4), mm(0, 3, 2, 9)) == mm(0, 2, 3, 9) and join(None) is None  # type: ignore[arg-type]


def test_default_sheet_obstacles() -> None:
    width, height = AUTO_PAPERS["A4"]
    margin, boxes = default_sheet_obstacles(width, height)
    assert margin == (10 * MM, 10 * MM, width - 10 * MM, height - 10 * MM)
    assert boxes[-1] == (width - 120 * MM, height - 44 * MM, width - 12 * MM, height - 12 * MM)
    assert boxes[0] == (10 * MM, 10 * MM, width - 10 * MM, 12 * MM) and len(boxes) == 5


def test_board_boxes_of_the_bench_pages() -> None:
    design, text = bench_design(), bench_text(10)
    assert fab_board_box(design, text, DEFAULT) == mm(89, 89, 176, 192)  # 8 mm + 2 x 1.5 mm at top and left
    plain = dataclasses.replace(DEFAULT, fab=FabSpec(dimensions=False))
    assert fab_board_box(design, text, plain) == mm(100, 100, 176, 192)
    drawn = text.rstrip()[:-1] + (
        '(gr_line (start 180 95) (end 190 200) (stroke (width 0.1) (type solid)) (layer "Dwgs.User")'
        ' (uuid "d0a00000-0000-4000-8000-0000000000d1")))\n'
    )
    assert fab_board_box(design, drawn, plain) == mm(100, 95, 190, 200)  # the user's drawings join the box
    _, top, parts = side_content(design, "top", DEFAULT)
    assert parts == 5 and top is not None and mm(100, 100, 176, 192)[0] < top[0] < top[2] < 176 * MM
    _, bottom, count = side_content(design, "bottom", DEFAULT)
    assert count == 1 and bottom is not None and bottom[0] < 160 * MM < bottom[2]
