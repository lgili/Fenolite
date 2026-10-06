# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The design of the lens acceptance test (change c0069): a part at the top and two modules, ``power`` and
``io``, whose local nets are named from the module path. Authored for Fenolite: no file, value, name or
layout comes from any other project.

The test builds it, edits the board as KiCad would, renames ``power`` and adds a part, and checks that the
rebuild keeps every edit. The libraries are the authored CC0 mini library, through this folder's tables.
"""

from fenolite.dsl import Design, Module, Net, Part, Power, connect, mm

design = Design("lensfix")
design.board(mm(60), mm(40))

u1 = Part("U1", "Mini:Mini_QFP32_IC", value="MCU")
design.add(u1)
vin, gnd, drv = Net("VIN"), Net("GND"), Net("DRV")
design.add(Power(vin, gnd))

power = Module("power")
r1 = Part("R1", "Mini:Mini_R", footprint="Mini:Mini_R_0603", value="10k")
r2 = Part("R2", "Mini:Mini_R", footprint="Mini:Mini_R_0603", value="10k")
r3 = Part("R3", "Mini:Mini_R", footprint="Mini:Mini_R_0603", value="330")
d1 = Part("D1", "Mini:Mini_LED", footprint="Mini:Mini_LED_THT_3mm", value="LED")
power.add(r1, r2, r3, d1)
design.add(power)
fb = Net(f"{power.path}/FB")
power_led = Net(f"{power.path}/LED_A")
connect(fb, r1[2], r2[1], u1[2])
connect(power_led, r3[2], d1[1])

io = Module("io")
r4 = Part("R4", "Mini:Mini_R", footprint="Mini:Mini_R_0603", value="330")
d2 = Part("D2", "Mini:Mini_LED", footprint="Mini:Mini_LED_THT_3mm", value="LED")
r5 = Part("R5", "Mini:Mini_R", footprint="Mini:Mini_R_0603", value="10k")
io.add(r4, d2, r5)
design.add(io)
io_led = Net(f"{io.path}/LED_A")
sense = Net(f"{io.path}/SENSE")
connect(io_led, r4[2], d2[1])
connect(sense, u1[3], r5[1])

connect(vin, u1[9], r1[1], r3[1])
connect(gnd, u1[10], r2[2], d1[2], d2[2], r5[2])
connect(drv, u1[1], r4[1])

u1.place(mm(30), mm(27), locked=True)
r1.place(mm(10), mm(10))
r2.place(mm(16), mm(10))
r3.place(mm(10), mm(15))
d1.place(mm(18), mm(17))
r4.place(mm(40), mm(10))
d2.place(mm(47), mm(10))
r5.place(mm(45), mm(18))
