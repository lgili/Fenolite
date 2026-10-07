# SPDX-License-Identifier: CC0-1.0
# Authored for Fenolite as an example; no file, value, name or layout comes from any other project.
"""Kit sample ``libs``: seven catalog parts, built for the libraries the build writes.

It is one of the five samples of the Altium verification kit (``docs/altium-kit.md``). Its schematic
library holds seven symbols and its PCB library seven footprints, all from Fenolite's own catalog; the
steps of groups K1 and K9 open the two libraries, save them again and update the schematic from them.
"""

from fenolite.dsl import Design, Net, Part, Power, connect, mm

design = Design("libs")
design.board(mm(60), mm(40))

j1 = Part("J1", "Fenolite:Connector_2", footprint="Fenolite:Header_1x2_P2.54", value="SUPPLY")
j2 = Part("J2", "Fenolite:Connector_4", footprint="Fenolite:Header_1x4_P2.54", value="PORT")
u1 = Part("U1", "Fenolite:Microcontroller", footprint="Fenolite:DIP8_Microchip_P", value="MCU")
r1 = Part("R1", "Fenolite:Resistor", footprint="Fenolite:Chip_0603", value="330")
c1 = Part("C1", "Fenolite:Capacitor", footprint="Fenolite:Chip_0805", value="100n")
# The LED land numbers its pads as the manufacturer does, pad 1 the cathode, while the symbol's pin 1 is the
# anode: the map puts the anode (pin 1) on pad 2 and the cathode (pin 2) on pad 1.
d1 = Part(
    "D1",
    "Fenolite:LED",
    footprint="Fenolite:LED0603_Kingbright_APT1608SURCK",
    value="red",
    pad_map={"1": "2", "2": "1"},
)
d2 = Part("D2", "Fenolite:Diode", footprint="Fenolite:DO214AC", value="rectifier")
design.add(j1, j2, u1, r1, c1, d1, d2)

vin, vcc, gnd, led_drv, led_a = Net("VIN"), Net("VCC"), Net("GND"), Net("LED_DRV"), Net("LED_A")
port = [Net(f"P{k}") for k in range(4)]
connect(vin, j1[1], d2[2])
connect(vcc, d2[1], u1[1], c1[1])
connect(gnd, j1[2], u1[8], c1[2], d1["K"])
connect(led_drv, u1[2], r1[1])
connect(led_a, r1[2], d1["A"])
for k, net in enumerate(port):
    connect(net, j2[k + 1], u1[k + 3])
design.add(Power(vin, gnd), Power(vcc, gnd))

j1.place(mm(6), mm(12))
j2.place(mm(6), mm(28))
d2.place(mm(16), mm(8))
u1.place(mm(28), mm(20), locked=True)
c1.place(mm(28), mm(8))
r1.place(mm(42), mm(14))
d1.place(mm(50), mm(26))
