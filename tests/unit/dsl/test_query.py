# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Part queries and their defaults in the DSL (change c0254; capability design-dsl, "Part queries in the
DSL", "Pins of query parts", "Query arguments", "Defaults in the DSL")."""

from __future__ import annotations

from fractions import Fraction

import pytest

from fenolite.core.partquery import PartQuery, Percent
from fenolite.dsl import (
    Design,
    DslError,
    Net,
    block,
    capacitor,
    connect,
    farad,
    henry,
    inductor,
    ohm,
    pct,
    resistor,
    volt,
    watt,
)


def test_a_query_part() -> None:
    design = Design("q")
    design.defaults(resistor={"case": "0603", "tolerance": pct(1)})
    r = design.part(device=resistor(ohm("10k")))
    assert r.query is not None and r.query.text() == "resistor(10kΩ, tolerance<=1%, case=0603)"
    assert r.device is None and r.lib_id == "Fenolite:Resistor" and r.path == "R"
    assert isinstance(r.query, PartQuery) and r.query.get("tolerance") == Percent(Fraction(-1), Fraction(1))


def test_pins_before_the_pick() -> None:
    design = Design("q")
    r = design.part(device=resistor(ohm("10k")))
    vin = Net("VIN")
    connect(vin, r[1])
    with pytest.raises(DslError, match=r"'3'") as caught:
        connect(vin, r[3])
    assert "pins 1 and 2" in str(caught.value)


def test_refused_queries() -> None:
    with pytest.raises(DslError, match="colour"):
        resistor(ohm("10k"), colour="red")
    with pytest.raises(DslError, match="farad"):
        capacitor(volt(5))
    with pytest.raises(DslError, match="tolerance"):
        resistor(ohm("10k").pct(5), tolerance=pct(1))
    with pytest.raises(DslError, match="not exact"):
        resistor(ohm("10k"), power=0.1)
    with pytest.raises(DslError, match="volt"):
        capacitor(farad("1u"), rating=watt(1))
    with pytest.raises(DslError, match="inch code"):
        resistor(ohm("1k"), case="1608M")


def test_spellings_give_one_text() -> None:
    first = capacitor(farad("10u"), rating=volt(25)).text()
    second = capacitor(farad("10 uF"), rating=volt("25.0")).text()
    assert first == second == "capacitor(10uF, rating>=25V)"
    assert inductor(henry("4u7"), dcr=ohm("50m")).text() == "inductor(4.7uH, dcr<=50mΩ)"
    assert capacitor(farad("1u"), dielectric=("X7R", "C0G")).text() == "capacitor(1uF, dielectric=C0G|X7R)"
    assert resistor(ohm("10k").pct(5)).text() == "resistor(10kΩ (9.5kΩ..10.5kΩ))"


def test_query_part_takes_no_footprint() -> None:
    design = Design("q")
    with pytest.raises(DslError, match="footprint"):
        design.part(device=resistor(ohm("1k")), footprint="Fenolite:Chip_0603")


def test_defaults_the_block_and_the_call_win_in_turn() -> None:
    design = Design("q")
    design.defaults(resistor={"case": "0603", "tolerance": pct(1)})
    seen: list[str] = []

    @block
    def inner(b):  # noqa: ANN001, ANN202
        b.defaults(resistor={"case": "0402"})
        part = b.part("R", device=resistor(ohm("10k"), tolerance=None))
        seen.append(part.query.text())

    design.use(inner, "blk")
    assert seen == ["resistor(10kΩ, case=0402)"]


def test_defaults_none_removes_and_later_calls_apply() -> None:
    design = Design("q")
    r = design.part(device=resistor(ohm("1k")))
    design.defaults(resistor={"power": watt("100m")})
    assert r.query is not None and r.query.text() == "resistor(1kΩ, power>=100mW)"
    design.defaults(resistor={"power": None})
    assert r.query.text() == "resistor(1kΩ)"


def test_defaults_unknown_kind() -> None:
    design = Design("q")
    with pytest.raises(DslError, match="diode") as caught:
        design.defaults(diode={"case": "0603"})
    assert "resistor, capacitor, inductor" in str(caught.value)
    with pytest.raises(DslError, match="colour"):
        design.defaults(resistor={"colour": "red"})
    with pytest.raises(DslError, match="volt"):
        design.defaults(capacitor={"rating": ohm(1)})


def test_a_range_value_ignores_a_default_tolerance() -> None:
    design = Design("q")
    design.defaults(resistor={"tolerance": pct(1)})
    r = design.part(device=resistor(ohm("10k").pct(5)))
    assert r.query is not None and r.query.get("tolerance") is None
