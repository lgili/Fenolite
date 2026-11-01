# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""One parallel warning per shared I2C line, with exact combined resistance."""

from fenolite.blocks.tests._support import bench


def test_two_sets_on_one_bus():
    extra = """
second = design.use(i2c_pullups, "second")
second.place(mm(18), mm(18))
connect(second.RAIL, dut.RAIL)
connect(second.BUS, dut.BUS)
"""
    with bench("i2c_pullups", extra=extra) as design:
        found = design.findings("circuit.pullup-parallel")
        assert len(found) == 2
        assert all("parallel" in f.message and "Ω" in f.message for f in found)
        assert {f.where.rsplit(".", 1)[-1] for f in found} == {"sda", "scl"}
        assert all(sum(ref in f.message for ref in ("R1", "R2", "R3", "R4")) == 2 for f in found)


def test_one_set_has_no_parallel_warning():
    with bench("i2c_pullups") as design:
        assert not design.findings("circuit.pullup-parallel")


def test_actual_rail_outside_generator_assumptions_is_not_passed():
    import dataclasses

    from fenolite.checks.circuit import judge_circuit
    from fenolite.cli._contracts import classes_of, devices_of
    from fenolite.model.circuit import Decimal10, ValueRange

    with bench("i2c_pullups") as design:
        model = design.model
        contracts = model.rules.contracts
        supplied = dataclasses.replace(
            contracts.rig[0],
            voltage=ValueRange("volt", Decimal10(18, -1), Decimal10(18, -1), Decimal10(18, -1)),
        )
        changed = dataclasses.replace(
            model,
            rules=dataclasses.replace(model.rules, contracts=dataclasses.replace(contracts, rig=(supplied,))),
        )
        devices = devices_of(changed, design.path)
        result = judge_circuit(changed, devices=devices, classes=classes_of(changed, devices))
        assert any(
            i.code == "circuit.expect-failed" and "supply within selection range" in i.message
            for i in result.issues
        )
