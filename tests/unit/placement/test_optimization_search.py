# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors

from fenolite.core.coords import Point
from fenolite.placement.optimization_contract import OptimizationBudget, ProposedPose
from fenolite.placement.optimize import SearchJudgment, beam_search

HASH = "a" * 64


def pose(ident, x):
    return ProposedPose(ident, Point(x, 0), 0, "top")


def test_joint_search_reconsiders_a_shorter_but_blocking_first_pose():
    domains = {"A": (pose("A", 0), pose("A", 4)), "B": (pose("B", 0), pose("B", 1))}

    def judge(poses, complete):
        at = [p.position.x for p in poses]
        return SearchJudgment((sum(at),), hard=("overlap",) if complete and abs(at[0] - at[1]) < 2 else ())

    greedy = beam_search(domains, input_sha256=HASH, budget=OptimizationBudget(10, 1), judge=judge)
    assert not greedy.candidates and greedy.beam_pruned
    assert greedy.partial == (pose("A", 0),) and greedy.unplaced == ("B",)

    better = beam_search(domains, input_sha256=HASH, budget=OptimizationBudget(10, 2), judge=judge)
    assert better.candidates[0].candidate.poses == (pose("A", 4), pose("B", 0))
    assert better.unplaced == () and better.partial == ()

    reordered = {key: domains[key][::-1] for key in reversed(domains)}
    assert beam_search(reordered, input_sha256=HASH, budget=OptimizationBudget(10, 2), judge=judge) == better


def test_pair_propagation_discards_dead_end_before_width_one_pruning():
    domains = {"A": (pose("A", 0), pose("A", 4)), "B": (pose("B", 0), pose("B", 1))}
    result = beam_search(
        domains,
        input_sha256=HASH,
        budget=OptimizationBudget(10, 1),
        judge=lambda poses, _: SearchJudgment((sum(p.position.x for p in poses),)),
        compatible=lambda first, second: abs(first.position.x - second.position.x) >= 2,
    )
    assert result.candidates[0].candidate.poses == (pose("A", 4), pose("B", 0))
    assert result.work == 8 and "domain_conflict:A:B" in result.blockers


def test_work_limit_and_cancellation_keep_partial_states_out_of_the_shortlist():
    domains = {"A": (pose("A", 0),), "B": (pose("B", 4),)}
    limited = beam_search(
        domains, input_sha256=HASH, budget=OptimizationBudget(1, 2), judge=lambda *_: SearchJudgment()
    )
    assert limited.termination == "budget_exhausted" and limited.work == 1
    assert limited.candidates == () and limited.partial == (pose("A", 0),)
    calls = []

    def judge(poses, _):
        calls.append(poses)
        return SearchJudgment()

    stopped = beam_search(
        domains,
        input_sha256=HASH,
        budget=OptimizationBudget(5, 2),
        judge=judge,
        cancelled=lambda: bool(calls),
    )
    assert stopped.termination == "cancelled" and stopped.work == 1
    assert stopped.partial == limited.partial and stopped.candidates == ()


def test_unchecked_final_candidate_cannot_beat_checked_geometry():
    domains = {"A": (pose("A", 0), pose("A", 2), pose("A", 4))}
    result = beam_search(
        domains,
        input_sha256=HASH,
        budget=OptimizationBudget(3, 2),
        judge=lambda poses, _: SearchJudgment(
            (0,), missing_inputs=("copper:unchecked",) if poses[0].position.x == 0 else ()
        ),
    )
    assert [row.candidate.poses[0].position.x for row in result.candidates] == [2, 4]
    assert result.blockers == ("copper:unchecked",)
