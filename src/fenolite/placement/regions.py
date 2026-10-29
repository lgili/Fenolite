# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The region strategy: an initial placement by domain (capability placement, "Region placement";
``docs/placement.md``, "Regions"; change c0205).

Each domain of parts gets a rectangle of the board, a region, and its parts are packed inside it by the grid
of ``placement.grid``. A barrier part (an isolator, a transformer) that joins two regions is placed first,
across the boundary between them, so that its pins sit in the two regions they join. The module works on
boxes, as the grid does: which part belongs to which domain, and which domains a barrier joins, is decided
by the caller (the ``place`` command, from ``analysis.ties.isolation_islands`` or from the user's groups).
No randomness, no clock, no dictionary order: equal inputs give equal results.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from types import MappingProxyType
from typing import Literal

from fenolite.core.coords import Point
from fenolite.core.evidence import Evidence, Level
from fenolite.core.units import Nm
from fenolite.geometry import BBox
from fenolite.placement.grid import DEFAULT_GAP, DEFAULT_MARGIN, DEFAULT_PITCH, Box
from fenolite.placement.grid import place as grid_place

Axis = Literal["x", "y"]
EVIDENCE = Evidence(Level.INFERRED, hypotheses=("H-G-REGION-PLACE",))
"""A region placement is Fenolite's own rule: no tool judges it. KiCad's DRC still judges the board."""


@dataclass(frozen=True, slots=True)
class Region:
    """A named rectangle of the board, in the board frame."""

    name: str
    bbox: BBox


@dataclass(frozen=True, slots=True)
class Barrier:
    """A barrier part to place across the boundary between the regions named by ``sides``."""

    box: Box
    sides: tuple[str, str]


@dataclass(frozen=True, slots=True)
class Boundary:
    """Where two regions meet: the line ``axis = at`` (``x``: a vertical line at x ``at``), from ``lo`` to
    ``hi`` along it."""

    axis: Axis
    at: Nm
    lo: Nm
    hi: Nm


@dataclass(frozen=True, slots=True)
class RegionRow:
    """What one region received: the paths placed in it and those that fit nowhere, in the order given,
    its area and the area of the boxes placed in it (nm²)."""

    name: str
    bbox: BBox
    placed: tuple[str, ...]
    unplaced: tuple[str, ...]
    area: int
    used: int

    @property
    def fill_permille(self) -> int:
        """``used`` over ``area`` in thousandths, rounded down; 0 for an empty region."""
        return self.used * 1000 // self.area if self.area > 0 else 0


@dataclass(frozen=True, slots=True)
class BarrierRow:
    """One barrier: ``status`` is ``boundary`` (placed across the boundary of its sides), ``inside`` (its
    sides share no boundary, so it was packed in the region of its first side) or ``unplaced``."""

    path: str
    sides: tuple[str, str]
    status: Literal["boundary", "inside", "unplaced"]


@dataclass(frozen=True, slots=True)
class RegionResult:
    """``positions`` maps each placed path to its new position; ``regions`` and ``barriers`` hold one row
    each, in the order given."""

    positions: Mapping[str, Point]
    regions: tuple[RegionRow, ...]
    barriers: tuple[BarrierRow, ...]

    @property
    def unplaced(self) -> tuple[str, ...]:
        """The paths that got no position: the region rows' in region order, then the barriers'."""
        rows = [path for row in self.regions for path in row.unplaced]
        return (*rows, *(row.path for row in self.barriers if row.status == "unplaced"))


def split(box: BBox, weights: Sequence[int], *, axis: Axis, minimums: Sequence[int] = ()) -> tuple[BBox, ...]:
    """``box`` cut into one band per weight, side by side along ``axis`` (``x``: bands left to right).

    Each band first gets its minimum (default 0), and the rest of the length is shared in proportion to the
    weights (a weight below 1 counts as 1); when the minimums do not fit, the whole length is shared by the
    weights. The cuts are whole nanometres, rounded down, and the last band takes what is left."""
    if not weights:
        return ()
    lows = [*minimums, *([0] * (len(weights) - len(minimums)))][: len(weights)]
    shares = [max(weight, 1) for weight in weights]
    start, end = (box.x0, box.x1) if axis == "x" else (box.y0, box.y1)
    length = end - start
    rest = length - sum(lows)
    if rest < 0:
        lows, rest = [0] * len(weights), length
    total = sum(shares)
    bands: list[BBox] = []
    cursor = start
    for index, share in enumerate(shares):
        stop = end if index == len(shares) - 1 else cursor + lows[index] + rest * share // total
        bands.append(
            BBox(cursor, box.y0, stop, box.y1) if axis == "x" else BBox(box.x0, cursor, box.x1, stop)
        )
        cursor = stop
    return tuple(bands)


def band_order(names: Sequence[str], links: Sequence[tuple[str, str]]) -> tuple[str, ...]:
    """An order of the domains ``names`` in which the pairs of ``links`` (the sides of the barriers) are
    neighbours where a chain allows it.

    Each chain starts at the first remaining domain, in the order given, with the fewest remaining
    neighbours, and goes on to the first remaining neighbour of the last domain, until none is left."""
    neighbours: dict[str, set[str]] = {name: set() for name in names}
    for a, b in links:
        if a in neighbours and b in neighbours and a != b:
            neighbours[a].add(b)
            neighbours[b].add(a)
    remaining = list(names)
    order: list[str] = []
    while remaining:
        left = set(remaining)
        current: str | None = min(remaining, key=lambda name: len(neighbours[name] & left))
        while current is not None:
            order.append(current)
            remaining.remove(current)
            current = next((name for name in remaining if name in neighbours[order[-1]]), None)
    return tuple(order)


def _overlap(a0: int, a1: int, b0: int, b1: int) -> tuple[int, int] | None:
    lo, hi = max(a0, b0), min(a1, b1)
    return (lo, hi) if lo < hi else None


def _open_overlap(a: BBox, b: BBox) -> bool:
    return a.x0 < b.x1 and b.x0 < a.x1 and a.y0 < b.y1 and b.y0 < a.y1


def boundary(a: BBox, b: BBox, *, others: Sequence[BBox] = ()) -> Boundary | None:
    """The line between two regions that face each other, or ``None``.

    The regions face each other along x when their y ranges overlap and one ends at or before the other
    begins; the line is the middle of the space between them, over the overlap. The same holds along y. A
    space between them that another region of ``others`` enters is no boundary."""
    span = _overlap(a.y0, a.y1, b.y0, b.y1)
    if span is not None:
        left, right = (a, b) if a.x1 <= b.x0 else (b, a) if b.x1 <= a.x0 else (None, None)
        if left is not None and right is not None:
            gap = BBox(left.x1, span[0], right.x0, span[1])
            if gap.width == 0 or not any(_open_overlap(gap, other) for other in others):
                return Boundary("x", (left.x1 + right.x0) // 2, *span)
    span = _overlap(a.x0, a.x1, b.x0, b.x1)
    if span is not None:
        top, bottom = (a, b) if a.y1 <= b.y0 else (b, a) if b.y1 <= a.y0 else (None, None)
        if top is not None and bottom is not None:
            gap = BBox(span[0], top.y1, span[1], bottom.y0)
            if gap.height == 0 or not any(_open_overlap(gap, other) for other in others):
                return Boundary("y", (top.y1 + bottom.y0) // 2, *span)
    return None


def _strip(line: Boundary, box: Box, margin: Nm) -> BBox:
    """The strip whose inset by ``margin`` holds ``box`` centred across ``line``, along the whole line."""
    if line.axis == "x":
        x0 = line.at - box.bbox.width // 2
        return BBox(x0 - margin, line.lo, x0 + box.bbox.width + margin, line.hi)
    y0 = line.at - box.bbox.height // 2
    return BBox(line.lo, y0 - margin, line.hi, y0 + box.bbox.height + margin)


def _placed(box: Box, at: Point) -> BBox:
    return BBox(at.x + box.bbox.x0, at.y + box.bbox.y0, at.x + box.bbox.x1, at.y + box.bbox.y1)


def place_regions(
    regions: Sequence[Region],
    members: Mapping[str, Sequence[Box]],
    barriers: Sequence[Barrier] = (),
    *,
    occupied: Sequence[BBox],
    cutouts: Sequence[BBox] = (),
    pitch: Nm = DEFAULT_PITCH,
    gap: Nm = DEFAULT_GAP,
    margin: Nm = DEFAULT_MARGIN,
) -> RegionResult:
    """A position for each box of ``members`` (region name → boxes) inside its region, and for each barrier
    across the boundary of its two sides.

    The barriers go first, in the order given: each one centred across the boundary of its sides
    (``boundary``), at the first free place along it, inset by ``margin`` from its ends, on a ``pitch``
    grid. A barrier whose sides share no boundary joins the boxes of its first side. Then each region, in
    the order given, is packed by ``grid.place`` with its boxes, around the boxes already taken. Every box
    keeps ``gap`` from the occupied boxes, the cut-outs and the boxes placed before it."""
    by_name = {region.name: region for region in regions}
    unknown = sorted({*members, *(side for barrier in barriers for side in barrier.sides)} - set(by_name))
    if unknown:
        raise ValueError(f"no region named {', '.join(unknown)}")
    taken: list[BBox] = list(occupied)
    positions: dict[str, Point] = {}
    extra: dict[str, list[Box]] = {}
    barrier_rows: list[BarrierRow] = []
    for barrier in barriers:
        a, b = (by_name[side] for side in barrier.sides)
        others = [region.bbox for region in regions if region.name not in barrier.sides]
        line = boundary(a.bbox, b.bbox, others=others) if a.name != b.name else None
        if line is None:
            extra.setdefault(a.name, []).append(barrier.box)
            barrier_rows.append(BarrierRow(barrier.box.path, barrier.sides, "inside"))
            continue
        packed = grid_place(
            [barrier.box],
            _strip(line, barrier.box, margin),
            occupied=taken,
            cutouts=cutouts,
            pitch=pitch,
            gap=gap,
            margin=margin,
        )
        at = packed.positions.get(barrier.box.path)
        if at is None:
            barrier_rows.append(BarrierRow(barrier.box.path, barrier.sides, "unplaced"))
            continue
        positions[barrier.box.path] = at
        taken.append(_placed(barrier.box, at))
        barrier_rows.append(BarrierRow(barrier.box.path, barrier.sides, "boundary"))
    rows: list[RegionRow] = []
    inside = {row.path for row in barrier_rows if row.status == "inside"}
    for region in regions:
        boxes = [*members.get(region.name, ()), *extra.get(region.name, ())]
        packed = grid_place(
            boxes, region.bbox, occupied=taken, cutouts=cutouts, pitch=pitch, gap=gap, margin=margin
        )
        used = 0
        placed: list[str] = []
        for box in boxes:
            at = packed.positions.get(box.path)
            if at is None:
                continue
            positions[box.path] = at
            taken.append(_placed(box, at))
            used += box.bbox.width * box.bbox.height
            placed.append(box.path)
        unplaced = tuple(path for path in packed.unplaced if path not in inside)
        rows.append(
            RegionRow(
                region.name,
                region.bbox,
                tuple(placed),
                unplaced,
                region.bbox.width * region.bbox.height,
                used,
            )
        )
    barrier_rows = [
        BarrierRow(row.path, row.sides, "unplaced") if row.path not in positions else row
        for row in barrier_rows
    ]
    return RegionResult(MappingProxyType(positions), tuple(rows), tuple(barrier_rows))


def region_of(regions: Sequence[Region], point: Point) -> str | None:
    """The name of the first region whose closed box holds ``point``, or ``None``."""
    return next((region.name for region in regions if region.bbox.contains_point(point)), None)


__all__ = [
    "EVIDENCE",
    "Barrier",
    "BarrierRow",
    "Boundary",
    "Region",
    "RegionResult",
    "RegionRow",
    "band_order",
    "boundary",
    "place_regions",
    "region_of",
    "split",
]
