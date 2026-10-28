# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Silkscreen strokes cut where they come near an opening (capability silkscreen-layout, "Silkscreen
clipping"; change c0226, design decisions 3, 4 and 6; user guide ``docs/assembly.md``, "Clipping").

A stroke is a centre line drawn with a round pen of ``width``. ``cut`` keeps the points of the centre line
that lie at least ``margin + GUARD + width / 2`` from every opening (a thick shape: a pad's copper grown by
its mask expansion, or a hole), so the ink of every piece keeps ``margin`` from it. A line is cut per
piece of an opening's core, each a capsule, and per filled region, in double precision: only correctly
rounded operations and square roots are used, so every platform gives the same pieces, and ``GUARD`` holds
their error. An arc or a circle is cut on its polygon of ``ARC_TOL`` sagitta with the reach grown by that
sagitta; each kept run becomes an arc whose ends and middle are projected on the true circle. The outline
of a rectangle or a polygon is cut as its sides. A piece shorter than the stroke is dropped. A filled shape
is never cut. ``piece_shape`` gives the thick shape that holds a piece's ink, for the exact check.

Pure geometry: no board, no file.
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Literal

from fenolite.core.coords import Point
from fenolite.core.units import Nm
from fenolite.geometry import Arc, Circle, GeometryError, Thick, thick_bbox, thick_closer_than

GUARD: Nm = 1_000
"""1 µm kept beyond the margin: it holds the rounding of a cut end to the nanometre."""
ARC_TOL: Nm = 1_000
"""The sagitta of the polygon an arc or a circle is cut on, and the widening of its check."""
Kind = Literal["line", "arc", "circle", "rect", "polygon"]
_Interval = tuple[float, float]


@dataclass(frozen=True, slots=True)
class Piece:
    """A kept piece of a stroke: two points for a line, ``(start, mid, end)`` for an arc."""

    points: tuple[Point, ...]

    @property
    def kind(self) -> Literal["line", "arc"]:
        return "line" if len(self.points) == 2 else "arc"


@dataclass(frozen=True, slots=True)
class Cut:
    """What ``cut`` made of a stroke that comes near an opening: the kept pieces, the number of pieces
    dropped as shorter than the stroke, and ``skipped`` for a filled shape, which is not cut."""

    pieces: tuple[Piece, ...]
    dropped: int = 0
    skipped: bool = False


def corners(kind: Kind, points: Sequence[Point]) -> tuple[Point, ...]:
    """The closed outline of a rectangle (from its two corners) or of a polygon, first point repeated."""
    if kind == "rect":
        a, b = points[0], points[1]
        ring = (a, Point(b.x, a.y), b, Point(a.x, b.y))
    else:
        ring = tuple(points)
    return (*ring, ring[0])


def stroke_shapes(kind: Kind, points: Sequence[Point], width: Nm) -> list[Thick]:
    """Thick shapes that hold the ink of an unfilled stroke (arcs and circles on their polygon, widened
    by the sagitta)."""
    pen = max(width, 1)
    if kind == "line":
        a, b = points[0], points[1]
        return [Thick((a, b) if a != b else (a,), pen)]
    if kind == "arc":
        return [Thick(Arc(points[0], points[1], points[2]).polygonize(ARC_TOL), pen + 2 * ARC_TOL + 2)]
    if kind == "circle":
        ring = Circle.from_kicad(points[0], points[1]).polygonize(ARC_TOL)
        return [Thick((*ring, ring[0]), pen + 2 * ARC_TOL + 2)]
    return [Thick(corners(kind, points), pen)]


def piece_shape(piece: Piece, width: Nm) -> Thick:
    """The thick shape that holds a piece's ink."""
    return stroke_shapes(piece.kind, piece.points, width)[0]


def near_openings(shapes: Sequence[Thick], openings: Sequence[Thick], limit: int) -> list[Thick]:
    """The openings that some shape comes closer to than ``limit``."""
    found: list[Thick] = []
    for opening in openings:
        box = thick_bbox(opening).inflate(limit)
        if any(
            thick_bbox(shape).intersects(box) and thick_closer_than(shape, opening, limit) for shape in shapes
        ):
            found.append(opening)
    return found


# --- the forbidden part of a segment --------------------------------------------------------------------


def _linear(k0: float, k1: float, lo: float, hi: float) -> _Interval | None:
    """The ``t`` with ``lo < k0 + k1·t < hi``."""
    if k1 == 0.0:
        return (-math.inf, math.inf) if lo < k0 < hi else None
    a, b = (lo - k0) / k1, (hi - k0) / k1
    return (min(a, b), max(a, b))


def _disc(px: float, py: float, dx: float, dy: float, cx: float, cy: float, r: float) -> _Interval | None:
    """The ``t`` with ``|p + t·d − c| < r``."""
    ex, ey = px - cx, py - cy
    a = dx * dx + dy * dy
    b = 2.0 * (dx * ex + dy * ey)
    c = ex * ex + ey * ey - r * r
    if a == 0.0:
        return (-math.inf, math.inf) if c < 0.0 else None
    disc = b * b - 4.0 * a * c
    if disc <= 0.0:
        return None
    root = math.sqrt(disc)
    return ((-b - root) / (2.0 * a), (-b + root) / (2.0 * a))


def _capsule(
    p: tuple[float, float], d: tuple[float, float], a: Point, b: Point, r: float
) -> _Interval | None:
    """The ``t`` where ``p + t·d`` lies within ``r`` of the segment ``ab`` (a convex set: one interval)."""
    px, py = p
    dx, dy = d
    found = [
        hit
        for hit in (_disc(px, py, dx, dy, a.x, a.y, r), _disc(px, py, dx, dy, b.x, b.y, r))
        if hit is not None
    ]
    ux, uy = float(b.x - a.x), float(b.y - a.y)
    length = math.sqrt(ux * ux + uy * uy)
    if length > 0.0:
        ux, uy = ux / length, uy / length
        ex, ey = px - a.x, py - a.y
        along = _linear(ex * ux + ey * uy, dx * ux + dy * uy, 0.0, length)
        across = _linear(ex * -uy + ey * ux, dx * -uy + dy * ux, -r, r)
        if along is not None and across is not None:
            lo, hi = max(along[0], across[0]), min(along[1], across[1])
            if lo < hi:
                found.append((lo, hi))
    if not found:
        return None
    return (min(hit[0] for hit in found), max(hit[1] for hit in found))


def _inside(x: float, y: float, ring: Sequence[Point]) -> bool:
    """Even-odd test of a point against a ring."""
    inside = False
    count = len(ring)
    for index in range(count):
        a, b = ring[index], ring[(index + 1) % count]
        if (a.y > y) != (b.y > y):
            cross = a.x + (y - a.y) * (b.x - a.x) / (b.y - a.y)
            if x < cross:
                inside = not inside
    return inside


def _region(p: tuple[float, float], d: tuple[float, float], ring: Sequence[Point]) -> list[_Interval]:
    """The ``t`` in [0, 1] where ``p + t·d`` lies inside a filled ring."""
    px, py = p
    dx, dy = d
    marks = [0.0, 1.0]
    count = len(ring)
    for index in range(count):
        a, b = ring[index], ring[(index + 1) % count]
        ex, ey = float(b.x - a.x), float(b.y - a.y)
        denom = dx * ey - dy * ex
        if denom == 0.0:
            continue
        wx, wy = a.x - px, a.y - py
        t = (wx * ey - wy * ex) / denom
        s = (wx * dy - wy * dx) / denom
        if 0.0 < t < 1.0 and 0.0 <= s <= 1.0:
            marks.append(t)
    marks.sort()
    found: list[_Interval] = []
    for lo, hi in zip(marks, marks[1:], strict=False):
        if hi > lo:
            mid = (lo + hi) / 2.0
            if _inside(px + mid * dx, py + mid * dy, ring):
                found.append((lo, hi))
    return found


def _forbidden(a: Point, b: Point, openings: Sequence[Thick], reach: float) -> list[_Interval]:
    """The merged ``t`` in [0, 1] of the segment ``ab`` that lie within ``reach`` of an opening."""
    p = (float(a.x), float(a.y))
    d = (float(b.x - a.x), float(b.y - a.y))
    hits: list[_Interval] = []
    for opening in openings:
        r = reach + opening.width / 2.0
        core = opening.core
        if len(core) == 1:
            hit = _disc(p[0], p[1], d[0], d[1], core[0].x, core[0].y, r)
            if hit is not None:
                hits.append(hit)
            continue
        edges = list(zip(core, core[1:], strict=False))
        if opening.filled:
            edges.append((core[-1], core[0]))
            hits.extend(_region(p, d, core))
        for start, end in edges:
            hit = _capsule(p, d, start, end, r)
            if hit is not None:
                hits.append(hit)
    clamped = sorted((max(lo, 0.0), min(hi, 1.0)) for lo, hi in hits if hi > 0.0 and lo < 1.0)
    merged: list[_Interval] = []
    for lo, hi in clamped:
        if merged and lo <= merged[-1][1]:
            merged[-1] = (merged[-1][0], max(merged[-1][1], hi))
        else:
            merged.append((lo, hi))
    return merged


def _kept(forbidden: Sequence[_Interval]) -> list[_Interval]:
    found: list[_Interval] = []
    at = 0.0
    for lo, hi in forbidden:
        if lo > at:
            found.append((at, lo))
        at = max(at, hi)
    if at < 1.0:
        found.append((at, 1.0))
    return found


def _at(a: Point, b: Point, t: float) -> Point:
    return Point(round(a.x + t * (b.x - a.x)), round(a.y + t * (b.y - a.y)))


def _length(a: Point, b: Point) -> float:
    return math.hypot(float(b.x - a.x), float(b.y - a.y))


# --- the cut of each kind --------------------------------------------------------------------------------


def _cut_segment(
    a: Point, b: Point, width: Nm, openings: Sequence[Thick], reach: float
) -> tuple[list[Piece], int]:
    length = _length(a, b)
    pieces: list[Piece] = []
    dropped = 0
    for lo, hi in _kept(_forbidden(a, b, openings, reach)):
        start, end = _at(a, b, lo), _at(a, b, hi)
        if (hi - lo) * length < max(width, 1) or start == end:
            dropped += 1
            continue
        pieces.append(Piece((start, end)))
    return pieces, dropped


def _runs(
    chain: Sequence[Point], openings: Sequence[Thick], reach: float, closed: bool
) -> list[list[tuple[int, float]]]:
    """The kept runs along a chain of chords, each a list of ``(chord, t)`` marks from its start to its end
    (the chords it passes whole in between); a closed chain's run may wrap over its first point."""
    chords = len(chain) - 1
    runs: list[list[tuple[int, float]]] = []
    current: list[tuple[int, float]] | None = None
    for index in range(chords):
        kept = _kept(_forbidden(chain[index], chain[index + 1], openings, reach))
        for lo, hi in kept:
            if current is not None and lo == 0.0:
                current.append((index, hi))
            else:
                if current is not None:
                    runs.append(current)
                current = [(index, lo), (index, hi)]
            if hi < 1.0:
                runs.append(current)
                current = None
        if not kept and current is not None:
            runs.append(current)
            current = None
    if current is not None:
        runs.append(current)
    if closed and len(runs) > 1 and runs[0][0] == (0, 0.0) and runs[-1][-1] == (chords - 1, 1.0):
        runs[0] = runs.pop() + runs[0]
    return runs


def _chain_point(chain: Sequence[Point], mark: tuple[int, float]) -> tuple[float, float]:
    index, t = mark
    a, b = chain[index], chain[index + 1]
    return (a.x + t * (b.x - a.x), a.y + t * (b.y - a.y))


def _on_circle(q: tuple[float, float], centre: tuple[float, float], radius: float) -> Point:
    vx, vy = q[0] - centre[0], q[1] - centre[1]
    norm = math.hypot(vx, vy)
    if norm == 0.0:
        return Point(round(q[0]), round(q[1]))
    return Point(round(centre[0] + vx * radius / norm), round(centre[1] + vy * radius / norm))


def _run_arc(
    chain: Sequence[Point], run: list[tuple[int, float]], centre: tuple[float, float], radius: float
) -> tuple[Piece | None, float]:
    """The arc of a run and the length of its chain."""
    points = [_chain_point(chain, mark) for mark in run]
    steps = [math.hypot(b[0] - a[0], b[1] - a[1]) for a, b in zip(points, points[1:], strict=False)]
    total = sum(steps)
    half, walked = total / 2.0, 0.0
    middle = points[0]
    for (a, b), step in zip(zip(points, points[1:], strict=False), steps, strict=True):
        if walked + step >= half and step > 0.0:
            f = (half - walked) / step
            middle = (a[0] + f * (b[0] - a[0]), a[1] + f * (b[1] - a[1]))
            break
        walked += step
    start, mid, end = (_on_circle(q, centre, radius) for q in (points[0], middle, points[-1]))
    if len({start, mid, end}) < 3:
        return None, total
    try:
        Arc(start, mid, end)
    except GeometryError:
        return None, total
    return Piece((start, mid, end)), total


def _cut_round(
    kind: Kind, points: Sequence[Point], width: Nm, openings: Sequence[Thick], reach: float
) -> tuple[list[Piece], int] | None:
    """The arc pieces of an arc or a circle; ``None`` when the whole stroke is kept."""
    if kind == "arc":
        arc = Arc(points[0], points[1], points[2])
        exact = arc.centre
        if exact is None:  # a straight arc: its two ends
            return _cut_segment(points[0], points[2], width, openings, reach)
        centre = (float(exact[0]), float(exact[1]))
        radius = math.sqrt(float(arc.radius2 or 0))
        chain = list(arc.polygonize(ARC_TOL))
        closed = False
    else:
        circle = Circle.from_kicad(points[0], points[1])
        centre = (float(circle.centre.x), float(circle.centre.y))
        radius = math.sqrt(float(circle.radius2))
        ring = circle.polygonize(ARC_TOL)
        chain = [*ring, ring[0]]
        closed = True
    runs = _runs(chain, openings, reach + ARC_TOL + 2, closed)
    if len(runs) == 1 and runs[0][0] == (0, 0.0) and runs[0][-1] == (len(chain) - 2, 1.0):
        return None
    pieces: list[Piece] = []
    dropped = 0
    for run in runs:
        piece, length = _run_arc(chain, run, centre, radius)
        if piece is None or length < max(width, 1):
            dropped += 1
            continue
        pieces.append(piece)
    return pieces, dropped


def _region_shape(kind: Kind, points: Sequence[Point], width: Nm) -> list[Thick]:
    """Thick shapes that hold a filled shape with its outline."""
    pen = max(width, 1)
    try:
        if kind == "circle":
            ring = Circle.from_kicad(points[0], points[1]).polygonize(ARC_TOL, outer=True)
            return [Thick(ring, pen, filled=True)]
        return [Thick(corners(kind, points)[:-1], pen, filled=True)]
    except (GeometryError, ValueError):
        return stroke_shapes(kind, points, width)


def cut(
    kind: Kind,
    points: Sequence[Point],
    width: Nm,
    openings: Sequence[Thick],
    margin: Nm,
    *,
    filled: bool = False,
) -> Cut | None:
    """The pieces of a stroke kept ``margin`` from every opening; ``None`` when its ink already keeps
    ``margin + GUARD`` from all of them (decided exactly), so it is left as it is. A filled rectangle,
    polygon or circle near an opening is ``Cut((), skipped=True)``."""
    if filled and kind in ("rect", "polygon", "circle"):
        return (
            Cut((), skipped=True)
            if near_openings(_region_shape(kind, points, width), openings, margin)
            else None
        )
    near = near_openings(stroke_shapes(kind, points, width), openings, margin + GUARD)
    if not near:
        return None
    reach = margin + GUARD + width / 2.0
    if kind == "line":
        pieces, dropped = _cut_segment(points[0], points[1], width, near, reach)
        if pieces == [Piece((points[0], points[1]))]:
            return None
    elif kind in ("arc", "circle"):
        found = _cut_round(kind, points, width, near, reach)
        if found is None:
            return None
        pieces, dropped = found
    else:
        outline = corners(kind, points)
        pieces: list[Piece] = []
        dropped = 0
        for a, b in zip(outline, outline[1:], strict=False):
            if a == b:
                continue
            side_pieces, side_dropped = _cut_segment(a, b, width, near, reach)
            pieces.extend(side_pieces)
            dropped += side_dropped
    return Cut(tuple(pieces), dropped)


__all__ = [
    "ARC_TOL",
    "GUARD",
    "Cut",
    "Kind",
    "Piece",
    "corners",
    "cut",
    "near_openings",
    "piece_shape",
    "stroke_shapes",
]
