# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The practice-check benches of change c0204: authored two-layer boards built with ``tests/_ties.py``. No
file is read, nothing comes from a library, and every value is a round invented one.

- ``cutout``: a ``BUS`` zone on ``F.Cu`` from x 2 mm to 54 mm, y 2 mm to 38 mm, with ``J1-1`` at (10, 20) mm
  and ``D1-2`` at (52, 20) mm. Its saved fill is the whole box. ``keepout`` adds a keep-out that forbids pours
  from x 28 mm to 32 mm across the whole board, drawn after the fill: the fill is stale, and the simulated
  pour leaves ``D1-2`` alone. ``fill`` false leaves the zone unfilled.
- ``dead``: a ``GND`` zone with two saved fill polygons, one under ``J1-1`` and one, x 40–50 mm, joined to
  nothing, and a ``GND`` track 20 mm from every pad.
- ``decoupling``: ``U1`` with the supply pin 4 on ``+3V3`` at (20, 20) mm and the pin 2 on ``GND`` 2 mm
  below; ``C1`` 1.5 mm to the right along a track, ``C2`` 10 mm along copper.
- ``bodies``: ``C1``, a part with a body (and a courtyard) of 10 mm by 10 mm centred at (30, 20) mm, a track
  of the class ``HV`` across it on ``F.Cu`` and a track of the class ``Default`` across it on ``B.Cu``.
- ``relief``: a ``GND`` pad of 2 mm by 2 mm at (30, 20) mm in a zone whose fill leaves a gap of 0.5 mm
  around it, crossed by four spokes 0.5 mm wide.
- ``coupling``: ``ISENSE`` from x 10 mm to 50 mm at y 20 mm, ``PHASE_U`` beside it for 10 mm at a gap of
  0.5 mm, ``LED`` beside it for 30 mm at a gap of 3 mm, and ``PHASE_V`` under it on ``B.Cu`` for 5 mm;
  tracks 0.25 mm wide.
"""

from __future__ import annotations

import dataclasses

from _groundties import ONE, _box, _p, _track, _zone
from _ties import MM, TieBoard

from fenolite.core.coords import Point
from fenolite.dsl import Footprint, nm
from fenolite.model.board import ComponentBody, Keepout, ZoneFill, ZoneSettings
from fenolite.model.circuit import NetClass, Pin
from fenolite.model.design import Design
from fenolite.model.library import FootprintDef

GRID = MM // 4
"""The raster of the tests: 0.25 mm."""
LOOP = 3 * MM * MM
"""The loop of ``U1-4``, ``C1-1``, ``C1-2``, ``U1-2``: 1.5 mm by 2 mm."""


def _part(
    name: str, pads: dict[str, tuple[float, float]], size: float = 1.0, courtyard: float = 0.0
) -> FootprintDef:
    footprint = Footprint("Practice", name, kind="smd")
    for number, (x, y) in pads.items():
        footprint.pad(number, at=(nm(round(x * MM)), nm(round(y * MM))), size=(nm(round(size * MM)),) * 2)
    if courtyard:
        half = round(courtyard * MM / 2)
        footprint.rect((nm(-half), nm(-half)), (nm(half), nm(half)), layer="F.CrtYd", width=nm(MM // 20))
    return footprint.definition


DIODE = _part("DIODE", {"1": (2.5, 0), "2": (-2.5, 0)})
IC = _part("IC", {"4": (0, 0), "2": (0, 2)})
CAP = _part("CAP", {"1": (0, 0), "2": (0, 2)})
CAN = _part("CAN", {"1": (-2, 0), "2": (2, 0)}, courtyard=10)
PAD = _part("PAD", {"1": (0, 0)}, size=2.0)


def _with_zones(design: Design, **items: object) -> Design:
    board = design.board
    assert board is not None
    return dataclasses.replace(design, board=dataclasses.replace(board, **items))


def cutout(*, keepout: bool = True, fill: bool = True) -> Design:
    bench = TieBoard()
    bus = bench.net("BUS")
    bench.place("J1", ONE, _p(10, 20), {"1": "BUS"})
    bench.place("D1", DIODE, _p(54.5, 20), {"1": "D1_1", "2": "BUS"})
    design = bench.build()
    zone = _zone(1, bus, _box(2, 2, 54, 38), fill=fill)
    keepouts = (
        (
            Keepout(
                id="kpo_00000000-0000-4000-8000-000000000001",
                outline=_box(28, 0, 32, 40),
                layers=("F.Cu",),
                no_copper_pour=True,
                name="CUT",
            ),
        )
        if keepout
        else ()
    )
    return _with_zones(design, zones=(zone,), keepouts=keepouts)


def dead() -> Design:
    bench = TieBoard()
    gnd = bench.net("GND")
    bench.place("J1", ONE, _p(10, 20), {"1": "GND"})
    bench.place("J2", ONE, _p(30, 20), {"1": "GND"})
    design = bench.build()
    zone = dataclasses.replace(
        _zone(1, gnd, _box(2, 2, 58, 38)),
        fills=(ZoneFill("F.Cu", _box(5, 15, 15, 25)), ZoneFill("F.Cu", _box(40, 5, 50, 15))),
    )
    tracks = (
        _track(1, gnd, _p(10, 20), _p(30, 20)),
        _track(2, gnd, _p(30, 35), _p(40, 35), "B.Cu"),
    )
    return _with_zones(design, zones=(zone,), tracks=tracks)


def decoupling() -> Design:
    bench = TieBoard()
    v33, gnd = bench.net("+3V3"), bench.net("GND")
    bench.place("U1", IC, _p(20, 20), {"4": "+3V3", "2": "GND"})
    bench.place("C1", CAP, _p(21.5, 20), {"1": "+3V3", "2": "GND"})
    bench.place("C2", CAP, _p(30, 20), {"1": "+3V3", "2": "GND"})
    design = bench.build()
    tracks = (
        _track(1, v33, _p(20, 20), _p(21.5, 20)),
        _track(2, v33, _p(21.5, 20), _p(30, 20)),
        _track(3, gnd, _p(20, 22), _p(21.5, 22)),
    )
    components = tuple(
        dataclasses.replace(
            c,
            pins=(
                Pin(id="pin_u1_2", number="2", name="GND", etype="power_in"),
                Pin(id="pin_u1_4", number="4", name="VDD", etype="power_in"),
            ),
        )
        if c.ref == "U1"
        else c
        for c in design.circuit.components
    )
    design = dataclasses.replace(design, circuit=dataclasses.replace(design.circuit, components=components))
    return _with_zones(design, tracks=tracks)


def bodies() -> Design:
    bench = TieBoard()
    hv, lv = bench.net("HV"), bench.net("LV")
    bench.place("C1", CAN, _p(30, 20), {"1": "C1_1", "2": "C1_2"})
    design = bench.build()
    board = design.board
    assert board is not None
    half = 5 * MM
    body = ComponentBody(
        id="bdy_00000000-0000-4000-8000-000000000001",
        kind="extruded",
        height=12 * MM,
        outline=(Point(-half, -half), Point(half, -half), Point(half, half), Point(-half, half)),
    )
    footprints = tuple(dataclasses.replace(fp, bodies=(body,)) for fp in board.footprints)
    hv_class = NetClass(id="cls_hv", name="HV")
    nets = tuple(
        dataclasses.replace(net, netclass_id=hv_class.id) if net.id == hv else net
        for net in design.circuit.nets
    )
    circuit = dataclasses.replace(
        design.circuit, nets=nets, netclasses=(*design.circuit.netclasses, hv_class)
    )
    tracks = (_track(1, hv, _p(20, 20), _p(40, 20)), _track(2, lv, _p(20, 18), _p(40, 18), "B.Cu"))
    design = dataclasses.replace(design, circuit=circuit)
    return _with_zones(design, footprints=footprints, tracks=tracks)


def relief(*, fill: bool = True) -> Design:
    bench = TieBoard()
    gnd = bench.net("GND")
    bench.place("P1", PAD, _p(30, 20), {"1": "GND"})
    design = bench.build()
    bands = (
        _box(10, 5, 50, 18.5),
        _box(10, 21.5, 50, 35),
        _box(10, 18.5, 28.5, 21.5),
        _box(31.5, 18.5, 50, 21.5),
    )
    spokes = (
        _box(29.75, 18, 30.25, 19),
        _box(29.75, 21, 30.25, 22),
        _box(28, 19.75, 29, 20.25),
        _box(31, 19.75, 32, 20.25),
    )
    zone = dataclasses.replace(
        _zone(1, gnd, _box(10, 5, 50, 35), fill=fill),
        fills=tuple(ZoneFill("F.Cu", ring) for ring in (*bands, *spokes)) if fill else (),
        settings=ZoneSettings(thermal_gap=MM // 2, thermal_spoke_width=MM // 2),
    )
    return _with_zones(design, zones=(zone,))


def coupling() -> Design:
    bench = TieBoard()
    names = ("ISENSE", "PHASE_U", "LED", "PHASE_V")
    ids = {name: bench.net(name) for name in names}
    design = bench.build()
    tracks = (
        _track(1, ids["ISENSE"], _p(10, 20), _p(50, 20)),
        _track(2, ids["PHASE_U"], _p(15, 20.75), _p(25, 20.75)),
        _track(3, ids["LED"], _p(15, 16.75), _p(45, 16.75)),
        _track(4, ids["PHASE_V"], _p(30, 20), _p(35, 20), "B.Cu"),
    )
    return _with_zones(design, tracks=tracks)


__all__ = ["GRID", "LOOP", "bodies", "coupling", "cutout", "dead", "decoupling", "relief"]
