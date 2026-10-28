# SPDX-License-Identifier: CC0-1.0
# Authored for Fenolite as an example; no file, value, name or layout comes from any other project.
"""Kit sample ``pour4``: probes of Altium's polygon pour on the inner layers of four (change c0215).

It is a sample of group K6 of the Altium verification kit (``docs/altium-kit.md``), as ``pour`` is, on a
60 mm by 30 mm board of four copper layers. Each probe is its own polygon on its own net, so that a
difference points to one input of ``docs/formats/altium/pcb-pour.md``:

- P0, a sentinel on ``In1.Cu`` that must pour copper;
- P1 on ``In1.Cu``: the clearance of 0.2 mm from objects of ``P1X`` that reach the layer, a through-hole
  pad, a through via, a blind via from ``F.Cu`` to ``In1.Cu`` and a buried via from ``In1.Cu`` to
  ``In2.Cu``, and none from a blind via from ``In2.Cu`` to ``B.Cu``, which has no copper there;
- P2 on ``In2.Cu``: a thermal relief to a through-hole pad of ``P2T``, and the direct joint of a via of
  ``P2T`` that ends on the layer.

``POINTS`` declares, per polygon, where copper must stay (``True``) or be gone (``False``), in millimetres
from the upper-left corner of the outline. Every value is a round number chosen for this sample; none is a
requirement of any standard.
"""

import dataclasses

from fenolite.core.coords import Point
from fenolite.core.ids import derived_id
from fenolite.dsl import BOARD_ORIGIN, Design, Net, mm

NAME = "pour4"
KIT = {"pour": "computed", "copper": 4}
design = Design(NAME)
design.board(mm(60), mm(30), copper=4)
design.rules.minimum(clearance=mm(0.2))

NETS = {name: Net(name) for name in ("P0", "P1", "P1X", "P2T")}


def rect(x0, y0, x1, y1):
    return [(mm(x0), mm(y0)), (mm(x1), mm(y0)), (mm(x1), mm(y1)), (mm(x0), mm(y1))]


def pad(ref, name, x, y, size=1.6, drill=0.8):
    design.test_point(ref, NETS[name], mm(x), mm(y), size=mm(size), drill=mm(drill))


design.zone(NETS["P0"], layers=("In1.Cu",), name="P0", outline=rect(1, 1, 14, 29))
pad("TP0", "P0", 4, 4)
design.zone(NETS["P1"], layers=("In1.Cu",), name="P1", outline=rect(16, 1, 38, 29))
pad("TP1", "P1", 19, 4)
pad("TP1X", "P1X", 22, 15)
design.zone(NETS["P2T"], layers=("In2.Cu",), name="P2T", outline=rect(40, 1, 59, 29), thermal_gap=mm(0.3),
            thermal_spoke_width=mm(0.3))  # fmt: skip
pad("TP2T", "P2T", 46, 15)

MM = 1_000_000


def at(x, y):
    """A point given in millimetres from the upper-left corner of the outline, in the frame of ``place()``."""
    return Point(BOARD_ORIGIN.x + round(x * MM), BOARD_ORIGIN.y + round(y * MM))


VIAS = (
    ("p1_through", "P1X", (28.0, 8.0), ("F.Cu", "B.Cu")),
    ("p1_blind_top", "P1X", (28.0, 15.0), ("F.Cu", "In1.Cu")),
    ("p1_buried", "P1X", (28.0, 22.0), ("In1.Cu", "In2.Cu")),
    ("p1_blind_bottom", "P1X", (34.0, 15.0), ("In2.Cu", "B.Cu")),
    ("p2_via", "P2T", (54.0, 15.0), ("F.Cu", "In2.Cu")),
)
"""(key, net, position, the two layers it spans) of the vias of 0.6 mm with a 0.3 mm drill."""

POINTS = (
    ("P0", 8.0, 20.0, True),
    ("P1", 28.0, 8.45, False),  # 0.15 mm from the through via, inside the 0.2 mm
    ("P1", 28.0, 15.45, False),  # by the blind via that ends on In1.Cu
    ("P1", 28.0, 22.45, False),  # by the buried via
    ("P1", 34.0, 15.0, True),  # the blind via from In2.Cu has no copper on In1.Cu: the pour covers its place
    ("P1", 22.0, 15.85, False),  # 0.05 mm from the through-hole pad
    ("P2T", 46.95, 15.0, True),  # on a conductor of the relief
    ("P2T", 46.67, 14.33, False),  # in the air gap, off the conductors
    ("P2T", 54.0, 15.45, True),  # a via is joined directly
)
"""(polygon, x, y, whether copper must be there), in millimetres from the upper-left corner."""


def kit_model(model):
    """``model`` with the sample's vias."""
    from fenolite.model.board import Via

    nets = {item.name: item.id for item in model.circuit.nets}
    vias = tuple(
        Via(id=derived_id("via", "dsl", f"{NAME}:{key}"), position=at(*xy), diameter=600_000, drill=300_000,
            layers=layers, net_id=nets[name])
        for key, name, xy, layers in VIAS
    )  # fmt: skip
    return dataclasses.replace(model, board=dataclasses.replace(model.board, vias=vias))
