# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Authored for Fenolite as test data; no file, value, name or layout comes from any other project.

The block sample of change c0269: one filter block used once, for the Altium target.

The block ``filt`` declares the ports ``IN`` (direction ``in``) and ``OUT`` (direction ``out``) of kind
``Net``. It is used as ``f1``, whose ``IN`` and ``OUT`` are joined to the nets ``SRC`` and ``DST``, each
with a pin of the connector ``J1`` on the top sheet. The net ``TEST`` joins a pin inside ``f1`` and a pin
of ``J2`` on the top sheet without a port, so it escapes the block. ``VCC`` and ``GND`` form a ``Power``
interface: their power ports stay global, so the port ``GND`` gives no sheet entry. Its symbols are catalog
symbols; its footprint links name the library ``FenoliteBlocks.PcbLib``, which Fenolite does not ship.
"""

from fenolite.dsl import Design, Net, Power, block, connect

LIB = "Fenolite"
PCBLIB = "FenoliteBlocks.PcbLib"
TEST = Net("TEST")

design = Design("blocks")


@block
def filt(b):
    inp = b.port("IN", direction="in")
    out = b.port("OUT", direction="out")
    gnd = b.port("GND", direction="in")
    r = b.part("R", f"{LIB}:Resistor", footprint=f"{PCBLIB}:R0603", value="1k")
    c = b.part("C", f"{LIB}:Capacitor", footprint=f"{PCBLIB}:C0603", value="10n")
    t = b.part("RT", f"{LIB}:Resistor", footprint=f"{PCBLIB}:R0603", value="10k")
    connect(inp, r[1])
    connect(out, r[2], c[1], t[1])
    connect(gnd, c[2])
    connect(TEST, t[2])


j1 = design.part("J1", f"{LIB}:Connector_4", footprint=f"{PCBLIB}:HDR1X4", value="IO")
j2 = design.part("J2", f"{LIB}:Connector_4", footprint=f"{PCBLIB}:HDR1X4", value="TP")
src, dst, vcc, gnd = Net("SRC"), Net("DST"), Net("VCC"), Net("GND")
f1 = design.use(filt, "f1")
connect(src, j1[1], f1.IN)
connect(dst, j1[2], f1.OUT)
connect(vcc, j1[3], j2[3])
connect(gnd, j1[4], f1.GND)
connect(TEST, j2[1])
connect(gnd, j2[2], j2[4])
design.add(Power(vcc, gnd))
