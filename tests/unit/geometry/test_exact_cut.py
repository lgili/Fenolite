# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Exact difference by groups and vertical strips, realized on integers (c0332 redesign)."""

from __future__ import annotations

from fractions import Fraction

import pytest

from fenolite.geometry.boolean import _exact_cut as cut
from fenolite.geometry.boolean._exact_noding import Budget
from fenolite.geometry.errors import GeometryError
from fenolite.geometry.polygon import Polygon
from fenolite.geometry.vector import Point


def rectangle(x0: int, y0: int, x1: int, y1: int) -> Polygon:
    return Polygon((Point(x0, y0), Point(x1, y0), Point(x1, y1), Point(x0, y1)))


def diamond(cx: int, cy: int, r: int) -> Polygon:
    return Polygon((Point(cx, cy - r), Point(cx + r, cy), Point(cx, cy + r), Point(cx - r, cy)))


def test_groups_without_a_cut_are_kept_as_they_are() -> None:
    far = rectangle(1000, 0, 1010, 10)
    result = cut.exact_difference((rectangle(0, 0, 10, 10), far), (rectangle(2, 2, 8, 8),), Budget())
    assert result.groups == 1 and far in result.polygons
    holed = next(p for p in result.polygons if p.holes)
    assert holed.area2 == 2 * (100 - 36)


def test_clip_keeps_exact_rational_seam_points() -> None:
    triangle = [(0, 0), (3, 1), (0, 2)]
    assert cut._clip(triangle, None, 1) == [(0, 0), (1, Fraction(1, 3)), (1, Fraction(5, 3)), (0, 2)]
    assert cut._clip(triangle, 4, None) == []
    assert cut._clip(triangle, 1, None, axis=1) == [(0, 1), (3, 1), (0, 2)]


def test_cells_split_on_both_axes_and_avoid_vertex_coordinates() -> None:
    wide = [(-1000, -5), (1000, -5), (1000, 5), (-1000, 5)]  # a cut piece across every x seam
    comb = [[(x, -100), (x + 3, -100), (x + 3, 100), (x, 100)] for x in range(-900, 900, 20)]
    rings = [(r, 0) for r in comb] + [(wide, 1)]
    seams: set[tuple[int, int]] = set()
    cells = cut._cells(rings, 40, seams)
    assert len(cells) > 1 and all(sum(len(r) for r, _ in c) <= 40 for c in cells)
    vertices = {p for r, _ in rings for p in r}
    assert all(all(p[axis] != v for p in vertices) for axis, v in seams)


def test_cells_give_the_same_polygons_as_one_arrangement() -> None:
    subject = [diamond(50 * k, 0, 40) for k in range(6)] + [rectangle(-40, -3, 290, 3)]
    pieces = [diamond(50 * k + 7, 1, 9) for k in range(6)] + [
        rectangle(50 * k + 20, -30, 50 * k + 23, 30) for k in range(5)
    ]
    whole = cut.exact_difference(subject, pieces, Budget())
    split = cut.exact_difference(subject, pieces, Budget(), strip_edges=12)
    assert whole.strips == 1 and split.strips > 1
    assert split.polygons == whole.polygons


def test_a_group_no_seam_reduces_refuses_above_the_input_cap() -> None:
    with pytest.raises(GeometryError, match="input-edge budget"):
        cut.exact_difference((rectangle(0, 0, 10, 10),) * 25_001, (rectangle(-1, -1, 11, 11),), Budget())
