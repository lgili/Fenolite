# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Schematic sheets (capability design-model, "Schematic sheet definitions", "Identifiers of schematic
entities" and "Schematic sheet schema"; change c0060)."""

from __future__ import annotations

import dataclasses
import json
import random
from pathlib import Path

import _schema
import pytest

from fenolite.core.coords import Point, Size
from fenolite.core.ids import derived_id, new_id
from fenolite.model import canonical
from fenolite.model.design import Design
from fenolite.model.presentation import SheetFrameRef
from fenolite.model.schematic import (
    NetLabel,
    NoConnectFlag,
    SchematicSheet,
    SheetPage,
    SheetRef,
    SheetUse,
    SymbolInstance,
    SymbolUse,
)

MM = 1_000_000


def _id(prefix: str, key: str) -> str:
    return derived_id(prefix, "fenolite", f"t:{key}")


def _sheet() -> SchematicSheet:
    symbols = (
        SymbolInstance("Mini:Mini_R", Point(50 * MM, 40 * MM), id=_id("sci", "R2")),
        SymbolInstance("Mini:Mini_LED", Point(20 * MM, 40 * MM), id=_id("sci", "D1")),
    )
    labels = (
        NetLabel("local", "N1", Point(0, 0), id=_id("lbl", "z")),
        NetLabel("global", "VCC", Point(MM, 0), id=_id("lbl", "a")),
        NetLabel("hierarchical", "IN", Point(2 * MM, 0), id=_id("lbl", "m")),
    )
    flags = (NoConnectFlag(Point(3 * MM, MM), id=_id("ncf", "1")),)
    return SchematicSheet(
        id=derived_id("sch", "fenolite", "t"), name="t", symbols=symbols, labels=labels, no_connects=flags
    )


def test_canonical_round_trip_keeps_order() -> None:
    sheet = _sheet()
    text = canonical.dumps(sheet)
    loaded = canonical.loads(text, SchematicSheet)
    assert loaded == sheet
    assert [s.lib_ref for s in loaded.symbols] == ["Mini:Mini_R", "Mini:Mini_LED"]
    assert [label.name for label in loaded.labels] == ["N1", "VCC", "IN"]
    assert canonical.dumps(loaded) == text


def test_full_sheet_round_trips_and_validates() -> None:
    use = SymbolUse("t", "/aa", "U1", 2)
    symbol = SymbolInstance(
        "Mini:Mini_R",
        Point(MM, MM),
        rotation=90_000_000,
        mirror="x",
        unit=2,
        ref="U1",
        value="1k",
        properties={"Value": "1k", "Reference": "U1"},
        dnp=True,
        on_board=False,
        lib_name="Mini_R_1",
        uses=(use, SymbolUse("t", "/bb", "U2")),
        id=_id("sci", "U1"),
    )
    ref = SheetRef(
        "Child",
        "child.kicad_sch",
        Point(0, 0),
        Size(10 * MM, 5 * MM),
        (SheetUse("t", "/", "2"),),
        id=_id("shr", "c"),
    )
    sheet = dataclasses.replace(
        _sheet(),
        paper=SheetFrameRef("A3"),
        symbols=(symbol,),
        sheets=(ref,),
        pages=(SheetPage("/", "1"),),
    )
    text = canonical.dumps(sheet)
    assert canonical.loads(text, SchematicSheet) == sheet
    data = json.loads(text)
    assert list(data["symbols"][0]["properties"]) == ["Reference", "Value"]
    assert _schema.validate(data, _schema.load("fenolite.model.v0/schematic.json")) == []


def test_label_kind_is_always_written() -> None:
    text = canonical.dumps(NetLabel("local", "N1", Point(0, 0), id=_id("lbl", "x")))
    assert json.loads(text)["kind"] == "local"


def test_entities_are_immutable() -> None:
    sheet = _sheet()
    with pytest.raises(dataclasses.FrozenInstanceError):
        sheet.symbols[0].unit = 2  # type: ignore[misc]
    with pytest.raises(dataclasses.FrozenInstanceError):
        sheet.name = "x"  # type: ignore[misc]


@pytest.mark.parametrize("rotation", [45_000_000, 1, 360_000_000, -90_000_000])
def test_symbol_rotation_is_a_right_angle(rotation: int) -> None:
    with pytest.raises(ValueError, match="rotation"):
        SymbolInstance("L:S", Point(0, 0), rotation=rotation, id=_id("sci", "r"))


def test_symbol_mirror_is_closed() -> None:
    with pytest.raises(ValueError, match="mirror"):
        SymbolInstance("L:S", Point(0, 0), mirror="xy", id=_id("sci", "m"))  # type: ignore[arg-type]


def test_sheets_are_not_layer_content(tmp_path: Path) -> None:
    written = canonical.dump_dir(Design.new("blink", seed=3), tmp_path)
    assert sorted(p.name for p in written) == sorted(name for name, _, _ in canonical.LAYER_FILES)
    assert len(written) == 6
    for path in written:
        data = json.loads(path.read_text(encoding="utf-8"))
        assert "lib_symbols" not in data and "no_connects" not in data


@pytest.mark.parametrize("prefix", ["sch", "sci", "lbl", "ncf", "shr"])
def test_prefixes_accepted(prefix: str) -> None:
    assert new_id(prefix, random.Random(1)).startswith(prefix + "_")


def test_unknown_prefix_refused() -> None:
    with pytest.raises(ValueError):
        new_id("scx", random.Random(1))


def test_uses_and_pages_carry_no_ids() -> None:
    for cls in (SymbolUse, SheetUse, SheetPage):
        assert "id" not in {f.name for f in dataclasses.fields(cls)}


def test_float_rejected_in_a_sheet_document() -> None:
    data = json.loads(canonical.dumps(_sheet()))
    schema = _schema.load("fenolite.model.v0/schematic.json")
    assert _schema.validate(data, schema) == []
    data["symbols"][0]["position"]["x"] = 1.5
    problems = _schema.validate(data, schema)
    assert problems and all("/symbols/0/position/x" in p for p in problems)
