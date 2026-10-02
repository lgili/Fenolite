# SPDX-License-Identifier: CC0-1.0
# Authored for Fenolite as an example; no file, value, name or layout comes from any other project.
"""Blink on KiCad's official libraries: the circuit of ``examples/blink_2layer`` with an STM32G4
symbol, ``Device:R`` and ``Device:LED``.

Only ``tests/libs/test_build_official.py`` builds it, into a temporary folder, where the official
libraries are installed; nothing generated from it is committed.
"""

from fenolite.dsl import Design, Net, Part, Power, connect, mm

design = Design("blink_official")
design.board(mm(50), mm(30))

u1 = Part("U1", "MCU_ST_STM32G4:STM32G431K6Tx", value="STM32G431K6Tx")
r1 = Part("R1", "Device:R", footprint="Resistor_SMD:R_0603_1608Metric", value="330")
d1 = Part("D1", "Device:LED", footprint="LED_THT:LED_D3.0mm", value="LED")
design.add(u1, r1, d1)

vin, gnd, led_drv, led_a = Net("VIN"), Net("GND"), Net("LED_DRV"), Net("LED_A")
connect(vin, u1["VDD"])
connect(gnd, u1["VSS"], d1["K"])
connect(led_drv, u1["PA5"], r1[1])
connect(led_a, r1[2], d1["A"])
design.add(Power(vin, gnd))
design.rules.netclass("PWR", clearance=mm(0.2), track_width=mm(0.5), nets=(vin, gnd))

u1.place(mm(14), mm(15), locked=True)
r1.place(mm(32), mm(9))
d1.place(mm(38), mm(20), side="bottom")
