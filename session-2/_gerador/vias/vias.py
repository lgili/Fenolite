# SPDX-License-Identifier: CC0-1.0
# Copyright (c) 2026 Fenolite contributors
"""Session 2, Part V: a board for Altium's "Remove Unused Pad Shapes" on vias (change c0132,
hypothesis ``H-A-IMP-VIA-PADLESS``).

Six copper layers, two of them internal planes on ``GND``: Top Layer (id 1), Internal Plane 1, Mid-Layer 2
(id 3), Internal Plane 2, Mid-Layer 4 (id 5), Bottom Layer (id 32). So the two inner SIGNAL layers have the
ids 3 and 5, and their positions among the signal layers (2 and 3) differ from their ids: the saved via
record tells which of the two indexes the table at offset 209.

- via ``A`` (net ``SIG``): tracks on the Top Layer and the Bottom Layer only. After the tool its pad shape
  should go on Mid-Layer 2 and Mid-Layer 4.
- via ``B`` (net ``AUX``): tracks on the Top Layer and Mid-Layer 4 only. After the tool its pad shape
  should go on Mid-Layer 2 and, unless the end layers are kept, on the Bottom Layer.

Built as ``fenolite kit build`` builds a sample (``construir.py``). Every value is a round number chosen
for this sample. Authored for this pack; nothing here comes from any other project.
"""

import dataclasses

from fenolite.core.coords import Point
from fenolite.core.ids import derived_id
from fenolite.dsl import BOARD_ORIGIN, Design, Net, Part, connect, mm
from fenolite.model.board import Layer, StackLayer, Stackup, Track, Via

NAME = "vias"
LAYERS = ("F.Cu", "In1.Cu", "In2.Cu", "In3.Cu", "In4.Cu", "B.Cu")
KIT = {"copper": 6, "planes": {"In1.Cu": "GND", "In3.Cu": "GND"}}

design = Design(NAME)
design.board(mm(40), mm(25))

HEADER = "Fenolite:Header_1x2_P2.54"
j1 = Part("J1", "Fenolite:Connector_2", footprint=HEADER, value="SIG_IN")
j2 = Part("J2", "Fenolite:Connector_2", footprint=HEADER, value="SIG_OUT")
j3 = Part("J3", "Fenolite:Connector_2", footprint=HEADER, value="AUX_IN")
j4 = Part("J4", "Fenolite:Connector_2", footprint=HEADER, value="AUX_OUT")
design.add(j1, j2, j3, j4)

sig, aux, gnd = Net("SIG"), Net("AUX"), Net("GND")
connect(sig, j1[1], j2[1])
connect(aux, j3[1], j4[1])
connect(gnd, j1[2], j2[2], j3[2], j4[2])

j1.place(mm(6), mm(7))
j2.place(mm(34), mm(7))
j3.place(mm(6), mm(17))
j4.place(mm(34), mm(17))

MM = 1_000_000


def at(x, y):
    """A point given in millimetres from the upper-left corner of the outline, in the frame of ``place()``."""
    return Point(BOARD_ORIGIN.x + round(x * MM), BOARD_ORIGIN.y + round(y * MM))


def _id(prefix, key):
    return derived_id(prefix, "dsl", f"{NAME}:{key}")


STACKUP = (
    ("F.Cu", "copper", 35_000),
    ("dielectric 1", "dielectric", 200_000),
    ("In1.Cu", "copper", 17_500),
    ("dielectric 2", "dielectric", 200_000),
    ("In2.Cu", "copper", 17_500),
    ("dielectric 3", "dielectric", 600_000),
    ("In3.Cu", "copper", 17_500),
    ("dielectric 4", "dielectric", 200_000),
    ("In4.Cu", "copper", 17_500),
    ("dielectric 5", "dielectric", 200_000),
    ("B.Cu", "copper", 35_000),
)
"""(name, kind, thickness in nm), top to bottom."""
PIN1_J1, PIN1_J2, PIN1_J3, PIN1_J4 = (6.0, 8.27), (34.0, 8.27), (6.0, 18.27), (34.0, 18.27)
"""Pad 1 of each header: 1.27 mm below the header's origin."""
VIAS = (
    ("A", "SIG", (20.0, 8.27)),
    ("B", "AUX", (20.0, 18.27)),
)
"""(key, net, position): through vias, 0.6 mm with a 0.3 mm hole."""
TRACKS = (
    ("a1", "F.Cu", "SIG", PIN1_J1, (20.0, 8.27)),
    ("a2", "B.Cu", "SIG", (20.0, 8.27), PIN1_J2),
    ("b1", "F.Cu", "AUX", PIN1_J3, (20.0, 18.27)),
    ("b2", "In4.Cu", "AUX", (20.0, 18.27), PIN1_J4),
)
"""(key, layer, net, start, end), 0.25 mm wide."""


def kit_model(model):
    """``model`` with the six copper layers, the stack-up, the two vias and their tracks."""
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
                    material="FR-4" if kind == "dielectric" else "",
                    epsilon_r="4.5" if kind == "dielectric" else "",
                )
                for name, kind, thickness in STACKUP
            ),
        ),
        tracks=tuple(
            Track(id=_id("trk", k), start=at(*a), end=at(*b), width=250_000, layer=layer, net_id=nets[net])
            for k, layer, net, a, b in TRACKS
        ),
        vias=tuple(
            Via(
                id=_id("via", k),
                position=at(*xy),
                diameter=600_000,
                drill=300_000,
                layers=("F.Cu", "B.Cu"),
                net_id=nets[net],
                via_type="through",
            )
            for k, net, xy in VIAS
        ),
    )
    return dataclasses.replace(model, board=board)
