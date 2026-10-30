# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The exact unit parser of ``fenolite.core.quantities`` (change c0248, task 1.1): the DSL and the device
records read units with it. The values are round numbers chosen for these tests."""

from __future__ import annotations

from fractions import Fraction

import pytest

from fenolite.core.quantities import MICRO_UNITS, QuantityError, micro_units, parse


def test_parse_matches_the_dsl_forms() -> None:
    assert parse("ohm", "4k7") == parse("ohm", "4.7 kΩ") == Fraction(4700)
    assert parse("volt", "2.7V") == Fraction(27, 10)
    assert parse("farad", "100n") == Fraction(1, 10**7)
    assert parse("celsius", "-40degC") == -40 and parse("celsius", "125°C") == 125


@pytest.mark.parametrize(
    ("unit", "text", "expected"),
    [
        ("volt", "6V", 6_000_000),
        ("volt", "2.7V", 2_700_000),
        ("volt", "-300mV", -300_000),
        ("ampere", "500mA", 500_000),
        ("ampere", "2A", 2_000_000),
        ("watt", "250mW", 250_000),
        ("celsius", "-40degC", -40_000),
        ("celsius", "125degC", 125_000),
        ("celsius", "0.5degC", 500),
    ],
)
def test_micro_units(unit: str, text: str, expected: int) -> None:
    value = micro_units(unit, text)
    assert value == expected and type(value) is int


@pytest.mark.parametrize(
    ("unit", "text"),
    [
        ("volt", "6.0000005V"),  # half a µV
        ("celsius", "0.0005degC"),  # half a m°C
        ("ampere", "6V"),  # wrong unit
        ("watt", "-1W"),  # power is not signed
        ("ohm", "1k"),  # no integer unit
    ],
)
def test_refused(unit: str, text: str) -> None:
    with pytest.raises(QuantityError):
        micro_units(unit, text)


def test_stored_units() -> None:
    assert {name for name, _ in MICRO_UNITS.values()} == {"uV", "uA", "uW", "mdegC"}
