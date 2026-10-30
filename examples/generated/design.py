# SPDX-License-Identifier: CC0-1.0
# Authored for Fenolite as an example; no file, value, name or layout comes from any other project.
"""Generated footprints (change c0260): one footprint of each package family, drawn from the records of
``packages/`` beside this script by ``Footprint.from_package``.

The nine records give the dimensions of a public package outline with its source id and, when the source
gives one, the manufacturer's land (``[land]``); otherwise the land calculator draws the pads from the
toleranced dimensions with Fenolite's authored constants ``lands/1`` (``docs/footprint-generators.md``).
Every footprint follows the drawing convention ``drawing/1``; the eight whose record gives a body height
(all but the TO-220, whose outline gives none) carry extruded bodies, so the build writes their STEP models
under ``lib/Local.3dshapes/`` beside ``lib/Local.pretty/``, and ``fenolite export step`` of the built board
finds them. The circuit is illustrative: a 5 V input, a linear
regulator in TO-220 and four controllers in SOIC-8, QFN-16, a 12-ball grid array and DIP-8, with a chip
resistor, a SOD-123 diode and two connectors.

Build it with ``fenolite build examples/generated/design.py --out build/generated --dry-run``, then
``--confirm --plan <plan_id>``. ``fenolite library generate examples/generated/packages/*.toml --out lib``
writes the same footprints, their models and ``lib/Local.PcbLib`` without a design.
"""

from pathlib import Path

from fenolite.dsl import Design, Footprint, Net, Part, connect, mm

PACKAGES = Path(__file__).resolve().parent / "packages"


def generated(record: str, **options: int) -> Footprint:
    """The footprint of ``packages/<record>.toml``, added to the design."""
    footprint = Footprint.from_package((PACKAGES / f"{record}.toml").read_text(encoding="utf-8"), **options)
    design.add_footprint(footprint)
    return footprint


design = Design("generated")
design.board(mm(80), mm(50))

chip = generated("chip0603")
sod = generated("sod123")
soic = generated("soic8")
qfn = generated("qfn16")
bga = generated("bga12")
to220 = generated("to220")
dip = generated("dip8")
header = generated("header1x2")
xh = generated("connector_xh", positions=3)

MCU = "Fenolite:Microcontroller"
j1 = Part("J1", "Fenolite:Connector_2", footprint=header.lib_id, value="5V IN")
d1 = Part("D1", "Fenolite:Diode", footprint=sod.lib_id, pad_map={"1": "2", "2": "1"})
q1 = Part("Q1", "Fenolite:Linear_Regulator", footprint=to220.lib_id, value="3V3")
r1 = Part("R1", "Fenolite:Resistor", footprint=chip.lib_id, value="10k")
u1 = Part("U1", MCU, footprint=soic.lib_id)
u2 = Part("U2", MCU, footprint=qfn.lib_id)
grid = {str(pin): ball for pin, ball in enumerate(("A1", "A2", "A3", "A4", "C1", "C2", "C3", "C4"), start=1)}
u3 = Part("U3", MCU, footprint=bga.lib_id, pad_map=grid)
u4 = Part("U4", MCU, footprint=dip.lib_id)
j2 = Part("J2", "Fenolite:Connector_3", footprint=xh.lib_id, value="UART")
design.add(j1, d1, q1, r1, u1, u2, u3, u4, j2)

vin, vbus, v33, gnd, rst, tx = (Net(n) for n in ("VIN", "VBUS", "V3V3", "GND", "RESET", "TX"))
connect(vin, j1[1], d1[1])
connect(vbus, d1[2], q1[1])
connect(gnd, j1[2], q1[2], u1[2], u2[2], u3[2], u4[2], j2[3])
connect(v33, q1[3], r1[1], u1[1], u2[1], u3[1], u4[1])
connect(rst, r1[2], u1[3], u2[3], u3[3], u4[3])
connect(tx, u1[8], j2[1])

j1.place(mm(6), mm(25), rot=90, locked=True)
d1.place(mm(14), mm(25))
q1.place(mm(24), mm(10))
r1.place(mm(24), mm(30))
u1.place(mm(36), mm(15))
u2.place(mm(36), mm(35))
u3.place(mm(50), mm(15))
u4.place(mm(52), mm(35), rot=90)
j2.place(mm(70), mm(25), rot=90)
