# SPDX-License-Identifier: CC0-1.0
# Authored for Fenolite as an example; no file, value, name or layout comes from any other project.
"""Blink: a mini MCU drives an LED through a resistor, on a 50 mm x 30 mm two-layer board.

Build it with ``fenolite build examples/blink_2layer/design.py --out build/blink --confirm``. The
libraries come from the authored CC0 mini library (``tests/data/libs``) through this folder's
``fp-lib-table`` and ``sym-lib-table``.
"""

from fenolite.dsl import Design, Net, Part, Power, connect, mm, no_connect

design = Design("blink")
design.board(mm(50), mm(30))

u1 = Part("U1", "Mini:Mini_QFP32_IC", value="MCU")
r1 = Part("R1", "Mini:Mini_R", footprint="Mini:Mini_R_0603", value="330")
d1 = Part("D1", "Mini:Mini_LED", footprint="Mini:Mini_LED_THT_3mm", value="LED")
design.add(u1, r1, d1)

vin, gnd, led_drv, led_a = Net("VIN"), Net("GND"), Net("LED_DRV"), Net("LED_A")
connect(vin, u1[9])
connect(gnd, u1[10], d1[1])
connect(led_drv, u1[1], r1[1])
connect(led_a, r1[2], d1[2])
# The blink uses three pins of the controller. The other 29 are marked, so the electrical rules checks
# of both tools know that they are left open on purpose.
no_connect(*(u1[pin] for pin in range(1, 33) if pin not in (1, 9, 10)))
design.add(Power(vin, gnd))
design.rules.netclass("PWR", clearance=mm(0.2), track_width=mm(0.5), nets=(vin, gnd))

u1.place(mm(14), mm(15), locked=True)
r1.place(mm(32), mm(9))
d1.place(mm(38), mm(20), side="bottom")
