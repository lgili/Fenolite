# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The E series agree with the rounding rule of their source (change c0254, "Series agree with their
rule")."""

from __future__ import annotations

from fractions import Fraction

import pytest

from fenolite.pick.series import EXCEPTIONS, SERIES, member, values


def rule(index: int, count: int) -> int:
    """``10 ** (index / count)`` to three significant digits, rounded half up, in exact integers: the
    integer ``m`` with ``(m - 1/2) <= 100 · 10 ** (index / count) < (m + 1/2)``."""
    target = 10 ** (index + 2 * count)  # (100 · 10 ** (i/n)) ** n
    m = 100
    while (2 * m + 1) ** count <= target * 2**count:
        m += 1
    return m


@pytest.mark.parametrize("name", ["E48", "E96", "E192"])
def test_series_follow_the_rule_but_the_listed_exceptions(name: str) -> None:
    table = SERIES[name]
    count = int(name[1:])
    assert len(table) == count
    exceptions = {index: (listed, ruled) for index, listed, ruled in EXCEPTIONS[name]}
    for index, value in enumerate(table):
        if index in exceptions:
            assert (value, rule(index, count)) == exceptions[index]
        else:
            assert value == rule(index, count), (name, index)


def test_e96_and_the_named_exception() -> None:
    e96 = SERIES["E96"]
    assert len(e96) == 96 and e96[0] == 100 and e96[-1] == 976
    assert all(a < b for a, b in zip(e96, e96[1:], strict=False)) and all(100 <= v <= 999 for v in e96)
    assert EXCEPTIONS["E192"] == ((185, 920, 919),) and SERIES["E192"][185] == 920
    assert SERIES["E48"] == SERIES["E96"][::2]


def test_coarse_series_nest() -> None:
    assert (
        len(SERIES["E24"]) == 24
        and SERIES["E12"] == SERIES["E24"][::2]
        and SERIES["E6"] == SERIES["E24"][::4]
    )


def test_values_span_decades() -> None:
    found = list(values("E24", Fraction(10), Fraction(100)))
    assert len(found) == 25 and found[0] == 10 and found[-1] == 100
    assert list(values("E6", Fraction(1, 1000), Fraction(5, 1000)))[-1] == Fraction(47, 10000)
    assert member("E96", Fraction(61900)) and not member("E24", Fraction(61900))
