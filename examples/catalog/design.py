# SPDX-License-Identifier: CC0-1.0
# Authored for Fenolite as an example; no file, value, name or layout comes from any other project.
"""Catalog: a 5 V to 3.3 V linear supply with an indicator LED, built from the built-in catalog alone.

Every symbol and footprint is a ``Fenolite:`` lib id, so the build needs no library table and no KiCad
library. The build of this script is recorded in ``tests/data/catalog/golden.json`` (change c0259): the
catalog's move from Python tables to record files kept every byte of it.

Build it with ``fenolite build examples/catalog/design.py --out build/catalog --confirm``.
"""

from fenolite.dsl import Design, Net, Part, connect, mm

design = Design("catalog")
design.board(mm(36), mm(20))

j1 = Part("J1", "Fenolite:Connector_2", footprint="Fenolite:Header_1x2_P2.54", value="5V")
c1 = Part("C1", "Fenolite:Capacitor", footprint="Fenolite:Chip_0805", value="10uF")
# The regulator symbol's pins are 1 IN, 2 GND, 3 OUT; this land carries GND on pad 1, OUT on 2, IN on 3.
u1 = Part(
    "U1",
    "Fenolite:Linear_Regulator",
    footprint="Fenolite:SOT23_3",
    value="3V3",
    pad_map={"1": "3", "2": "1", "3": "2"},
)
c2 = Part("C2", "Fenolite:Capacitor", footprint="Fenolite:Chip_0805", value="10uF")
r1 = Part("R1", "Fenolite:Resistor", footprint="Fenolite:Chip_0603", value="1k")
d1 = Part(
    "D1",
    "Fenolite:LED",
    footprint="Fenolite:LED0603_Kingbright_APT1608SURCK",
    value="LED",
    pad_map={"1": "2", "2": "1"},
)
design.add(j1, c1, u1, c2, r1, d1)

vin, v33, gnd, led = Net("VIN"), Net("V3V3"), Net("GND"), Net("LED_A")
connect(vin, j1[1], c1[1], u1["IN"])
connect(v33, u1["OUT"], c2[1], r1[1])
connect(led, r1[2], d1["A"])
connect(gnd, j1[2], c1[2], u1["GND"], c2[2], d1["K"])

j1.place(mm(5), mm(10), rot=90, locked=True)
c1.place(mm(11), mm(6))
u1.place(mm(18), mm(10))
c2.place(mm(25), mm(6))
r1.place(mm(25), mm(14))
d1.place(mm(31), mm(14))
