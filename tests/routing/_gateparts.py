# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Footprints and symbols of the gate benches of change c0110, authored for Fenolite with ``dsl.Footprint``
and ``dsl.Symbol``: pin headers of 1.27 mm pitch, a QFN-48 of 0.5 mm pitch with an exposed pad and a BGA of
11 by 11 balls at 0.8 mm. The sizes are round values chosen for the benches, not those of a vendor's land
pattern; the built-in catalog holds none of these parts, and no KiCad library is read.
"""

from __future__ import annotations

from fenolite.dsl import Footprint, Symbol, mm

LIBRARY = "Gate"
HEADER_PAD = 0.85
HEADER_DRILL = 0.5
QFN_PITCH = 0.5
QFN_PADS = 12
"""Pads per side of the QFN-48."""
QFN_ROW = 3.45
"""The distance of each row of QFN pads from the centre, in millimetres."""
QFN_EP = 5.1
BGA_PITCH = 0.8
BGA_BALL = 0.35
BGA_ROWS = "ABCDEFGHJKL"
"""The row letters of the BGA, without ``I`` as KiCad's libraries write them."""


def header(rows: int, columns: int) -> Footprint:
    """A through-hole header of ``rows`` rows and ``columns`` positions at 1.27 mm, the positions along Y.
    Pad 1 is row 1 of the first position; the numbers run across the rows first (1 and 2 face each other)."""
    fp = Footprint(LIBRARY, f"Header_{rows}x{columns:02d}_P1.27", kind="through_hole")
    for position in range(columns):
        for row in range(rows):
            number = position * rows + row + 1
            x = (row - (rows - 1) / 2) * 1.27
            y = (position - (columns - 1) / 2) * 1.27
            fp.pad(
                str(number),
                at=(mm(round(x, 3)), mm(round(y, 3))),
                size=(mm(HEADER_PAD), mm(HEADER_PAD)),
                shape="circle",
                drill=mm(HEADER_DRILL),
            )
    half_x = (rows - 1) * 1.27 / 2 + 0.8
    half_y = (columns - 1) * 1.27 / 2 + 0.8
    fp.rect(
        (mm(round(-half_x, 3)), mm(round(-half_y, 3))),
        (mm(round(half_x, 3)), mm(round(half_y, 3))),
        layer="F.CrtYd",
        width=mm(0.05),
    )
    return fp


def qfn_position(number: int) -> tuple[float, float, bool]:
    """The centre of pad ``number`` (1 to 48) of the QFN-48 and whether its long side is along X: pads 1 to
    12 down the left side, 13 to 24 along the bottom, 25 to 36 up the right side, 37 to 48 along the top."""
    side, index = divmod(number - 1, QFN_PADS)
    offset = (index - (QFN_PADS - 1) / 2) * QFN_PITCH
    if side == 0:
        return -QFN_ROW, offset, True
    if side == 1:
        return offset, QFN_ROW, False
    if side == 2:
        return QFN_ROW, -offset, True
    return -offset, -QFN_ROW, False


def qfn48() -> Footprint:
    """A QFN-48 of 0.5 mm pitch: pads of 0.8 mm by 0.25 mm and an exposed pad ``49`` of 5.1 mm square."""
    fp = Footprint(LIBRARY, "QFN48_P0.5_EP5.1", kind="smd")
    for number in range(1, 4 * QFN_PADS + 1):
        x, y, along_x = qfn_position(number)
        size = (mm(0.8), mm(0.25)) if along_x else (mm(0.25), mm(0.8))
        fp.pad(str(number), at=(mm(round(x, 3)), mm(round(y, 3))), size=size)
    fp.pad("49", at=(mm(0), mm(0)), size=(mm(QFN_EP), mm(QFN_EP)))
    fp.rect((mm(-4.2), mm(-4.2)), (mm(4.2), mm(4.2)), layer="F.CrtYd", width=mm(0.05))
    return fp


def bga_names() -> list[str]:
    """The ball names of the BGA in row order: ``A1`` … ``L11``."""
    return [f"{row}{column}" for row in BGA_ROWS for column in range(1, len(BGA_ROWS) + 1)]


def bga_ring(name: str) -> int:
    """The ring of ball ``name``: 0 for the outermost, 5 for the centre ball."""
    row = BGA_ROWS.index(name[0])
    column = int(name[1:]) - 1
    last = len(BGA_ROWS) - 1
    return min(row, column, last - row, last - column)


def bga121() -> Footprint:
    """A BGA of 11 by 11 balls at 0.8 mm, balls of 0.35 mm."""
    fp = Footprint(LIBRARY, "BGA121_P0.8", kind="smd")
    count = len(BGA_ROWS)
    for name in bga_names():
        row = BGA_ROWS.index(name[0])
        column = int(name[1:]) - 1
        x = (column - (count - 1) / 2) * BGA_PITCH
        y = (row - (count - 1) / 2) * BGA_PITCH
        fp.pad(name, at=(mm(round(x, 3)), mm(round(y, 3))), size=(mm(BGA_BALL), mm(BGA_BALL)), shape="circle")
    fp.rect((mm(-5), mm(-5)), (mm(5), mm(5)), layer="F.CrtYd", width=mm(0.05))
    return fp


def symbol_for(footprint: Footprint, numbers: list[str], reference: str) -> Symbol:
    """A one-unit symbol whose pins are ``numbers`` (named after them), one column at 2.54 mm, with the
    footprint ``footprint``."""
    symbol = Symbol(LIBRARY, footprint.name, reference=reference, footprint=footprint.lib_id)
    for index, number in enumerate(numbers):
        symbol.pin(number, f"P{number}", at=(mm(-5.08), mm(round(-2.54 * index, 2))), length=mm(2.54))
    return symbol


__all__ = ["BGA_ROWS", "bga121", "bga_names", "bga_ring", "header", "qfn48", "qfn_position", "symbol_for"]
