# SPDX-License-Identifier: CC0-1.0
# Authored for Fenolite as an example; no file, value, name or layout comes from any other project.
"""Kit sample ``flat``: a controller drives an LED through a resistor, on one schematic sheet.

It is one of the five samples of the Altium verification kit (``docs/altium-kit.md``), built by
``fenolite kit build``. Every symbol and footprint comes from Fenolite's own catalog, so the build reads no
library and gives the same bytes on every machine. The sheet carries the generic drawing sheet that
Fenolite ships and a title block, which the steps of group K8 read; the kit also builds this sample's
schematic in the ASCII form.
"""

from fenolite.dsl import Design, Net, Part, Power, connect, mm

KIT = {"forms": ("binary", "ascii"), "drawing_sheet": "iso5457_generic"}

design = Design("flat")
design.board(mm(50), mm(30))
design.sheet("A4")
design.title_block(title="Flat", revision="B", date="2026-10-06", organization="Fenolite")

j1 = Part("J1", "Fenolite:Connector_2", footprint="Fenolite:Header_1x2_P2.54", value="SUPPLY")
u1 = Part("U1", "Fenolite:Microcontroller", footprint="Fenolite:DIP8_Microchip_P", value="MCU")
r1 = Part("R1", "Fenolite:Resistor", footprint="Fenolite:Chip_0603", value="330")
# The LED land numbers its pads as the manufacturer does, pad 1 the cathode, while the symbol's pin 1 is the
# anode: the map puts the anode (pin 1) on pad 2 and the cathode (pin 2) on pad 1.
d1 = Part(
    "D1",
    "Fenolite:LED",
    footprint="Fenolite:LED0603_Kingbright_APT1608SURCK",
    value="red",
    pad_map={"1": "2", "2": "1"},
)
design.add(j1, u1, r1, d1)

vin, gnd, led_drv, led_a = Net("VIN"), Net("GND"), Net("LED_DRV"), Net("LED_A")
connect(vin, j1[1], u1[1])
connect(gnd, j1[2], u1[8], d1["K"])
connect(led_drv, u1[2], r1[1])
connect(led_a, r1[2], d1["A"])
design.add(Power(vin, gnd))
design.rules.netclass("PWR", clearance=mm(0.2), track_width=mm(0.5), nets=(vin, gnd))

j1.place(mm(6), mm(15))
u1.place(mm(20), mm(15), locked=True)
r1.place(mm(34), mm(9))
d1.place(mm(42), mm(20))
