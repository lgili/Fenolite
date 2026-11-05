# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""An authored placed board for c0370's combined router-family proof (``tests/kicad/routing``).

``SIG`` (``R1-1`` to ``R2-1``, sensitive) and ``SECOND`` (``R3-1`` to ``R4-1``) cross, so that only a
negotiated bundle closes both; ``EXTRA`` (``R5-1`` to ``R6-1``) is left for a second pass. A ground zone on
the reference layer (``B.Cu`` on two layers, ``In1.Cu`` on four) gives the role-aware search its saved
reference field. Coordinates are millimetres in the frame of ``place()``.
"""

from dataclasses import replace
from pathlib import Path

from _search_project import bench, cli

BODY = """
from fenolite.dsl import Design, Net, Part, connect, mm

design=Design("families")
design.board(mm(24),mm(20),copper={layers})
parts=[Part(f"R{{i}}","Fenolite:Resistor",footprint="Fenolite:Chip_0603",value="1k") for i in range(1,7)]
design.add(*parts)
sig,second,extra,gnd=Net("SIG"),Net("SECOND"),Net("EXTRA"),Net("GND")
connect(sig,parts[0][1],parts[1][1])
connect(second,parts[2][1],parts[3][1])
connect(extra,parts[4][1],parts[5][1])
design.rules.netclass("SIGNAL",clearance=mm("0.2"),track_width=mm("0.25"),
                      via_diameter=mm("0.6"),via_drill=mm("0.3"),nets=(sig,second,extra))
for part,(x,y) in zip(parts,((4,10),(20,10),(12,4),(12,16),(4,18),(20,18))):
    part.place(mm(x),mm(y),rot=90)
design.zone(gnd,layers=("{reference}",),outline=((mm(1),mm(1)),(mm(23),mm(1)),
            (mm(23),mm(19)),(mm(1),mm(19))),clearance=mm("0.2"),islands="never")
design.net_role(sig,"signal",sensitive=True)
design.net_role(second,"signal")
design.net_role(gnd,"ground")
"""


def project(folder: Path, *, layers: int = 2, major: int = 10):
    reference = "B.Cu" if layers == 2 else "In1.Cu"
    built = bench(folder, "families", BODY.format(layers=layers, reference=reference))
    if major != 10:
        out = folder / "oracle"
        code, _, err = cli(
            "build",
            str(folder / "families.py"),
            "--out",
            str(out),
            "--kicad-version",
            str(major),
            "--confirm",
        )
        assert code == 0, err
        built = replace(built, out=out, board=out / built.board.name)
        from _roleboards import fill_as_outline

        built.board.write_text(fill_as_outline(built.board.read_text()))
    return built
