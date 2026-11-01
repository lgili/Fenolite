# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Generator calls in the DSL (change c0254; design-dsl, "Generators in the DSL", "Generator arguments")."""

from __future__ import annotations

import pytest

from fenolite.dsl import Design, DslError, Net, amp, between, block, connect, volt, voltage_divider


def test_divider_parts_and_nets() -> None:
    design = Design("g")
    made: list[object] = []

    @block
    def buck(b):  # noqa: ANN001, ANN202
        out, gnd, fb = b.port("VOUT"), b.port("GND"), b.net("FB")
        made.extend(
            voltage_divider(
                b,
                out,
                fb,
                gnd,
                target=volt("3.3").pct(5),
                ref=volt("0.6").pct(1),
                current=between(amp("40u"), amp("100u")),
            )  # fmt: skip
        )

    inst = design.use(buck, "buck1")
    vout, gnd = Net("VOUT"), Net("GND")
    connect(vout, inst.VOUT)
    connect(gnd, inst.GND)
    top, bot = design.parts["buck1/FB_top"], design.parts["buck1/FB_bot"]
    assert made == [top, bot]
    assert top.connections["2"].name == "buck1/FB" and bot.connections["1"].name == "buck1/FB"
    for part in (top, bot):
        query = part.query
        assert query is not None and query.generator is not None
        assert query.generator.name == "voltage_divider" and query.generator.group == "buck1/FB"
    assert top.query.text().endswith("role=top)") and bot.query.text().endswith("role=bot)")  # type: ignore[union-attr]


def test_the_search_window_must_be_stated() -> None:
    design = Design("g")
    with pytest.raises(DslError, match="current must be a range"):
        voltage_divider(
            design,
            Net("O"),
            Net("F"),
            Net("G"),
            target=volt("3.3").pct(5),
            ref=volt("0.6").pct(1),
            current=amp("50u"),
        )


def test_generator_arguments() -> None:
    design = Design("g")
    with pytest.raises(DslError, match="ref= .* or vin="):
        voltage_divider(design, Net("O"), Net("F"), Net("G"), target=volt("3.3").pct(5),
                        current=between(amp("40u"), amp("100u")))  # fmt: skip
    voltage_divider(design, Net("O"), Net("F"), Net("G"), target=volt("3.3").pct(5), ref=volt("0.6"),
                    current=between(amp("40u"), amp("100u")))  # fmt: skip
    with pytest.raises(DslError, match="already used"):
        voltage_divider(design, Net("O"), Net("F"), Net("G"), target=volt("3.3").pct(5), ref=volt("0.6"),
                        current=between(amp("40u"), amp("100u")))  # fmt: skip
