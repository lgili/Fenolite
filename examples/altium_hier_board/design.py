# SPDX-License-Identifier: CC0-1.0
# Authored for Fenolite as an example; no file, value, name or layout comes from any other project.
"""Altium hierarchy with a board: the blink circuit of ``examples/blink_2layer`` split into two modules, so
the Altium build writes a PCB document whose parts sit on module sheets.

Build it with ``fenolite build examples/altium_hier_board/design.py --out build/altium_hier_board --target
altium --altium-sheets modules --confirm``. ``U1`` and ``R1`` are in the module ``driver`` and ``D1`` in
the module ``led``, so each PCB component links to its schematic part through the sheet symbol of its
module (step H7 of ``docs/evidence/altium-schematic.md``). The libraries come from the authored CC0 mini
library (``tests/data/libs``) through this folder's ``fp-lib-table`` and ``sym-lib-table``.
"""

from fenolite.dsl import Design, Module, Net, Part, Power, connect, mm

design = Design("altium_hier_board")
design.board(mm(50), mm(30))

driver = Module("driver")
u1 = Part("U1", "Mini:Mini_QFP32_IC", value="MCU")
r1 = Part("R1", "Mini:Mini_R", footprint="Mini:Mini_R_0603", value="330")
driver.add(u1, r1)

led = Module("led")
d1 = Part("D1", "Mini:Mini_LED", footprint="Mini:Mini_LED_THT_3mm", value="LED")
led.add(d1)

design.add(driver, led)

vin, gnd, led_drv, led_a = Net("VIN"), Net("GND"), Net("LED_DRV"), Net("LED_A")
connect(vin, u1[9])
connect(gnd, u1[10], d1[1])
connect(led_drv, u1[1], r1[1])
connect(led_a, r1[2], d1[2])
design.add(Power(vin, gnd))
design.rules.netclass("PWR", clearance=mm(0.2), track_width=mm(0.5), nets=(vin, gnd))

u1.place(mm(14), mm(15), locked=True)
r1.place(mm(32), mm(9))
d1.place(mm(38), mm(20), side="bottom")
