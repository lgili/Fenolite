# SPDX-License-Identifier: CC0-1.0
# Authored for Fenolite as an example; no file, value, name or layout comes from any other project.
"""Kit sample ``board6``: the circuit of ``flat`` on six copper layers, with one board item of every kind.

It is one of the five samples of the Altium verification kit (``docs/altium-kit.md``). The DSL declares
boards of two or four copper layers, so ``KIT`` gives the build six layers with ``In2.Cu`` as a plane on
``GND``, and ``kit_model`` puts the stack-up and the items into the model, in millimetres from the
upper-left corner of the 50 mm by 30 mm outline:

- three vias: one through, one blind from the top layer to ``In1.Cu``, one buried from ``In1.Cu`` to the
  plane;
- tracks on the top layer, on three inner signal layers and on the bottom layer;
- four texts on four layers, one with accented characters and one turned by 90 degrees;
- a line, an arc, a circle, a rectangle and a filled triangle;
- one keep-out for tracks and vias on every copper layer, and one non-plated hole of 3.2 mm;
- two ``GND`` polygons, on the top and on the bottom layer.

Every value is a round number chosen for this sample; none is a requirement of any standard.
"""

import dataclasses

from fenolite.core.coords import Point, Size
from fenolite.core.ids import derived_id
from fenolite.dsl import BOARD_ORIGIN, Design, Net, Part, Power, connect, mm
from fenolite.model.board import Graphic, Hole, Keepout, Layer, StackLayer, Stackup, Text, Track, Via, Zone

NAME = "board6"
LAYERS = ("F.Cu", "In1.Cu", "In2.Cu", "In3.Cu", "In4.Cu", "B.Cu")
KIT = {"copper": 6, "planes": {"In2.Cu": "GND"}}

design = Design(NAME)
design.board(mm(50), mm(30))

j1 = Part("J1", "Fenolite:Connector_2", footprint="Fenolite:Header_1x2_P2.54", value="SUPPLY")
u1 = Part("U1", "Fenolite:Microcontroller", footprint="Fenolite:DIP8_Microchip_P", value="MCU")
r1 = Part("R1", "Fenolite:Resistor", footprint="Fenolite:Chip_0603", value="330")
d1 = Part("D1", "Fenolite:LED", footprint="Fenolite:LED0603_Kingbright_APT1608SURCK", value="red")
design.add(j1, u1, r1, d1)

vin, gnd, led_drv, led_a = Net("VIN"), Net("GND"), Net("LED_DRV"), Net("LED_A")
connect(vin, j1[1], u1[1])
connect(gnd, j1[2], u1[8], d1[1])
connect(led_drv, u1[2], r1[1])
connect(led_a, r1[2], d1[2])
design.add(Power(vin, gnd))
design.rules.netclass("PWR", clearance=mm(0.2), track_width=mm(0.5), nets=(vin, gnd))

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


STACKUP = (
    ("F.Cu", "copper", 35_000, "", ""),
    ("dielectric 1", "dielectric", 110_000, "FR-4 prepreg", "4.2"),
    ("In1.Cu", "copper", 17_500, "", ""),
    ("dielectric 2", "dielectric", 200_000, "FR-4 core", "4.5"),
    ("In2.Cu", "copper", 17_500, "", ""),
    ("dielectric 3", "dielectric", 800_000, "FR-4 prepreg", "4.2"),
    ("In3.Cu", "copper", 17_500, "", ""),
    ("dielectric 4", "dielectric", 200_000, "FR-4 core", "4.5"),
    ("In4.Cu", "copper", 17_500, "", ""),
    ("dielectric 5", "dielectric", 110_000, "FR-4 prepreg", "4.2"),
    ("B.Cu", "copper", 35_000, "", ""),
)
"""(name, kind, thickness in nm, material, dielectric constant), top to bottom."""
VIAS = (
    ("v1", "VIN", (10.0, 18.81), ("F.Cu", "B.Cu"), "through"),
    ("v2", "LED_A", (38.0, 9.0), ("F.Cu", "In1.Cu"), "blind"),
    ("v3", "GND", (20.0, 24.0), ("In1.Cu", "In2.Cu"), "buried"),
)
"""(key, net, position, span, type)."""
TRACKS = (
    ("t1", "F.Cu", "LED_DRV", (16.19, 16.27), (12.0, 16.27), 250_000),
    ("t2", "F.Cu", "LED_DRV", (12.0, 16.27), (12.0, 6.0), 250_000),
    ("t3", "F.Cu", "LED_DRV", (12.0, 6.0), (33.2, 6.0), 250_000),
    ("t4", "F.Cu", "LED_DRV", (33.2, 6.0), (33.2, 9.0), 250_000),
    ("t5", "F.Cu", "LED_A", (34.8, 9.0), (38.0, 9.0), 250_000),
    ("t6", "In1.Cu", "LED_A", (38.0, 9.0), (42.825, 20.0), 250_000),
    ("t7", "In1.Cu", "GND", (20.0, 24.0), (26.0, 24.0), 500_000),
    ("t8", "F.Cu", "VIN", (6.0, 16.27), (6.0, 18.81), 500_000),
    ("t9", "F.Cu", "VIN", (6.0, 18.81), (16.19, 18.81), 500_000),
    ("t10", "In3.Cu", "VIN", (10.0, 18.81), (10.0, 26.0), 500_000),
    ("t11", "In4.Cu", "VIN", (10.0, 18.81), (4.0, 22.0), 500_000),
    ("t12", "B.Cu", "VIN", (10.0, 18.81), (14.0, 22.0), 500_000),
)
"""(key, layer, net, start, end, width in nm)."""
TEXTS = (
    ("x1", "Tensão 5 V", "F.SilkS", (22.0, 4.0), 1.0, 0.15, 0),
    ("x2", "BOARD6 REV A", "B.SilkS", (30.0, 27.0), 1.2, 0.18, 0),
    ("x3", "ASSEMBLY TOP", "F.Fab", (3.0, 28.0), 0.8, 0.12, 0),
    ("x4", "BOTTOM", "B.Fab", (47.0, 12.0), 1.0, 0.15, 90),
)
"""(key, string, layer, position, height in mm, stroke in mm, rotation in degrees)."""
GRAPHICS = (
    ("g1", "line", "F.Fab", ((2.0, 2.0), (12.0, 2.0)), 0.1, False),
    ("g2", "arc", "F.SilkS", ((44.0, 4.0), (45.414214, 4.585786), (46.0, 6.0)), 0.15, False),
    ("g3", "circle", "F.SilkS", ((4.0, 25.0), (6.0, 25.0)), 0.15, False),
    ("g4", "rect", "B.Fab", ((36.0, 22.0), (44.0, 27.0)), 0.1, False),
    ("g5", "polygon", "F.SilkS", ((40.0, 2.0), (42.0, 2.0), (41.0, 3.5)), 0.0, True),
)
"""(key, kind, layer, points, width in mm, filled)."""
KEEPOUT = ((27.0, 12.0), (33.0, 12.0), (33.0, 17.0), (27.0, 17.0))
HOLE = ((4.0, 25.0), 3_200_000)
POLYGON = ((1.0, 1.0), (49.0, 1.0), (49.0, 29.0), (1.0, 29.0))


def kit_model(model):
    """``model`` with the six copper layers, the stack-up and the sample's board items."""
    nets = {net.name: net.id for net in model.circuit.nets}
    board = dataclasses.replace(
        model.board,
        layers=tuple(
            Layer(id=_id("lay", name), name=name, kind="copper", ordinal=n) for n, name in enumerate(LAYERS)
        ),
        stackup=Stackup(
            id=_id("stk", "stackup"),
            layers=tuple(
                StackLayer(
                    id=_id("sly", name),
                    name=name,
                    kind=kind,
                    thickness=thickness,
                    material=material,
                    epsilon_r=epsilon,
                )
                for name, kind, thickness, material, epsilon in STACKUP
            ),
        ),
        tracks=tuple(
            Track(id=_id("trk", k), start=at(*a), end=at(*b), width=width, layer=layer, net_id=nets[net])
            for k, layer, net, a, b, width in TRACKS
        ),
        vias=tuple(
            Via(
                id=_id("via", k),
                position=at(*xy),
                diameter=600_000,
                drill=300_000,
                layers=span,
                net_id=nets[net],
                via_type=kind,
            )
            for k, net, xy, span, kind in VIAS
        ),
        zones=tuple(
            Zone(
                id=_id("zon", layer),
                outline=tuple(at(*p) for p in POLYGON),
                layers=(layer,),
                net_id=nets["GND"],
            )
            for layer in ("F.Cu", "B.Cu")
        ),
        keepouts=(
            Keepout(
                id=_id("kpo", "k1"),
                outline=tuple(at(*p) for p in KEEPOUT),
                layers=LAYERS,
                no_tracks=True,
                no_vias=True,
            ),
        ),
        texts=tuple(
            Text(
                id=_id("txt", k),
                text=string,
                position=at(*xy),
                layer=layer,
                size=Size(round(height * MM), round(height * MM)),
                thickness=round(stroke * MM),
                rotation=rotation * 1_000_000,
            )
            for k, string, layer, xy, height, stroke, rotation in TEXTS
        ),
        graphics=tuple(
            Graphic(
                id=_id("gfx", k),
                kind=kind,
                layer=layer,
                points=tuple(at(*p) for p in points),
                width=round(width * MM),
                filled=filled,
            )
            for k, kind, layer, points, width, filled in GRAPHICS
        ),
        holes=(Hole(id=_id("hol", "h1"), position=at(*HOLE[0]), drill=HOLE[1]),),
    )
    return dataclasses.replace(model, board=board)
