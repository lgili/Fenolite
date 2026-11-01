# SPDX-License-Identifier: CC0-1.0
# Copyright (c) 2026 Fenolite contributors
# Authored for Fenolite; circuit, dimensions and illustrative inputs are original.
"""Authored bench for protected_input; every port is connected to J1.

Bench placement and copper are authored in code, then captured. No GUI review is claimed.
Protection figures, where used, are illustrative and UNVERIFIED.
"""

from fenolite.blocks import protected_input
from fenolite.dsl import Design, Part, amp, connect, mm, ohm, supply, volt

design = Design("protected_input_usage")
design.board(mm(40), mm(30))
j1 = Part("J1", "Fenolite:Connector_3", footprint="Fenolite:Header_1x3_P2.54")
design.add(j1)
dut = design.use(
    protected_input,
    "dut",
    protection="Example:IllustrativeTVS",
    clamp=volt("9.2").max(),
    abs_max=volt("3.6"),
    r_series=ohm("1.5k"),
    inject_max=amp("5m"),
    hold=volt("3.6"),
)
dut.place(mm(12), mm(12))
j1.place(mm(28), mm("12.54"), rot=180)
connect(dut.EXT, j1[1])
connect(dut.INT, j1[2])
connect(dut.GND, j1[3])
design.rig(supply(dut.EXT, dut.GND, voltage=volt(5), name="bench"))

dut.part("tvs").field("Reference", layer="fab")
dut.part("r").field("Reference", layer="fab")

# Host copper: original bench routes; the captured asset holds the local block copper.

tvs, r = dut.part("tvs"), dut.part("r")
design.via("bench_ext_via", mm(14), mm(12), net=connect(dut.EXT), diameter=mm("0.6"), drill=mm("0.3"))
design.track("bench_ext_back", (mm(14), mm(12)), j1.pad(1), layer="B.Cu", width=mm("0.25"))
design.via("bench_int_via", mm("16.8"), mm("15.5"), net=connect(dut.INT), diameter=mm("0.6"), drill=mm("0.3"))
design.track("bench_int_front", r.pad(2), (mm("16.8"), mm("15.5")), width=mm("0.25"))
design.track("bench_int_back", (mm("16.8"), mm("15.5")), j1.pad(2), layer="B.Cu", width=mm("0.25"))
design.track(
    "bench_ground_back",
    tvs.pad("A").at(mm(0), mm(1)),
    (mm(9), mm(11)),
    (mm(9), mm(18)),
    (mm(28), mm(18)),
    j1.pad(3),
    layer="B.Cu",
    width=mm("0.25"),
)
