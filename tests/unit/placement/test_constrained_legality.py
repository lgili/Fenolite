# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Hard checks for independently authored outline, faces, drills, copper and volumes."""

from dataclasses import replace

from fenolite.backends.base import BoardFrame, PlacedExtent
from fenolite.backends.kicad import frame
from fenolite.core.coords import Point
from fenolite.model.board import Keepout
from fenolite.placement.constrained_legality import check_constraints
from fenolite.placement.constraints import GroupRegion, PlacementConstraints

from ._constrained_fixture import board, copper_checker, part


def test_fixed_geometry_and_layer_keepout() -> None:
    d = board(part("fixed", 5, 5, locked=True), part("move", 16, 16))
    assert not check_constraints(d, frame, PlacementConstraints()).hard
    forbidden = Keepout(
        id="access",
        outline=(Point(14, 14), Point(18, 14), Point(18, 18), Point(14, 18)),
        no_footprints=True,
        layers=("F.Cu",),
    )
    d = replace(d, board=replace(d.board, keepouts=(forbidden,)))
    assert any(
        x.startswith("keepout:access:move") for x in check_constraints(d, frame, PlacementConstraints()).hard
    )
    d = replace(
        d, board=replace(d.board, footprints=(d.board.footprints[0], part("move", 16, 16, side="bottom")))
    )
    assert not check_constraints(d, frame, PlacementConstraints()).hard
    outside = board(part("edge", 1, 7))
    assert any("outside-outline" in x for x in check_constraints(outside, frame, PlacementConstraints()).hard)
    near = board(part("edge", 3, 7))
    assert any(
        "edge-clearance" in x
        for x in check_constraints(near, frame, PlacementConstraints(edge_clearance=2)).hard
    )


def test_drills_and_copper_cross_faces() -> None:
    opposite = board(part("top", 10, 10), part("bottom", 10, 10, side="bottom"))
    assert not check_constraints(opposite, frame, PlacementConstraints()).hard
    drilled = board(part("top", 10, 10, drill=2), part("bottom", 10, 10, side="bottom"))
    assert any(
        x.startswith("drill-copper") for x in check_constraints(drilled, frame, PlacementConstraints()).hard
    )
    same = board(part("top", 10, 10), part("other", 15, 10))
    same = replace(
        same,
        board=replace(
            same.board,
            footprints=(
                same.board.footprints[0],
                replace(
                    same.board.footprints[1], pads=(replace(same.board.footprints[1].pads[0], net_id="b"),)
                ),
            ),
        ),
    )
    assert any(
        x.startswith("copper:copper.clearance")
        for x in check_constraints(same, frame, PlacementConstraints(), checker=copper_checker).hard
    )


def test_absent_checks_are_explicit_and_intrinsic_findings_survive_injection() -> None:
    design = board(part("package", 10, 10, two_pads=True))
    unchecked = check_constraints(design, frame, PlacementConstraints())
    assert "copper:checker-unavailable" in unchecked.missing_inputs
    assert "mechanical:checker-unavailable" in unchecked.missing_inputs
    checked = check_constraints(design, frame, PlacementConstraints(), checker=copper_checker)
    assert len(checked.intrinsic) == 1
    assert checked.intrinsic[0].relation == "intrinsic" and checked.intrinsic[0].clearance == 3
    assert "mechanical:checker-unavailable" in checked.missing_inputs


def test_group_regions_gap_and_pad_keepout_retain_distinct_constraints() -> None:
    design = board(part("A", 10, 10), part("B", 16, 10))
    region = GroupRegion("bounded", ("B",), (Point(1, 1), Point(13, 1), Point(13, 20), Point(1, 20)))
    report = check_constraints(design, frame, PlacementConstraints(gap=3, regions=(region,)))
    assert "region:bounded:B" in report.hard
    assert "gap:A:B:front" in report.hard
    forbidden = Keepout(
        id="pad-area", outline=region.outline, layers=("F.Cu",), no_footprints=False, no_pads=True
    )
    design = replace(design, board=replace(design.board, keepouts=(forbidden,)))
    assert "keepout:pad-area:p_A:pad" in check_constraints(design, frame, PlacementConstraints()).hard


def test_geometry_accepts_an_authored_neutral_frame_protocol() -> None:
    class AuthoredFrame:
        def board_pads(self, design, *, issues=None):
            return ()

        def placed_extents(self, design, *, issues=None):
            ring = (Point(8, 8), Point(12, 8), Point(12, 12), Point(8, 12))
            return (PlacedExtent("A", "top", front=(ring,), source="courtyard"),)

    supplied_frame = AuthoredFrame()
    assert isinstance(supplied_frame, BoardFrame)
    report = check_constraints(board(part("A", 10, 10)), supplied_frame, PlacementConstraints())
    assert not report.hard
    assert set(report.missing_inputs) == {"copper:checker-unavailable", "mechanical:checker-unavailable"}


def test_empty_layer_keepout_judges_nothing() -> None:
    design = board(part("A", 10, 10))
    empty = Keepout(
        id="no-layers",
        outline=(Point(8, 8), Point(12, 8), Point(12, 12), Point(8, 12)),
        no_footprints=True,
        no_pads=True,
    )
    design = replace(design, board=replace(design.board, keepouts=(empty,)))
    assert not check_constraints(design, frame, PlacementConstraints()).hard
