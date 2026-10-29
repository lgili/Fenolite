# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Exact length ranges (change c0260, requirement "Exact length ranges")."""

from __future__ import annotations

import pytest

from fenolite.core.errors import FormatError
from fenolite.core.quantities import LengthRange, parse_length_range


def test_range_spellings() -> None:
    span = parse_length_range("4.80mm..5.00mm")
    assert (span.min, span.nom, span.max) == (4_800_000, None, 5_000_000)
    assert span.nominal == 4_900_000
    assert parse_length_range("1.75mm max") == LengthRange(None, None, 1_750_000)
    assert parse_length_range("0.10mm min") == LengthRange(100_000, None, None)
    assert parse_length_range("50mil") == LengthRange(1_270_000, 1_270_000, 1_270_000)
    assert parse_length_range("0.05in") == LengthRange.exact(1_270_000)
    assert parse_length_range("400um .. 1270um") == LengthRange(400_000, None, 1_270_000)
    table = parse_length_range({"min": "0.31mm", "nom": "0.4mm", "max": "0.51mm"})
    assert table == LengthRange(310_000, 400_000, 510_000) and table.nominal == 400_000


def test_nominal_floors_and_may_be_unknown() -> None:
    assert LengthRange(1, None, 2).nominal == 1
    assert LengthRange(None, None, 1_750_000).nominal is None
    assert LengthRange(100_000, None, None).nominal is None


@pytest.mark.parametrize("text", ["0.0000005mm", "1e-7mm"])
def test_sub_nanometre_value(text: str) -> None:
    with pytest.raises(FormatError) as raised:
        parse_length_range(text, file="p.toml", locator="lead.width")
    assert text in raised.value.message and raised.value.locator == "lead.width"


@pytest.mark.parametrize(
    "value",
    [
        "5mm..4mm",
        {"min": "2mm", "nom": "1mm"},
        {"nom": "3mm", "max": "2mm"},
        "1.2",
        "abc",
        "1mm..",
        {},
        {"low": "1mm"},
        {"min": 1},
        3,
    ],
)
def test_malformed_ranges(value: object) -> None:
    with pytest.raises(FormatError) as raised:
        parse_length_range(value, locator="body.length")
    assert raised.value.locator.startswith("body.length")


def test_constructor_checks() -> None:
    with pytest.raises(ValueError, match="at least one"):
        LengthRange(None, None, None)
    with pytest.raises(ValueError, match="order"):
        LengthRange(3, 2, None)
