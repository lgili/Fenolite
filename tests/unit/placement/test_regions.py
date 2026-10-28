# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The region strategy of ``placement.regions`` (change c0205; capability placement, "Region placement"), on
authored boxes. Every value is a round invented one."""

from __future__ import annotations

import pytest

from fenolite.core.coords import Point
from fenolite.geometry import BBox
from fenolite.placement.grid import Box
from fenolite.placement.regions import (
    Barrier,
    Boundary,
    Region,
    band_order,
    boundary,
    place_regions,
    region_of,
    split,
)

MM = 1_000_000
PART = BBox(-2 * MM, -MM // 2, 2 * MM, MM // 2)
"""A 4 × 1 mm box centred on its position."""


def part(name: str) -> Box:
    return Box(name, name, PART)


def test_split_shares_by_weight_after_the_minimums() -> None:
    box = BBox(0, 0, 60 * MM, 40 * MM)
    assert split(box, [1, 1], axis="x") == (BBox(0, 0, 30 * MM, 40 * MM), BBox(30 * MM, 0, 60 * MM, 40 * MM))
    bands = split(box, [3, 1], axis="y", minimums=[0, 20 * MM])
    assert bands == (BBox(0, 0, 60 * MM, 15 * MM), BBox(0, 15 * MM, 60 * MM, 40 * MM))
    # minimums that do not fit: the weights alone share the length; a weight 0 counts as 1
    assert split(box, [0, 1], axis="x", minimums=[50 * MM, 50 * MM])[0] == BBox(0, 0, 30 * MM, 40 * MM)
    assert split(box, [], axis="x") == ()


def test_band_order_keeps_barrier_sides_neighbours() -> None:
    assert band_order(["A", "B", "C"], [("A", "C"), ("C", "B")]) == ("A", "C", "B")
    assert band_order(["A", "B", "C"], []) == ("A", "B", "C")
    assert band_order(["A", "B", "C"], [("B", "C")]) == ("A", "B", "C")


def test_boundary_of_touching_regions() -> None:
    left, right = BBox(0, 0, 20 * MM, 10 * MM), BBox(20 * MM, 5 * MM, 40 * MM, 20 * MM)
    assert boundary(left, right) == Boundary("x", 20 * MM, 5 * MM, 10 * MM)
    assert boundary(right, left) == Boundary("x", 20 * MM, 5 * MM, 10 * MM)
    top, bottom = BBox(0, 0, 10 * MM, 10 * MM), BBox(0, 12 * MM, 10 * MM, 20 * MM)
    assert boundary(top, bottom) == Boundary("y", 11 * MM, 0, 10 * MM)
    # a region between them, or boxes that face each other on no span
    middle = BBox(0, 10 * MM, 10 * MM, 12 * MM)
    assert boundary(top, bottom, others=[middle]) is None
    assert boundary(BBox(0, 0, 10 * MM, 10 * MM), BBox(20 * MM, 20 * MM, 30 * MM, 30 * MM)) is None


def test_barrier_straddles_the_boundary() -> None:
    regions = [Region("A", BBox(0, 0, 20 * MM, 10 * MM)), Region("B", BBox(20 * MM, 0, 40 * MM, 10 * MM))]
    members = {"A": [part("R1"), part("R3")], "B": [part("R2")]}
    barriers = [Barrier(part("U5"), ("A", "B"))]
    result = place_regions(regions, members, barriers, occupied=[])
    assert result == place_regions(regions, members, barriers, occupied=[])
    assert result.positions["U5"] == Point(20 * MM, 3 * MM // 2)
    for name in ("R1", "R3"):
        assert regions[0].bbox.contains_point(result.positions[name])
    assert regions[1].bbox.contains_point(result.positions["R2"])
    placed = {name: BBox(at.x + PART.x0, at.y + PART.y0, at.x + PART.x1, at.y + PART.y1)
              for name, at in result.positions.items()}  # fmt: skip
    assert not placed["U5"].inflate(MM // 2 - 1).intersects(placed["R2"])
    (a, b) = result.regions
    assert (a.placed, b.placed, a.unplaced, b.unplaced) == (("R1", "R3"), ("R2",), (), ())
    assert a.used == 2 * 4 * MM * MM and a.area == 200 * MM * MM and a.fill_permille == 40
    assert [row.status for row in result.barriers] == ["boundary"]
    assert region_of(regions, Point(19 * MM, MM)) == "A" and region_of(regions, Point(21 * MM, MM)) == "B"
    assert region_of(regions, Point(50 * MM, MM)) is None


def test_barrier_without_a_boundary_goes_inside() -> None:
    regions = [
        Region("A", BBox(0, 0, 20 * MM, 10 * MM)),
        Region("C", BBox(20 * MM, 0, 40 * MM, 10 * MM)),
        Region("B", BBox(40 * MM, 0, 60 * MM, 10 * MM)),
    ]
    result = place_regions(regions, {}, [Barrier(part("U5"), ("A", "B"))], occupied=[])
    assert [row.status for row in result.barriers] == ["inside"]
    assert regions[0].bbox.contains_point(result.positions["U5"])
    assert result.regions[0].placed == ("U5",) and result.unplaced == ()


def test_no_room_in_a_region() -> None:
    regions = [Region("A", BBox(0, 0, 5 * MM, 5 * MM))]
    result = place_regions(regions, {"A": [part("R1")]}, occupied=[])
    assert result.positions == {} and result.regions[0].unplaced == ("R1",) and result.unplaced == ("R1",)
    assert result.regions[0].fill_permille == 0
    with pytest.raises(ValueError, match="no region named Z"):
        place_regions(regions, {"Z": [part("R1")]}, occupied=[])
