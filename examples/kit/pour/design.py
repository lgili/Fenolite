# SPDX-License-Identifier: CC0-1.0
# Authored for Fenolite as an example; no file, value, name or layout comes from any other project.
"""Kit sample ``pour``: eleven probes of Altium's polygon pour on two copper layers (change c0215).

It is a sample of group K6 of the Altium verification kit (``docs/altium-kit.md``). Each probe is its own
polygon on its own net, on the top layer unless said, so that a difference between Fenolite's pour and
Altium's points to one input of ``docs/formats/altium/pcb-pour.md``. The kit writes the document twice
from one computation: ``computed/`` with Fenolite's pour and ``reference/`` without it. Lengths are in
millimetres from the upper-left corner of the 120 mm by 90 mm outline:

- P0, a sentinel that must pour copper;
- P1, clearance: a pad of each shape, a via, a track and an arc of the net ``P1X`` (class ``P1C``, 0.4 mm),
  and a pad of ``P1Y`` with a rule of 0.8 mm between ``P1`` and ``P1Y``; 0.2 mm elsewhere;
- P2, the connect styles that a build lowers, one net each: ``P2T`` thermal, ``P2H`` through-hole only,
  ``P2S`` solid and ``P2N`` none, each with a through-hole pad, a surface pad and a via;
- P3, necks of 4.5 mil and 5.5 mil against the 5 mil threshold, between three tracks of ``P3X``, and a
  ``P3`` track of 0.1 mm, narrower than the threshold;
- P4, islands inside three square loops of ``P4X``: 1.44 mm² and 1.80 mm² against the 2500 mil² threshold,
  and a 1.44 mm² one that holds a pad of ``P4``; the polygon keeps dead copper (``islands="never"``);
- P5, dead copper: a polygon whose net has no pad inside it, and a polygon without a net;
- P6, order: two overlapping polygons of two nets and two overlapping polygons of one net;
- P7, curves: a round pad of 5 mm and an arc track of ``P7X``;
- P8, keep-outs: one on the top layer and one on every copper layer (the Keep-Out layer);
- P9, the edge: a polygon past the board's lower edge and one up to it, with a Board Outline Clearance of
  0.5 mm;
- P10, pour over: three polygons with ``POUROVERSTYLE`` 0, 1 and 2, each over a track of its own net.

``POINTS`` declares, per polygon, where copper must stay (``True``) or be gone (``False``): the points
that a kit run's comparison judges (M5 of ``pourcompare``). Every value is a round number chosen for this
sample; none is a requirement of any standard.
"""

import dataclasses

from fenolite.core.coords import Point
from fenolite.core.ids import derived_id
from fenolite.dsl import BOARD_ORIGIN, Design, Net, mm, select
from fenolite.model.base import ExtBag
from fenolite.model.board import Arc, Track, Via

NAME = "pour"
KIT = {"pour": "computed"}
design = Design(NAME)
design.board(mm(120), mm(90))
design.rules.minimum(clearance=mm(0.2))
design.rules.rule("edge", "edge_clearance", min=mm(0.5))

NETS = {}


def net(name):
    if name not in NETS:
        NETS[name] = Net(name)
    return NETS[name]


POINTS_TP = []


def pad(ref, name, x, y, size, *, shape="circle", drill=None):
    """A test point of ``size`` mm on ``name``: a surface pad, or a through-hole pad with ``drill``."""
    design.test_point(
        ref, net(name), mm(x), mm(y), size=mm(size), shape=shape, drill=None if drill is None else mm(drill)
    )


def rect(x0, y0, x1, y1):
    return [(mm(x0), mm(y0)), (mm(x1), mm(y0)), (mm(x1), mm(y1)), (mm(x0), mm(y1))]


def zone(name, x0, y0, x1, y1, *, layer="F.Cu", polygon_net=None, **settings):
    design.zone(
        net(polygon_net or name) if polygon_net != "" else None,
        layers=(layer,),
        name=name,
        outline=rect(x0, y0, x1, y1),
        **settings,
    )


# --- P0: the sentinel ---------------------------------------------------------------------------------------
zone("P0", 2, 2, 22, 22)
pad("TP0", "P0", 12, 12, 1.0)

# --- P1: clearance ------------------------------------------------------------------------------------------
zone("P1", 24, 2, 56, 22)
pad("TP1", "P1", 26, 4, 1.0)
pad("TP1A", "P1X", 30, 8, 1.6, drill=0.8)
pad("TP1B", "P1X", 36, 8, 1.2, shape="rect")
pad("TP1Y", "P1Y", 50, 6, 1.0)
design.rules.netclass("P1C", clearance=mm(0.4), nets=(net("P1X"),))
design.rules.rule(
    "p1y", "clearance", where=select.net("P1"), between=select.net("P1Y"), min=mm(0.8), priority=1
)

# --- P2: connect styles -------------------------------------------------------------------------------------
STYLES = (("P2T", "thermal"), ("P2H", "thru_hole_only"), ("P2S", "solid"), ("P2N", "none"))
for column, (name, connection) in enumerate(STYLES):
    x0 = 58 + 15 * column
    zone(name, x0 + 0.5, 2.5, x0 + 14.5, 21.5, connection=connection, thermal_gap=mm(0.3),
         thermal_spoke_width=mm(0.3))  # fmt: skip
    pad(f"TP{name}A", name, x0 + 4, 8, 1.6, drill=0.8)
    pad(f"TP{name}B", name, x0 + 10, 8, 1.2, shape="rect")

# --- P3: necks ----------------------------------------------------------------------------------------------
zone("P3", 2.5, 24.5, 29.5, 43.5)
pad("TP3A", "P3", 5, 27, 1.0)
pad("TP3B", "P3", 27, 41, 1.0)
pad("TP3X", "P3X", 31, 45, 0.6)

# --- P4: islands --------------------------------------------------------------------------------------------
zone("P4", 32.5, 24.5, 59.5, 43.5, islands="never")
pad("TP4", "P4", 35, 27, 1.0)
pad("TP4I", "P4", 52, 37, 0.4)
pad("TP4X", "P4X", 61, 45, 0.6)

# --- P5: dead copper ----------------------------------------------------------------------------------------
zone("P5", 62.5, 24.5, 74.5, 43.5)
pad("TP5", "P5", 76, 42, 0.6)
zone("P5_NONET", 78, 24.5, 89.5, 43.5, polygon_net="")

# --- P6: order ----------------------------------------------------------------------------------------------
zone("P6A", 92, 24.5, 106, 34, priority=2)
zone("P6B", 100, 24.5, 117.5, 34, priority=1)
pad("TP6A", "P6A", 94, 27, 1.0)
pad("TP6B", "P6B", 115, 27, 1.0)
zone("P6C", 92, 36, 106, 43.5, priority=0)
zone("P6C_2", 100, 36, 117.5, 43.5, polygon_net="P6C", priority=0)
pad("TP6C", "P6C", 94, 41, 1.0)
pad("TP6D", "P6C", 115, 41, 1.0)

# --- P7: curves ---------------------------------------------------------------------------------------------
zone("P7", 2.5, 46.5, 29.5, 66)
pad("TP7", "P7", 5, 49, 1.0)
pad("TP7X", "P7X", 10, 56, 5.0, drill=2.0)

# --- P8: keep-outs ------------------------------------------------------------------------------------------
zone("P8", 32.5, 46.5, 59.5, 66)
pad("TP8", "P8", 35, 49, 1.0)
design.rule_area("P8_TOP", rect(38, 52, 44, 58), layers=("F.Cu",), forbid=("pours",))
design.rule_area("P8_ALL", rect(48, 52, 54, 58), forbid=("pours", "tracks", "vias"))

# --- P9: the edge -------------------------------------------------------------------------------------------
zone("P9A", 63, 72, 75, 95)
zone("P9B", 77, 72, 89, 90)
pad("TP9A", "P9A", 65, 75, 1.0)
pad("TP9B", "P9B", 79, 75, 1.0)

# --- P10: pour over -----------------------------------------------------------------------------------------
for column, style in enumerate(("0", "1", "2")):
    x0 = 92 + 9 * column
    zone(f"P10_{style}", x0, 46.5, x0 + 8, 66)
    pad(f"TP10_{style}", f"P10_{style}", x0 + 2, 49, 1.0)

MM = 1_000_000


def at(x, y):
    """A point given in millimetres from the upper-left corner of the outline, in the frame of ``place()``."""
    return Point(BOARD_ORIGIN.x + round(x * MM), BOARD_ORIGIN.y + round(y * MM))


def _id(prefix, key):
    return derived_id(prefix, "dsl", f"{NAME}:{key}")


TRACKS = (
    ("p1t", "P1X", (28.0, 14.0), (40.0, 14.0), 0.3),
    ("p3a", "P3X", (16.0, 24.0), (16.0, 29.0), 0.3),
    ("p3b", "P3X", (16.0, 29.8143), (16.0, 35.0), 0.3),
    ("p3c", "P3X", (16.0, 35.8397), (16.0, 44.0), 0.3),
    ("p3n", "P3", (5.0, 40.0), (12.0, 40.0), 0.1),
    ("p10_0", "P10_0", (93.0, 58.0), (99.0, 58.0), 0.3),
    ("p10_1", "P10_1", (102.0, 58.0), (108.0, 58.0), 0.3),
    ("p10_2", "P10_2", (111.0, 58.0), (117.0, 58.0), 0.3),
)
"""(key, net, start, end, width in mm), all on the top layer. The ends of ``p3a``, ``p3b`` and ``p3c`` are
0.5143 mm and 0.5397 mm apart (4.5 mil and 5.5 mil of copper between their 0.2 mm voids)."""
LOOPS = (("p4a", 40.0, 34.0, 1.9), ("p4b", 46.0, 34.0, 2.04), ("p4c", 52.0, 37.0, 1.9))
"""(key, centre x, centre y, side of the centre line) of the ``P4X`` loops, 0.3 mm wide: islands of
1.20 mm and 1.34 mm square inside their 0.2 mm voids."""
ARCS = (("p1a", "P1X", (46.0, 14.0), (48.0, 12.0), (50.0, 14.0), 0.3),
        ("p7a", "P7X", (18.0, 60.0), (22.0, 56.0), (26.0, 60.0), 0.3))  # fmt: skip
"""(key, net, start, mid, end, width in mm) on the top layer."""
VIAS = (
    ("p1v", "P1X", (42.0, 8.0)),
    *((f"{name.lower()}v", name, (58 + 15 * column + 7, 15.0)) for column, (name, _) in enumerate(STYLES)),
)
"""(key, net, position) of through vias of 0.6 mm with a 0.3 mm drill."""
POUR_OVER = {"P10_0": "0", "P10_1": "1", "P10_2": "2"}
"""The ``POUROVERSTYLE`` of each polygon of P10 (the zone's ``pour_over`` pair, change c0215)."""

POINTS = (
    ("P0", 6.0, 6.0, True),
    ("P1", 30.0, 9.0, False),  # 0.2 mm from the edge of TP1A, inside its 0.4 mm
    ("P1", 30.0, 9.5, True),  # 0.7 mm from it
    ("P1", 50.0, 7.2, False),  # 0.7 mm from TP1Y, inside the 0.8 mm of rule p1y
    ("P1", 50.0, 7.6, True),
    ("P1", 34.0, 14.0, False),  # on the track
    ("P2T", 62.95, 8.0, True),  # on a conductor of the relief, in the air gap
    ("P2T", 62.67, 7.33, False),  # in the air gap, off the conductors
    ("P2S", 92.67, 7.33, True),  # a solid joint fills the gap
    ("P2N", 107.95, 8.0, False),  # no connection: the gap stays
    ("P3", 16.0, 29.4071, False),  # the 4.5 mil neck is removed
    ("P3", 16.0, 35.4198, True),  # the 5.5 mil neck stays
    ("P4", 40.0, 34.0, False),  # the island of 1.44 mm²
    ("P4", 46.0, 34.0, True),  # the island of 1.80 mm²
    ("P5", 68.0, 34.0, False),  # dead
    ("P6A", 103.0, 30.0, True),  # the overlap goes to the polygon poured first
    ("P6B", 103.0, 30.0, False),
    ("P7", 10.0, 58.9, True),  # 0.2 mm past the void of the 5 mm pad
    ("P7", 10.0, 58.6, False),  # in the void
    ("P8", 41.0, 55.0, False),
    ("P8", 51.0, 55.0, False),
    ("P8", 46.0, 55.0, True),
    ("P9A", 69.0, 89.7, False),  # within the 0.5 mm of the edge
    ("P9A", 69.0, 89.3, True),
    ("P9B", 83.0, 89.7, False),
    ("P10_0", 96.0, 58.0, False),  # no pour over its own track
    ("P10_1", 105.0, 58.0, True),
)
"""(polygon, x, y, whether copper must be there), in millimetres from the upper-left corner."""


def _loop(key, x, y, side):
    half = side / 2
    corners = ((x - half, y - half), (x + half, y - half), (x + half, y + half), (x - half, y + half))
    return tuple((f"{key}{n}", "P4X", corners[n], corners[(n + 1) % 4], 0.3) for n in range(4))


def kit_model(model):
    """``model`` with the sample's tracks, arcs and vias, and the pour-over style of the polygons of P10."""
    nets = {item.name: item.id for item in model.circuit.nets}
    tracks = [*TRACKS, *(edge for loop in LOOPS for edge in _loop(*loop))]
    zones = tuple(
        dataclasses.replace(z, ext={"altium": ExtBag(None, (("pour_over", POUR_OVER[z.name]),))})
        if z.name in POUR_OVER
        else z
        for z in model.board.zones
    )
    board = dataclasses.replace(
        model.board,
        tracks=tuple(
            Track(
                id=_id("trk", key),
                start=at(*a),
                end=at(*b),
                width=round(width * MM),
                layer="F.Cu",
                net_id=nets[name],
            )
            for key, name, a, b, width in tracks
        ),  # fmt: skip
        arcs=tuple(
            Arc(
                id=_id("arc", key),
                start=at(*a),
                mid=at(*m),
                end=at(*b),
                width=round(width * MM),
                layer="F.Cu",
                net_id=nets[name],
            )
            for key, name, a, m, b, width in ARCS
        ),  # fmt: skip
        vias=tuple(
            Via(
                id=_id("via", key),
                position=at(*xy),
                diameter=600_000,
                drill=300_000,
                layers=("F.Cu", "B.Cu"),
                net_id=nets[name],
            )
            for key, name, xy in VIAS
        ),  # fmt: skip
        zones=zones,
    )
    return dataclasses.replace(model, board=board)
