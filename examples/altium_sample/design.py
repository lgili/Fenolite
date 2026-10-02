# SPDX-License-Identifier: CC0-1.0
# Authored for Fenolite as an example; no file, value, name or layout comes from any other project.
"""Altium sample: a 5 V regulator, a small driver with an enable pull-up, and an LED, for the Altium target.

Build it with ``fenolite build examples/altium_sample/design.py --out build/altium_sample --target altium
--confirm``. The lib ids name the libraries ``FenoliteSample.SchLib`` and ``FenoliteSample.PcbLib``,
which Fenolite does not ship: the build reads no library. Every pin is connected by its number.
"""

from fenolite.dsl import Design, Module, Net, Part, Power, connect

SCHLIB = "FenoliteSample.SchLib"
PCBLIB = "FenoliteSample.PcbLib"

design = Design("altium_sample")

j1 = Part("J1", f"{SCHLIB}:HDR2", footprint=f"{PCBLIB}:HDR1X2")
r2 = Part("R2", f"{SCHLIB}:RES", footprint=f"{PCBLIB}:R0603", value="10k")
u2 = Part("U2", f"{SCHLIB}:DRV4", footprint=f"{PCBLIB}:SOT143", value="DRV4")

led = Module("led")
r1 = Part("R1", f"{SCHLIB}:RES", footprint=f"{PCBLIB}:R0603", value="330")
d1 = Part("D1", f"{SCHLIB}:LED", footprint=f"{PCBLIB}:LED0603", value="red")
led.add(r1, d1)

power = Module("power")
u1 = Part("U1", f"{SCHLIB}:LDO3", footprint=f"{PCBLIB}:SOT23", value="5V")
c1 = Part("C1", f"{SCHLIB}:CAP", footprint=f"{PCBLIB}:C0603", value="10uF")
c2 = Part("C2", f"{SCHLIB}:CAP", footprint=f"{PCBLIB}:C0603", value="10uF")
power.add(u1, c1, c2)

design.add(j1, r2, u2, led, power)

vin, gnd, p5v = Net("VIN"), Net("GND"), Net("+5V")
en, led_drv, led_a = Net("EN"), Net("LED_DRV"), Net("LED_A")
connect(vin, j1[1], u1[1], c1[1])
connect(gnd, j1[2], u1[2], c1[2], c2[2], d1[1], u2[2])
connect(p5v, u1[3], c2[1], u2[1], r2[1])
connect(en, r2[2], u2[4])
connect(led_drv, u2[3], r1[1])
connect(led_a, r1[2], d1[2])
design.add(Power(vin, gnd), Power(p5v, gnd))
