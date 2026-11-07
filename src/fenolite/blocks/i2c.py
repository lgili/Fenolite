# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""I2C pull-ups from the shared S-0941 (UM10204) limits."""

from typing import Any

from fenolite.dsl import (
    I2C,
    Rail,
    at_least,
    at_most,
    between,
    block,
    farad,
    param,
    schematic_group,
    value_of,
    volt,
    voltage_of,
    within,
)
from fenolite.dsl import generators as gen
from fenolite.dsl.block import Block


@block(
    id="Fenolite:i2c_pullups",
    version="1.0.0",
    summary="I2C pull-ups selected for sink current and rise time",
    category="interface",
    sources=("S-0941", "S-1124"),
)
def i2c_pullups(
    b: Block,
    *,
    mode: Any = param("standard", choices=("standard", "fast", "fast-plus"), doc="UM10204 speed mode"),
    vdd: Any = param(
        volt("3.3").pct(5), doc="Rail range used to choose resistors; must exceed 2 V", unit="volt"
    ),
    bus_capacitance: Any = param(
        between(farad("10p"), farad("200p")), doc="Bus capacitance window", unit="farad"
    ),
    series: Any = param("E24", choices=("E24", "E96"), doc="Resistor series"),
) -> None:
    rail = b.port("RAIL", Rail, direction="in", doc="Bus reference and pull-up supply")
    bus = b.port(
        "BUS", I2C, direction="inout", reference=rail, doc="SDA and SCL, with one pull-up set per bus"
    )
    b.layout(reuse="layouts/i2c_pullups.toml", copper=True)
    b.defaults(resistor={"case": "0603", "series": series})
    sda, scl = gen.i2c_pull_ups(b, bus, rail, bus_capacitance=bus_capacitance, vdd=vdd, mode=mode, name="r")
    vol, iol, maximum = gen.i2c_mode_limits(mode, bus_capacitance)
    for resistor in (sda, scl):
        b.expect(
            at_least(value_of(resistor), (voltage_of(rail) - vol) / iol),
            f"{resistor.key}: pull-up not below the bus minimum",
        )
        b.expect(
            at_most(value_of(resistor), maximum), f"{resistor.key}: pull-up not above the rise-time maximum"
        )
    b.expect(within(voltage_of(rail), vdd), "supply within selection range")
    b.schematic(schematic_group("pullups", sda, scl, title="I2C pull-ups", flow="top-to-bottom"))


__all__ = ["i2c_pullups"]
