# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Symbol library reading: units, pins, power, hide forms, the ``~`` rule, errors (kicad-library-read)."""

from __future__ import annotations

import dataclasses

import pytest
from _libs import MINI

from fenolite.backends.kicad import slots
from fenolite.backends.kicad.sym import EVIDENCE, read_symbol_library, split_unit_name, write_symbol_library
from fenolite.backends.kicad.versions import UnsupportedFormatError
from fenolite.core.coords import Point
from fenolite.core.errors import FormatError, Issue
from fenolite.core.ids import derived_id
from fenolite.model.base import Modeled, Opaque
from fenolite.model.library import PinAlternate, SymbolDef

V10 = MINI / "Mini.kicad_sym"
V9 = MINI / "Mini_v9.kicad_sym"


def _by_name(path: object) -> dict[str, SymbolDef]:
    return {s.name: s for s in read_symbol_library(path)}  # type: ignore[arg-type]


def _lib(version: int, body: str) -> str:
    return f'(kicad_symbol_lib (version {version}) (generator "t") {body})'


def _pin(etype: str = "passive", style: str = "line", angle: str = "0", extra: str = "") -> str:
    return f'(pin {etype} {style} (at 0 0 {angle}) (length 2.54) {extra} (name "A") (number "1"))'


def test_units_and_common_body_style() -> None:
    gate = _by_name(V10)["Mini_DualGate"]
    assert [(u.unit, u.body_style) for u in gate.units] == [(1, 1), (1, 2), (2, 1), (2, 2), (3, 0)]
    assert gate.unit_count == 3 and gate.body_style_count == 2
    assert [p.number for p in gate.pins_of(3, 2)] == ["7", "14"]
    assert [p.number for p in gate.pins_of(1, 2)] == ["1", "2", "3"]
    assert {p.shape for p in gate.pins_of(1, 2)} == {"inverted", "line"}


def test_power_symbol_in_both_forms() -> None:
    for path in (V10, V9):
        gnd = _by_name(path)["Mini_GND"]
        assert gnd.power == "global" and gnd.reference == "#PWR"
        assert len(gnd.pins) == 1
        pin = gnd.pins[0]
        assert (pin.etype, pin.hidden, pin.length, pin.name, pin.number) == ("power_in", True, 0, "", "1")
    local = read_symbol_library(_lib(20251024, f'(symbol "L" (power local) (symbol "L_1_1" {_pin()}))'))
    assert local[0].power == "local"


def test_empty_text_marker_in_a_9_library() -> None:
    v9, v10 = _by_name(V9)["Mini_QFP32_IC"], _by_name(V10)["Mini_QFP32_IC"]
    assert V9.read_text(encoding="utf-8").count('"~"') >= 2
    assert v9.pins[15].name == "" and v10.pins[15].name == ""
    assert v9.datasheet == "" and v10.datasheet == ""
    assert v9.pins == v10.pins


@pytest.mark.parametrize(("version", "expected"), [(20250317, ""), (20250318, "~"), (20251024, "~")])
def test_tilde_rule_boundary(version: int, expected: str) -> None:
    pin = '(pin passive line (at 0 0 0) (length 1) (name "~") (number "~"))'
    body = f'(symbol "S" (property "Datasheet" "~") (symbol "S_1_1" {pin}))'
    symbol = read_symbol_library(_lib(version, body))[0]
    assert (
        symbol.datasheet == expected and symbol.pins[0].name == expected and symbol.pins[0].number == expected
    )


def test_8_0_hide_atoms() -> None:
    pin = '(pin passive line (at 0 0 0) (length 2.54) hide (name "A") (number "1"))'
    body = f'(symbol "S" (pin_numbers hide) (pin_names (offset 0) hide) (in_bom yes) (symbol "S_1_1" {pin}))'
    symbol = read_symbol_library(_lib(20231120, body))[0]
    assert symbol.pin_numbers_hidden and symbol.pin_names_hidden and symbol.pin_name_offset == 0
    assert symbol.pins[0].hidden


def test_hide_yes_and_no_forms() -> None:
    body = '(symbol "S" (pin_numbers (hide no)) (pin_names (hide yes)))'
    symbol = read_symbol_library(_lib(20251024, body))[0]
    assert not symbol.pin_numbers_hidden and symbol.pin_names_hidden and symbol.pin_name_offset is None


def test_alternate_pin_function() -> None:
    pin = _by_name(V10)["Mini_QFP32_IC"].pins[0]
    assert pin.alternates == (PinAlternate("SDA", "bidirectional", "line"),)
    assert pin.position == Point(-12_700_000, 19_050_000) and pin.length == 2_540_000


def test_hidden_pin_and_flags() -> None:
    ic = _by_name(V10)["Mini_QFP32_IC"]
    assert [p.number for p in ic.pins if p.hidden] == ["32"]
    assert (ic.in_bom, ic.on_board, ic.exclude_from_sim) == (True, True, False)
    assert ic.footprint == "Mini:Mini_QFP-32_7x7mm_P0.8mm" and ic.footprint_filters == ("Mini_QFP*",)
    flags = read_symbol_library(
        _lib(20251024, '(symbol "S" (in_bom no) (on_board no) (exclude_from_sim yes))')
    )[0]
    assert (flags.in_bom, flags.on_board, flags.exclude_from_sim) == (False, False, True)


def test_pin_rotation() -> None:
    resistor = _by_name(V10)["Mini_R"]
    assert [p.rotation for p in resistor.pins] == [270_000_000, 90_000_000]


def test_unknown_electrical_type() -> None:
    body = f'(symbol "S" (symbol "S_1_1" {_pin("analog")}))'
    with pytest.raises(FormatError, match="analog") as caught:
        read_symbol_library(_lib(20251024, body))
    assert caught.value.locator == "/kicad_symbol_lib/symbol[0]/symbol[0]/pin[0]"


@pytest.mark.parametrize(
    ("pin", "match"),
    [(_pin(style="squiggle"), "squiggle"), (_pin(angle="45"), "45"),
     (_pin(extra='(alternate "X" analog line)'), "analog")],
)  # fmt: skip
def test_pin_vocabulary(pin: str, match: str) -> None:
    with pytest.raises(FormatError, match=match):
        read_symbol_library(_lib(20251024, f'(symbol "S" (symbol "S_1_1" {pin}))'))


def test_malformed_unit_suffix() -> None:
    with pytest.raises(FormatError, match="Mini_R_x_1") as caught:
        read_symbol_library(_lib(20251024, '(symbol "Mini_R" (symbol "Mini_R_x_1"))'))
    assert caught.value.locator == "/kicad_symbol_lib/symbol[0]/symbol[0]"


def test_split_unit_name() -> None:
    assert split_unit_name("Mini_R", "Mini_R_1_0") == (1, 0)
    assert split_unit_name("A_B", "A_B_12_2") == (12, 2)
    for bad in ("Mini_R_1", "Other_1_1", "Mini_R_1_1_1", "Mini_R__1"):
        with pytest.raises(ValueError, match=bad):
            split_unit_name("Mini_R", bad)


def test_authored_symbol_graphics_round_trip_and_legacy_rectangle_fallback() -> None:
    from fenolite.dsl import Symbol, mm

    authored = Symbol("Local", "Graphic", reference="R")
    authored.pin("1", "A", at=(mm(-5), mm(0)), length=mm(2.5), rotation=180)
    authored.pin("2", "B", at=(mm(5), mm(0)), length=mm(2.5))
    authored.rect((mm(-2.5), mm(-1.25)), (mm(2.5), mm(1.25)), width=mm(0.2))
    authored.line((mm(-2.5), mm(0)), (mm(2.5), mm(0)))
    authored.circle((mm(0), mm(0)), (mm(0.5), mm(0)))
    authored.polygon(((mm(-1), mm(-1)), (mm(1), mm(-1)), (mm(0), mm(1))))

    rendered = write_symbol_library((authored.definition,))
    loaded = read_symbol_library(rendered, library="Local")[0]
    assert loaded.graphics == authored.definition.graphics
    assert "(rectangle (start -2.5 -1.25) (end 2.5 1.25)" in rendered
    assert "(circle (center 0 0) (radius 0.5)" in rendered
    assert "(xy -1 -1) (xy 1 -1) (xy 0 1) (xy -1 -1)" in rendered

    hidden = dataclasses.replace(authored.definition, pin_names_hidden=True, pin_numbers_hidden=True)
    hidden_text = write_symbol_library((hidden,))
    hidden_readback = read_symbol_library(hidden_text, library="Local")[0]
    assert hidden_readback.pin_names_hidden and hidden_readback.pin_numbers_hidden

    legacy = Symbol("Local", "Legacy", reference="R")
    legacy.pin("1", "A", at=(mm(-1), mm(0)), length=mm(1), rotation=180)
    legacy.pin("2", "B", at=(mm(1), mm(0)), length=mm(1))
    legacy_text = write_symbol_library((legacy.definition,))
    assert "(rectangle (start -2.27 -1.27) (end 2.27 1.27)" in legacy_text


def test_sub_symbols_are_opaque_slots() -> None:
    resistor = _by_name(V10)["Mini_R"]
    found = slots.from_ext(resistor.ext["kicad"])
    assert found[0] == Modeled("name")
    subs = [s for s in found if isinstance(s, Opaque) and s.fragment.startswith('(symbol "Mini_R_')]
    assert len(subs) == 2 and all(s.min_version == "20251024" for s in subs)
    assert Modeled("pin_numbers_hidden") in found and Modeled("in_bom") in found


def test_text_input_and_ids() -> None:
    symbol = read_symbol_library(_lib(20251024, '(symbol "S")'))[0]
    assert symbol.library == "" and symbol.lib_id == "S" and symbol.id == derived_id("sym", "kicad", "S")
    named = _by_name(V10)["Mini_R"]
    assert named.library == "Mini" and named.id == derived_id("sym", "kicad", "Mini:Mini_R")
    assert named.native_ids == {"kicad": "Mini:Mini_R"}
    assert named.provenance is not None and named.provenance.locator.startswith("/kicad_symbol_lib/symbol[")
    assert named.provenance.evidence == EVIDENCE


def test_derived_symbol_read_as_written() -> None:
    red = _by_name(V10)["Mini_LED_Red"]
    assert red.extends == "Mini_LED" and red.pins == () and red.value == "Mini_LED_Red"


def test_version_policy() -> None:
    with pytest.raises(UnsupportedFormatError) as caught:
        read_symbol_library(_lib(20211014, ""))
    assert "sym upgrade" in caught.value.hint
    issues: list[Issue] = []
    assert read_symbol_library(_lib(20990101, '(symbol "S")'), issues=issues)[0].name == "S"
    assert [(i.code, i.severity) for i in issues] == [("kicad.version.future", "warning")]
    with pytest.raises(FormatError, match="kicad_symbol_lib"):
        read_symbol_library('(footprint "X" (version 20260206))')


def test_9_and_10_symbols_compare_equal_without_provenance() -> None:
    def strip(symbol: SymbolDef) -> SymbolDef:
        return dataclasses.replace(symbol, provenance=None, ext={})

    v9 = {s.name: strip(s) for s in read_symbol_library(V9, library="Mini")}
    v10 = {s.name: strip(s) for s in read_symbol_library(V10, library="Mini")}
    assert v9["Mini_QFP32_IC"] == v10["Mini_QFP32_IC"]
    assert v9["Mini_GND"] == v10["Mini_GND"]
