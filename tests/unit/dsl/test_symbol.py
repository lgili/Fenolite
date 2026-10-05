# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Project-authored symbol DSL."""

import pytest

from fenolite.dsl import Design, DslError, Symbol, mm


def test_symbol_is_attached_explicitly_and_produces_model_definition() -> None:
    design = Design("symbols")
    symbol = Symbol("Local", "TwoPin", reference="J", value="TwoPin", footprint="Local:Header")
    symbol.pin("1", "A", at=(mm(-2.54), mm(0)), length=mm(2.54), rotation=180, etype="input")
    symbol.pin("2", "B", at=(mm(2.54), mm(0)), length=mm(2.54), etype="output")
    design.add(symbol)
    assert symbol.definition.lib_id == "Local:TwoPin"
    assert [pin.number for pin in symbol.definition.pins] == ["1", "2"]
    assert design.symbols == {"Local:TwoPin": symbol}
    with pytest.raises(DslError, match="registered twice"):
        design.add(Symbol("Local", "TwoPin", reference="J"))


def test_symbol_rejects_invalid_pin_declarations() -> None:
    symbol = Symbol("Local", "Bad", reference="U")
    with pytest.raises(DslError, match="rotation"):
        symbol.pin("1", "A", at=(mm(0), mm(0)), length=mm(1), rotation=45)
    with pytest.raises(DslError, match="positive"):
        symbol.pin("1", "A", at=(mm(0), mm(0)), length=mm(0))


def test_symbol_graphics_are_exposed_as_ordered_model_geometry() -> None:
    symbol = Symbol("Local", "Resistor", reference="R")
    symbol.pin("1", "A", at=(mm(-5), mm(0)), length=mm(2.5), rotation=180)
    symbol.pin("2", "B", at=(mm(5), mm(0)), length=mm(2.5))
    symbol.rect((mm(-2.5), mm(-1.25)), (mm(2.5), mm(1.25)), width=mm(0.25))
    symbol.circle((mm(0), mm(0)), (mm(1), mm(0)), filled=True)

    assert [graphic.kind for graphic in symbol.definition.graphics] == ["rect", "circle"]
    assert symbol.definition.graphics[0].points[0].x == -2_500_000
    assert symbol.definition.graphics[1].filled

    with pytest.raises(DslError, match="same horizontal axis"):
        symbol.circle((mm(0), mm(0)), (mm(0), mm(1)))
