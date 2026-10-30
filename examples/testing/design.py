# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Authored test fixture: two vertical resistors with their first terminals joined."""

from fenolite.dsl import Design, Net, Part, connect, mm

design = Design("design_tests")
design.board(mm(30), mm(20))
r1 = Part("R1", "Fenolite:Resistor", footprint="Fenolite:Chip_0603", value="1000")
r2 = Part("R2", "Fenolite:Resistor", footprint="Fenolite:Chip_0603", value="2000")
design.add(r1, r2)
gnd = Net("GND")
connect(gnd, r1[1], r2[1])
r1.place(mm(5), mm(5), rot=90)
r2.place(mm(15), mm(5), rot=90)
design.track("ground", r1.pad(1), r2.pad(1), width=mm("0.2"))
