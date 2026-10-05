# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Net names as KiCad stores and derives them (capability kicad-schematic, "Names of unconnected-pin
nets"; capability kicad-file-backend, "Net names in KiCad's stored form"; change c0061)."""

from __future__ import annotations

import pytest
from hypothesis import given
from hypothesis import strategies as st

from fenolite.backends.kicad import netnames
from fenolite.backends.kicad.netnames import (
    model_name,
    pin_text,
    stored_name,
    unconnected_name,
    unit_letter,
)


def test_named_and_unnamed_pins() -> None:
    named = unconnected_name("U1", unit=1, unit_count=1, pin_name="PA1", pad_number="2")
    unnamed = unconnected_name("U1", unit=1, unit_count=1, pin_name="", pad_number="16")
    assert (named, unnamed) == ("unconnected-(U1-PA1-Pad2)", "unconnected-(U1-Pad16)")


def test_unit_letter_only_with_a_name() -> None:
    named = unconnected_name("U2", unit=3, unit_count=3, pin_name="GND", pad_number="7")
    unnamed = unconnected_name("U2", unit=1, unit_count=3, pin_name="", pad_number="1")
    assert (named, unnamed) == ("unconnected-(U2C-GND-Pad7)", "unconnected-(U2-Pad1)")


def test_slash_and_blank_in_a_pin_name() -> None:
    assert pin_text("A/B") == "A{slash}B" and pin_text("X 1") == "X_1"
    assert "A{slash}B" in unconnected_name("U1", unit=1, unit_count=1, pin_name="A/B", pad_number="1")
    assert "X_1" in unconnected_name("U1", unit=1, unit_count=1, pin_name="X 1", pad_number="2")


def test_unit_letters() -> None:
    assert unit_letter(1, 1) == "" and unit_letter(1, 2) == "A" and unit_letter(26, 30) == "Z"
    with pytest.raises(ValueError, match="1 to 26"):
        unit_letter(27, 30)


def test_stored_form_of_a_slash() -> None:
    assert stored_name("mod/LED_A") == "mod{slash}LED_A"
    assert model_name("mod{slash}LED_A") == "mod/LED_A"
    assert stored_name("GND") == "GND" and model_name("/power/VCC") == "/power/VCC"


@given(st.text().filter(lambda text: "{slash}" not in text))
def test_stored_name_has_an_inverse(text: str) -> None:
    assert model_name(stored_name(text)) == text
    assert "/" not in stored_name(text)


def test_proved_characters() -> None:
    assert netnames.proved("PA1") and netnames.proved("") and netnames.proved("A/B 1")
    assert not netnames.proved("µC") and not netnames.proved("A(B)")
    assert {"A", "z", "0", " ", "/"} <= netnames.PROVED_PIN_CHARS
