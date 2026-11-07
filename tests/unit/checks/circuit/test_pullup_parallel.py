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


def test_exact_parallel_waiver_keeps_the_other_line_and_expires_with_a_wrong_digest():
    import dataclasses

    from fenolite.checks.circuit import judge_circuit
    from fenolite.cli._contracts import classes_of, devices_of
    from fenolite.model.findings import Waiver

    extra = """
second = design.use(i2c_pullups, "second")
second.place(mm(18), mm(18))
connect(second.RAIL, dut.RAIL)
connect(second.BUS, dut.BUS)
"""
    with bench("i2c_pullups", extra=extra) as design:
        model = design.model
        devices = devices_of(model, design.path)
        classes = classes_of(model, devices)
        baseline = judge_circuit(model, devices=devices, classes=classes)
        original = [item for item in baseline.issues if item.code == "circuit.pullup-parallel"]
        assert len(original) == 2 and all(item.severity == "warning" for item in original)
        target = original[0]
        digest = target.hint.rsplit("digest ", 1)[1]
        waiver = Waiver(
            name="reviewed-line",
            code=target.code,
            items=(target.where,),
            reason="authored current-budget review",
            digest=digest,
        )
        matched = judge_circuit(model, devices=devices, classes=classes, waivers=(waiver,))
        found = [item for item in matched.issues if item.code == target.code]
        assert len(found) == 2
        assert {item.where: item.severity for item in found} == {
            original[0].where: "info",
            original[1].where: "warning",
        }
        wrong = "0" * 16 if digest != "0" * 16 else "1" * 16
        expired = judge_circuit(
            model,
            devices=devices,
            classes=classes,
            waivers=(dataclasses.replace(waiver, digest=wrong),),
        )
        assert all(item.severity == "warning" for item in expired.issues if item.code == target.code)
        assert expired.waived is not None
        assert any(item.code == "check.waiver-expired" for item in expired.waived.reports)


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
