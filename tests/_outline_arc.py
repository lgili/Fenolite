# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""An Altium board whose outline has an arc vertex (change c0378), authored for Fenolite."""

from __future__ import annotations

import _altium_records as rec

from fenolite.backends.altium.adapter import import_board
from fenolite.core.coords import Point
from fenolite.model.design import Design

NM_PER_MIL = 25_400
CORNER = ((0, 0), (1000, 0), (1000, 700), (900, 800), (0, 800))
"""A board of 1000 by 800 mil with its upper right corner rounded by an arc of 100 mil around (900, 700)."""


def rounded(end_y: str = "800mil") -> Design:
    """The board of ``CORNER``; the arc's end vertex lies at ``end_y`` (on its circle at 800 mil)."""
    arc = {"KIND2": "1", "CX2": "900mil", "CY2": "700mil", "R2": "100mil", "SA2": "0", "EA2": "90"}
    record = rec.board(outline=CORNER, extra={**arc, "VY3": end_y})
    return import_board(rec.document(record), file="a.PcbDoc", sha256=rec.SHA)


def mil(x: float, y: float) -> Point:
    return Point(round(x * NM_PER_MIL), -round(y * NM_PER_MIL))
