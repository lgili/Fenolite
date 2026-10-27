# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The ground-tie benches of change c0198: authored two-layer boards built with ``tests/_ties.py``. No file
is read, nothing comes from a library, and every value is a round invented one.

``ground`` is one ``GND`` net in two areas, a power area (a fill on ``F.Cu`` from x 2 mm to 20 mm) and a
control area (a fill from x 40 mm to 58 mm), joined by the diagonal track ``t1``. ``Q1-1`` lies in the
power area, ``U1-1`` in the control area, and ``Q2-1`` sits inside the box of ``t1``, joined to the power
area by ``t2``, which does not touch ``t1``."""

from __future__ import annotations

import dataclasses

from _ties import MM, TieBoard, row, tie_footprint

from fenolite.backends.base import BoardPad
from fenolite.backends.kicad.frame import board_pads
from fenolite.core.coords import Point
from fenolite.model.board import Track, Via, Zone, ZoneFill
from fenolite.model.design import Design

ONE = tie_footprint("ONE", (0,))
"""A footprint of one square pad."""
TWO = tie_footprint("TWO", row(2, 3 * MM))
"""A footprint of two square pads 3 mm apart."""
NET_TIE = tie_footprint("NET_TIE", row(2, 4 * MM // 5), groups=(("1", "2"),))
"""A net-tie footprint: two square pads that overlap, in one net-tie group."""
SHUNT = tie_footprint("SHUNT", (-3 * MM, 0, 4 * MM // 5), groups=(("2", "3"),))
"""A shunt: pad 1 on the bus, pads 2 and 3 overlap as a net tie, the sense pad 3 beside the load pad 2."""


def _p(x_mm: float, y_mm: float) -> Point:
    return Point(round(x_mm * MM), round(y_mm * MM))


def _box(x0: float, y0: float, x1: float, y1: float) -> tuple[Point, ...]:
    return (_p(x0, y0), _p(x1, y0), _p(x1, y1), _p(x0, y1))


def _zone(n: int, net_id: str, box: tuple[Point, ...], *, fill: bool = True) -> Zone:
    fills = (ZoneFill("F.Cu", box),) if fill else ()
    return Zone(
        id=f"zon_00000000-0000-4000-8000-{n:012d}",
        outline=box,
        layers=("F.Cu",),
        net_id=net_id,
        fills=fills,
        filled=fill,
    )


def _via(n: int, net_id: str, at: Point) -> Via:
    return Via(
        id=f"via_00000000-0000-4000-8000-{n:012d}",
        position=at,
        diameter=MM // 2 + MM // 10,
        drill=MM * 3 // 10,
        layers=("F.Cu", "B.Cu"),
        net_id=net_id,
    )


def _track(n: int, net_id: str, start: Point, end: Point, layer: str = "F.Cu") -> Track:
    return Track(
        id=f"trk_00000000-0000-4000-8000-{n:012d}",
        start=start,
        end=end,
        width=MM // 4,
        layer=layer,
        net_id=net_id,
    )


def ground(*, via: bool = False, intruder: bool = False, fill: bool = True) -> Design:
    """The ``GND`` bench. ``via`` adds a parallel joint: a via in each area and a ``B.Cu`` track between
    them. ``intruder`` adds ``U2-1``, a control pad inside the power area. ``fill`` false leaves the
    zones unfilled."""
    bench = TieBoard()
    gnd = bench.net("GND")
    bench.place("Q1", ONE, _p(8, 10), {"1": "GND"})
    bench.place("U1", ONE, _p(50, 10), {"1": "GND"})
    bench.place("Q2", ONE, _p(26, 15), {"1": "GND"})
    if intruder:
        bench.place("U2", ONE, _p(12, 5), {"1": "GND"})
    design = bench.build()
    board = design.board
    assert board is not None
    tracks = (
        _track(1, gnd, _p(19, 4), _p(41, 16)),  # t1, the tie: its box holds Q2-1
        _track(2, gnd, _p(18, 15), _p(26, 15)),  # t2, from the power area to Q2-1
    )
    vias: tuple[Via, ...] = ()
    if via:
        vias = (_via(1, gnd, _p(10, 15)), _via(2, gnd, _p(50, 15)))
        tracks += (_track(3, gnd, _p(10, 15), _p(50, 15), "B.Cu"),)
    zones = (_zone(1, gnd, _box(2, 2, 20, 18), fill=fill), _zone(2, gnd, _box(40, 2, 58, 18), fill=fill))
    board = dataclasses.replace(board, tracks=tracks, vias=vias, zones=zones)
    return dataclasses.replace(design, board=board)


T1 = "trk_00000000-0000-4000-8000-000000000001"
T2 = "trk_00000000-0000-4000-8000-000000000002"
V1 = "via_00000000-0000-4000-8000-000000000001"


def split_nets() -> Design:
    """Two ground nets, ``GND_P`` (power area) and ``GND_C`` (control area), joined only by the net-tie
    part ``NT1`` at x 30 mm, with a track from each area to its pad."""
    bench = TieBoard()
    p, c = bench.net("GND_P"), bench.net("GND_C")
    bench.place("Q1", ONE, _p(8, 10), {"1": "GND_P"})
    bench.place("U1", ONE, _p(50, 10), {"1": "GND_C"})
    bench.place("NT1", NET_TIE, _p(30, 10), {"1": "GND_P", "2": "GND_C"})
    design = bench.build()
    board = design.board
    assert board is not None
    tracks = (_track(1, p, _p(19, 10), _p(29.6, 10)), _track(2, c, _p(30.4, 10), _p(41, 10)))
    zones = (_zone(1, p, _box(2, 2, 20, 18)), _zone(2, c, _box(40, 2, 58, 18)))
    return dataclasses.replace(design, board=dataclasses.replace(board, tracks=tracks, zones=zones))


def sense(*, from_pour: bool = True) -> Design:
    """A shunt ``R1`` whose pad 1 lies on the ``DC_BUS`` pour (x 2 mm to 20 mm). ``ISENSE_N`` leaves the
    sense pad ``R1-3`` of the net tie. With ``from_pour``, ``ISENSE_P`` starts on the pour beside
    ``R1-1``, else on ``R1-1``'s own sense pad of a second net tie."""
    bench = TieBoard()
    bus, sense_p, sense_n = bench.net("DC_BUS"), bench.net("ISENSE_P"), bench.net("ISENSE_N")
    bench.place("R1", SHUNT, _p(23, 10), {"1": "DC_BUS", "2": "DC_OUT", "3": "ISENSE_N"})
    bench.place("U3", TWO, _p(30, 30), {"1": "ISENSE_P", "2": "ISENSE_N"})
    design = bench.build()
    board = design.board
    assert board is not None
    start = _p(19, 12) if from_pour else _p(28.5, 30)
    tracks = (
        _track(1, sense_p, start, _p(28.5, 30)),
        _track(2, sense_n, _p(23.8, 10), _p(31.5, 30)),
    )
    zones = (_zone(1, bus, _box(2, 2, 20.6, 18)),)
    return dataclasses.replace(design, board=dataclasses.replace(board, tracks=tracks, zones=zones))


def isolated() -> Design:
    """Nets on two sides of the isolator ``U5``: ``A1`` and ``A2`` joined by ``R1``, ``B1`` and ``B2`` by
    ``R2``; ``U5`` has a pin on ``A1`` and one on ``B1``. No copper."""
    bench = TieBoard()
    bench.place("R1", TWO, _p(10, 10), {"1": "A1", "2": "A2"})
    bench.place("U5", TWO, _p(30, 10), {"1": "A1", "2": "B1"})
    bench.place("R2", TWO, _p(50, 10), {"1": "B1", "2": "B2"})
    return bench.build()


def pads(design: Design) -> tuple[BoardPad, ...]:
    return board_pads(design)


__all__ = ["T1", "T2", "V1", "ground", "isolated", "pads", "sense", "split_nets"]
