# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The grid strategy on authored boxes (capability placement, "Grid placement"; change c0022)."""

from __future__ import annotations

import pytest
from hypothesis import given
from hypothesis import strategies as st

from fenolite.core.coords import Point
from fenolite.geometry import BBox
from fenolite.placement import Box, GridResult, place
from fenolite.placement.grid import DEFAULT_GAP, DEFAULT_MARGIN, DEFAULT_PITCH

MM = 1_000_000
REGION = BBox(0, 0, 20 * MM, 10 * MM)


def box(name: str, width: float, height: float, *, x0: float = 0, y0: float = 0) -> Box:
    """A box of ``width`` × ``height`` mm whose top-left corner lies at (``x0``, ``y0``) from its position."""
    a, b = round(x0 * MM), round(y0 * MM)
    return Box(name, name, BBox(a, b, a + round(width * MM), b + round(height * MM)))


def placed_boxes(boxes: list[Box], result: GridResult) -> dict[str, BBox]:
    out: dict[str, BBox] = {}
    for item in boxes:
        at = result.positions.get(item.path)
        if at is not None:
            b = item.bbox
            out[item.path] = BBox(at.x + b.x0, at.y + b.y0, at.x + b.x1, at.y + b.y1)
    return out


def overlap(a: BBox, b: BBox) -> bool:
    return a.x0 < b.x1 and b.x0 < a.x1 and a.y0 < b.y1 and b.y0 < a.y1


FIVE = [box("A", 4, 2), box("B", 4, 3), box("C", 4, 1), box("D", 4, 2), box("E", 4, 2)]


def test_grid_rows_are_deterministic() -> None:
    first = place(FIVE, REGION, occupied=())
    assert first == place(list(FIVE), REGION, occupied=())
    assert first.unplaced == ()
    found = placed_boxes(FIVE, first)
    # the inset region is (1, 1)–(19, 9) mm; boxes are 4 mm wide and 0.5 mm apart on a 0.5 mm grid
    assert [found[name].x0 for name in "ABCD"] == [1 * MM, 5_500_000, 10 * MM, 14_500_000]
    assert {found[name].y0 for name in "ABCD"} == {1 * MM}
    # the next row starts below the tallest box of the first (B, 3 mm) plus the gap
    assert (found["E"].x0, found["E"].y0) == (1 * MM, 4_500_000)
    assert list(first.positions) == ["A", "B", "C", "D", "E"]


def test_grid_positions_are_the_part_positions() -> None:
    """A box that is not anchored at its position: the box lands on the grid, the part where it must."""
    part = box("R1", 3, 1.5, x0=-1.5, y0=-0.75)
    result = place([part], REGION, occupied=())
    assert result.positions["R1"] == Point(2_500_000, 1_750_000)
    assert placed_boxes([part], result)["R1"] == BBox(1 * MM, 1 * MM, 4 * MM, 2_500_000)


def test_grid_occupied_area_is_avoided() -> None:
    occupied = [BBox(0, 0, 6 * MM, 4 * MM)]
    result = place(FIVE, REGION, occupied=occupied)
    found = placed_boxes(FIVE, result)
    assert all(not overlap(b.inflate(DEFAULT_GAP), occupied[0]) for b in found.values())
    assert found["A"] == BBox(6_500_000, 1 * MM, 10_500_000, 3 * MM)


def test_grid_cutouts_are_avoided() -> None:
    cutout = BBox(4 * MM, 0, 8 * MM, 10 * MM)
    result = place(FIVE[:2], REGION, occupied=(), cutouts=[cutout])
    found = placed_boxes(FIVE, result)
    assert found["A"].x0 == 8_500_000 and found["B"].x0 == 13 * MM
    assert all(not overlap(b.inflate(DEFAULT_GAP), cutout) for b in found.values())


def test_grid_no_room() -> None:
    wide = box("W", 19, 1)
    result = place([wide, box("A", 4, 2)], REGION, occupied=())
    assert result.unplaced == ("W",) and "W" not in result.positions
    assert placed_boxes([box("A", 4, 2)], result)["A"].x0 == 1 * MM
    full = place(FIVE, REGION, occupied=[BBox(0, 0, 20 * MM, 10 * MM)])
    assert full.unplaced == ("A", "B", "C", "D", "E") and dict(full.positions) == {}
    assert place(FIVE[:1], BBox(0, 0, 1 * MM, 1 * MM), occupied=()).unplaced == ("A",)


def test_grid_a_subset_is_placed_alone() -> None:
    """What ``--only`` gives the placer: fewer boxes, the same region and occupied boxes."""
    subset = [FIVE[2], FIVE[4]]
    result = place(subset, REGION, occupied=())
    assert list(result.positions) == ["C", "E"]
    assert placed_boxes(subset, result)["E"].x0 == 5_500_000


def test_grid_defaults_and_bad_arguments() -> None:
    assert (DEFAULT_PITCH, DEFAULT_GAP, DEFAULT_MARGIN) == (500_000, 500_000, 1_000_000)
    with pytest.raises(ValueError, match="pitch"):
        place(FIVE, REGION, occupied=(), pitch=0)
    with pytest.raises(ValueError, match="negative"):
        place(FIVE, REGION, occupied=(), gap=-1)
    tight = place(FIVE[:2], REGION, occupied=(), gap=0, margin=0, pitch=1 * MM)
    found = placed_boxes(FIVE, tight)
    assert (found["A"].x0, found["B"].x0) == (0, 4 * MM)  # touching boxes are allowed with no gap


sizes = st.integers(min_value=1, max_value=12).map(lambda n: n * 250_000)
offsets = st.integers(min_value=-8, max_value=8).map(lambda n: n * 125_000)


@st.composite
def parts(draw: st.DrawFn) -> list[Box]:
    count = draw(st.integers(min_value=0, max_value=12))
    out: list[Box] = []
    for n in range(count):
        x0, y0 = draw(offsets), draw(offsets)
        out.append(Box(f"P{n}", f"P{n}", BBox(x0, y0, x0 + draw(sizes), y0 + draw(sizes))))
    return out


@st.composite
def taken(draw: st.DrawFn) -> list[BBox]:
    out: list[BBox] = []
    for _ in range(draw(st.integers(min_value=0, max_value=3))):
        x0 = draw(st.integers(min_value=0, max_value=18)) * MM
        y0 = draw(st.integers(min_value=0, max_value=8)) * MM
        out.append(BBox(x0, y0, x0 + draw(sizes), y0 + draw(sizes)))
    return out


@given(
    parts(), taken(), st.sampled_from([250_000, 500_000, 1_000_000]), st.sampled_from([0, 300_000, 500_000])
)
def test_grid_placed_boxes_keep_the_gap(boxes: list[Box], occupied: list[BBox], pitch: int, gap: int) -> None:
    result = place(boxes, REGION, occupied=occupied, pitch=pitch, gap=gap)
    assert result == place(boxes, REGION, occupied=occupied, pitch=pitch, gap=gap)
    found = placed_boxes(boxes, result)
    assert set(found) | set(result.unplaced) == {b.path for b in boxes}
    assert not set(found) & set(result.unplaced)
    inset = REGION.inflate(-DEFAULT_MARGIN)
    names = list(found)
    for i, name in enumerate(names):
        here = found[name]
        assert inset.contains_bbox(here)
        assert (here.x0 - inset.x0) % pitch == 0 and (here.y0 - inset.y0) % pitch == 0
        grown = here.inflate(gap)
        assert not any(overlap(grown, other) for other in occupied)
        assert not any(overlap(grown, found[other]) for other in names[:i] + names[i + 1 :])
