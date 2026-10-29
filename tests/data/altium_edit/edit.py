# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The board of Part J, the edit sessions of Altium documents (change c0241). Authored for Fenolite: no
file, value, name or layout comes from any other project.

A 40 × 30 mm two-layer rectangle with two resistors and a through-hole LED on three nets. Coordinates below
are in the frame of ``place()``: millimetres from the upper-left corner, Y down. In the written document,
whose origin is the board's lower-left corner with Y up, the track ``probe`` runs from (10, 5) to (20, 5) mm
on the Top Layer, 0.25 mm wide on ``GND``: the track that the cases of Part J move, widen, copy and delete.

- a ``GND`` polygon on the Bottom Layer over the board and a ``VIN`` polygon on the Top Layer in the
  upper-left corner, fed by a via: two polygons, so that pour indices and poured pieces can be observed;
- one free text ``FENOLITE EDIT`` on the top silkscreen (a wide-string entry), and one line and one filled
  rectangle (a region, which holds a layer byte and a ``V7_LAYER`` key) on the layer of ``F.Fab``, a
  mechanical layer: the items of the property and the layer cases;
- one clearance rule ``gap`` of 0.2 mm, the item of the rule case.

Every value is a round number chosen for this board; none is a requirement of any standard.
"""

from fenolite.dsl import Design, Net, Part, connect, mm

design = Design("edit")
design.board(mm(40), mm(30))

r1 = Part("R1", "Mini:Mini_R", footprint="Mini:Mini_R_0603", value="1k")
r2 = Part("R2", "Mini:Mini_R", footprint="Mini:Mini_R_0603", value="1k")
d1 = Part("D1", "Mini:Mini_LED", footprint="Mini:Mini_LED_THT_3mm", value="LED")
design.add(r1, r2, d1)
design.rules.rule("gap", "clearance", min=mm(0.2))

vin, mid, gnd = Net("VIN"), Net("MID"), Net("GND")
connect(vin, r1[1], r2[1])
connect(mid, r1[2], d1[2])
connect(gnd, d1[1], r2[2])

r1.place(mm(12), mm(10))
r2.place(mm(12), mm(18))
d1.place(mm(26), mm(15))

design.track("vin", r1.pad(1), r2.pad(1), width=mm(0.25))
design.track("vin_feed", (mm(5), mm(5)), (mm(11.2), mm(5)), r1.pad(1), width=mm(0.25), net=vin)
design.via("vin_via", mm(5), mm(5), net=vin, diameter=mm(0.6), drill=mm(0.3))
design.track("mid", r1.pad(2), (mm(28.54), mm(10)), d1.pad(2), width=mm(0.25))
design.track("gnd", r2.pad(2), (mm(16), mm(18)), (mm(16), mm(22)), width=mm(0.25))
design.via("gnd_via", mm(16), mm(22), net=gnd, diameter=mm(0.6), drill=mm(0.3))
design.track("probe", (mm(10), mm(25)), (mm(20), mm(25)), width=mm(0.25), net=gnd)
design.via("probe_via", mm(20), mm(25), net=gnd, diameter=mm(0.6), drill=mm(0.3))

design.zone(
    gnd, layers=("B.Cu",), outline=((mm(1), mm(1)), (mm(39), mm(1)), (mm(39), mm(29)), (mm(1), mm(29)))
)
design.zone(vin, layers=("F.Cu",), outline=((mm(2), mm(2)), (mm(8), mm(2)), (mm(8), mm(8)), (mm(2), mm(8))))

design.text("label", "FENOLITE EDIT", (mm(30), mm(26)), layer="F.SilkS")
design.line("mech", (mm(2), mm(28)), (mm(12), mm(28)), layer="F.Fab", width=mm(0.1))
design.rect("mech_box", (mm(30), mm(2)), (mm(36), mm(6)), layer="F.Fab", width=mm(0.1), fill=True)
