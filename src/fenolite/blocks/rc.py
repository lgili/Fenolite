# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""First-order RC low-pass with an enclosed π; S-1122 and S-1124."""

from typing import Any

from fenolite.dsl import (
    Ground,
    Net,
    Quantity,
    at_least,
    block,
    capacitor,
    farad,
    hertz,
    param,
    pct,
    rating_of,
    schematic_group,
    value_of,
    volt,
    within,
)
from fenolite.dsl import generators as gen
from fenolite.dsl.block import Block


@block(
    id="Fenolite:rc_lowpass",
    version="1.0.0",
    summary="RC low-pass with a worst-case cut-off range",
    category="analog",
    sources=("S-1122", "S-1124"),
)
def rc_lowpass(
    b: Block,
    *,
    corner: Any = param(hertz("1k").pct(20), doc="Accepted cut-off range", unit="hertz"),
    c: Quantity | None = param(farad("100n"), doc="Fixed capacitance; None lets the generator choose"),
    c_tolerance: Any = param(10, min=0, max=100, doc="Required symmetric capacitor tolerance in percent"),
    series: Any = param("E96", choices=("E24", "E96"), doc="Resistor series"),
    voltage: Any = param(
        volt(5), doc="Highest normal voltage across the capacitor", unit="volt", min=volt(0)
    ),
) -> None:
    inp = b.port("IN", Net, direction="in", doc="Filter input")
    out = b.port("OUT", Net, direction="out", doc="Unloaded filter output")
    gnd = b.port("GND", Ground, direction="in", doc="Capacitor return")
    b.layout(reuse="layouts/rc_lowpass.toml", copper=True)
    b.defaults(
        resistor={"case": "0603", "series": series},
        capacitor={"case": "0603", "tolerance": pct(c_tolerance), "rating": voltage},
    )
    fixed = None if c is None else capacitor(c)
    r, cap = gen.rc_lowpass(b, inp, out, gnd, corner=corner, c=fixed, name="filter")
    b.schematic(schematic_group("filter", r, cap, title="RC low-pass"))
    b.expect(within(1 / (2 * gen.PI * value_of(r) * value_of(cap)), corner), "cut-off in range")
    b.expect(at_least(rating_of(cap, "voltage"), voltage), "capacitor voltage rating")


__all__ = ["rc_lowpass"]
