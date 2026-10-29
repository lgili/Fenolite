# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The exact unit parser of ``fenolite.core.quantities`` (change c0248, task 1.1): the DSL and the device
records read units with it. The values are round numbers chosen for these tests."""

from __future__ import annotations

from fractions import Fraction

import pytest

from fenolite.core.quantities import MICRO_UNITS, QuantityError, celsius_text, micro_units, parse


def test_parse_matches_the_dsl_forms() -> None:
    assert parse("ohm", "4k7") == parse("ohm", "4.7 kΩ") == Fraction(4700)
    assert parse("volt", "2.7V") == Fraction(27, 10)
    assert parse("farad", "100n") == Fraction(1, 10**7)
    assert parse("kelvin", "-40degC") == Fraction("233.15") and parse("kelvin", "125°C") == Fraction("398.15")
    assert parse("kelvin", "233.15K") == parse("kelvin", "-40degC") and parse("kelvin", "15mK") == Fraction(
        3, 200
    )


@pytest.mark.parametrize(
    ("unit", "text", "expected"),
    [
        ("volt", "6V", 6_000_000),
        ("volt", "2.7V", 2_700_000),
        ("volt", "-300mV", -300_000),
        ("ampere", "500mA", 500_000),
        ("ampere", "2A", 2_000_000),
        ("watt", "250mW", 250_000),
        ("kelvin", "-40degC", 233_150),
        ("kelvin", "125degC", 398_150),
        ("kelvin", "0.5degC", 273_650),
        ("kelvin", "233.15K", 233_150),
    ],
)
def test_micro_units(unit: str, text: str, expected: int) -> None:
    value = micro_units(unit, text)
    assert value == expected and type(value) is int


@pytest.mark.parametrize(
    ("unit", "text"),
    [
        ("volt", "6.0000005V"),  # half a µV
        ("kelvin", "0.0005degC"),  # half a mK
        ("kelvin", "-40.0001degC"),  # a tenth of a mK
        ("kelvin", "-274degC"),  # below absolute zero
        ("kelvin", "-1K"),  # an absolute temperature is not signed
        ("kelvin", "1mdegC"),  # no prefix on a Celsius text
        ("ampere", "6V"),  # wrong unit
        ("watt", "-1W"),  # power is not signed
        ("ohm", "1k"),  # no integer unit
    ],
)
def test_refused(unit: str, text: str) -> None:
    with pytest.raises(QuantityError):
        micro_units(unit, text)


def test_stored_units() -> None:
    assert {name for name, _ in MICRO_UNITS.values()} == {"uV", "uA", "uW", "mK"}


def test_celsius_text() -> None:
    assert celsius_text(Fraction("233.15")) == "-40°C" and celsius_text(Fraction("300")) == "26.85°C"
    assert celsius_text(Fraction("398.15"), "degC") == "125degC"
