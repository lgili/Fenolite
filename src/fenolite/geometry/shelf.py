# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Shelf packing of rectangles into rows: the one placement rule both schematic writers share.

The unit is the caller's (mils for the Altium sheet, nanometres for the KiCad sheet); the function only
adds and compares integers. It knows nothing of symbols, pins or sheets.
"""

from __future__ import annotations

from collections.abc import Sequence


def shelf_pack(cells: Sequence[tuple[int, int]], usable_width: int) -> tuple[list[tuple[int, int]], int]:
    """Each cell's (left, top) offset, left to right and top to bottom, and the total height.

    ``cells`` holds (width, height) pairs in the order to place them. A cell that does not fit in the rest
    of its row starts the next row; a cell wider than ``usable_width`` takes a row of its own and sticks
    out of it, which the caller detects by comparing widths.
    """
    offsets: list[tuple[int, int]] = []
    x = top = row_height = 0
    for width, height in cells:
        if x > 0 and x + width > usable_width:
            top += row_height
            x = row_height = 0
        offsets.append((x, top))
        x += width
        row_height = max(row_height, height)
    return offsets, top + row_height


__all__ = ["shelf_pack"]
