# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Exact quantities (capability design-dsl, "Quantities in the DSL" and "Part values from quantities";
change c0073). The values are round numbers chosen for these tests."""

from __future__ import annotations

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
    amp,
    farad,
    henry,
    hertz,
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
    names = ("Quantity", "ohm", "farad", "henry", "volt", "amp", "hertz", "watt", "second")
    assert all(name in dsl.__all__ and hasattr(dsl, name) for name in names)
    assert list(UNITS) == ["ohm", "farad", "henry", "volt", "ampere", "hertz", "watt", "second"]


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
