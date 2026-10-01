# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Closed integer boxes and segments (capability geometry-kernel)."""

from __future__ import annotations

import pytest
from hypothesis import given
from strategies import small_points

from fenolite.geometry import BBox, Point, Segment


def test_touching_boxes_intersect() -> None:
    assert BBox(0, 0, 10, 10).intersects(BBox(10, 0, 20, 10))
    assert BBox(0, 0, 10, 10).intersects(BBox(10, 10, 20, 20))
    assert not BBox(0, 0, 10, 10).intersects(BBox(11, 0, 20, 10))


def test_inverted_box_rejected() -> None:
    with pytest.raises(ValueError):
        BBox(10, 0, 0, 10)


def test_over_deflation_rejected() -> None:
    assert BBox(0, 0, 10, 10).inflate(-5) == BBox(5, 5, 5, 5)
    with pytest.raises(ValueError):
        BBox(0, 0, 10, 10).inflate(-6)


def test_box_operations() -> None:
    box = BBox.of_points([Point(3, 4), Point(-1, 7), Point(2, -2)])
    assert box == BBox(-1, -2, 3, 7)
    assert (box.width, box.height) == (4, 9)
    assert box.union(BBox(10, 10, 11, 11)) == BBox(-1, -2, 11, 11)
    assert box.contains_point(Point(3, 7)) and not box.contains_point(Point(4, 7))
    assert box.contains_bbox(BBox(0, 0, 3, 7)) and not box.contains_bbox(BBox(0, 0, 4, 7))
    assert box.inflate(2) == BBox(-3, -4, 5, 9)
    assert box.as_tuple() == (-1, -2, 3, 7)


def test_empty_and_float_rejected() -> None:
    with pytest.raises(ValueError):
        BBox.of_points([])
    with pytest.raises(TypeError, match="x1"):
        BBox(0, 0, 1.5, 2)  # type: ignore[arg-type]


@given(small_points, small_points, small_points)
def test_union_contains_both(a: Point, b: Point, c: Point) -> None:
    first, second = BBox.of_points([a, b]), BBox.of_points([c])
    union = first.union(second)
    assert union.contains_bbox(first) and union.contains_bbox(second)
    assert first.intersects(second) == second.intersects(first)


def test_segment() -> None:
    s = Segment(Point(0, 0), Point(3, 4))
    assert s.length2 == 25
    assert not s.is_degenerate
    assert s.bbox() == BBox(0, 0, 3, 4)
    assert s.reversed() == Segment(Point(3, 4), Point(0, 0))
    assert (s.start, s.end) == (s.a, s.b)
    assert Segment(Point(1, 1), Point(1, 1)).is_degenerate
    with pytest.raises(TypeError, match=r"\bb\b"):
        Segment(Point(0, 0), (1, 1))  # type: ignore[arg-type]
