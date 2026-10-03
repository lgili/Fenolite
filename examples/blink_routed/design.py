# SPDX-License-Identifier: CC0-1.0
# Authored for Fenolite as an example; no file, value, name or layout comes from any other project.
"""Blink, routed by the script: the blink of ``examples/blink_2layer`` with four copper intents.

Build it with ``fenolite build examples/blink_routed/design.py --out build/blink_routed --confirm``.
The copper is declared by pad references and points in the frame of ``place()``. The build resolves it
after placement, so a part moved in KiCad pulls its tracks along on the next build (``docs/copper.md``).
"""

from fenolite.dsl import Design, Net, Part, Power, connect, mm, via_step

design = Design("blink_routed")
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
design.add(Power(vin, gnd))
design.rules.netclass("PWR", clearance=mm(0.2), track_width=mm(0.5), nets=(vin, gnd))

u1.place(mm(14), mm(15), locked=True)
r1.place(mm(32), mm(9))
d1.place(mm(38), mm(20), side="bottom")

# Copper. Each key names its intent: the tracks and vias it creates keep their ids across builds.
# The net of a track comes from its pads; a via step changes the layer with a through via.
design.track(
    "led_drv",
    u1.pad(1), (mm(8), mm(12.2)), (mm(8), mm(7)), (mm(31.2), mm(7)), r1.pad(1),
    width=mm(0.3),
)  # fmt: skip
design.track(
    "led_a",
    r1.pad(2), (mm(36), mm(9)),
    via_step(mm(36), mm(14), to="B.Cu", diameter=mm(0.6), drill=mm(0.3)),
    d1.pad(2),
    width=mm(0.3),
)  # fmt: skip
# No width here: class PWR sets 0.5 mm for GND. It sets no via sizes, so every via gives its own.
design.track(
    "gnd",
    u1.pad(10), (mm(12), mm(26)), via_step(mm(14), mm(26), to="B.Cu", diameter=mm(0.6), drill=mm(0.3)),
    (mm(38), mm(26)), d1.pad(1),
)  # fmt: skip
# Stitching vias every 5 mm along the bottom part of the GND track, which connects them.
design.stitch(
    "gnd_fence",
    net=gnd,
    pitch=mm(5),
    along=((mm(16), mm(26)), (mm(36), mm(26))),
    diameter=mm(0.6),
    drill=mm(0.3),
)
