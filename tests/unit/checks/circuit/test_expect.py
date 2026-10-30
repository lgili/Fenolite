# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Expectations judged by the stage (change c0253; capability electrical-contracts, "Expectation judgement"
and "Unresolved expectations")."""

from __future__ import annotations

import dataclasses
from fractions import Fraction
from typing import Any

from _contracts import row

from fenolite.checks.circuit import judge_circuit
from fenolite.checks.circuit.expect import PRODUCTS, QUOTIENTS, Interval, verdict
from fenolite.dsl import Design, Rail, at_least, block, connect, ohm, to_model, value_of, volt, within
from fenolite.dsl.quantity import RATIO, SQUARED, UNIT_PRODUCTS, UNIT_QUOTIENTS
from fenolite.model.circuit import Decimal10, ValueRange
from fenolite.model.design import Design as ModelDesign

VOUT = volt("3.3").pct(3)


@block
def _buck(b: Any, *, vref: Any = None, second: bool = False) -> None:
    out = b.port("VOUT", Rail, direction="out")
    fb, gnd = b.net("FB"), b.net("GND")
    top = b.part("R_top", device="Fenolite:R_0603", value=ohm("45k3").pct(1))
    bot = b.part("R_bot", device="Fenolite:R_0603", value=ohm("10k").pct(1))
    connect(out, top.P1)
    connect(fb, top.P2, bot.P1)
    connect(gnd, bot.P2)
    b.expect(within(vref * (1 + value_of(top) / value_of(bot)), VOUT), "VOUT set by the divider")
    if second:
        b.expect(at_least(value_of(bot), ohm("1k")), "the divider draws little")


def _model(percent: str, *, second: bool = False) -> ModelDesign:
    d = Design("t")
    d.use(_buck, "buck1", vref=volt("0.6").pct(percent), second=second)
    return to_model(d)


def _edited(model: ModelDesign, value: ValueRange | None, text: str) -> ModelDesign:
    components = tuple(
        dataclasses.replace(c, value_range=value, value=text)
        if c.properties.get("fenolite.path") == "buck1/R_top"
        else c
        for c in model.circuit.components
    )
    return dataclasses.replace(model, circuit=dataclasses.replace(model.circuit, components=components))


def test_divider_of_a_buck() -> None:
    """Scenario "The divider of a buck": unsure at vref ± 1 %, pass at ± 0.5 %."""
    result = judge_circuit(_model("1"))
    (found,) = [i for i in result.issues if i.code == "circuit.expect-unsure"]
    assert found.severity == "warning"
    assert all(
        t in found.message
        for t in ("buck1/expect#1", "VOUT set by the divider", "3.2315V", "3.201V", "3.399V")
    )
    expectation = row(result, "circuit.expect:buck1/expect#1")
    assert expectation.status == "unsure" and expectation.value.range.unit == "volt"
    low = Fraction(594, 1000) * (1 + Fraction(45300 * 99, 100) / Fraction(10000 * 101, 100))
    assert expectation.value.range.low == low
    assert row(judge_circuit(_model("0.5")), "circuit.expect:buck1/expect#1").status == "pass"


def test_judged_again_after_an_edit() -> None:
    """Scenario "Judged again after an edit": the model's value range is what is judged."""
    edited = ValueRange("ohm", Decimal10(49401, 0), Decimal10(499, 2), Decimal10(50399, 0))
    result = judge_circuit(_edited(_model("1"), edited, "49k9"))
    (found,) = [i for i in result.issues if i.code == "circuit.expect-failed"]
    assert found.severity == "error" and "buck1/expect#1" in found.message and "3.4993V" in found.message
    low = row(result, "circuit.expect:buck1/expect#1").value.range.low  # rounded outward in the text
    assert Fraction(34993, 10000) < low < Fraction(34994, 10000)


def test_value_without_a_range() -> None:
    """Scenario "A value without a range": one ``expect-unknown`` warning, and the other expectation is
    judged."""
    result = judge_circuit(_edited(_model("1", second=True), None, "45k3 trimmed"))
    (found,) = [i for i in result.issues if i.code == "circuit.expect-unknown"]
    assert found.severity == "warning" and "buck1/expect#1" in found.message and "value of" in found.message
    assert row(result, "circuit.expect:buck1/expect#2").status == "pass"


def test_verdicts() -> None:
    def span(low: int | None, high: int | None) -> Interval:
        return Interval(
            "volt", None if low is None else Fraction(low), None if high is None else Fraction(high)
        )

    assert verdict("within", span(2, 3), span(1, 4)) == "pass"
    assert verdict("within", span(0, 2), span(1, 4)) == "unsure"
    assert verdict("within", span(5, 6), span(1, 4)) == "fail"
    assert verdict("at_least", span(4, 5), span(1, 4)) == "pass"
    assert verdict("at_least", span(0, 1), span(2, 3)) == "fail"
    assert verdict("at_most", span(0, 1), span(1, None)) == "pass"
    assert verdict("at_most", span(5, None), span(1, 4)) == "fail"
    assert verdict("within", span(None, 3), span(1, 4)) == "unsure"


def test_unit_tables_equal_the_dsl() -> None:
    """The judge's product and quotient tables are those of the DSL (``checks`` does not import it)."""
    known = {*PRODUCTS.keys()} | {*QUOTIENTS.keys()}
    assert all(unit in (*SQUARED, RATIO) or unit for pair in known for unit in pair)
    assert dict(PRODUCTS) == dict(UNIT_PRODUCTS)
    assert dict(QUOTIENTS) == dict(UNIT_QUOTIENTS)
