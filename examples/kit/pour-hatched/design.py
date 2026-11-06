# SPDX-License-Identifier: CC0-1.0
# Authored for Fenolite as an example; no file, value, name or layout comes from any other project.
"""Kit sample ``pour-hatched``: Altium's hatched pour and two outlines it may fill (change c0463, task 3.1).

It is a sample of group K6 of the Altium verification kit (``docs/altium-kit.md``), built like ``pour``: two
free documents, ``computed/`` and ``reference/``, and ``probes.json``. Altium pours ``reference/`` and the
saved board shows (S-2223) how a hatch is made: which tracks, at which pitch, aligned to which origin, and
how they are clipped to the solid pour's area. Every polygon is its own probe and its own net on the top
layer. Lengths are in mils from the upper-left corner of the 4000 by 2400 mil outline, so every value is a
whole number of the document's units:

- P0, a solid sentinel that must pour copper;
- P1 to P4, one polygon for each hatch style: ``90Degree``, ``45Degree``, ``Horizontal`` and ``Vertical``,
  with a grid of 50 mil and tracks of 10 mil, each 800 by 800 mil around a pad of its net and a round pad of
  another net (``PX``) that its hatch must clear by the 8 mil clearance;
- P5 and P6, two ``90Degree`` polygons of the same size whose corners lie 13 mil and 29 mil off the 50 mil
  grid: the tracks of the two show whether the grid starts at the board origin, at the polygon or at its
  first vertex;
- P7, a ``45Degree`` polygon of five vertices, none of its edges on a grid line, for the clipping of the
  tracks at a slanted edge;
- P8, a solid ring that touches itself at one vertex (two squares joined at a corner);
- P9, a solid ring that crosses itself (a bow tie).

``POINTS`` declares copper at the middle of each solid probe only: no point of a hatched polygon is known
before the sample's record exists (design of c0463, D3). Every value is a round number chosen for this
sample; none is a requirement of any standard.
"""

import dataclasses

from fenolite.dsl import Design, Net, mil, mm
from fenolite.model.base import ExtBag

NAME = "pour-hatched"
KIT = {"pour": "computed"}
MIL = 25_400
design = Design(NAME)
design.board(mm(101.6), mm(60.96))  # 4000 by 2400 mil
design.rules.minimum(clearance=mil(8))

NETS = {}


def net(name):
    if name not in NETS:
        NETS[name] = Net(name)
    return NETS[name]


def pad(ref, name, x, y, size, *, shape="circle"):
    """A surface test point of ``size`` mil on ``name`` at (``x``, ``y``) mil."""
    design.test_point(ref, net(name), mil(x), mil(y), size=mil(size), shape=shape)


def rect(x0, y0, x1, y1):
    return [(mil(x0), mil(y0)), (mil(x1), mil(y0)), (mil(x1), mil(y1)), (mil(x0), mil(y1))]


def zone(name, points):
    design.zone(net(name), layers=("F.Cu",), name=name, outline=[(mil(x), mil(y)) for x, y in points])


def box(x0, y0, x1, y1):
    return ((x0, y0), (x1, y0), (x1, y1), (x0, y1))


HATCH = {
    "P1": "90Degree",
    "P2": "45Degree",
    "P3": "Horizontal",
    "P4": "Vertical",
    "P5": "90Degree",
    "P6": "90Degree",
    "P7": "45Degree",
}
"""The ``HATCHSTYLE`` of each hatched probe; every one has ``GRIDSIZE`` 50 mil and ``TRACKWIDTH`` 10 mil."""
GRID, TRACK = 50, 10

# --- P0: the sentinel ---------------------------------------------------------------------------------------
zone("P0", box(100, 100, 500, 500))
pad("TP0", "P0", 300, 300, 40)

# --- P1 to P4: one polygon per hatch style ------------------------------------------------------------------
for column, probe in enumerate(("P1", "P2", "P3", "P4")):
    x0 = 600 + 850 * column
    zone(probe, box(x0, 100, x0 + 800, 900))
    pad(f"T{probe}", probe, x0 + 150, 250, 40)
    pad(f"T{probe}X", "PX", x0 + 500, 550, 120)

# --- P5 and P6: the grid's origin ---------------------------------------------------------------------------
zone("P5", box(113, 1013, 713, 1613))
pad("TP5", "P5", 413, 1313, 40)
zone("P6", box(829, 1029, 1429, 1629))
pad("TP6", "P6", 1129, 1329, 40)

# --- P7: a slanted outline ----------------------------------------------------------------------------------
zone("P7", ((1550, 1030), (2290, 1110), (2370, 1700), (1900, 2230), (1530, 1660)))
pad("TP7", "P7", 1950, 1550, 40)

# --- P8 and P9: a ring that touches itself, a ring that crosses itself --------------------------------------
zone("P8", ((2500, 1100), (2900, 1100), (2900, 1500), (3300, 1500), (3300, 1900), (2900, 1900), (2900, 1500),
            (2500, 1500)))  # fmt: skip
pad("TP8", "P8", 2700, 1300, 40)
zone("P9", ((3400, 1100), (3900, 1100), (3400, 1900), (3900, 1900)))
pad("TP9", "P9", 3650, 1250, 40)

POINTS = (
    ("P0", 5.08, 5.08, True),  # 200 mil from the corner of the outline, inside P0
    ("P8", 66.04, 33.02, True),  # 2600, 1300 mil: the first square of P8
)
"""(polygon, x, y, whether copper must be there), in millimetres from the upper-left corner."""


def kit_model(model):
    """``model`` with the hatch of P1 to P7: ``hatch_style``, ``grid_size`` and ``track_width`` (nm)."""
    zones = tuple(
        dataclasses.replace(
            z,
            ext={
                "altium": ExtBag(
                    None,
                    (
                        ("hatch_style", HATCH[z.name]),
                        ("grid_size", str(GRID * MIL)),
                        ("track_width", str(TRACK * MIL)),
                    ),
                )
            },
        )
        if z.name in HATCH
        else z
        for z in model.board.zones
    )
    return dataclasses.replace(model, board=dataclasses.replace(model.board, zones=zones))
