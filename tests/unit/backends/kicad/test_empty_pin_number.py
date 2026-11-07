# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Checked raw/canonical pin identity, preserving empty and literal texts (c0353)."""

from __future__ import annotations

import dataclasses

import pytest
from _empty_pin_number import definition

from fenolite.backends.kicad.symembed import embed_symbol
from fenolite.core.errors import FormatError


@pytest.mark.parametrize("source", [9, 10])
@pytest.mark.parametrize("target", [9, 10])
def test_empty_number_identity_survives_all_source_target_pairs(source, target):
    original = definition(source)
    actual = embed_symbol(original, target=target, show_hidden_power=False)
    assert [(pin.number, pin.name) for pin in actual.definition.pins] == [
        ("", "AUTH_EMPTY"),
        ("2", "AUTH_CONTROL"),
    ]


def test_modern_literal_tilde_is_not_an_empty_number():
    original = definition(10, "~")
    actual = embed_symbol(original, target=10)
    assert [pin.number for pin in actual.definition.pins] == ["~", "2"]
    for lossy in (False, True):
        with pytest.raises(FormatError, match="tilde"):
            embed_symbol(original, target=9, allow_lossy=lossy)


@pytest.mark.parametrize("unit,style", [(1, 1), (2, 1), (2, 2)])
def test_blank_number_lookup_is_bound_to_unit_and_body_style(unit, style):
    actual = embed_symbol(definition(9, unit=unit, style=style), target=10)
    assert [(pin.number, pin.unit, pin.body_style) for pin in actual.definition.pins] == [
        ("", unit, style),
        ("2", unit, style),
    ]


def test_explicit_mapping_uses_checked_empty_identity_and_literal_can_map_for_nine():
    blank = embed_symbol(definition(9), target=10, pin_numbers=(("", "A"),))
    literal = embed_symbol(definition(10, "~"), target=9, pin_numbers=(("~", "A"),))
    assert [pin.number for pin in blank.definition.pins] == ["A", "2"]
    assert [pin.number for pin in literal.definition.pins] == ["A", "2"]


def test_unchecked_cardinality_does_not_pick_first_blank_pin():
    source = definition(9)
    broken = dataclasses.replace(source, pins=source.pins[1:])
    with pytest.raises(FormatError, match="pin"):
        embed_symbol(broken, target=10)


def test_old_empty_name_and_number_are_both_preserved():
    found = embed_symbol(definition(9, empty_name=True), target=10)
    assert [(pin.number, pin.name) for pin in found.definition.pins] == [("", ""), ("2", "AUTH_CONTROL")]


@pytest.mark.parametrize("kind", ["unit", "geometry"])
def test_stale_model_association_refuses_locally(kind):
    from fenolite.core.coords import Point

    source = definition(9)
    pin = source.pins[0]
    changed = (
        dataclasses.replace(pin, unit=2)
        if kind == "unit"
        else dataclasses.replace(pin, position=Point(pin.position.x + 1, pin.position.y))
    )
    source = dataclasses.replace(source, pins=(changed, *source.pins[1:]))
    with pytest.raises(FormatError, match="pin"):
        embed_symbol(source, target=10)


def test_modern_literal_and_empty_numbers_at_same_position_remain_distinct():
    from _empty_pin_number import library

    from fenolite.backends.kicad.sym import read_symbol_library

    text = library(10)
    extra = (
        "(pin passive line (at -5.08 0 0) (length 2.54) "
        '(name "LITERAL" (effects (font (size 1.27 1.27)))) '
        '(number "~" (effects (font (size 1.27 1.27))))) '
    )
    text = text.replace("(pin passive line (at 5.08", extra + "(pin passive line (at 5.08")
    source = read_symbol_library(text, library="Author")[0]
    found = embed_symbol(source, target=10)
    assert [pin.number for pin in found.definition.pins] == ["", "~", "2"]
