# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The pour-shape benches of change c0213: authored two-layer boards built with ``tests/_ties.py``. No file
is read, nothing comes from a library, and every value is a round invented one.

- ``neck``: a ``GND`` zone on ``F.Cu`` from x 10 mm to 32 mm, y 10 mm to 20 mm, with ``J1-1`` at (15, 15) mm
  and ``J2-1`` at (27, 15) mm, and two keep-outs from x 20 mm to 22 mm that leave a band from y 14.85 mm to
  15.15 mm between them. Its saved fill is two 10 mm squares joined by that 0.3 mm neck, 2 mm long.
- ``tips``: a ``GND`` fill of a 10 mm square with a finger 0.3 mm wide and 3 mm long on its right side, and a
  separate fill strip of 0.3 mm by 5 mm.
- ``loop``: ``U1`` with pin 4 on ``+3V3`` at (20, 20) mm and pin 2 on ``GND`` 2 mm below; ``C1`` 1.5 mm to
  the right along a track, ``C2`` at x ``far`` mm along the same track, a ``GND`` track from ``U1-2`` to
  ``C1-2`` only.
- ``balance``: ``R1``, two 1 mm pads 3 mm apart at (30, 20) mm; pad 1 on ``GND`` inside a fill from x 20 mm to
  30 mm, pad 2 on ``N`` with a 0.5 mm track to the right.
"""

from __future__ import annotations

import dataclasses

from _groundties import ONE, _box, _p, _track
from _practicebench import CAP, IC, _part, _with_zones
from _ties import MM, TieBoard

from fenolite.core.coords import Point
from fenolite.model.board import Keepout, Track, Zone, ZoneFill
from fenolite.model.design import Design

GRID = MM // 20
"""The raster of the neck tests: 0.05 mm."""
RESISTOR = _part("RES", {"1": (-1.5, 0), "2": (1.5, 0)})


def _gnd_zone(outline: tuple[Point, ...], *fills: tuple[Point, ...]) -> Zone:
    return Zone(
        id="zon_00000000-0000-4000-8000-000000000001",
        outline=outline,
        layers=("F.Cu",),
        net_id=None,
        fills=tuple(ZoneFill("F.Cu", ring) for ring in fills),
        filled=bool(fills),
    )


def _keepout(n: int, ring: tuple[Point, ...]) -> Keepout:
    return Keepout(
        id=f"kpo_00000000-0000-4000-8000-{n:012d}",
        outline=ring,
        layers=("F.Cu",),
        no_copper_pour=True,
        name=f"CUT{n}",
    )


def neck() -> Design:
    bench = TieBoard()
    gnd = bench.net("GND")
    bench.place("J1", ONE, _p(15, 15), {"1": "GND"})
    bench.place("J2", ONE, _p(27, 15), {"1": "GND"})
    design = bench.build()
    fill = tuple(
        _p(x, y)
        for x, y in (
            (10, 10), (20, 10), (20, 14.85), (22, 14.85), (22, 10), (32, 10),
            (32, 20), (22, 20), (22, 15.15), (20, 15.15), (20, 20), (10, 20),
        )
    )  # fmt: skip
    zone = dataclasses.replace(_gnd_zone(_box(10, 10, 32, 20), fill), net_id=gnd)
    keepouts = (_keepout(1, _box(20, 10, 22, 14.85)), _keepout(2, _box(20, 15.15, 22, 20)))
    return _with_zones(design, zones=(zone,), keepouts=keepouts)


def tips() -> Design:
    bench = TieBoard()
    gnd = bench.net("GND")
    bench.place("J1", ONE, _p(15, 15), {"1": "GND"})
    design = bench.build()
    finger = tuple(
        _p(x, y)
        for x, y in (
            (10, 10), (20, 10), (20, 14.85), (23, 14.85), (23, 15.15), (20, 15.15), (20, 20), (10, 20),
        )
    )  # fmt: skip
    zone = dataclasses.replace(_gnd_zone(_box(10, 5, 30, 25), finger, _box(25, 10, 25.3, 15)), net_id=gnd)
    return _with_zones(design, zones=(zone,))


def loop(*, far: float = 30) -> Design:
    bench = TieBoard()
    v33, gnd = bench.net("+3V3"), bench.net("GND")
    bench.place("U1", IC, _p(20, 20), {"4": "+3V3", "2": "GND"})
    bench.place("C1", CAP, _p(21.5, 20), {"1": "+3V3", "2": "GND"})
    bench.place("C2", CAP, _p(far, 20), {"1": "+3V3", "2": "GND"})
    design = bench.build()
    tracks = (
        _track(1, v33, _p(20, 20), _p(21.5, 20)),
        _track(2, v33, _p(21.5, 20), _p(far, 20)),
        _track(3, gnd, _p(20, 22), _p(21.5, 22)),
    )
    return _with_zones(design, tracks=tracks)


def balance() -> Design:
    bench = TieBoard()
    gnd, n = bench.net("GND"), bench.net("N")
    bench.place("R1", RESISTOR, _p(30, 20), {"1": "GND", "2": "N"})
    design = bench.build()
    zone = dataclasses.replace(_gnd_zone(_box(20, 15, 30, 25), _box(20, 15, 30, 25)), net_id=gnd)
    track = Track(
        id="trk_00000000-0000-4000-8000-000000000001",
        start=_p(31.5, 20),
        end=_p(40, 20),
        width=MM // 2,
        layer="F.Cu",
        net_id=n,
    )
    return _with_zones(design, zones=(zone,), tracks=(track,))


__all__ = ["GRID", "balance", "loop", "neck", "tips"]
