# SPDX-License-Identifier: CC0-1.0
# Authored for Fenolite as an example; no file, value, name or layout comes from any other project.
"""Devices: a 5 V to 3.3 V step-down board whose parts are placed from device records (change c0248).

``U1`` comes from ``devices/example_buck.toml`` beside this script: an illustrative regulator (not a real
product) whose record joins an authored symbol, a catalog footprint, the map from pin function to pad, its
ratings and its evidence label. The passives, the LED and the connector come from the shipped generic
``Fenolite:`` devices. Pins are named by function (``u1.VIN``), and a typo stops the script at its line with
the closest names.

Build it with ``fenolite build examples/devices/design.py --out build/devices --confirm``. Every symbol and
footprint is authored in the script or comes from the built-in catalog, so no library table is needed.
"""

from fenolite.dsl import Design, Net, Symbol, connect, farad, henry, mm, ohm

design = Design("devices")
design.board(mm(40), mm(25))

# The symbol that the example device names: six pins, numbered as its land.
buck = Symbol("Example", "Buck_6pin", reference="U", value="EXB6202")
for number, name, y in (("1", "BST", -2.54), ("2", "GND", 0), ("3", "FB", 2.54)):
    buck.pin(number, name, at=(mm(-7.62), mm(y)), length=mm(2.54))
for number, name, y in (("4", "EN", 2.54), ("5", "VIN", 0), ("6", "SW", -2.54)):
    buck.pin(number, name, at=(mm(7.62), mm(y)), length=mm(2.54), rotation=180)
buck.rect((mm(-5.08), mm(-5.08)), (mm(5.08), mm(5.08)))
design.add(buck)

vin, gnd, sw, bst, fb, v33, led = (Net(n) for n in ("VIN", "GND", "SW", "BST", "FB", "V3V3", "LED_A"))

j1 = design.part("J1", device="Fenolite:Conn_1x2_P2.54", value="5V IN")
u1 = design.part("U1", device="Example:BUCK_6V_2A")
c1 = design.part("C1", device="Fenolite:C_0805", value=farad("10u"))
c2 = design.part("C2", device="Fenolite:C_0603", value=farad("100n"))
c3 = design.part("C3", device="Fenolite:C_0805", value=farad("22u"))
l1 = design.part("L1", "Fenolite:Inductor", footprint="Fenolite:Chip_0805", value=henry("4u7"))
r1 = design.part("R1", device="Fenolite:R_0603", value=ohm("31k6"))
r2 = design.part("R2", device="Fenolite:R_0603", value=ohm("10k"))
r3 = design.part("R3", device="Fenolite:R_0603", value=ohm("1k"))
d1 = design.part("D1", device="Fenolite:LED_0603")

connect(vin, j1.P1, c1.P1, u1.VIN, u1.EN)
connect(gnd, j1.P2, c1.P2, u1.GND, c3.P2, r2.P2, d1.K)
connect(bst, u1.BST, c2.P1)
connect(sw, u1.SW, c2.P2, l1[1])
connect(v33, l1[2], c3.P1, r1.P1, r3.P1)
connect(fb, u1.FB, r1.P2, r2.P1)
connect(led, r3.P2, d1.A)

j1.place(mm(5), mm(12.5), rot=90, locked=True)
c1.place(mm(12), mm(8))
u1.place(mm(18), mm(12.5))
c2.place(mm(18), mm(7))
l1.place(mm(25), mm(12.5))
c3.place(mm(31), mm(8))
r1.place(mm(25), mm(18))
r2.place(mm(20), mm(18))
r3.place(mm(31), mm(17))
d1.place(mm(35), mm(17))
