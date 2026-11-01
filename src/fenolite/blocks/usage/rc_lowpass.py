# SPDX-License-Identifier: CC0-1.0
# Copyright (c) 2026 Fenolite contributors
# Authored for Fenolite; circuit, dimensions and illustrative inputs are original.
"""Authored bench for rc_lowpass; every port is connected to J1.

Bench placement and copper are authored in code, then captured. No GUI review is claimed.
Protection figures, where used, are illustrative and UNVERIFIED.
"""

from fenolite.blocks import rc_lowpass
from fenolite.dsl import Design, Part, connect, mm, supply, volt

design = Design("rc_lowpass_usage")
design.board(mm(40), mm(30))
j1 = Part("J1", "Fenolite:Connector_3", footprint="Fenolite:Header_1x3_P2.54")
design.add(j1)
dut = design.use(rc_lowpass, "dut")
dut.place(mm(12), mm(12))
j1.place(mm(28), mm("12.54"), rot=180)
connect(dut.IN, j1[1])
connect(dut.OUT, j1[2])
connect(dut.GND, j1[3])
design.rig(supply(dut.IN, dut.GND, voltage=volt(5), name="bench"))

dut.part("filter_R").field("Reference", layer="fab")
dut.part("filter_C").field("Reference", layer="fab")

# Host copper: original bench routes; the captured asset holds the local block copper.

r, c = dut.part("filter_R"), dut.part("filter_C")
design.via("bench_in_via", mm("11.2"), mm(10), net=connect(dut.IN), diameter=mm("0.6"), drill=mm("0.3"))
design.track("bench_in_front", r.pad(1), (mm("11.2"), mm(10)), width=mm("0.25"))
design.track("bench_in_back", (mm("11.2"), mm(10)), j1.pad(1), layer="B.Cu", width=mm("0.25"))
design.via("bench_out_via", mm(14), mm(12), net=connect(dut.OUT), diameter=mm("0.6"), drill=mm("0.3"))
design.track("bench_out_back", (mm(14), mm(12)), j1.pad(2), layer="B.Cu", width=mm("0.25"))
design.via("bench_gnd_via", mm("16.8"), mm("15.5"), net=connect(dut.GND), diameter=mm("0.6"), drill=mm("0.3"))
design.track("bench_gnd_front", c.pad(2), (mm("16.8"), mm("15.5")), width=mm("0.25"))
design.track("bench_gnd_back", (mm("16.8"), mm("15.5")), j1.pad(3), layer="B.Cu", width=mm("0.25"))
