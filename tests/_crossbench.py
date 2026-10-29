# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The barrier-crossing benches of change c0199: authored two-layer boards built with ``tests/_ties.py``.
No file is read, nothing comes from a library, and every value is a round invented one.

``row`` is a row of eight through-hole pads of 1 mm at a pitch of 2.54 mm on y 20 mm, each on a net of its
own, under a ``Default`` class of 0.2 mm clearance. The cut ``ROW`` runs from the centre of the first pad to
the centre of the last, so its ways are the seven gaps. Counted by hand: a gap is 2.54 − 1 = 1.54 mm of
board, 1.54 − 2 × 0.2 = 1.14 mm of way, and ⌊(1.14 + 0.2) / (0.25 + 0.2)⌋ = 2 tracks of 0.25 mm."""

from __future__ import annotations

import dataclasses

from _groundties import ONE
from _ties import LIBRARY, MM, TieBoard

from fenolite.analysis.crossings import Cut
from fenolite.core.coords import Point
from fenolite.dsl import Footprint, nm
from fenolite.model.board import Keepout
from fenolite.model.design import Design

PITCH = 2_540_000
FIRST = 10 * MM
ROW_Y = 20 * MM
CLEARANCE = MM // 5
WIDTH = MM // 4
GAP_WAY = PITCH - MM - 2 * CLEARANCE
"""The way of one gap: 1.14 mm."""
ROW = Cut("row", Point(FIRST, ROW_Y), Point(FIRST + 7 * PITCH, ROW_Y))


def _through() -> Footprint:
    footprint = Footprint(LIBRARY, "THT", kind="through_hole")
    footprint.pad("1", at=(nm(0), nm(0)), size=(nm(MM), nm(MM)), drill=nm(6 * MM // 10))
    return footprint


THT = _through().definition


def row(*, links: int = 0, top_only: bool = False) -> Design:
    """The row bench. ``links`` adds that many nets with one pad above the row (y 10 mm) and one below
    (y 30 mm), unrouted, each straight line crossing the cut. ``top_only`` adds a rule area that forbids
    tracks on ``B.Cu`` over the whole board."""
    bench = TieBoard(clearance=CLEARANCE)
    for index in range(8):
        bench.place(f"J{index + 1}", THT, Point(FIRST + index * PITCH, ROW_Y))
    for index in range(links):
        x = FIRST + MM // 2 + index * (4 * MM // 5)
        net = {"1": f"L{index + 1:02d}"}
        bench.place(f"A{index + 1}", ONE, Point(x, 10 * MM), net)
        bench.place(f"B{index + 1}", ONE, Point(x, 30 * MM), net)
    design = bench.build()
    board = design.board
    assert board is not None
    if top_only:
        area = Keepout(
            id="kpt_00000000-0000-4000-8000-000000000001",
            outline=(Point(0, 0), Point(60 * MM, 0), Point(60 * MM, 40 * MM), Point(0, 40 * MM)),
            layers=("B.Cu",),
            no_tracks=True,
            name="top only",
        )
        board = dataclasses.replace(board, keepouts=(area,))
    return dataclasses.replace(design, board=board)


__all__ = ["CLEARANCE", "GAP_WAY", "PITCH", "ROW", "THT", "WIDTH", "row"]
