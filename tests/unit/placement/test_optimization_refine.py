# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors

from fenolite.core.coords import Point
from fenolite.placement.optimization_contract import OptimizationBudget, ProposedPose
from fenolite.placement.optimize import SearchJudgment, beam_search
from fenolite.placement.refine import refine_placement

HASH = "b" * 64


def test_joint_window_swaps_parts_without_moving_a_fixed_neighbor():
    a0, a1 = (ProposedPose("A", Point(x, 0), 0, "top") for x in (0, 10))
    b0, b1 = (ProposedPose("B", Point(x, 0), 0, "top") for x in (10, 0))
    fixed = ProposedPose("fixed-neighbor", Point(20, 0), 0, "top")
    domains = {"A": (a0, a1), "B": (b0, b1)}
    seed = (a0, b0)

    def judge(poses, complete):
        assert all(p.footprint_id != fixed.footprint_id for p in poses)
        points = [pose.position for pose in (*poses, fixed)]
        blocked = len(points) != len(set(points))
        return SearchJudgment((0 if a1 in poses else 10,), hard=("overlap",) if blocked else ())

    single = refine_placement(seed, domains, input_sha256=HASH, judge=judge, max_attempts=30, step_nm=10)
    assert single.best is not None and single.best.candidate.poses == seed
    joint = refine_placement(
        seed, domains, input_sha256=HASH, judge=judge, max_attempts=30, step_nm=10, windows=(("B", "A"),)
    )
    exhaustive = beam_search(domains, input_sha256=HASH, budget=OptimizationBudget(20, 4), judge=judge)
    assert joint.best == exhaustive.candidates[0]
    assert joint.improvements == 1 and joint.termination == "complete"


def test_rotation_stays_in_domain_and_a_budget_cannot_accept_an_unchecked_pose():
    seed = ProposedPose("A", Point(0, 0), 0, "top")
    turn = ProposedPose("A", seed.position, 90_000_000, "top")
    domains = {"A": (seed, turn)}

    def judge(poses, _):
        return SearchJudgment((0 if turn in poses else 1,))

    limited = refine_placement((seed,), domains, input_sha256=HASH, judge=judge, max_attempts=1, step_nm=0)
    assert limited.best is not None and limited.best.candidate.poses == (seed,)
    assert limited.termination == "budget_exhausted" and limited.work == 1
    rotated = refine_placement((seed,), domains, input_sha256=HASH, judge=judge, max_attempts=8, step_nm=0)
    assert rotated.best is not None and rotated.best.candidate.poses == (turn,)
