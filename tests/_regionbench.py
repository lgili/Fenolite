# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The region-placement bench of change c0205: an authored 60 × 40 mm two-layer board built with
``tests/_ties.py``. No file is read, nothing comes from a library, and every value is a round invented one.

Every part is staged below the board (y 60 mm). ``R1`` (``A1``-``A2``) and ``R3`` (``A2``-``A3``) form
the domain ``A``; ``R2`` (``B1``-``B2``) and ``R4`` (``B2``-``B3``) the domain ``B``; the isolator ``U5``
has a pin on ``A1`` and one on ``B1``; the mounting part ``H1`` has no net. Each two-pad part has pads of
1 mm, 3 mm apart, so its pad hull is 4 mm by 1 mm."""

from __future__ import annotations

from _ties import MM, TieBoard, row, tie_footprint

from fenolite.backends.kicad.pcb import write_board
from fenolite.core.coords import Point
from fenolite.model.design import Design

TWO = tie_footprint("TWO", row(2, 3 * MM))
ONE = tie_footprint("ONE", (0,))
STAGE_Y = 60 * MM


def bench() -> Design:
    """The staged parts on the empty 60 × 40 mm board."""
    board = TieBoard()
    parts = (
        ("R1", {"1": "A1", "2": "A2"}),
        ("R2", {"1": "B1", "2": "B2"}),
        ("R3", {"1": "A2", "2": "A3"}),
        ("R4", {"1": "B2", "2": "B3"}),
        ("U5", {"1": "A1", "2": "B1"}),
    )
    for index, (ref, nets) in enumerate(parts):
        board.place(ref, TWO, Point(10 * MM * (index + 1), STAGE_Y), nets)
    board.place("H1", ONE, Point(70 * MM, STAGE_Y), {})
    return board.build()


def bench_text() -> str:
    """The bench as a KiCad 10 board file."""
    return write_board(bench(), target=10).text


__all__ = ["MM", "STAGE_Y", "bench", "bench_text"]
