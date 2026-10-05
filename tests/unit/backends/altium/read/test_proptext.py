# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Property text and lengths (capability altium-project-reader)."""

from __future__ import annotations

import pytest
from hypothesis import given
from hypothesis import strategies as st

from fenolite.backends.altium.read.proptext import PropRecord, parse_fields, parse_length


def test_fields_in_order_with_repeats() -> None:
    record = parse_fields("A=1|B=x=y|A=2|FLAG|C=")
    assert record.fields == (("A", "1"), ("B", "x=y"), ("A", "2"), ("FLAG", None), ("C", ""))
    assert record.get("A") == "1" and record.get("FLAG") is None and record.get("Z") is None
    assert record.keys() == ("A", "B", "A", "FLAG", "C")
    assert record.text == "A=1|B=x=y|A=2|FLAG|C="


def test_leading_and_trailing_separator() -> None:
    assert parse_fields("|STACKUPVERSION=1|X=2|").fields == (("STACKUPVERSION", "1"), ("X", "2"))
    assert parse_fields("").fields == ()
    assert parse_fields("|").fields == ()
    assert parse_fields("a||b").fields == (("a", None), ("", None), ("b", None))


def test_record_from_fields_alone() -> None:
    record = PropRecord((("K", "v"),))
    assert record.get("K") == "v" and record.text == ""


@pytest.mark.parametrize(
    ("text", "nm"),
    [
        ("6mil", 152_400),
        ("10mil", 254_000),
        ("0.035mm", 35_000),
        ("1.5mm", 1_500_000),
        ("1.4mil", 35_560),
        ("3.937mil", 100_000),  # 99 999.8 nm
        ("0.00001mil", 0),  # 0.254 nm
        ("0.00002mil", 1),  # 0.508 nm
        ("0.0001mil", 3),  # 2.54 nm
        ("-2mil", -50_800),
        (".5mm", 500_000),
        ("0.0000005mm", 0),  # 0.5 nm: half to even
        ("0.0000015mm", 2),  # 1.5 nm: half to even
    ],
)
def test_lengths(text: str, nm: int) -> None:
    value = parse_length(text)
    assert value == nm and type(value) is int


@pytest.mark.parametrize("text", ["6", "6 mil", "6MIL", "6in", "mil", "", "1e3mil", " 6mil", "6.0.0mm"])
def test_not_lengths(text: str) -> None:
    assert parse_length(text) is None


@given(st.integers(min_value=-(10**9), max_value=10**9))
def test_whole_nanometres_round_trip(nm: int) -> None:
    whole, rest = divmod(abs(nm), 1_000_000)
    text = f"{'-' if nm < 0 else ''}{whole}.{rest:06d}mm"
    assert parse_length(text) == nm
