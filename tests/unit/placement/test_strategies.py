# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The four layout strategies (change c0255; capability placement-in-code, "Row and column strategies" and
"Grid and pack strategies")."""

from __future__ import annotations

from fenolite.dsl import mm, nm
from fenolite.dsl.relative import column, grid, pack, row
from fenolite.geometry.shapes import BBox
from fenolite.placement.strategies import Item, arrange

MM = 1_000_000


def _box(width: int, height: int) -> BBox:
    """A box of ``width`` × ``height`` millimetres centred on its origin."""
    return BBox(-width * MM // 2, -height * MM // 2, width * MM // 2, height * MM // 2)


def _placed(items: list[Item], moves: tuple[tuple[str, tuple[int, int]], ...]) -> dict[str, BBox]:
    boxes = {item.key: item.box for item in items}
    return {
        key: BBox(boxes[key].x0 + dx, boxes[key].y0 + dy, boxes[key].x1 + dx, boxes[key].y1 + dy)
        for key, (dx, dy) in moves
    }


def test_a_row_of_three() -> None:
    items = [Item("R1", _box(2, 1)), Item("C1", _box(4, 3)), Item("R2", _box(2, 1))]
    placed = _placed(items, arrange(row(gap=mm(1)), items).moves)
    assert [placed[k].x0 for k in ("R1", "C1", "R2")] == [0, 3 * MM, 8 * MM]
    assert {placed[k].y0 for k in placed} == {0}


def test_row_and_column_alignment() -> None:
    items = [Item("A", _box(2, 2)), Item("B", _box(2, 4))]
    centred = _placed(items, arrange(row(align="center"), items).moves)
    assert (centred["A"].y0 + centred["A"].y1) // 2 == (centred["B"].y0 + centred["B"].y1) // 2
    ended = _placed(items, arrange(row(align="end"), items).moves)
    assert ended["A"].y1 == ended["B"].y1 == 4 * MM
    stacked = _placed(items, arrange(column(gap=mm(1), align="end", at=(mm(5), mm(5))), items).moves)
    assert stacked["A"].y0 == 5 * MM and stacked["B"].y0 == 8 * MM
    assert stacked["A"].x1 == stacked["B"].x1 == 7 * MM


def test_grid_cells() -> None:
    items = [Item(f"P{i}", _box(2 if i else 4, 2)) for i in range(5)]
    placed = _placed(items, arrange(grid(2, gap=mm(1)), items).moves)
    centres = {k: ((b.x0 + b.x1) // 2, (b.y0 + b.y1) // 2) for k, b in placed.items()}
    assert centres["P0"] == (2 * MM, MM) and centres["P1"] == (7 * MM, MM)
    assert centres["P2"] == (2 * MM, 4 * MM) and centres["P4"] == (2 * MM, 7 * MM)


def test_pack_within_a_width() -> None:
    items = [
        Item("A", _box(4, 2)),
        Item("B", _box(4, 3)),
        Item("WIDE", _box(12, 1)),
        Item("C", _box(3, 3)),
        Item("D", _box(5, 1)),
    ]
    strategy = pack(width=mm(10), gap=mm(1))
    first = arrange(strategy, items)
    assert first == arrange(strategy, items)
    assert first.overflow == ("WIDE",)
    placed = _placed(items, first.moves)
    for key, box in placed.items():
        if key != "WIDE":
            assert box.x0 >= 0 and box.x1 <= 10 * MM, key
    assert placed["B"].y0 == placed["C"].y0 == 0 and placed["B"].x0 == 0 and placed["C"].x0 == 5 * MM
    assert placed["A"].y0 == 4 * MM
    wide = placed["WIDE"]
    assert all(not wide.intersects(box) for key, box in placed.items() if key != "WIDE")
    assert all(box.y1 < wide.y0 or box.y0 > wide.y1 for key, box in placed.items() if key != "WIDE")


def test_origin_is_added() -> None:
    items = [Item("A", BBox(nm(0).nm, 0, 2 * MM, MM))]
    assert arrange(row(), items, (100 * MM, 50 * MM)).moves == (("A", (100 * MM, 50 * MM)),)
