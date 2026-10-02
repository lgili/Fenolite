# SPDX-License-Identifier: CC0-1.0
# Authored for Fenolite as an example; no file, value, name or layout comes from any other project.
"""Altium target from KiCad symbols: a buffered signal path with a dual amplifier and a small controller.

Build it with ``fenolite build examples/altium_kicad/design.py --out build/altium_kicad --target altium
--confirm``. The lib ids are KiCad lib ids of ``FenoliteDemo.kicad_sym``, found through this folder's
``sym-lib-table``; the build writes their symbols, pins and units into ``altium_kicad.SchLib``. The
footprints name ``FenoliteDemo:<name>``, a library that is never opened. ``U1`` names no footprint, so it
takes its symbol's ``Footprint`` property.
"""

from fenolite.dsl import Design, Net, Part, Power, connect

LIB = "FenoliteDemo"

design = Design("altium_kicad")

j1 = Part("J1", f"{LIB}:CONN2", footprint=f"{LIB}:PinHeader_1x02", value="IN")
r1 = Part("R1", f"{LIB}:R_V", footprint=f"{LIB}:R0603", value="1k")
r2 = Part("R2", f"{LIB}:R_V", footprint=f"{LIB}:R0603", value="10k")
u1 = Part("U1", f"{LIB}:DUAL_OPAMP")
u2 = Part("U2", f"{LIB}:MCU8", footprint=f"{LIB}:SOIC8")
design.add(j1, r1, r2, u1, u2)

vin, gnd = Net("VIN"), Net("GND")
sig, fb_a, fb_b, oe_n = Net("SIG"), Net("FB_A"), Net("FB_B"), Net("OE_N")
connect(vin, j1[1], u1[8], u2[1], u2[6], r1[1])
connect(gnd, j1[2], u1[4], u2[7], r2[2])
connect(sig, r1[2], u1[3])
connect(fb_a, u1[1], u1[2], u1[5])
connect(fb_b, u1[6], u1[7], u2[3])
connect(oe_n, u2[5], r2[1])
design.add(Power(vin, gnd))
