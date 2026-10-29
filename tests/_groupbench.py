# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The group-move bench of change c0227: an authored module, ``U1`` (``IC6`` of ``tests/_reusebench.py``)
at (20, 20) mm with four satellites joined to it by tracks, built with ``tests/_ties.py``. No file is read,
nothing comes from a library, and every value is a round invented one.

``C1`` lies at (20, 15) mm and ``C2`` at (26, 22) mm on the top, joined by tracks on ``F.Cu`` from
``U1-1`` and ``U1-4``; ``C3`` at (20, 26) mm and ``C4`` at (14, 18) mm lie on the bottom, joined from
``U1-3`` and ``U1-2`` by a track on ``F.Cu``, a via and a track on ``B.Cu``. With ``outside`` the part
``R9`` at (34, 10) mm is joined to ``C1-2`` by a track that leaves the group. The board is 60 mm by 40 mm,
its outline from (0, 0); the clearance is 0.2 mm.
"""

from __future__ import annotations

import dataclasses

from _groundties import _p, _via
from _reusebench import CHIP, CLEARANCE, DEFINITIONS, IC6, QUARTER
from _ties import TieBoard

from fenolite.backends.kicad.replace import footprint_ref, move_footprint
from fenolite.model.board import Track
from fenolite.model.design import Design

GROUP = ("U1", "C1", "C2", "C3", "C4")
NETS = {
    "U1": {"1": "A", "2": "B", "3": "D", "4": "C"},
    "C1": {"1": "A", "2": "E"},
    "C2": {"1": "C"},
    "C3": {"1": "D"},
    "C4": {"2": "B"},
}
BOTTOM_TRACKS = (("d-bottom", "D", (18, 23), (19, 26)), ("b-bottom", "B", (16, 20), (15, 18)))


def module(*, outside: bool = False) -> Design:
    """The module board, with ``R9`` joined to ``C1-2`` when ``outside``."""
    board = TieBoard(clearance=CLEARANCE)
    board.place("U1", IC6, _p(20, 20), nets=NETS["U1"])
    board.place("C1", CHIP, _p(20, 15), nets=NETS["C1"])
    board.place("C2", CHIP, _p(26, 22), nets=NETS["C2"])
    board.place("C3", CHIP, _p(20, 26), nets=NETS["C3"])
    board.place("C4", CHIP, _p(14, 18), nets=NETS["C4"])
    if outside:
        board.place("R9", CHIP, _p(34, 10), nets={"1": "E"})
    board.track("a", "A", _p(18, 19), _p(19, 15))
    board.track("c", "C", _p(22, 21), _p(25, 22))
    board.track("d", "D", _p(18, 21), _p(18, 23))
    board.track("b", "B", _p(18, 20), _p(16, 20))
    if outside:
        board.track("e", "E", _p(21, 15), _p(33, 10))
    design = board.build()
    assert design.board is not None
    for ref in ("C3", "C4"):
        fp = next(fp for fp in design.board.footprints if footprint_ref(design, fp) == ref)
        design = move_footprint(design, fp.id, side="bottom", definitions=DEFINITIONS)
        assert design.board is not None
    nets = {net.name: net.id for net in design.circuit.nets}
    width = design.board.tracks[0].width
    bottom = tuple(
        Track(
            id=f"trk_00000000-0000-4000-8000-0000000009{n:02d}",
            start=_p(*start),
            end=_p(*end),
            width=width,
            layer="B.Cu",
            net_id=nets[net],
        )
        for n, (_, net, start, end) in enumerate(BOTTOM_TRACKS)
    )
    vias = (_via(21, nets["D"], _p(18, 23)), _via(22, nets["B"], _p(16, 20)))
    return dataclasses.replace(
        design,
        board=dataclasses.replace(design.board, tracks=(*design.board.tracks, *bottom), vias=vias),
    )


__all__ = ["BOTTOM_TRACKS", "GROUP", "NETS", "QUARTER", "module"]
