# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Authored for Fenolite as test data; no file, value, name or layout comes from any other project.

The tree sample of change c0086: a supply, a sensing stage and four indicator LEDs, for the Altium target.

The design has the modules ``power``, ``io`` and ``io/leds``, so a ``modules`` build writes four sheets.
Its symbols are catalog symbols, which are drawn from their own graphics. Its footprint links name the
library ``FenoliteTree.PcbLib``, which Fenolite does not ship: the build writes no PCB library.

- ``SENSE`` leaves ``io`` as an output (the amplifier drives it), ``ALARM`` and ``SENSE_IN`` enter it as
  inputs, and ``LED_K`` crosses ``io/leds`` between passive pins only, so it stays unspecified.
- ``D0`` to ``D3`` run from ``J2`` on the top sheet to the LEDs two levels down. The DSL has no bus, so
  ``tests/_altium_tree.py`` adds the bus ``D`` of these four nets to the model before it builds.
- ``L1`` holds a value with accented characters and ``C1`` two properties, which become hidden parameters.
"""

from fenolite.dsl import Design, Module, Net, Part, Power, connect

LIB = "Fenolite"
PCBLIB = "FenoliteTree.PcbLib"

design = Design("tree")

j1 = Part("J1", f"{LIB}:Connector_4", footprint=f"{PCBLIB}:HDR1X4", value="IN")
j2 = Part("J2", f"{LIB}:Connector_4", footprint=f"{PCBLIB}:HDR1X4", value="DATA")
u1 = Part("U1", f"{LIB}:Comparator", footprint=f"{PCBLIB}:SOT23-5", value="CMP")

power = Module("power")
u2 = Part("U2", f"{LIB}:Linear_Regulator", footprint=f"{PCBLIB}:SOT223", value="3V3")
l1 = Part("L1", f"{LIB}:Inductor", footprint=f"{PCBLIB}:L0805", value="Indutância 10 µH")
c1 = Part(
    "C1",
    f"{LIB}:Capacitor",
    footprint=f"{PCBLIB}:C0603",
    value="10uF",
    properties={"MPN": "X-1", "Note": "tolerância ±10 %"},
)
power.add(u2, l1, c1)

io = Module("io")
u3 = Part("U3", f"{LIB}:Operational_Amplifier", footprint=f"{PCBLIB}:SOT23-5", value="BUF")
q1 = Part("Q1", f"{LIB}:BJT_NPN", footprint=f"{PCBLIB}:SOT23", value="NPN")
leds = Module("leds")
d = [Part(f"D{k}", f"{LIB}:LED", footprint=f"{PCBLIB}:LED0603", value="red") for k in range(1, 5)]
leds.add(*d)
io.add(u3, q1, leds)

design.add(j1, j2, u1, power, io)

vin, gnd, vreg, p3v3 = Net("VIN"), Net("GND"), Net("VREG"), Net("+3V3")
sense_in, sense, ref, alarm, led_k = Net("SENSE_IN"), Net("SENSE"), Net("REF"), Net("ALARM"), Net("LED_K")
data = [Net(f"D{k}") for k in range(4)]

connect(vin, j1[1], u2[1])
connect(gnd, j1[2], u1[5], u2[2], c1[2], u3[5], q1[3])
connect(vreg, u2[3], l1[1])
connect(p3v3, l1[2], c1[1], u1[4], u3[4])
connect(sense_in, j1[3], u3[2])
connect(sense, u3[1], u3[3], u1[2])
connect(ref, j1[4], u1[3])
connect(alarm, u1[1], q1[1])
connect(led_k, q1[2], *(led[2] for led in d))
for k, net in enumerate(data):
    connect(net, j2[k + 1], d[k][1])
design.add(Power(vin, gnd), Power(p3v3, gnd))
