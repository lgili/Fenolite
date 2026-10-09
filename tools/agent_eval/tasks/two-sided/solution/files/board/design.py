# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Reference solution of the task ``two-sided``: a resistor on top, a LED on the bottom, one via.

Authored for Fenolite's agent evaluation. Every part comes from the built-in catalog and every number
is a round value chosen for the task. All copper is written here, so no router is needed: the net
between the resistor and the LED changes layer through a via.
"""

from fenolite.dsl import Design, Net, Part, connect, mm, via_step

design = Design("board")
design.board(mm(30), mm(20))

# The minimums the task gives.
design.rules.minimum(
    clearance=mm(0.2), track_width=mm(0.25), via_diameter=mm(0.7), via_drill=mm(0.3), edge_clearance=mm(0.5)
)

j1 = Part("J1", "Fenolite:Connector_2", footprint="Fenolite:Header_1x2_P2.54", value="PWR")
r1 = Part("R1", "Fenolite:Resistor", footprint="Fenolite:Chip_0805", value="470")
d1 = Part("D1", "Fenolite:LED", footprint="Fenolite:Chip_0805", value="LED")
design.add(j1, r1, d1)

vin, led_a, gnd = Net("VIN"), Net("LED_A"), Net("GND")
connect(vin, j1[1], r1[1])
connect(led_a, r1[2], d1[1])
connect(gnd, d1[2], j1[2])

# The placement, from the board's top-left corner: the resistor on the top side, the LED on the bottom.
j1.place(mm(6), mm(10))
r1.place(mm(14), mm(6))
d1.place(mm(22), mm(14), side="bottom")

# The copper. VIN stays on the top layer; LED_A starts on top, goes through a via and ends on the
# bottom layer at the LED; GND runs on the bottom layer to the through-hole pad of the header.
design.track("vin", j1.pad(1), (mm(10), mm(11.27)), (mm(10), mm(6)), r1.pad(1), width=mm(0.3))
design.track(
    "led_a",
    r1.pad(2),
    via_step(mm(19), mm(6), to="B.Cu", diameter=mm(0.7), drill=mm(0.3)),
    (mm(19), mm(14)),
    d1.pad(1),
    width=mm(0.3),
)
design.track(
    "gnd",
    d1.pad(2),
    (mm(25), mm(14)),
    (mm(25), mm(17)),
    (mm(3), mm(17)),
    (mm(3), mm(8.73)),
    j1.pad(2),
    layer="B.Cu",
    width=mm(0.3),
)
