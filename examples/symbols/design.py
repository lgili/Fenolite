# SPDX-License-Identifier: CC0-1.0
# Authored for Fenolite as an example; no file, value, name or layout comes from any other project.
"""Symbols from pin tables (change c0261): an illustrative regulator and an illustrative 120-pin controller.

Build it with ``fenolite build examples/symbols/design.py --out build/symbols --dry-run``, then
``--confirm --plan <plan_id>``. Both symbols and their variants are generated from the tables of
``pins/`` and written into ``lib/Example.kicad_sym``; the regulator is placed on the board through its
derived symbol with its input and output parts, the controller is a library symbol only.
``fenolite library symbol pins/EXB6202.toml pins/EXM120.toml --out lib/Example.kicad_sym`` writes the
same symbols without a design.
"""

from pathlib import Path

from fenolite.catalog.pins import read_pins
from fenolite.dsl import Design, Net, Part, Symbol, connect, mm

PINS = Path(__file__).resolve().parent / "pins"

design = Design("symbols")
design.board(mm(30), mm(20))

regulator = Symbol.from_pins(read_pins(PINS / "EXB6202.toml"), library="Example", footprint="Fenolite:SOIC_8")
controller = Symbol.from_pins(read_pins(PINS / "EXM120.toml"), library="Example")
design.add(regulator, *regulator.variants, controller, *controller.variants)

u1 = Part("U1", "Example:EXB6202DR", value="EXB6202DR")
c1 = Part("C1", "Fenolite:Capacitor", footprint="Fenolite:Chip_0603", value="10u")
l1 = Part("L1", "Fenolite:Inductor", footprint="Fenolite:Chip_0805", value="4u7")
c2 = Part("C2", "Fenolite:Capacitor", footprint="Fenolite:Chip_0603", value="22u")
design.add(u1, c1, l1, c2)
vin, gnd, sw, vout = Net("VIN"), Net("GND"), Net("SW"), Net("VOUT")
connect(vin, u1["VIN"], c1[1])
connect(gnd, u1["GND"], c1[2], c2[2])  # u1["GND"] is pins 2 and 7: the exposed pad is stacked on GND
connect(sw, u1["SW"], l1[1])
connect(vout, l1[2], c2[1])
u1.place(mm(12), mm(10))
c1.place(mm(5), mm(10), rot=90)
l1.place(mm(20), mm(7))
c2.place(mm(25), mm(12), rot=90)
