# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Reference solution of the task ``led-indicator``: a header feeds a LED through a resistor.

Authored for Fenolite's agent evaluation. Every part comes from the built-in catalog and every number
is a round value chosen for the task. The placement lets a straight track close each net, so the
built-in ``direct`` router is enough.
"""

from fenolite.dsl import Design, Net, Part, connect, mm

design = Design("board")
design.board(mm(30), mm(20))
design.rules.minimum(
    clearance=mm(0.2), track_width=mm(0.2), via_diameter=mm(0.6), via_drill=mm(0.3), edge_clearance=mm(0.3)
)

j1 = Part("J1", "Fenolite:Connector_2", footprint="Fenolite:Header_1x2_P2.54", value="PWR")
r1 = Part("R1", "Fenolite:Resistor", footprint="Fenolite:Chip_0603", value="330")
d1 = Part("D1", "Fenolite:LED", footprint="Fenolite:Chip_0603", value="LED")
design.add(j1, r1, d1)

vin, led_a, gnd = Net("VIN"), Net("LED_A"), Net("GND")
connect(vin, j1[1], r1[1])
connect(led_a, r1[2], d1[1])
connect(gnd, d1[2], j1[2])

# The placement, from the board's top-left corner: no straight track between two pads of a net
# crosses another one.
j1.place(mm(6), mm(9))
r1.place(mm(15), mm(14))
d1.place(mm(15), mm(6), rot=180)
