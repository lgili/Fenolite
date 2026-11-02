# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Authored custom sheet texts: exact closed representation and code-owned field boundaries (c0329)."""

from __future__ import annotations

import dataclasses
import tomllib
from decimal import localcontext

import _schema
import pytest

from fenolite.core.coords import Point, Size
from fenolite.core.errors import FormatError
from fenolite.lens.drawn import CLOSED_KEYS, read_drawn, write_drawn
from fenolite.model.canonical import to_data
from fenolite.model.drawn import (
    DrawnField,
    DrawnFont,
    DrawnSchematic,
    DrawnSheet,
    DrawnSheetProperty,
    DrawnSheetRef,
)


def reference(properties=()) -> DrawnSheetRef:
    return DrawnSheetRef("child", "child", "m", "Authored child", Point(1, 2), Size(3, 4), "2",
                         "child.kicad_sch", properties=properties)  # fmt: skip


def drawing(properties=()) -> DrawnSchematic:
    return DrawnSchematic(
        "root", (DrawnSheet("root", sheet_refs=(reference(properties),)), DrawnSheet("child"))
    )


def test_ordered_literal_text_and_exact_pose_round_trip() -> None:
    values = (
        DrawnSheetProperty('z = "quoted"', 'µV\n"author"\\text', Point(1, -2), 90_000_000,
                           "right bottom", True, DrawnFont(Size(250_001, 350_003), 0, False)),
        DrawnSheetProperty("a", "", Point(3, 4)),
    )  # fmt: skip
    value = drawing(values)
    with localcontext() as ctx:
        ctx.prec = 1
        text = write_drawn(value)
        assert read_drawn(text) == value
    assert write_drawn(read_drawn(text)) == text
    assert 'text = ""' in text
    assert tuple(tomllib.loads(text)["sheet"][0]["sheet_ref"][0]["properties"]) == tuple(
        p.name for p in values
    )
    assert to_data(reference(values))["properties"][0]["name"] == values[0].name
    assert hash(values[0]) == hash(dataclasses.replace(values[0]))
    assert _schema.validate(tomllib.loads(text), _schema.load("fenolite.drawn-schematic.v0.json")) == []


def test_absence_preserves_old_canonical_text() -> None:
    text = write_drawn(drawing())
    assert "properties" not in text
    assert "properties" not in to_data(reference())
    assert read_drawn(text) == drawing()


@pytest.mark.parametrize(
    "kwargs, error",
    [
        ({"name": ""}, ValueError),
        ({"name": "Sheetname"}, ValueError),
        ({"name": "Sheetfile"}, ValueError),
        ({"name": "line\nbreak"}, ValueError),
        ({"name": 2}, TypeError),
        ({"text": None}, TypeError),
        ({"at": Point(True, 1)}, TypeError),
        ({"at": Point(1, 0.5)}, TypeError),
        ({"rotation": 180_000_000}, ValueError),
        ({"rotation": 0.5}, TypeError),
        ({"hide": 1}, TypeError),
        ({"font": "invented"}, TypeError),
    ],
)
def test_invalid_property_values_refuse(kwargs, error) -> None:
    with pytest.raises(error):
        DrawnSheetProperty(**({"name": "Field2", "text": "authored", "at": Point(1, 2)} | kwargs))


def test_duplicate_properties_and_pose_only_values_refuse() -> None:
    prop = DrawnSheetProperty("Field2", "authored", Point(1, 2))
    with pytest.raises(ValueError, match="unique"):
        reference((prop, dataclasses.replace(prop, text="different")))
    with pytest.raises(TypeError, match="DrawnSheetProperty"):
        reference((DrawnField("Field2", Point(1, 2)),))
    with pytest.raises(TypeError):
        reference([prop])


@pytest.mark.parametrize(
    "replacement",
    [
        "properties.Field2 = { at = [0, 0] }",
        "properties.Field2 = { text = 1, at = [0, 0] }",
        'properties.Field2 = { text = "x", at = [0, 0], surprise = true }',
        'properties.Sheetname = { text = "override", at = [0, 0] }',
        'properties.Sheetfile = { text = "override", at = [0, 0] }',
        'properties.Field2 = { text = "x", at = [0, 0], hide = 1 }',
        "properties = []",
    ],
)
def test_closed_toml_refuses_malformed_or_reserved_records(replacement: str) -> None:
    text = write_drawn(drawing((DrawnSheetProperty("Field2", "x", Point(0, 0)),)))
    lines = [replacement if line.startswith("properties.") else line for line in text.splitlines()]
    with pytest.raises(FormatError):
        read_drawn("\n".join(lines))


def test_duplicate_toml_property_refuses() -> None:
    text = write_drawn(drawing((DrawnSheetProperty("Field2", "x", Point(0, 0)),)))
    row = next(line for line in text.splitlines() if line.startswith("properties."))
    with pytest.raises(FormatError):
        read_drawn(text.replace(row, row + "\n" + row))


def test_editor_schema_agrees_with_new_closed_records() -> None:
    schema = _schema.load("fenolite.drawn-schematic.v0.json")
    for kind in ("sheet_ref", "sheet_property"):
        assert tuple(schema["$defs"][kind]["properties"]) == CLOSED_KEYS[kind]
    assert _schema.validate({"text": 3, "at": [0, 0]}, schema["$defs"]["sheet_property"], schema)
