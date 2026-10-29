# SPDX-License-Identifier: CC0-1.0
# Authored for Fenolite as a test fixture; no file, value, name or layout comes from any other project.
"""Drawn fixture ``bus`` (change c0276): the root bus ``D[0..3]`` carries four MCU pins to the sheet pin
``D[0..3]`` of the module ``child``, whose bus entries lead to four resistors through the labels ``D0`` to
``D3``."""

from fenolite.dsl import Design, Module, Net, Part, connect, mm

design = Design("drawn_bus")
design.board(mm(40), mm(30))
u1 = Part("U1", "Mini:Mini_QFP32_IC", value="MCU")
child = Module("child")
design.add(u1, child)
for k in range(4):
    r = Part(f"R{10 + k}", "Mini:Mini_R", footprint="Mini:Mini_R_0603", value="1k")
    child.add(r)
    connect(Net(f"D{k}"), u1[17 + k], r[1])
design.load_schematic("schematic.toml")
