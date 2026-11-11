# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors

from fenolite.core.coords import Point
from fenolite.geometry.shapes import BBox
from fenolite.placement.constraints import GroupRegion, PlacementConstraints
from fenolite.placement.domains import sample_domain
from fenolite.placement.optimization_contract import ProposedPose


def test_small_budget_preserves_original_nonquarter_pose_and_explores_another_rotation():
    start = ProposedPose("part", Point(20, 10), 30_000_000, "bottom")
    domain = sample_domain(
        start,
        BBox(0, 0, 50, 40),
        {0: BBox(-3, -1, 3, 1), start.rotation: BBox(-2, -2, 2, 2)},
        PlacementConstraints(pitch=3),
        max_attempts=2,
    )
    assert domain.poses[0] == start
    assert [(pose.rotation, pose.side) for pose in domain.poses] == [(30_000_000, "bottom"), (0, "bottom")]
    assert domain.attempts == 2 and domain.exhausted


def test_domain_intersects_regions_using_asymmetric_local_offsets_and_board_margin():
    region = GroupRegion("far", ("part",), (Point(70, 20), Point(100, 20), Point(100, 45), Point(70, 45)))
    domain = sample_domain(
        ProposedPose("part", Point(0, 0), 0, "top"),
        BBox(0, 0, 100, 50),
        {0: BBox(-4, -1, 7, 2)},
        PlacementConstraints(pitch=5, edge_clearance=3, regions=(region,)),
        anchors=(Point(80, 25),),
        max_attempts=500,
    )
    assert domain.poses[0].position == Point(80, 25)
    assert not domain.exhausted
    assert len({pose.position for pose in domain.poses}) == len(domain.poses)
    for pose in domain.poses:
        assert 74 <= pose.position.x <= 90 and 21 <= pose.position.y <= 43


def test_unfit_pose_and_truncated_search_are_distinct():
    start = ProposedPose("part", Point(0, 0), 0, "top")
    board = BBox(0, 0, 4, 4)
    constraints = PlacementConstraints(pitch=1)
    unfit = sample_domain(start, board, {0: BBox(-3, -3, 3, 3)}, constraints, max_attempts=0)
    limited = sample_domain(start, board, {0: BBox(0, 0, 1, 1)}, constraints, max_attempts=0)
    assert not unfit.poses and not unfit.exhausted
    assert not limited.poses and limited.exhausted
