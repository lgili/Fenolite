# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Legible pin texts (capability fenolite-component-catalog, "Legible pin texts"; change c0134).

Every symbol that Fenolite authors is measured with ``tests/_pintext.py``: the catalog symbols, the
symbols of each example library under ``examples/``, and the mini library of ``tests/data/libs`` that
the other examples place. A symbol passes when no shown pin text overlaps another, every shown name has
room inside the body, and no shown name only repeats its pin's number. ``KNOWN`` is the one list of
symbols that do not pass, each with its reason; no other symbol is treated by name.
"""

from __future__ import annotations

import dataclasses
from pathlib import Path
from typing import get_args

import pytest
from _pintext import (
    ALTIUM,
    CHECKED,
    DEFAULT_NAME_OFFSET,
    KICAD,
    MIL,
    STEPS,
    body_box,
    body_end,
    findings,
    judge,
    pin_marks,
    repeats,
    shown_texts,
    unchecked,
)

from fenolite.backends.altium import layout, schlib, symbols
from fenolite.backends.kicad.sym import read_symbol_library, resolve_extends, write_symbol_library
from fenolite.catalog import get_symbol, list_entries
from fenolite.core.coords import Point
from fenolite.core.ids import derived_id
from fenolite.model.library import PinShape, SymbolDef, SymbolGraphic, SymbolPin, SymbolUnit

ROOT = Path(__file__).resolve().parents[3]
MM = 1_000_000
GRID = 2_540_000
LIBRARIES = (
    *sorted((ROOT / "examples").rglob("*.kicad_sym")),
    *sorted((ROOT / "tests" / "data" / "libs").glob("*.kicad_sym")),
)
"""The authored symbol libraries: the example libraries and the mini library the examples place."""

_NO_BODY = (
    "its power unit has no body: the two pins face each other 5.08 mm apart, so GND and VCC lie on each "
    "other at any size. The symbol is a fixture of the library reader (units, common pins) and no "
    "example places it; a new body would change the mini library that the reader's tests pin"
)
_NARROW = (
    "at the Altium size three rows of facing names overlap (NRST and PB12, OSC_IN and PB13, OSC_OUT and "
    "PB14) in a body 20.32 mm wide; it passes at the KiCad size. A wider body would change the mini "
    "library and the committed samples built from it (blink, routed, board6, the hierarchy board), which "
    "the maintainer's author reports partly cover; it waits for one look at U1 of the blink sample in "
    "Altium, which also settles the width the Altium size assumes"
)
KNOWN: dict[str, str] = {
    "Mini.kicad_sym:Mini_DualGate": _NO_BODY,
    "Mini_v9.kicad_sym:Mini_DualGate": _NO_BODY,
    "Mini.kicad_sym:Mini_QFP32_IC": _NARROW,
    "Mini_v9.kicad_sym:Mini_QFP32_IC": _NARROW,
}
"""Symbols that do not pass, with the reason each is left as it is (design of change c0134)."""


def _cases() -> list[tuple[str, SymbolDef]]:
    cases = [
        (f"catalog:{entry.lib_id.removeprefix('Fenolite:')}", get_symbol(entry.lib_id))
        for entry in list_entries(kind="symbol")
    ]
    for path in LIBRARIES:
        cases += [(f"{path.name}:{s.name}", s) for s in resolve_extends(read_symbol_library(path))]
    return cases


CASES = _cases()


def test_every_authored_library_is_measured() -> None:
    names = [name for name, _ in CASES]
    assert len(names) == len(set(names))
    assert sum(name.startswith("catalog:") for name in names) == 49
    measured = {path.relative_to(ROOT).as_posix() for path in LIBRARIES}
    assert {
        "examples/altium_kicad/FenoliteDemo.kicad_sym",
        "tests/data/libs/Mini.kicad_sym",
        "tests/data/libs/Mini_v9.kicad_sym",
    } <= measured
    assert set(KNOWN) <= set(names)


@pytest.mark.parametrize(("name", "symbol"), CASES, ids=[name for name, _ in CASES])
def test_shown_pin_texts_are_legible(name: str, symbol: SymbolDef) -> None:
    found = findings(symbol)
    if name in KNOWN:
        assert found, f"{name} passes now: remove it from KNOWN"
        return
    assert not found, "\n".join([f"{name}: {len(found)} finding(s)", *found])


def test_catalog_shows_names_only_where_the_body_is_a_plain_box() -> None:
    """A drawing tells its pins apart, so it hides their names; a plain rectangle says nothing about its
    pins, so it shows them."""
    for entry in list_entries(kind="symbol"):
        symbol = get_symbol(entry.lib_id)
        plain = len(symbol.graphics) == 1 and symbol.graphics[0].kind == "rect"
        assert symbol.pin_names_hidden == (not plain), entry.lib_id
        assert not symbol.pin_numbers_hidden, entry.lib_id


def test_the_estimate_follows_the_writers() -> None:
    """The two sizes are those of the texts the writers ask for; a writer that changes its size, its
    offset or its font brings this test down, and the estimate with it."""
    text = write_symbol_library((get_symbol("Fenolite:Linear_Regulator"),))
    assert '(name "IN" (effects (font (size 1.27 1.27))))' in text
    assert '(number "1" (effects (font (size 1.27 1.27))))' in text
    assert "(pin_names (offset 0.508) (hide no))" in text
    assert KICAD.height == 1_270_000 and DEFAULT_NAME_OFFSET == 508_000
    assert 100 * KICAD.char == 115 * KICAD.height
    assert KICAD.height < KICAD.thick == 1_600_000
    assert (schlib.FONT_NAME, schlib.FONT_SIZE) == ("Times New Roman", 10)
    assert ALTIUM.height == layout.TEXT_HEIGHT * MIL == 100 * MIL
    assert ALTIUM.thick == 90 * MIL < ALTIUM.height
    assert ALTIUM.char == ALTIUM.height > symbols.CHAR_WIDTH * MIL


def _with_pins_of(symbol: SymbolDef, length: int) -> SymbolDef:
    """``symbol`` with every pin ``length`` long and its body end where it is."""
    pins = []
    for pin in symbol.pins:
        end_x, end_y = body_end(pin)
        dx, dy = STEPS[pin.rotation]
        pins.append(
            dataclasses.replace(pin, position=Point(end_x - dx * length, end_y - dy * length), length=length)
        )
    return dataclasses.replace(symbol, pins=tuple(pins))


def test_mcu8_keeps_its_texts_off_its_bubbles_and_its_wedge() -> None:
    """Scenario "Pin shapes of the example library": what the name offset and the longer pins are for."""
    library = ROOT / "examples" / "altium_kicad" / "FenoliteDemo.kicad_sym"
    (mcu,) = [symbol for symbol in read_symbol_library(library) if symbol.name == "MCU8"]
    assert {pin.number: pin.shape for pin in mcu.pins if pin.shape != "line"} == {
        "2": "inverted",
        "3": "clock",
        "5": "inverted",
    }
    assert mcu.pin_name_offset == 1_778_000 and {pin.length for pin in mcu.pins} == {2 * GRID}
    assert findings(mcu) == []
    assert findings(dataclasses.replace(mcu, pin_name_offset=None)) == [
        "unit 1, KiCad size: MARK name 'CLK' of pin 3 lies over the clock mark of pin 3"
    ]
    assert findings(_with_pins_of(mcu, GRID)) == [
        "unit 1, KiCad size: MARK number '2' of pin 2 lies over the inverted mark of pin 2",
        "unit 1, KiCad size: MARK number '5' of pin 5 lies over the inverted mark of pin 5",
    ]


def test_numbers_stand_clear_of_the_strokes_beside_their_pins() -> None:
    """Scenario "A number on a stroke of the body": the hook of the Schottky bar, the plus of a polarized
    capacitor, the corners of the upright resistor of the example library."""
    schottky = get_symbol("Fenolite:Schottky_Diode")
    assert findings(schottky) == []
    assert findings(_with_pins_of(schottky, GRID)) == [
        "unit 1, KiCad size: STROKE number '2' of pin 2 lies over 2 body stroke(s) and 0 pin stem(s)"
    ]
    for name in ("Capacitor_Polarized", "Capacitor_Electrolytic"):
        capacitor = get_symbol(f"Fenolite:{name}")
        assert findings(capacitor) == []
        marks = [g for g in capacitor.graphics if g.kind == "line" and max(p.y for p in g.points) < 0]
        assert len(marks) == 2  # the plus, below the positive lead
        above = tuple(
            dataclasses.replace(g, points=tuple(Point(p.x, -p.y) for p in g.points)) if g in marks else g
            for g in capacitor.graphics
        )
        assert findings(dataclasses.replace(capacitor, graphics=above)) == [
            "unit 1, KiCad size: STROKE number '1' of pin 1 lies over 1 body stroke(s) and 0 pin stem(s)"
        ]
    library = ROOT / "examples" / "altium_kicad" / "FenoliteDemo.kicad_sym"
    (upright,) = [symbol for symbol in read_symbol_library(library) if symbol.name == "R_V"]
    assert findings(upright) == []
    assert {line.split(": ", 1)[1] for line in findings(_with_pins_of(upright, GRID // 2))} == {
        "STROKE number '1' of pin 1 lies over 2 body stroke(s) and 0 pin stem(s)",
        "STROKE number '2' of pin 2 lies over 2 body stroke(s) and 0 pin stem(s)",
    }


# --- the measure itself, on symbols made for it -------------------------------------------------------


def _pin(number: str, name: str, x: int, y: int, rotation: int, **more: object) -> SymbolPin:
    fields: dict[str, object] = {
        "number": number,
        "name": name,
        "etype": "passive",
        "position": Point(x, y),
        "rotation": rotation * 1_000_000,
        "length": GRID,
        "unit": 1,
        "body_style": 1,
        **more,
    }
    return SymbolPin(**fields)  # type: ignore[arg-type]


def _box(half_x: int, half_y: int, pins: tuple[SymbolPin, ...], **flags: object) -> SymbolDef:
    """A rectangle of ``2 * half_x`` by ``2 * half_y`` around the origin with ``pins``."""
    body = SymbolGraphic("rect", (Point(-half_x, -half_y), Point(half_x, half_y)), 254_000, True)
    return SymbolDef(
        id=derived_id("sym", "test", "T:BOX"),
        name="BOX",
        library="T",
        units=(SymbolUnit(1, 1),),
        pins=pins,
        graphics=(body,),
        **flags,  # type: ignore[arg-type]
    )


def _facing(half_x: int, left: str = "ABCD", right: str = "EFGH") -> SymbolDef:
    pins = (_pin("1", left, -half_x - GRID, 0, 0), _pin("2", right, half_x + GRID, 0, 180))
    return _box(half_x, GRID, pins)


def _kinds(symbol: SymbolDef) -> set[str]:
    return {line.split(": ", 1)[1].split(" ", 1)[0] for line in findings(symbol)}


def test_facing_names_need_a_body_wide_enough_for_both() -> None:
    """Two four-letter names: 2 x (0.508 + 4 x 1.4605) = 12.7 mm at the KiCad size, and
    2 x (50 + 4 x 100) = 900 mil at the Altium size."""
    assert _kinds(_facing(2 * GRID)) == {"OVERLAP", "OUTSIDE", "STROKE"}
    narrow = _facing(3 * GRID)  # 15.24 mm = 600 mil: room at the KiCad size only
    assert judge(narrow, 1, KICAD) == []
    assert [line.split(" ", 1)[0] for line in judge(narrow, 1, ALTIUM)] == ["OVERLAP"]
    assert findings(_facing(9 * GRID // 2)) == []  # 22.86 mm = 900 mil: the names just meet
    assert findings(_facing(5 * GRID)) == []


def test_a_name_that_repeats_its_number_is_a_finding_only_while_both_show() -> None:
    symbol = _facing(5 * GRID, "1", "~{2}")
    assert repeats(symbol, 1) == [
        "REPEAT name '1' of pin 1 only repeats its number",
        "REPEAT name '2' of pin 2 only repeats its number",
    ]
    assert _kinds(symbol) == {"REPEAT"}
    assert findings(dataclasses.replace(symbol, pin_names_hidden=True)) == []
    assert findings(dataclasses.replace(symbol, pin_numbers_hidden=True)) == []


def test_a_name_under_a_stroke_or_a_pin_stem_has_no_room() -> None:
    clean = _facing(5 * GRID, "IN", "")
    assert findings(clean) == []
    bar = SymbolGraphic("line", (Point(-4 * GRID, -GRID), Point(-4 * GRID, GRID)))
    struck = dataclasses.replace(clean, graphics=(*clean.graphics, bar))
    assert _kinds(struck) == {"STROKE"}
    ring = SymbolGraphic("circle", (Point(-4 * GRID, 0), Point(-4 * GRID + MM, 0)))
    assert _kinds(dataclasses.replace(clean, graphics=(*clean.graphics, ring))) == {"STROKE"}
    around = SymbolGraphic("circle", (Point(0, 0), Point(40 * MM, 0)))  # the name lies wholly inside it
    assert findings(dataclasses.replace(clean, graphics=(*clean.graphics, around))) == []
    stem = _pin("3", "", -4 * GRID, 3 * GRID, 270, length=3 * GRID)  # runs down through the name
    crossed = dataclasses.replace(clean, pins=(*clean.pins, stem))
    assert [line for line in findings(crossed) if "STROKE name" in line] == [
        "unit 1, KiCad size: STROKE name 'IN' of pin 1 lies over 0 body stroke(s) and 1 pin stem(s)",
        "unit 1, Altium size: STROKE name 'IN' of pin 1 lies over 0 body stroke(s) and 1 pin stem(s)",
    ]


def test_a_number_on_a_body_stroke_is_a_finding() -> None:
    """KiCad centres a number on its pin, so a short pin puts it over whatever the body draws beside the
    pin's end: the hook of a diode's bar, the corner of a narrow box, a polarity mark."""
    clean = _facing(5 * GRID, "IN", "")
    assert findings(clean) == []
    hook = SymbolGraphic(
        "line", (Point(-11 * GRID // 2, MM), Point(-11 * GRID // 2, 2 * MM))
    )  # over number 1
    assert findings(dataclasses.replace(clean, graphics=(*clean.graphics, hook))) == [
        "unit 1, KiCad size: STROKE number '1' of pin 1 lies over 1 body stroke(s) and 0 pin stem(s)"
    ]
    below = SymbolGraphic("line", (Point(-11 * GRID // 2, -2 * MM), Point(-11 * GRID // 2, -MM)))
    assert findings(dataclasses.replace(clean, graphics=(*clean.graphics, below))) == []
    upright = (
        _pin("1", "", 0, 3 * GRID // 2, 270, length=GRID // 2),
        _pin("2", "", 0, -3 * GRID // 2, 90, length=GRID // 2),
    )
    assert _kinds(_box(GRID // 2, GRID, upright)) == {"STROKE"}  # 1.27 mm of pin: the digit reaches the box
    longer = (_pin("1", "", 0, 2 * GRID, 270), _pin("2", "", 0, -2 * GRID, 90))
    assert findings(_box(GRID // 2, GRID, longer)) == []


SHAPES = (
    "inverted",
    "clock",
    "inverted_clock",
    "input_low",
    "clock_low",
    "output_low",
    "edge_clock_high",
    "non_logic",
)


def test_pin_marks_are_what_kicad_draws_at_the_body_end() -> None:
    """A left pin whose body end is the origin: the bubble outside it, the wedge inside it, the low-level
    marks above the pin; an upright pin has them on its left, where its number is."""
    level = _pin("1", "A", -GRID, 0, 0)
    half, full = 635_000, 1_270_000
    assert pin_marks(level) == ([], [])
    assert pin_marks(dataclasses.replace(level, shape="inverted")) == ([], [(-half, 0, half * half)])
    wedge = [((0, -half), (full, 0)), ((full, 0), (0, half))]
    assert pin_marks(dataclasses.replace(level, shape="clock")) == (wedge, [])
    assert pin_marks(dataclasses.replace(level, shape="inverted_clock")) == (wedge, [(-half, 0, half * half)])
    low = [((-full, 0), (-full, full)), ((-full, full), (0, 0))]
    assert pin_marks(dataclasses.replace(level, shape="input_low")) == (low, [])
    assert pin_marks(dataclasses.replace(level, shape="clock_low")) == (wedge + low, [])
    assert pin_marks(dataclasses.replace(level, shape="output_low")) == ([((0, full), (-full, 0))], [])
    assert pin_marks(dataclasses.replace(level, shape="edge_clock_high")) == (
        [((0, -half), (-full, 0)), ((-full, 0), (0, half))],
        [],
    )
    assert pin_marks(dataclasses.replace(level, shape="non_logic")) == (
        [((half, half), (-half, -half)), ((half, -half), (-half, half))],
        [],
    )
    right = _pin("1", "A", GRID, 0, 180, shape="input_low")
    assert pin_marks(right)[0] == [((full, 0), (full, full)), ((full, full), (0, 0))]  # above, as on the left
    down = _pin(
        "1", "A", 0, GRID, 270, shape="clock_low"
    )  # from above: the wedge points down, the mark is left
    assert pin_marks(down)[0] == [
        ((half, 0), (0, -full)),
        ((0, -full), (-half, 0)),
        ((0, full), (-full, full)),
        ((-full, full), (0, 0)),
    ]
    assert set(SHAPES) | {"line"} == set(get_args(PinShape))


def test_a_text_on_the_mark_of_a_pin_shape_is_a_finding() -> None:
    """A clock wedge reaches 1.27 mm into the body, past KiCad's default name offset; a bubble takes the
    1.27 mm of the pin next to the body, under the number of a pin of 2.54 mm."""
    half = 5 * GRID

    def one(shape: str, length: int, offset: int | None, pitch: int = 2 * GRID) -> list[str]:
        pins = (
            _pin("1", "AB", -half - length, 0, 0, length=length, shape=shape),
            _pin("2", "CD", -half - length, -pitch, 0, length=length),
        )
        return judge(_box(half, 3 * GRID, pins, pin_name_offset=offset), 1, KICAD)

    assert one("clock", GRID, None) == ["MARK name 'AB' of pin 1 lies over the clock mark of pin 1"]
    assert one("clock", GRID, 1_778_000) == []
    assert one("inverted", GRID, None) == ["MARK number '1' of pin 1 lies over the inverted mark of pin 1"]
    assert one("inverted", 2 * GRID, None) == []
    assert one("inverted_clock", GRID, None) == [
        "MARK name 'AB' of pin 1 lies over the inverted_clock mark of pin 1",
        "MARK number '1' of pin 1 lies over the inverted_clock mark of pin 1",
    ]
    assert one("inverted_clock", 2 * GRID, 1_778_000) == []
    # on a pitch of 2.54 mm the number of the pin below reaches the bubble of the pin above
    assert one("inverted", 2 * GRID, None, GRID) == []
    assert one("inverted", GRID, None, GRID) == [
        "MARK number '1' of pin 1 lies over the inverted mark of pin 1",
        "MARK number '2' of pin 2 lies over the inverted mark of pin 1",
    ]
    # on a pin of 2.54 mm every mark lies under a text, but the outer wedge, which ends below the number
    for shape in SHAPES:
        assert bool(one(shape, GRID, None)) == (shape != "edge_clock_high"), shape
    assert judge(_box(half, 3 * GRID, (_pin("1", "AB", -half - GRID, 0, 0, shape="clock"),)), 1, ALTIUM) == []


def test_a_character_that_was_not_compared_is_a_finding() -> None:
    """The KiCad-size box holds what KiCad draws for capitals, digits and four signs; a wide glyph or a
    descender can leave it, so such a text is not passed on the strength of its box."""
    assert CHECKED == frozenset("ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789+-_~")
    assert findings(_facing(5 * GRID, "A_1+", "~{B-}")) == []
    assert unchecked(_facing(5 * GRID, "@@", "gyp"), 1) == [
        "UNCHECKED name '@@' of pin 1 holds '@', outside the compared characters",
        "UNCHECKED name 'gyp' of pin 2 holds 'gpy', outside the compared characters",
    ]
    assert _kinds(_facing(5 * GRID, "@@", "")) == {"UNCHECKED"}
    assert findings(dataclasses.replace(_facing(5 * GRID, "@@", ""), pin_names_hidden=True)) == []
    used = {
        char
        for _, symbol in CASES
        for unit in range(1, symbol.unit_count + 1)
        for text in shown_texts(symbol, unit, KICAD)
        for char in text.text
    }
    assert used <= CHECKED


def test_hidden_pins_empty_names_and_tildes_draw_nothing() -> None:
    pins = (
        _pin("1", "", -6 * GRID, 0, 0),
        _pin("2", "~", 6 * GRID, 0, 180),
        _pin("3", "LONGNAMEHERE", 0, -2 * GRID, 90, hidden=True),
    )
    symbol = _box(5 * GRID, GRID, pins)
    assert [(t.kind, t.text) for t in shown_texts(symbol, 1, KICAD)] == [
        ("number", "1"),
        ("name", "~"),
        ("number", "2"),
    ]
    assert [(t.kind, t.text) for t in shown_texts(symbol, 1, ALTIUM)] == [("number", "1"), ("number", "2")]
    assert findings(symbol) == []


def test_boxes_follow_the_pin_and_its_side() -> None:
    """One name on each side of a box of 20.32 mm: the boxes in millimetres, at both sizes."""
    half = 4 * GRID
    pins = (
        _pin("1", "AB", -half - GRID, 0, 0),
        _pin("2", "AB", half + GRID, 0, 180),
        _pin("3", "AB", 0, half + GRID, 270),
        _pin("4", "AB", 0, -half - GRID, 90),
    )
    symbol = _box(half, half, pins)
    assert body_box(symbol) == (-half, -half, half, half)

    def boxes(size: object, kind: str) -> list[tuple[float, ...]]:
        return [
            tuple(v / MM for v in t.box)
            for t in shown_texts(symbol, 1, size)  # type: ignore[arg-type]
            if t.kind == kind
        ]

    assert boxes(KICAD, "name") == [
        (-9.652, -0.8, -6.731, 0.8),
        (6.731, -0.8, 9.652, 0.8),
        (-0.8, 6.731, 0.8, 9.652),
        (-0.8, -9.652, 0.8, -6.731),
    ]
    assert boxes(KICAD, "number") == [
        (-12.16025, 0.36, -10.69975, 1.96),
        (10.69975, 0.36, 12.16025, 1.96),
        (-1.96, 10.69975, -0.36, 12.16025),
        (-1.96, -12.16025, -0.36, -10.69975),
    ]
    assert boxes(ALTIUM, "name") == [
        (-8.89, -1.143, -3.81, 1.143),
        (3.81, -1.143, 8.89, 1.143),
        (-1.143, 3.81, 1.143, 8.89),
        (-1.143, -8.89, 1.143, -3.81),
    ]
    assert boxes(ALTIUM, "number") == [
        (-14.732, 0.254, -12.192, 2.54),
        (12.192, 0.254, 14.732, 2.54),
        (-2.54, 12.192, -0.254, 14.732),
        (-2.54, -14.732, -0.254, -12.192),
    ]
    assert findings(symbol) == []


def test_names_outside_the_body_sit_above_their_pins() -> None:
    """A name offset of 0 is KiCad's "names outside": the name above the pin line, the number below it,
    and the body's box does not bound the name."""
    symbol = dataclasses.replace(_facing(2 * GRID, "A", "B"), pin_name_offset=0)
    texts = {(t.kind, t.pin): t for t in shown_texts(symbol, 1, KICAD)}
    assert texts[("name", "1")].box == (-7_080_250, 360_000, -5_619_750, 1_960_000)
    assert texts[("number", "1")].box == (-7_080_250, -1_960_000, -5_619_750, -360_000)
    assert not texts[("name", "1")].inside
    assert judge(symbol, 1, KICAD) == []
    wide = dataclasses.replace(_facing(2 * GRID, "ABC", "D"), pin_name_offset=0)
    assert judge(wide, 1, KICAD) == [
        "STROKE name 'ABC' of pin 1 lies over 1 body stroke(s) and 0 pin stem(s)"
    ]  # 4.38 mm of name over a pin of 2.54 mm reach the body's edge


def test_an_overbar_needs_room_on_the_side_the_letters_point_to() -> None:
    """KiCad draws the bar of ``~{AB}`` beyond the tops of the letters: above a level name, to the left
    of an upright one. The Altium size counts nothing for it."""
    half = 4 * GRID
    pins = (_pin("1", "~{AB}", -half - GRID, 0, 0), _pin("2", "~{AB}", 0, half + GRID, 270))
    symbol = _box(half, half, pins)
    level, upright = (t.box for t in shown_texts(symbol, 1, KICAD) if t.kind == "name")
    assert level == (-9_652_000, -800_000, -6_731_000, 1_300_000)
    assert upright == (-1_300_000, 6_731_000, 800_000, 9_652_000)
    plain = [t.box for t in shown_texts(symbol, 1, ALTIUM) if t.kind == "name"]
    assert plain == [
        (-8_890_000, -1_143_000, -3_810_000, 1_143_000),
        (-1_143_000, 3_810_000, 1_143_000, 8_890_000),
    ]
    # a name 2 mm above: clear of a plain name (1.6 mm of line each), under the bar of a barred one
    for name, kinds in (("AB", set()), ("~{AB}", {"OVERLAP"})):
        rows = (_pin("1", name, -half - GRID, 0, 0), _pin("3", "CD", -half - GRID, 2 * MM, 0))
        found = judge(dataclasses.replace(symbol, pins=rows), 1, KICAD)
        assert {line.split(" ", 1)[0] for line in found} == kinds


def test_a_symbol_without_graphics_is_judged_on_the_box_the_writer_draws() -> None:
    bare = dataclasses.replace(_facing(5 * GRID, "IN", "OUT"), graphics=())
    assert body_box(bare) == (-6 * GRID - 1_270_000, -1_270_000, 6 * GRID + 1_270_000, 1_270_000)
    assert findings(bare) == []
