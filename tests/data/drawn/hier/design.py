# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
# Authored for Fenolite as a test fixture; no file, value, name or layout comes from any other project.
"""Drawn fixture ``hier`` (change c0276): the root wires the sheet pin ``IN`` of the module ``child`` to U1
pin 3; the child labels R2 pin 1 ``IN`` (hierarchical), joins R2 and R3 through the local label ``FB`` and
reaches U1 pin 9 through the global label ``VCC``."""

from fenolite.dsl import Design, Module, Net, Part, connect, mm

design = Design("drawn_hier")
design.board(mm(40), mm(30))
u1 = Part("U1", "Mini:Mini_QFP32_IC", value="MCU")
child = Module("child")
r2 = Part("R2", "Mini:Mini_R", footprint="Mini:Mini_R_0603", value="10k")
r3 = Part("R3", "Mini:Mini_R", footprint="Mini:Mini_R_0603", value="22k")
child.add(r2, r3)
design.add(u1, child)
connect(Net("IN"), u1[3], r2[1])
connect(Net("FB"), r2[2], r3[1])
connect(Net("VCC"), u1[9], r3[2])
connect(Net("GND"), u1[10])
design.load_schematic("schematic.toml")
