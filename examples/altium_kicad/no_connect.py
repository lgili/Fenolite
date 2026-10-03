# SPDX-License-Identifier: CC0-1.0
# Authored for Fenolite as an example; no file, value, name or layout comes from any other project.
"""Altium target with no-connect marks: a small controller whose unused pins are marked.

Build it with ``fenolite build examples/altium_kicad/no_connect.py --out build/altium_no_connect --target
altium --confirm``. ``no_connect`` marks ``U1`` pins 2 (an input), 4 (an output) and 8 (a passive pin) as
intentionally unconnected: each gets a No ERC directive at its electrical end and no wire. Pin 3, an
input, is left open and unmarked on purpose: Altium's compiler should report it and stay silent about the
marked pins (Part N of ``docs/evidence/altium-schematic.md``). The lib ids are KiCad lib ids of
``FenoliteDemo.kicad_sym``, found through this folder's ``sym-lib-table``.
"""

from fenolite.dsl import Design, Net, Part, Power, connect, no_connect

LIB = "FenoliteDemo"

design = Design("altium_no_connect")

j1 = Part("J1", f"{LIB}:CONN2", footprint=f"{LIB}:PinHeader_1x02", value="IN")
r1 = Part("R1", f"{LIB}:R_V", footprint=f"{LIB}:R0603", value="10k")
u1 = Part("U1", f"{LIB}:MCU8", footprint=f"{LIB}:SOIC8")
design.add(j1, r1, u1)

vin, gnd, oe_n = Net("VIN"), Net("GND"), Net("OE_N")
connect(vin, j1[1], u1[1], u1[6], r1[1])
connect(gnd, j1[2], u1[7])
connect(oe_n, r1[2], u1[5])
design.add(Power(vin, gnd))

no_connect(u1[2], u1[4], u1[8])
