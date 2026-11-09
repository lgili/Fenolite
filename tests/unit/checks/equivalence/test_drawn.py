# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Level S compares what a converted drawing must keep (change c0470, task 5.2; capability
design-equivalence, "Level S compares drawn schematics"): the unit of a part, the power style, the label
shape, the paper and title block, and an opaque record by its Altium text. Display mode is not in the drawn
model: the conversion carries it and reports it under ``symbol-graphic`` (design D5). Hermetic: the
authored drawn fixtures and the mini library only."""

from __future__ import annotations

import dataclasses

import _drawn

from fenolite.checks.equivalence import compare_drawn
from fenolite.model.drawn import DrawnOpaque, DrawnSchematic

FLAT = _drawn.drawn("flat")
PINS = _drawn.pins(FLAT, "flat")


def replaced(value: DrawnSchematic, **changes: object) -> DrawnSchematic:
    root = value.sheets[0]
    return dataclasses.replace(value, sheets=(dataclasses.replace(root, **changes), *value.sheets[1:]))  # type: ignore[arg-type]


def found(a: DrawnSchematic, b: DrawnSchematic) -> list[tuple[str, str, str, str]]:
    """The differences of ``a`` and ``b``, whose pins are those of ``flat`` (the changes move no pin)."""
    result = compare_drawn(a, b, pins_a=PINS, pins_b=PINS)
    return [(d.kind, d.field, d.a, d.b) for d in result.differences]


def test_c0470_unit_of_a_part() -> None:
    root = FLAT.sheets[0]
    symbols = tuple(dataclasses.replace(s, unit=2) if s.part == "R1" else s for s in root.symbols)
    b = replaced(FLAT, symbols=symbols)
    result = compare_drawn(FLAT, b, pins_a=PINS, pins_b=_drawn.pins(b, "flat"))
    assert [(d.kind, d.where) for d in result.differences] == [
        ("symbol-missing", "/:R1:1"),
        ("symbol-missing", "/:R1:2"),
    ]


def test_c0470_power_style() -> None:
    powers = FLAT.sheets[0].powers
    b = replaced(FLAT, powers=(dataclasses.replace(powers[0], symbol="AltiumPower:Arrow"), *powers[1:]))
    assert found(FLAT, b) == [("item-field", "power.symbol", "Mini:Mini_GND", "AltiumPower:Arrow")]


def test_c0470_label_shape() -> None:
    labels = tuple(dataclasses.replace(x, kind="global", shape="input") for x in FLAT.sheets[0].labels)
    a = replaced(FLAT, labels=labels)
    b = replaced(FLAT, labels=tuple(dataclasses.replace(x, shape="output") for x in labels))
    assert found(a, b) == [("item-field", "label.global.shape", "input", "output")]


def test_c0470_paper_and_title_block() -> None:
    b = replaced(FLAT, paper="A3", title_block=(("title", "Blink"),))
    assert found(FLAT, b) == [
        ("item-field", "sheet.paper", "A4", "A3"),
        ("item-field", "sheet.title_block.title", "", "Blink"),
    ]


def test_c0470_opaque_compares_by_its_altium_text() -> None:
    """The KiCad text that stands for an Altium record may change; its Altium text may not."""
    a = replaced(FLAT, opaques=(DrawnOpaque("(text a)", "|RECORD=4|TEXT=a"),))
    standing = replaced(FLAT, opaques=(DrawnOpaque("(text b)", "|RECORD=4|TEXT=a"),))
    other = replaced(FLAT, opaques=(DrawnOpaque("", "|RECORD=4|TEXT=b"),))
    assert found(a, standing) == []
    assert sorted(kind for kind, *_ in found(a, other)) == ["item-missing", "item-missing"]
