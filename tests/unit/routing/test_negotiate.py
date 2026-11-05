# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Authored geometry, deterministic limits and immutable original-copper proofs (c0367)."""

from dataclasses import replace

import pytest
from _negotiatebench import negotiation_bench
from _searchbench import MM, wall

from fenolite.routing.negotiate import Cost, clashes, negotiate, options, shapes
from fenolite.routing.protocol import JobPair
from fenolite.routing.search import Limits

LIMITS = Limits(MM // 2, 40_000, 0)


def test_two_crossing_connections_negotiate_a_jointly_legal_detour() -> None:
    job, world = negotiation_bench()
    before = job.design
    result = negotiate(job, world, LIMITS, 5, max_length=40 * MM)
    assert result.members and not result.reason and result.rounds > 1
    a, b = result.members
    assert not any(clashes(x, y, world) for x in shapes(a, job) for y in shapes(b, job))
    assert job.design == before and not world.placed
    assert result == negotiate(
        replace(job, subjects=tuple(reversed(job.subjects))), world, LIMITS, 5, max_length=40 * MM
    )


def test_one_round_never_leaks_crossing_geometry() -> None:
    job, world = negotiation_bench()
    result = negotiate(job, world, LIMITS, 1, max_length=40 * MM)
    assert not result.members and result.reason == "negotiate-round-limit" and result.rounds == 1


def test_discovered_state_bound_is_shared_across_subjects_and_rounds() -> None:
    job, world = negotiation_bench()
    result = negotiate(job, world, replace(LIMITS, max_states=10), 5, max_length=40 * MM)
    assert not result.members and result.reason == "state-limit" and result.discovered <= 10


@pytest.mark.parametrize("why", ["budget", "cancelled"])
def test_interruption_never_returns_partial_copper(why: str) -> None:
    job, world = negotiation_bench()
    assert negotiate(job, world, LIMITS, 5, max_length=40 * MM, stop=lambda: why).reason == why


def test_locked_original_copper_is_never_a_reroute_candidate() -> None:
    obstacle = replace(wall("locked", 6, 0, 10), locked=True)
    job, world = negotiation_bench(tracks=(obstacle,))
    result = negotiate(job, world, LIMITS, 5, max_length=40 * MM)
    assert not result.members
    assert job.design.board.tracks == (obstacle,) and not world.placed


def test_coupled_leg_and_group_are_refused_whole() -> None:
    job, world = negotiation_bench()
    paired = replace(job, pairs=(JobPair("pair", "SIG", "WALL", 100_000, 100_000),))
    assert negotiate(paired, world, LIMITS, 5, max_length=40 * MM).reason == "negotiate-unsupported"
    grouped = replace(job, subjects=(replace(job.subjects[0], kind="group"), job.subjects[1]))
    assert negotiate(grouped, world, LIMITS, 5, max_length=40 * MM).reason == "negotiate-unsupported"


def test_cost_is_nonnegative_and_grows_with_history() -> None:
    job, world = negotiation_bench()
    result = negotiate(job, world, LIMITS, 3, max_length=40 * MM)
    held = shapes(result.members[0], job)
    empty = Cost(world, (), (), 0)("SECOND", "F.Cu", (held[0].shape.core[0], held[0].shape.core[1]), 100_000)
    repeated = Cost(world, held, held, 2)("SECOND", "F.Cu", held[0].shape.core, 100_000)
    assert empty == 0 and repeated > 0


@pytest.mark.parametrize(
    "given",
    [
        {"negotiate": "bad"},
        {"negotiate": "on"},
        {"negotiate-max-rounds": "2"},
        {"negotiate": "on", "negotiate-max-rounds": "0"},
    ],
)
def test_invalid_bounds_are_usage_errors(given) -> None:
    with pytest.raises(ValueError):
        options(given)
