# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Level S observes typed effects after backend effective-style extraction (c0326)."""

from __future__ import annotations

import dataclasses

import _drawn
import pytest

from fenolite.checks.equivalence import compare_drawn
from fenolite.core.coords import Point, Size
from fenolite.model.drawn import DrawnField, DrawnFont, DrawnSchematic


def _font(value: DrawnSchematic, surface: str, font: DrawnFont | None) -> DrawnSchematic:
    root = value.sheets[0]
    if surface == "symbol":
        symbol = root.symbols[0]
        fields = tuple(
            dataclasses.replace(field, font=font) if field.name == "Reference" else field
            for field in symbol.fields
        )
        root = dataclasses.replace(
            root, symbols=(dataclasses.replace(symbol, fields=fields), *root.symbols[1:])
        )
    elif surface == "power":
        power = root.powers[0]
        fields = (DrawnField("Value", Point(power.at.x, power.at.y + 2_540_000), font=font),)
        root = dataclasses.replace(root, powers=(dataclasses.replace(power, fields=fields),))
    elif surface in {"pin", "sheet-field"}:
        ref = root.sheet_refs[0]
        if surface == "pin":
            ref = dataclasses.replace(
                ref, pins=tuple(dataclasses.replace(pin, font=font) for pin in ref.pins)
            )
        else:
            ref = dataclasses.replace(ref, fields=(DrawnField("Sheetname", ref.at, font=font),))
        root = dataclasses.replace(root, sheet_refs=(ref,))
    else:
        index, sheet = next(
            (index, sheet)
            for index, sheet in enumerate(value.sheets)
            if any(label.kind == surface for label in sheet.labels)
        )
        k = next(k for k, label in enumerate(sheet.labels) if label.kind == surface)
        labels = tuple(
            dataclasses.replace(label, font=font) if i == k else label for i, label in enumerate(sheet.labels)
        )
        sheet = dataclasses.replace(sheet, labels=labels)
        return dataclasses.replace(
            value, sheets=tuple(sheet if i == index else old for i, old in enumerate(value.sheets))
        )
    return dataclasses.replace(value, sheets=(root, *value.sheets[1:]))


def _differences(a: DrawnSchematic, b: DrawnSchematic):
    return compare_drawn(a, b, pins_a=_drawn.pins(a, "full"), pins_b=_drawn.pins(b, "full")).differences


@pytest.mark.parametrize(
    "surface", ("symbol", "power", "local", "global", "hierarchical", "pin", "sheet-field")
)
@pytest.mark.parametrize(
    ("attribute", "replacement"),
    (
        ("size", Size(750_000, 500_000)),
        ("thickness", 100_000),
        ("bold", True),
        ("italic", True),
        ("face", "Authored B"),
    ),
)
def test_each_effect_has_a_located_level_s_difference(
    surface: str, attribute: str, replacement: object
) -> None:
    font = DrawnFont(Size(500_000, 750_000), 75_000, False, False, "Authored A")
    a = _font(_drawn.drawn("full"), surface, font)
    b = _font(a, surface, dataclasses.replace(font, **{attribute: replacement}))
    differences = _differences(a, b)
    assert len(differences) == 1, differences
    found = differences[0]
    assert found.level == "S" and found.field.endswith(f".font.{attribute}"), found
    assert found.kind == ("symbol-field" if surface == "symbol" else "item-field")
    assert found.where.startswith("/") and found.a != found.b


@pytest.mark.parametrize("surface", ("label", "pin"))
def test_explicit_centring_does_not_equal_the_legacy_anchor(surface: str) -> None:
    a = _drawn.drawn("full")
    root = a.sheets[0]
    if surface == "label":
        labels = (dataclasses.replace(root.labels[0], justify=""), *root.labels[1:])
        changed = dataclasses.replace(root, labels=labels)
    else:
        ref = root.sheet_refs[0]
        pins = (dataclasses.replace(ref.pins[0], justify=""), *ref.pins[1:])
        changed = dataclasses.replace(root, sheet_refs=(dataclasses.replace(ref, pins=pins),))
    b = dataclasses.replace(a, sheets=(changed, *a.sheets[1:]))
    differences = _differences(a, b)
    assert len(differences) == 1 and differences[0].field.endswith(".justify"), differences
    assert differences[0].a != differences[0].b


def test_sheet_field_pose_is_observable_without_a_font() -> None:
    a = _font(_drawn.drawn("full"), "sheet-field", None)
    root = a.sheets[0]
    ref = root.sheet_refs[0]
    field = dataclasses.replace(ref.fields[0], at=Point(ref.at.x + 1_000_000, ref.at.y))
    changed = dataclasses.replace(root, sheet_refs=(dataclasses.replace(ref, fields=(field,)),))
    found = _differences(a, dataclasses.replace(a, sheets=(changed, *a.sheets[1:])))
    assert len(found) == 1 and found[0].field == "sheet_ref.fields.Sheetname", found


@pytest.mark.parametrize("target", (9, 10))
def test_native_default_presence_and_legacy_anchor_spellings_compare_equal(target: int) -> None:
    plain = _drawn.drawn("full")
    declared = _font(plain, "symbol", DrawnFont(Size(1_270_000, 1_270_000), 0, False, False))
    a, _, _ = _drawn.resolved(_drawn.build("full", target, value=plain))
    b, _, _ = _drawn.resolved(_drawn.build("full", target, value=declared))
    assert _differences(a, b) == ()
