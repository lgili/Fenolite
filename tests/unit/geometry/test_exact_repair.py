# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""An authored rational hairline repair retains integer corners and proves whole curves (c0332)."""

from __future__ import annotations

from collections import Counter
from dataclasses import replace
from fractions import Fraction as F

import pytest

from fenolite.backends.altium.pour import _without_debris
from fenolite.geometry.boolean import _exact_realization as real
from fenolite.geometry.boolean._exact_noding import Budget, Limits, ResourceLimit, Segment
from fenolite.geometry.boolean._exact_repair import candidates
from fenolite.geometry.errors import GeometryError
from fenolite.geometry.vector import Point


def authored_loop(height: F = F(2, 5)) -> tuple[real.Ring, tuple[Segment, ...]]:
    # Integer anchors are authored independently of the integration captures.
    anchors = ((0, 0), (10, 1), (20, 3), (20, 10), (0, 10))
    loop = (
        tuple((F(x), F(y)) for x, y in anchors[:2])
        + ((F(4, 5), height),)
        + tuple((F(x), F(y)) for x, y in anchors[2:])
    )
    source = tuple(Segment(a, b, 0) for a, b in zip(anchors, anchors[1:] + anchors[:1], strict=True))
    return loop, source


def test_proven_noninteger_shortcut_preserves_all_integer_corners(monkeypatch: pytest.MonkeyPatch) -> None:
    loop, source = authored_loop()
    budget = Budget()
    calls: Counter[tuple[F, F]] = Counter()
    original = real.round_point

    def counted(x: F | int, y: F | int) -> Point:
        calls[F(x), F(y)] += 1
        return original(x, y)

    monkeypatch.setattr(real, "round_point", counted)
    projected = real.project_nodes((loop,), budget)
    with pytest.raises(GeometryError, match="nonsimple"):
        real.project_boundaries((loop,), source, budget, projected=projected)
    proposals = list(candidates((loop,), source, projected, budget))
    assert len(proposals) == 1
    projection = proposals[0]
    assert projection.omitted == frozenset({(0, 2)})
    result = _without_debris(projection.polygons, 1)
    certificate = projection.certify(result, 1, budget)
    assert certificate.protected_vertices == 5
    assert set(calls.values()) == {1} and len(calls) == 6
    assert set(result[0].outer) == {Point(0, 0), Point(10, 1), Point(20, 3), Point(20, 10), Point(0, 10)}
    # This distinct continuous certificate does not pretend the earlier exact
    # projected point-set gate passed.
    assert real.line_cover(tuple(projected[p] for p in loop), Budget()) != real.line_cover(
        projection.integer_loops[0], Budget()
    )


def test_shortcut_cannot_exceed_the_original_continuous_error_bound() -> None:
    loop, source = authored_loop(F(4, 5))
    projection = real.project_boundaries((loop,), source, Budget(), omitted=frozenset({(0, 2)}))
    result = _without_debris(projection.polygons, 1)
    with pytest.raises(GeometryError, match="uncovered continuous interval endpoint"):
        projection.certify(result, 1, Budget())


def test_integer_node_omission_is_always_refused() -> None:
    loop, source = authored_loop()
    with pytest.raises(GeometryError, match="integer boundary node omitted"):
        real.project_boundaries((loop,), source, Budget(), omitted=frozenset({(0, 1)}))


@pytest.mark.parametrize("field", ["repair_nodes", "repair_proposal_nodes", "repair_candidates"])
def test_repair_search_refuses_on_its_shared_resource_limits(field: str) -> None:
    loop, source = authored_loop()
    budget = Budget(replace(Limits(), **{field: 0}))
    projected = real.project_nodes((loop,), budget)
    with pytest.raises(ResourceLimit, match="budget"):
        list(candidates((loop,), source, projected, budget))


def authored_hairlines(count: int) -> tuple[tuple[real.Ring, ...], tuple[Segment, ...]]:
    loop, source = authored_loop()
    loops = tuple(tuple((x + 30 * i, y) for x, y in loop) for i in range(count))
    segments = tuple(
        Segment((s.a[0] + 30 * i, s.a[1]), (s.b[0] + 30 * i, s.b[1]), s.channel)
        for i in range(count)
        for s in source
    )
    return loops, segments


def test_many_independent_hairlines_preserve_every_integer_corner() -> None:
    loops, segments = authored_hairlines(17)
    budget = Budget()
    projected = real.project_nodes(loops, budget)
    proposals = candidates(loops, segments, projected, budget)
    projection = next(proposals)
    result = _without_debris(projection.polygons, 1)
    certificate = projection.certify(result, 1, budget)
    proposals.close()
    assert len(result) == 17 and certificate.protected_vertices == 85
    assert projection.omitted == frozenset((i, 2) for i in range(17))
    assert all(type(p.x) is int and type(p.y) is int for poly in result for p in poly.outer)


def test_single_proposal_obeys_its_declared_node_cap() -> None:
    loops, source = authored_hairlines(257)
    budget = Budget()
    projected = real.project_nodes(loops, budget)
    with pytest.raises(ResourceLimit, match="proposal-node budget"):
        next(candidates(loops, source, projected, budget))


def test_invalid_default_without_a_self_crossing_does_not_invent_repairs() -> None:
    loop, source = authored_loop(F(4, 5))
    budget = Budget()
    projected = real.project_nodes((loop,), budget)
    assert list(candidates((loop,), source, projected, budget)) == []
