# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Fenolite's own power symbols (capability kicad-schematic, "Power symbols on a generated sheet"; change
c0406). Hermetic: the symbols are built and read in memory."""

from __future__ import annotations

import pytest

from fenolite.backends.kicad import symembed
from fenolite.backends.kicad.sexpr import dumps


@pytest.mark.parametrize("target", symembed.TARGET_MAJORS)
@pytest.mark.parametrize(("kind", "name"), [("ground", "GND"), ("rail", "RAIL")])
def test_power_symbol(kind: str, name: str, target: int) -> None:
    found = symembed.power_symbol(kind, target)
    assert found.name == name and symembed.is_power_symbol(found.lib_id)
    (pin,) = found.definition.pins
    assert pin.etype == "power_in" and pin.hidden and pin.length == 0
    assert (pin.position.x, pin.position.y) == (0, 0)
    assert found.definition.graphics  # a drawn glyph, authored for Fenolite
    text = dumps(found.node)
    assert "(power global)" in text if target >= 10 else "(power)" in text
    assert symembed.POWER_REFERENCE in text


@pytest.mark.parametrize(
    ("lib_id", "expected"),
    [
        ("fenolite:GND", True),
        ("Fenolite:RAIL", True),
        ("FENOLITE:GND", True),
        ("fenolite:PWR_FLAG", False),
        ("power:GND", False),
        ("fenolite:VCC", False),
    ],
)
def test_is_power_symbol(lib_id: str, expected: bool) -> None:
    assert symembed.is_power_symbol(lib_id) is expected


def test_unknown_kind_and_target() -> None:
    with pytest.raises(ValueError, match="unknown power symbol kind"):
        symembed.power_symbol("negative", 10)
    with pytest.raises(ValueError, match="unsupported target"):
        symembed.power_symbol("ground", 7)


def test_power_symbols_are_deterministic() -> None:
    assert dumps(symembed.power_symbol("rail", 10).node) == dumps(symembed.power_symbol("rail", 10).node)
