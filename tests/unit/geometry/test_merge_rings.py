# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The union of curved rings (capability geometry-boolean-backends, "Union of curved rings"; hypothesis
H-G-RING-UNION; change c0167)."""

from __future__ import annotations

import random
import sys
from fractions import Fraction

import pytest

from fenolite.core.coords import Point
from fenolite.core.stadium import stadium
from fenolite.geometry import GeometryError, Polygon
from fenolite.geometry.boolean import select_backend
from fenolite.geometry.errors import BackendUnavailable
from fenolite.geometry.polygon import area2
from fenolite.geometry.rings import MERGE_TOL, CurvedRing, merge_groups, merge_rings, overlap_groups

pytest.importorskip("pyclipper")
MM = 1_000_000


def slot(cx: int, cy: int, rotation: int = 0, length: int = 12 * MM, width: int = 2 * MM) -> CurvedRing:
    ring = stadium(Point(cx, cy), length, width, rotation)
    mids: list[Point | None] = [None] * 4
    for edge, mid in ring.arcs():
        mids[edge] = mid
    return CurvedRing(ring.points, tuple(mids))


def ell() -> list[CurvedRing]:
    """The two stadiums 2 mm wide between (110, 110)–(120, 110) mm and (120, 110)–(120, 120) mm."""
    return [slot(115 * MM, 110 * MM), slot(120 * MM, 115 * MM, 90_000_000)]


def _on_circle(point: Point, cx: Fraction, cy: Fraction, r2: Fraction, within: int) -> bool:
    distance = (point.x - cx) ** 2 + (point.y - cy) ** 2
    root = Fraction(int(r2**0.5))
    return abs(distance - r2) <= 2 * within * (root + within)


def test_ell_of_two_slots_keeps_its_arcs() -> None:
    (merged,) = merge_rings(ell())
    assert len(merged.points) == 7
    arcs = merged.arcs()
    assert len(arcs) == 3
    quarter = [
        merged.edge_arc(k)
        for k, _ in arcs
        if {merged.points[k], merged.points[(k + 1) % 7]}
        == {Point(120 * MM, 109 * MM), Point(121 * MM, 110 * MM)}
    ]
    assert len(quarter) == 1 and quarter[0] is not None and quarter[0].centre is not None
    cx, cy = quarter[0].centre
    assert abs(cx - 120 * MM) <= 1 and abs(cy - 110 * MM) <= 1
    assert Point(119 * MM, 111 * MM) in merged.points  # the concave corner, a plain vertex
    assert merge_rings(ell()) == merge_rings(ell())
    assert merged.points[0] == min(merged.points) and area2(merged.polygonize()) > 0


def test_the_order_of_the_inputs_does_not_change_the_ring() -> None:
    first, second = ell()
    assert merge_rings([first, second]) == merge_rings([second, first])


def test_a_union_with_a_hole_is_refused() -> None:
    # four slots whose round ends overlap at the corners of a square of 10 mm: they enclose board
    frame = [
        slot(115 * MM, 110 * MM),
        slot(120 * MM, 115 * MM, 90_000_000),
        slot(115 * MM, 120 * MM),
        slot(110 * MM, 115 * MM, 90_000_000),
    ]
    names = ["slot A", "slot B", "slot C", "slot D"]
    with pytest.raises(GeometryError) as info:
        merge_rings(frame, names=names)
    assert all(name in str(info.value) for name in names)


def test_separate_rings_untouched() -> None:
    a, b = slot(115 * MM, 110 * MM), slot(115 * MM, 117 * MM)  # 5 mm apart
    assert merge_rings([a, b]) == (a, b)
    assert overlap_groups([a, b]) == ((0,), (1,))


def test_rings_that_only_touch_or_nest_stay_apart() -> None:
    a = slot(115 * MM, 110 * MM)
    touching = slot(115 * MM, 112 * MM)  # shares the line y = 111 mm
    inner = slot(115 * MM, 110 * MM, length=4 * MM, width=MM)
    assert overlap_groups([a, touching]) == ((0,), (1,))
    assert overlap_groups([a, inner]) == ((0,), (1,))


def test_groups_name_their_members() -> None:
    first, second = ell()
    lone = slot(150 * MM, 150 * MM)
    groups = merge_groups([lone, first, second])
    assert [group.members for group in groups] == [(0,), (1, 2)]
    assert groups[0].ring is lone


def test_without_the_extra(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setitem(sys.modules, "pyclipper", None)
    lone = slot(150 * MM, 150 * MM)
    assert merge_rings([lone]) == (lone,)
    with pytest.raises(BackendUnavailable) as info:
        merge_rings(ell())
    assert "fenolite[geo]" in info.value.issue.hint


def _perimeter(points: tuple[Point, ...]) -> int:
    total = 0
    for i, a in enumerate(points):
        b = points[(i + 1) % len(points)]
        total += int(((a.x - b.x) ** 2 + (a.y - b.y) ** 2) ** 0.5) + 1
    return total


@pytest.mark.parametrize("seed", range(12))
def test_merged_area_is_the_union_area(seed: int) -> None:
    rng = random.Random(seed)
    rings = [
        slot(
            rng.randrange(100, 110) * MM + rng.randrange(MM),
            rng.randrange(100, 110) * MM + rng.randrange(MM),
            rng.randrange(0, 180) * 1_000_000 + rng.randrange(1_000_000),
            length=rng.randrange(6, 14) * MM,
            width=2 * rng.randrange(MM // 4, MM),
        )
        for _ in range(3)
    ]
    try:
        merged = merge_rings(rings)
    except GeometryError:
        return  # a union that encloses board is refused, not merged
    polygons = [Polygon(ring.polygonize(MERGE_TOL)) for ring in rings]
    union = select_backend(operation="union").union(polygons)
    exact = sum(area2(poly.outer) - sum(area2(hole) for hole in poly.holes) for poly in union)
    found = sum(area2(ring.polygonize(MERGE_TOL)) for ring in merged)
    perimeter = sum(_perimeter(ring.polygonize(MERGE_TOL)) for ring in merged)
    assert abs(found - exact) <= 2 * MERGE_TOL * perimeter
    # every arc of the result runs through a point of a source circle (its mid, within 1 nm)
    circles = [
        (arc.centre[0], arc.centre[1], arc.radius2)
        for ring in rings
        for k in range(len(ring.points))
        if (arc := ring.edge_arc(k)) is not None and arc.centre is not None and arc.radius2 is not None
    ]
    for ring in merged:
        for _, mid in ring.arcs():
            assert any(_on_circle(mid, cx, cy, r2, 1) for cx, cy, r2 in circles)
    assert merge_rings(rings) == merged
