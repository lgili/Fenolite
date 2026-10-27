# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The fabrication read-back bench of change c0203: an authored two-layer board, every value round and
invented. It holds a plated round hole (``J1``), a non-plated slot (``H1``, 1 mm by 3 mm), a via, a square
cut-out and a milled outline slot, so that each check of the read-back has something to match."""

from __future__ import annotations

import dataclasses

from _groundties import _p, _track
from _ties import LIBRARY, MM, TieBoard

from fenolite.core.coords import Point
from fenolite.dsl import Footprint, nm
from fenolite.model.board import OutlineSlot, Via
from fenolite.model.design import Design


def _through() -> Footprint:
    footprint = Footprint(LIBRARY, "PIN", kind="through_hole")
    footprint.pad("1", at=(nm(0), nm(0)), size=(nm(2 * MM), nm(2 * MM)), drill=nm(MM), shape="circle")
    return footprint


def _slot() -> Footprint:
    footprint = Footprint(LIBRARY, "SLOT", kind="through_hole")
    footprint.pad(
        "",
        at=(nm(0), nm(0)),
        size=(nm(3 * MM), nm(MM)),
        kind="np_thru_hole",
        shape="oval",
        drill=nm(MM),
        drill_shape="slot",
        drill_length=nm(3 * MM),
    )
    return footprint


def bench() -> Design:
    build = TieBoard()
    build.place("J1", _through().definition, _p(10, 10), {"1": "SIG"})
    build.place("H1", _slot().definition, _p(30, 10), {})
    design = build.build()
    board = design.board
    assert board is not None
    sig = next(net.id for net in design.circuit.nets if net.name == "SIG")
    via = Via(
        id="via_00000000-0000-4000-8000-000000000001",
        position=_p(20, 20),
        diameter=6 * MM // 10,
        drill=3 * MM // 10,
        layers=("F.Cu", "B.Cu"),
        net_id=sig,
    )
    outline = board.outline
    assert outline is not None
    cutout = (
        Point(40 * MM, 25 * MM),
        Point(50 * MM, 25 * MM),
        Point(50 * MM, 35 * MM),
        Point(40 * MM, 35 * MM),
    )
    slot = OutlineSlot(
        id="slt_00000000-0000-4000-8000-000000000001", center=_p(15, 32), length=6 * MM, width=2 * MM
    )
    outline = dataclasses.replace(outline, cutouts=(cutout,), slots=(slot,))
    board = dataclasses.replace(
        board, outline=outline, vias=(via,), tracks=(_track(1, sig, _p(10, 10), _p(20, 20)),)
    )
    return dataclasses.replace(design, board=board)


__all__ = ["bench"]
