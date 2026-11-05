# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Original wavy-chain RED for the explicitly new exact identity encoding."""

from dataclasses import replace
from fractions import Fraction as F

import pytest

from fenolite.geometry.boolean import _exact_distance as distance
from fenolite.geometry.boolean._exact_identity import IdentityRun
from fenolite.geometry.boolean._exact_noding import Budget, ExactDeadline, Limits
from fenolite.geometry.errors import GeometryError


def authored_ring():
    return tuple((F(i), F(i % 2)) for i in range(100)) + ((F(99), F(-10)), (F(0), F(-10)))


def test_exact_identity_chain_fits_the_same_sixteen_interval_cap():
    ring = authored_ring()
    budget = Budget(replace(Limits(), distance_intervals=16))
    proof = distance.cover(ring, ring, budget)
    assert not proof.intervals
    assert sum(run.count for run in proof.identities) == len(ring)
    distance.verify_cover(ring, ring, proof, Budget())


@pytest.mark.parametrize(
    "fault", ["edit1nm", "omit", "duplicate", "reverseowner", "wrongstart", "boolcount", "unknown"]
)
def test_exact_run_rejects_mutations_and_invalid_ownership(fault):
    ring = authored_ring()
    target = ring
    proof = distance.cover(ring, ring, Budget())
    if fault == "edit1nm":
        target = ((ring[0][0] + 1, ring[0][1]),) + ring[1:]
    elif fault == "omit":
        proof = replace(proof, identities=(IdentityRun(0, 0, len(ring) - 1),))
    elif fault == "duplicate":
        proof = replace(proof, identities=proof.identities + proof.identities)
    elif fault == "reverseowner":
        target = tuple(reversed(ring))
    elif fault == "wrongstart":
        proof = replace(proof, identities=(IdentityRun(0, 1, len(ring)),))
    elif fault == "boolcount":
        proof = replace(proof, identities=(IdentityRun(0, 0, True),))
    else:
        proof = replace(proof, identities=(object(),))
    with pytest.raises(GeometryError):
        distance.verify_cover(ring, target, proof, Budget())


def test_capsule_identity_overlap_refuses():
    ring = authored_ring()
    proof = distance.cover(ring, ring, Budget())
    proof = replace(proof, intervals=(distance.Interval(0, F(0), F(1), 0),))
    with pytest.raises(GeometryError, match="overlap"):
        distance.verify_cover(ring, ring, proof, Budget())


@pytest.mark.parametrize("turns", range(4))
def test_cyclic_quarter_turns_preserve_all_original_ids(turns):
    ring = authored_ring()
    for _ in range(turns):
        ring = tuple((-y, x) for x, y in ring)
    target = ring[17:] + ring[:17]
    a, b = distance.boundary_bound(ring, target, Budget())
    assert not a.intervals and not b.intervals
    for source, other, proof in ((ring, target, a), (target, ring, b)):
        covered = [(run.source_start + i) % len(source) for run in proof.identities for i in range(run.count)]
        assert sorted(covered) == list(range(len(source)))
        distance.verify_cover(source, other, proof, Budget())


@pytest.mark.parametrize(
    "field", ["nodes", "halfedges", "winding_visits", "distance_predicates", "distance_bits"]
)
def test_identity_encoder_preserves_shared_resource_guards(field):
    ring = authored_ring()
    with pytest.raises(GeometryError, match="budget"):
        distance.cover(ring, ring, Budget(replace(Limits(), **{field: 0})))


def test_identity_verification_preserves_shared_deadline_and_target_multiplicity():
    ring = authored_ring()
    proof = distance.cover(ring, ring, Budget())
    now = [0.0]
    budget = Budget(clock=lambda: now[0])
    now[0] = 1201
    with pytest.raises(ExactDeadline, match="deadline"):
        distance.verify_cover(ring, ring, proof, budget)
    # Duplicate target ownership cannot be hidden by disjoint source ranges.
    bad = replace(proof, identities=(IdentityRun(0, 0, 1), IdentityRun(1, 0, 1)))
    with pytest.raises(GeometryError, match="multiplicity"):
        distance.verify_cover(ring, ring, bad, Budget())


def test_duplicate_ambiguous_directed_edges_use_capsules_without_losing_ids():
    ring = tuple((F(x), F(y)) for x, y in ((0, 0), (1, 0), (0, 0), (1, 0), (1, 1), (0, 1)))
    proof = distance.cover(ring, ring, Budget())
    identity_ids = {(run.source_start + i) % len(ring) for run in proof.identities for i in range(run.count)}
    assert not identity_ids.intersection({0, 2})
    assert {part.edge for part in proof.intervals} >= {0, 2}
    assert identity_ids | {part.edge for part in proof.intervals} == set(range(len(ring)))
    distance.verify_cover(ring, ring, proof, Budget())
