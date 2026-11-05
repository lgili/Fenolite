# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Private selective snap rounding of exact selected loops (c0332 redesign).

Every exact boundary node goes to its half-even integer point. An exact edge is
drawn straight between the points of its ends (nearest projection) unless that
drawing conflicts with another one; a conflicting edge instead passes through
the centre of every hot pixel it meets, in order (snap rounding). A hot pixel is
the set of points whose half-even projection is the projection of an exact node.
Bending only adds pixel centres met by the edge, so every point of every drawing
lies within half a nanometre per axis of its exact edge, in the straight-line
deformation too: membership of a point farther than that from the exact
boundary never changes.

The drawings are re-noded on integers, opposite currents cancel, and the result
is accepted only when no two integer edges cross, every edge keeps a unit
current and every face winds 0 or 1. A conflict bends more edges; when every
edge is bent the drawing is the snap rounding of the arrangement, which has no
crossings. A remaining conflict then refuses. No backend or file is used.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable, Iterator, Sequence
from dataclasses import dataclass
from fractions import Fraction as F
from functools import cmp_to_key
from math import ceil, floor

from fenolite.geometry.boolean._exact_noding import Budget, ExactPoint, IntPoint, Segment, candidate_pairs
from fenolite.geometry.boolean._exact_seed_index import ClosedYIndex
from fenolite.geometry.errors import GeometryError
from fenolite.geometry.index import SpatialIndex
from fenolite.geometry.polygon import Polygon, normalize_polygons
from fenolite.geometry.shapes import BBox
from fenolite.geometry.vector import Point

ExactRing = tuple[ExactPoint, ...]
IntRing = tuple[IntPoint, ...]
EdgeId = tuple[int, int]
HALF = F(1, 2)
CELL = 1 << 12
UNIT = ((F(0), True), (F(1), True))


def require(condition: bool, message: str) -> None:
    if not condition:
        raise GeometryError("exact snap rounding: " + message)


def half_even(value: F) -> int:
    q, r = divmod(value.numerator, value.denominator)
    return q + int(2 * r > value.denominator or (2 * r == value.denominator and q % 2 != 0))


def project(p: ExactPoint) -> IntPoint:
    return half_even(p[0]), half_even(p[1])


Bound = tuple[F, bool]


def _axis(p: F, d: F, c: int) -> tuple[Bound, Bound] | None:
    """The parameters ``t`` at which ``p + t d`` has half-even projection ``c`` (closed for even ``c``)."""
    closed = c % 2 == 0
    lo, hi = c - HALF, c + HALF
    if d == 0:
        inside = lo <= p <= hi if closed else lo < p < hi
        return ((F(-1), True), (F(2), True)) if inside else None
    a, b = (lo - p) / d, (hi - p) / d
    if a > b:
        a, b = b, a
    return (a, closed), (b, closed)


def _meet(r: tuple[Bound, Bound], s: tuple[Bound, Bound]) -> tuple[Bound, Bound] | None:
    lo = max(r[0], s[0], key=lambda x: (x[0], not x[1]))
    hi = min(r[1], s[1], key=lambda x: (x[0], x[1]))
    if lo[0] < hi[0] or (lo[0] == hi[0] and lo[1] and hi[1]):
        return lo, hi
    return None


def pixel_hit(a: ExactPoint, b: ExactPoint, c: IntPoint) -> tuple[Bound, Bound] | None:
    """The parameter interval of segment ``ab`` inside the hot pixel of ``c``, or None."""
    rx = _axis(a[0], b[0] - a[0], c[0])
    if rx is None:
        return None
    ry = _axis(a[1], b[1] - a[1], c[1])
    if ry is None:
        return None
    r = _meet(rx, ry)
    return None if r is None else _meet(r, UNIT)


class _Hot:
    """Hot pixel centres bucketed on a coarse integer grid."""

    def __init__(self, centres: Iterable[IntPoint]) -> None:
        self.grid: dict[IntPoint, list[IntPoint]] = defaultdict(list)
        for c in sorted(set(centres)):
            self.grid[c[0] // CELL, c[1] // CELL].append(c)

    def near(self, a: ExactPoint, b: ExactPoint, budget: Budget) -> set[IntPoint]:
        x0, x1 = min(a[0], b[0]) - 1, max(a[0], b[0]) + 1
        dx = b[0] - a[0]
        found: set[IntPoint] = set()
        for cx in range(x0.__floor__() // CELL, x1.__floor__() // CELL + 1):
            if dx == 0:
                ylo, yhi = min(a[1], b[1]), max(a[1], b[1])
            else:
                xs = max(F(cx * CELL) - 1, x0), min(F((cx + 1) * CELL) + 1, x1)
                ys = [a[1] + (x - a[0]) * (b[1] - a[1]) / dx for x in xs]
                ylo, yhi = max(min(ys), min(a[1], b[1])), min(max(ys), max(a[1], b[1]))
            for cy in range((ylo - 1).__floor__() // CELL, (yhi + 1).__floor__() // CELL + 1):
                cell = self.grid.get((cx, cy))
                if cell:
                    budget.visit(len(cell))
                    found.update(cell)
        return found


def _line(a: ExactPoint, b: ExactPoint) -> tuple[int, int, int, int]:
    """Integers ``nx, ny, k, w`` such that the closed pixel of centre ``c`` meets the line ``ab`` exactly when
    ``2 |nx c0 + ny c1 - k| <= w``."""
    nx, ny = a[1] - b[1], b[0] - a[0]
    k = nx * a[0] + ny * a[1]
    scale = F(nx).denominator * F(ny).denominator * F(k).denominator
    nx, ny, k = int(nx * scale), int(ny * scale), int(k * scale)
    return nx, ny, k, abs(nx) + abs(ny)


def _bend(a: ExactPoint, b: ExactPoint, hot: _Hot, budget: Budget) -> list[IntPoint]:
    """The hot pixel centres met by ``ab`` in order, from the projection of ``a`` to that of ``b``."""
    found: list[tuple[Bound, IntPoint]] = []
    nx, ny, k, w = _line(a, b)
    for c in hot.near(a, b, budget):
        if 2 * abs(nx * c[0] + ny * c[1] - k) > w:  # the pixel misses the line: ``pixel_hit`` is None
            continue
        r = pixel_hit(a, b, c)
        if r is not None:
            found.append(((r[0][0], not r[0][1]), c))
    found.sort()
    path = [c for _, c in found]
    require(bool(path) and path[0] == project(a) and path[-1] == project(b), "bent edge leaves its ends")
    return path


def _orient(a: IntPoint, b: IntPoint, c: IntPoint) -> int:
    v = (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0])
    return (v > 0) - (v < 0)


def _inside(p: IntPoint, a: IntPoint, b: IntPoint) -> bool:
    """``p`` lies on segment ``ab`` strictly between its ends."""
    return (
        p != a
        and p != b
        and _orient(a, b, p) == 0
        and min(a[0], b[0]) <= p[0] <= max(a[0], b[0])
        and min(a[1], b[1]) <= p[1] <= max(a[1], b[1])
    )


def _angular(center: IntPoint, a: IntPoint, b: IntPoint) -> int:
    x = (a[0] - center[0], a[1] - center[1])
    y = (b[0] - center[0], b[1] - center[1])
    first = 0 if x[1] > 0 or (x[1] == 0 and x[0] >= 0) else 1
    second = 0 if y[1] > 0 or (y[1] == 0 and y[0] >= 0) else 1
    if first != second:
        return first - second
    det = x[0] * y[1] - x[1] * y[0]
    require(det != 0 or x == y, "overlapping integer directions")
    return -((det > 0) - (det < 0))


def _area2(ring: IntRing) -> int:
    return sum(a[0] * b[1] - b[0] * a[1] for a, b in zip(ring, ring[1:] + ring[:1], strict=True))


def _winding(edge: tuple[IntPoint, IntPoint], sources: Iterable[Segment]) -> int:
    """Winding of the integer chain just left of the midpoint of ``edge`` (formal infinitesimal)."""
    a, b = edge
    mx, my = a[0] + b[0], a[1] + b[1]  # doubled midpoint
    nx, ny = -(b[1] - a[1]), b[0] - a[0]
    value = 0
    for s in sources:
        ya, yb = 2 * s.a[1] - my, 2 * s.b[1] - my
        sa = (ya > 0) - (ya < 0) if ya else (ny < 0) - (ny > 0)
        sb = (yb > 0) - (yb < 0) if yb else (ny < 0) - (ny > 0)
        up, down = sa <= 0 < sb, sb <= 0 < sa
        if not (up or down):
            continue
        dx, dy = s.b[0] - s.a[0], s.b[1] - s.a[1]
        o = dx * (my - 2 * s.a[1]) - dy * (mx - 2 * s.a[0])
        if o == 0:
            o = dx * ny - dy * nx
        require(o != 0, "seed remains on an integer edge")
        if up and o > 0:
            value += 1
        if down and o < 0:
            value -= 1
    return value


class _Rows:
    """Integer edges in horizontal bands: a query returns every edge whose closed y range holds the
    level (and some that do not, which the exact winding ignores)."""

    def __init__(self, edges: Sequence[Segment], budget: Budget) -> None:
        self.edges = edges
        ys = [c for s in edges for c in (s.a[1], s.b[1])]
        self.low = min(ys, default=0)
        span = max(ys, default=0) - self.low
        self.height = max(1, -(-span // 4096))
        self.bands: dict[int, list[int]] = defaultdict(list)
        for k, s in enumerate(edges):
            lo, hi = sorted((s.a[1], s.b[1]))
            first, last = (lo - self.low) // self.height, (hi - self.low) // self.height
            budget.visit(last - first + 1)
            for band in range(first, last + 1):
                self.bands[band].append(k)

    def near(self, doubled_y: int) -> list[Segment]:
        """The edges of the band of level ``doubled_y / 2``."""
        band = (doubled_y // 2 - self.low) // self.height
        return [self.edges[k] for k in self.bands.get(band, ())]


def _clean(ring: IntRing) -> IntRing:
    current = ring
    while True:
        dedup = tuple(p for i, p in enumerate(current) if i == 0 or p != current[i - 1])
        if len(dedup) > 1 and dedup[0] == dedup[-1]:
            dedup = dedup[:-1]
        if len(dedup) < 3:
            return dedup
        result = tuple(
            p for i, p in enumerate(dedup) if _orient(dedup[i - 1], p, dedup[(i + 1) % len(dedup)]) != 0
        )
        if result == current:
            return result
        current = result


def _split_contacts(ring: IntRing) -> list[IntRing]:
    todo = [ring]
    result: list[IntRing] = []
    while todo:
        current = todo.pop()
        seen: dict[IntPoint, int] = {}
        for i, p in enumerate(current):
            if p in seen:
                j = seen[p]
                first, second = current[j:i], current[:j] + current[i:]
                require(len(first) >= 3 and len(second) >= 3, "degenerate integer contact")
                todo.extend((second, first))
                break
            seen[p] = i
        else:
            result.append(current)
    return result


@dataclass(frozen=True, slots=True)
class Snapped:
    """The realized rings, their polygons and what the realization changed."""

    rings: tuple[IntRing, ...]
    polygons: tuple[Polygon, ...]
    bent: int
    rounds: int
    erased: frozenset[IntPoint]


class _Conflict(Exception):  # noqa: N818 - internal control flow, never escapes this module
    def __init__(self, sources: set[EdgeId]) -> None:
        super().__init__()
        self.sources = sources


def _draw(
    loops: Sequence[ExactRing],
    bent: set[EdgeId],
    paths: dict[EdgeId, list[IntPoint]],
    hot: _Hot,
    budget: Budget,
) -> list[tuple[IntPoint, IntPoint, EdgeId]]:
    edges: list[tuple[IntPoint, IntPoint, EdgeId]] = []
    for i, ring in enumerate(loops):
        n = len(ring)
        for j in range(n):
            a, b = ring[j], ring[(j + 1) % n]
            if (i, j) in bent:
                if (i, j) not in paths:
                    paths[i, j] = _bend(a, b, hot, budget)
                path = paths[i, j]
            else:
                path = [project(a), project(b)]
            for p, q in zip(path, path[1:], strict=False):
                if p != q:
                    edges.append((p, q, (i, j)))
        budget.check()
    return edges


def _planar(
    edges: Sequence[tuple[IntPoint, IntPoint, EdgeId]], budget: Budget
) -> tuple[dict[tuple[IntPoint, IntPoint], int], dict[tuple[IntPoint, IntPoint], set[EdgeId]]]:
    """Split at integer points inside other edges; refuse proper crossings; sum the currents."""
    boxes = [
        Segment((min(p[0], q[0]), min(p[1], q[1])), (max(p[0], q[0]), max(p[1], q[1])), 0)
        for p, q, _ in edges
    ]
    pairs = candidate_pairs(boxes, budget, edge_limit=budget.limits.fragments, start_stage=False)
    cuts: dict[int, set[IntPoint]] = defaultdict(set)
    crossing: set[EdgeId] = set()
    for k, (u, v) in enumerate(pairs):
        if k % 1024 == 0:
            budget.check(1024)
        a, b, s = edges[u]
        c, d, t = edges[v]
        o1, o2, o3, o4 = _orient(a, b, c), _orient(a, b, d), _orient(c, d, a), _orient(c, d, b)
        if o1 * o2 < 0 and o3 * o4 < 0:
            crossing.update((s, t))
            continue
        for p in (c, d):
            if _inside(p, a, b):
                cuts[u].add(p)
        for p in (a, b):
            if _inside(p, c, d):
                cuts[v].add(p)
    if crossing:
        raise _Conflict(crossing)
    current: dict[tuple[IntPoint, IntPoint], int] = defaultdict(int)
    owners: dict[tuple[IntPoint, IntPoint], set[EdgeId]] = defaultdict(set)
    for u, (a, b, s) in enumerate(edges):
        points = sorted({a, b, *cuts.get(u, ())})
        direction = 1 if a < b else -1
        for p, q in zip(points, points[1:], strict=False):
            current[p, q] += direction
            owners[p, q].add(s)
    heavy = {e for e, value in current.items() if abs(value) > 1}
    if heavy:
        raise _Conflict(set[EdgeId]().union(*(owners[e] for e in heavy)))
    return {e: value for e, value in current.items() if value}, owners


def _faces(
    current: dict[tuple[IntPoint, IntPoint], int],
    owners: dict[tuple[IntPoint, IntPoint], set[EdgeId]],
    budget: Budget,
) -> list[tuple[IntPoint, IntPoint]]:
    """The halfedges with winding 1 on their left and 0 on their right; refuse any other winding."""
    directed = {(a, b) if value > 0 else (b, a) for (a, b), value in current.items()}
    adjacent: dict[IntPoint, set[IntPoint]] = defaultdict(set)
    for a, b in directed:
        adjacent[a].add(b)
        adjacent[b].add(a)
    require(2 * len(directed) <= budget.limits.halfedges, "halfedge budget exceeded")
    neighbors = {
        p: tuple(sorted(qs, key=cmp_to_key(lambda a, b, p=p: _angular(p, a, b))))
        for p, qs in adjacent.items()
    }
    positions = {p: {q: i for i, q in enumerate(qs)} for p, qs in neighbors.items()}
    left: dict[tuple[IntPoint, IntPoint], int] = {}
    cycles: list[list[tuple[IntPoint, IntPoint]]] = []
    for start in sorted(directed | {(b, a) for a, b in directed}):
        if start in left:
            continue
        require(len(cycles) < budget.limits.faces, "face budget exceeded")
        cycle: list[tuple[IntPoint, IntPoint]] = []
        here = start
        while True:
            left[here] = len(cycles)
            cycle.append(here)
            a, b = here
            here = (b, neighbors[b][(positions[b][a] - 1) % len(neighbors[b])])
            if here == start:
                break
            if len(cycle) % 256 == 0:
                budget.check(256)
        cycles.append(cycle)
    # components of the integer graph, one exterior (negative) cycle each
    component: dict[IntPoint, int] = {}
    marks = 0
    for start in sorted(adjacent):
        if start in component:
            continue
        todo = [start]
        mark = marks
        marks += 1
        while todo:
            p = todo.pop()
            if p in component:
                continue
            component[p] = mark
            todo.extend(q for q in adjacent[p] if q not in component)
    exteriors: dict[int, int] = {}
    for i, cycle in enumerate(cycles):
        if _area2(tuple(a for a, _ in cycle)) < 0:
            c = component[cycle[0][0]]
            require(c not in exteriors, "component exterior not unique")
            exteriors[c] = i
    require(len(exteriors) == marks, "component without exterior")
    sources = [Segment(a, b, 0) for a, b in sorted(directed)]
    rows = _Rows(sources, budget)
    winding: dict[int, int] = {}
    for c in sorted(exteriors):
        outside = exteriors[c]
        edge = cycles[outside][0]
        selected = rows.near(edge[0][1] + edge[1][1])
        budget.visit(len(selected))
        winding[outside] = _winding(edge, selected)
        todo = [outside]
        while todo:
            face = todo.pop()
            for a, b in cycles[face]:
                other = left[b, a]
                # crossing halfedge a->b from its left face to the right face
                value = winding[face] - (1 if (a, b) in directed else -1)
                if other in winding:
                    require(winding[other] == value, "contradictory integer face winding")
                else:
                    winding[other] = value
                    todo.append(other)
            budget.check()
    require(len(winding) == len(cycles), "unresolved integer face winding")
    bad = {i for i, value in winding.items() if value not in (0, 1)}
    if bad:
        culprits: set[EdgeId] = set()
        for i in bad:
            for a, b in cycles[i]:
                culprits.update(owners[min(a, b), max(a, b)])
        raise _Conflict(culprits)
    return [e for e in directed if winding[left[e]] == 1 and winding[left[e[1], e[0]]] == 0]


def _rings(boundary: Sequence[tuple[IntPoint, IntPoint]], budget: Budget) -> list[IntRing]:
    edges = set(boundary)
    require(len(edges) == len(boundary), "duplicate boundary halfedge")
    adjacent: dict[IntPoint, set[IntPoint]] = defaultdict(set)
    for a, b in edges:
        adjacent[a].add(b)
        adjacent[b].add(a)
    neighbors = {
        p: tuple(sorted(qs, key=cmp_to_key(lambda a, b, p=p: _angular(p, a, b))))
        for p, qs in adjacent.items()
    }
    positions = {p: {q: i for i, q in enumerate(qs)} for p, qs in neighbors.items()}
    visited: set[tuple[IntPoint, IntPoint]] = set()
    rings: list[IntRing] = []
    for start in sorted(edges):
        if start in visited:
            continue
        points: list[IntPoint] = []
        here = start
        while True:
            require(here not in visited, "boundary halfedge visited twice")
            visited.add(here)
            a, b = here
            points.append(a)
            following = None
            around = neighbors[b]
            back = positions[b][a]
            for step in range(1, len(around) + 1):
                candidate = (b, around[(back - step) % len(around)])
                if candidate in edges:
                    following = candidate
                    break
            require(following is not None, "open integer boundary")
            assert following is not None
            here = following
            if here == start:
                break
            if len(points) % 256 == 0:
                budget.check(256)
        rings.extend(_split_contacts(tuple(points)))
    return rings


def _ring_winding(p2: IntPoint, edges: Iterable[tuple[IntPoint, IntPoint]]) -> int | None:
    """Winding of the edges (coordinates doubled) around doubled point ``p2``; None on an edge."""
    value = 0
    px, py = p2
    for a, b in edges:
        ax, ay, bx, by = 2 * a[0], 2 * a[1], 2 * b[0], 2 * b[1]
        o = (bx - ax) * (py - ay) - (by - ay) * (px - ax)
        if o == 0 and min(ax, bx) <= px <= max(ax, bx) and min(ay, by) <= py <= max(ay, by):
            return None
        if ay <= py < by and o > 0:
            value += 1
        elif by <= py < ay and o < 0:
            value -= 1
    return value


class _Owner:
    """Integer winding of one outer ring, through a closed y index when the ring is long."""

    def __init__(self, ring: IntRing, budget: Budget) -> None:
        self.edges = tuple(zip(ring, ring[1:] + ring[:1], strict=True))
        self.box = (min(p[0] for p in ring), min(p[1] for p in ring), max(p[0] for p in ring),
                    max(p[1] for p in ring))  # fmt: skip
        self.budget = budget
        self.index: ClosedYIndex | None = None

    def winding(self, p2: IntPoint) -> int | None:
        edges = self.edges
        if len(edges) > 32:
            if self.index is None:
                self.index = ClosedYIndex([Segment(a, b, 0) for a, b in edges], self.budget)
            edges = tuple(self.edges[k] for k in self.index.query(F(p2[1], 2)))
        self.budget.visit(len(edges))
        return _ring_winding(p2, edges)


def _polygons(rings: Sequence[IntRing], budget: Budget) -> tuple[Polygon, ...]:
    areas = [_area2(r) for r in rings]
    outers = {i: _Owner(rings[i], budget) for i, a in enumerate(areas) if a > 0}
    boxes = SpatialIndex[int].build(((BBox(*owner.box), i) for i, owner in outers.items()), capacity=8)
    holes: dict[int, list[int]] = defaultdict(list)
    for i, area in enumerate(areas):
        if area >= 0:
            continue
        found: list[int] = []
        for j in sorted(boxes.query(BBox.of_points(tuple(Point(*p) for p in rings[i])))):
            # a hole lies inside its owner or on its boundary: the first of its doubled edge midpoints
            # and vertices off the owner's boundary decides
            for p2 in (
                *(
                    (a[0] + b[0], a[1] + b[1])
                    for a, b in zip(rings[i], rings[i][1:] + rings[i][:1], strict=True)
                ),
                *((2 * p[0], 2 * p[1]) for p in rings[i]),
            ):
                w = outers[j].winding(p2)
                if w is not None:
                    if w:
                        found.append(j)
                    break
        require(bool(found), "integer hole has no owner")
        holes[min(found, key=lambda j: areas[j])].append(i)
    polys = [
        Polygon(
            tuple(Point(*p) for p in rings[i]),
            tuple(tuple(Point(*p) for p in rings[j]) for j in holes.get(i, ())),
        )
        for i in sorted(outers)
    ]
    return normalize_polygons(polys)


def _box(loops: Sequence[ExactRing], edge: EdgeId) -> BBox:
    ring = loops[edge[0]]
    a, b = ring[edge[1]], ring[(edge[1] + 1) % len(ring)]
    return BBox(
        floor(min(a[0], b[0])) - 1,
        floor(min(a[1], b[1])) - 1,
        ceil(max(a[0], b[0])) + 1,
        ceil(max(a[1], b[1])) + 1,
    )


def _edge_index(loops: Sequence[ExactRing]) -> SpatialIndex[EdgeId]:
    return SpatialIndex[EdgeId].build(
        ((_box(loops, (i, j)), (i, j)) for i, ring in enumerate(loops) for j in range(len(ring))), capacity=8
    )


def _close(
    loops: Sequence[ExactRing],
    bent: set[EdgeId],
    fresh: set[EdgeId],
    paths: dict[EdgeId, list[IntPoint]],
    hot: _Hot,
    index: SpatialIndex[EdgeId],
    budget: Budget,
) -> None:
    """Bend ``fresh`` and every edge that meets a hot pixel a bent edge now passes through (a bent edge
    next to a straight one through the same pixel would only conflict in the next round)."""
    todo = sorted(fresh - bent)
    bent.update(todo)
    while todo:
        edge = todo.pop()
        ring = loops[edge[0]]
        a, b = ring[edge[1]], ring[(edge[1] + 1) % len(ring)]
        if edge not in paths:
            paths[edge] = _bend(a, b, hot, budget)
        for c in paths[edge][1:-1]:
            for other in sorted(index.query(BBox(c[0] - 1, c[1] - 1, c[0] + 1, c[1] + 1))):
                if other in bent:
                    continue
                budget.visit(1)
                ring = loops[other[0]]
                p, q = ring[other[1]], ring[(other[1] + 1) % len(ring)]
                nx, ny, k, w = _line(p, q)
                if 2 * abs(nx * c[0] + ny * c[1] - k) <= w and pixel_hit(p, q, c) is not None:
                    bent.add(other)
                    todo.append(other)


@dataclass(frozen=True, slots=True)
class Drawing:
    """Directed integer boundary edges, winding 1 on their left and 0 on their right."""

    boundary: tuple[tuple[IntPoint, IntPoint], ...]
    bent: int
    rounds: int


def draw(loops: Sequence[ExactRing], budget: Budget) -> Drawing:
    """Realize exact selected loops on integers; see the module docstring."""
    loops = tuple(loops)
    hot = _Hot(project(p) for ring in loops for p in ring)
    bent: set[EdgeId] = set()
    paths: dict[EdgeId, list[IntPoint]] = {}
    total = sum(len(r) for r in loops)
    index: SpatialIndex[EdgeId] | None = None
    rounds = 0
    while True:
        rounds += 1
        edges = _draw(loops, bent, paths, hot, budget)
        try:
            current, owners = _planar(edges, budget)
            boundary = _faces(current, owners, budget)
        except _Conflict as conflict:
            # bend the sources of the conflict and the exact edges around them; every edge at worst
            require(len(bent) < total, "conflict remains with every edge bent")
            if index is None:
                index = _edge_index(loops)
            fresh = (
                conflict.sources | {e for s in conflict.sources for e in index.query(_box(loops, s))}
            ) - bent
            if not fresh:
                fresh = {(i, j) for i, ring in enumerate(loops) for j in range(len(ring))} - bent
            _close(loops, bent, fresh, paths, hot, index, budget)
            continue
        return Drawing(tuple(sorted(boundary)), len(bent), rounds)


def assemble(
    boundary: Sequence[tuple[IntPoint, IntPoint]], protected: frozenset[IntPoint], budget: Budget
) -> Snapped:
    """The rings and polygons of directed integer boundary edges, and the protected corners they erase."""
    raw = _rings(boundary, budget)
    rings: list[IntRing] = []
    erased: set[IntPoint] = set()
    for ring in raw:
        cleaned = _clean(ring)
        kept = set(cleaned)
        erased.update(p for p in ring if p in protected and p not in kept)
        if len(cleaned) >= 3 and _area2(cleaned) != 0:
            rings.append(cleaned)
    polygons = _polygons(rings, budget)
    actual = sorted(_key(tuple((p.x, p.y) for p in r)) for poly in polygons for r in poly.rings())
    expected = sorted(_key(r) for r in rings)
    require(actual == expected, "normalization changes realized rings")
    return Snapped(tuple(rings), polygons, 0, 0, frozenset(erased))


def snap_round(loops: Sequence[ExactRing], protected: frozenset[IntPoint], budget: Budget) -> Snapped:
    drawing = draw(loops, budget)
    snapped = assemble(drawing.boundary, protected, budget)
    return Snapped(snapped.rings, snapped.polygons, drawing.bent, drawing.rounds, snapped.erased)


def merge(
    drawings: Sequence[Sequence[tuple[IntPoint, IntPoint]]], seams: Sequence[tuple[int, int]]
) -> list[tuple[IntPoint, IntPoint]]:
    """The boundary of the union of regions with disjoint interiors that meet only on the seam lines
    ``(axis, value)`` (axis 0: ``x = value``): edges on a seam line are split at every vertex on that line and
    opposite currents cancel."""
    lines = (frozenset(v for a, v in seams if a == 0), frozenset(v for a, v in seams if a == 1))
    on_line: tuple[dict[int, set[int]], dict[int, set[int]]] = (defaultdict(set), defaultdict(set))
    for edges in drawings:
        for a, b in edges:
            for p in (a, b):
                for axis in (0, 1):
                    if p[axis] in lines[axis]:
                        on_line[axis][p[axis]].add(p[1 - axis])
    current: dict[tuple[IntPoint, IntPoint], int] = defaultdict(int)
    for edges in drawings:
        for a, b in edges:
            pieces = [(a, b)]
            for axis in (0, 1):
                if a[axis] == b[axis] and a[axis] in lines[axis]:
                    other = 1 - axis
                    lo, hi = min(a[other], b[other]), max(a[other], b[other])
                    ws = sorted(w for w in on_line[axis][a[axis]] if lo <= w <= hi)
                    ordered = ws if a[other] < b[other] else ws[::-1]
                    points = [(a[axis], w) if axis == 0 else (w, a[axis]) for w in ordered]
                    pieces = list(zip(points, points[1:], strict=False))
            for p, q in pieces:
                if p < q:
                    current[p, q] += 1
                else:
                    current[q, p] -= 1
    require(all(abs(v) <= 1 for v in current.values()), "merged cells overlap")
    return sorted((a, b) if v > 0 else (b, a) for (a, b), v in current.items() if v)


def _key(ring: IntRing) -> IntRing:
    """Rotation- and direction-free key of a ring."""
    forms: list[IntRing] = []
    for r in (ring, tuple(reversed(ring))):
        k = r.index(min(r))
        forms.append(r[k:] + r[:k])
    return min(forms)


def turns(ring: ExactRing) -> Iterator[tuple[ExactPoint, F]]:
    n = len(ring)
    for j in range(n):
        a, p, b = ring[j - 1], ring[j], ring[(j + 1) % n]
        yield p, (p[0] - a[0]) * (b[1] - p[1]) - (p[1] - a[1]) * (b[0] - p[0])


def protected_corners(loops: Sequence[ExactRing], segments: Sequence[Segment]) -> frozenset[IntPoint]:
    """The integer source vertices at which an exact loop turns."""
    source = {p for s in segments for p in (s.a, s.b)}
    found: set[IntPoint] = set()
    for ring in loops:
        for p, turn in turns(ring):
            if turn != 0 and p[0].denominator == 1 and p[1].denominator == 1:
                q = (int(p[0]), int(p[1]))
                if q in source:
                    found.add(q)
    return frozenset(found)
