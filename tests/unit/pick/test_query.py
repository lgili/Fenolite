# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Canonical query texts read back on the pick side (change c0254, "Canonical query text")."""

from __future__ import annotations

from fractions import Fraction

import pytest

from fenolite.core.errors import FormatError
from fenolite.core.partquery import KEYS, KINDS, Percent
from fenolite.dsl import capacitor, farad, ohm, pct, resistor, volt
from fenolite.pick.query import parse_query


def test_keys_are_closed_and_ordered() -> None:
    assert KINDS == ("resistor", "capacitor", "inductor")
    assert [key.name for key in KEYS["capacitor"]] == [
        "tolerance",
        "rating",
        "case",
        "dielectric",
        "series",
        "row",
    ]


@pytest.mark.parametrize(
    "made",
    [
        capacitor(farad("10u"), rating=volt(25), case="0805", dielectric="X7R"),
        resistor(ohm("10k"), tolerance=pct(1), case="0603", series="E96"),
        resistor(ohm("10k").pct(5), case="0603"),
    ],
)
def test_dsl_texts_read_back(made: object) -> None:
    from fenolite.core.partquery import PartQuery

    assert isinstance(made, PartQuery)
    found = parse_query(made.text())
    assert (found.kind, found.value, found.exact, found.constraints) == (
        made.kind,
        made.value,
        made.exact,
        made.constraints,
    )


def test_parse_values() -> None:
    found = parse_query("capacitor(10uF, rating>=25V)")
    assert found.value is not None and found.value.low == Fraction(1, 100000) and found.get("rating") == 25
    assert parse_query("resistor(1kΩ, tolerance<=-1%..+2%)").get("tolerance") == Percent(
        Fraction(-1), Fraction(2)
    )


@pytest.mark.parametrize(
    "text", ["diode(1k)", "resistor()", "resistor(1kΩ, colour=red)", "capacitor(1uF, rating<=5V)"]
)
def test_refused_texts(text: str) -> None:
    with pytest.raises(FormatError):
        parse_query(text)
