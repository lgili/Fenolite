# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Independent exact cell constraints, ties, shared guards and local pressure."""

from dataclasses import replace
from fractions import Fraction as F

import pytest

from fenolite.geometry.boolean import _exact_refinement as refinement
from fenolite.geometry.boolean._exact_cells import cell_point
from fenolite.geometry.boolean._exact_faces import cross, sign, sub
from fenolite.geometry.boolean._exact_noding import Budget, ExactDeadline, Limits
from fenolite.geometry.boolean._exact_realization import project_nodes
from fenolite.geometry.errors import GeometryError
from fenolite.geometry.predicates import round_point

BASES = (
    ((F(-5), F(0)), (F(1, 3), F(1, 2)), (F(7), F(1))),
    ((F(0), F(5)), (F(1, 2), F(1, 2)), (F(5), F(1, 2))),
)


@pytest.mark.parametrize("base", BASES)
@pytest.mark.parametrize("turns", range(4))
@pytest.mark.parametrize("reverse", [False, True])
@pytest.mark.parametrize("shift", [0, 1])
@pytest.mark.parametrize("ending", [False, True])
def test_open_cells_preserve_exact_edge_half_even_ties_and_proposal_turn(base, turns, reverse, shift, ending):
    ring = base
    for _ in range(turns):
        ring = tuple((-y, x) for x, y in ring)
    if reverse:
        ring = tuple(reversed(ring))
    ring = tuple((x + shift, y + shift) for x, y in ring)
    projected = project_nodes((ring,), Budget())
    point = cell_point(ring, 1, ending, frozenset({(0, 1)}), projected, Budget(), 0)
    if point is None:
        return
    a = ring[1]
    z = ring[0] if ending else ring[2]
    v = sub(point, a)
    direction = sub(z, a)
    assert cross(v, direction) == 0
    assert 0 < v[0] * direction[0] + v[1] * direction[1] < direction[0] ** 2 + direction[1] ** 2
    q = round_point(*point)
    anchor = projected[a]
    other = projected[ring[2 if ending else 0]]
    first = (F(q.x - anchor[0]), F(q.y - anchor[1]))
    second = (F(other[0] - anchor[0]), F(other[1] - anchor[1]))
    actual = cross(first, second) if ending else cross(second, first)
    assert sign(actual) == sign(cross(sub(ring[0], a), sub(ring[2], a)))


@pytest.mark.parametrize("remaining,expected", [(52, False), (51, True)])
def test_pressure_is_only_the_first_affected_owner_and_boundary(remaining, expected, monkeypatch):
    ring = BASES[0]
    calls = []

    def probes(source, target, budget):
        calls.append(source)
        return () if source == ring else (0, 1)

    other = tuple((x + 20, y) for x, y in ring)
    monkeypatch.setattr(refinement, "_bad_probes", probes)
    initial, pressure = refinement._first_pressure(
        [0, 1],
        (ring, other),
        frozenset({(1, 0), (1, 1)}),
        project_nodes((ring, other), Budget()),
        Budget(),
        remaining,
    )
    assert pressure is expected
    assert initial == {0: (), 1: (0, 1)} and calls == [ring, other]


@pytest.mark.parametrize("field", ["nodes", "winding_visits", "coordinate_bits"])
def test_cell_producer_preserves_resource_guards(field):
    ring = BASES[0]
    projected = project_nodes((ring,), Budget())
    with pytest.raises(GeometryError, match="budget"):
        cell_point(ring, 1, False, frozenset({(0, 1)}), projected, Budget(replace(Limits(), **{field: 0})), 0)


def test_cell_malformed_zero_edge_unbound_target_and_deadline_refuse():
    ring = BASES[0]
    projected = project_nodes((ring,), Budget())
    with pytest.raises(GeometryError, match="invalid cell"):
        cell_point(ring, -1, False, frozenset(), projected, Budget(), 0)
    with pytest.raises(GeometryError, match="zero cell"):
        cell_point((ring[0], ring[0], ring[2]), 1, True, frozenset(), projected, Budget(), 0)
    with pytest.raises(GeometryError, match="unbound cell"):
        cell_point(ring, 1, False, frozenset(), {}, Budget(), 0)
    now = [0.0]
    budget = Budget(clock=lambda: now[0])
    now[0] = 1201
    with pytest.raises(ExactDeadline, match="deadline"):
        cell_point(ring, 1, False, frozenset(), projected, budget, 0)
