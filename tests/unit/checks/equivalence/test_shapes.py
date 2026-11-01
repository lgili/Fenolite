# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The normalisation of level 7 (capability design-equivalence, "Level 7 normalisation"; change c0278)."""

from __future__ import annotations

from fenolite.checks.equivalence.shapes import arc, circle, doubled_area, graphic_points, ring, segment
from fenolite.core.coords import Point
from fenolite.model.board import Graphic

SQUARE = (Point(0, 0), Point(10, 0), Point(10, 10), Point(0, 10))


def test_a_ring_has_one_form() -> None:
    expected = ring(SQUARE)
    assert [vertex for vertex, _ in expected][0] == Point(0, 0)
    assert doubled_area([vertex for vertex, _ in expected]) > 0
    clockwise = tuple(reversed(SQUARE))
    for other in (clockwise, SQUARE[2:] + SQUARE[:2], clockwise[1:] + clockwise[:1], (*SQUARE, SQUARE[0])):
        assert ring(other) == expected


def test_a_reversed_ring_keeps_its_arcs_on_their_edges() -> None:
    """Edge 1 (from (10, 0) to (10, 10)) bulges out through (12, 5); drawn the other way the mid stays on
    the edge between the same two vertices."""
    one = ring(SQUARE, {1: Point(12, 5)})
    clockwise = (Point(0, 10), Point(10, 10), Point(10, 0), Point(0, 0))
    other = ring(clockwise, {1: Point(12, 5)})
    assert one == other
    assert dict(one)[Point(10, 0)] == Point(12, 5)


def test_a_circle_of_two_arcs() -> None:
    a = ring((Point(-5, 0), Point(5, 0)), {0: Point(0, -5), 1: Point(0, 5)})
    b = ring((Point(5, 0), Point(-5, 0)), {0: Point(0, 5), 1: Point(0, -5)})
    assert a == b


def test_segments_arcs_circles() -> None:
    assert (
        segment(Point(5, 5), Point(0, 0)) == segment(Point(0, 0), Point(5, 5)) == (Point(0, 0), Point(5, 5))
    )
    assert arc(Point(5, 0), Point(3, 3), Point(0, 0)) == (Point(0, 0), Point(3, 3), Point(5, 0))
    assert circle(Point(0, 0), Point(3, 4)) == (Point(0, 0), 25)


def test_a_rectangle_is_its_ring() -> None:
    rect = Graphic(id="gfx-1", kind="rect", layer="F.SilkS", points=(Point(10, 10), Point(0, 0)))
    polygon = Graphic(id="gfx-2", kind="polygon", layer="F.SilkS", points=SQUARE)
    assert graphic_points(rect) == graphic_points(polygon)
