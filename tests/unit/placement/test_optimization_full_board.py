# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors

from fenolite.backends.kicad import frame
from fenolite.geometry import BBox
from fenolite.placement.floorplan import bind_blocks, search_region_placements
from fenolite.placement.optimization_contract import OptimizationBudget
from fenolite.placement.optimize import SearchJudgment
from fenolite.placement.regions import Region

from .test_optimization_blocks import bench

REGIONS = (Region("a-right", BBox(20, 0, 40, 30)), Region("z-left", BBox(0, 0, 20, 30)))


def test_local_expansion_tries_a_neighbor_when_the_first_region_has_no_whole_block_pose():
    design, request, _ = bench()
    blocks = bind_blocks(design, (request,))
    budget = OptimizationBudget(32, 4)
    placed = search_region_placements(
        design,
        frame,
        blocks,
        REGIONS,
        {"filter": 50},
        {},
        {},
        input_sha256="authored",
        budget=budget,
        judge=lambda _poses, _complete: SearchJudgment((0,)),
    )
    assert placed.assignments == {"filter": "z-left"}
    assert placed.attempts == 2 and placed.work <= budget.evaluations
    assert "block:filter:region-no-pose" in placed.blockers
    assert placed.search is not None and placed.search.candidates
    for row in placed.search.candidates:
        assert tuple(pose.footprint_id for pose in row.candidate.poses) == ("A", "B")
        assert all(pose.position.x + 2 <= 20 for pose in row.candidate.poses)


def test_region_barrier_and_coarse_overflow_never_produce_a_partial_board_candidate():
    design, request, _ = bench()
    blocks = bind_blocks(design, (request,))
    cases = (
        ({"filter": 50}, {"filter": frozenset({"a-right"})}, "block:filter:region-no-pose"),
        ({"filter": 601}, {}, "block:filter:region-overflow"),
    )
    for areas, allowed, blocker in cases:
        refused = search_region_placements(
            design,
            frame,
            blocks,
            REGIONS,
            areas,
            allowed,
            {},
            input_sha256="authored",
            budget=OptimizationBudget(32, 4),
            judge=lambda _poses, _complete: SearchJudgment((0,)),
        )
        assert refused.search is None and refused.assignments == {}
        assert blocker in refused.blockers
