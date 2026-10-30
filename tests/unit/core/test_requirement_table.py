# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The requirement table (change c0253; capability electrical-contracts, "Requirement table")."""

from __future__ import annotations

import json
from fractions import Fraction

import pytest

from fenolite.core.requirement_table import (
    Bound,
    Corner,
    RequirementRow,
    Side,
    amount_text,
    joined,
    table_json,
)
from fenolite.dsl import volt
from fenolite.dsl.convert import range_to_model
from fenolite.dsl.quantity import Range
from fenolite.model.canonical import to_data


@pytest.mark.parametrize(
    "value",
    [volt("12").pct(10), volt("3.3").pct(3), Range("ohm", Fraction(1, 3), Fraction(2, 3)),
     Range("volt", Fraction(-5, 7), Fraction(13, 1000)), Range("kelvin", Fraction(25315, 100), Fraction(34315, 100))],
)  # fmt: skip
def test_bound_encoding_is_the_models(value: Range) -> None:
    """``Bound`` re-states c0246's ``ValueRange`` encoding byte for byte, rounding outward included."""
    model = to_data(range_to_model(value))
    nominal = value.nominal_value
    bound = Bound(value.unit, value.low, value.high, nominal)
    assert json.dumps(bound.to_json()) == json.dumps(model)


def test_bound_text() -> None:
    assert Bound("volt", Fraction(108, 10), Fraction(132, 10)).text() == "10.8V..13.2V"
    assert Bound("watt", None, Fraction(176, 1000)).text() == "..176mW"
    assert Bound("kelvin", Fraction(25315, 100), Fraction(34315, 100)).text() == "-20°C..70°C"
    assert amount_text("volt", Fraction(10, 3), "up") == "~3.3334V"
    assert amount_text("volt", Fraction(10, 3), "down") == "~3.3333V"


def _row(row_id: str, status: str = "pass") -> RequirementRow:
    return RequirementRow(
        row_id,
        "circuit.rating-voltage",
        "C1",
        "voltage",
        "volt",
        Side(Bound("volt", Fraction(0), Fraction(132, 10)), "0V..13.2V", "user", "rig bench"),
        Side(Bound("volt", None, Fraction(16)), "..16V", "device", "Fenolite:C", "UNVERIFIED", "abs_max"),
        status,  # type: ignore[arg-type]
        entities=("b", "a", "a"),
        corners=(Corner("bench=max", "pass", "13.2V"),),
    )


def test_rows_in_canonical_order() -> None:
    table = table_json([_row("b"), _row("a"), _row("a", "fail")])
    assert [row["id"] for row in table] == ["a", "b"]
    assert table[0]["status"] == "pass" and table[0]["entities"] == ["a", "b"]
    assert table[0]["limit"]["kind"] == "abs_max"  # type: ignore[index]
    assert table[0]["value"]["range"] == {
        "unit": "volt",
        "low": {"m": 0, "e": 0},
        "high": {"m": 132, "e": -1},
    }  # type: ignore[index]
    assert "evidence" not in table[0]["value"]  # type: ignore[operator]
    assert table[0]["corners"] == [{"corner": "bench=max", "status": "pass", "text": "13.2V"}]
    assert "." not in json.dumps([row["value"] for row in table]).replace('"', "").split("text")[0]
    assert [row["id"] for row in joined(table, [{"id": "0"}, {"id": "a"}])] == ["0", "a", "b"]


@pytest.mark.parametrize(
    ("make", "match"),
    [(lambda: Bound("furlong", Fraction(1)), "unit"), (lambda: Bound("volt"), "low or a high"),
     (lambda: Side(None, "", "guess", ""), "source"), (lambda: _row("x", "maybe"), "status")],  # type: ignore[arg-type]
)  # fmt: skip
def test_refused(make: object, match: str) -> None:
    with pytest.raises(ValueError, match=match):
        make()  # type: ignore[operator]
