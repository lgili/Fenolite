# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The region-render bench of change c0211: an authored two-layer board built with ``tests/_ties.py``. No
file is read, nothing comes from a library, and every value is a round invented one.

Inside the region 0..20 mm: the unrouted nets ``L1`` (``A1-1`` at 5,5 mm and ``B1-1`` at 15,5 mm) and ``L2``
(``A2-1`` at 5,15 mm and ``B2-1`` at 15,15 mm), so two open connections of 10 mm; the through-hole pad
``H1-1`` of net ``H`` with an oval hole (a slot) at 10,10 mm; a via of net ``GND`` at 10,18 mm under a
``GND`` zone on ``B.Cu`` from 2,17 mm to 18,19 mm, filled (or not). Outside it: the net ``R`` routed by a
track from ``C1-1`` (25,5 mm) to ``C2-1`` (35,5 mm)."""

from __future__ import annotations

import dataclasses

from _groundties import ONE, _box, _p
from _ties import LIBRARY, MM, TieBoard

from fenolite.dsl import Footprint, nm
from fenolite.model.board import Via, Zone, ZoneFill
from fenolite.model.design import Design

REGION = "0mm,0mm,20mm,20mm"
LABELLED = ("A1-1", "A2-1", "B1-1", "B2-1", "H1-1")
"""The pads with a net whose position lies in the region."""
ZONE = "zon_00000000-0000-4000-8000-000000000001"
VIA = "via_00000000-0000-4000-8000-000000000001"


def _slotted() -> Footprint:
    footprint = Footprint(LIBRARY, "SLOT", kind="through_hole")
    footprint.pad(
        "1",
        at=(nm(0), nm(0)),
        size=(nm(3 * MM), nm(3 * MM // 2)),
        shape="oval",
        drill=nm(MM // 2),
        drill_shape="slot",
        drill_length=nm(2 * MM),
    )
    return footprint


SLOT = _slotted().definition


def bench(*, fill: bool = True) -> Design:
    """The bench; ``fill`` false leaves the ``GND`` zone without a stored fill."""
    board_bench = TieBoard(clearance=MM // 5)
    board_bench.place("A1", ONE, _p(5, 5), {"1": "L1"})
    board_bench.place("B1", ONE, _p(15, 5), {"1": "L1"})
    board_bench.place("A2", ONE, _p(5, 15), {"1": "L2"})
    board_bench.place("B2", ONE, _p(15, 15), {"1": "L2"})
    board_bench.place("H1", SLOT, _p(10, 10), {"1": "H"})
    board_bench.place("C1", ONE, _p(25, 5), {"1": "R"})
    board_bench.place("C2", ONE, _p(35, 5), {"1": "R"})
    board_bench.track("r", "R", _p(25, 5), _p(35, 5))
    gnd = board_bench.net("GND")
    design = board_bench.build()
    board = design.board
    assert board is not None
    box = _box(2, 17, 18, 19)
    zone = Zone(
        id=ZONE,
        outline=box,
        layers=("B.Cu",),
        net_id=gnd,
        fills=(ZoneFill("B.Cu", box),) if fill else (),
        filled=fill,
    )
    via = Via(
        id=VIA,
        position=_p(10, 18),
        diameter=6 * MM // 10,
        drill=3 * MM // 10,
        layers=("F.Cu", "B.Cu"),
        net_id=gnd,
    )
    return dataclasses.replace(design, board=dataclasses.replace(board, vias=(via,), zones=(zone,)))


__all__ = ["LABELLED", "REGION", "SLOT", "VIA", "ZONE", "bench"]
