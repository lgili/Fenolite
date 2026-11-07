# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Private exact difference of integer polygon sets, realized on integers (c0332 redesign).

The subject and cut polygons fall into groups: two polygons share a group when their closed boxes, grown
by ``MARGIN`` nanometres, meet. A group without a cut polygon is kept as it is. Each other group is cut
exactly (``_exact_faces.difference_loops``) and realized on integers (``_exact_snap.draw``). A drawing lies
within half a nanometre per axis of its exact boundary, inside its group's box, so groups never interact.

A group whose arrangement would exceed ``strip_edges`` source edges is cut into rectangular cells, by
recursive integer seams on x or y at the median vertex, avoiding every vertex coordinate. Every subject and
cut ring is clipped exactly to each closed half (rational ends on the seam line), which keeps its winding
inside that half, so each cell holds the difference restricted to it. Each cell is cut and drawn on its own.
A cell's drawing lies inside its closed cell (its nodes do, and so do straight segments and pixel centres
between them), so drawings of different cells meet only on seam lines; there their edges are split at every
vertex on the line and opposite currents cancel (``_exact_snap.merge``): the result is the boundary of the
union of regions with disjoint interiors. Every existing per-arrangement storage cap holds in each cell,
and every cell charges the one per-operation ``Budget``.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from fractions import Fraction

from fenolite.geometry.boolean._exact_faces import difference_loops
from fenolite.geometry.boolean._exact_noding import Budget, ExactPoint, IntPoint, Segment, SourcePoint
from fenolite.geometry.boolean._exact_snap import assemble, draw, merge, protected_corners
from fenolite.geometry.errors import GeometryError
from fenolite.geometry.index import SpatialIndex
from fenolite.geometry.polygon import Polygon, normalize_polygons
from fenolite.geometry.shapes import BBox

MARGIN = 2
"""Nanometres by which polygon boxes grow before they group: more than the reach of two drawings."""


@dataclass(frozen=True, slots=True)
class Cut:
    """The realized difference, before any debris policy, and what the realization did."""

    polygons: tuple[Polygon, ...]
    erased: frozenset[IntPoint]
    groups: int
    strips: int
    bent: int
    rounds: int


def _box(poly: Polygon, margin: int) -> BBox:
    box = poly.bbox()
    return BBox(box.x0 - margin, box.y0 - margin, box.x1 + margin, box.y1 + margin)


GROUP_WORK = 1_000_000
"""Index visits plus overlapping pairs the grouping may spend; beyond it everything is one group."""


class _Crowded(Exception):  # noqa: N818 - internal control flow
    pass


def _groups(subject: Sequence[Polygon], cut: Sequence[Polygon]) -> list[tuple[list[int], list[int]]]:
    items = [*subject, *cut]
    index = SpatialIndex[int].build(((_box(p, MARGIN), i) for i, p in enumerate(items)), capacity=8)
    parent = list(range(len(items)))
    work = 0

    def visit() -> None:
        nonlocal work
        work += 1
        if work > GROUP_WORK:
            raise _Crowded

    def reserve(count: int) -> None:
        if count > GROUP_WORK:
            raise _Crowded

    def find(x: int) -> int:
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    try:
        for i, j in index._join_pairs(visit, reserve):  # pyright: ignore[reportPrivateUsage]
            visit()
            a, b = find(i), find(j)
            if a != b:
                parent[max(a, b)] = min(a, b)
    except _Crowded:  # densely overlapping boxes: one group, the whole arrangement
        return [(list(range(len(subject))), list(range(len(cut))))]
    members: dict[int, tuple[list[int], list[int]]] = {}
    for i in range(len(items)):
        group = members.setdefault(find(i), ([], []))
        if i < len(subject):
            group[0].append(i)
        else:
            group[1].append(i - len(subject))
    return [members[k] for k in sorted(members)]


def _clip(
    points: Sequence[SourcePoint], low: int | None, high: int | None, axis: int = 0
) -> list[SourcePoint]:
    """The ring ``points`` clipped exactly to the closed slab ``low <= p[axis] <= high`` (Sutherland-Hodgman
    per side); an intersection keeps an ``int`` coordinate when it is integral."""
    other = 1 - axis
    for bound, keep in ((low, 1), (high, -1)):
        if bound is None or not points:
            continue
        out: list[SourcePoint] = []
        for k, current in enumerate(points):
            previous = points[k - 1]
            inside_now = (current[axis] - bound) * keep >= 0
            inside_before = (previous[axis] - bound) * keep >= 0
            if inside_now != inside_before:
                u0, v0, u1, v1 = previous[axis], previous[other], current[axis], current[other]
                v = Fraction(v0) + (bound - Fraction(u0)) * (Fraction(v1) - v0) / (Fraction(u1) - u0)
                w: int | Fraction = int(v) if v.denominator == 1 else v
                out.append((bound, w) if axis == 0 else (w, bound))
            if inside_now:
                out.append(current)
        points = out
    result: list[SourcePoint] = []
    for p in points:
        if not result or result[-1] != p:
            result.append(p)
    while len(result) > 1 and result[0] == result[-1]:
        result.pop()
    return result if len(result) >= 3 else []


Cell = list[tuple[list[SourcePoint], int]]


def _seam(cell: Cell, axis: int) -> int | None:
    """An integer strictly inside the cell's extent on ``axis``, near its median vertex, of no vertex."""
    values = sorted(p[axis] for ring, _ in cell for p in ring)
    taken = {v for v in values if type(v) is int}
    low, high = values[0], values[-1]
    middle = values[len(values) // 2].__floor__()
    for step in range(4096):
        for seam in (middle + step, middle - step - 1):
            if low < seam < high and seam not in taken:
                return seam
    return None


def _cells(cell: Cell, target: int, seams: set[tuple[int, int]]) -> list[Cell]:
    """``cell`` split until each part holds at most ``target`` edges, or no seam reduces it any more."""
    done: list[Cell] = []
    todo = [cell]
    while todo:
        current = todo.pop()
        size = sum(len(ring) for ring, _ in current)
        if size <= target:
            done.append(current)
            continue
        extents: list[tuple[int | Fraction, int]] = []
        for axis in (0, 1):
            values = [p[axis] for ring, _ in current for p in ring]
            extents.append((max(values) - min(values), axis))
        for _, axis in sorted(extents, reverse=True):
            seam = _seam(current, axis)
            if seam is None:
                continue
            halves = [
                [(clipped, channel) for ring, channel in current if (clipped := _clip(ring, low, high, axis))]
                for low, high in ((None, seam), (seam, None))
            ]
            if all(sum(len(ring) for ring, _ in half) < size for half in halves):
                seams.add((axis, seam))
                todo.extend(reversed(halves))
                break
        else:
            done.append(current)
    return done


def _segments(points: Sequence[SourcePoint], channel: int) -> list[Segment]:
    return [Segment(a, b, channel) for a, b in zip(points, [*points[1:], points[0]], strict=True)]


def exact_difference(
    subject: Sequence[Polygon], cut: Sequence[Polygon], budget: Budget, *, strip_edges: int | None = None
) -> Cut:
    """``subject`` minus ``cut`` (non-zero rule on both), exact and then realized on integers."""
    target = budget.limits.input_edges // 2 if strip_edges is None else strip_edges
    if target < 1:
        raise GeometryError("exact cut strip size must be positive")
    kept: list[Polygon] = []
    drawings: list[tuple[tuple[IntPoint, IntPoint], ...]] = []
    source: set[SourcePoint] = set()
    bent = rounds = strips = groups = 0
    loops_all: list[tuple[ExactPoint, ...]] = []
    segments_all: list[Segment] = []
    seams: set[tuple[int, int]] = set()
    for subject_ids, cut_ids in _groups(subject, cut):
        polys = [subject[i] for i in subject_ids]
        if not cut_ids:
            kept.extend(polys)
            continue
        if not polys:
            continue
        groups += 1
        pieces = [cut[j] for j in cut_ids]
        rings: Cell = [
            ([(p.x, p.y) for p in ring], channel)
            for channel, members in ((0, polys), (1, pieces))
            for poly in members
            for ring in poly.rings()
        ]
        source.update(p for ring, _ in rings for p in ring)  # integers before any clipping
        for part in _cells(rings, target, seams):
            strips += 1
            segments = [s for ring, channel in part for s in _segments(ring, channel)]
            if len(segments) > budget.limits.input_edges:
                raise GeometryError("exact geometry input-edge budget exceeded")
            loops = difference_loops(segments, budget)
            budget.stage("drawing")
            drawing = draw(loops, budget)
            drawings.append(drawing.boundary)
            bent += drawing.bent
            rounds = max(rounds, drawing.rounds)
            loops_all.extend(loops)
            segments_all.extend(segments)
    budget.stage("assembly")
    protected = protected_corners(loops_all, [s for s in segments_all if _integer(s)]) & frozenset(source)
    boundary = merge(drawings, sorted(seams)) if len(drawings) > 1 else list(drawings[0] if drawings else ())
    snapped = assemble(boundary, protected, budget)
    return Cut(normalize_polygons((*kept, *snapped.polygons)), snapped.erased, groups, strips, bent, rounds)


def _integer(s: Segment) -> bool:
    return all(type(c) is int for p in (s.a, s.b) for c in p)
