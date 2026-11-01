# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
# Authored for Fenolite as a test fixture; no file, value, name or layout comes from any other project.
"""Drawn fixture ``flat`` (change c0276): one sheet, an MCU pin pulled down through R1, drawn with a bent
wire, a T joint with a junction, a local label and a power symbol."""

from fenolite.dsl import Design, Net, Part, connect, mm

design = Design("drawn_flat")
design.board(mm(40), mm(30))
u1 = Part("U1", "Mini:Mini_QFP32_IC", value="MCU")
r1 = Part("R1", "Mini:Mini_R", footprint="Mini:Mini_R_0603", value="4k7")
design.add(u1, r1)
connect(Net("SDA"), u1[17], r1[1])
connect(Net("GND"), r1[2])
design.load_schematic("schematic.toml")
