# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Exact quantities (capability design-dsl, "Quantities in the DSL" and "Part values from quantities";
change c0073). The values are round numbers chosen for these tests."""

from __future__ import annotations

import json
from collections.abc import Callable
from fractions import Fraction

import pytest
from hypothesis import given
from hypothesis import strategies as st

import fenolite.dsl as dsl
from fenolite.dsl import (
    Design,
    DslError,
    Part,
    Quantity,
    Range,
    amp,
    between,
    celsius,
    farad,
    henry,
    hertz,
    kelvin,
    ohm,
    second,
    to_model,
    volt,
    watt,
)
from fenolite.dsl.quantity import UNITS


def test_equal_forms() -> None:
    forms = [ohm("4k7"), ohm("4.7k"), ohm("4.7 kΩ"), ohm(4700), ohm(Fraction(4700)), ohm("4700R")]
    assert len(set(forms)) == 1 and len({hash(f) for f in forms}) == 1
    assert {f.text() for f in forms} == {"4.7kΩ"}
    assert forms[0].value == Fraction(4700) and forms[0].unit == "ohm"


def test_canonical_texts() -> None:
    assert farad("0.1u").text() == "100nF"
    assert volt("3.30").text() == "3.3V"
    assert hertz(16_000_000).text() == "16MHz"
    assert ohm("2R2").text(code=True) == "2R2"
    assert farad("100n").text(code=True) == "100n" and henry("4u7").text(code=True) == "4u7"
    assert ohm("0").text() == "0Ω" and ohm(0).text(code=True) == "0R"
    assert volt("-12").text() == "-12V" and amp("-500m").text() == "-500mA"
    assert second("10µ").text() == "10us" and watt("0.25").text() == "250mW"
    assert farad(Fraction(1, 10**13)).text() == "0.1pF" and hertz("2.4G").text() == "2.4GHz"
    assert str(ohm("10 M")) == "10MΩ" and ohm("10m").text() == "10mΩ"
    assert ohm("1Ω") == ohm(1) and farad("1μF") == farad("1uF")


@pytest.mark.parametrize(
    "call",
    [
        lambda: ohm(4.7e3),  # type: ignore[arg-type]
        lambda: ohm(True),
        lambda: ohm(None),  # type: ignore[arg-type]
        lambda: farad("10V"),
        lambda: farad("2R2"),
        lambda: ohm("4k7Ω"),
        lambda: ohm("4,7k"),
        lambda: ohm(""),
        lambda: ohm("k"),
        lambda: ohm("1 k Ω"),
        lambda: ohm("-1"),
        lambda: farad(-1),
        lambda: volt("3V3"),
        lambda: Quantity("metre", Fraction(1)),
    ],
)
def test_refused_input(call: object) -> None:
    with pytest.raises(DslError):
        call()  # type: ignore[operator]


def test_errors_name_the_input() -> None:
    with pytest.raises(DslError, match="4700.0"):
        ohm(4.7e3)  # type: ignore[arg-type]
    with pytest.raises(DslError, match="10V"):
        farad("10V")


def test_ordering_and_arithmetic() -> None:
    assert ohm("1k") < ohm("4k7") <= ohm(4700) and ohm("1M") > ohm("1k") and ohm(1) >= ohm(1)
    assert ohm("1k") != farad("1k") and ohm(1) != 1
    assert ohm("1k") + ohm(500) == ohm("1k5") and volt(5) - volt("3.3") == volt("1.7")
    assert ohm("10k") / 4 == ohm("2k5") and 2 * ohm("1k") == ohm("2k") == ohm("1k") * Fraction(2)
    for bad in (
        lambda: ohm(1) < farad(1),
        lambda: ohm(1) < 2,
        lambda: ohm(1) + farad(1),
        lambda: ohm(1) + 1,
        lambda: ohm(1) * ohm(1),
        lambda: ohm(1) * 1.5,
        lambda: ohm(1) / True,
    ):
        with pytest.raises(TypeError):
            bad()
    with pytest.raises(DslError, match="negative"):
        ohm(1) - ohm(2)


def test_text_refusals() -> None:
    with pytest.raises(DslError, match="terminating"):
        (ohm(1) / 3).text()
    with pytest.raises(DslError, match="letter code"):
        volt("3.3").text(code=True)
    with pytest.raises(DslError, match="letter code"):
        farad(2).text(code=True)


def test_exports() -> None:
    names = (
        "Quantity",
        "ohm",
        "farad",
        "henry",
        "volt",
        "amp",
        "hertz",
        "watt",
        "second",
        "celsius",
        "kelvin",
    )
    assert all(name in dsl.__all__ and hasattr(dsl, name) for name in names)
    assert list(UNITS) == ["ohm", "farad", "henry", "volt", "ampere", "hertz", "watt", "second", "kelvin"]


def test_one_value_for_two_spellings() -> None:
    d = Design("t")
    d.add(Part("R1", "Mini:Mini_R", value=ohm("4k7")), Part("R2", "Mini:Mini_R", value=ohm("4700")))
    d.add(Part("R3", "Mini:Mini_R", value="4k7"))
    values = {c.ref: c.value for c in to_model(d).circuit.components}
    assert values == {"R1": "4.7kΩ", "R2": "4.7kΩ", "R3": "4k7"}
    with pytest.raises(DslError, match="value"):
        Part("R4", "Mini:Mini_R", value=4700)  # type: ignore[arg-type]


MAKERS = {"ohm": ohm, "farad": farad, "henry": henry, "volt": volt, "ampere": amp, "hertz": hertz}
DECIMALS = st.builds(
    lambda digits, shift: Fraction(digits, 10**3) * Fraction(10) ** shift,
    st.integers(min_value=1, max_value=999_999),
    st.integers(min_value=-9, max_value=6),
)


@given(st.sampled_from(sorted(MAKERS)), DECIMALS)
def test_text_parses_back(unit: str, value: Fraction) -> None:
    made = Quantity(unit, value)
    assert MAKERS[unit](made.text()) == made


@given(st.sampled_from(["ohm", "farad", "henry"]), DECIMALS)
def test_letter_code_parses_back(unit: str, value: Fraction) -> None:
    made = Quantity(unit, value)
    if unit != "ohm" and 1 <= value < 1000:
        with pytest.raises(DslError):
            made.text(code=True)
        return
    assert MAKERS[unit](made.text(code=True)) == made


# -- temperatures, products and one-sided ranges (change c0274, tasks 1.1 to 1.3)


def test_celsius_range() -> None:
    ambient = between(celsius(-20), celsius(70))
    assert ambient.unit == "kelvin"
    assert (ambient.low, ambient.high) == (Fraction("253.15"), Fraction("343.15"))
    assert ambient.temperature_text() == "-20°C..70°C"
    assert kelvin(15).text() == "15K" and celsius(-40).temperature_text() == "-40°C"
    assert celsius("-40") == celsius("-40degC") == kelvin("233.15") == kelvin("233.15K")
    assert celsius(25).text() == "298.15K"
    assert between(celsius(0), celsius(85), nominal=celsius(25)).temperature_text() == "25°C (0°C..85°C)"


@pytest.mark.parametrize(
    "call",
    [
        lambda: celsius(20.5),  # type: ignore[arg-type]
        lambda: celsius(True),
        lambda: kelvin(1.5),  # type: ignore[arg-type]
        lambda: celsius(-274),
        lambda: celsius("300K"),
        lambda: volt("1").temperature_text(),
        lambda: volt("1").pct(1).temperature_text(),
    ],
)
def test_celsius_and_kelvin_refusals(call: Callable[[], object]) -> None:
    with pytest.raises(DslError):
        call()


def test_kelvin_in_the_model() -> None:
    from fenolite.dsl.convert import range_to_model
    from fenolite.model import canonical

    stored = range_to_model(between(celsius(-20), celsius(70)))
    assert json.loads(canonical.dumps(stored)) == {
        "high": {"e": -2, "m": 34315},
        "low": {"e": -2, "m": 25315},
        "unit": "kelvin",
    }


def test_products_power_of_a_bleeder() -> None:
    v_squared = volt("13.2") * volt("13.2")
    assert v_squared.unit == "volt_squared" and v_squared.low == v_squared.high == Fraction("174.24")
    p = v_squared / ohm("1k").pct(1)
    assert p.unit == "watt" and p.high == Fraction("174.24") / 990 and p.low == Fraction("174.24") / 1010
    q = amp("0.5") * amp("0.5") * ohm("0.1")
    assert q.unit == "watt" and q.low == q.high == q.nominal_value == Fraction(1, 40)
    assert (watt("1").pct(0) / ohm("4")).unit == "ampere_squared"
    assert (volt("13.2") * volt("13.2") / ohm("990")).text() == "176mW (176mW..176mW)"
    with pytest.raises(TypeError):
        _ = volt("1") * ohm("1")  # pyright: ignore[reportOperatorIssue, reportCallIssue, reportArgumentType]
    with pytest.raises(TypeError):
        _ = volt("1") * amp("1")  # pyright: ignore[reportOperatorIssue, reportCallIssue, reportArgumentType]


def test_products_never_reach_the_model() -> None:
    from typing import get_args

    from fenolite.dsl.convert import range_to_model
    from fenolite.model.circuit import RangeUnit

    assert "kelvin" in get_args(RangeUnit)
    assert not {"volt_squared", "ampere_squared"} & set(get_args(RangeUnit))
    with pytest.raises(DslError, match="volt_squared"):
        range_to_model(volt("2").pct(1) * volt("2").pct(1))
    with pytest.raises(DslError):
        _ = (volt("2") * volt("2")).min


def test_one_sided_floor() -> None:
    assert volt("4.5").min() + volt("0.2") == Range("volt", Fraction("4.7"), None)
    assert amp("1").min() * ohm("2") == Range("volt", Fraction(2), None)
    with pytest.raises(DslError, match="subtraction"):
        _ = volt("4.5").min() - volt("1").min()
    assert volt("5") - amp("1").min() * ohm("1") == Range("volt", None, Fraction(4))
    assert volt("6").min() / ohm("2").pct(0) == Range("ampere", Fraction(3), None)
    assert volt("6") / ohm("2").min() == Range("ampere", Fraction(0), Fraction(3))


@pytest.mark.parametrize(
    "call",
    [
        lambda: volt("-1").min() * 2,  # signed one-sided product
        lambda: volt("1").min() * between(volt("-1"), volt("1")) / ohm("1"),
        lambda: volt("1").min() / between(ohm("0"), ohm("1")),  # divisor holds zero
        lambda: volt("1") / ohm("0").min(),
        lambda: volt("1").min() - volt("1").min(),  # unbounded on both sides
    ],
)
def test_one_sided_refusals(call: Callable[[], object]) -> None:
    with pytest.raises(DslError):
        call()


_POINT = st.fractions(min_value=0, max_value=1000, max_denominator=50)


@given(_POINT, _POINT, _POINT, _POINT, _POINT)
def test_one_sided_against_bounded_ranges(
    a0: Fraction, b0: Fraction, b_span: Fraction, x_up: Fraction, t: Fraction
) -> None:
    """A one-sided result agrees with the same operation on a bounded range that cuts the open side at any
    height: its kept bound is exact, and every sampled value lies in it."""
    one_sided = Range("ratio", a0, None)
    cut = Range("ratio", a0, a0 + x_up)
    b = Range("ratio", b0, b0 + b_span)
    y = b0 + b_span * (t / (1 + t))
    x = a0 + x_up
    ops: dict[str, Callable[[Range | Fraction, Range | Fraction], Range | Fraction]] = {
        "+": lambda p, q: p + q,  # pyright: ignore[reportOperatorIssue]
        "-": lambda p, q: p - q,  # pyright: ignore[reportOperatorIssue]
        "*": lambda p, q: p * q,  # pyright: ignore[reportOperatorIssue]
        "/": lambda p, q: p / q,  # pyright: ignore[reportOperatorIssue]
    }
    for name, op in ops.items():
        if name == "/" and b0 == 0:
            continue
        open_result, bounded = op(one_sided, b), op(cut, b)
        assert isinstance(open_result, Range) and isinstance(bounded, Range)
        point = op(x, y) if y or name != "/" else x
        assert isinstance(point, Fraction)
        assert open_result.low == bounded.low and open_result.high is None
        assert Range("ratio", point, point).within(open_result)
    below = Range("ratio", None, a0)
    assert (below + b).high == a0 + b.high and (below - b).high == a0 - b0 and (below + b).low is None
