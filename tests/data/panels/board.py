# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The board of the panel fixtures (change c0173). Authored for Fenolite: no file, value, name or layout
comes from any other project.

A 40 × 30 mm two-layer rectangle with two resistors and a through-hole LED on three nets, routed on both
sides with one via, and a track ``edge`` on the bottom side whose copper lies 0.3 mm from the right edge:
the planted finding of a V-score between columns (``vscore.py``). ``tabs.py`` and ``mixed.py`` keep that
edge tabbed, where 0.3 mm is clear of the mouse-bite holes.
"""

from fenolite.dsl import Design, Net, Part, connect, mm, via_step

design = Design("board")
design.board(mm(40), mm(30))

r1 = Part("R1", "Mini:Mini_R", footprint="Mini:Mini_R_0603", value="1k")
r2 = Part("R2", "Mini:Mini_R", footprint="Mini:Mini_R_0603", value="1k")
d1 = Part("D1", "Mini:Mini_LED", footprint="Mini:Mini_LED_THT_3mm", value="LED")
design.add(r1, r2, d1)
# Copper may come 0.25 mm near a routed edge (the outer-layer figure of S-0799), so the planted track is
# legal on the board itself and only a V-score next to it is a finding.
design.rules.minimum(edge_clearance=mm(0.25))

vin, mid, gnd = Net("VIN"), Net("MID"), Net("GND")
connect(vin, r1[1], r2[1])
connect(mid, r1[2], d1[2])
connect(gnd, d1[1], r2[2])

r1.place(mm(10), mm(10))
r2.place(mm(10), mm(20))
d1.place(mm(25), mm(15))

design.track("vin", r1.pad(1), r2.pad(1), width=mm(0.25))
design.track("mid", r1.pad(2), (mm(27.54), mm(10)), d1.pad(2), width=mm(0.25))
design.track(
    "gnd",
    r2.pad(2), (mm(18), mm(20)),
    via_step(mm(18), mm(24), to="B.Cu", diameter=mm(0.6), drill=mm(0.3)),
    (mm(22), mm(24)), d1.pad(1),
    width=mm(0.25),
)  # fmt: skip
# The planted track: 0.2 mm wide, its centre line 0.4 mm inside the right edge, so its copper is 0.3 mm from
# the edge. It hangs on GND through the via, on the bottom side.
design.track(
    "edge", (mm(22), mm(24)), (mm(39.6), mm(24)), (mm(39.6), mm(6)), width=mm(0.2), layer="B.Cu", net=gnd
)
