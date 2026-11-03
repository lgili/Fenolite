# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Continuous covers, endpoint-only counterexamples and finite repair budgets (c0332)."""

from __future__ import annotations

from dataclasses import replace
from fractions import Fraction as F

import pytest

from fenolite.geometry.boolean import _exact_distance as distance
from fenolite.geometry.boolean._exact_noding import Budget, Limits
from fenolite.geometry.boolean.base import COORD_LIMIT
from fenolite.geometry.errors import GeometryError


def square(x: int | F = 0, y: int | F = 0) -> tuple[tuple[F, F], ...]:
    return ((F(x), F(y)), (F(x) + 10, F(y)), (F(x) + 10, F(y) + 10), (F(x), F(y) + 10))


def test_entire_boundary_is_certified_in_both_directions() -> None:
    first, second = distance.boundary_bound(square(), square(F(1, 2)), Budget())
    assert first.maximum_squared_distance == second.maximum_squared_distance == F(1, 4)
    covered = {i.edge for i in first.intervals} | {
        (run.source_start + offset) % 4 for run in first.identities for offset in range(run.count)
    }
    assert covered == set(range(4))


def test_original_endpoints_close_to_different_features_do_not_cover_the_middle() -> None:
    source = ((F(0), F(0)), (F(10), F(0)))
    target = ((F(0), F(-2)), (F(10), F(-2)), (F(10), F(2)), (F(0), F(2)))
    for p in source:
        assert (
            min(
                distance.distance_squared(p, a, b, Budget())
                for a, b in zip(target, target[1:] + target[:1], strict=True)
            )
            == 0
        )
    assert (
        min(
            distance.distance_squared((F(5), F(0)), a, b, Budget())
            for a, b in zip(target, target[1:] + target[:1], strict=True)
        )
        == 4
    )
    with pytest.raises(GeometryError, match="uncovered continuous interval endpoint"):
        distance.cover(source, target, Budget())


def test_interior_interval_gap_cannot_pass() -> None:
    ring = square()
    valid = distance.Cover(tuple(distance.Interval(i, F(0), F(1), i) for i in range(4)), F(0))
    distance.verify_cover(ring, ring, valid, Budget())
    first, *rest = valid.intervals
    broken = distance.Cover((replace(first, lo=F(1, 2)), *rest), valid.maximum_squared_distance)
    with pytest.raises(GeometryError, match="parameter gap"):
        distance.verify_cover(ring, ring, broken, Budget())


def test_false_capsule_assignment_and_summary_are_rejected() -> None:
    ring = square()
    valid = distance.Cover(tuple(distance.Interval(i, F(0), F(1), i) for i in range(4)), F(0))
    distance.verify_cover(ring, ring, valid, Budget())
    first, *rest = valid.intervals
    broken = distance.Cover(
        (replace(first, target=(first.target + 2) % 4), *rest), valid.maximum_squared_distance
    )
    with pytest.raises(GeometryError, match="precision bound"):
        distance.verify_cover(ring, ring, broken, Budget())
    with pytest.raises(GeometryError, match="summary mismatch"):
        distance.verify_cover(ring, ring, replace(valid, maximum_squared_distance=F(1, 4)), Budget())


@pytest.mark.parametrize(
    "field", ["distance_predicates", "distance_intervals", "distance_depth", "distance_bits"]
)
def test_distance_limits_refuse_an_incomplete_certificate(field: str) -> None:
    source = ((F(0), F(0)), (F(2), F(0)))
    target = ((F(0), F(0)), (F(1), F(1, 2)), (F(2), F(0)), (F(2), F(-2)), (F(0), F(-2)))
    # Both slopes cover the source, but no one capsule covers its entire edge.
    distance.cover(source, target, Budget())
    with pytest.raises(GeometryError, match="budget"):
        distance.cover(source, target, Budget(replace(Limits(), **{field: 0})))


def test_query_envelope_at_native_coordinate_domain_boundary_is_conservative() -> None:
    edge = ((F(COORD_LIMIT - 10), F(COORD_LIMIT)), (F(COORD_LIMIT), F(COORD_LIMIT)))
    first, second = distance.boundary_bound(edge, edge, Budget())
    assert first.maximum_squared_distance == second.maximum_squared_distance == 0


def test_projected_vertex_witness_fits_the_same_five_interval_budget(monkeypatch):
    # Isolate the capsule producer from the separately tested identity encoder.
    monkeypatch.setattr(distance, "identity_matches", lambda *args: ({}, ()))
    from dataclasses import replace

    source = ((F(0), F(0)), (F(10), F(0)), (F(10), F(10)), (F(0), F(10)))
    target = ((F(0), F(0)), (F(11, 3), F(1, 4)), (F(10), F(0)), (F(10), F(10)), (F(0), F(10)))
    budget = Budget(replace(Limits(), distance_intervals=5))
    proof = distance.cover(source, target, budget)
    assert len(proof.intervals) == 5
    distance.verify_cover(source, target, proof, Budget())


def test_projected_break_refusal_keeps_the_original_dyadic_fallback(monkeypatch):
    monkeypatch.setattr(distance, "identity_matches", lambda *args: ({}, ()))
    source = ((F(0), F(0)), (F(10), F(0)), (F(10), F(10)), (F(0), F(10)))
    target = ((F(0), F(0)), (F(11, 3), F(1, 4)), (F(10), F(0)), (F(10), F(10)), (F(0), F(10)))
    monkeypatch.setattr(distance, "_projected_split", lambda *args: None)
    proof = distance.cover(source, target, Budget())
    assert len(proof.intervals) == 7
    distance.verify_cover(source, target, proof, Budget())


def test_projected_break_resource_failure_is_not_swallowed(monkeypatch):
    from fenolite.geometry.boolean._exact_noding import ResourceLimit

    def exhausted(*args):
        raise ResourceLimit("authored projection budget exhausted")

    monkeypatch.setattr(distance, "_projected_split", exhausted)
    source = ((F(0), F(0)), (F(2), F(0)))
    target = ((F(0), F(0)), (F(1), F(1, 2)), (F(2), F(0)), (F(2), F(-2)), (F(0), F(-2)))
    with pytest.raises(ResourceLimit, match="projection budget"):
        distance.cover(source, target, Budget())


def test_false_projected_break_still_fails_the_original_complete_verifier(monkeypatch):
    monkeypatch.setattr(
        distance, "_projected_split", lambda *args: (F(1, 2), (0, F(0), F(0)), (0, F(0), F(0)))
    )
    source = ((F(0), F(0)), (F(2), F(0)))
    target = ((F(0), F(0)), (F(1), F(1, 2)), (F(2), F(0)), (F(2), F(-2)), (F(0), F(-2)))
    with pytest.raises(GeometryError, match="continuous interval|summary mismatch"):
        distance.cover(source, target, Budget())
