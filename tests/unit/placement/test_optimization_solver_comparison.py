# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors

from itertools import permutations
from math import exp
from random import Random

import pytest

from fenolite.core.coords import Point
from fenolite.placement.optimization_contract import OptimizationBudget, ProposedPose
from fenolite.placement.optimize import SearchJudgment, beam_search

PARTS = tuple("ABCDEF")
SITES = tuple(Point(x, y) for y in (0, 6) for x in (0, 5, 10))
EVALUATIONS = 240


@pytest.mark.parametrize(
    "edges",
    [
        ("AD", "BE", "CF", "AB", "BC", "DE", "EF"),
        ("AF", "BC", "DE", "AC", "CF", "BF", "BD"),
    ],
    ids=["repeated-channel", "feedback-holdout"],
)
def test_seeded_annealing_benchmark_under_equal_evaluations(edges):
    domains = {key: tuple(ProposedPose(key, point, 0, "top") for point in SITES) for key in PARTS}

    def cost(positions):
        return sum(
            abs(positions[a].x - positions[b].x) + abs(positions[a].y - positions[b].y)
            for a, b in edges
            if a in positions and b in positions
        )

    def judge(poses, _complete):
        positions = {row.footprint_id: row.position for row in poses}
        if len(set(positions.values())) != len(poses):
            return SearchJudgment(hard=("shared site",))
        return SearchJudgment((cost(positions),))

    baseline = beam_search(
        domains,
        input_sha256="authored",
        budget=OptimizationBudget(EVALUATIONS, 8),
        judge=judge,
    )
    assert baseline.candidates and baseline.work <= EVALUATIONS
    seed = dict(zip(PARTS, SITES, strict=True))

    def anneal(budget):
        rng = Random(17)
        current, current_cost = seed.copy(), cost(seed)
        best = current_cost
        for attempt in range(1, budget):
            a, b = rng.sample(PARTS, 2)
            trial = current | {a: current[b], b: current[a]}
            score = cost(trial)
            delta = score - current_cost
            temperature = 1 + 19 * (budget - attempt) / budget
            if delta <= 0 or rng.random() < exp(-delta / temperature):
                current, current_cost = trial, score
                best = min(best, current_cost)
        return best

    optimum = min(cost(dict(zip(PARTS, row, strict=True))) for row in permutations(SITES))
    measured = anneal(baseline.work)
    assert optimum <= measured <= cost(seed)
    assert optimum <= baseline.candidates[0].score[0]
    assert measured == anneal(baseline.work)
    print(
        f"equal evaluations={baseline.work} beam={baseline.candidates[0].score[0]} "
        f"annealing={measured} exact={optimum}"
    )
