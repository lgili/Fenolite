# SPDX-License-Identifier: CC0-1.0
# Authored for Fenolite as an example; no file, value, name or layout comes from any other project.
"""Relative placement (change c0255; ``docs/dsl.md``, "Relative placement"): parts placed by references.

The regulator ``U1`` is placed with coordinates. Its input capacitor sits by its pad 2, 2 mm left of the
regulator's pad 1, the two pad centres in line (``by=``); its output capacitor sits right of the regulator's
courtyard, 1 mm away, centres aligned. The connector ``J1`` holds the board's left edge, 2 mm in, on the
board's centre line, and the LED and its resistor follow the output capacitor. No coordinate below the
regulator's is computed by hand: moving ``U1`` in the script moves every part that follows it.
"""

from fenolite.dsl import Design, Net, Power, connect, mm

design = Design("relative_pads")
board = design.board(mm(40), mm(30))

j1 = design.part("J1", "Fenolite:Connector_2", footprint="Fenolite:Header_1x2_P2.54", value="5V")
u1 = design.part("U1", "Fenolite:Linear_Regulator", footprint="Fenolite:SOT223_3_Diodes", value="3V3")
c1 = design.part("C1", "Fenolite:Capacitor", footprint="Fenolite:Chip_0805", value="10u")
c2 = design.part("C2", "Fenolite:Capacitor", footprint="Fenolite:Chip_0805", value="22u")
r1 = design.part("R1", "Fenolite:Resistor", footprint="Fenolite:Chip_0603", value="1k")
d1 = design.part(
    "D1",
    "Fenolite:LED",
    footprint="Fenolite:LED0603_Kingbright_APT1608SURCK",
    value="green",
    pad_map={"1": "2", "2": "1"},
)

vin, v3, gnd, led_a = Net("VIN"), Net("+3V3"), Net("GND"), Net("LED_A")
connect(vin, j1[1], u1["IN"], c1["A"])
connect(gnd, j1[2], u1["GND"], c1["B"], c2["B"], d1["K"])
connect(v3, u1["OUT"], c2["A"], r1[1])
connect(led_a, r1[2], d1["A"])
design.add(Power(vin, gnd))

u1.place(mm(18), mm(15))
c1.place(left_of=u1.pad(1), gap=mm(2), by=c1.pad(2))
c2.place(right_of=u1, gap=mm(1))
j1.place(left=board.left + mm(2), center_y=board.center_y)
r1.place(below=c2, gap=mm(1), align="start")
d1.place(right_of=r1, gap=mm("0.5"))
