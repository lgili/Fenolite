# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
# Authored for Fenolite as a test fixture; no file, value, name or layout comes from any other project.
"""Drawn fixture ``full`` (change c0276): every item kind of the drawn file once at least: field poses, a
power symbol, a wire of four points, a bus with an alias and two bus entries, a junction, a no-connect
flag, local, global and hierarchical labels, a sheet reference with a pin, two opaque items and a title
block."""

from fenolite.dsl import Design, Module, Net, Part, connect, mm

design = Design("drawn_full")
design.board(mm(40), mm(30))
u1 = Part("U1", "Mini:Mini_QFP32_IC", value="MCU")
r1 = Part("R1", "Mini:Mini_R", footprint="Mini:Mini_R_0603", value="4k7")
sub = Module("sub")
r2 = Part("R2", "Mini:Mini_R", footprint="Mini:Mini_R_0603", value="1k")
sub.add(r2)
design.add(u1, r1, sub)
connect(Net("SDA"), u1[17], r1[2])
connect(Net("VCC"), u1[9], r1[1])
connect(Net("GND"), u1[10], r2[2])
connect(Net("IN"), u1[1], r2[1])
connect(Net("B0"), u1[18])
connect(Net("B1"), u1[19])
design.load_schematic("schematic.toml")
