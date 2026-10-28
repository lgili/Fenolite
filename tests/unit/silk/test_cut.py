# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""``fenolite.silk.cut`` (change c0226; capability silkscreen-layout, "Silkscreen clipping", scenario
"Pieces of a line, an arc and a circle"). The openings are written out here as thick shapes; the
expected cut ends are worked out by hand from the reach ``margin + 1 µm + width / 2``."""

from __future__ import annotations

from math import isqrt

import pytest

from fenolite.core.coords import Point
from fenolite.geometry import Thick, thick_closer_than
from fenolite.silk.cut import GUARD, Cut, Piece, cut, piece_shape

MM = 1_000_000
UM = 1_000
WIDTH = 100 * UM
MARGIN = 100 * UM
PAD = Thick((Point(4 * MM, -MM), Point(6 * MM, -MM), Point(6 * MM, MM), Point(4 * MM, MM)), 0, filled=True)
"""A pad of 2 mm x 2 mm from x = 4 mm to 6 mm."""


def _clear(result: Cut, openings: list[Thick], margin: int = MARGIN) -> None:
    for piece in result.pieces:
        shape = piece_shape(piece, WIDTH)
        assert not any(thick_closer_than(shape, opening, margin) for opening in openings), piece


def test_line_cut_at_the_reach() -> None:
    result = cut("line", (Point(0, 0), Point(10 * MM, 0)), WIDTH, [PAD], MARGIN)
    assert result is not None and result.dropped == 0
    reach = MARGIN + GUARD + WIDTH // 2
    (a, b), (c, d) = (piece.points for piece in result.pieces)
    assert a == Point(0, 0) and d == Point(10 * MM, 0)
    assert abs(b.x - (4 * MM - reach)) <= 1 and abs(c.x - (6 * MM + reach)) <= 1
    _clear(result, [PAD])


def test_untouched_stroke_is_none() -> None:
    assert cut("line", (Point(0, 2 * MM), Point(10 * MM, 2 * MM)), WIDTH, [PAD], MARGIN) is None
    assert cut("line", (Point(0, 2 * MM), Point(10 * MM, 2 * MM)), WIDTH, [], MARGIN) is None


def test_short_piece_is_dropped() -> None:
    # the line starts 50 µm before the reach of the pad: that stub is shorter than its stroke
    reach = MARGIN + GUARD + WIDTH // 2
    start = Point(4 * MM - reach - 50 * UM, 0)
    result = cut("line", (start, Point(8 * MM, 0)), WIDTH, [PAD], MARGIN)
    assert result is not None and result.dropped == 1
    assert [piece.points[1] for piece in result.pieces] == [Point(8 * MM, 0)]
    _clear(result, [PAD])


def _radius_error(piece: Piece, centre: Point, radius: int) -> int:
    worst = 0
    for p in piece.points:
        dx, dy = p.x - centre.x, p.y - centre.y
        worst = max(worst, abs(isqrt(dx * dx + dy * dy) - radius))
    return worst


def test_arc_pieces_lie_on_the_circle() -> None:
    hole = Thick((Point(0, -5 * MM),), MM)
    arc = (Point(-5 * MM, 0), Point(0, -5 * MM), Point(5 * MM, 0))
    result = cut("arc", arc, WIDTH, [hole], MARGIN)
    assert result is not None and len(result.pieces) == 2
    assert all(piece.kind == "arc" for piece in result.pieces)
    assert result.pieces[0].points[0] == arc[0] and result.pieces[1].points[2] == arc[2]
    assert all(_radius_error(piece, Point(0, 0), 5 * MM) <= 2 for piece in result.pieces)
    _clear(result, [hole])
    # the cut ends lie within 2 µm of where the reach meets the circle
    reach = MARGIN + GUARD + WIDTH // 2 + MM // 2
    for end in (result.pieces[0].points[2], result.pieces[1].points[0]):
        gap = isqrt(end.x**2 + (end.y + 5 * MM) ** 2)
        assert reach <= gap <= reach + 2 * UM, gap


def test_circle_cut_once_is_one_arc() -> None:
    # the opening sits on the first vertex of the circle's polygon: the kept run wraps over it
    hole = Thick((Point(2 * MM, 0),), 400 * UM)
    result = cut("circle", (Point(0, 0), Point(2 * MM, 0)), WIDTH, [hole], MARGIN)
    assert result is not None and len(result.pieces) == 1 and result.pieces[0].kind == "arc"
    assert _radius_error(result.pieces[0], Point(0, 0), 2 * MM) <= 2
    _clear(result, [hole])


def test_rectangle_outline_cut_into_lines() -> None:
    result = cut("rect", (Point(3 * MM, -500 * UM), Point(7 * MM, 500 * UM)), WIDTH, [PAD], MARGIN)
    assert result is not None and result.pieces
    assert all(piece.kind == "line" for piece in result.pieces)
    assert len(result.pieces) == 6  # the two short sides whole, each long side cut in two by the pad
    _clear(result, [PAD])


@pytest.mark.parametrize("kind", ["rect", "polygon", "circle"])
def test_filled_shape_is_skipped(kind: str) -> None:
    points = {
        "rect": (Point(3 * MM, -500 * UM), Point(5 * MM, 500 * UM)),
        "polygon": (Point(3 * MM, 0), Point(5 * MM, -500 * UM), Point(5 * MM, 500 * UM)),
        "circle": (Point(3 * MM, 0), Point(4 * MM, 0)),
    }[kind]
    assert cut(kind, points, WIDTH, [PAD], MARGIN, filled=True) == Cut((), skipped=True)  # type: ignore[arg-type]
    far = tuple(Point(p.x, p.y + 10 * MM) for p in points)
    assert cut(kind, far, WIDTH, [PAD], MARGIN, filled=True) is None  # type: ignore[arg-type]
