# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""A search refusal names its wall and says whether it is proven (change c0501, requirement "Search
refusals name their wall"), on the authored ring bench of ``_route_benches``."""

from __future__ import annotations

from _route_benches import MM, ring

from fenolite.routing.search import Limits, search


def test_ring_is_a_proven_wall() -> None:
    """Scenario "A closed ring of pads"."""
    b = ring()
    out = search(b.job, b.subject, b.world, Limits(100_000, 50_000, 0), max_length=100 * MM)
    assert out.reason == "no-room" and not out.runs
    assert out.proven
    assert sorted(w.blocker.label for w in out.wall) == [f"B{i}-1" for i in range(1, 9)]
    assert all(w.blocker.kind == "pad" and w.blocker.clearance == 200_000 for w in out.wall)


def test_a_gap_off_the_grid_is_grid_limited() -> None:
    """Scenario "A gap off the grid": one free gap of 0.3 mm between two lines of a 0.5 mm grid."""
    b = ring(opened=200_000)
    out = search(b.job, b.subject, b.world, Limits(500_000, 50_000, 0), max_length=100 * MM)
    assert out.reason == "no-room" and not out.proven
    assert out.widest is not None
    assert {out.widest.a.label, out.widest.b.label} == {"B4-1", "B5-1"}
    assert 300_000 <= out.widest.free < 301_000


def test_a_cut_search_proves_nothing() -> None:
    """Scenario "A cut search proves nothing"."""
    b = ring()
    out = search(b.job, b.subject, b.world, Limits(100_000, 10, 0), max_length=100 * MM)
    assert out.reason == "state-limit" and out.wall == () and not out.proven
