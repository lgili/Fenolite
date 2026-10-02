# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Library symbols from KiCad symbols (capability altium-schematic-writer, "Library symbols from KiCad
symbols"; change c0034; ``docs/formats/altium/schematic-library.md``, "Mapping from a KiCad symbol")."""

from __future__ import annotations

import dataclasses

import pytest
from _altium import MIL, dual_symbol, symbol_pin

from fenolite.backends.altium.altsym import (
    EDGE_CODES,
    ELECTRICAL,
    AltiumRect,
    from_symbol_def,
    overbar,
)
from fenolite.core.coords import Point
from fenolite.core.errors import Issue
from fenolite.core.ids import derived_id
from fenolite.model.library import PinAlternate, SymbolDef, SymbolPin, SymbolUnit


def symbol(*pins: SymbolPin, **more: object) -> SymbolDef:
    fields: dict[str, object] = {
        "id": derived_id("sym", "kicad", "Demo:X"),
        "name": "X",
        "library": "Demo",
        "pins": pins,
        **more,
    }
    return SymbolDef(**fields)  # type: ignore[arg-type]


def test_resistor_turned_upright() -> None:
    upright = symbol(
        symbol_pin("1", 0, 150, 270, 1, "passive", length=50 * MIL),
        symbol_pin("2", 0, -150, 90, 1, "passive", length=50 * MIL),
        properties={"Reference": "R", "Value": "10k"},
    )
    mapped = from_symbol_def(upright, lib_ref="R", footprint=None)
    one, two = mapped.pins
    assert (one.designator, one.direction, one.x, one.y, one.length) == ("1", 1, 0, 100, 50)
    assert (two.designator, two.direction, two.x, two.y) == ("2", 3, 0, -100)
    assert one.hot_end == (0, 150) and two.hot_end == (0, -150)
    assert mapped.rectangles == (AltiumRect(1, -100, -100, 100, 100),)
    assert (mapped.prefix, mapped.comment, mapped.parts) == ("R", "10k", 1)


def test_dual_unit_with_common_power_pins() -> None:
    issues: list[Issue] = []
    mapped = from_symbol_def(dual_symbol(), lib_ref="DUAL", footprint=("Demo", "SO8"), issues=issues)
    assert mapped.parts == 2
    power = [p for p in mapped.pins if p.designator in ("4", "8")]
    assert [p.part for p in power] == [0, 0] and {p.electrical for p in power} == {7}
    assert [p.designator for p in mapped.pins] == ["4", "8", "1", "2", "3", "5", "6", "7"]
    for part in (1, 2):
        rect = mapped.rectangle(part)
        for pin in (p for p in mapped.pins if p.part in (0, part)):
            assert rect.x0 <= pin.x <= rect.x1 and rect.y0 <= pin.y <= rect.y1
    assert mapped.rectangle(1) == AltiumRect(1, -200, -200, 200, 200)
    assert [p.designator for p in mapped.pins_of(1)] == ["4", "8", "1", "2", "3"]
    assert [p.designator for p in mapped.pins_of(2)] == ["5", "6", "7"]
    assert [i.code for i in issues] == ["altium.symbol-simplified"]
    assert mapped.footprint == ("Demo", "SO8")


def test_off_grid_pin_refused() -> None:
    off = symbol_pin("7", 0, 0, 0, 1)
    off = dataclasses.replace(off, position=Point(1_270_000 + 1_000, 0))
    with pytest.raises(ValueError, match="Demo:X pin 7"):
        from_symbol_def(symbol(off), lib_ref="X", footprint=None)
    with pytest.raises(ValueError, match="length"):
        from_symbol_def(symbol(symbol_pin("1", 0, 0, 0, 1, length=MIL)), lib_ref="X", footprint=None)


def test_directions() -> None:
    pins = [symbol_pin(str(i), 0, 0, rot, 1) for i, rot in enumerate((0, 90, 180, 270), start=1)]
    mapped = from_symbol_def(symbol(*pins), lib_ref="X", footprint=None)
    by = {p.designator: p for p in mapped.pins}
    assert [by[str(i)].direction for i in (1, 2, 3, 4)] == [2, 3, 0, 1]
    assert [(by[str(i)].x, by[str(i)].y) for i in (1, 2, 3, 4)] == [(100, 0), (0, 100), (-100, 0), (0, -100)]


@pytest.mark.parametrize(
    ("etype", "code", "lossy"),
    [
        ("input", 0, False),
        ("bidirectional", 1, False),
        ("output", 2, False),
        ("open_collector", 3, False),
        ("passive", 4, False),
        ("tri_state", 5, False),
        ("open_emitter", 6, False),
        ("power_in", 7, False),
        ("power_out", 7, True),
        ("free", 4, True),
        ("unspecified", 4, True),
        ("no_connect", 4, True),
    ],
)
def test_electrical_types(etype: str, code: int, lossy: bool) -> None:
    issues: list[Issue] = []
    mapped = from_symbol_def(
        symbol(symbol_pin("1", 0, 0, 0, 1, etype)), lib_ref="X", footprint=None, issues=issues
    )  # type: ignore[arg-type]
    assert mapped.pins[0].electrical == code == ELECTRICAL[etype]
    warnings = [i for i in issues if i.code == "altium.pin-lossy"]
    assert len(warnings) == lossy and all(i.severity == "warning" for i in warnings)


@pytest.mark.parametrize(
    ("shape", "inner", "outer", "lossy"),
    [
        ("line", 0, 0, False),
        ("inverted", 0, 1, False),
        ("clock", 3, 0, False),
        ("inverted_clock", 3, 1, False),
        ("input_low", 0, 4, False),
        ("output_low", 0, 17, False),
        ("clock_low", 3, 4, False),
        ("edge_clock_high", 0, 0, True),
        ("non_logic", 0, 0, True),
    ],
)
def test_shapes(shape: str, inner: int, outer: int, lossy: bool) -> None:
    issues: list[Issue] = []
    pin = symbol_pin("1", 0, 0, 0, 1, shape=shape)
    mapped = from_symbol_def(symbol(pin), lib_ref="X", footprint=None, issues=issues)
    assert (mapped.pins[0].inner_edge, mapped.pins[0].outer_edge) == (inner, outer) == EDGE_CODES[shape]
    assert any(i.code == "altium.pin-lossy" for i in issues) is lossy


def test_visibility_and_overbar() -> None:
    pins = (
        symbol_pin("1", 0, 0, 0, 1, name="~{RST}"),
        symbol_pin("2", 0, 100, 0, 1, name="~"),
        symbol_pin("3", 0, 200, 0, 1, hidden=True),
    )
    mapped = from_symbol_def(symbol(*pins), lib_ref="X", footprint=None)
    one, two, three = mapped.pins
    assert one.name == "R\\S\\T\\" and one.name_shown and one.number_shown
    assert not two.name_shown and three.hidden and three.conglomerate & 0x04
    hidden = from_symbol_def(
        symbol(*pins, pin_names_hidden=True, pin_numbers_hidden=True), lib_ref="X", footprint=None
    )
    assert not any(p.name_shown or p.number_shown for p in hidden.pins)
    assert overbar("A~{B}C~{DE}") == "AB\\CD\\E\\" and overbar("~{open") == "~{open"


def test_other_body_styles_and_alternates_dropped() -> None:
    alternate = PinAlternate("ALT", "input", "line")
    pins = (
        symbol_pin("1", 0, 0, 0, 1, body_style=1, alternates=(alternate,)),
        symbol_pin("1", 0, 0, 0, 1, body_style=2),
        symbol_pin("2", 0, 100, 0, 1, body_style=0),
    )
    issues: list[Issue] = []
    mapped = from_symbol_def(
        symbol(*pins, units=(SymbolUnit(1, 1), SymbolUnit(1, 2))), lib_ref="X", footprint=None, issues=issues
    )
    assert [p.designator for p in mapped.pins] == ["1", "2"]
    (info,) = issues
    assert info.code == "altium.symbol-simplified" and info.severity == "info"
    assert "other body styles" in info.message and "alternates" in info.message


def test_part_without_pins_and_defaults() -> None:
    mapped = from_symbol_def(
        symbol(symbol_pin("1", 0, 0, 0, 1), units=(SymbolUnit(1, 1), SymbolUnit(2, 1))),
        lib_ref="X",
        footprint=None,
    )
    assert mapped.rectangle(2) == AltiumRect(2, -100, -100, 100, 100)
    assert (mapped.prefix, mapped.comment, mapped.description) == ("U", "X", "")


def test_small_bodies_grow_outwards() -> None:
    pins = (symbol_pin("1", -150, 30, 0, 1), symbol_pin("2", 150, 30, 180, 1))
    mapped = from_symbol_def(symbol(*pins), lib_ref="X", footprint=None)
    rect = mapped.rectangle(1)
    assert (rect.x0, rect.x1) == (-100, 100)
    assert (rect.y0, rect.y1) == (-70, 130) and rect.y1 - rect.y0 >= 200
