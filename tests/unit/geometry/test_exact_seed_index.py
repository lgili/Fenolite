# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Independent exact closed-interval selection and infinitesimal winding controls."""

from dataclasses import replace
from fractions import Fraction as F

import pytest

from fenolite.geometry.boolean import _exact_faces as faces
from fenolite.geometry.boolean._exact_noding import Budget, ExactDeadline, Limits, Segment
from fenolite.geometry.boolean._exact_seed_index import ClosedYIndex
from fenolite.geometry.errors import GeometryError


@pytest.mark.parametrize("direction", [(1, 0), (0, 1), (-1, 0), (0, -1), (1, 1), (-1, 1), (1, -1), (-1, -1)])
@pytest.mark.parametrize("height", [F(-2), F(-1), F(-1, 2), F(0), F(1, 2), F(1)])
@pytest.mark.parametrize("rotation", [0, 1, 2])
def test_exact_candidates_and_formal_winding(direction, height, rotation):
    source = [
        Segment((-2, -1), (2, -1), 0),
        Segment((2, -1), (2, 1), 0),
        Segment((2, 1), (-2, 1), 0),
        Segment((-2, 1), (-2, -1), 0),
        Segment((5, 0), (5, 0), 1),
    ]
    source += [source[0], Segment(source[0].b, source[0].a, 1)]
    for _ in range(rotation):
        source = [Segment((-s.a[1], s.a[0]), (-s.b[1], s.b[0]), s.channel) for s in source]
    index = ClosedYIndex(source, Budget())
    ids = index.query(height)
    assert ids == tuple(
        i for i, s in enumerate(source) if min(s.a[1], s.b[1]) <= height <= max(s.a[1], s.b[1])
    )
    exact = tuple(faces.ExactSegment(tuple(map(F, s.a)), tuple(map(F, s.b)), s.channel) for s in source)
    dx, dy = direction
    # Irrationality is unnecessary: this authored rational X avoids every source line.
    edge = ((F(1, 7) - dx, height - dy), (F(1, 7) + dx, height + dy))
    selected = tuple(exact[i] for i in ids)
    try:
        expected = faces.winding(edge, exact, Budget())
    except GeometryError:
        with pytest.raises(GeometryError):
            faces.winding(edge, selected, Budget())
    else:
        assert faces.winding(edge, selected, Budget()) == expected


def test_gap_zero_spanners_duplicates_exact_fraction_and_bounds():
    source = [Segment((0, y), (1, y), 0) for y in (0, 0, 10, 10)]
    index = ClosedYIndex(source, Budget())
    assert index._root.center == F(5)
    assert index._root.low == ()
    assert index.query(F(0)) == (0, 1)
    assert index.query(F(10)) == (2, 3)
    assert index.query(F(1, 10**20)) == ()
    with pytest.raises(GeometryError, match="bit budget"):
        index.query(F(1, 2**300))
    with pytest.raises(GeometryError, match="rational"):
        index.query(0)
    with pytest.raises(GeometryError, match="tree-node"):
        ClosedYIndex(source, Budget(replace(Limits(), nodes=1)))
    with pytest.raises(GeometryError, match="bit budget"):
        ClosedYIndex([Segment((0, 2**300), (1, 2**300), 0)], Budget())


def test_construction_queries_share_visits_and_deadline():
    source = [Segment((0, 0), (1, 1), 0)]
    budget = Budget(replace(Limits(), winding_visits=5))
    index = ClosedYIndex(source, budget)
    assert index.query(F(0)) == (0,)
    with pytest.raises(GeometryError, match="visit budget"):
        index.query(F(0))
    now = [0.0]
    index = ClosedYIndex(source, Budget(clock=lambda: now[0]))
    now[0] = 1201
    with pytest.raises(ExactDeadline, match="deadline"):
        index.query(F(0))
