# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Minimal exact contract and metadata bridges used by the starter bodies."""

from fractions import Fraction

import pytest

from fenolite.blocks import protected_input
from fenolite.checks.circuit import judge_circuit
from fenolite.dsl import Design, DslError, block, describe, param, to_model, volt, within
from fenolite.dsl.contracts import operand
from fenolite.dsl.quantity import Range
from fenolite.dsl.record import record_data
from fenolite.model import canonical
from fenolite.model.circuit import Decimal10, ValueRange
from fenolite.model.rules import ExpectNode


def test_bounded_ratio_literal_roundtrip_and_judgement():
    design = Design("bounded_ratio")
    pi = Range("ratio", Fraction("3.14159265358"), Fraction("3.14159265359"))
    design.expect(within(operand(pi) * volt(1), volt(3).pct(10)), "enclosed constant")
    model = to_model(design)
    literal = model.rules.contracts.expects[0].test.a.a
    assert literal.num == (157079632679, 50000000000, 314159265359, 100000000000)
    assert not judge_circuit(model).issues
    assert canonical.to_data(literal)["num"] == list(literal.num)
    with pytest.raises(ValueError):
        ExpectNode(num=(2, 1, 1, 1))
    with pytest.raises(ValueError):
        ExpectNode(num=(2, 2, 3, 1))


def test_partial_metadata_is_explicit_and_does_not_create_defaults():
    assert describe(protected_input).ports is None
    partial = describe(protected_input, partial=True)
    assert {p.name for p in partial.ports} == {"EXT", "INT", "GND"}
    assert partial.elaboration == {"reason": "required parameter abs_max"}
    params = {p["name"]: p for p in record_data(partial)["params"]}
    assert params["protection"]["type"] == "str" and params["protection"]["default"] is None
    with pytest.raises(DslError, match="protection.*expected str"):
        Design("invalid_id").use(protected_input, "dut", protection=12, clamp=volt(5), abs_max=volt(5))
    with pytest.raises(DslError, match="clamp.*unit is volt"):
        Design("invalid_voltage").use(protected_input, "dut", protection="x", clamp="5V", abs_max=volt(5))


def test_required_annotation_is_checked_before_function():
    calls = []

    @block
    def named(b, *, device_id: str = param()):
        calls.append(device_id)

    with pytest.raises(DslError, match="expected str"):
        Design("typed").use(named, "dut", device_id=1)
    assert not calls


def test_rating_containment_and_ordered_threshold_both_pass():
    import dataclasses

    from fenolite.blocks.tests._support import bench
    from fenolite.cli._contracts import classes_of, devices_of

    with bench("voltage_divider") as design:
        model = design.model
        contracts = model.rules.contracts
        base = contracts.expects[1]
        rating = base.test.a
        power = ExpectNode(lit=ValueRange("watt", Decimal10(1, -3), None, Decimal10(2, -3)))
        contained = dataclasses.replace(
            base,
            id="dut/expect#4",
            reason="power within rating range",
            test=ExpectNode("within", power, rating),
        )
        changed = dataclasses.replace(
            model,
            rules=dataclasses.replace(
                model.rules, contracts=dataclasses.replace(contracts, expects=(*contracts.expects, contained))
            ),
        )
        devices = devices_of(changed, design.path)
        result = judge_circuit(changed, devices=devices, classes=classes_of(changed, devices))
        assert not [i for i in result.issues if i.code.startswith("circuit.expect-")]
