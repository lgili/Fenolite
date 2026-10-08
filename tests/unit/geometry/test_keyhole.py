# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""One ring for a polygon with holes (capability geometry-kernel, "Keyhole ring of a polygon with holes";
change c0122; ``H-G-KEYHOLE``).

Every polygon here is authored or drawn from a seeded generator: an outline around a grid of cells, and
at most one hole inside each cell, so the holes are disjoint and inside the outline by construction.
"""

from __future__ import annotations

import itertools
import random
from collections.abc import Sequence

import pytest

from fenolite.geometry import (
    FillRule,
    Keyhole,
    Location,
    Point,
    Polygon,
    Thick,
    area2,
    dist2_point_segment,
    keyhole_ring,
    point_in_ring,
    thick_touch,
)
from fenolite.geometry import polygon as polygon_module

P = Point
Ring = tuple[Point, ...]
RULES = (FillRule.NONZERO, FillRule.EVENODD)
SQUARE: Ring = (P(0, 0), P(100, 0), P(100, 100), P(0, 100))
HOLE: Ring = (P(30, 40), P(70, 40), P(70, 60), P(30, 60))
CELL = 1000


def box(x0: int, y0: int, x1: int, y1: int) -> Ring:
    return (P(x0, y0), P(x1, y0), P(x1, y1), P(x0, y1))


def edges(ring: Sequence[Point]) -> list[tuple[Point, Point]]:
    return [(ring[i], ring[(i + 1) % len(ring)]) for i in range(len(ring))]


def exact(found: Keyhole, outer: Ring, holes: Sequence[Ring]) -> bool:
    """Whether no anchor was rounded: every point of the ring that is no point of the input lies on an
    edge of the input."""
    given = set(outer).union(*holes) if holes else set(outer)
    sides = [edge for ring in (outer, *holes) for edge in edges(ring)]
    return all(
        any(dist2_point_segment(point, a, b) == 0 for a, b in sides)
        for point in set(found.ring)
        if point not in given
    )


def in_order(points: Sequence[Point], ring: Sequence[Point]) -> bool:
    """Whether ``ring`` starts at ``points[0]`` and holds ``points`` in their order."""
    rest = iter(ring)
    return ring[0] == points[0] and all(any(point == other for other in rest) for point in points)


def holes_area2(holes: Sequence[Ring]) -> int:
    return sum(abs(area2(hole)) for hole in holes)


# --- the scenarios of the requirement --------------------------------------------------------------


def test_one_hole() -> None:
    found = keyhole_ring(SQUARE, [HOLE])
    assert found.ring == (
        P(0, 0), P(100, 0), P(100, 100), P(0, 100), P(0, 40),
        P(30, 40), P(30, 60), P(70, 60), P(70, 40), P(30, 40), P(0, 40),
    )  # fmt: skip
    assert (found.merged, found.outside) == (1, 0) and area2(found.ring) == 18400
    for rule in RULES:
        assert point_in_ring(P(50, 50), found.ring, rule) == Location.OUTSIDE
        assert point_in_ring(P(10, 10), found.ring, rule) == Location.INSIDE
        assert point_in_ring(P(15, 40), found.ring, rule) == Location.BOUNDARY
        assert point_in_ring(P(200, 50), found.ring, rule) == Location.OUTSIDE


def test_the_hole_runs_against_the_outline_whichever_way_both_are_given() -> None:
    turned_hole = HOLE[::-1]
    assert keyhole_ring(SQUARE, [turned_hole]) == keyhole_ring(SQUARE, [HOLE])
    assert keyhole_ring(SQUARE, [HOLE[2:] + HOLE[:2]]) == keyhole_ring(SQUARE, [HOLE])
    back = keyhole_ring(SQUARE[::-1], [HOLE])
    assert back.ring[:4] == SQUARE[::-1] and area2(back.ring) == -18400
    for rule in RULES:
        assert point_in_ring(P(50, 50), back.ring, rule) == Location.OUTSIDE
        assert point_in_ring(P(10, 10), back.ring, rule) == Location.INSIDE


def test_without_a_hole_the_ring_is_the_outline_as_given() -> None:
    turned = SQUARE[2:] + SQUARE[:2]
    assert keyhole_ring(turned, []) == Keyhole(turned, 0, 0)
    assert keyhole_ring(turned, [[P(5, 5), P(5, 5), P(5, 5)]]) == Keyhole(turned, 0, 0)
    assert keyhole_ring(turned, [[P(5, 5), P(9, 5)]]) == Keyhole(turned, 0, 0)
    assert keyhole_ring(turned, [[P(5, 5), P(7, 5), P(9, 5)]]) == Keyhole(turned, 0, 0)  # no area


def test_a_hole_outside_the_outline_is_dropped_and_counted() -> None:
    found = keyhole_ring(SQUARE, [box(200, 200, 220, 220), HOLE, box(-50, 10, -40, 20)])
    assert found == Keyhole(keyhole_ring(SQUARE, [HOLE]).ring, 1, 2)
    assert keyhole_ring(SQUARE, [box(200, 200, 220, 220)]) == Keyhole(SQUARE, 0, 1)


def test_an_outline_without_area_keeps_its_points_and_counts_the_holes() -> None:
    flat = (P(0, 0), P(10, 0), P(20, 0))
    assert keyhole_ring(flat, [HOLE, [P(1, 1), P(1, 1)]]) == Keyhole(flat, 0, 1)
    assert keyhole_ring((P(0, 0), P(10, 0)), [HOLE]) == Keyhole((P(0, 0), P(10, 0)), 0, 1)


def test_points_are_integers_and_a_float_is_refused() -> None:
    slanted = (P(0, 0), P(100, 0), P(100, 100), P(7, 100))
    found = keyhole_ring(slanted, [HOLE])
    assert all(type(point.x) is int and type(point.y) is int for point in found.ring)
    with pytest.raises(TypeError):
        keyhole_ring(SQUARE, [[P(30, 40), P(70.5, 40), P(70, 60)]])  # type: ignore[arg-type]
    with pytest.raises(TypeError):
        keyhole_ring([P(0.5, 0), P(100, 0), P(100, 100)], [])  # type: ignore[arg-type]


# --- anchors ---------------------------------------------------------------------------------------


def test_anchor_inside_an_edge_is_rounded_half_to_even() -> None:
    # the left edge runs from (7, 100) to (0, 0): at y = 40 its x is 2.8, at y = 50 it is 3.5
    slanted = (P(0, 0), P(100, 0), P(100, 100), P(7, 100))
    found = keyhole_ring(slanted, [HOLE])
    assert found.ring[4] == P(3, 40) == found.ring[-1] and not exact(found, slanted, [HOLE])
    half = keyhole_ring(slanted, [box(30, 50, 70, 60)])
    assert half.ring[4] == P(4, 50)  # 3.5 goes to the even neighbour
    assert abs(area2(found.ring) - (area2(slanted) - 1600)) <= 2 * 100  # the edge bends by under 1 nm


def test_anchor_at_a_vertex_is_that_vertex() -> None:
    kinked = (P(0, 0), P(100, 0), P(100, 100), P(0, 100), P(10, 40))
    found = keyhole_ring(kinked, [HOLE])
    assert found.ring == (
        *kinked, P(30, 40), P(30, 60), P(70, 60), P(70, 40), P(30, 40), P(10, 40),
    )  # fmt: skip
    assert area2(found.ring) == area2(kinked) - 1600 and exact(found, kinked, [HOLE])


def test_a_later_hole_anchors_on_an_earlier_hole() -> None:
    first, second = box(10, 40, 30, 60), box(50, 45, 70, 55)
    found = keyhole_ring(SQUARE, [second, first])
    assert found.merged == 2 and area2(found.ring) == 20000 - 800 - 400
    assert P(30, 45) in found.ring and found.ring.count(P(30, 45)) == 2  # on the right edge of the first
    for rule in RULES:
        assert point_in_ring(P(20, 50), found.ring, rule) == Location.OUTSIDE
        assert point_in_ring(P(60, 50), found.ring, rule) == Location.OUTSIDE
        assert point_in_ring(P(40, 50), found.ring, rule) == Location.INSIDE
        assert point_in_ring(P(40, 45), found.ring, rule) == Location.BOUNDARY


def test_a_ray_along_an_earlier_bridge_stops_at_the_earlier_hole() -> None:
    # both leftmost vertices lie on y = 40, so the second ray runs along the first bridge's line; the
    # first hole is a triangle whose leftmost vertex has both neighbours above the ray
    first: Ring = (P(10, 40), P(20, 50), P(30, 50))
    second = box(60, 40, 80, 60)
    found = keyhole_ring(SQUARE, [first, second])
    assert found.merged == 2 and area2(found.ring) == 20000 - 100 - 800
    assert found.ring.count(P(10, 40)) == 3  # the first hole's vertex, twice for its own bridge, once more
    for rule in RULES:
        assert point_in_ring(P(22, 49), found.ring, rule) == Location.OUTSIDE
        assert point_in_ring(P(70, 50), found.ring, rule) == Location.OUTSIDE
        assert point_in_ring(P(40, 50), found.ring, rule) == Location.INSIDE
        assert point_in_ring(P(40, 40), found.ring, rule) == Location.BOUNDARY


def test_a_hole_on_the_outline_is_merged_without_a_bridge() -> None:
    touching = box(0, 40, 20, 60)
    found = keyhole_ring(SQUARE, [touching])
    assert found.merged == 1 and area2(found.ring) == 20000 - 800
    assert all(a != b for a, b in edges(found.ring))
    assert point_in_ring(P(10, 50), found.ring) == Location.OUTSIDE
    corner = keyhole_ring(SQUARE, [box(0, 0, 20, 20)])
    assert corner.merged == 1 and area2(corner.ring) == 20000 - 800
    assert all(a != b for a, b in edges(corner.ring))


def test_the_copper_check_reads_the_ring_as_copper_without_its_hole() -> None:
    fill = Thick(keyhole_ring(SQUARE, [HOLE]).ring, 0, filled=True)
    island = Thick(box(45, 45, 55, 55), 0, filled=True)
    assert not thick_touch(fill, island) and not thick_touch(island, fill)
    assert not thick_touch(fill, Thick((P(40, 50), P(60, 50)), 4))  # a track inside the hole
    assert thick_touch(fill, Thick((P(15, 30), P(15, 50)), 2))  # across the bridge, which is copper
    assert thick_touch(fill, Thick((P(50, 50), P(90, 50)), 2))  # from the hole into the copper
    assert thick_touch(Thick(SQUARE, 0, filled=True), island)  # what the outline alone said


# --- generated polygons ----------------------------------------------------------------------------


def generated(rng: random.Random, columns: int, rows: int, *, slanted: bool) -> tuple[Ring, list[Ring]]:
    """An outline around ``columns`` × ``rows`` cells and a hole in about two cells of three. With
    ``slanted`` the left side of the outline is a zigzag and the holes are triangles and quadrilaterals
    with slanted sides; without it everything is a rectangle on the grid, so no anchor needs rounding."""
    width, height = columns * CELL, rows * CELL
    if slanted:
        left = [P(-rng.randrange(100, 900), y) for y in range(height - 333, 0, -333)]
        outer: Ring = (P(0, 0), P(width, 0), P(width, height), P(0, height), *left)
    else:
        outer = box(0, 0, width, height)
    holes: list[Ring] = []
    for column in range(columns):
        for row in range(rows):
            if rng.random() < 0.34:
                continue
            x0, y0 = column * CELL + 100, row * CELL + 100
            if slanted:
                count = rng.choice((3, 4, 5))
                # points on a circle-like order inside the cell: one per sector, so the ring is simple
                sectors = [(1, 1), (5, 0), (7, 3), (6, 7), (2, 6)][:count]
                hole = tuple(
                    P(x0 + sx * 100 + rng.randrange(0, 90), y0 + sy * 100 + rng.randrange(0, 90))
                    for sx, sy in sectors
                )
                if area2(hole) == 0:
                    continue
            else:
                hole = box(x0 + rng.randrange(0, 300), y0 + rng.randrange(0, 300), x0 + 700, y0 + 700)
            if rng.random() < 0.5:
                hole = hole[::-1]
            holes.append(hole)
    return outer, holes


def samples(rng: random.Random, columns: int, rows: int, count: int) -> list[Point]:
    return [
        P(rng.randrange(-1000, columns * CELL + 100), rng.randrange(-100, rows * CELL + 100))
        for _ in range(count)
    ]


def near_an_edge(point: Point, rings: Sequence[Ring]) -> bool:
    return any(dist2_point_segment(point, a, b) < 4 for ring in rings for a, b in edges(ring))


@pytest.mark.parametrize("slanted", [False, True], ids=["grid", "slanted"])
def test_area_and_location_over_generated_polygons(slanted: bool) -> None:
    rng = random.Random(20261006 + slanted)
    rounded = 0
    for _ in range(40):
        columns, rows = rng.randrange(1, 5), rng.randrange(1, 4)
        outer, holes = generated(rng, columns, rows, slanted=slanted)
        found = keyhole_ring(outer, holes)
        assert (found.merged, found.outside) == (len(holes), 0)
        assert in_order(outer, found.ring)
        assert all(a != b for a, b in edges(found.ring))
        assert all(type(point.x) is int and type(point.y) is int for point in found.ring)
        sign = 1 if area2(outer) > 0 else -1
        if exact(found, outer, holes):
            assert sign * area2(found.ring) == abs(area2(outer)) - holes_area2(holes)
        else:
            rounded += 1
        reference = Polygon(outer, tuple(holes))
        for point in samples(rng, columns, rows, 60):
            if near_an_edge(point, (outer, *holes)):
                continue  # a rounded anchor bends its edge by under a nanometre
            for rule in RULES:
                mine = point_in_ring(point, found.ring, rule)
                theirs = reference.locate(point, rule)
                if mine == Location.BOUNDARY:
                    assert theirs == Location.INSIDE  # on a bridge, which lies in the copper
                else:
                    assert mine == theirs, (point, rule)
        # the order of the holes and the direction and start of each do not matter
        shuffled = [hole[k:] + hole[:k] for hole in holes for k in [rng.randrange(len(hole))]]
        shuffled = [hole[::-1] if rng.random() < 0.5 else hole for hole in shuffled]
        rng.shuffle(shuffled)
        assert keyhole_ring(outer, shuffled) == found
        # the outline the other way round: the same copper
        back = keyhole_ring(outer[::-1], holes)
        assert back.merged == len(holes) and in_order(outer[::-1], back.ring)
        if exact(back, outer, holes):
            assert -sign * area2(back.ring) == abs(area2(outer)) - holes_area2(holes)
    assert (rounded > 0) == slanted  # the grid never rounds; the slanted outlines do


def test_every_order_of_four_holes_gives_one_ring() -> None:
    holes = [box(10, 10, 20, 20), box(40, 12, 50, 22), box(10, 60, 30, 80), box(60, 55, 80, 75)]
    first = keyhole_ring(SQUARE, holes)
    assert first.merged == 4 and area2(first.ring) == 20000 - 2 * (100 + 100 + 400 + 400)
    for order in itertools.permutations(holes):
        assert keyhole_ring(SQUARE, order) == first


def test_three_hundred_holes_within_the_bound_of_edge_tests() -> None:
    rng = random.Random(20261007)
    outer = box(0, 0, 25 * CELL, 12 * CELL)
    holes = [
        box(c * CELL + 100, r * CELL + 100 + rng.randrange(0, 200), c * CELL + 800, r * CELL + 900)
        for c in range(25)
        for r in range(12)
    ]
    assert len(holes) == 300
    found, tested = polygon_module._keyhole(outer, holes)  # pyright: ignore[reportPrivateUsage]
    assert (found.merged, found.outside) == (300, 0)
    # per hole: its four points, its first again, and the anchor twice (once when it is a vertex already)
    assert 4 + 300 * 6 <= len(found.ring) <= 4 + 300 * 7
    assert 0 < tested <= found.merged * len(found.ring)
    assert area2(found.ring) == area2(outer) - holes_area2(holes)
    assert point_in_ring(P(450, 600), found.ring) == Location.OUTSIDE
    assert point_in_ring(P(50, 50), found.ring) == Location.INSIDE
