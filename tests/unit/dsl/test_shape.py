# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""``fenolite.dsl.shape``: ``rect``, ``circle`` and ``slot`` (capability design-dsl, "Outline shapes in the
DSL"; change c0102). Every rounded coordinate is compared with an exact computation: the square of the
error is bounded with ``Fraction``, so no float decides a result."""

from __future__ import annotations

from fractions import Fraction

import pytest

from fenolite.core.coords import Point
from fenolite.dsl import ArcStep, Design, DslError, mm, nm, shape, to_model
from fenolite.dsl.shape import round_root
from fenolite.geometry import Transform
from fenolite.model.board import OutlineArc

MM = 1_000_000
ORIGIN = 100 * MM


def at(x: float, y: float) -> Point:
    return Point(round((100 + x) * MM), round((100 + y) * MM))


def model_outline(outline: object, *cutouts: object):  # type: ignore[no-untyped-def]
    design = Design("shapes")
    if outline is None:
        design.board(mm(60), mm(40))
    else:
        design.board(outline=outline)
    for path in cutouts:
        design.cutout(path)
    found = to_model(design).board.outline  # type: ignore[union-attr]
    assert found is not None
    return found


def nearest(value_squared: Fraction, found: int) -> bool:
    """Whether ``found`` (at least 0) is ``sqrt(value_squared)`` rounded half to even: the true value lies
    within one half of it, and on a tie ``found`` is even."""
    low, high = Fraction(2 * found - 1, 2), Fraction(2 * found + 1, 2)
    if found == 0:
        return value_squared <= high**2
    inside = low**2 <= value_squared <= high**2
    tie = value_squared in (low**2, high**2)
    return inside and (not tie or found % 2 == 0)


# --- round_root ----------------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("p", "q", "expected"),
    [(0, 1, 0), (1, 1, 1), (2, 1, 1), (9, 4, 2), (25, 4, 2), (49, 4, 4), (27, 4, 3), (23, 4, 2), (1, 4, 0)],
)
def test_round_root_rounds_half_to_even(p: int, q: int, expected: int) -> None:
    assert round_root(p, q) == expected
    assert nearest(Fraction(p, q), expected)


def test_round_root_over_a_range_is_the_nearest_integer() -> None:
    for p in range(0, 400):
        for q in (1, 2, 3, 4, 7, 9, 16):
            assert nearest(Fraction(p, q), round_root(p, q)), (p, q)
    with pytest.raises(ValueError, match="q > 0"):
        round_root(1, 0)


# --- rect ----------------------------------------------------------------------------------------------


def test_rect_without_a_radius_is_the_board_rectangle() -> None:
    outline = model_outline(shape.rect(mm(0), mm(0), mm(60), mm(40)))
    assert outline.points == (at(0, 0), at(60, 0), at(60, 40), at(0, 40)) and outline.arcs == ()
    assert outline == model_outline(None)  # the rectangle of board(width, height)


def test_rounded_corners() -> None:
    outline = model_outline(shape.rect(mm(0), mm(0), mm(60), mm(40), radius=mm(3)))
    assert len(outline.points) == 8
    assert outline.points[:3] == (at(3, 0), at(57, 0), at(60, 3))
    assert outline.arcs[0] == OutlineArc(0, 1, Point(159_121_320, 100_878_680))
    assert [(arc.ring, arc.edge) for arc in outline.arcs] == [(0, 1), (0, 3), (0, 5), (0, 7)]


@pytest.mark.parametrize("radius", [1, 2, 3, 1_000, 123_457, 3_000_000, 2_999_999, 7_654_321])
def test_every_corner_mid_is_the_exact_point_rounded(radius: int) -> None:
    size = 20 * MM
    path = shape.rect(nm(0), nm(0), nm(size), nm(size), radius=nm(radius))
    mids = [step.mid for step in path if isinstance(step, ArcStep)]
    centres = [
        (size - radius, radius),
        (size - radius, size - radius),
        (radius, size - radius),
        (radius, radius),
    ]
    signs = [(1, -1), (1, 1), (-1, 1), (-1, -1)]
    assert len(mids) == 4
    for mid, (cx, cy), (sx, sy) in zip(mids, centres, signs, strict=True):
        dx, dy = (mid.x - ORIGIN - cx) * sx, (mid.y - ORIGIN - cy) * sy
        assert dx == dy and nearest(Fraction(radius * radius, 2), dx)


def test_a_radius_of_half_a_side_leaves_the_zero_edges_out() -> None:
    outline = model_outline(shape.rect(mm(0), mm(0), mm(10), mm(6), radius=mm(3)))
    # the left and right edges have length 0: a stadium of six vertices
    assert len(outline.points) == 6 and len(outline.arcs) == 4
    square = model_outline(shape.rect(mm(0), mm(0), mm(6), mm(6), radius=mm(3)))
    assert len(square.points) == 4 and len(square.arcs) == 4  # a circle of four quarter arcs


def test_refused_rects() -> None:
    for call in (
        lambda: shape.rect(mm(0), mm(0), mm(0), mm(5)),
        lambda: shape.rect(mm(0), mm(0), mm(5), mm(-1)),
        lambda: shape.rect(mm(0), mm(0), mm(10), mm(6), radius=mm(3.1)),
        lambda: shape.rect(mm(0), mm(0), mm(10), mm(6), radius=mm(0)),
        lambda: shape.rect(mm(0), mm(0), 10, mm(6)),
    ):
        with pytest.raises(DslError, match=r"shape\.rect\(\)"):
            call()


# --- circle --------------------------------------------------------------------------------------------


def test_a_round_cutout() -> None:
    outline = model_outline(None, shape.circle(mm(10), mm(10), mm(3.2)))
    assert outline.cutouts == ((at(11.6, 10), at(8.4, 10)),)
    assert outline.arcs == (
        OutlineArc(1, 0, Point(110_000_000, 108_400_000)),
        OutlineArc(1, 1, Point(110_000_000, 111_600_000)),
    )


def test_refused_circles() -> None:
    for diameter in (nm(3), mm(0), mm(-2)):
        with pytest.raises(DslError, match=r"shape\.circle\(\): diameter"):
            shape.circle(mm(5), mm(5), diameter)


# --- slot ----------------------------------------------------------------------------------------------


def test_a_horizontal_slot() -> None:
    outline = model_outline(None, shape.slot((mm(10), mm(20)), (mm(20), mm(20)), mm(2)))
    assert outline.cutouts == ((at(10, 19), at(20, 19), at(20, 21), at(10, 21)),)
    assert outline.arcs == (OutlineArc(1, 1, at(21, 20)), OutlineArc(1, 3, at(9, 20)))


def test_a_vertical_slot_is_exact() -> None:
    outline = model_outline(None, shape.slot((mm(10), mm(10)), (mm(10), mm(20)), mm(2)))
    assert outline.cutouts == ((at(11, 10), at(11, 20), at(9, 20), at(9, 10)),)
    assert outline.arcs == (OutlineArc(1, 1, at(10, 21)), OutlineArc(1, 3, at(10, 9)))


def test_a_slot_at_30_degrees_agrees_with_the_placement_transform() -> None:
    """A slot of 12 × 1.5 mm turned 30°: each point within 1 nm of the horizontal slot's point moved by
    ``Transform.placement``, the transform of a placed footprint."""
    half_run = 5_250_000  # the centres lie 10.5 mm apart: 12 mm overall less the width
    turn = Transform.placement(Point(0, 0), 30_000_000)
    start, end = turn.apply(Point(-half_run, 0)), turn.apply(Point(half_run, 0))
    path = shape.slot((nm(start.x), nm(start.y)), (nm(end.x), nm(end.y)), mm(1.5))
    flat = shape.slot((nm(-half_run), nm(0)), (nm(half_run), nm(0)), mm(1.5))

    def points(found: object) -> list[Point]:
        out: list[Point] = []
        for element in found:  # type: ignore[attr-defined]
            if isinstance(element, ArcStep):
                out += [element.mid, element.end]
            else:
                out.append(Point(ORIGIN + element[0].nm, ORIGIN + element[1].nm))
        return out

    for turned, straight in zip(points(path), points(flat), strict=True):
        wanted = turn.apply(Point(straight.x - ORIGIN, straight.y - ORIGIN))
        # the centres themselves were rounded once by the transform: one more nanometre of slack
        assert abs(turned.x - ORIGIN - wanted.x) <= 2 and abs(turned.y - ORIGIN - wanted.y) <= 2


@pytest.mark.parametrize(("dx", "dy"), [(3, 4), (10_000_000, 1), (1, 10_000_000), (-7_000_001, 2_999_999)])
def test_every_slot_point_is_the_exact_point_rounded(dx: int, dy: int) -> None:
    width = 1_500_000
    half = width // 2
    path = shape.slot((nm(0), nm(0)), (nm(dx), nm(dy)), nm(width))
    length2 = dx * dx + dy * dy
    first = path[0]
    assert not isinstance(first, ArcStep)
    # the first vertex is start − h·n with n = (−u_y, u_x): (h·dy/L, −h·dx/L)
    assert nearest(Fraction((half * dy) ** 2, length2), abs(first[0].nm))
    assert nearest(Fraction((half * dx) ** 2, length2), abs(first[1].nm))
    assert (first[0].nm >= 0) == (dy >= 0) or first[0].nm == 0
    assert (first[1].nm <= 0) == (dx >= 0) or first[1].nm == 0


def test_refused_slots() -> None:
    for call in (
        lambda: shape.slot((mm(1), mm(1)), (mm(1), mm(1)), mm(1)),
        lambda: shape.slot((mm(1), mm(1)), (mm(5), mm(1)), nm(3)),
        lambda: shape.slot((mm(1), mm(1)), (mm(5), mm(1)), mm(0)),
        lambda: shape.slot((mm(1),), (mm(5), mm(1)), mm(1)),
        lambda: shape.slot((1, 1), (mm(5), mm(1)), mm(1)),
    ):
        with pytest.raises(DslError, match=r"shape\.slot\(\)"):
            call()


def test_the_helpers_return_plain_paths() -> None:
    for path in (
        shape.rect(mm(0), mm(0), mm(6), mm(4), radius=mm(1)),
        shape.circle(mm(5), mm(5), mm(2)),
        shape.slot((mm(1), mm(1)), (mm(5), mm(1)), mm(1)),
    ):
        assert isinstance(path, tuple) and not isinstance(path[0], ArcStep)
        assert all(isinstance(e, ArcStep) or (isinstance(e, tuple) and len(e) == 2) for e in path)
