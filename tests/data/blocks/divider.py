# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
# Authored for Fenolite as test data (change c0268); no file, value or name comes from any other project.
"""A block with a record: a resistive divider with documented ports and parameters."""

from fenolite.dsl import Rail, block, connect, param
from fenolite.dsl.quantity import amp, volt

__all__ = ["divider"]

VOUT = volt("3.3").pct(5)  # the target output range; chosen for the test


@block(
    id="Acme:divider",
    version="1.0.0",
    summary="Resistive divider with a worst-case output range",
    category="analog",
    licence="CC0-1.0",
    sources=("authored for the Fenolite tests",),
)
def divider(
    b,
    *,
    vout=param(VOUT, doc="target output range", unit="volt"),
    current=param(amp("100u"), doc="bias current at nominal input", min=amp("1u"), max=amp("10m")),
    series=param("E96", choices=("E24", "E96"), doc="resistor series"),
):
    hi = b.port("HI", Rail, direction="in", doc="input")
    out = b.port("OUT", Rail, direction="out", doc="divided output")
    lo = b.port("LO", Rail, direction="in", doc="reference, usually ground")
    top = b.part("top", "Fenolite:Resistor", footprint="Fenolite:Chip_0603", prefix="R", value="10k")
    bot = b.part("bot", "Fenolite:Resistor", footprint="Fenolite:Chip_0603", prefix="R", value="3k3")
    connect(hi.hv, top[1])
    connect(out.hv, top[2], bot[1])
    connect(lo.hv, bot[2])
