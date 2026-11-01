# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Sensor: the converted script of the authored fidelity fixture ``tests/data/fidelity/sensor/``.

A four-layer board with a controller, a resistor and an LED, two net classes, a custom rule, a ground
pour on an inner layer, a track with an arc, through and blind vias, and a line of board text. The project
under ``../sensor/`` stands for the original that ``fenolite verify-source`` proves this script against.
Authored for Fenolite as a test fixture of change c0278; no file, value, name or layout comes from any other
project.
"""

from fenolite.dsl import Design, Net, Part, Power, arc_to, connect, mm, select, via_step

design = Design("sensor")
design.board(mm(40), mm(30), copper=4)

u1 = Part("U1", "Mini:Mini_QFP32_IC", value="MCU")
r1 = Part("R1", "Mini:Mini_R", footprint="Mini:Mini_R_0603", value="1k")
d1 = Part("D1", "Mini:Mini_LED", footprint="Mini:Mini_LED_THT_3mm", value="LED")
design.add(u1, r1, d1)

vin, gnd, sig, led = Net("VIN"), Net("GND"), Net("SIG"), Net("LED")
connect(vin, u1[9])
connect(gnd, u1[10], d1[1])
connect(sig, u1[1], r1[1])
connect(led, r1[2], d1[2])
u1.unused_no_connect()
design.add(Power(vin, gnd))
design.rules.netclass("PWR", clearance=mm(0.25), track_width=mm(0.4), nets=(vin, gnd))
design.rules.netclass("SIG", clearance=mm(0.2), track_width=mm(0.25), nets=(sig, led))
design.rules.rule("sig_gap", "clearance", where=select.netclass("SIG"), min=mm(0.2))

u1.place(mm(12), mm(15), locked=True)
r1.place(mm(27), mm(9))
d1.place(mm(32), mm(21))

design.track(
    "sig",
    u1.pad(1), (mm(6), mm(12.2)), (mm(6), mm(6)),
    arc_to((mm("6.585786"), mm("4.585786")), (mm(8), mm(4))),
    (mm(26.2), mm(4)), r1.pad(1),
    width=mm(0.25),
)  # fmt: skip
design.track(
    "led",
    r1.pad(2), (mm(31), mm(9)),
    via_step(mm(31), mm(14), to="In2.Cu", kind="blind", diameter=mm(0.6), drill=mm(0.3)),
    via_step(mm(31), mm(18), to="B.Cu", diameter=mm(0.6), drill=mm(0.3)),
    d1.pad(2),
    width=mm(0.25),
)  # fmt: skip
design.via("gnd_tie", mm(20), mm(25), net=gnd, diameter=mm(0.6), drill=mm(0.3))
design.zone(gnd, layers=("In1.Cu",), clearance=mm(0.3), connection="solid")
design.text("label", "SENSOR", (mm(20), mm(27)), size=mm(1.2), thickness=mm(0.18))
