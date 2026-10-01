# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Library definitions (capability design-model, requirement "Library definitions")."""

from __future__ import annotations

import dataclasses
import random

import pytest

from fenolite.core.coords import Point, Size
from fenolite.core.ids import derived_id, new_id
from fenolite.model import Graphic, Pad
from fenolite.model.canonical import dumps, loads
from fenolite.model.library import FootprintDef, Library, PinAlternate, SymbolDef, SymbolPin, SymbolUnit


def _pad(number: str, rng: random.Random) -> Pad:
    return Pad(
        id=new_id("pad", rng),
        number=number,
        shape="rect",
        size=Size(1_000_000, 500_000),
        position=Point(0, 0),
    )


def test_minimal_construction() -> None:
    fp = FootprintDef(id=derived_id("fpd", "kicad", "X"), name="X")
    sym = SymbolDef(id=derived_id("sym", "kicad", "Y"), name="Y")
    assert fp.pads == () and fp.graphics == () and fp.properties == {} and fp.kind == "unspecified"
    assert sym.units == () and sym.pins == () and sym.properties == {} and sym.power == ""
    assert Library().footprints == () and Library().symbols == ()


def test_definitions_are_immutable() -> None:
    fp = FootprintDef(id=derived_id("fpd", "kicad", "X"), name="X")
    with pytest.raises(dataclasses.FrozenInstanceError):
        fp.name = "Y"  # type: ignore[misc]
    pin = SymbolPin("1", "A", "input", Point(0, 0))
    with pytest.raises(dataclasses.FrozenInstanceError):
        pin.name = "B"  # type: ignore[misc]


def test_lib_id_and_convenience_properties() -> None:
    fp = FootprintDef(
        id=derived_id("fpd", "kicad", "Mini:R"),
        name="R",
        library="Mini",
        properties={"Reference": "R**", "Value": "R"},
    )
    assert fp.lib_id == "Mini:R" and fp.reference == "R**" and fp.value == "R"
    assert FootprintDef(id=derived_id("fpd", "kicad", "R"), name="R").lib_id == "R"
    sym = SymbolDef(
        id=derived_id("sym", "kicad", "Mini:U"),
        name="U",
        library="Mini",
        properties={
            "Reference": "U",
            "Value": "U",
            "Footprint": "Mini:F",
            "Datasheet": "",
            "Description": "d",
            "ki_keywords": "a  b",
            "ki_fp_filters": "F_*",
        },
    )
    assert (sym.lib_id, sym.reference, sym.footprint, sym.description) == ("Mini:U", "U", "Mini:F", "d")
    assert sym.keywords == ("a", "b") and sym.footprint_filters == ("F_*",) and sym.datasheet == ""


def test_graphics_on() -> None:
    rng = random.Random(4)
    line = Graphic(id=new_id("gfx", rng), kind="line", layer="F.CrtYd", points=(Point(0, 0), Point(1, 0)))
    silk = Graphic(id=new_id("gfx", rng), kind="line", layer="F.SilkS", points=(Point(0, 0), Point(1, 0)))
    fp = FootprintDef(id=derived_id("fpd", "kicad", "X"), name="X", graphics=(line, silk))
    assert fp.graphics_on("F.CrtYd") == (line,) and fp.graphics_on("B.Cu") == ()


def test_units_body_styles_and_pins_of() -> None:
    def pin(number: str, unit: int, style: int) -> SymbolPin:
        return SymbolPin(number, "", "passive", Point(0, 0), unit=unit, body_style=style)

    pins = (pin("1", 1, 1), pin("2", 1, 2), pin("3", 2, 1), pin("4", 3, 0), pin("5", 0, 1))
    units = tuple(SymbolUnit(u, s) for u, s in ((1, 1), (1, 2), (2, 1), (2, 2), (3, 0)))
    sym = SymbolDef(id=derived_id("sym", "kicad", "G"), name="G", units=units, pins=pins)
    assert sym.unit_count == 3 and sym.body_style_count == 2
    assert [p.number for p in sym.pins_of(3, 2)] == ["4"]
    assert [p.number for p in sym.pins_of(1)] == ["1", "5"]
    assert [p.number for p in sym.pins_of(1, 2)] == ["2"]
    assert SymbolDef(id=derived_id("sym", "kicad", "E"), name="E").unit_count == 1


def test_pad_order_survives_the_canonical_form() -> None:
    rng = random.Random(5)
    fp = FootprintDef(
        id=derived_id("fpd", "kicad", "X"), name="X", pads=tuple(_pad(n, rng) for n in ("2", "1", "3"))
    )
    back = loads(dumps(fp), FootprintDef)
    assert [p.number for p in back.pads] == ["2", "1", "3"]
    assert back == fp


def test_ordered_fields_are_marked() -> None:
    def ordered(cls: type, name: str) -> bool:
        return bool({f.name: f for f in dataclasses.fields(cls)}[name].metadata.get("ordered"))

    for name in ("keywords", "flags", "pads", "graphics", "models"):
        assert ordered(FootprintDef, name), name
    for name in ("units", "pins"):
        assert ordered(SymbolDef, name), name
    assert ordered(SymbolPin, "alternates")


def test_library_round_trip_keeps_value_objects() -> None:
    pin = SymbolPin(
        "1",
        "IO",
        "bidirectional",
        Point(-2_540_000, 0),
        rotation=180_000_000,
        length=2_540_000,
        unit=1,
        body_style=1,
        alternates=(PinAlternate("SDA", "bidirectional", "line"),),
    )
    sym = SymbolDef(
        id=derived_id("sym", "kicad", "L:U"), name="U", library="L", pins=(pin,), pin_name_offset=0
    )
    lib = Library("L", symbols=(sym,))
    text = dumps(lib)
    assert dumps(loads(text, Library)) == text
    assert loads(text, Library).symbols[0].pins[0] == pin


def test_float_rejected_by_the_library_schema() -> None:
    import json

    import _schema

    rng = random.Random(6)
    lib = Library(
        "L",
        footprints=(FootprintDef(id=derived_id("fpd", "kicad", "L:X"), name="X", pads=(_pad("1", rng),)),),
    )
    data = json.loads(dumps(lib))
    schema = _schema.load("fenolite.model.v0/library.json")
    assert _schema.validate(data, schema) == []
    data["footprints"][0]["pads"][0]["size"]["w"] = 1.5
    errors = _schema.validate(data, schema)
    assert errors and all(e.startswith("/footprints/0/pads/0/size/w") for e in errors), errors
