# SPDX-License-Identifier: CC0-1.0
# Authored for Fenolite as a test fixture; no file, value, name or layout comes from any other project.
"""The edit merge acceptance fixture (change c0250): a supply connector, a resistor with a user property at
the root, and an indicator in the module ``led``. ``tests/unit/lens/test_edit_merge_acceptance.py`` builds
it, edits the board and the schematic as KiCad would, and builds and syncs it again. Every symbol and
footprint comes from Fenolite's own catalog, so the build reads no library."""

from fenolite.dsl import Design, Module, Net, Power, connect, mm

design = Design("edit_merge")
design.board(mm(40), mm(30))

j = design.part("J1", "Fenolite:Connector_2", footprint="Fenolite:Header_1x2_P2.54", value="5V")
r_bias = design.part(
    "R1",
    "Fenolite:Resistor",
    footprint="Fenolite:Chip_0603",
    value="330",
    properties={"Part number": "FEN-R330"},
)

led = Module("led")
design.add(led)
r = led.part("R2", "Fenolite:Resistor", footprint="Fenolite:Chip_0603", value="1k")
d = led.part(
    "D1",
    "Fenolite:LED",
    footprint="Fenolite:LED0603_Kingbright_APT1608SURCK",
    value="green",
    pad_map={"1": "2", "2": "1"},
)

vin, gnd, bias, led_a = Net("VIN"), Net("GND"), Net("BIAS"), Net("LED_A")
connect(vin, j[1], r_bias[1])
connect(bias, r_bias[2], r[1])
connect(led_a, r[2], d["A"])
connect(gnd, j[2], d["K"])
design.add(Power(vin, gnd))

j.place(mm(5), mm(15))
r_bias.place(mm(15), mm(10))
r.place(mm(25), mm(10))
d.place(mm(32), mm(15))
