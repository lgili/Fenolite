# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Generic component bodies (capability altium-schematic-writer, "Generic component bodies"; change
c0032)."""

from __future__ import annotations

import pytest

from fenolite.backends.altium.symbols import GenericPin, generic_symbol, natural_key


def _same(*designators: str) -> list[tuple[str, str]]:
    return [(d, d) for d in designators]


def test_natural_order() -> None:
    symbol = generic_symbol(_same("10", "B", "2", "A1", "1"))
    assert [p.designator for p in symbol.pins] == ["1", "2", "10", "A1", "B"]
    assert [p.designator for p in symbol.pins if p.side == "left"] == ["1", "2", "10"]
    assert [p.designator for p in symbol.pins if p.side == "right"] == ["A1", "B"]
    assert [p.row for p in symbol.pins] == [0, 1, 2, 0, 1]


def test_natural_key() -> None:
    texts = ["10", "A10", "2", "B", "A2", "1", "A1", "GND", "PA5", "PA10"]
    assert sorted(texts, key=natural_key) == ["1", "2", "10", "A1", "A2", "A10", "B", "GND", "PA5", "PA10"]
    assert natural_key("A10") == ((1, "A"), (0, 10))


def test_four_pin_body() -> None:
    symbol = generic_symbol(_same("4", "3", "2", "1"))
    assert (symbol.width, symbol.height, symbol.rows) == (600, 300, 2)
    assert symbol.pins == (
        GenericPin("1", "1", "left", 0),
        GenericPin("2", "2", "left", 1),
        GenericPin("3", "3", "right", 0),
        GenericPin("4", "4", "right", 1),
    )


@pytest.mark.parametrize(("count", "height"), [(0, 200), (1, 200), (2, 200), (3, 300), (5, 400), (8, 500)])
def test_body_height(count: int, height: int) -> None:
    symbol = generic_symbol(_same(*(str(n) for n in range(1, count + 1))))
    assert symbol.height == height and symbol.width == 600


def test_part_without_pins() -> None:
    symbol = generic_symbol([])
    assert (symbol.pins, symbol.width, symbol.height) == ((), 600, 200)


def test_shown_names_widen_the_body() -> None:
    symbol = generic_symbol([("1", "VCC_LONG_NAME"), ("2", "2")])
    assert symbol.pins[0].name_shown and not symbol.pins[1].name_shown
    assert symbol.width == 2000  # 100 * ceil((100 + 2 * 70 * 13) / 100)


def test_pin_ends() -> None:
    symbol = generic_symbol(_same("1", "2", "3"))
    left, _, right = symbol.pins
    assert left.body_end(symbol.width) == (0, 100) and left.hot_end(symbol.width) == (-200, 100)
    assert right.body_end(symbol.width) == (600, 100) and right.hot_end(symbol.width) == (800, 100)


def test_repeated_designator() -> None:
    with pytest.raises(ValueError):
        generic_symbol(_same("1", "1"))
