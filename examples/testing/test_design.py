# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Tests for the authored fixture; no CAD install or pytest plugin is needed."""

from pathlib import Path

from fenolite.dsl import block, connect, mm
from fenolite.testing import assert_render, instantiate, load

HERE = Path(__file__).resolve().parent


@block
def divider(b, *, top="1000", bottom="2000"):
    """A divider block tested alone. Ports: VIN, MID, GND."""
    vin, mid, gnd = b.port("VIN"), b.port("MID"), b.port("GND")
    r_top = b.part("R_TOP", "Fenolite:Resistor", footprint="Fenolite:Chip_0603", value=top)
    r_bottom = b.part("R_BOT", "Fenolite:Resistor", footprint="Fenolite:Chip_0603", value=bottom)
    connect(vin, r_top[1])
    connect(mid, r_top[2], r_bottom[1])
    connect(gnd, r_bottom[2])
    r_top.place(mm(10), mm(10), rot=90)
    r_bottom.place(mm(20), mm(10), rot=90)


def test_connections():
    with load(HERE / "design.py") as d:
        assert d.net("GND").pins == ("R1-1", "R2-1")
        assert d.ref("R1")[1].net == "GND"
        assert d.connected("R1-1", "R2-1")
        assert d.connected("R1-1", "R2-1", copper=True)
        assert not d.findings("build.unattached")


def test_ground_picture():
    assert_render(HERE / "design.py", HERE / "golden/net-GND.svg", net="GND")


def test_divider_block():
    with instantiate(divider, bottom="3000") as d:
        assert d.ref("dut/R_BOT").value == "3000"
        assert d.connected(d.ref("dut/R_TOP")[2], d.net("dut/MID"))
        assert not d.connected(d.ref("dut/R_TOP")[1], d.net("dut/GND"))
