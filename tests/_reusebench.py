# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The layout-reuse bench of change c0210: an authored reference block and the boards it is copied onto,
built with ``tests/_ties.py``. No file is read, nothing comes from a library, and every value is a round
invented one.

The block is ``U1`` (``IC6``, six pads numbered counter-clockwise, so it is chiral) with ``R1`` to ``R4``
(``CHIP``, two pads 2 mm apart) around it. On the reference board ``U1`` lies at (20, 20) mm, ``R1`` at
(20, 15) mm, ``R2`` at (26, 20) mm turned by 90°, ``R3`` at (20, 25) mm and ``R4`` at (14, 20) mm turned
by 90° on the bottom. Each resistor's pad 1 is on its own net to a pad of ``U1``; every pad 2, ``U1-3``
and ``U1-6`` are on ``GND``. Copper: ``in`` joins ``U1-1`` to ``R1-1``; ``out`` joins ``U1-4`` to
``R2-1``; ``tail`` runs on from ``R2-1`` to the test pad ``TP1`` at (32, 21) mm, which is not in the
block; ``down`` leads from ``R3-2`` to the via ``v1``, which joins nothing on ``B.Cu``. Tracks are 0.25 mm
wide on ``F.Cu``; the clearance is 0.2 mm.

On the target board the same parts lie in a row along y 35 mm, and ``U1`` at (42, 18) mm turned by 90°.
"""

from __future__ import annotations

import dataclasses
from collections.abc import Mapping

from _groundties import _p, _via
from _ties import MM, TieBoard

from fenolite.backends.base import BoardPad
from fenolite.backends.kicad.frame import board_pads
from fenolite.backends.kicad.libs import LibRow, LibTable, write_lib_table
from fenolite.backends.kicad.mod import prepare_authored_definition, write_pretty
from fenolite.backends.kicad.pcb import write_board
from fenolite.backends.kicad.pro import synthesize_project
from fenolite.backends.kicad.replace import footprint_ref, move_footprint
from fenolite.core.coords import Point
from fenolite.dsl import Footprint, nm
from fenolite.model.board import FootprintInstance, Zone, ZoneFill, ZoneSettings
from fenolite.model.design import Design
from fenolite.model.library import FootprintDef
from fenolite.reuse import Layout

LIBRARY = "Reuse"
CLEARANCE = MM // 5
QUARTER = 90_000_000


def _footprint(
    name: str, pads: Mapping[str, tuple[float, float]], size: tuple[float, float], box: float
) -> FootprintDef:
    footprint = Footprint(LIBRARY, name, kind="smd")
    for number, (x, y) in pads.items():
        footprint.pad(
            number,
            at=(nm(round(x * MM)), nm(round(y * MM))),
            size=(nm(round(size[0] * MM)), nm(round(size[1] * MM))),
        )
    half_w, half_h = box, box * 2 / 3 if name != "TP" else box
    footprint.rect(
        (nm(round(-half_w * MM)), nm(round(-half_h * MM))),
        (nm(round(half_w * MM)), nm(round(half_h * MM))),
        layer="F.CrtYd",
        width=nm(MM // 20),
    )
    return footprint.definition


IC6 = _footprint(
    "IC6",
    {"1": (-2, -1), "2": (-2, 0), "3": (-2, 1), "4": (2, 1), "5": (2, 0), "6": (2, -1)},
    (1.2, 0.6),
    3,
)
"""Six pads, 1 to 3 down the left column and 4 to 6 up the right one: no turn maps it on its mirror."""
CHIP = _footprint("CHIP", {"1": (-1, 0), "2": (1, 0)}, (1, 1.2), 1.8)
WIDE = _footprint("WIDE", {"1": (-1.5, 0), "2": (1.5, 0)}, (1, 1.2), 2.4)
"""A chip of another pitch: it fits no ``CHIP``."""
TP = _footprint("TP", {"1": (0, 0)}, (1.5, 1.5), 1)
DEFINITIONS: dict[str, FootprintDef] = {
    defn.lib_id: prepare_authored_definition(defn) for defn in (IC6, CHIP, WIDE, TP)
}
"""The library definitions by lib id, for turns and side changes."""

NETS = {
    "U1": {"1": "IN", "2": "FB", "3": "GND", "4": "OUT", "5": "EN", "6": "GND"},
    "R1": {"1": "IN", "2": "GND"},
    "R2": {"1": "OUT", "2": "GND"},
    "R3": {"1": "FB", "2": "GND"},
    "R4": {"1": "EN", "2": "GND"},
}


def _turned(design: Design, placements: Mapping[str, tuple[int, str]]) -> Design:
    """``design`` with the parts of ``placements`` turned to an angle and put on a side."""
    assert design.board is not None
    for ref, (rotation, side) in placements.items():
        fp = next(fp for fp in design.board.footprints if footprint_ref(design, fp) == ref)
        design = move_footprint(
            design,
            fp.id,
            rotation=rotation,
            side=side,
            definitions=DEFINITIONS,  # type: ignore[arg-type]
        )
        assert design.board is not None
    return design


def reference(*, copper: bool = True) -> Design:
    """The reference board of the block, with its copper and ``TP1``."""
    board = TieBoard(clearance=CLEARANCE)
    board.place("U1", IC6, _p(20, 20), nets=NETS["U1"])
    board.place("R1", CHIP, _p(20, 15), nets=NETS["R1"])
    board.place("R2", CHIP, _p(26, 20), nets=NETS["R2"])
    board.place("R3", CHIP, _p(20, 25), nets=NETS["R3"])
    board.place("R4", CHIP, _p(14, 20), nets=NETS["R4"])
    board.place("TP1", TP, _p(32, 21), nets={"1": "OUT"})
    if copper:
        board.track("in", "IN", _p(18, 19), _p(19, 15))
        board.track("out", "OUT", _p(22, 21), _p(26, 21))
        board.track("tail", "OUT", _p(26, 21), _p(32, 21))
        board.track("down", "GND", _p(21, 25), _p(21, 28))
    design = board.build()
    design = _turned(design, {"R2": (QUARTER, "top"), "R4": (QUARTER, "bottom")})
    if copper:
        assert design.board is not None
        via = _via(1, board.net("GND"), _p(21, 28))
        design = dataclasses.replace(design, board=dataclasses.replace(design.board, vias=(via,)))
    return design


def target(
    *,
    r3: FootprintDef = CHIP,
    anchor_side: str = "top",
    locked_anchor: bool = False,
    intruder: bool = False,
    across: bool = False,
) -> Design:
    """The target board: the block's parts in a row along y 35 mm, ``U1`` at (42, 18) mm turned by 90°
    on ``anchor_side``. ``r3`` is the footprint of ``R3``. ``intruder`` adds the test pad ``X1`` of net
    ``OTHER`` at (39, 20.2) mm, across the place of the copy of ``in``; ``across`` a track of ``OTHER``
    from (35, 19) mm to (36.5, 19) mm, under the place of ``R1-1``."""
    board = TieBoard(clearance=CLEARANCE)
    board.place("U1", IC6, _p(42, 18), nets=NETS["U1"])
    board.place("R1", CHIP, _p(6, 35), nets=NETS["R1"])
    board.place("R2", CHIP, _p(12, 35), nets=NETS["R2"])
    board.place("R3", r3, _p(18, 35), nets=NETS["R3"])
    board.place("R4", CHIP, _p(24, 35), nets=NETS["R4"])
    if intruder:
        board.place("X1", TP, _p(39, 20.2), nets={"1": "OTHER"})
    if across:
        board.track("across", "OTHER", _p(35, 19), _p(36.5, 19))
    design = _turned(board.build(), {"U1": (QUARTER, anchor_side)})
    if locked_anchor:
        assert design.board is not None
        design = dataclasses.replace(
            design,
            board=dataclasses.replace(
                design.board,
                footprints=tuple(
                    dataclasses.replace(fp, locked=True) if footprint_ref(design, fp) == "U1" else fp
                    for fp in design.board.footprints
                ),
            ),
        )
    return design


POUR = (_p(20.5, 14.5), _p(26.5, 14.5), _p(26.5, 19.5), _p(25.5, 19.5), _p(25.5, 15.5), _p(20.5, 15.5))
"""An L of ``GND`` on the reference board that joins ``R1-2`` and ``R2-2`` (change c0227)."""
PLANE = (_p(25.5, 20.6), _p(32.8, 20.6), _p(32.8, 21.4), _p(25.5, 21.4))
"""A strip of ``OUT`` that joins ``R2-1`` and the test pad ``TP1``, which is not in the block."""


SOLID = ZoneSettings(connection="solid")
"""Pads joined to a pour in full: a stored fill that covers a pad has no thermal spokes to count."""


def with_zones(design: Design, *, outline: bool = True) -> Design:
    """The reference ``design`` with two filled zones on ``F.Cu``: ``pour`` (``POUR``, without its outline
    when ``outline`` is false, as a reader that keeps an outline opaque gives it) and ``plane``
    (``PLANE``)."""
    assert design.board is not None
    nets = {net.name: net.id for net in design.circuit.nets}
    zones = (
        Zone(
            id="zon_00000000-0000-4000-8000-000000000001",
            outline=POUR if outline else (),
            name="pour",
            layers=("F.Cu",),
            net_id=nets["GND"],
            fills=(ZoneFill("F.Cu", POUR),),
            filled=True,
            settings=SOLID,
        ),
        Zone(
            id="zon_00000000-0000-4000-8000-000000000002",
            outline=PLANE,
            name="plane",
            layers=("F.Cu",),
            net_id=nets["OUT"],
            fills=(ZoneFill("F.Cu", PLANE),),
            filled=True,
            settings=SOLID,
        ),
    )
    return dataclasses.replace(design, board=dataclasses.replace(design.board, zones=zones))


def layout(design: Design) -> Layout:
    return Layout(design, board_pads(design))


def _mirror(point: Point) -> Point:
    return Point(point.x, -point.y)


def _pad(record: BoardPad) -> BoardPad:
    copper = tuple(
        dataclasses.replace(
            entry,
            core=tuple(_mirror(p) for p in (reversed(entry.core) if entry.filled else entry.core)),
        )
        for entry in record.copper
    )
    return dataclasses.replace(
        record,
        position=_mirror(record.position),
        copper=copper,
        hole=tuple(_mirror(p) for p in record.hole),
    )


def y_up(drawn: Layout) -> Layout:
    """``drawn`` as a reader that keeps a Y-up frame gives it: every point with its y negated, every side
    as it was. The pads, the footprints' positions and the copper are mirrored."""
    board = drawn.design.board
    assert board is not None
    footprints: tuple[FootprintInstance, ...] = tuple(
        dataclasses.replace(fp, position=_mirror(fp.position)) for fp in board.footprints
    )
    mirrored = dataclasses.replace(
        board,
        footprints=footprints,
        tracks=tuple(
            dataclasses.replace(t, start=_mirror(t.start), end=_mirror(t.end)) for t in board.tracks
        ),
        vias=tuple(dataclasses.replace(v, position=_mirror(v.position)) for v in board.vias),
    )
    return Layout(
        dataclasses.replace(drawn.design, board=mirrored), tuple(_pad(record) for record in drawn.pads)
    )


def project_files(target_design: Design, *, name: str = "target", major: int = 10) -> dict[str, str]:
    """The files of a target project for KiCad ``major``: the board, its project (with the bench's
    clearance), the authored library ``Reuse.pretty`` and an ``fp-lib-table`` that names it."""
    files = {
        f"{name}.kicad_pcb": write_board(target_design, target=major).text,
        f"{name}.kicad_pro": synthesize_project(target_design, target=major, board_name=name),
        "fp-lib-table": write_lib_table(
            LibTable("footprint", (LibRow(LIBRARY, "KiCad", f"${{KIPRJMOD}}/{LIBRARY}.pretty"),)),
            target=major,
        ),
    }
    for file, text in write_pretty(DEFINITIONS.values(), target=major).items():
        files[f"{LIBRARY}.pretty/{file}"] = text
    return files


__all__ = [
    "CHIP",
    "CLEARANCE",
    "DEFINITIONS",
    "IC6",
    "LIBRARY",
    "NETS",
    "PLANE",
    "POUR",
    "TP",
    "WIDE",
    "layout",
    "project_files",
    "reference",
    "target",
    "with_zones",
    "y_up",
]
