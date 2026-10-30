# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The ``fenolite.family.v1`` reader (change c0263, "Grammar family records", scenario "An unknown key")."""

from __future__ import annotations

from fractions import Fraction

import pytest
from _grammars import MLCC, edited, mlcc

from fenolite.catalog.devices import DeviceFormatError, DeviceFormatTooNewError, is_family
from fenolite.catalog.records import record_uid
from fenolite.core.partquery import Percent
from fenolite.pick.grammar.schema import attribute_names, parse_family
from fenolite.pick.rows import is_grammar


def test_the_example_reads() -> None:
    family = mlcc()
    assert (
        family.id == "Example:EX_MLCC"
        and family.kind == "capacitor"
        and family.manufacturer == "Example Passive"
    )
    assert family.placeholders == ("size", "dielectric", "value", "tolerance", "voltage", "packing")
    assert family.literal_prefix == "EX" and family.tail == "none"
    value = family.value_field
    assert value is not None and value.scheme == "eia3" and value.scale == Fraction(1, 10**12)
    size = family.fields["size"]
    assert [code.code for code in size.codes] == ["03", "05"]
    k = family.fields["tolerance"].code("K")
    assert k is not None and k.attributes["tolerance"] == Percent(Fraction(-10), Fraction(10))
    assert family.fields["voltage"].code("A").attributes["rating"] == 25  # type: ignore[union-attr]
    assert family.fields["packing"].role == "ordering" and family.fields["packing"].prefer == "T"
    assert len(family.valid) == 2 and len(family.exclude) == 1
    assert family.valid[0].codes["voltage"] == ("A", "B")
    assert family.uid == record_uid("family", "Example:EX_MLCC")
    assert family.pins == (("1", "1"), ("2", "2"))


def test_unknown_key() -> None:
    """Scenario "An unknown key"."""
    with pytest.raises(DeviceFormatError) as error:
        edited(MLCC, 'licence = "CC0-1.0"', 'licence = "CC0-1.0"\nprice = "0.01"')
    assert error.value.cli_code == "FEN-3004"
    assert error.value.file == "example_mlcc.toml" and error.value.locator == "price"


@pytest.mark.parametrize(
    ("old", "new", "key"),
    [
        (
            'codes.K = { tolerance = "10%" }',
            "codes.K = { tolerance = 0.1 }",
            "fields.tolerance.codes.K.tolerance",
        ),
        (
            'codes.A = { rating = "25V" }',
            'codes.A = { rating = "25V", price = "1" }',
            "fields.voltage.codes.A.price",
        ),
        (
            'codes.A = { rating = "25V" }',
            'codes.A = { rating = "25 parsecs" }',
            "fields.voltage.codes.A.rating",
        ),
        ('codes."03" = {', 'codes."0x" = {', "fields.size.codes.0x"),
        ('scheme = "eia3"', 'scheme = "eia5"', "fields.value.scheme"),
        ('unit = "pF"\n', "", "fields.value.unit"),
        ('series = "E12"', 'series = "E13"', "fields.value.series"),
        ('role = "ordering"', 'role = "cosmetic"', "fields.packing.role"),
        ('size = "05"', 'grade = "05"', "valid[1].grade"),
        ('value = { min = "10pF", max = "1nF" }', 'value = { min = "1nF", max = "10pF" }', "valid[1].value"),
        ('value = { min = "10pF", max = "1nF" }', "", "valid[1].value"),
        ('tail = "none"', 'tail = "some"', "tail"),
        ('version = "1.0.0"', 'version = "1.0"', "version"),
        ('evidence = "INFERRED"', 'evidence = "PROBABLY"', "evidence"),
        ('pattern = "EX{size}', 'pattern = "ex{size}', "pattern"),
        ('datasheet = "https://example.invalid/ex-mlcc.pdf"', 'datasheet = "ex-mlcc.pdf"', "datasheet"),
        ('kind = "capacitor"', 'kind = "diode"', "kind"),
    ],
)
def test_a_malformed_family(old: str, new: str, key: str) -> None:
    with pytest.raises(DeviceFormatError) as error:
        edited(MLCC, old, new)
    assert error.value.locator == key, str(error.value)


def test_a_float_is_refused() -> None:
    with pytest.raises(DeviceFormatError, match="float"):
        edited(MLCC, 'codes."05" = { case = "0805"', 'codes."05" = { case = 805.0')


def test_attributes_are_closed_per_kind() -> None:
    assert attribute_names("capacitor") == (
        "tolerance", "rating", "case", "dielectric", "series", "footprint", "symbol", "packing"
    )  # fmt: skip
    with pytest.raises(DeviceFormatError, match="not an attribute of a capacitor"):
        edited(MLCC, 'codes.A = { rating = "25V" }', 'codes.A = { power = "1W" }')


def test_schema_versions() -> None:
    with pytest.raises(DeviceFormatTooNewError) as error:
        edited(MLCC, 'schema = "fenolite.family.v1"', 'schema = "fenolite.family.v2"')
    assert error.value.cli_code == "FEN-3002"
    with pytest.raises(DeviceFormatError, match="must be 'fenolite.family.v1'"):
        edited(MLCC, 'schema = "fenolite.family.v1"', 'schema = "fenolite.family.v0"')


def test_schema_dispatch() -> None:
    text = MLCC.read_text(encoding="utf-8")
    assert is_grammar(text) and is_family(text)
    assert not is_grammar(text.replace("family.v1", "family.v0")) and is_family(
        text.replace("family.v1", "family.v0")
    )


def test_sources_by_attribute() -> None:
    family = edited(MLCC, 'sources = ["EX series datasheet rev A, ordering code table (illustrative)"]',
                    'sources = { value = ["rev A"], tolerance = ["rev A"] }')  # fmt: skip
    assert family.sources == () and family.sources_by["value"] == ("rev A",)
    with pytest.raises(DeviceFormatError) as error:
        parse_family(MLCC.read_text(encoding="utf-8").replace('sources = ["EX', 'sources = { price = ["EX', 1)
                     .replace('(illustrative)"]', '(illustrative)"] }', 1), file="x.toml")  # fmt: skip
    assert error.value.locator == "sources.price"
