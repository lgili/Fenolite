# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
from __future__ import annotations

from fractions import Fraction

import pytest
from hypothesis import given
from hypothesis import strategies as st

from fenolite.core.units import (
    format_angle,
    format_length,
    nm_to_u,
    parse_angle,
    parse_length,
    round_half_even_div,
    u_to_nm,
)


@pytest.mark.parametrize(
    ("text", "nm"),
    [("0.25mm", 250_000), ("0.25 mm", 250_000), ("10mil", 254_000), ("1in", 25_400_000), ("250um", 250_000),
     ("250µm", 250_000), ("-1.5mm", -1_500_000), ("1e-3m", 1_000_000), ("12nm", 12), ("0.1cm", 1_000_000)],
)  # fmt: skip
def test_parse_length(text: str, nm: int) -> None:
    assert parse_length(text) == nm


@pytest.mark.parametrize("text", ["0.0000001mm", "0.5nm", "1.23456789mil"])
def test_inexact_lengths_are_rejected(text: str) -> None:
    with pytest.raises(ValueError, match="not representable in nanometres"):
        parse_length(text)


@pytest.mark.parametrize("text", ["12", "12parsecs", "mm", "1.2.3mm", ""])
def test_malformed_lengths(text: str) -> None:
    with pytest.raises(ValueError):
        parse_length(text)


def test_default_unit() -> None:
    assert parse_length("2", default_unit="mm") == 2_000_000


def test_angles() -> None:
    assert parse_angle("90deg") == 90_000_000
    assert parse_angle("45.5deg") == 45_500_000
    assert format_angle(90_000_000) == "90deg"
    with pytest.raises(ValueError):
        parse_angle("0.0000001deg")


def test_format_round_trip() -> None:
    assert format_length(250_000, "mm") == "0.25mm"
    assert parse_length(format_length(250_000, "mm")) == 250_000
    assert format_length(254_000, "mil") == "10mil"
    assert format_length(-1_500_000) == "-1.5mm"
    assert format_length(0) == "0mm"


def test_inexact_format_needs_places() -> None:
    with pytest.raises(ValueError, match="places"):
        format_length(1, "mil")
    assert format_length(1, "mil", places=6) == "0.000039mil"


@given(st.integers(min_value=-(10**15), max_value=10**15))
def test_mm_round_trip_property(nm: int) -> None:
    assert parse_length(format_length(nm, "mm")) == nm


@pytest.mark.parametrize(
    ("n", "d", "q"), [(5, 2, 2), (7, 2, 4), (-5, 2, -2), (-7, 2, -4), (3175, 50, 64), (9525, 50, 190)]
)
def test_round_half_even(n: int, d: int, q: int) -> None:
    assert round_half_even_div(n, d) == q


def test_whole_multiples_are_exact() -> None:
    assert u_to_nm(50) == 127 and nm_to_u(127) == 50
    assert nm_to_u(254_000) == 100_000


def test_documented_ties() -> None:
    assert [u_to_nm(u) for u in (25, 75, 125, -25, -75)] == [64, 190, 318, -64, -190]


def test_no_floats_even_for_huge_values() -> None:
    u = 10**18
    assert u_to_nm(u) == u * 127 // 50


@given(st.integers(min_value=-(10**12), max_value=10**12))
def test_u_to_nm_is_symmetric_and_nearest(u: int) -> None:
    assert u_to_nm(-u) == -u_to_nm(u)
    assert abs(Fraction(u_to_nm(u)) - Fraction(u * 127, 50)) <= Fraction(1, 2)


@given(st.integers(min_value=-(10**12), max_value=10**12))
def test_nm_to_u_is_symmetric_and_nearest(nm: int) -> None:
    assert nm_to_u(-nm) == -nm_to_u(nm)
    assert abs(Fraction(nm_to_u(nm)) - Fraction(nm * 50, 127)) < Fraction(1, 2)
