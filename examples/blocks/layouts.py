# SPDX-License-Identifier: CC0-1.0
# Copyright (c) 2026 Fenolite contributors
# Authored for Fenolite; no third-party circuit or data.
"""Bench for capturing the authored divider with every port bound (c0271)."""

from fenolite.dsl import Design, Footprint, block, connect, mm


@block(id="Test:divider", version="1.0.0", summary="Authored resistive divider", licence="CC0-1.0")
def divider(b, *, value="10k", footprint="Fenolite:Chip_0603"):
    hi, out, lo = b.port("HI", optional=True), b.port("OUT", optional=True), b.port("LO", optional=True)
    top = b.part("top", "Fenolite:Resistor", footprint=footprint, prefix="R", value=value)
    bot = b.part("bot", "Fenolite:Resistor", footprint=footprint, prefix="R", value="3k3")
    connect(hi, top[1])
    connect(out, top[2], bot[1])
    connect(lo, bot[2])
    b.layout(reuse="layouts/divider.toml", copper=True)


design = Design("block_layouts")
design.board(mm(40), mm(25))
# Chosen bench dimensions; this is a fresh authored definition, not a library land pattern.
chip = Footprint("Fenolite", "Chip_0603", kind="smd")
chip.pad("1", at=(mm("0.8"), mm(0)), size=(mm("0.6"), mm("0.8")))
chip.pad("2", at=(mm("-0.8"), mm(0)), size=(mm("0.6"), mm("0.8")))
chip.rect((mm("-1.2"), mm("-0.5")), (mm("1.2"), mm("0.5")), layer="F.CrtYd", width=mm("0.05"))
design.add_footprint(chip)
sense_a = design.use(divider, "sense_a")
sense_a.place(mm(10), mm(8))
sense_b = design.use(divider, "sense_b")
sense_b.place(mm(25), mm(8), side="bottom")
