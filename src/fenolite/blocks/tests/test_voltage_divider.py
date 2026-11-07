# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Plain self-tests for the divider; no test framework is needed at runtime."""

from fractions import Fraction

from fenolite.blocks import voltage_divider
from fenolite.blocks.tests._support import bench, high, low, part, refused
from fenolite.dsl import volt
from fenolite.testing import instantiate, stimulus


def test_default_divider() -> None:
    with instantiate(voltage_divider, stimulus=stimulus(HI=volt(12).pct(2), LO=volt(0))) as design:
        assert part(design, "divider_top").value == "137k"
        assert part(design, "divider_bot").value == "52k3"
        rows = design.requirements("dut/expect*")
        assert len(rows) == 3 and all(r.status == "pass" for r in rows)
        assert low(rows[0].value) <= Fraction("3.20224626210248")
        assert high(rows[0].value) >= Fraction("3.43084758533958")
        assert high(rows[1].limit) < Fraction("0.001104606")


def test_unreachable_output() -> None:
    refused(lambda: instantiate(voltage_divider, vin=volt(12).pct(10)), "gen.unachievable")


def test_two_dividers_no_collision() -> None:
    with bench(
        "voltage_divider",
        extra="""
second = design.use(voltage_divider, "second", vout=volt("2.5").pct(5))
second.place(mm(18), mm(18))
connect(second.HI, dut.HI)
connect(second.LO, dut.LO)
extra = Part("J2", "Fenolite:Connector_2", footprint="Fenolite:Header_1x2_P2.54")
design.add(extra)
extra.place(mm(28), mm(22))
connect(second.OUT, extra[1])
connect(second.LO, extra[2])
""",
    ) as design:
        parts = [c for c in design.model.circuit.components if c.ref.startswith("R")]
        assert len(parts) == 4 and len({c.ref for c in parts}) == 4
