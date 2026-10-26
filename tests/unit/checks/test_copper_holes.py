# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Drilled holes against cut-outs, slots and other holes (capability copper-check, "Drilled holes against
cut-outs and holes"; change c0169). Every board is authored here or is the shared slot fixture of change
c0167 with items added."""

from __future__ import annotations

import dataclasses
import math
import runpy
from pathlib import Path

from _coppercheck import Copper, mm
from _outlinehelp import build_script

from fenolite import dsl
from fenolite.backends.base import BoardPad, EdgeRing
from fenolite.backends.kicad.backend import KicadBackend
from fenolite.checks.copper import HOLE_IN_CUTOUT, HOLE_OVERLAP, check_copper
from fenolite.core.coords import Point
from fenolite.model.board import Hole

SLOTS = Path(__file__).resolve().parents[2] / "data" / "slots"
BOARD = EdgeRing("board", (Point(0, 0), Point(mm(50), 0), Point(mm(50), mm(30)), Point(0, mm(30))))
CUTOUT = EdgeRing(
    "cut-out 1", (Point(mm(20), mm(10)), Point(mm(30), mm(10)), Point(mm(30), mm(20)), Point(mm(20), mm(20)))
)


def codes(report, code: str):  # noqa: ANN001, ANN201
    return [f for f in report.findings if f.code == code]


def built(design: dsl.Design):  # noqa: ANN201
    """``check_copper`` of the built model of ``design`` with the KiCad frame's pads and edges."""
    model = build_script(design, 10, copper_intents=dsl.copper(design)).design
    frame = KicadBackend()
    return check_copper(model, pads=frame.board_pads(model), edges=frame.board_edges(model))


def test_via_drilled_into_a_slot() -> None:
    design = runpy.run_path(str(SLOTS / "design.py"))["design"]
    assert isinstance(design, dsl.Design)
    s1 = next(s for s in dsl.to_model(design).board.outline.slots if s.name == "S1")  # type: ignore[union-attr]
    turn = math.radians(s1.rotation / 1_000_000)
    # on the long side of S1, opposite its middle: the drill of 0.3 mm crosses the edge line
    x = s1.center.x / 1e6 - 100 + math.sin(turn) * 1
    y = s1.center.y / 1e6 - 100 + math.cos(turn) * 1
    net = dsl.Net("VIA")
    design.add(net)
    design.via(
        "v1", dsl.mm(round(x, 6)), dsl.mm(round(y, 6)), net=net, diameter=dsl.mm(0.6), drill=dsl.mm(0.3)
    )
    report = built(design)
    (found,) = codes(report, HOLE_IN_CUTOUT)
    assert found.severity == "error" and found.items[0].kind == "via"
    assert found.items[1].where == "slot S1" and "breaks into slot S1" in found.message
    assert report.summary["hole_in_cutout"] == 1 and codes(report, HOLE_OVERLAP) == []


def test_two_drilled_slots_in_an_ell() -> None:
    design = dsl.Design("drilledell")
    design.board(dsl.mm(40), dsl.mm(30))
    design.hole("H1", dsl.mm(15), dsl.mm(10), drill=dsl.mm(2), length=dsl.mm(12))
    design.hole("H2", dsl.mm(20), dsl.mm(15), drill=dsl.mm(2), length=dsl.mm(12), rot=90)
    report = built(design)
    (found,) = codes(report, HOLE_OVERLAP)
    assert found.severity == "warning"
    assert {item.where for item in found.items} == {"H1", "H2"}  # unnumbered pads are named by their part
    assert all(item.kind == "pad" for item in found.items)
    assert codes(report, HOLE_IN_CUTOUT) == []


def _pad_hole(ref: str, at: Point, drill: int, *, ends: tuple[Point, ...] = ()) -> BoardPad:
    return BoardPad(
        footprint_id=f"fpi_{ref}",
        ref=ref,
        path=ref,
        pad_id=f"pad_{ref}",
        number="",
        kind="np_thru_hole",
        position=at,
        rotation=0,
        side="top",
        layers=("*.Cu",),
        net_id=None,
        net=None,
        hole=ends or (at,),
        drill=drill,
    )


def test_holes_against_the_rings() -> None:
    made = Copper()
    made.via("A", Point(mm(0.1), mm(5)), diameter=mm(0.6))  # its drill of 0.3 mm crosses the left side
    made.via("B", Point(mm(25), mm(15)), diameter=mm(0.6))  # wholly inside the cut-out
    made.via("C", Point(mm(19.85), mm(15)), diameter=mm(0.6))  # its drill only touches the cut-out
    made.via("D", Point(mm(60), mm(15)), diameter=mm(0.6))  # wholly outside the board: not crossing
    design = made.build()
    hole = Hole(id="hol_1", position=Point(mm(30), mm(12)), drill=mm(1))  # on the cut-out's right side
    assert design.board is not None
    design = dataclasses.replace(design, board=dataclasses.replace(design.board, holes=(hole,)))
    report = check_copper(design, pads=made.pads, edges=(BOARD, CUTOUT))
    found = {(f.items[0].kind, f.items[0].net, f.items[1].where) for f in codes(report, HOLE_IN_CUTOUT)}
    assert found == {("via", "A", "board"), ("via", "B", "cut-out 1"), ("hole", "<no net>", "cut-out 1")}
    crossing = next(f for f in codes(report, HOLE_IN_CUTOUT) if f.items[1].where == "board")
    assert "crosses the board edge" in crossing.message
    # without edges no hole is judged against a ring
    assert codes(check_copper(design, pads=made.pads), HOLE_IN_CUTOUT) == []


def test_hole_overlap_copies_and_touching() -> None:
    pads = [
        _pad_hole("H1", Point(mm(10), mm(10)), mm(2)),
        _pad_hole("H2", Point(mm(11), mm(10)), mm(2)),  # overlaps H1
        _pad_hole("H3", Point(mm(10), mm(10)), mm(2)),  # a copy of H1: not reported against H1
        _pad_hole("H4", Point(mm(14), mm(10)), mm(2)),  # touches H2 only
        _pad_hole("H5", Point(mm(20), mm(20)), mm(1), ends=(Point(mm(20), mm(20)), Point(mm(24), mm(20)))),
        _pad_hole("H6", Point(mm(24), mm(21)), mm(1.2)),  # overlaps the slot H5 at its end
    ]
    report = check_copper(Copper().build(), pads=pads)
    found = sorted(tuple(sorted(i.where for i in f.items)) for f in codes(report, HOLE_OVERLAP))
    assert found == [("H1", "H2"), ("H2", "H3"), ("H5", "H6")]
    assert all(f.severity == "warning" for f in codes(report, HOLE_OVERLAP))
    assert report.summary["holes"] == 6 and report.summary["hole_overlap"] == 3
