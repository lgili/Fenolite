# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Path lengths of the kernel (capability geometry-kernel, "Path lengths"; change c0106)."""

from __future__ import annotations

import ast
import math
import random
import sys
from pathlib import Path

import pytest

from fenolite.analysis import views
from fenolite.checks.equivalence import routing
from fenolite.core.coords import Point
from fenolite.geometry import arc_length, arc_length_to, segment_length
from fenolite.geometry import lengths as kernel
from fenolite.model.board import Arc

ROOT = Path(__file__).resolve().parents[3]
MM = 1_000_000
ARC_ID = "arc_00000000-0000-4000-8000-000000000001"


def _generated(count: int = 600) -> list[tuple[Point, Point, Point, float, float, float, float, float]]:
    """Arcs of radius 0.1 mm to 50 mm and sweep 1° to 359°: the three points, then the centre, the radius,
    the start angle and the signed sweep they were rounded from."""
    rng = random.Random(106)
    found: list[tuple[Point, Point, Point, float, float, float, float, float]] = []
    while len(found) < count:
        radius = rng.randint(100_000, 50_000_000)
        cx, cy = rng.randint(-(10**8), 10**8), rng.randint(-(10**8), 10**8)
        first = rng.uniform(0, 2 * math.pi)
        sweep = math.radians(rng.uniform(1, 359)) * rng.choice((1, -1))
        points = [
            Point(
                round(cx + radius * math.cos(first + f * sweep)),
                round(cy + radius * math.sin(first + f * sweep)),
            )
            for f in (0, 0.5, 1)
        ]
        if len(set(points)) == 3:
            found.append((points[0], points[1], points[2], cx, cy, radius, first, sweep))
    return found


def _float_arc(start: Point, mid: Point, end: Point) -> tuple[float, float, float, float, float]:
    """Centre, radius, start angle and signed sweep of the circle through three points, in floats."""
    ax, ay, bx, by, cx, cy = start.x, start.y, mid.x, mid.y, end.x, end.y
    d = 2 * (ax * (by - cy) + bx * (cy - ay) + cx * (ay - by))
    ux = (
        (ax * ax + ay * ay) * (by - cy) + (bx * bx + by * by) * (cy - ay) + (cx * cx + cy * cy) * (ay - by)
    ) / d
    uy = (
        (ax * ax + ay * ay) * (cx - bx) + (bx * bx + by * by) * (ax - cx) + (cx * cx + cy * cy) * (bx - ax)
    ) / d
    radius = math.hypot(ax - ux, ay - uy)
    a0, a1, a2 = (math.atan2(p.y - uy, p.x - ux) for p in (start, mid, end))
    way = 1 if (bx - ax) * (cy - ay) - (by - ay) * (cx - ax) > 0 else -1
    first = (way * (a1 - a0)) % (2 * math.pi)
    second = (way * (a2 - a1)) % (2 * math.pi)
    return ux, uy, radius, a0, way * (first + second)


def test_segment() -> None:
    assert segment_length(Point(0, 0), Point(3 * MM, 4 * MM)) == 5 * MM
    assert segment_length(Point(0, 0), Point(1, 1)) == 1
    assert segment_length(Point(7, 7), Point(7, 7)) == 0


def test_half_circle_and_its_quarter() -> None:
    start, mid, end = Point(15 * MM, 30 * MM), Point(18 * MM, 33 * MM), Point(21 * MM, 30 * MM)
    assert arc_length(start, mid, end) == 9_424_778
    assert arc_length_to(start, mid, end, mid) == 4_712_389
    assert arc_length_to(start, mid, end, end) == 9_424_778
    assert arc_length_to(start, mid, end, start) == 0
    # a point off the arc: the point of the arc on its spoke, or the nearer end
    assert arc_length_to(start, mid, end, Point(18 * MM, 40 * MM)) == 4_712_389
    assert arc_length_to(start, mid, end, Point(22 * MM, 25 * MM)) == 9_424_778
    assert arc_length_to(start, mid, end, Point(14 * MM, 25 * MM)) == 0


def test_points_on_a_line() -> None:
    assert arc_length(Point(0, 0), Point(MM, 0), Point(3 * MM, 0)) == 3 * MM
    assert arc_length(Point(0, 0), Point(0, 0), Point(3 * MM, 0)) == 3 * MM
    assert arc_length_to(Point(0, 0), Point(MM, 0), Point(3 * MM, 0), Point(2 * MM, 5)) == 2 * MM
    assert arc_length_to(Point(0, 0), Point(0, 0), Point(3 * MM, 0), Point(-MM, 0)) == 0


def test_independent_computation() -> None:
    rng = random.Random(7)
    compared = 0
    for start, mid, end, *_ in _generated():
        ux, uy, radius, a0, sweep = _float_arc(start, mid, end)
        assert abs(arc_length(start, mid, end) - radius * abs(sweep)) <= 1
        arc = Arc(id=ARC_ID, start=start, mid=mid, end=end, width=1, layer="F.Cu")
        assert views.arc_length(arc) == arc_length(start, mid, end)
        for _ in range(3):
            # a point on the spoke of a part of the arc, off the arc by up to a tenth of the radius
            part = rng.uniform(0.02, 0.98)
            reach = radius * rng.uniform(0.9, 1.1)
            at = Point(
                round(ux + reach * math.cos(a0 + part * sweep)),
                round(uy + reach * math.sin(a0 + part * sweep)),
            )
            # the rounded point sits on a spoke of its own: measure the angle of that spoke
            way = 1 if sweep > 0 else -1
            turned = (way * (math.atan2(at.y - uy, at.x - ux) - a0)) % (2 * math.pi)
            assert abs(arc_length_to(start, mid, end, at) - radius * turned) <= 1
            compared += 1
    assert compared == 1800


def test_routing_copy_equals_the_kernel() -> None:
    """Scenario "Equivalence level 5 measures with the kernel": generated arcs, the level-5 fixtures, and
    the inputs that form no arc."""
    sys.path.insert(0, str(ROOT / "tests" / "unit" / "checks" / "equivalence"))
    try:
        import _routes
    finally:
        sys.path.pop(0)
    cases = [(s, m, e) for s, m, e, *_ in _generated()]
    board = _routes.routed().board
    assert board is not None and board.arcs
    cases += [(a.start, a.mid, a.end) for a in board.arcs]
    rng = random.Random(11)
    for _ in range(200):
        a = Point(rng.randint(-(10**7), 10**7), rng.randint(-(10**7), 10**7))
        b = Point(rng.randint(-(10**7), 10**7), rng.randint(-(10**7), 10**7))
        dx, dy = rng.randint(-1000, 1000), rng.randint(-1000, 1000)
        cases += [
            (a, Point(a.x + 3 * dx, a.y + 3 * dy), Point(a.x + 7 * dx, a.y + 7 * dy)),  # mid between
            (a, Point(a.x + 9 * dx, a.y + 9 * dy), Point(a.x + 4 * dx, a.y + 4 * dy)),  # mid outside
            (a, Point(a.x - 2 * dx, a.y - 2 * dy), Point(a.x + 5 * dx, a.y + 5 * dy)),
            (a, a, b),
            (a, b, b),
            (a, b, a),
        ]
        assert arc_length(a, b, a) == 0
        assert arc_length(a, a, b) == segment_length(a, b)
    for start, mid, end in cases:
        assert routing.arc_length(start, mid, end) == arc_length(start, mid, end)


def test_straight_arc_is_two_parts() -> None:
    start, mid, end = Point(0, 0), Point(1, 1), Point(3, 3)
    assert arc_length(start, mid, end) == segment_length(start, mid) + segment_length(mid, end)
    assert arc_length(start, Point(5, 5), end) == segment_length(start, end)


@pytest.mark.parametrize("module", [kernel, views, routing])
def test_no_float_and_one_implementation(module: object) -> None:
    source = Path(module.__file__).read_text(encoding="utf-8")  # type: ignore[attr-defined]
    tree = ast.parse(source)
    assert not any(isinstance(n, ast.Constant) and isinstance(n.value, float) for n in ast.walk(tree))
    assert not any(isinstance(n, ast.Name) and n.id == "float" for n in ast.walk(tree))
    if module is not kernel:
        assert "_atan_fixed" not in source
