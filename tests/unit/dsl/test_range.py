# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Exact value ranges (capability design-dsl, "Range values in the DSL" to "Range unit quotients" and
"Part values from quantities"; change c0246). The values are round numbers chosen for these tests."""

from __future__ import annotations

import subprocess
import sys
from fractions import Fraction

import pytest
from hypothesis import given
from hypothesis import strategies as st

import fenolite.dsl as dsl
from fenolite.dsl import (
    Design,
    DslError,
    Part,
    Range,
    Tolerance,
    amp,
    between,
    farad,
    henry,
    ohm,
    pct,
    second,
    to_model,
    volt,
)
from fenolite.dsl.quantity import UNIT_PRODUCTS, UNIT_QUOTIENTS, UNITS
from fenolite.model.circuit import Decimal10, ValueRange

F = Fraction


# ------------------------------------------------------------------------------------ values (1.1)


def test_ranges_compare_by_value() -> None:
    a = Range("volt", F(3), F(4))
    assert a == Range("volt", F(3), F(4)) and hash(a) == hash(Range("volt", F(3), F(4)))
    b = Range("volt", F(3), F(4), F("3.5"))
    assert a != b
    with pytest.raises(TypeError):
        _ = a < b  # pyright: ignore[reportOperatorIssue]
    with pytest.raises(TypeError):
        _ = a >= b  # pyright: ignore[reportOperatorIssue]


@pytest.mark.parametrize(
    "build",
    [
        lambda: Range("volt", None, None),
        lambda: Range("volt", F(2), F(1)),
        lambda: Range("volt", F(1), F(2), F(3)),
        lambda: Range("uohm", F(1), F(2)),
        lambda: Range("volt", 1.0, F(2)),  # pyright: ignore[reportArgumentType]
    ],
)
def test_inconsistent_range_refused(build: object) -> None:
    with pytest.raises(DslError):
        build()  # pyright: ignore[reportCallIssue]


def test_bounds_as_quantities_value() -> None:
    r = ohm("10k").pct(1)
    assert (r.min, r.max, r.nominal) == (ohm("9.9k"), ohm("10.1k"), ohm("10k"))
    assert r.low == F(9900) and r.high == F(10100) and r.nominal_value == F(10000)
    ratio = ohm("1k").pct(10) / ohm("1k")
    assert ratio.min == F("0.9") and ratio.nominal == F(1)
    assert volt("1").min().max is None and amp("1").max().nominal is None


def test_negative_bound_of_unsigned_unit_refused_on_read() -> None:
    r = ohm("1k") - ohm("2k").pct(10)
    assert r.low == F(-1200)
    with pytest.raises(DslError, match="negative"):
        _ = r.min


# ------------------------------------------------------------------------------ constructors (1.2)


def test_symmetric_pct() -> None:
    r = volt("3.3").pct(3)
    assert r == Range("volt", F("3.201"), F("3.399"), F("3.3"))
    assert r.text() == "3.3V (3.201V..3.399V)"


def test_asymmetric_pct_and_a_tolerance_value() -> None:
    expected = Range("farad", F(8, 10**6), F(18, 10**6), F(10, 10**6))
    assert farad("10u").pct(-20, 80) == expected == farad("10u").pct(pct(-20, 80))
    assert pct(5) == Tolerance(F(-5), F(5)) and pct(F(-1, 2), "1.5") == Tolerance(F(-1, 2), F(3, 2))


def test_pct_of_a_negative_value_uses_the_magnitude() -> None:
    assert volt("-5").pct(10) == Range("volt", F("-5.5"), F("-4.5"), F(-5))


def test_at_most_and_at_least() -> None:
    most = amp("1.5").max()
    assert most == Range("ampere", F(0), F("1.5")) and most.nominal is None
    least = volt("4.5").min()
    assert least.low == F("4.5") and least.high is None and least.text() == "4.5V.."


@pytest.mark.parametrize(
    "call",
    [
        lambda: volt("3.3").pct(-1),
        lambda: volt("3.3").pct(1.5),  # pyright: ignore[reportArgumentType]
        lambda: pct(True),
        lambda: pct("1,5"),
        lambda: pct(1, -1),
        lambda: volt("3.3").pct(pct(1), 2),
        lambda: between(volt("2"), volt("1")),
        lambda: between(volt("1"), amp("2")),
        lambda: between(volt("1"), volt("2"), nominal=volt("3")),
        lambda: between(volt("1"), 2),  # pyright: ignore[reportArgumentType]
        lambda: volt("-1").max(),
    ],
)
def test_refused_inputs_pct_between(call: object) -> None:
    with pytest.raises(DslError):
        call()  # pyright: ignore[reportCallIssue]


def test_decimal_text_pct() -> None:
    assert ohm("100").pct("0.5") == Range("ohm", F("99.5"), F("100.5"), F(100))


def test_between_with_nominal() -> None:
    assert between(volt("3"), volt("3.6"), nominal=volt("3.3")) == Range("volt", F(3), F("3.6"), F("3.3"))


# -------------------------------------------------------------------------------- arithmetic (1.3)


def test_arithmetic_divider_output_worst_case() -> None:
    vref, r_top, r_bot = volt("0.8").pct(1), ohm("100k").pct(1), ohm("31.6k").pct(1)
    vout = vref * (1 + r_top / r_bot)
    assert vout.unit == "volt"
    assert vout.low == F("0.792") * (1 + F(99000, 31916))
    assert vout.high == F("0.808") * (1 + F(101000, 31284))
    assert vout.nominal_value == F("0.8") * (1 + F(100000, 31600))
    loose = vref * (1 + r_top / between(ohm("31k"), ohm("32k")))
    assert loose.nominal is None


def test_arithmetic_ohms_law_through_the_unit_table() -> None:
    i = volt("12").pct(10) / ohm("1k").pct(5)
    assert i.unit == "ampere" and i.low == F("10.8") / 1050 and i.high == F("13.2") / 950


def test_arithmetic_power_from_voltage_and_current() -> None:
    p = volt("5").pct(10) * amp("1").max()
    assert p.unit == "watt" and p.low == 0 and p.high == F("5.5")


def test_arithmetic_units_outside_the_tables() -> None:
    with pytest.raises(TypeError, match="farad.*henry"):
        _ = farad("1u").pct(10) * henry("1u").pct(10)
    with pytest.raises(TypeError, match="ohm.*volt"):
        _ = ohm("1k").pct(1) / volt("1")
    with pytest.raises(TypeError, match="volt.*ohm"):
        _ = volt("1").pct(1) + ohm("1")


def test_arithmetic_divisor_holding_zero() -> None:
    with pytest.raises(DslError, match="0Ω..10Ω"):
        _ = volt("1") / between(ohm("0"), ohm("10"))


def test_arithmetic_unbounded_operand() -> None:
    # c0274 lets a one-sided range enter arithmetic when the result keeps a bound (test_quantity.py).
    assert volt("4.5").min() + volt("1") == Range("volt", F("5.5"), None)
    assert -volt("4.5").min() == Range("volt", None, F("-4.5"))
    with pytest.raises(DslError, match="unbounded on both sides"):
        _ = volt("4.5").min() + (-volt("1").min())


def test_arithmetic_quantity_with_a_range_gives_a_range() -> None:
    assert volt("1") + between(volt("0"), volt("1")) == Range("volt", F(1), F(2))
    assert volt("1") - between(volt("0"), volt("1")) == Range("volt", F(0), F(1))
    assert volt("2") / ohm("1k").pct(0) == Range("ampere", F(2, 1000), F(2, 1000), F(2, 1000))
    assert 2 * ohm("1k").pct(1) == ohm("1k").pct(1) * 2 == ohm("2k").pct(1)
    assert 1 - ohm("1k").pct(10) / ohm("1k") == Range("ratio", F(-1, 10), F(1, 10), F(0))
    assert F(1) / second("1m").pct(0) == Range("hertz", F(1000), F(1000), F(1000))
    assert -volt("1").pct(10) == volt("-1").pct(10)


def test_arithmetic_two_quantities_of_different_units_still_refused() -> None:
    with pytest.raises(TypeError):
        _ = volt("1") * amp("1")  # pyright: ignore[reportOperatorIssue, reportCallIssue, reportArgumentType]
    with pytest.raises(TypeError):
        _ = ohm("1k").pct(1) + "1"  # pyright: ignore[reportOperatorIssue]


def test_arithmetic_unit_tables() -> None:
    for unit in UNITS:
        assert UNIT_PRODUCTS[(unit, "ratio")] == UNIT_PRODUCTS[("ratio", unit)] == unit
        assert UNIT_QUOTIENTS[(unit, unit)] == "ratio" and UNIT_QUOTIENTS[(unit, "ratio")] == unit
    assert UNIT_PRODUCTS[("ampere", "volt")] == "watt" and UNIT_PRODUCTS[("farad", "ohm")] == "second"
    assert UNIT_PRODUCTS[("second", "hertz")] == "ratio" and ("volt", "ohm") not in UNIT_PRODUCTS
    assert UNIT_QUOTIENTS[("ratio", "hertz")] == "second" and ("ohm", "volt") not in UNIT_QUOTIENTS


_EXACT = st.fractions(min_value=-1000, max_value=1000, max_denominator=50)


@st.composite
def _range_and_point(draw: st.DrawFn) -> tuple[Range, Fraction]:
    a, b = sorted((draw(_EXACT), draw(_EXACT)))
    t = draw(st.fractions(min_value=0, max_value=1, max_denominator=20))
    return Range("ratio", a, b), a + (b - a) * t


@given(_range_and_point(), _range_and_point())
def test_arithmetic_every_sampled_result_is_contained(
    left: tuple[Range, Fraction], right: tuple[Range, Fraction]
) -> None:
    (a, x), (b, y) = left, right
    point = Range("ratio", x, x)
    assert Range("ratio", x + y, x + y).within(a + b)
    assert Range("ratio", x - y, x - y).within(a - b)
    assert Range("ratio", x * y, x * y).within(a * b)
    assert point.within(a)
    assert b.low is not None and b.high is not None
    if not b.low <= 0 <= b.high:
        assert Range("ratio", x / y, x / y).within(a / b)


# --------------------------------------------------------------------------------- within, text (1.4)


def test_within_containment() -> None:
    v33 = volt("3.3").pct(3)
    assert between(volt("3.25"), volt("3.35")).within(v33)
    assert not volt("3.4").within(v33)
    assert v33.within(volt("3").min())
    assert not volt("3").min().within(v33) and volt("5").within(volt("5"))
    assert amp("1").within(amp("2").max()) and not amp("1").min().within(amp("2").max())


def test_within_different_units() -> None:
    with pytest.raises(TypeError):
        volt("3.3").pct(3).within(amp("1").max())
    with pytest.raises(TypeError):
        volt("3.3").within(3)  # pyright: ignore[reportArgumentType]


def test_text_non_terminating() -> None:
    assert (between(ohm("1"), ohm("2")) / ohm("3")).text() == "~0.3333..~0.6667"


def test_text_forms() -> None:
    assert str(between(volt("3"), volt("3.6"))) == "3V..3.6V"
    assert (ohm("1k") - ohm("2k").pct(10)).text() == "-1kΩ (-1.2kΩ..-800Ω)"
    third = between(volt("-2"), volt("-1"), nominal=volt("-1.5")) / 3
    assert third.text() == "-500mV (~-666.7mV..~-333.3mV)"
    assert (ohm("1k").pct(1) / ohm(3)).text() == "~333.3 (330..~336.7)"


@given(st.fractions(min_value=F(1, 10**6), max_value=10**12, max_denominator=10**6))
def test_text_never_raises_and_rounds_outward(value: Fraction) -> None:
    r = Range("ohm", value, value * 2, value)
    assert r.text()
    low = r.text().split("(")[1].split("..")[0]
    assert ohm(low.lstrip("~")).value <= value


# --------------------------------------------------------------------------------- re-export (1.5)


def test_reexport() -> None:
    names = ("Range", "Tolerance", "between", "pct")
    for name in names:
        assert name in dsl.__all__ and hasattr(dsl, name)
    out = subprocess.run(
        [
            sys.executable,
            "-c",
            "from fenolite.dsl import Range, Tolerance, between, pct; print(Range.__module__)",
        ],
        capture_output=True,
        text=True,
        check=True,
    )
    assert out.stdout.strip() == "fenolite.dsl.quantity"


# ----------------------------------------------------------------------------------- part values (2.2)


def _model_component(value: object) -> tuple[str, ValueRange | None]:
    design = Design("ranges")
    design.add(Part("R1", "Mini:Mini_R", value=value))  # pyright: ignore[reportArgumentType]
    (component,) = to_model(design).circuit.components
    return component.value, component.value_range


def test_part_ranged_value_keeps_the_value_text() -> None:
    part = Part("R1", "Mini:Mini_R", value=ohm("10k").pct(1))
    assert part.value == "10kΩ" and part.value_range == ohm("10k").pct(1)
    assert Part("R2", "Mini:Mini_R", value=ohm("10k")).value_range is None
    assert _model_component(ohm("10k").pct(1)) == (
        "10kΩ",
        ValueRange("ohm", Decimal10(99, 2), Decimal10(1, 4), Decimal10(101, 2)),
    )
    assert _model_component(ohm("10k")) == ("10kΩ", None)


@pytest.mark.parametrize(
    ("value", "message"),
    [
        (between(ohm("9k"), ohm("11k")), "needs a nominal"),
        (ohm("10k").min(), "unbounded"),
        (ohm("1k") - ohm("1k").pct(200), "negative"),
        (ohm("1k").pct(1) / ohm("1k"), "ratio"),
        (ohm(10**40).pct(1), "exponent"),
        (ohm(F(1, 10**40)).pct(1), "exponent"),
    ],
)
def test_part_refused_ranges(value: Range, message: str) -> None:
    with pytest.raises(DslError, match=f"R1.*{message}"):
        Part("R1", "Mini:Mini_R", value=value)


def test_part_outward_rounding() -> None:
    value = between(ohm("1"), ohm("2"), nominal=ohm("1.5")) / 3
    assert _model_component(value)[1] == ValueRange(
        "ohm", Decimal10(333333333333333, -15), Decimal10(5, -1), Decimal10(666666666666667, -15)
    )


def test_part_extreme_realistic_values_are_exact() -> None:
    cases = [
        (ohm("0.1m").pct(1), Decimal10(1, -4)),
        (ohm("10000G").pct(10), Decimal10(1, 13)),
        (farad("0.1p").pct(10), Decimal10(1, -13)),
        (farad(3000).pct(-10, 20), Decimal10(3, 3)),
    ]
    for value, nominal in cases:
        stored = _model_component(value)[1]
        assert stored is not None and stored.nominal == nominal
        assert stored.low is not None and stored.high is not None
        assert (stored.low.fraction(), stored.high.fraction()) == (value.low, value.high)


def test_part_negative_volts_are_kept() -> None:
    stored = _model_component(volt("-5").pct(10))[1]
    assert stored == ValueRange("volt", Decimal10(-55, -1), Decimal10(-5, 0), Decimal10(-45, -1))
