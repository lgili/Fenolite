# SPDX-License-Identifier: CC0-1.0
# Authored for Fenolite as an example; no file, value, name or layout comes from any other project.
"""Kit sample ``routed``: the circuit of ``flat`` with copper, a polygon, rules and two planted violations.

It is one of the five samples of the Altium verification kit (``docs/altium-kit.md``). ``kit_model`` puts
the copper into the model, in millimetres from the upper-left corner of the 50 mm by 30 mm outline:

- ``LED_DRV`` from pin 2 of ``U1`` round the controller to pad 1 of ``R1``, and ``LED_A`` from pad 2 of
  ``R1`` to pad 2 of ``D1``, both 0.25 mm wide on the top layer;
- ``VIN`` from pin 1 of ``J1`` to pin 1 of ``U1``, 0.6 mm wide; ``GND`` from pad 1 of ``D1`` to a via,
  0.6 mm wide, and one ``GND`` polygon on the bottom layer, 1 mm inside the outline;
- planted violation 1: one ``VIN`` stub that is 0.5 mm wide, below the 0.6 mm minimum of the width rule
  of the net class ``PWR``;
- planted violation 2: one ``VIN`` via and one ``LED_A`` via whose edges are 0.6 mm apart, inside the
  1.5 mm that the clearance rule between those two nets asks for. The two vias join no track, so that
  no second pair of objects comes inside that distance.

Every value is a round number chosen for this sample; none is a requirement of any standard.
"""

import dataclasses

from fenolite.core.coords import Point
from fenolite.core.ids import derived_id
from fenolite.dsl import BOARD_ORIGIN, Design, Net, Part, Power, connect, mm, select
from fenolite.model.board import Track, Via, Zone

NAME = "routed"
design = Design(NAME)
design.board(mm(50), mm(30))

j1 = Part("J1", "Fenolite:Connector_2", footprint="Fenolite:Header_1x2_P2.54", value="SUPPLY")
u1 = Part("U1", "Fenolite:Microcontroller", footprint="Fenolite:DIP8_Microchip_P", value="MCU")
r1 = Part("R1", "Fenolite:Resistor", footprint="Fenolite:Chip_0603", value="330")
# The LED land numbers its pads as the manufacturer does, pad 1 the cathode, while the symbol's pin 1 is the
# anode: the map puts the anode (pin 1) on pad 2 and the cathode (pin 2) on pad 1.
d1 = Part(
    "D1",
    "Fenolite:LED",
    footprint="Fenolite:LED0603_Kingbright_APT1608SURCK",
    value="red",
    pad_map={"1": "2", "2": "1"},
)
design.add(j1, u1, r1, d1)

vin, gnd, led_drv, led_a = Net("VIN"), Net("GND"), Net("LED_DRV"), Net("LED_A")
connect(vin, j1[1], u1[1])
connect(gnd, j1[2], u1[8], d1["K"])
connect(led_drv, u1[2], r1[1])
connect(led_a, r1[2], d1["A"])
design.add(Power(vin, gnd))
design.rules.netclass("PWR", clearance=mm(0.2), track_width=mm(0.6), nets=(vin, gnd))
design.rules.rule("gap", "clearance", min=mm(0.15))
design.rules.rule(
    "apart", "clearance", where=select.net("VIN"), between=select.net("LED_A"), min=mm(1.5), priority=1
)
design.rules.rule("w", "track_width", min=mm(0.15), opt=mm(0.25), max=mm(2))
design.rules.rule(
    "w_pwr", "track_width", where=select.netclass("PWR"), min=mm(0.6), opt=mm(0.6), max=mm(2), priority=1
)

j1.place(mm(6), mm(15))
u1.place(mm(20), mm(15), locked=True)
r1.place(mm(34), mm(9))
d1.place(mm(42), mm(20))

MM = 1_000_000


def at(x, y):
    """A point given in millimetres from the upper-left corner of the outline, in the frame of ``place()``."""
    return Point(BOARD_ORIGIN.x + round(x * MM), BOARD_ORIGIN.y + round(y * MM))


def _id(prefix, key):
    return derived_id(prefix, "dsl", f"{NAME}:{key}")


SIGNAL, POWER, NARROW = 250_000, 600_000, 500_000
TRACKS = (
    ("t1", "LED_DRV", (16.19, 16.27), (12.0, 16.27), SIGNAL),
    ("t2", "LED_DRV", (12.0, 16.27), (12.0, 6.0), SIGNAL),
    ("t3", "LED_DRV", (12.0, 6.0), (33.2, 6.0), SIGNAL),
    ("t4", "LED_DRV", (33.2, 6.0), (33.2, 9.0), SIGNAL),
    ("t5", "LED_A", (34.8, 9.0), (42.825, 9.0), SIGNAL),
    ("t6", "LED_A", (42.825, 9.0), (42.825, 20.0), SIGNAL),
    ("t7", "VIN", (6.0, 16.27), (6.0, 18.81), POWER),
    ("t8", "VIN", (6.0, 18.81), (16.19, 18.81), POWER),
    ("t9", "GND", (41.175, 20.0), (41.175, 24.0), POWER),
    ("stub", "VIN", (6.0, 16.27), (2.5, 16.27), NARROW),
)
"""(key, net, start, end, width in nm), all on the top layer; ``stub`` is planted violation 1."""
VIAS = (("v1", "GND", (41.175, 24.0)), ("v2", "VIN", (26.0, 26.0)), ("v3", "LED_A", (27.2, 26.0)))
"""(key, net, position); ``v2`` and ``v3`` are planted violation 2."""
POLYGON = ((1.0, 1.0), (49.0, 1.0), (49.0, 29.0), (1.0, 29.0))


def kit_model(model):
    """``model`` with the sample's tracks, vias and polygon on its board."""
    nets = {net.name: net.id for net in model.circuit.nets}
    board = dataclasses.replace(
        model.board,
        tracks=tuple(
            Track(id=_id("trk", key), start=at(*a), end=at(*b), width=width, layer="F.Cu", net_id=nets[net])
            for key, net, a, b, width in TRACKS
        ),
        vias=tuple(
            Via(
                id=_id("via", key),
                position=at(*xy),
                diameter=600_000,
                drill=300_000,
                layers=("F.Cu", "B.Cu"),
                net_id=nets[net],
            )
            for key, net, xy in VIAS
        ),
        zones=(
            Zone(
                id=_id("zon", "z1"),
                outline=tuple(at(*p) for p in POLYGON),
                layers=("B.Cu",),
                net_id=nets["GND"],
            ),
        ),
    )
    return dataclasses.replace(model, board=board)
