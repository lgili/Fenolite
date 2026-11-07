# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Selective snap rounding of exact selected loops (c0332 redesign)."""

from __future__ import annotations

from fractions import Fraction as F

import pytest

from fenolite.geometry.boolean import _exact_snap as snap
from fenolite.geometry.boolean._exact_faces import difference_loops
from fenolite.geometry.boolean._exact_noding import Budget, Segment, _q

Point = tuple[F, F]


def exact(*points: tuple[F | int, F | int]) -> tuple[Point, ...]:
    return tuple((F(x), F(y)) for x, y in points)


def ring_segments(points: list[tuple[int, int]], channel: int) -> list[Segment]:
    return [Segment(a, b, channel) for a, b in zip(points, [*points[1:], points[0]], strict=True)]


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (F(1, 2), 0),
        (F(3, 2), 2),
        (F(5, 2), 2),
        (F(-1, 2), 0),
        (F(-3, 2), -2),
        (F(2, 3), 1),
        (F(-2, 3), -1),
        (F(7), 7),
    ],
)
def test_half_even_breaks_ties_to_even(value: F, expected: int) -> None:
    assert snap.half_even(value) == expected


def test_hot_pixels_are_closed_for_even_and_open_for_odd_centres() -> None:
    vertical = exact((F(1, 2), -1), (F(1, 2), 1))
    assert snap.pixel_hit(*vertical, (0, 0)) is not None  # x = 1/2 rounds to 0
    assert snap.pixel_hit(*vertical, (1, 0)) is None
    for p in [(F(n, d), F(m, d)) for d in (1, 2, 3, 4) for n in range(-5, 6) for m in range(-5, 6)]:
        owners = [
            (x, y) for x in range(-6, 7) for y in range(-6, 7) if snap.pixel_hit(p, p, (x, y)) is not None
        ]
        assert owners == [snap.project(p)]


def test_integer_loops_are_drawn_unchanged_in_one_round() -> None:
    loop = exact((0, 0), (10, 0), (10, 10), (0, 10))
    drawing = snap.draw((loop,), Budget())
    assert drawing.rounds == 1 and drawing.bent == 0
    assert sorted(drawing.boundary) == [
        ((0, 0), (10, 0)),
        ((0, 10), (0, 0)),
        ((10, 0), (10, 10)),
        ((10, 10), (0, 10)),
    ]


def test_a_crossing_straight_drawing_bends_through_the_hot_pixel() -> None:
    # (3/10, 3/5) lies below the exact edge of the upper quad but rounds to (0, 1), above its straight
    # drawing from (-10, 0) to (10, 1): the straight drawings cross, so the upper edge is bent.
    upper = exact((-10, F(2, 5)), (10, F(9, 10)), (10, 20), (-10, 20))
    lower = exact((F(3, 10), F(3, 5)), (0, -5), (2, -5))
    drawing = snap.draw((upper, lower), Budget())
    assert drawing.rounds >= 2 and drawing.bent >= 1
    assert ((-10, 0), (0, 1)) in drawing.boundary and ((0, 1), (10, 1)) in drawing.boundary
    # the realized boundary has no crossing and unit currents
    current, _ = snap._planar([(a, b, (0, 0)) for a, b in drawing.boundary], Budget())
    assert set(current.values()) <= {-1, 1}
    # every bent vertex is a hot pixel met by its exact edge: within half a nanometre per axis
    assert snap.pixel_hit(upper[0], upper[1], (0, 1)) is not None


def test_a_sub_nanometre_source_corner_is_recorded_when_its_turn_vanishes() -> None:
    subject = ring_segments([(-4, 1), (0, 0), (4, 0), (4, 2), (-4, 2)], 0)
    cut = ring_segments([(-5, -5), (-1, -5), (-1, 5), (-5, 5)], 1) + ring_segments(
        [(1, -5), (5, -5), (5, 5), (1, 5)], 1
    )
    budget = Budget()
    loops = difference_loops(subject + cut, budget)
    protected = snap.protected_corners(loops, subject + cut)
    assert (0, 0) in protected  # the exact loop turns at (0, 0) by a quarter nanometre over one
    snapped = snap.snap_round(loops, protected, budget)
    assert snapped.erased == frozenset({(0, 0)})
    assert [(p.x, p.y) for poly in snapped.polygons for p in poly.outer] == [(-1, 0), (1, 0), (1, 2), (-1, 2)]


def test_merge_splits_seam_edges_and_cancels_opposite_currents() -> None:
    left = [((0, 0), (5, 0)), ((5, 0), (5, 10)), ((5, 10), (0, 10)), ((0, 10), (0, 0))]
    right = [((5, 0), (10, 0)), ((10, 0), (10, 10)), ((10, 10), (5, 10)), ((5, 10), (5, 3)), ((5, 3), (5, 0))]
    merged = snap.merge([left, right], [(0, 5)])
    snapped = snap.assemble(merged, frozenset(), Budget())
    assert [(p.x, p.y) for p in snapped.polygons[0].outer] == [(0, 0), (10, 0), (10, 10), (0, 10)]
    with pytest.raises(Exception, match="overlap"):
        snap.merge([left, left], [(0, 5)])


def test_node_coordinates_keep_fraction_value_hash_and_order() -> None:
    third = _q(F(1, 3))
    assert third == F(1, 3) and F(1, 3) == third and hash(third) == hash(F(1, 3))
    assert _q(2) == 2 and hash(_q(2)) == hash(2)
    assert sorted([_q(3), _q(F(1, 2)), _q(-1)]) == [-1, F(1, 2), 3]
    assert type(third + third) is F
