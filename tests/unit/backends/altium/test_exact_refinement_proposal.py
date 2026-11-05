# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Original analytic notch controls for exact-curve subdivision proposals (c0332).

The pour no longer calls this path (c0332 redesign, selective snap rounding): its caller-wired tests were
removed with that change; these controls test the modules directly."""

from fractions import Fraction as F

import pytest

from fenolite.geometry.errors import GeometryError
from fenolite.geometry.polygon import Polygon
from fenolite.geometry.vector import Point


def authored_notch(x=F(2, 5), y=F(43, 10)):
    anchors = ((0, 0), (10, 0), (10, 4), (10, 5), (10, 10), (0, 10))
    loop = (
        tuple((F(a), F(b)) for a, b in anchors[:3]) + ((x, y),) + tuple((F(a), F(b)) for a, b in anchors[3:])
    )
    return loop, Polygon(tuple(Point(a, b) for a, b in anchors))


def failed_projection():
    from fenolite.backends.altium.pour import _without_debris
    from fenolite.geometry.boolean._exact_noding import Budget, Segment
    from fenolite.geometry.boolean._exact_realization import project_nodes
    from fenolite.geometry.boolean._exact_repair import candidates

    loop, subject = authored_notch()
    source = tuple(
        Segment((a.x, a.y), (b.x, b.y), 0)
        for a, b in zip(subject.outer, subject.outer[1:] + subject.outer[:1], strict=True)
    )
    budget = Budget()
    projected = project_nodes((loop,), budget)
    proposal = next(candidates((loop,), source, projected, budget))
    return proposal, source, _without_debris(proposal.polygons, 1), budget


def test_exact_subdivision_rejects_malformed_or_noninterior_points():
    from fenolite.geometry.boolean import _exact_refinement as refinement
    from fenolite.geometry.boolean._exact_noding import Budget

    loop, _ = authored_notch()
    for edge, point in ((-1, (F(1), F(1))), (2, (F(1), F(2))), (2, loop[2]), (2, (F(20), F(3)))):
        with pytest.raises(GeometryError, match="refinement"):
            refinement._subdivide(loop, edge, point, Budget())


def test_refinement_requires_the_exact_source_and_actual_policy_boundaries():
    from fenolite.geometry.boolean._exact_refinement import refinement_candidates

    projection, source, result, budget = failed_projection()
    with pytest.raises(GeometryError, match="source context"):
        tuple(refinement_candidates(projection, (), result, budget))
    invented = Polygon((Point(100, 100), Point(110, 100), Point(110, 110), Point(100, 110)))
    with pytest.raises(GeometryError, match="policy changes outer"):
        tuple(refinement_candidates(projection, source, (invented,), budget))


def test_shared_projection_cannot_move_an_original_node():
    from dataclasses import replace

    from fenolite.geometry.boolean._exact_refinement import refinement_candidates

    projection, source, result, budget = failed_projection()
    changed = {**projection.projected, projection.loops[0][0]: (1, 0)}
    with pytest.raises(GeometryError, match="quantization|half-even"):
        tuple(refinement_candidates(replace(projection, projected=changed), source, result, budget))


def test_malformed_parentage_is_not_a_refinement_opportunity():
    from dataclasses import replace

    from fenolite.geometry.boolean._exact_noding import Budget, Segment
    from fenolite.geometry.boolean._exact_realization import project_boundaries
    from fenolite.geometry.boolean._exact_refinement import refinement_candidates

    outer = ((0, 0), (20, 0), (20, 20), (0, 20))
    hole = ((5, 5), (5, 10), (10, 10), (10, 5))
    loops = tuple(tuple((F(x), F(y)) for x, y in ring) for ring in (outer, hole))
    source = tuple(
        Segment(a, b, 0) for ring in (outer, hole) for a, b in zip(ring, ring[1:] + ring[:1], strict=True)
    )
    budget = Budget()
    projection = project_boundaries(loops, source, budget)
    wrong = replace(projection, parent={1: 999})
    with pytest.raises(GeometryError, match="hole ownership"):
        tuple(refinement_candidates(wrong, source, projection.polygons, budget))


@pytest.mark.parametrize(
    "field",
    [
        "repair_nodes",
        "repair_proposal_nodes",
        "repair_candidates",
        "nodes",
        "distance_predicates",
        "halfedges",
    ],
)
def test_refinement_uses_shared_resource_limits(field):
    from dataclasses import replace

    from fenolite.geometry.boolean._exact_refinement import refinement_candidates

    projection, source, result, budget = failed_projection()
    before = budget._repair_trials
    budget.limits = replace(budget.limits, **{field: 0})
    with pytest.raises(GeometryError, match="budget"):
        tuple(refinement_candidates(projection, source, result, budget))
    assert budget._repair_trials >= before


def test_refinement_does_not_reset_the_shared_stage_deadline():
    from fenolite.geometry.boolean._exact_refinement import refinement_candidates

    projection, source, result, budget = failed_projection()
    budget.clock = lambda: budget._stage_started + 121
    with pytest.raises(GeometryError, match="deadline"):
        tuple(refinement_candidates(projection, source, result, budget))


def certified_manual_proposal():
    from fenolite.geometry.boolean._exact_noding import Budget
    from fenolite.geometry.boolean._exact_realization import project_boundaries

    bad, source, _, _ = failed_projection()
    loop = bad.loops[0]
    a, b = loop[2], loop[3]
    point = tuple(a[c] + F(47, 48) * (b[c] - a[c]) for c in (0, 1))
    refined = loop[:3] + (point,) + loop[3:]
    good = project_boundaries((refined,), source, Budget(), omitted=frozenset({(0, 4)}))
    return bad, good


def test_pressure_selected_cells_fit_two_shared_proposal_slots():
    from dataclasses import replace

    from fenolite.backends.altium.pour import _without_debris
    from fenolite.geometry.boolean._exact_noding import Budget, Limits, Segment
    from fenolite.geometry.boolean._exact_realization import project_nodes
    from fenolite.geometry.boolean._exact_refinement import refinement_candidates
    from fenolite.geometry.boolean._exact_repair import candidates

    loop, subject = authored_notch(F(1, 5), F(41, 10))
    source = tuple(
        Segment((a.x, a.y), (b.x, b.y), 0)
        for a, b in zip(subject.outer, subject.outer[1:] + subject.outer[:1], strict=True)
    )
    budget = Budget(replace(Limits(), repair_proposal_nodes=2))
    initial = next(candidates((loop,), source, project_nodes((loop,), budget), budget))
    result = _without_debris(initial.polygons, 1)
    refined = next(refinement_candidates(initial, source, result, budget))
    final = _without_debris(refined.polygons, 1)
    certificate = refined.certify(final, 1, budget)
    assert certificate.protected_vertices == 6
    assert budget._repair_trials <= 4096


@pytest.mark.parametrize("cap,expects_cells", [(26, True), (27, False)])
def test_producer_choice_pressure_boundary_retains_old_path(cap, expects_cells, monkeypatch):
    from dataclasses import replace

    from fenolite.backends.altium.pour import _without_debris
    from fenolite.geometry.boolean import _exact_refinement as refinement
    from fenolite.geometry.boolean._exact_noding import Budget, Limits, Segment
    from fenolite.geometry.boolean._exact_realization import project_nodes
    from fenolite.geometry.boolean._exact_repair import candidates

    original = refinement.cell_point
    calls = []

    def observed(*args):
        calls.append(1)
        return original(*args)

    monkeypatch.setattr(refinement, "cell_point", observed)
    loop, subject = authored_notch(F(1, 5), F(41, 10))
    source = tuple(
        Segment((a.x, a.y), (b.x, b.y), 0)
        for a, b in zip(subject.outer, subject.outer[1:] + subject.outer[:1], strict=True)
    )
    budget = Budget(replace(Limits(), repair_proposal_nodes=cap))
    initial = next(candidates((loop,), source, project_nodes((loop,), budget), budget))
    refined = next(
        refinement.refinement_candidates(initial, source, _without_debris(initial.polygons, 1), budget)
    )
    assert bool(calls) is expects_cells
    assert refined.certify(_without_debris(refined.polygons, 1), 1, budget).protected_vertices == 6
    assert len(set(refined.projected) - set(initial.projected)) + len(initial.omitted) <= cap


def test_pressure_cell_resource_failure_propagates_without_old_producer_retry(monkeypatch):
    from dataclasses import replace

    from fenolite.backends.altium.pour import _without_debris
    from fenolite.geometry.boolean import _exact_refinement as refinement
    from fenolite.geometry.boolean._exact_noding import Budget, Limits, ResourceLimit, Segment
    from fenolite.geometry.boolean._exact_realization import project_nodes
    from fenolite.geometry.boolean._exact_repair import candidates

    def exhausted(*args):
        raise ResourceLimit("authored shared cell budget exhausted")

    monkeypatch.setattr(refinement, "cell_point", exhausted)
    loop, subject = authored_notch(F(1, 5), F(41, 10))
    source = tuple(
        Segment((a.x, a.y), (b.x, b.y), 0)
        for a, b in zip(subject.outer, subject.outer[1:] + subject.outer[:1], strict=True)
    )
    budget = Budget(replace(Limits(), repair_proposal_nodes=2))
    initial = next(candidates((loop,), source, project_nodes((loop,), budget), budget))
    with pytest.raises(ResourceLimit, match="shared cell budget"):
        next(refinement.refinement_candidates(initial, source, _without_debris(initial.polygons, 1), budget))
