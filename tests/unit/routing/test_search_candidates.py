# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Search integrates into proposals without changing default output or merging copper."""

from dataclasses import replace

import pytest
from _searchbench import bench, wall

from fenolite.routing.octilinear import OctilinearRouter
from fenolite.routing.search import options

OPTIONS = {
    "search": "only",
    "search-grid": "1mm",
    "search-max-states": "20000",
    "search-max-vias": "0",
    "max-length": "40mm",
}


def test_search_only_candidates_have_stable_ids_and_no_merged_copper() -> None:
    job, _, _ = bench(tracks=(wall("one", 4, 0, 6), wall("two", 8, 4, 10)), allowed=("F.Cu",))
    job = replace(job, options=OPTIONS)
    router = OctilinearRouter()
    a, b = router.route(job), router.route(job)
    assert a == b and a.candidates and a.candidates[0].source == "search"
    assert not (a.tracks or a.vias or a.arcs)
    assert not a.refusals and a.log and "expanded=" in a.log[0]
    assert all(not t.locked for candidate in a.candidates for t in candidate.tracks)


def test_default_patterns_are_unchanged_and_fallback_is_conditional() -> None:
    job, _, _ = bench()
    router = OctilinearRouter()
    before = router.route(job)
    off = router.route(replace(job, options={"search": "off"}))
    fallback = router.route(replace(job, options={**OPTIONS, "search": "fallback"}))
    assert before.candidates == off.candidates == fallback.candidates
    assert not fallback.log
    job, _, _ = bench(tracks=(wall("one", 4, 0, 6), wall("two", 8, 4, 10)), allowed=("F.Cu",))
    assert not router.route(job).candidates
    assert (
        router.route(replace(job, options={**OPTIONS, "search": "fallback"})).candidates[0].source == "search"
    )


def test_state_bound_is_an_explicit_refusal_with_work_counters() -> None:
    job, _, _ = bench()
    result = OctilinearRouter().route(replace(job, options={**OPTIONS, "search-max-states": "1"}))
    assert not result.candidates and result.refusals[0][1] == "state-limit"
    assert "discovered=1" in result.refusals[0][2][0]


def test_cancelled_api_job_is_read_only() -> None:
    job, _, _ = bench()
    result = OctilinearRouter().route(
        replace(job, options=OPTIONS, extra={**job.extra, "cancelled": lambda: True})
    )
    assert not result.candidates and result.refusals[0][1] == "cancelled"
    assert not (result.tracks or result.vias)


def test_one_job_budget_is_not_reset_between_subjects(monkeypatch) -> None:
    from fenolite.routing import propose

    instances = []

    class ClockBudget:
        def __init__(self, seconds):
            instances.append(seconds)

        def left(self):
            return 0

    monkeypatch.setattr(propose, "Budget", ClockBudget)
    job, subject, _ = bench()
    job = replace(job, options=OPTIONS, budget=1, subjects=(subject, replace(subject, key="second")))
    result = OctilinearRouter().route(job)
    assert instances == [1]
    assert [reason for _, reason, _ in result.refusals] == ["budget", "budget"]


@pytest.mark.parametrize(
    "change",
    [
        {"search": "bad"},
        {"search-grid": "1mm"},
        {"search": "only"},
        {**OPTIONS, "search-grid": "0mm"},
        {**OPTIONS, "search-max-states": "0"},
        {**OPTIONS, "search-max-vias": "-1"},
        {**OPTIONS, "search-max-states": "2.5"},
    ],
)
def test_invalid_options_are_not_silently_ignored(change) -> None:
    with pytest.raises(ValueError):
        options(change)


def test_search_requires_proposal_job_even_when_called_directly() -> None:
    job, _, _ = bench()
    with pytest.raises(ValueError, match="proposal"):
        OctilinearRouter().route(replace(job, subjects=(), options=OPTIONS))


@pytest.mark.parametrize("mode", ["fallback", "only"])
def test_search_modes_never_offer_an_independent_pair_leg(mode: str) -> None:
    from fenolite.routing.protocol import JobPair

    job, _, _ = bench()
    paired = replace(
        job, pairs=(JobPair("pair", "SIG", "OTHER", 100_000, 100_000),), options={**OPTIONS, "search": mode}
    )
    result = OctilinearRouter().route(paired)
    assert not result.candidates
    assert result.refusals[0][1] == "search-unsupported"
