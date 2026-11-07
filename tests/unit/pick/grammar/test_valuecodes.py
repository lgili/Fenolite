# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Value codes of grammar families (change c0263, "Value-code schemes", scenario "Codes round-trip")."""

from __future__ import annotations

from fractions import Fraction

import pytest

from fenolite.core.quantities import parse
from fenolite.pick.grammar.valuecodes import SCHEMES, WIDTHS, decode_value, encode_value
from fenolite.pick.series import SERIES, values

PF = Fraction(1, 10**12)
OHM = Fraction(1)


def test_named_examples() -> None:
    assert decode_value("eia3", "104", PF) == parse("farad", "100n")
    assert decode_value("rkm", "4K7", OHM) == parse("ohm", "4.7k")
    assert decode_value("eia3", "4R7", PF) == parse("farad", "4.7p")
    assert decode_value("eia4", "1002", OHM) == 10_000 and decode_value("eia4", "49R9", OHM) == Fraction(
        499, 10
    )
    assert decode_value("rkm", "100R", OHM) == 100 and decode_value("rkm", "R47", OHM) == Fraction(47, 100)
    # the two examples of the registered public sources
    assert decode_value("eia96", "88A", OHM) == 806 and decode_value("eia96", "07B", OHM) == 1150
    assert (
        encode_value("eia4", Fraction(1330), OHM) == "1331"
        and encode_value("eia3", Fraction(33), OHM) == "330"
    )


@pytest.mark.parametrize(
    ("scheme", "text"),
    [
        ("eia3", "010"),  # a leading zero
        ("eia3", "1R00"),  # too wide
        ("eia4", "100"),  # too narrow
        ("eia96", "97A"),  # no 97th E96 value
        ("eia96", "01R"),  # R is read two ways by public pages: not read
        ("rkm", "1K0"),  # a trailing zero is not the canonical spelling
        ("rkm", "0K47"),  # nor a leading zero
        ("rkm", "4.7K"),
    ],
)
def test_other_spellings_are_refused(scheme: str, text: str) -> None:
    assert decode_value(scheme, text, OHM) is None


def test_unspellable_values() -> None:
    assert encode_value("eia3", Fraction(123), OHM) is None  # three significant digits
    assert encode_value("eia96", Fraction(1000), OHM) == "01B"
    assert encode_value("eia96", Fraction(1001), OHM) is None
    assert encode_value("eia3", Fraction(0), OHM) is None
    with pytest.raises(ValueError, match="scheme"):
        encode_value("eia5", Fraction(1), OHM)


@pytest.mark.parametrize("scheme", SCHEMES)
def test_every_spellable_value_round_trips(scheme: str) -> None:
    """For every value of E192 over twelve decades each scheme can spell, decoding its encoding gives the
    value back, at the scheme's fixed width."""
    spelled = 0
    for value in values("E192", Fraction(1, 100), Fraction(10**10)):
        for series_value in {value, value / 10}:
            text = encode_value(scheme, series_value, OHM)
            if text is None:
                continue
            spelled += 1
            assert decode_value(scheme, text, OHM) == series_value, (scheme, series_value, text)
            if scheme in WIDTHS:
                assert len(text) == WIDTHS[scheme]
    assert spelled > 100


def test_eia96_indexes_the_series_table() -> None:
    table = SERIES["E96"]
    for index, mantissa in enumerate(table, start=1):
        assert encode_value("eia96", Fraction(mantissa), OHM) == f"{index:02d}A"
