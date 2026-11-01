# SPDX-License-Identifier: CC0-1.0
# Copyright (c) 2026 Fenolite contributors
# Authored for Fenolite; circuit, dimensions and illustrative inputs are original.
"""Authored bench for i2c_pullups; every port is connected to J1.

Bench placement and copper are authored in code, then captured. No GUI review is claimed.
Protection figures, where used, are illustrative and UNVERIFIED.
"""

from fenolite.blocks import i2c_pullups
from fenolite.dsl import Design, Part, connect, mm, supply, volt

design = Design("i2c_pullups_usage")
design.board(mm(40), mm(30))
j1 = Part("J1", "Fenolite:Connector_4", footprint="Fenolite:Header_1x4_P2.54")
design.add(j1)
dut = design.use(i2c_pullups, "dut")
dut.place(mm(12), mm(12))
j1.place(mm(28), mm("13.81"), rot=180)
connect(dut.RAIL.hv, j1[1])
ground = Part("J2", "Fenolite:Connector_2", footprint="Fenolite:Header_1x2_P2.54")
design.add(ground)
ground.place(mm(28), mm("25.27"), rot=180)
connect(dut.RAIL.lv, j1[2], ground[1], ground[2])
connect(dut.BUS.sda, j1[3])
connect(dut.BUS.scl, j1[4])
design.rig(supply(dut.RAIL, dut.RAIL.lv, voltage=volt("3.3").pct(5), name="bench"))

dut.part("r_sda").field("Reference", layer="fab")
dut.part("r_scl").field("Reference", layer="fab")

# Host copper: original bench routes; the captured asset holds the local block copper.

sda, scl = dut.part("r_sda"), dut.part("r_scl")
design.via("bench_supply_via", mm("11.2"), mm(10), net=connect(dut.RAIL), diameter=mm("0.6"), drill=mm("0.3"))
design.track("bench_supply_front", sda.pad(1), (mm("11.2"), mm(10)), width=mm("0.25"))
design.track("bench_supply_back", (mm("11.2"), mm(10)), j1.pad(1), layer="B.Cu", width=mm("0.25"))
design.via("bench_sda_via", mm("14.3"), mm(12), net=connect(dut.BUS.sda), diameter=mm("0.6"), drill=mm("0.3"))
design.track("bench_sda_front", sda.pad(2), (mm("14.3"), mm(12)), width=mm("0.25"))
design.track("bench_sda_back", (mm("14.3"), mm(12)), j1.pad(3), layer="B.Cu", width=mm("0.25"))
design.via("bench_scl_via", mm("14.3"), mm(15), net=connect(dut.BUS.scl), diameter=mm("0.6"), drill=mm("0.3"))
design.track("bench_scl_front", scl.pad(2), (mm("14.3"), mm(15)), width=mm("0.25"))
design.track("bench_scl_back", (mm("14.3"), mm(15)), j1.pad(4), layer="B.Cu", width=mm("0.25"))
design.track(
    "bench_ground", j1.pad(2), (mm(31), mm("12.54")), (mm(31), mm(24)), ground.pad(1), width=mm("0.25")
)
design.track("bench_ground_header", ground.pad(1), ground.pad(2), width=mm("0.25"))
