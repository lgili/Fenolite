# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Thick shapes and exact gaps (capability geometry-kernel, "Thick shapes" and "Exact gaps between thick
shapes"; change c0029)."""

from __future__ import annotations

import ast
from fractions import Fraction
from pathlib import Path

import pytest
from _coppercheck import thick_cases

import fenolite.geometry.thick as thick_module
from fenolite.core.coords import Point
from fenolite.geometry import (
    BBox,
    GeometryError,
    Location,
    Thick,
    dist2_point_segment,
    dist2_segment_segment,
    floor_sqrt,
    point_in_ring,
    thick_bbox,
    thick_closer_than,
    thick_gap_floor,
    thick_touch,
    thick_witness,
)

SQUARE = Thick((Point(0, 0), Point(100, 0), Point(100, 100), Point(0, 100)), 0, filled=True)


# --- shapes ---------------------------------------------------------------------------------------


def test_shapes_built() -> None:
    disc = Thick((Point(0, 0),), 600_000)
    stadium = Thick((Point(0, 0), Point(10, 0)), 250_000)
    triangle = Thick((Point(0, 0), Point(100, 0), Point(100, 100)), 0, filled=True)
    assert thick_bbox(disc) == BBox(-300_000, -300_000, 300_000, 300_000)
    assert thick_bbox(stadium) == BBox(-125_000, -125_000, 125_010, 125_000)
    assert thick_bbox(triangle) == BBox(0, 0, 100, 100)
    assert not disc.filled and not stadium.filled and triangle.filled


def test_bbox_rounds_a_half_width_up() -> None:
    assert thick_bbox(Thick((Point(0, 0),), 5)) == BBox(-3, -3, 3, 3)


def test_degenerate_shapes_refused() -> None:
    for build in (
        lambda: Thick((Point(0, 0),), 0),
        lambda: Thick((), 5),
        lambda: Thick((Point(0, 0), Point(1, 1), Point(2, 2)), 0, filled=True),
        lambda: Thick((Point(0, 0), Point(1, 1)), 0, filled=True),
    ):
        with pytest.raises(GeometryError) as caught:
            build()
        assert caught.value.code == "geometry.degenerate"
    with pytest.raises(ValueError, match="at least 0"):
        Thick((Point(0, 0),), -1)
    with pytest.raises(ValueError, match="at least 0"):
        Thick((), -1)  # the width is checked first
    with pytest.raises(ValueError):
        Thick((Point(0, 0),), 2.0)  # type: ignore[arg-type]


def test_zero_width_line_is_a_shape() -> None:
    line = Thick((Point(0, 0), Point(10, 0)), 0)
    assert thick_touch(line, Thick((Point(5, 0),), 1))
    assert not thick_touch(line, Thick((Point(5, 1),), 1))


def test_shapes_are_values() -> None:
    a, b = Thick((Point(0, 0), Point(5, 5)), 3), Thick((Point(0, 0), Point(5, 5)), 3)
    thick_touch(a, SQUARE)  # fills the lazy fields of ``a`` only
    assert a == b and hash(a) == hash(b)
    assert "Point" in repr(a) and "_pieces" not in repr(a)


# --- gaps -----------------------------------------------------------------------------------------


def test_parallel_tracks() -> None:
    a = Thick((Point(0, 0), Point(10, 0)), 2)
    b = Thick((Point(0, 5), Point(10, 5)), 2)
    assert not thick_touch(a, b)
    assert not thick_closer_than(a, b, 3)
    assert thick_closer_than(a, b, 4)
    assert thick_gap_floor(a, b) == 3
    assert thick_witness(a, b).y in (2, 3)
    assert thick_witness(a, b) == thick_witness(b, a)


def test_half_nanometre_radii_touch_exactly() -> None:
    a = Thick((Point(0, 0),), 5)
    assert thick_touch(a, Thick((Point(0, 5),), 5))
    far = Thick((Point(0, 6),), 5)
    assert not thick_touch(a, far)
    assert thick_gap_floor(a, far) == 1
    assert thick_gap_floor(a, Thick((Point(0, 5),), 5)) == 0


def test_point_inside_a_filled_ring() -> None:
    inside = Thick((Point(50, 50),), 2)
    outside = Thick((Point(150, 50),), 20)
    assert thick_touch(SQUARE, inside) and thick_touch(inside, SQUARE)
    assert thick_gap_floor(SQUARE, inside) == 0
    assert thick_witness(SQUARE, inside) == Point(50, 50)
    assert not thick_touch(SQUARE, outside)
    assert not thick_closer_than(SQUARE, outside, 40)
    assert thick_closer_than(SQUARE, outside, 41)
    assert thick_gap_floor(SQUARE, outside) == 40
    assert thick_witness(SQUARE, outside) == Point(125, 50)


def test_hole_of_a_fractured_ring_is_outside() -> None:
    """A ring that walks out to a hole and back encloses nothing inside the hole (non-zero rule)."""
    fractured = Thick(
        (
            Point(0, 0),
            Point(100, 0),
            Point(100, 100),
            Point(0, 100),
            Point(0, 0),
            Point(40, 40),
            Point(40, 60),
            Point(60, 60),
            Point(60, 40),
            Point(40, 40),
        ),
        0,
        filled=True,
    )
    assert not thick_touch(fractured, Thick((Point(50, 50),), 2))
    assert thick_gap_floor(fractured, Thick((Point(50, 50),), 2)) == 9
    assert thick_touch(fractured, Thick((Point(20, 50),), 2))


def test_ring_inside_a_ring() -> None:
    inner = Thick((Point(40, 40), Point(60, 40), Point(60, 60), Point(40, 60)), 0, filled=True)
    assert thick_touch(SQUARE, inner) and thick_touch(inner, SQUARE)
    assert thick_witness(SQUARE, inner) == thick_witness(inner, SQUARE) == Point(40, 40)


def test_limit_is_checked() -> None:
    a = Thick((Point(0, 0),), 2)
    with pytest.raises(ValueError):
        thick_closer_than(a, a, -1)
    assert not thick_closer_than(a, Thick((Point(2, 0),), 2), 0)  # touching: the gap is 0, not below 0
    assert thick_closer_than(a, Thick((Point(1, 0),), 2), 0)  # overlapping: the gap is negative


def test_witness_of_crossing_and_collinear_cores() -> None:
    a = Thick((Point(0, 0), Point(10, 10)), 2)
    assert thick_witness(a, Thick((Point(0, 10), Point(10, 0)), 2)) == Point(5, 5)
    assert thick_witness(a, Thick((Point(4, 4), Point(20, 20)), 2)) == Point(4, 4)
    assert thick_witness(Thick((Point(0, 0),), 4), Thick((Point(10, 0),), 4)) == Point(5, 0)


# --- agreement with exact brute force -------------------------------------------------------------


def _pieces(t: Thick) -> list[tuple[Point, Point]]:
    core = t.core
    if len(core) == 1:
        return [(core[0], core[0])]
    last = len(core) if t.filled else len(core) - 1
    return [(core[i], core[(i + 1) % len(core)]) for i in range(last)]


def brute_dist2(a: Thick, b: Thick) -> Fraction:
    """The squared distance of the two cores, over every pair of core pieces."""
    if a.filled and point_in_ring(b.core[0], a.core) != Location.OUTSIDE:
        return Fraction(0)
    if b.filled and point_in_ring(a.core[0], b.core) != Location.OUTSIDE:
        return Fraction(0)
    best: Fraction | None = None
    for p, q in _pieces(a):
        for r, s in _pieces(b):
            found = dist2_point_segment(p, r, s) if p == q else dist2_segment_segment(p, q, r, s)
            best = found if best is None or found < best else best
    assert best is not None
    return best


def test_brute_force_agreement() -> None:
    cases = thick_cases()
    touching = closer = 0
    for a, b in cases:
        quadruple = 4 * brute_dist2(a, b)
        total = a.width + b.width
        touch = quadruple <= total * total
        assert thick_touch(a, b) is touch
        assert thick_touch(b, a) is touch
        floor = thick_gap_floor(a, b)
        assert type(floor) is int and floor == thick_gap_floor(b, a)
        if touch:
            assert floor == 0
        else:
            assert (2 * floor + total) ** 2 <= quadruple < (2 * floor + 2 + total) ** 2
        for limit in (0, 1, floor, floor + 1, 200_000):
            expected = quadruple < (2 * limit + total) ** 2
            assert thick_closer_than(a, b, limit) is expected
            assert thick_closer_than(b, a, limit) is expected
        witness = thick_witness(a, b)
        assert type(witness) is Point and type(witness.x) is int and type(witness.y) is int
        assert witness == thick_witness(b, a)
        touching += touch
        closer += not touch and floor < 200_000
    assert touching > 100 and closer > 50 and len(cases) - touching > 300


def test_brute_force_witness_lies_between_the_cores() -> None:
    """The witness is the rounded midpoint of a closest pair, so it lies within half the core distance,
    plus one nanometre of rounding, of each core: ``dist² ≤ (d / 2 + 1)²``, bounded with ``d ≤ ⌊d⌋ + 1``."""
    for a, b in thick_cases(count=300, seed=7):
        witness = Thick((thick_witness(a, b),), 2)
        dist2 = brute_dist2(a, b)
        bound = dist2 / 4 + floor_sqrt(dist2) + 2
        for shape in (a, b):
            assert brute_dist2(witness, shape) <= bound


def test_brute_force_source_is_integer_only() -> None:
    """The module names neither ``float`` nor ``math.sqrt``, and holds no float literal or true division
    of numbers: an AST scan of its source."""
    tree = ast.parse(Path(thick_module.__file__).read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        assert not (isinstance(node, ast.Name) and node.id == "float"), "float is named"
        assert not (isinstance(node, ast.Attribute) and node.attr == "sqrt"), "a sqrt attribute is used"
        assert not (isinstance(node, ast.Constant) and isinstance(node.value, float)), "a float literal"
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            module = node.module if isinstance(node, ast.ImportFrom) else None
            names = [alias.name for alias in node.names]
            assert module != "math" and "math" not in names, "math is imported"
        if (
            isinstance(node, ast.ImportFrom)
            and node.module is not None
            and node.module.startswith("fenolite")
        ):
            assert node.module.startswith(("fenolite.geometry", "fenolite.core")), node.module
