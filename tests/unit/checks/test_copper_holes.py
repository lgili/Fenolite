# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Drilled holes against cut-outs, slots and other holes (capability copper-check, "Drilled holes against
cut-outs and holes"; change c0169), and against copper (``copper.hole-clearance``, change c0403). Every
board is authored here or is the shared slot fixture of change c0167 with items added."""

from __future__ import annotations

import dataclasses
import math
import runpy
from pathlib import Path

from _coppercheck import Copper, disc_entry, mm
from _outlinehelp import build_script

from fenolite import dsl
from fenolite.backends.base import BoardPad, EdgeRing
from fenolite.backends.kicad.backend import KicadBackend
from fenolite.checks.copper import HOLE_CLEARANCE, HOLE_IN_CUTOUT, HOLE_OVERLAP, check_copper
from fenolite.core.coords import Point
from fenolite.model.board import Hole
from fenolite.model.rules import Selector

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


# --- copper against holes (change c0403) -----------------------------------------------------------------

CENTRE = Point(mm(10), mm(10))
"""The centre of the 3 mm unplated hole of ``MH1``: its wall is 1.5 mm from it."""


def _npth(made: Copper) -> None:
    """The mounting hole ``MH1``: an unplated pad of no copper with a 3 mm drill at ``CENTRE``."""
    made.pad("MH1", "", None, kind="np_thru_hole", layers=("*.Cu", "*.Mask"))
    made.pads[-1] = dataclasses.replace(made.pads[-1], position=CENTRE, hole=(CENTRE,), drill=mm(3))


def _track_at(made: Copper, gap: float, *, net: str = "SIG", width: float = 0.2) -> None:
    """A track of ``net`` along x whose copper edge is ``gap`` mm above the hole wall of ``MH1``."""
    y = mm(10 + 1.5 + gap + width / 2)
    made.track(net, Point(mm(5), y), Point(mm(15), y), width=mm(width))


def test_track_across_an_unplated_hole() -> None:
    made = Copper()
    _npth(made)
    made.track("SIG", Point(mm(5), mm(10)), Point(mm(15), mm(10)))
    report = check_copper(made.build(), pads=made.pads, min_hole_clearance=mm(0.25))
    (found,) = codes(report, HOLE_CLEARANCE)
    assert (found.severity, found.gap, found.clearance, found.source) == ("error", 0, mm(0.25), "floor")
    assert [(item.kind, item.where) for item in found.items][1] == ("pad", "MH1")
    assert found.items[0].kind == "track" and found.layer == "F.Cu"
    assert "is 0 mm from the drill of pad MH1" in found.message
    assert report.summary["hole_clearance"] == 1
    assert check_copper(made.build(), pads=made.pads, min_hole_clearance=None).findings == ()


def test_gap_to_the_hole_wall() -> None:
    near, far = Copper(), Copper()
    for made, gap in ((near, 0.1), (far, 0.3)):
        _npth(made)
        _track_at(made, gap)
    (found,) = codes(check_copper(near.build(), pads=near.pads, min_hole_clearance=mm(0.25)), HOLE_CLEARANCE)
    assert found.gap == mm(0.1) and found.at == Point(mm(10), mm(10.85))  # between the two cores
    assert check_copper(far.build(), pads=far.pads, min_hole_clearance=mm(0.25)).findings == ()
    assert check_copper(near.build(), pads=near.pads, min_hole_clearance=0).findings == ()


def test_own_net_and_own_pad_are_left_out() -> None:
    """A plated pad's hole: its own copper and copper of its net are not judged; a track of another net
    across the pad is a short, which KiCad reports instead of a hole clearance (one violation a pair)."""
    made = Copper()
    lands = (disc_entry(mm(10), mm(10), mm(5)), disc_entry(mm(10), mm(10), mm(5), "B.Cu"))
    made.pad("J1", "1", "GND", *lands, kind="thru_hole", layers=("*.Cu",))
    made.pads[-1] = dataclasses.replace(made.pads[-1], hole=(CENTRE,), drill=mm(3))
    made.track("GND", Point(mm(5), mm(10)), Point(mm(15), mm(10)))
    report = check_copper(made.build(), pads=made.pads, min_hole_clearance=mm(0.25))
    assert report.findings == ()
    made.track("SIG", Point(mm(10), mm(5)), Point(mm(10), mm(15)), layer="B.Cu")
    report = check_copper(made.build(), pads=made.pads, min_hole_clearance=mm(0.25))
    (short,) = report.findings
    assert short.code == "copper.short" and {item.where for item in short.items} >= {"J1-1"}


def test_hole_clearance_rule_governs() -> None:
    """A ``hole_clearance`` rule replaces the board minimum, below it too (``H-K-PRO-MIN-RULE-3``), and
    one of severity ``ignore`` silences the pair."""
    made = Copper()
    _npth(made)
    _track_at(made, 0.1)
    made.rule("tight", mm(0.05), kind="hole_clearance")
    assert check_copper(made.build(), pads=made.pads, min_hole_clearance=mm(0.25)).findings == ()
    wide = Copper()
    _npth(wide)
    _track_at(wide, 0.3)
    wide.rule("wide", mm(0.5), Selector("net", "SIG"), kind="hole_clearance", severity="warning")
    (found,) = check_copper(wide.build(), pads=wide.pads, min_hole_clearance=mm(0.25)).findings
    assert (found.code, found.severity, found.source) == (HOLE_CLEARANCE, "warning", "rule:wide")
    quiet = Copper()
    _npth(quiet)
    _track_at(quiet, 0.1)
    quiet.rule("quiet", mm(1), kind="hole_clearance", severity="ignore")
    assert check_copper(quiet.build(), pads=quiet.pads, min_hole_clearance=mm(0.25)).findings == ()


def test_via_drill_only_on_its_span() -> None:
    made = Copper(layers=4)
    made.via("V", CENTRE, diameter=mm(0.6), layers=("F.Cu", "In1.Cu"), via_type="blind")
    made.track("SIG", Point(mm(5), mm(10)), Point(mm(15), mm(10)), layer="B.Cu")
    report = check_copper(made.build(), pads=made.pads, min_hole_clearance=mm(0.25))
    assert report.findings == ()  # B.Cu is below the blind via's span
    made.track("SIG", Point(mm(5), mm(10.35)), Point(mm(15), mm(10.35)), width=mm(0.2), layer="In1.Cu")
    report = check_copper(made.build(), pads=made.pads, min_hole_clearance=mm(0.25))
    assert codes(report, HOLE_CLEARANCE) == []  # the track touches the via's copper: a short
    assert [f.code for f in report.findings] == ["copper.short"]


def test_hole_clearance_takes_the_tool_tolerance() -> None:
    """Change c0420, N4: the hole clearance takes the tolerance the pair clearance takes (change c0281), so
    a gap of the floor less 5 nm, the rounding an imported fill holds, is no finding with KiCad's 500 nm;
    without a tolerance, and 501 nm below the floor, it is one."""
    floor = mm(0.25)
    for short, tolerance, expected in ((5, 500, 0), (500, 500, 0), (501, 500, 1), (5, 0, 1)):
        made = Copper()
        _npth(made)
        y = mm(10) + mm(1.5) + floor - short + mm(0.1)
        made.track("SIG", Point(mm(5), y), Point(mm(15), y), width=mm(0.2))
        report = check_copper(made.build(), pads=made.pads, min_hole_clearance=floor, tolerance=tolerance)
        assert len(codes(report, HOLE_CLEARANCE)) == expected, (short, tolerance)


# --- the net of an unplated pad (change c0491) -------------------------------------------------------------


def _same_net_board(pad_net: str | None, via_net: str) -> Copper:
    """Scenario boards of "Copper against drilled holes": the unplated pad ``MH1`` of ``pad_net``, a ``GND``
    zone fill whose edge is 0.1 mm from the wall and a via of ``via_net`` 0.1 mm from the wall."""
    made = Copper()
    _npth(made)
    made.net("GND")
    made.pads[-1] = dataclasses.replace(made.pads[-1], net_id=made.net(pad_net))
    edge = mm(10 + 1.5 + 0.1)
    fill = (Point(mm(2), edge), Point(mm(18), edge), Point(mm(18), mm(18)), Point(mm(2), mm(18)))
    made.zone("GND", fill, fills=(fill,), clearance=0)
    made.via(via_net, Point(mm(10 - 1.5 - 0.1 - 0.3), mm(10)), diameter=mm(0.6))
    return made


def _hole_findings(made: Copper) -> list[tuple[str, str]]:
    report = check_copper(made.build(), pads=made.pads, min_hole_clearance=mm(0.25))
    return sorted((found.items[0].kind, found.items[0].net) for found in codes(report, HOLE_CLEARANCE))


def test_copper_of_the_net_of_an_unplated_pad() -> None:
    """Scenario "Copper of the net of an unplated pad": no finding for the pad's own net; a via of
    another net is one."""
    assert _hole_findings(_same_net_board("GND", "GND")) == []
    assert _hole_findings(_same_net_board("GND", "N1")) == [("via", "N1")]


def test_an_unplated_pad_without_a_net() -> None:
    """Scenario "An unplated pad without a net": all copper near it is judged, as before."""
    assert _hole_findings(_same_net_board(None, "GND")) == [("fill", "GND"), ("via", "GND")]


def test_the_kicad_view_judges_the_pads_own_net() -> None:
    """KiCad's DRC judges copper of an unplated pad's own net (``H-G-HOLE-SAME-NET``): with
    ``hole_clearance_same_net`` the verdict is the one of a pad without a net."""
    made = _same_net_board("GND", "GND")
    report = check_copper(
        made.build(), pads=made.pads, min_hole_clearance=mm(0.25), hole_clearance_same_net=True
    )
    found = sorted((f.items[0].kind, f.items[0].net) for f in codes(report, HOLE_CLEARANCE))
    assert found == [("fill", "GND"), ("via", "GND")]
