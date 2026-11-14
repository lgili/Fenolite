# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""``fenolite.tidy.style`` (change c0214; capability copper-tidy, "Style report"), on authored boards of
``tests/_tidybench.py`` whose joints are counted by hand. Hermetic."""

from __future__ import annotations

import dataclasses

from _groundties import _p
from _tidybench import CLEARANCE, acute, bench, staircase
from _ties import MM, TieBoard

from fenolite.backends.kicad.frame import board_pads
from fenolite.checks.copper import check_copper
from fenolite.model.design import Design
from fenolite.tidy import Clash, StyleRow, straighten, style

W = MM // 4


def check(design: Design) -> list[Clash]:
    report = check_copper(design, pads=board_pads(design))
    return [
        Clash(found.code, found.layer, tuple(sorted({item.entity_id for item in found.items})), found.gap)
        for found in report.findings
    ]


def test_acute_joints_reported() -> None:
    """Scenario "Acute joints reported": one 30° joint gives one ``tidy.acute`` at it."""
    report = style(acute())
    (row,) = report.rows
    assert (row.netclass, row.layer, row.acute, row.joints_45, row.joints_90, row.other) == (
        "Default",
        "F.Cu",
        1,
        0,
        0,
        0,
    )
    (found,) = report.issues
    assert (found.code, found.severity) == ("tidy.acute", "warning")
    assert "(20mm, 10mm)" in found.message and found.where.count("trk_") == 2


def test_a_staircase_counted_by_hand() -> None:
    """16 right angles, 8 jogs (the 0.5 mm risers, under three widths), 14 mm of 0.25 mm track."""
    design = staircase()
    report = style(design)
    assert report.rows == (StyleRow("Default", "F.Cu", joints_90=16, jogs=8, widths=((W, 14 * MM),)),)
    assert report.counts() == {
        "joints_45": 0,
        "joints_90": 16,
        "acute": 0,
        "other": 0,
        "collinear": 0,
        "jogs": 8,
        "vias": 0,
    }
    assert [found.code for found in report.issues] == ["tidy.jog"] * 8
    straight = straighten(design, pads=board_pads(design), check=check).design
    assert style(straight).counts() == {
        "joints_45": 1,
        "joints_90": 0,
        "acute": 0,
        "other": 0,
        "collinear": 0,
        "jogs": 0,
        "vias": 0,
    }


def test_vias_classes_and_nets() -> None:
    """The bench: ``SIG`` has one right angle and the via ``v1``; ``BUS`` meets on the middle of a track,
    which is no joint of two ends."""
    design = bench()
    report = style(design)
    assert report.vias == (("Default", 1),)
    assert report.counts()["joints_90"] == 1
    assert style(design, nets={"BUS"}).counts() == {
        "joints_45": 0,
        "joints_90": 0,
        "acute": 0,
        "other": 0,
        "collinear": 0,
        "jogs": 0,
        "vias": 0,
    }
    assert design.board is not None
    classless = dataclasses.replace(
        design,
        circuit=dataclasses.replace(
            design.circuit,
            netclasses=(),
            nets=tuple(dataclasses.replace(net, netclass_id=None) for net in design.circuit.nets),
        ),
    )
    assert {row.netclass for row in style(classless).rows} == {"Default"}


def test_three_ends_and_straight_joints() -> None:
    """Three ends at one point: only acute pairs count. Two collinear tracks make no joint; a joint at
    60° (a turn of 60°) is ``other``."""
    board = TieBoard(clearance=CLEARANCE)
    board.track("a", "SIG", _p(10, 10), _p(20, 10))
    board.track("b", "SIG", _p(20, 10), _p(30, 10))
    board.track("c", "SIG", _p(20, 10), _p(10, 12))
    board.track("d", "SIG", _p(30, 10), _p(35, 18.66))
    board.track("e", "SIG", _p(35, 18.66), _p(35, 30))
    report = style(board.build())
    assert report.counts()["acute"] == 1 and report.counts()["other"] == 2
    assert sorted(found.code for found in report.issues) == ["tidy.acute", "tidy.off-45", "tidy.off-45"]


def test_no_board() -> None:
    design = staircase()
    assert style(dataclasses.replace(design, board=None)).rows == ()


def test_jog_off_45_and_collinear_at_their_places() -> None:
    """Scenario "A jog, a 60° corner and a redundant point" (change c0504, D4): one finding of each code at
    its point, and one ``collinear`` joint counted."""
    board = TieBoard(clearance=CLEARANCE)
    board.track("a", "SIG", _p(10, 10), _p(20, 10))  # a 45° turn, then a 0.21 mm jog, then a 45° turn back
    board.track("b", "SIG", _p(20, 10), _p(20.15, 10.15))
    board.track("c", "SIG", _p(20.15, 10.15), _p(30, 10.15))
    board.track("d", "SIG", _p(30, 10.15), _p(35, 18.81))  # a turn of 60°: a corner of 120°
    board.track("e", "SIG", _p(35, 18.81), _p(40, 27.47))  # collinear with d, nothing else at (35, 18.81)
    report = style(board.build())
    codes = sorted(found.code for found in report.issues)
    assert codes == ["tidy.collinear", "tidy.jog", "tidy.off-45"], codes
    assert all(found.severity == "info" for found in report.issues)
    places = {found.code: found.message for found in report.issues}
    assert "(35mm, 18.81mm)" in places["tidy.collinear"] and "(30mm, 10.15mm)" in places["tidy.off-45"]
    assert "(20.075mm, 10.075mm)" in places["tidy.jog"]
    assert report.counts()["collinear"] == 1 and report.counts()["jogs"] == 1
