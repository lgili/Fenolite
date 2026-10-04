# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The grid strategy: a deterministic shelf placer for staged parts (capability placement, "Grid
placement"; ``docs/placement.md``).

``place`` works on boxes: the bounding box of each part's courtyard relative to its position, the region
to fill, and the boxes already taken. It only translates: parts keep their rotation and side. The result
depends on its inputs alone: no randomness, no clock, no dictionary order.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from types import MappingProxyType

from fenolite.core.coords import Point
from fenolite.core.units import Nm
from fenolite.geometry import BBox

DEFAULT_PITCH: Nm = 500_000
DEFAULT_GAP: Nm = 500_000
DEFAULT_MARGIN: Nm = 1_000_000
"""Fenolite choices, not fabrication rules: the grid step, the space kept around a placed box and the
distance kept from the bounding box of the board."""


@dataclass(frozen=True, slots=True)
class Box:
    """A part to place: its component path, its reference and the bounding box of its extent relative to
    its position."""

    path: str
    ref: str
    bbox: BBox


@dataclass(frozen=True, slots=True)
class GridResult:
    """``positions`` maps the path of each placed part to its new position; ``unplaced`` lists the paths
    that fit nowhere, in the order given."""

    positions: Mapping[str, Point]
    unplaced: tuple[str, ...] = ()


def _overlap(a: BBox, b: BBox) -> bool:
    """Whether the open boxes intersect: boxes that only touch do not."""
    return a.x0 < b.x1 and b.x0 < a.x1 and a.y0 < b.y1 and b.y0 < a.y1


def _ceil_to(value: int, origin: int, pitch: int) -> int:
    """The smallest grid coordinate at or after ``value``."""
    return origin + -(-(value - origin) // pitch) * pitch


def place(
    boxes: Sequence[Box],
    region: BBox,
    *,
    occupied: Sequence[BBox],
    cutouts: Sequence[BBox] = (),
    pitch: Nm = DEFAULT_PITCH,
    gap: Nm = DEFAULT_GAP,
    margin: Nm = DEFAULT_MARGIN,
) -> GridResult:
    """A position for each box, in the order given, by shelf packing inside ``region`` inset by ``margin``.

    A box goes at the first place, scanning rows from the top and columns from the left on a ``pitch``
    grid whose origin is the inset region's top-left corner, where it lies inside the inset region and,
    grown by ``gap`` on every side, overlaps no occupied box, no cut-out and no box placed before it. A
    row is as high as the tallest box placed in it. A box that fits nowhere is listed in ``unplaced``.
    """
    if pitch <= 0:
        raise ValueError(f"the grid pitch must be positive, got {pitch}")
    if gap < 0 or margin < 0:
        raise ValueError("the gap and the margin cannot be negative")
    positions: dict[str, Point] = {}
    unplaced: list[str] = []
    x0, y0, x1, y1 = region.x0 + margin, region.y0 + margin, region.x1 - margin, region.y1 - margin
    taken: list[BBox] = [*occupied, *cutouts]
    row_y, row_height, cursor = y0, 0, x0

    def free(box: BBox) -> bool:
        grown = box.inflate(gap)
        return not any(_overlap(grown, other) for other in taken)

    for box in boxes:
        width, height = box.bbox.width, box.bbox.height
        if x1 - x0 < width or y1 - y0 < height:
            unplaced.append(box.path)
            continue
        y, shelf, start = row_y, row_height, cursor
        found: BBox | None = None
        while y + height <= y1:
            x = start
            while x + width <= x1:
                candidate = BBox(x, y, x + width, y + height)
                if free(candidate):
                    found = candidate
                    break
                x += pitch
            if found is not None:
                break
            y = _ceil_to(y + (shelf + gap if shelf else pitch), y0, pitch)
            shelf, start = 0, x0
        if found is None:
            unplaced.append(box.path)
            continue
        taken.append(found)
        row_y, row_height = found.y0, max(shelf, height)
        cursor = _ceil_to(found.x1 + gap, x0, pitch)
        positions[box.path] = Point(found.x0 - box.bbox.x0, found.y0 - box.bbox.y0)
    return GridResult(MappingProxyType(positions), tuple(unplaced))


__all__ = ["DEFAULT_GAP", "DEFAULT_MARGIN", "DEFAULT_PITCH", "Box", "GridResult", "place"]
