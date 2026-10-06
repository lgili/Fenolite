# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Bounded deterministic search, no hidden placement, explicit objectives (c0096)."""

from dataclasses import replace

from fenolite.backends.kicad import frame
from fenolite.core.coords import Point, Size
from fenolite.model import canonical
from fenolite.placement.constrained import propose_placement as _propose_placement
from fenolite.placement.constraints import PlacementConstraints, PlacementObjective

from ._constrained_fixture import board, copper_checker, part


def propose_placement(*args, **kwargs):
    return _propose_placement(*args, checker=copper_checker, **kwargs)


def test_determinism_locks_and_unchanged_net_partition() -> None:
    d = board(part("anchor", 5, 5, locked=True), part("a", 70, 40), part("b", 80, 40, side="bottom"))
    constraints = PlacementConstraints(pitch=5, gap=1, max_candidates=100)
    first = propose_placement(d, frame, ("b", "anchor", "a"), constraints=constraints)
    second = propose_placement(d, frame, ("a", "b", "anchor"), constraints=constraints)
    assert first == second and not first.unplaced
    assert first.design.circuit == d.circuit
    assert first.design.board.footprints[0] == d.board.footprints[0]
    assert first.design.board.footprints[2].side == "bottom"
    assert not first.legality.hard and first.assessment.state == "incomplete"
    assert first.source_sha256 == second.source_sha256 and first.request_sha256 == second.request_sha256
    assert "mechanical:checker-unavailable" in first.assessment.missing_inputs
    assert first.constraints == constraints
    assert d.board.footprints[1].position == Point(70, 40)


def test_no_room_and_budget_report_retains_geometry_and_intrinsic_findings() -> None:
    huge = part("huge", 90, 90, two_pads=True)
    huge = replace(huge, pads=tuple(replace(p, size=Size(50, 50)) for p in huge.pads))
    d = board(huge)
    result = propose_placement(d, frame, ("huge",), constraints=PlacementConstraints(pitch=5))
    assert result.positions == () and result.unplaced[0].footprint_id == "huge"
    assert result.unplaced[0].reasons == ("no_feasible_candidate",)
    assert result.design.board.footprints == d.board.footprints
    assert result.intrinsic and result.intrinsic[0].relation == "intrinsic"
    assert any("copper.short" in finding for finding in result.assessment.findings)
    blocked = board(part("anchor", 2, 2, locked=True), part("a", 90, 90))
    bounded = propose_placement(
        blocked, frame, ("a",), constraints=PlacementConstraints(pitch=1, max_candidates=1)
    )
    assert bounded.unplaced[0].reasons[0] == "search_budget_exhausted"
    assert bounded.candidate_counts == (("a", 1),)


def test_objective_is_measured_surrogate_and_pending_target() -> None:
    d = board(part("anchor", 30, 20, locked=True), part("a", 90, 90))
    objective = PlacementObjective("drive", "p_anchor", "p_a", max_distance=1, weight=2)
    result = propose_placement(
        d,
        frame,
        ("a",),
        constraints=PlacementConstraints(pitch=5, max_candidates=100),
        objectives=(objective,),
    )
    assert result.positions and not result.unplaced
    measured = result.objectives[0]
    assert measured.status == "unmet" and measured.contribution_nm == measured.distance_nm * 2
    assert measured.squared_distance_nm > 1
    unknown = propose_placement(
        d,
        frame,
        ("a",),
        constraints=PlacementConstraints(pitch=5, max_candidates=3),
        objectives=(replace(objective, second_pad="missing"),),
    )
    assert unknown.objectives[0].status == "unknown"
    assert result.assessment.state != "checked"
    assert "float" not in canonical.dumps(result.objectives)


def test_proposal_never_accepts_violating_locked_geometry() -> None:
    d = board(part("anchor", 1, 1, locked=True), part("a", 90, 90))
    result = propose_placement(
        d, frame, ("a", "anchor"), constraints=PlacementConstraints(pitch=5, max_candidates=8)
    )
    assert result.unplaced and result.design.board.footprints[0].position == Point(1, 1)
    assert any("outside-outline" in finding for finding in result.legality.hard)


def test_missing_checker_is_reported_without_accepting_unchecked_candidates() -> None:
    design = board(part("move", 90, 90))
    result = _propose_placement(design, frame, ("move",), constraints=PlacementConstraints(max_candidates=2))
    assert result.positions == () and result.unplaced
    assert result.design == design
    assert "copper:checker-unavailable" in result.assessment.missing_inputs


def test_search_starts_in_far_group_region() -> None:
    from fenolite.placement.constraints import GroupRegion

    design = board(part("moving", 250, 250))
    design = replace(
        design,
        board=replace(
            design.board,
            outline=replace(
                design.board.outline,
                points=(Point(0, 0), Point(200, 0), Point(200, 200), Point(0, 200)),
            ),
        ),
    )
    region = GroupRegion(
        "far", ("moving",), (Point(170, 170), Point(190, 170), Point(190, 190), Point(170, 190))
    )
    result = propose_placement(
        design, frame, ("moving",), constraints=PlacementConstraints(pitch=1, regions=(region,))
    )
    assert not result.unplaced
    assert result.positions == (("moving", Point(172, 172)),)
    assert result.candidate_counts == (("moving", 1),)
    assert not result.legality.hard
