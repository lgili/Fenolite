# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Pickable rows: families and device rows (change c0254, "Family rows", "Discrete rows and row sources")."""

from __future__ import annotations

from fractions import Fraction
from pathlib import Path

import pytest
from _picks import family, rows

from fenolite.catalog.devices import parse_device
from fenolite.core.errors import FormatError
from fenolite.pick.rows import (
    CASE_ORDER,
    PROJECT,
    device_row,
    digest,
    family_text,
    folder_rows,
    parse_family,
    value_code,
)


def test_a_family_expands_to_its_series() -> None:
    found = rows(family("Fenolite:R_0603_E24_5pct", series="E24", low="10", high="100", tolerance="5%"))
    assert len(found) == 25
    assert (
        found[0].device == "Fenolite:R_0603_E24_5pct@10R"
        and found[-1].device == "Fenolite:R_0603_E24_5pct@100R"
    )
    assert [row.value for row in found] == sorted(row.value for row in found)
    first = found[0].record
    assert first.mpn == "" and first.symbol == "Fenolite:Resistor" and first.value == "10Ω"
    assert {pin.function: pin.pins for pin in first.pins} == {"P1": ("1",), "P2": ("2",)}


def test_value_codes() -> None:
    assert value_code("ohm", Fraction(61900)) == "61k9"
    assert value_code("ohm", Fraction(47, 10)) == "4R7"
    assert value_code("ohm", Fraction(10**6)) == "1M"
    assert value_code("farad", Fraction(1, 10**7)) == "100n"
    assert value_code("farad", Fraction(47, 10**7)) == "4u7"


@pytest.mark.parametrize(
    ("change", "key"),
    [
        (('min = "10"', 'min = "ten"'), "values.min"),
        (('kind = "resistor"', 'kind = "diode"'), "kind"),
        (('series = "E96"', 'series = "E7"'), "series"),
        (('case = "0603"', 'case = "1608M"'), "case"),
        (('tolerance = "1%"', 'tolerance = "one"'), "tolerance"),
    ],
)
def test_a_malformed_family(change: tuple[str, str], key: str) -> None:
    text = family("Test:R").replace(*change)
    with pytest.raises(FormatError) as caught:
        parse_family(text, file="devices/bad.toml")
    assert caught.value.file == "devices/bad.toml" and caught.value.locator == key


def test_shipped_family_needs_sources() -> None:
    with pytest.raises(FormatError, match="sources"):
        parse_family(family("Test:R_X").replace("Test:R_X", "Fenolite:R_X"), file="x.toml")
    text = family("Fenolite:R_X", extra='sources = { values = ["S-0942"] }\n')
    assert parse_family(text).sources == {"values": ("S-0942",)}


def test_canonical_text_ignores_formatting() -> None:
    text = family("Test:R")
    spaced = "# a comment\n" + text.replace(" = ", "   =   ")
    assert family_text(parse_family(text)) == family_text(parse_family(spaced))
    assert digest(family_text(parse_family(text))) == rows(text)[0].sha256


DEVICE = """schema = "fenolite.device.v0"
id = "Test:C_10u"
summary = "Test capacitor"
symbol = "Fenolite:Capacitor"
footprint = "Fenolite:Chip_0805"
value = "10uF"
kind = "capacitor"
case = "0805"
tolerance = "10%"
dielectric = "X7R"
evidence = "INFERRED"

[pins]
P1 = "1"
P2 = "2"

[ratings]
voltage = { max = "25V" }
"""


def test_a_device_with_kind_and_value_is_a_row(tmp_path: Path) -> None:
    device = parse_device(DEVICE, file="caps.toml")
    row = device_row(device, origin=PROJECT, catalog="project:devices/caps.toml")
    assert row is not None and row.value == Fraction(1, 100000) and row.attributes["rating"] == 25
    assert row.attributes["dielectric"] == "X7R" and row.attributes["case"] == "0805"
    folder = tmp_path / "devices"
    folder.mkdir()
    (folder / "caps.toml").write_text(DEVICE, encoding="utf-8")
    (folder / "fam.toml").write_text(family("Test:R", low="10", high="10.2"), encoding="utf-8")
    found = folder_rows(folder, "devices")
    assert [r.catalog for r in found] == [
        "project:devices/caps.toml",
        "project:devices/fam.toml",
        "project:devices/fam.toml",
    ]
    plain = parse_device(DEVICE.replace('kind = "capacitor"\n', ""))
    assert device_row(plain, origin=PROJECT, catalog="x") is None


def test_a_row_with_other_pins_is_refused() -> None:
    text = DEVICE.replace('P2 = "2"', 'P2 = "2"\nP3 = "3"')
    with pytest.raises(FormatError, match="Test:C_10u"):
        device_row(parse_device(text), origin=PROJECT, catalog="x", file="devices/caps.toml")


def test_case_order() -> None:
    assert CASE_ORDER.index("0402") < CASE_ORDER.index("0603") < CASE_ORDER.index("1206")
