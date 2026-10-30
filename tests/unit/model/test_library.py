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
from fenolite.model.library import (
    DeviceDef,
    DevicePin,
    DeviceProvenance,
    FootprintDef,
    Library,
    PinAlternate,
    Rating,
    SymbolDef,
    SymbolGraphic,
    SymbolPin,
    SymbolUnit,
)


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


def test_symbol_graphics_keep_order_in_canonical_library() -> None:
    graphics = (
        SymbolGraphic("rect", (Point(-1, -1), Point(1, 1)), 10),
        SymbolGraphic("line", (Point(-2, 0), Point(-1, 0)), 10),
    )
    symbol = SymbolDef(id=derived_id("sym", "kicad", "L:R"), name="R", graphics=graphics)
    text = dumps(Library("L", symbols=(symbol,)))
    loaded = loads(text, Library)
    assert loaded.symbols[0].graphics == graphics
    assert dumps(loaded) == text


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


# --- change c0261: graphics per unit and pin tables ------------------------------------------------

CATALOG_SYMBOLS_SHA256 = "f7d914d11baf2565822ceaf0b03c2934af579376010445c1a388440eb6bcb537"
"""The canonical JSON of the 49 catalog symbols before change c0261 added ``SymbolGraphic.unit``."""


def test_old_canonical_json_unchanged() -> None:
    import hashlib

    from fenolite.catalog import ENTRIES, get_symbol

    symbols = tuple(get_symbol(e.lib_id) for e in ENTRIES if e.kind == "symbol")
    text = dumps(Library(name="Fenolite", symbols=symbols))
    assert len(symbols) == 49
    assert hashlib.sha256(text.encode()).hexdigest() == CATALOG_SYMBOLS_SHA256
    assert all(g.unit == 0 and g.body_style == 0 for s in symbols for g in s.graphics)


def test_two_bodies_keep_their_units() -> None:
    bodies = tuple(SymbolGraphic("rect", (Point(-1, -1), Point(1, 1)), unit=u, body_style=1) for u in (1, 2))
    sym = SymbolDef(id=derived_id("sym", "dsl", "L:Two"), name="Two", library="L", graphics=bodies)
    back = loads(dumps(Library(symbols=(sym,))), Library)
    assert [(g.unit, g.body_style) for g in back.symbols[0].graphics] == [(1, 1), (2, 1)]
    common = SymbolGraphic("line", (Point(0, 0), Point(1, 0)))
    assert (common.unit, common.body_style) == (0, 0)
    assert "unit" not in dumps(common)


def test_pin_table_value_objects() -> None:
    from fenolite.model.library import PinRow, PinTable, PinVariant

    row = PinRow("2", "GND", "power_in", group="ground", stacked=("7",))
    table = PinTable("EXB6202", (row,), variants=(PinVariant("EXB6202DR", value="EXB6202DR"),))
    assert row.unit is None and row.shape == "line" and not row.hidden
    assert (table.reference, table.split_above, table.unit_pins, table.auto_bus) == ("U", 100, 48, True)
    assert table.rows[0].stacked == ("7",)
    with pytest.raises(dataclasses.FrozenInstanceError):
        row.name = "X"  # type: ignore[misc]


# -- devices (change c0248, capability design-model, "Device definitions in the library layer")


def _buck_device() -> DeviceDef:
    """The illustrative device of ``tests/data/devices/example_buck.toml``, built by hand (authored for
    Fenolite; not a real product)."""
    return DeviceDef(
        id="Example:BUCK_6V_2A",
        summary="6 V 2 A step-down regulator (illustrative)",
        symbol="Example:Buck_6pin",
        footprint="Fenolite:SOT23_6_TI_DBV0006A",
        manufacturer="Example Semi",
        mpn="EXB6202",
        datasheet="https://example.invalid/exb6202.pdf",
        ref_prefix="U",
        evidence="UNVERIFIED",
        ground="GND",
        pins=(
            DevicePin("BST", (("1", "1"),)),
            DevicePin("EN", (("4", "4"),), voltage=Rating("voltage", "uV", max=6_000_000), must_connect=True),
            DevicePin("FB", (("3", "3"),), voltage=Rating("voltage", "uV", max=6_000_000)),
            DevicePin("GND", (("2", "2"), ("2", "EP"))),
            DevicePin("SW", (("6", "6"),)),
            DevicePin("VIN", (("5", "5"),), voltage=Rating("voltage", "uV", 2_700_000, 6_000_000)),
        ),
        ratings=(
            Rating("current", "uA", max=2_000_000),
            Rating("temperature", "mdegC", -40_000, 125_000),
        ),
        provenance=DeviceProvenance(
            "fenolite catalog import", "Example:Buck_6pin Fenolite:X", "2026-10-29", "0" * 64
        ),
    )


def test_device_round_trip() -> None:
    device = _buck_device()
    text = dumps(device)
    loaded = loads(text, DeviceDef)
    assert loaded == device
    assert [pin.function for pin in loaded.pins] == ["BST", "EN", "FB", "GND", "SW", "VIN"]
    assert loaded.pad_map == (
        ("1", "1"), ("2", "2"), ("2", "EP"), ("3", "3"), ("4", "4"), ("5", "5"), ("6", "6"),
    )  # fmt: skip
    assert loaded.pin("GND").pads == ("2", "EP") and loaded.pin("GND").pins == ("2",)
    assert loaded.rating("temperature") == Rating("temperature", "mdegC", -40_000, 125_000)
    assert loaded.rating("power") is None


def test_device_library_round_trip() -> None:
    library = Library(name="devices", devices=(_buck_device(),))
    assert loads(dumps(library), Library) == library


def test_no_float_in_a_device() -> None:
    import re

    text = dumps(_buck_device())
    assert not re.search(r"\d[.eE]\d|\d[eE][+-]?\d", text.replace("example.invalid/exb6202.pdf", ""))
    with pytest.raises(TypeError):
        dumps(dataclasses.replace(_buck_device().ratings[0], max=2.5))  # type: ignore[arg-type]


def test_devices_stay_out_of_the_layer_files() -> None:
    import typing

    from fenolite.model import canonical

    def holds_device(tp: object, seen: set[object]) -> bool:
        if tp in seen:
            return False
        seen.add(tp)
        if tp in (DeviceDef, DevicePin, Rating, DeviceProvenance):
            return True
        if isinstance(tp, type) and dataclasses.is_dataclass(tp):
            hints = typing.get_type_hints(tp)
            return any(holds_device(hint, seen) for hint in hints.values())
        return any(holds_device(arg, seen) for arg in typing.get_args(tp))

    for _file, _key, cls in canonical.LAYER_FILES:
        assert not holds_device(cls, set()), cls
