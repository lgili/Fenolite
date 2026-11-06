# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The grid lines of Altium's hatched pour (change c0463, task 3.2; ``docs/formats/altium/pcb-pour.md``,
"Hatched pour"; S-2223).

Altium's kit run of the sample ``pour-hatched`` shows the grid: lines of each family of the polygon's
``HATCHSTYLE`` at whole multiples of ``GRIDSIZE`` from the document's origin, measured along the family's
normal (``90Degree`` and ``Vertical`` lines at ``x = k·GRIDSIZE``, ``90Degree`` and ``Horizontal`` at
``y = k·GRIDSIZE``, ``45Degree`` at ``(x ± y)/√2 = k·GRIDSIZE``), each cut to the inside of the area the
hatch fills. The import frame is the file's with Y negated and no offset, so the same multiples hold there.

``grid_segments`` gives the parts of those lines inside the area: the centre lines of the hatch's tracks;
``first_part`` the centre line of a relief conductor. Pure geometry on floats rounded to the nanometre;
the copper they make is the pour's (``pour._hatched``).
"""

# evidence: see pour

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Final

from fenolite.core.coords import Point
from fenolite.core.trig import ONE, cos_sin_fixed
from fenolite.geometry.polygon import Location, Polygon

HATCH_NORMALS: Final[Mapping[str, tuple[int, ...]]] = {
    "90Degree": (0, 90_000_000),
    "45Degree": (45_000_000, 135_000_000),
    "Horizontal": (90_000_000,),
    "Vertical": (0,),
}
"""``HATCHSTYLE`` → the angles of the normals of its families of lines, in microdegrees (S-2223)."""

Segment = tuple[Point, Point]

MIN_RUN = 2
"""A part of a line shorter than this (nm) is left out: its middle cannot be placed apart from its ends."""


def _inside(pieces: Sequence[Polygon], point: Point) -> bool:
    return any(piece.locate(point) == Location.INSIDE for piece in pieces)


def _runs(
    pieces: Sequence[Polygon], origin: tuple[float, float], d: tuple[float, float], ts: list[float]
) -> list[tuple[float, float]]:
    """The maximal runs between the sorted positions ``ts`` along the line ``origin + t·d`` whose parts lie
    inside ``pieces``; a part shorter than ``MIN_RUN`` or along an edge (its middle on the boundary) is
    out."""
    found: list[tuple[float, float]] = []
    start: float | None = None
    end = 0.0
    for t0, t1 in zip(ts, ts[1:], strict=False):
        if t1 - t0 >= MIN_RUN and _inside(pieces, _at(origin, d, (t0 + t1) / 2)):
            if start is None:
                start = t0
            end = t1
            continue
        if start is not None:
            found.append((start, end))
            start = None
    if start is not None:
        found.append((start, end))
    return found


def _crossings(pieces: Sequence[Polygon], origin: tuple[float, float], d: tuple[float, float]) -> list[float]:
    """The positions ``t`` along the line ``origin + t·d`` (``d`` of unit length) where it meets an edge of
    ``pieces``: each crossing, and each vertex on the line."""
    nx, ny = -d[1], d[0]
    level = nx * origin[0] + ny * origin[1]
    found: list[float] = []
    for piece in pieces:
        for ring in piece.rings():
            for a, b in zip(ring, (*ring[1:], ring[0]), strict=True):
                fa = nx * a.x + ny * a.y - level
                fb = nx * b.x + ny * b.y - level
                if fa == 0:
                    found.append(d[0] * (a.x - origin[0]) + d[1] * (a.y - origin[1]))
                if (fa < 0 < fb) or (fb < 0 < fa):
                    s = fa / (fa - fb)
                    x, y = a.x + s * (b.x - a.x), a.y + s * (b.y - a.y)
                    found.append(d[0] * (x - origin[0]) + d[1] * (y - origin[1]))
    return sorted(set(found))


def grid_segments(pieces: Sequence[Polygon], style: str, grid: int) -> tuple[Segment, ...]:
    """The parts of the hatch's grid lines of ``style`` at pitch ``grid`` (nm) that lie inside ``pieces``,
    family by family and line by line, each from its lower to its higher position along the line. A line
    that runs along an edge of ``pieces`` gives no part there: the edge's own track covers it."""
    if grid <= 0 or not pieces:
        return ()
    out: list[Segment] = []
    for udeg in HATCH_NORMALS[style]:
        cos, sin = cos_sin_fixed(udeg)
        nx, ny = cos / ONE, sin / ONE
        d = (-ny, nx)
        levels = [nx * p.x + ny * p.y for piece in pieces for ring in piece.rings() for p in ring]
        first, last = -int(-min(levels) // grid), int(max(levels) // grid)
        for k in range(first, last + 1):
            origin = (nx * k * grid, ny * k * grid)
            ts = _crossings(pieces, origin, d)
            for t0, t1 in _runs(pieces, origin, d, ts):
                out.append((_at(origin, d, t0), _at(origin, d, t1)))
    return tuple(out)


def _at(origin: tuple[float, float], d: tuple[float, float], t: float) -> Point:
    return Point(round(origin[0] + d[0] * t), round(origin[1] + d[1] * t))


def first_part(pieces: Sequence[Polygon], a: Point, b: Point) -> Segment | None:
    """The part of the segment from ``a`` to ``b`` that starts at ``a`` and runs inside ``pieces`` until it
    first leaves them (a relief conductor from a pad's centre), or ``None`` when ``a`` is not inside."""
    length = ((b.x - a.x) ** 2 + (b.y - a.y) ** 2) ** 0.5
    if length < MIN_RUN:
        return None
    origin = (float(a.x), float(a.y))
    d = ((b.x - a.x) / length, (b.y - a.y) / length)
    ts = [0.0, *(t for t in _crossings(pieces, origin, d) if 0 < t < length), length]
    runs = _runs(pieces, origin, d, ts)
    if not runs or runs[0][0] != 0.0:
        return None
    return (a, _at(origin, d, runs[0][1]))


__all__ = ["HATCH_NORMALS", "MIN_RUN", "Segment", "first_part", "grid_segments"]
