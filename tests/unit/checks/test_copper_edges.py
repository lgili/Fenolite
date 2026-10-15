# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Copper to board edge clearance (capability copper-check, "Copper to board edge clearance"; capability
copper-rule-explanation, "Edge clearance explanation"; change c0169). Every board is authored here or is
the shared slot fixture of change c0167 with parts added."""

from __future__ import annotations

import math
import runpy
from pathlib import Path

import pytest
from _coppercheck import Copper, mm
from _outlinehelp import build_script

from fenolite import dsl
from fenolite.backends.base import EdgeRing, PadCopper
from fenolite.backends.kicad.backend import KicadBackend
from fenolite.checks.clearance import ClearanceCandidate, ClearanceResolver, EdgeClearanceExplanation
from fenolite.checks.copper import EDGE_CODE, check_copper, copper_stage, frame_edges, group_findings
from fenolite.core.coords import Point
from fenolite.core.evidence import Evidence
from fenolite.model.board import OutlineSlot
from fenolite.model.rules import Selector

SLOTS = Path(__file__).resolve().parents[2] / "data" / "slots"
BOARD = EdgeRing("board", (Point(0, 0), Point(mm(50), 0), Point(mm(50), mm(30)), Point(0, mm(30))))
"""A 50 × 30 mm board ring at the origin."""


def edge_findings(report):  # noqa: ANN001, ANN201
    return [f for f in report.findings if f.code == EDGE_CODE]


# --- a pad near a slot ------------------------------------------------------------------------------------


def slot_part(gap: float) -> tuple[dsl.Design, OutlineSlot]:
    """The shared fixture with a plated hole part ``P1`` of 2 mm copper whose copper lies ``gap`` mm from
    the long side of slot ``S1`` (turned 30°), opposite the middle of that side."""
    design = runpy.run_path(str(SLOTS / "design.py"))["design"]
    assert isinstance(design, dsl.Design)
    s1 = next(s for s in dsl.to_model(design).board.outline.slots if s.name == "S1")  # type: ignore[union-attr]
    turn = math.radians(s1.rotation / 1_000_000)
    # the slot's axis runs along (cos, −sin) in the board frame, whose y points down; this is its normal
    nx, ny = math.sin(turn), math.cos(turn)
    reach = s1.width / 2 / 1e6 + 1 + gap
    x = s1.center.x / 1e6 - 100 + nx * reach
    y = s1.center.y / 1e6 - 100 + ny * reach
    design.hole("P1", dsl.mm(round(x, 6)), dsl.mm(round(y, 6)), drill=dsl.mm(1), pad=dsl.mm(2))
    return design, s1


def slot_report(gap: float):  # noqa: ANN201
    """``check_copper`` on the built model of ``slot_part(gap)`` (the build places the part), with a board
    minimum of 0.5 mm."""
    design, _ = slot_part(gap)
    model = build_script(design, 10).design
    frame = KicadBackend()
    edges = frame.board_edges(model)
    return check_copper(model, pads=frame.board_pads(model), edges=edges, min_edge_clearance=mm(0.5))


def test_slot_pad_too_close() -> None:
    (found,) = edge_findings(slot_report(0.47))
    assert found.severity == "error" and found.clearance == mm(0.5) and found.source == "floor"
    assert abs(found.gap - mm(0.47)) <= 2  # the part's place is rounded to the nanometre
    assert found.items[0].kind == "pad" and found.items[0].where == "P1-1"
    assert found.items[1].kind == "edge" and found.items[1].where == "slot S1"
    assert found.where == "P1-1, slot S1" and found.relation == "edge"
    assert "slot S1" in found.message and "0.5 mm (floor)" in found.message
    assert "from the board edge" in found.message
    assert isinstance(found.explanation, EdgeClearanceExplanation)
    assert found.explanation.ring == "slot S1"


def test_slot_pad_clear() -> None:
    report = slot_report(0.52)
    assert edge_findings(report) == []
    rings = report.summary["edges"]["rings"]
    assert rings[:3] == ["board", "cut-out 1", "slot S1"]
    # merged with the geo extra, else left as two rings
    assert rings[3:] in (["slot S2 + slot S3"], ["slot S2", "slot S3"])


# --- a rule for one net -----------------------------------------------------------------------------------


def hv_gnd(*, severity: str = "error") -> Copper:
    """Tracks of ``HV`` and ``GND`` 0.8 mm (copper edge) from the board ring's lower side, and a rule of
    1 mm for ``HV``."""
    made = Copper()
    width = mm(0.25)
    y = mm(30) - mm(0.8) - width // 2
    made.track("HV", Point(mm(5), y), Point(mm(20), y), width=width, locator="hv")
    made.track("GND", Point(mm(25), y), Point(mm(45), y), width=width, locator="gnd")
    made.rule("hv_edge", mm(1), Selector("net", "HV"), kind="edge_clearance", severity=severity)  # type: ignore[arg-type]
    return made


def test_rule_for_one_net() -> None:
    made = hv_gnd()
    report = check_copper(made.build(), pads=made.pads, edges=(BOARD,), min_edge_clearance=mm(0.5))
    (found,) = edge_findings(report)
    assert found.items[0].net == "HV" and found.items[1].where == "board"
    assert found.gap == mm(0.8) and found.clearance == mm(1) and found.source == "rule:hv_edge"
    explained = found.explanation
    assert isinstance(explained, EdgeClearanceExplanation)
    assert explained.governing.source == "rule:hv_edge"
    assert [row.source for row in explained.candidates] == ["rule:hv_edge", "floor"]
    assert explained.candidates[1] == ClearanceCandidate("floor", mm(0.5), "error")


def test_rule_over_the_board_minimum_resolves_again() -> None:
    made = hv_gnd()
    design = made.build()
    (found,) = edge_findings(check_copper(design, pads=made.pads, edges=(BOARD,), min_edge_clearance=mm(0.5)))
    explained = found.explanation
    assert isinstance(explained, EdgeClearanceExplanation)
    # resolving the explained inputs gives the finding's limit
    resolver = ClearanceResolver(
        design, min_edge_clearance=mm(0.5), edge_floor_over_rules=explained.edge_floor_over_rules
    )
    assert resolver.edge(explained.subject) == explained.governing
    assert explained.governing.value == mm(1) == found.clearance
    assert isinstance(hash(found), int)


def test_rule_severity_and_ignore() -> None:
    made = hv_gnd(severity="warning")
    (found,) = edge_findings(check_copper(made.build(), pads=made.pads, edges=(BOARD,)))
    assert found.severity == "warning"
    quiet = hv_gnd(severity="ignore")
    report = check_copper(quiet.build(), pads=quiet.pads, edges=(BOARD,), min_edge_clearance=mm(1))
    assert [f.items[0].net for f in edge_findings(report)] == ["GND"]


def test_no_edges_judges_nothing() -> None:
    made = hv_gnd()
    report = check_copper(made.build(), pads=made.pads, min_edge_clearance=mm(2))
    assert edge_findings(report) == [] and report.summary["edges"]["rings"] is None


# --- kinds, rings and counting ----------------------------------------------------------------------------


def test_every_kind_against_every_ring() -> None:
    made = Copper()
    hole = EdgeRing("cut-out 1", (Point(mm(20), mm(10)), Point(mm(30), mm(10)), Point(mm(30), mm(20))))
    round_hole = EdgeRing(
        "cut-out 2",
        (Point(mm(40), mm(5)), Point(mm(40), mm(9))),
        (Point(mm(42), mm(7)), Point(mm(38), mm(7))),
    )
    made.via("A", Point(mm(1), mm(15)), diameter=mm(0.6))  # copper 0.7 mm from the left side
    made.track("B", Point(mm(31), mm(15)), Point(mm(31), mm(25)), width=mm(0.2))  # 0.9 mm from the cut-out
    made.pad("U1", "1", "C", PadCopper("F.Cu", (Point(mm(43), mm(7)),), mm(1)))  # 0.5 mm from the circle
    made.arc("D", Point(mm(10), mm(29)), Point(mm(15), mm(28)), Point(mm(20), mm(29)), width=mm(0.2))
    fill = (Point(mm(5), mm(0.6)), Point(mm(15), mm(0.6)), Point(mm(15), mm(8)))
    made.zone("E", fill, fills=(fill,))  # 0.6 mm from the upper side
    report = check_copper(
        made.build(), pads=made.pads, edges=(BOARD, hole, round_hole), min_edge_clearance=mm(1)
    )
    found = {(f.items[0].kind, f.items[1].where): f for f in edge_findings(report)}
    assert set(found) == {
        ("via", "board"),
        ("track", "cut-out 1"),
        ("pad", "cut-out 2"),
        ("arc", "board"),
        ("fill", "board"),
    }
    assert found[("via", "board")].gap == mm(0.7)
    assert found[("track", "cut-out 1")].gap == mm(0.9)
    # the circle is polygonised and widened by its band: the gap is a lower bound within it
    assert mm(0.5) - 1_001 <= found[("pad", "cut-out 2")].gap <= mm(0.5)
    assert found[("arc", "board")].gap <= mm(0.9)
    assert found[("fill", "board")].gap == mm(0.6)
    # the via spans both layers and is reported once, on the first
    assert found[("via", "board")].layer == "F.Cu"
    assert report.summary["edge_clearance"] == 5
    groups = [group for group in group_findings(report) if group.findings[0].code == EDGE_CODE]
    assert groups and all(group.relation == "edge" for group in groups)


def test_copper_outside_or_inside_a_cutout_far_from_its_edge() -> None:
    made = Copper()
    made.track("A", Point(mm(60), mm(10)), Point(mm(70), mm(10)))  # wholly outside, 10 mm away
    made.track("B", Point(mm(-0.3), mm(10)), Point(mm(0.3), mm(10)))  # across the left side
    report = check_copper(made.build(), pads=made.pads, edges=(BOARD,), min_edge_clearance=mm(0.5))
    ((found),) = edge_findings(report)
    assert found.items[0].net == "B" and found.gap == 0


def test_one_finding_per_item_and_ring() -> None:
    made = Copper()
    # a track along the lower left corner: close to two sides of the one ring
    made.track("A", Point(mm(0.2), mm(5)), Point(mm(0.2), mm(29.8)))
    made.track("A", Point(mm(0.2), mm(29.8)), Point(mm(10), mm(29.8)))
    report = check_copper(made.build(), pads=made.pads, edges=(BOARD,), min_edge_clearance=mm(0.5))
    assert len(edge_findings(report)) == 2  # two tracks, one finding each
    assert {f.items[1].where for f in edge_findings(report)} == {"board"}


# --- the stage --------------------------------------------------------------------------------------------


class _OldFrame:
    def board_pads(self, design, *, issues=None):  # noqa: ANN001, ANN201
        return ()

    def placed_extents(self, design, *, issues=None):  # noqa: ANN001, ANN201
        return ()


class _OpenFrame(_OldFrame):
    def board_edges(self, design, *, issues=None):  # noqa: ANN001, ANN201
        return None


@pytest.mark.parametrize(
    ("frame", "code"), [(_OldFrame(), "copper.rules-incomplete"), (_OpenFrame(), "copper.item-unsupported")]
)
def test_frame_without_edges(frame: object, code: str) -> None:
    made = hv_gnd()
    design = made.build()
    edges, issues = frame_edges(frame, design)
    assert edges is None and [i.code for i in issues] == [code] and issues[0].where == "edge"
    from fenolite.backends.base import ProjectSet

    result = copper_stage(
        design,
        project=ProjectSet(Path("."), "b.kicad_pcb", {"b.kicad_pcb": Path("b.kicad_pcb")}),
        rules_source=None,
        frame=frame,  # type: ignore[arg-type]
        evidence=Evidence(),
    )
    assert code in {i.code for i in result.issues}
