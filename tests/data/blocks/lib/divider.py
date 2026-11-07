# SPDX-License-Identifier: CC0-1.0
# Copyright (c) 2026 Fenolite contributors
# Authored for Fenolite as test data (change c0270).
"""A small resistive divider with an expectation depending on the outside input."""

from fenolite.dsl import Ground, Net, block, connect, mm, ohm, volt, voltage_of, within

__all__ = ["divider"]


@block(
    id="Test:divider",
    version="1.0.0",
    summary="Authored three-port resistive divider",
    category="analog",
    licence="CC0-1.0",
    sources=("authored for Fenolite",),
)
def divider(b, *, bottom="10000"):
    hi = b.port("HI", Net, direction="in")
    out = b.port("OUT", Net, direction="out")
    lo = b.port("LO", Ground)
    top = b.part("top", "Fenolite:Resistor", footprint="Fenolite:Chip_0603", value="20000", prefix="R")
    bot = b.part("bot", "Fenolite:Resistor", footprint="Fenolite:Chip_0603", value=bottom, prefix="R")
    connect(hi, top[1])
    connect(out, top[2], bot[1])
    connect(lo, bot[2])
    top.place(mm(10), mm(10))
    bot.place(mm(20), mm(10))
    b.expect(
        within(voltage_of(hi) * (ohm(bottom).value / (ohm(20000).value + ohm(bottom).value)), volt(4).pct(5)),
        "the divided input lies in its target window",
    )
