# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Matching and ranking (change c0254, "Query value matching", "Query constraint matching", "Query
ranking")."""

from __future__ import annotations

from _picks import family, rows

from fenolite.dsl import capacitor, farad, ohm, pct, resistor, volt
from fenolite.pick.match import match, unknown_rows
from fenolite.pick.resolve import resolve


def test_a_range_value_admits_a_neighbouring_value() -> None:
    catalog = rows(family("Fenolite:R_0603_E96_1pct", low="9k", high="11k"), shipped=True)
    found = match(resistor(ohm("10k").pct(5), case="0603"), catalog)
    names = {row.device.rpartition("@")[2] for row in found.matches}
    assert {"9k76", "10k", "10k2"} <= names and not {"9k53", "10k5"} & names
    assert found.best is not None and found.best.device.endswith("@10k")


def test_an_unknown_rating_never_matches() -> None:
    catalog = rows(
        family("Test:C_0603", kind="capacitor", series="E6", low="100n", high="100n", tolerance="10%")
    )
    query = capacitor(farad("100n"), rating=volt(16))
    result = match(query, catalog)
    assert result.matches == () and [(e.row.row, e.key) for e in unknown_rows(result)] == [
        ("Test:C_0603", "rating")
    ]
    resolved = resolve({"C": query}, {}, catalog)
    codes = [found.code for found in resolved.issues]
    assert codes == ["pick.no-match", "pick.attribute-unknown"] and "rating" in resolved.issues[1].message


def test_ties_are_broken_in_order() -> None:
    project = rows(family("Proj:R_0603_E96_1pct", low="10k", high="10k"))
    shipped = rows(family("Fenolite:R_0603_E96_1pct", low="10k", high="10k"), shipped=True)
    loose = rows(
        family("Fenolite:R_0603_E24_5pct", series="E24", low="10k", high="10k", tolerance="5%"), shipped=True
    )
    catalog = (*shipped, *loose, *project)
    best = match(resistor(ohm("10k").pct(5), case="0603"), catalog).best
    assert best is not None and best.device == "Fenolite:R_0603_E24_5pct@10k"
    best = match(resistor(ohm("10k"), case="0603", tolerance=pct(1)), catalog).best
    assert best is not None and best.device == "Proj:R_0603_E96_1pct@10k"


def test_smaller_case_ranks_first_and_ratings_compare() -> None:
    small = rows(
        family("Fenolite:R_0402", case="0402", low="1k", high="1k", extra='power = "0.0625W"\n'), shipped=True
    )
    big = rows(
        family("Fenolite:R_0805", case="0805", low="1k", high="1k", extra='power = "0.125W"\n'), shipped=True
    )
    best = match(resistor(ohm("1k")), (*big, *small)).best
    assert best is not None and best.device.startswith("Fenolite:R_0402")
    from fenolite.dsl import watt

    best = match(resistor(ohm("1k"), power=watt("100m")), (*big, *small)).best
    assert best is not None and best.device.startswith("Fenolite:R_0805")
