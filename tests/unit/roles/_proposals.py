# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The authored benches of the proposal tests (change c0280), built like the reference boards of the net
roles.

The subject bench: a two-layer board of 40 mm by 30 mm with one open connection of each kind the board can
show: ``SIG`` (``R1-1`` to ``R2-1``, no copper: a ``connection``), ``GND`` (the SMD pad ``R3-2`` on ``F.Cu``
with the ground zone on ``B.Cu`` and the through-hole pad ``J1-2`` on it: a ``fanout``), ``PWR`` (``R5-1``
outside the pour ``role.power.PWR.F.Cu`` that holds ``R4-1``: a ``join``) and ``VS`` (a ``power`` net
without a current, ``R6-1`` to ``R7-1``: a ``role-net``). The wall bench: ``R8-1`` of ``WALLED`` inside a ring
of ``FENCE`` on both copper layers (joined by the through-hole pads of ``J9``), so that its connection to
``R9-1`` has no room. Coordinates are millimetres in the frame of ``place()``; the board frame adds 100 mm on
each axis.
"""

from __future__ import annotations

from pathlib import Path

from _critical import bench
from _roleboards import Built

SUBJECTS = """
from fenolite.dsl import Design, Net, Part, amp, connect, mm

design = Design("{name}")
design.board(mm(40), mm(30))
parts = {{}}
for ref, value in (("R1", "1k"), ("R2", "1k"), ("R3", "1k"), ("R4", "1k"), ("R5", "1k"), ("R6", "1k"),
                   ("R7", "1k")):
    parts[ref] = Part(ref, "Fenolite:Resistor", footprint="Fenolite:Chip_0603", value=value)
j1 = Part("J1", "Fenolite:Connector_2", footprint="Roles:Roles_Terminal_2P", value="IN")
design.add(*parts.values(), j1)
r1, r2, r3, r4, r5, r6, r7 = (parts[f"R{{n}}"] for n in range(1, 8))
sig, gnd, pwr, vs = Net("SIG"), Net("GND"), Net("PWR"), Net("VS")
connect(sig, r1[1], r2[1])
connect(gnd, r3[2], j1[2])
connect(pwr, r4[1], r5[1])
connect(vs, r6[1], r7[1])
design.net_role(gnd, "ground", current=amp(2))
design.net_role(pwr, "power", current=amp(2))
design.net_role(vs, "power")
design.rules.netclass("SIGNAL", clearance=mm("0.2"), track_width=mm("0.25"), via_diameter=mm("0.6"),
                      via_drill=mm("0.3"), nets=(sig, gnd, pwr, vs))
r1.place(mm(6), mm(6), rot=90)
r2.place(mm(16), mm(6), rot=90)
r3.place(mm(6), mm(15))
j1.place(mm(30), mm(20))
r4.place(mm(25), mm(5))
r5.place(mm(34), mm(5))
r6.place(mm(6), mm(24), rot=180)
r7.place(mm(14), mm(24))


def box(net, name, x0, y0, x1, y1, layer):
    ring = tuple((mm(str(x)), mm(str(y))) for x, y in ((x0, y0), (x1, y0), (x1, y1), (x0, y1)))
    design.zone(net, layers=(layer,), name=name, outline=ring, clearance=mm("0.3"), connection="solid")


box(gnd, "GND_PLANE", 2, 10, 38, 28, "B.Cu")
box(pwr, "role.power.PWR.F.Cu", 20, 2, 30, 9, "F.Cu")
{extra}
"""

WALL = """
from fenolite.dsl import Design, Net, Part, connect, mm

design = Design("{name}")
design.board(mm(40), mm(30))
r8 = Part("R8", "Fenolite:Resistor", footprint="Fenolite:Chip_0603", value="1k")
r9 = Part("R9", "Fenolite:Resistor", footprint="Fenolite:Chip_0603", value="1k")
j9 = Part("J9", "Fenolite:Connector_2", footprint="Roles:Roles_Terminal_2P", value="FENCE")
design.add(r8, r9, j9)
walled, fence = Net("WALLED"), Net("FENCE")
connect(walled, r8[1], r9[1])
connect(fence, j9[1], j9[2])
r8.place(mm(10), mm(15))
r9.place(mm(25), mm(15))
j9.place(mm(10), mm(25))  # its through-hole pads at (5, 25) and (15, 25) join the two rings
w = mm("0.25")


def p(x, y):
    return (mm(str(x)), mm(str(y)))


ring = (p(5.0, 12.0), p(15.0, 12.0), p(15.0, 25.0), p(5.0, 25.0), p(5.0, 12.0))
design.track("wall_top", *ring, width=w, net=fence)
design.track("wall_bottom", *ring, width=w, net=fence, layer="B.Cu")
"""


def subject_bench(tmp: Path, name: str = "subjects", extra: str = "") -> Built:
    """The subject bench built in ``tmp``."""
    return bench(tmp, name, SUBJECTS.format(name=name, extra=extra))


def wall_bench(tmp: Path, name: str = "walled") -> Built:
    """The wall bench built in ``tmp``."""
    return bench(tmp, name, WALL.format(name=name))
