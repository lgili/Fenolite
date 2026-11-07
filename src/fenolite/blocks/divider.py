# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Unloaded resistive divider; S-1120, S-1121 and S-1124."""

from typing import Any

from fenolite.dsl import (
    Ground,
    Net,
    Rail,
    amp,
    at_least,
    between,
    block,
    param,
    rating_of,
    schematic_group,
    value_of,
    volt,
    voltage_of,
    within,
)
from fenolite.dsl import generators as gen
from fenolite.dsl.block import Block


@block(
    id="Fenolite:voltage_divider",
    version="1.0.0",
    summary="Resistive divider with a worst-case output range",
    category="analog",
    sources=("S-1120", "S-1121", "S-1124"),
)
def voltage_divider(
    b: Block,
    *,
    vin: Any = param(volt(12).pct(2), doc="Input HI against LO used to choose resistors", unit="volt"),
    vout: Any = param(volt("3.3").pct(5), doc="Accepted unloaded output range", unit="volt"),
    current: Any = param(
        between(amp("50u"), amp("200u")), doc="Divider current window at nominal input", unit="ampere"
    ),
    series: Any = param("E96", choices=("E24", "E96"), doc="Resistor series"),
) -> None:
    hi = b.port("HI", Rail, direction="in", doc="Input rail; its actual voltage is judged")
    out = b.port("OUT", Net, direction="out", doc="Unloaded divided output")
    lo = b.port("LO", Ground, direction="in", doc="Input and output reference")
    b.layout(reuse="layouts/voltage_divider.toml", copper=True)
    b.defaults(resistor={"case": "0603"})
    top, bot = gen.voltage_divider(
        b, hi, out, lo, target=vout, vin=vin, current=current, series=series, name="divider"
    )
    b.schematic(schematic_group("divider", top, bot, title="Divider", flow="top-to-bottom"))
    b.expect(within(voltage_of(hi) / (1 + value_of(top) / value_of(bot)), vout), "output in range")
    b.expect(
        at_least(rating_of(top, "power"), voltage_of(hi) * voltage_of(hi) / value_of(top)),
        "top power upper bound",
    )
    b.expect(
        at_least(rating_of(bot, "power"), voltage_of(hi) * voltage_of(hi) / value_of(bot)),
        "bottom power upper bound",
    )


__all__ = ["voltage_divider"]
