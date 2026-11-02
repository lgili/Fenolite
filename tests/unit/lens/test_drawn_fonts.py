# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Closed drawn font TOML and unchanged legacy text (c0326); original authored values only."""

from __future__ import annotations

import tomllib
from decimal import localcontext

import _schema
import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from fenolite.core.coords import Point, Size
from fenolite.core.errors import FormatError
from fenolite.lens.drawn import CLOSED_KEYS, read_drawn, write_drawn
from fenolite.model.drawn import (
    DrawnField,
    DrawnFont,
    DrawnLabel,
    DrawnPin,
    DrawnPower,
    DrawnSchematic,
    DrawnSheet,
    DrawnSheetRef,
    DrawnSymbol,
)

PREFIX = """schema = "fenolite.drawn-schematic.v0"
root = "root"
[[sheet]]
key = "root"
paper = "A4"
[[sheet.symbol]]
part = "R1"
at = [1, 2]
"""


def drawing(font: DrawnFont) -> DrawnSchematic:
    field = DrawnField("Value", Point(3, 4), 90_000_000, "right bottom", True, font)
    root = DrawnSheet(
        "root",
        symbols=(DrawnSymbol("R1", 1, Point(1, 2), fields=(field,)),),
        powers=(DrawnPower("Authored:Power", "GND", Point(5, 6), fields=(field,)),),
        labels=tuple(
            DrawnLabel(kind, "SIG", Point(7, 8), font=font, justify=justify)
            for kind, justify in (("local", None), ("global", ""), ("hierarchical", "left bottom"))
        ),
        sheet_refs=(
            DrawnSheetRef(
                "child",
                "child",
                "ch0",
                "Channel",
                Point(9, 10),
                Size(11, 12),
                "2",
                pins=tuple(
                    DrawnPin("SIG", "input", Point(13, 14), font=font, justify=justify)
                    for justify in (None, "", "right top")
                ),
                fields=(
                    DrawnField("Sheetname", Point(15, 16), font=font),
                    DrawnField("Sheetfile", Point(17, 18), hide=True, font=font),
                ),
            ),
        ),
    )
    return DrawnSchematic("root", (root, DrawnSheet("child")))


@pytest.mark.parametrize(
    "font",
    (
        DrawnFont(Size(250_001, 350_003), 0, False, True, 'Authored "Sans"'),
        DrawnFont(Size(1, 499)),
        DrawnFont(thickness=0),
        DrawnFont(bold=False),
        DrawnFont(italic=False),
        DrawnFont(face="Authored Ω"),
    ),
)
def test_every_typed_surface_keeps_exact_font_and_presence(font: DrawnFont) -> None:
    value = drawing(font)
    text = write_drawn(value)
    assert read_drawn(text) == value
    assert write_drawn(read_drawn(text)) == text
    if font.size == Size(250_001, 350_003):
        assert "font = { size = [0.250001, 0.350003], thickness = 0, bold = false, italic = true" in text
    schema = _schema.load("fenolite.drawn-schematic.v0.json")
    assert _schema.validate(tomllib.loads(text), schema) == []


@pytest.mark.parametrize(
    "font, locator",
    (
        ("{}", "font"),
        ("42", "font"),
        ('{ size = "small" }', "font.size"),
        ("{ size = [1] }", "font.size"),
        ("{ size = [1, 2, 3] }", "font.size"),
        ("{ size = [true, 1] }", "font.size"),
        ("{ size = [0, 1] }", "font.size"),
        ("{ size = [1, -1] }", "font.size"),
        ("{ size = [0.0000001, 1] }", "font.size"),
        ("{ size = [nan, 1] }", "font.size"),
        ("{ thickness = -0.000001 }", "font.thickness"),
        ("{ thickness = true }", "font.thickness"),
        ("{ thickness = 0.0000001 }", "font.thickness"),
        ("{ bold = 0 }", "font.bold"),
        ('{ italic = "false" }', "font.italic"),
        ("{ face = false }", "font.face"),
        ('{ face = "" }', "font.face"),
        ('{ face = "Authored\\nSans" }', "font.face"),
        ('{ face = "/fonts/authored.ttf" }', "font.face"),
        ("{ unknown = true }", "font.unknown"),
    ),
)
def test_invalid_font_has_exact_locator(font: str, locator: str) -> None:
    text = PREFIX + f"fields.Value = {{ at = [3, 4], font = {font} }}\n"
    with pytest.raises(FormatError) as caught:
        read_drawn(text, file="schematic.toml")
    assert caught.value.file == "schematic.toml"
    assert caught.value.locator == f"sheet[0].symbol[0].fields.Value.{locator}"


@pytest.mark.parametrize(
    "font, locator",
    (
        ("{ size = [1.0000000000000000000000000001, 1] }", "size"),
        ("{ thickness = 1.0000000000000000000000000001 }", "thickness"),
    ),
)
def test_long_fractional_nanometres_are_not_rounded_into_integers(font: str, locator: str) -> None:
    text = PREFIX + f"fields.Value = {{ at = [3, 4], font = {font} }}\n"
    with pytest.raises(FormatError) as caught:
        read_drawn(text)
    assert caught.value.locator == f"sheet[0].symbol[0].fields.Value.font.{locator}"


@pytest.mark.parametrize("precision", (1, 2, 6, 28))
def test_exact_lengths_ignore_ambient_decimal_precision(precision: int) -> None:
    text = PREFIX + (
        "fields.Value = { at = [12.345678, -98.765432], font = { "
        "size = [12.3456780000000000000000000000, 2.000001], thickness = 0.000123 } }\n"
    )
    with localcontext() as context:
        context.prec = precision
        value = read_drawn(text)
        field = value.sheets[0].symbols[0].fields[0]
        assert field.at == Point(12_345_678, -98_765_432)
        assert field.font == DrawnFont(Size(12_345_678, 2_000_001), thickness=123)
        assert read_drawn(write_drawn(value)) == value


def test_sheet_property_fields_cannot_hold_other_names_or_text() -> None:
    text = """schema = "fenolite.drawn-schematic.v0"
root = "root"
[[sheet]]
key = "root"
paper = "A4"
[[sheet.sheet_ref]]
key = "child"
sheet = "child"
module = "ch0"
name = "Channel"
at = [1, 2]
size = [3, 4]
page = "2"
fields.Value = { at = [1, 2] }
[[sheet]]
key = "child"
paper = "A4"
"""
    with pytest.raises(FormatError) as caught:
        read_drawn(text)
    assert caught.value.locator == "sheet[0].sheet_ref[0].fields.Value"
    with pytest.raises(FormatError) as caught:
        read_drawn(text.replace("fields.Value", "fields.Sheetname").replace("{ at =", '{ text = "x", at ='))
    assert caught.value.locator == "sheet[0].sheet_ref[0].fields.Sheetname.text"


def test_absent_and_empty_justification_are_distinct_in_file() -> None:
    value = drawing(DrawnFont(bold=False))
    decoded = read_drawn(write_drawn(value)).sheets[0]
    assert [label.justify for label in decoded.labels] == [None, "", "left bottom"]
    assert [pin.justify for pin in decoded.sheet_refs[0].pins] == [None, "", "right top"]
    text = write_drawn(value).replace('justify = "left bottom"', 'justify = " left"')
    with pytest.raises(FormatError) as caught:
        read_drawn(text)
    assert caught.value.locator == "sheet[0].label[2].justify"


def test_editor_schema_and_closed_codec_keys_agree() -> None:
    schema = _schema.load("fenolite.drawn-schematic.v0.json")
    definitions = schema["$defs"]
    for kind in ("font", "field", "label", "pin", "sheet_ref"):
        assert tuple(definitions[kind]["properties"]) == CLOSED_KEYS[kind]
    assert definitions["font"]["minProperties"] == 1
    assert definitions["font"]["properties"]["size"]["items"]["exclusiveMinimum"] == 0
    assert definitions["sheet_fields"]["additionalProperties"] is False
    assert set(definitions["sheet_fields"]["properties"]) == {"Sheetname", "Sheetfile"}
    assert _schema.validate({"size": [1, 2], "surprise": 1}, definitions["font"], schema)
    assert _schema.validate({"bold": 0}, definitions["font"], schema)


@settings(max_examples=40, deadline=None)
@given(
    width=st.integers(1, 10**9),
    height=st.integers(1, 10**9),
    thickness=st.one_of(st.none(), st.integers(0, 10**6)),
    bold=st.one_of(st.none(), st.booleans()),
    italic=st.one_of(st.none(), st.booleans()),
)
def test_exact_integer_fonts_roundtrip_property(
    width: int, height: int, thickness: int | None, bold: bool | None, italic: bool | None
) -> None:
    value = drawing(DrawnFont(Size(width, height), thickness, bold, italic))
    text = write_drawn(value)
    assert read_drawn(text) == value
    assert write_drawn(read_drawn(text)) == text
