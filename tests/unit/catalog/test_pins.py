# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Pin tables ``fenolite.pins.v0`` (change c0261, capability symbol-generation, "Pin table records" and
"Canonical pin table text")."""

from __future__ import annotations

import dataclasses
from decimal import Decimal
from pathlib import Path

import pytest

from fenolite.catalog.pins import PinsSchemaError, parse_pins, pins_text, read_pins
from fenolite.cli.errors import from_exception
from fenolite.core.errors import FormatError
from fenolite.model.library import PinTable

DATA = Path(__file__).resolve().parents[2] / "data" / "pins"
HEADER = """schema = "fenolite.pins.v0"
id = "Example:T1"
version = "1.0.0"
summary = "test table"
licence = "CC0-1.0"
evidence = "UNVERIFIED"
"""


def _walk(value: object) -> list[object]:
    if dataclasses.is_dataclass(value) and not isinstance(value, type):
        return [value, *(x for f in dataclasses.fields(value) for x in _walk(getattr(value, f.name)))]
    if isinstance(value, (tuple, list)):
        return [x for item in value for x in _walk(item)]  # pyright: ignore[reportUnknownVariableType]
    return [value]


def test_read_example_buck() -> None:
    table = read_pins(DATA / "example_buck.toml")
    assert isinstance(table, PinTable)
    assert (table.namespace, table.name, table.version) == ("Example", "EXB6202", "1.0.0")
    assert len(table.rows) == 6
    gnd = next(row for row in table.rows if row.name == "GND")
    assert gnd.stacked == ("7",) and gnd.group == "ground"
    assert [row.number for row in table.rows] == ["5", "2", "4", "3", "6", "1"]
    assert table.rows[-1].side == "right"
    assert table.variants[0].name == "EXB6202DR" and table.variants[0].value == "EXB6202DR"
    assert table.keywords == ("regulator", "buck")
    assert not any(isinstance(x, (float, Decimal)) for x in _walk(table))


def test_read_explicit_units_and_alternates() -> None:
    table = read_pins(DATA / "example_dual.toml")
    assert table.unit_names == ((1, "A"), (2, "B"))
    assert {row.unit for row in table.rows} == {0, 1, 2}
    y1 = next(row for row in table.rows if row.name == "Y1")
    assert [(a.name, a.etype, a.shape) for a in y1.alternates] == [
        ("PWM1", "output", "line"),
        ("CLK1", "output", "clock"),
    ]
    assert next(row for row in table.rows if row.name == "NC").hidden
    assert table.variants[0].fp_filters == ("SOIC*", "TSSOP*")


def _row(extra: str) -> str:
    return HEADER + '\n[[pin]]\nnumber = "1"\nname = "A"\ntype = "input"\n' + extra


@pytest.mark.parametrize(
    ("text", "locator"),
    [
        (_row('stacked = ["2"]\n[[pin]]\nnumber = "2"\nname = "B"\ntype = "input"\n'), "pin[1].number"),
        (_row('[[pin]]\nnumber = "2"\nname = "B"\ntype = "input"\nstacked = ["1"]\n'), "pin[1].stacked"),
        (HEADER + '[[pin]]\nnumber = "1"\nname = "A"\ntype = "power"\n', "pin[0].type"),
        (_row('unit = 1\n[[pin]]\nnumber = "2"\nname = "B"\ntype = "input"\n'), "pin[1].unit"),
        (_row('colour = "red"\n'), "pin[0].colour"),
        (HEADER + '[[pin]]\nnumber = "1"\ntype = "input"\n', "pin[0].name"),
        (HEADER + '[[pin]]\nnumber = 1\nname = "A"\ntype = "input"\n', "pin[0].number"),
        (_row("unit = 2\n"), "pin"),
        (_row("hidden = 1\n"), "pin[0].hidden"),
        (_row("unit = 1.5\n"), "pin[0].unit"),
        (HEADER, "pin"),
        (HEADER.replace('id = "Example:T1"', 'id = "T1"'), "id"),
        (HEADER.replace('version = "1.0.0"', 'version = "1.0"'), "version"),
        (HEADER.replace('evidence = "UNVERIFIED"', 'evidence = "PROBABLY"'), "evidence"),
        (HEADER + 'colour = "red"\n', "colour"),
        (_row("[symbol]\nsplit_above = 2\n"), "symbol.split_above"),
        (_row('[[variant]]\nname = "X"\ndatasheet = "http://x"\n'), "variant[0].datasheet"),
        (_row('[[variant]]\nname = "T1"\n'), "variant[0].name"),
    ],
)
def test_refused_rows(text: str, locator: str) -> None:
    with pytest.raises(FormatError) as caught:
        parse_pins(text, file="t.toml")
    assert caught.value.locator == locator
    assert caught.value.file == "t.toml"
    assert from_exception(caught.value, "t.toml").code == "FEN-3004"


def test_hidden_power_refused() -> None:
    with pytest.raises(FormatError) as caught:
        parse_pins(HEADER + '[[pin]]\nnumber = "1"\nname = "VCC"\ntype = "power_in"\nhidden = true\n')
    assert caught.value.locator == "pin[0].hidden"
    assert "hidden" in caught.value.message


def test_newer_schema_is_fen_3002() -> None:
    with pytest.raises(PinsSchemaError) as caught:
        parse_pins(HEADER.replace("pins.v0", "pins.v1"))
    assert from_exception(caught.value, "t").code == "FEN-3002"


def test_not_toml() -> None:
    with pytest.raises(FormatError):
        parse_pins("schema = ", file="bad.toml")


@pytest.mark.parametrize("path", sorted(DATA.glob("*.toml")), ids=lambda p: p.name)
def test_round_trip(path: Path) -> None:
    table = read_pins(path)
    text = pins_text(table)
    again = parse_pins(text)
    assert again == table
    assert pins_text(again) == text
    assert text.endswith("\n") and not text.endswith("\n\n") and "\r" not in text


def test_text_escapes_quotes_and_controls() -> None:
    table = parse_pins(_row(""))
    odd = dataclasses.replace(table, summary='a "quoted" \\ text, ünïcode')
    assert parse_pins(pins_text(odd)) == odd
