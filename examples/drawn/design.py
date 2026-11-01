# SPDX-License-Identifier: CC0-1.0
# Authored for Fenolite as an example; no file, value, name or layout comes from any other project.
"""A drawn schematic beside code (change c0276; ``docs/drawn-schematic.md``).

The code below is the only source of the nets. ``schematic.toml`` beside it is the drawing: symbol poses,
bent wires, a junction, local, global and hierarchical labels, a power symbol and the sheet of the module
``child``. ``fenolite build`` writes the sheets from the drawing instead of generating them, reads them
back and proves that they mean the nets of this script; ``fenolite check`` proves it again on the sheets as
they are on disk, and ``fenolite sync --to-source`` copies a drawing edited in KiCad back into
``schematic.toml``. Build it with ``fenolite build examples/drawn/design.py --out build/drawn --confirm``.
"""

from fenolite.dsl import Design, Module, Net, Part, connect, mm

design = Design("drawn")
design.board(mm(50), mm(30))

u1 = Part("U1", "Mini:Mini_QFP32_IC", value="MCU")
r1 = Part("R1", "Mini:Mini_R", footprint="Mini:Mini_R_0603", value="4k7")
child = Module("child")
r2 = Part("R2", "Mini:Mini_R", footprint="Mini:Mini_R_0603", value="10k")
r3 = Part("R3", "Mini:Mini_R", footprint="Mini:Mini_R_0603", value="22k")
child.add(r2, r3)
design.add(u1, r1, child)

connect(Net("SDA"), u1[17], r1[1])
connect(Net("VCC"), u1[9], r1[2], r3[2])
connect(Net("IN"), u1[3], r2[1])
connect(Net("FB"), r2[2], r3[1])
connect(Net("GND"), u1[10])

design.load_schematic("schematic.toml")
