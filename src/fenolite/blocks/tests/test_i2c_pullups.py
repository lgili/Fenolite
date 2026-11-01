# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Plain I2C tests use a connector on the rail return as an explicit rig reference."""

from fenolite.blocks.tests._support import bench, part
from fenolite.dsl import between, farad
from fenolite.dsl.generators import i2c_mode_limits


def test_window_for_each_mode() -> None:
    for mode in ("standard", "fast", "fast-plus"):
        with bench("i2c_pullups", f"mode={mode!r}") as design:
            rows = design.requirements("dut/expect*")
            assert len(rows) == 5 and all(row.status == "pass" for row in rows)
            a, b = part(design, "r_sda"), part(design, "r_scl")
            assert a.value == b.value
            _, _, maximum = i2c_mode_limits(mode, between(farad("10p"), farad("200p")))
            assert a.value_range is not None and a.value_range.high is not None
            assert maximum.high is not None
            assert a.value_range.high.fraction() <= maximum.high
            bus = next(p for p in design.model.circuit.ports if p.name == "BUS")
            rail = next(p for p in design.model.circuit.ports if p.name == "RAIL")
            assert bus.reference == rail.id


def test_two_buses() -> None:
    with bench(
        "i2c_pullups",
        extra="""
second = design.use(i2c_pullups, "second")
second.place(mm(18), mm(18))
connect(second.RAIL, dut.RAIL)
other = Part("J3", "Fenolite:Connector_2", footprint="Fenolite:Header_1x2_P2.54")
design.add(other)
other.place(mm(6), mm(24))
connect(second.BUS.sda, other[1])
connect(second.BUS.scl, other[2])
""",
    ) as design:
        assert not design.findings("circuit.pullup-parallel")
