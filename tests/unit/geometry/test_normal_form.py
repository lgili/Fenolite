# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Canonical form of polygon sets (capability geometry-kernel)."""

from __future__ import annotations

from hypothesis import given, settings
from hypothesis import strategies as st
from strategies import rings

from fenolite.geometry import Point, Polygon, normalize_polygons

P = Point


def ring(*pairs: tuple[int, int]) -> tuple[Point, ...]:
    return tuple(P(x, y) for x, y in pairs)


def test_corner_touching_squares() -> None:
    poly = Polygon(ring((0, 0), (10, 0), (10, 10), (20, 10), (20, 20), (10, 20), (10, 10), (0, 10)))
    assert normalize_polygons([poly]) == (
        Polygon(ring((0, 0), (10, 0), (10, 10), (0, 10))),
        Polygon(ring((10, 10), (20, 10), (20, 20), (10, 20))),
    )


def test_hole_touching_the_shell() -> None:
    poly = Polygon(ring((0, 0), (30, 0), (30, 30), (0, 30), (0, 15), (10, 20), (10, 10), (0, 15)))
    (result,) = normalize_polygons([poly])
    assert result.outer == ring((0, 0), (30, 0), (30, 30), (0, 30))
    assert result.holes == (ring((0, 15), (10, 20), (10, 10)),)


def test_pinch_at_the_first_vertex() -> None:
    poly = Polygon(ring((10, 10), (20, 10), (20, 20), (10, 20), (10, 10), (0, 10), (0, 0), (10, 0)))
    assert normalize_polygons([poly]) == (
        Polygon(ring((0, 0), (10, 0), (10, 10), (0, 10))),
        Polygon(ring((10, 10), (20, 10), (20, 20), (10, 20))),
    )


def test_negative_input_orientation_and_hole_orientation() -> None:
    outer = ring((0, 30), (30, 30), (30, 0), (0, 0))  # negative orientation
    hole = ring((10, 10), (20, 10), (20, 20), (10, 20))  # same sign as a shell would have
    (result,) = normalize_polygons([Polygon(outer, (hole,))])
    assert result.outer == ring((0, 0), (30, 0), (30, 30), (0, 30))
    assert result.holes == (ring((10, 10), (10, 20), (20, 20), (20, 10)),)
    assert result.area2 == 2 * (900 - 100)


def test_holes_go_to_their_part() -> None:
    # Two squares touching at a corner, each with a hole: the holes follow their containing square.
    outer = ring((0, 0), (10, 0), (10, 10), (20, 10), (20, 20), (10, 20), (10, 10), (0, 10))
    holes = (ring((12, 12), (12, 18), (18, 18), (18, 12)), ring((2, 2), (2, 8), (8, 8), (8, 2)))
    first, second = normalize_polygons([Polygon(outer, holes)])
    assert first.holes == (ring((2, 2), (2, 8), (8, 8), (8, 2)),)
    assert second.holes == (ring((12, 12), (12, 18), (18, 18), (18, 12)),)


def test_sort_key() -> None:
    a = Polygon(ring((0, 0), (10, 0), (10, 10), (0, 10)))
    b = Polygon(ring((0, 0), (10, 0), (0, 5)))
    c = Polygon(ring((-5, 3), (0, 3), (0, 8)))
    assert normalize_polygons([a, b, c]) == (c, b, a)


def test_idempotent_on_normal_form() -> None:
    result = normalize_polygons([Polygon(ring((0, 10), (10, 10), (10, 0), (0, 0)))])
    assert normalize_polygons(result) == result


@settings(max_examples=100)
@given(st.lists(rings(), min_size=1, max_size=5), st.randoms(use_true_random=False))
def test_order_independence(shapes: list[tuple[Point, ...]], rnd: object) -> None:
    import random

    assert isinstance(rnd, random.Random)
    polys = [Polygon(r if i % 2 else tuple(reversed(r))) for i, r in enumerate(shapes)]
    shuffled = list(polys)
    rnd.shuffle(shuffled)
    rotated = [Polygon(p.outer[1:] + p.outer[:1]) for p in shuffled]
    expected = normalize_polygons(polys)
    assert normalize_polygons(shuffled) == expected
    assert normalize_polygons(rotated) == expected
    assert all(p.outer[0] == min(p.outer) and p.area2 > 0 for p in expected)
