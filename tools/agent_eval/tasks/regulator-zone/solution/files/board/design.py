# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Reference solution of the task ``regulator-zone``: a Zener shunt regulator between two headers.

Authored for Fenolite's agent evaluation. Every part comes from the built-in catalog and every number
is a round value chosen for the task. The two supply nets are in a net class with a wide track and are
scripted tracks on the top layer; the ground is a zone on the bottom layer, which the through-hole pads
reach by themselves. No router is needed.
"""

from fenolite.dsl import Design, Net, Part, connect, mm

design = Design("board")
design.board(mm(40), mm(30))
design.rules.minimum(
    clearance=mm(0.2), track_width=mm(0.2), via_diameter=mm(0.6), via_drill=mm(0.3), edge_clearance=mm(0.3)
)

j1 = Part("J1", "Fenolite:Connector_2", footprint="Fenolite:Header_1x2_P2.54", value="IN")
r1 = Part("R1", "Fenolite:Resistor", footprint="Fenolite:R_Axial_Vishay_MRS16_P7.62", value="220")
d1 = Part("D1", "Fenolite:Zener_Diode", footprint="Fenolite:DO35_P10.16_Diodes", value="5V1")
c1 = Part(
    "C1", "Fenolite:Capacitor_Film", footprint="Fenolite:C_Film_Wima_MKS02_L4.6_W2.5_P2.5", value="100n"
)
j2 = Part("J2", "Fenolite:Connector_2", footprint="Fenolite:Header_1x2_P2.54", value="OUT")
design.add(j1, r1, d1, c1, j2)

vin, vout, gnd = Net("VIN"), Net("VOUT"), Net("GND")
connect(vin, j1[1], r1[1])
connect(vout, r1[2], d1[2], c1[1], j2[1])
connect(gnd, j1[2], d1[1], c1[2], j2[2])

# The supply class: wider tracks for the two nets that carry the load current.
design.rules.netclass("Supply", track_width=mm(0.6), nets=(vin, vout))

# The ground pour: the whole board on the bottom layer.
design.zone(gnd, layers=("B.Cu",), clearance=mm(0.3))

# The placement, from the board's top-left corner. Every supply pad lies on the line y = 10 mm, so each
# supply net is one straight track; the ground pads are elsewhere and are joined by the pour.
j1.place(mm(5), mm(10), rot=90)
r1.place(mm(14), mm(10))
d1.place(mm(22), mm(15.08), rot=90)
c1.place(mm(28), mm(11.25), rot=270)
j2.place(mm(35), mm(10), rot=270)

# The supply copper on the top layer. A track takes its width from the class of its net.
design.track("vin", j1.pad(1), r1.pad(1))
design.track("vout", r1.pad(2), d1.pad(2), c1.pad(1), j2.pad(1))
