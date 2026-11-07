# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""An authored placed board for c0370's reviewed-stage workflow proofs (``tests/kicad/routing``).

Two open connections, ``SIG`` (``R1-1`` to ``R2-1``) and ``SECOND`` (``R3-1`` to ``R4-1``), a right-angle
bend that joins ``R5-1`` and ``R6-1`` on ``MANUAL`` and a locked track on ``BLOCK``. ``by_hand`` gives the
bend the plain uuids of copper drawn in KiCad, so that it is manual copper, which an unscoped chamfer
would cut (copper that the design writes carries the copper marker and is never tidied). Coordinates are
millimetres in the frame of ``place()``.
"""

import re
from dataclasses import replace
from pathlib import Path

from _search_project import bench, cli

from fenolite.backends.kicad.pcb import read_board

BODY = """
from fenolite.dsl import Design, Net, Part, connect, mm

design=Design("completion")
design.board(mm(30),mm(20),copper={layers})
parts=[Part(f"R{{i}}","Fenolite:Resistor",footprint="Fenolite:Chip_0603",value="1k") for i in range(1,7)]
design.add(*parts)
sig,second,manual,block=Net("SIG"),Net("SECOND"),Net("MANUAL"),Net("BLOCK")
connect(sig,parts[0][1],parts[1][1])
connect(second,parts[2][1],parts[3][1])
connect(manual,parts[4][1],parts[5][1])
design.add(block)
design.rules.netclass("SIGNAL",clearance=mm("0.2"),track_width=mm("0.25"),
                      via_diameter=mm("0.6"),via_drill=mm("0.3"),nets=(sig,second,manual,block))
for part,(x,y) in zip(parts,((4,5),(26,5),(4,12),(26,12))):
    part.place(mm(x),mm(y),rot=90)
parts[4].place(mm(4),mm(17),rot=180)
parts[5].place(mm(12),mm(15),rot=90)
design.net_role(sig,"signal")
design.net_role(second,"signal")
design.track("manual_bend",(mm("4.8"),mm(17)),(mm(12),mm(17)),(mm(12),mm("15.8")),width=mm("0.25"),
             net=manual)
design.track("locked_bar",(mm(21),mm(17)),(mm(27),mm(17)),width=mm("0.25"),net=block,locked=True)
"""


def project(folder: Path, *, layers: int = 2, major: int = 10):
    built = bench(folder, "completion", BODY.format(layers=layers))
    if major != 10:
        out = folder / "oracle"
        code, _, err = cli(
            "build",
            str(folder / "completion.py"),
            "--out",
            str(out),
            "--kicad-version",
            str(major),
            "--confirm",
        )
        assert code == 0, err
        built = replace(built, out=out, board=out / built.board.name)
    return built


HAND_UUIDS = ("0f1e2d3c-4b5a-4978-8a6b-5c4d3e2f1a0b", "1a2b3c4d-5e6f-4a7b-9c8d-7e6f5a4b3c2d")
"""Version-4 uuids without the copper marker, authored for the two tracks of the bend."""


def by_hand(board: Path) -> None:
    """Give the tracks of ``MANUAL`` the uuids of copper drawn in KiCad (only those bytes change)."""
    text = board.read_text(encoding="utf-8")
    design = read_board(text, file=board.name)
    assert design.board is not None
    ids = {net.id: net.name for net in design.circuit.nets}
    marked = sorted(t.native_ids["kicad"] for t in design.board.tracks if ids.get(t.net_id) == "MANUAL")
    assert len(marked) == len(HAND_UUIDS), marked
    for old, new in zip(marked, HAND_UUIDS, strict=True):
        text, count = re.subn(rf'\(uuid "{old}"\)', f'(uuid "{new}")', text)
        assert count == 1, old
    board.write_text(text, encoding="utf-8")
