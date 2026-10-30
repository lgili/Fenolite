# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Exact relations of two simple rings: do their interiors meet, where does one lie against the other.

Moved here from ``fenolite.placement.legality`` by change c0140 without a change of behaviour, so that
``fenolite.checks`` (the height limits of the stage ``placement.rules``) judges "a part under an area" with
the predicate the legality check uses for keep-outs; ``placement.legality`` imports it from here.

Change c0167 adds ``CurvedRing`` and ``merge_rings``: the union of rings of lines and arcs (overlapping
cut-outs and slots of a board outline) with every source arc put back on its circle (capability
geometry-boolean-backends, "Union of curved rings").
"""

from __future__ import annotations

from collections.abc import Iterator, Sequence
from dataclasses import dataclass
from fractions import Fraction

from fenolite.geometry.boolean import select_backend
from fenolite.geometry.errors import GeometryError
from fenolite.geometry.polygon import Polygon, area2
from fenolite.geometry.predicates import Location, SegmentRelation, classify_segments, orient2d, point_in_ring
from fenolite.geometry.shapes import Arc, BBox
from fenolite.geometry.vector import Point

Ring = Sequence[Point]


def ring_edges(ring: Ring) -> Iterator[tuple[Point, Point]]:
    """The edges of a closed ring, the last back to the first vertex."""
    for i, a in enumerate(ring):
        yield a, ring[(i + 1) % len(ring)]


def _doubled(ring: Ring) -> tuple[Point, ...]:
    return tuple(Point(2 * p.x, 2 * p.y) for p in ring)


def _strictly_between(p: Point, a: Point, b: Point) -> bool:
    """Whether ``p`` lies on the open segment ``a–b``."""
    if p in (a, b) or orient2d(a, b, p) != 0:
        return False
    return min(a.x, b.x) <= p.x <= max(a.x, b.x) and min(a.y, b.y) <= p.y <= max(a.y, b.y)


def _midpoints(ring: Ring, other: Ring) -> Iterator[Point]:
    """The midpoints, in doubled coordinates, of the pieces that the vertices of ``other`` cut the edges of
    ``ring`` into. Without a proper crossing, each piece lies wholly inside, outside or on ``other``."""
    for a, b in ring_edges(ring):
        cuts = [v for v in other if _strictly_between(v, a, b)]
        cuts.sort(key=lambda v: (v.x - a.x) * (b.x - a.x) + (v.y - a.y) * (b.y - a.y))
        stops = [a, *cuts, b]
        for p, q in zip(stops, stops[1:], strict=False):
            if p != q:
                yield Point(p.x + q.x, p.y + q.y)


def ring_locations(ring: Ring, other: Ring) -> set[Location]:
    """Where the pieces of the edges of ``ring`` lie against ``other`` (meaningful without a crossing)."""
    doubled = _doubled(other)
    return {point_in_ring(m, doubled) for m in _midpoints(ring, other)}


def rings_cross(a: Ring, b: Ring) -> bool:
    """Whether two edges cross at a point interior to both."""
    return any(
        classify_segments(p, q, r, s) is SegmentRelation.PROPER
        for p, q in ring_edges(a)
        for r, s in ring_edges(b)
    )


def open_boxes_overlap(a: BBox, b: BBox) -> bool:
    """Whether the open boxes intersect."""
    return a.x0 < b.x1 and b.x0 < a.x1 and a.y0 < b.y1 and b.y0 < a.y1


def interiors_intersect(a: Ring, b: Ring) -> bool:
    """Whether the interiors of two simple rings share a point; rings that only touch do not."""
    if not open_boxes_overlap(BBox.of_points(a), BBox.of_points(b)):
        return False
    if rings_cross(a, b):
        return True
    a_in_b, b_in_a = ring_locations(a, b), ring_locations(b, a)
    if Location.INSIDE in a_in_b or Location.INSIDE in b_in_a:
        return True
    return a_in_b == {Location.BOUNDARY} and b_in_a == {Location.BOUNDARY}  # the same region


# --- the union of curved rings (change c0167) ------------------------------------------------------------

MERGE_TOL = 1_000
"""The polygonisation tolerance of ``merge_rings`` in nanometres: the merged ring lies within it of the
exact union."""
Circle = tuple[Fraction, Fraction, Fraction]
"""A circle as ``(centre x, centre y, squared radius)``, exact."""


@dataclass(frozen=True, slots=True)
class CurvedRing:
    """A closed ring of lines and arcs: its vertices and, per edge, the mid of the arc it is or ``None``
    for a line (edge i joins vertex i to vertex i + 1 mod n). ``mids`` may be empty for a polygon."""

    points: tuple[Point, ...]
    mids: tuple[Point | None, ...] = ()

    def __post_init__(self) -> None:
        points = tuple(self.points)
        mids = tuple(self.mids) or (None,) * len(points)
        if len(mids) != len(points):
            raise ValueError(f"a ring of {len(points)} vertices needs as many mids, not {len(mids)}")
        object.__setattr__(self, "points", points)
        object.__setattr__(self, "mids", mids)

    def arcs(self) -> tuple[tuple[int, Point], ...]:
        """``(edge, mid)`` of each arc, in edge order."""
        return tuple((k, mid) for k, mid in enumerate(self.mids) if mid is not None)

    def edge_arc(self, k: int) -> Arc | None:
        """Edge ``k`` as an ``Arc`` when it is a true arc, else ``None``."""
        mid = self.mids[k]
        start, end = self.points[k], self.points[(k + 1) % len(self.points)]
        if mid is None or start == end:
            return None
        try:
            arc = Arc(start, mid, end)
        except (GeometryError, ValueError):
            return None
        return None if arc.is_straight else arc

    def tagged(self, tol: int = MERGE_TOL) -> tuple[tuple[Point, Circle | None], ...]:
        """The polygonisation at ``tol``, each point with the circle of the arc it is an interior point
        of, or ``None`` for a vertex of the ring."""
        out: list[tuple[Point, Circle | None]] = []
        for k, start in enumerate(self.points):
            out.append((start, None))
            arc = self.edge_arc(k)
            if arc is None or arc.centre is None or arc.radius2 is None:
                continue
            circle = (arc.centre[0], arc.centre[1], arc.radius2)
            out += [(point, circle) for point in arc.polygonize(tol)[1:-1]]
        return tuple(out)

    def polygonize(self, tol: int = MERGE_TOL) -> tuple[Point, ...]:
        """The vertices with each arc replaced by its polygonisation at ``tol``."""
        return tuple(point for point, _ in self.tagged(tol))

    def reversed(self) -> CurvedRing:
        """The same ring run the other way."""
        n = len(self.points)
        points = tuple(self.points[(n - i) % n] for i in range(n))
        # edge i of the reversed ring joins points[i] to points[i + 1], which is old edge (n − i − 1)
        return CurvedRing(points, tuple(self.mids[(n - i - 1) % n] for i in range(n)))

    def normalized(self) -> CurvedRing:
        """The ring with a positive orientation (of its polygonisation), starting at its least vertex."""
        ring = self.reversed() if area2(self.polygonize()) < 0 else self
        start = ring.points.index(min(ring.points))
        return CurvedRing(ring.points[start:] + ring.points[:start], ring.mids[start:] + ring.mids[:start])


def zone_ring(
    points: Sequence[Point], arcs: Sequence[tuple[int, Point]], tol: int = MERGE_TOL
) -> tuple[Point, ...]:
    """The polygon of a zone outline whose edges ``arcs`` (``(edge, mid)``) are arcs, each arc polygonised at
    ``tol`` (change c0277); the vertices themselves for an outline without arcs."""
    if not arcs:
        return tuple(points)
    mids: list[Point | None] = [None] * len(points)
    for edge, mid in arcs:
        if 0 <= edge < len(points):
            mids[edge] = mid
    return CurvedRing(tuple(points), tuple(mids)).polygonize(tol)


@dataclass(frozen=True, slots=True)
class MergedGroup:
    """One result of ``merge_groups``: the indices of the input rings it holds, in input order, and its
    ring (the input itself for a group of one)."""

    members: tuple[int, ...]
    ring: CurvedRing


def _inside(a: Ring, b: Ring) -> bool:
    """Whether ``a`` lies wholly inside or on ``b`` (meaningful when no edges cross)."""
    return not rings_cross(a, b) and Location.OUTSIDE not in ring_locations(a, b)


def overlap_groups(rings: Sequence[CurvedRing], *, tol: int = MERGE_TOL) -> tuple[tuple[int, ...], ...]:
    """The indices of ``rings`` grouped by overlap, each group in input order and the groups in the order
    of their first member. Two rings overlap when the interiors of their polygonisations at ``tol`` meet
    and neither lies inside the other: rings that only touch, and a ring inside another, stay apart."""
    polys = [ring.polygonize(tol) for ring in rings]
    boxes = [BBox.of_points(poly) if len(poly) >= 3 else None for poly in polys]
    parent = list(range(len(rings)))

    def root(i: int) -> int:
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    for i in range(len(rings)):
        for j in range(i + 1, len(rings)):
            bi, bj = boxes[i], boxes[j]
            if bi is None or bj is None or not open_boxes_overlap(bi, bj):
                continue
            if not interiors_intersect(polys[i], polys[j]):
                continue
            if _inside(polys[i], polys[j]) or _inside(polys[j], polys[i]):
                continue
            a, b = root(i), root(j)
            if a != b:
                parent[max(a, b)] = min(a, b)
    groups: dict[int, list[int]] = {}
    for i in range(len(rings)):
        groups.setdefault(root(i), []).append(i)
    return tuple(tuple(members) for _, members in sorted(groups.items()))


def _names(members: Sequence[int], names: Sequence[str] | None) -> str:
    return ", ".join(names[i] if names is not None else f"ring {i}" for i in members)


def _kept(keys: Sequence[Circle | None]) -> list[bool]:
    """Which points of a ring stay vertices: those of no arc, and the first point of a run of one circle
    that follows a run of another circle directly (it ends the first arc and starts the second)."""
    n = len(keys)
    return [keys[i] is None or (keys[i - 1] is not None and keys[i - 1] != keys[i]) for i in range(n)]


def _restore_arcs(outer: Sequence[Point], keys: Sequence[Circle | None]) -> CurvedRing:
    """``outer`` with every maximal run of interior points of arcs of one circle replaced by one arc from
    the vertex before the run to the vertex after it, through the run's middle point."""
    n = len(outer)
    kept = _kept(keys)
    starts = [i for i in range(n) if kept[i]]
    if not starts:
        return CurvedRing(tuple(outer))
    if len(starts) == 1:  # one vertex and a run all the way round: keep the run's middle point too
        run = [(starts[0] + k) % n for k in range(1, n)]
        if len(run) < 3:
            return CurvedRing(tuple(outer))
        kept[run[len(run) // 2]] = True
        starts = [i for i in range(n) if kept[i]]
    points: list[Point] = []
    mids: list[Point | None] = []
    for s, start in enumerate(starts):
        end = starts[(s + 1) % len(starts)]
        run = [(start + k) % n for k in range(1, (end - start) % n or n)]
        mid = outer[run[len(run) // 2]] if run else None
        if mid is not None:
            try:
                straight = Arc(outer[start], mid, outer[end]).is_straight
            except (GeometryError, ValueError):
                straight = True
            if straight:  # no true arc: keep the run's points as straight vertices
                points += [outer[start], *(outer[i] for i in run)]
                mids += [None] * (1 + len(run))
                continue
        points.append(outer[start])
        mids.append(mid)
    return CurvedRing(tuple(points), tuple(mids)).normalized()


def _merge(group: Sequence[CurvedRing], label: str, tol: int) -> CurvedRing:
    tags: dict[Point, Circle | None] = {}
    vertices: set[Point] = set()
    polygons: list[Polygon] = []
    for ring in group:
        vertices.update(ring.points)
        tagged = ring.tagged(tol)
        for point, circle in tagged:
            if circle is None:
                continue
            if point in tags and tags[point] != circle:
                tags[point] = None  # an interior point of arcs of two circles belongs to neither
            else:
                tags.setdefault(point, circle)
        polygons.append(Polygon(tuple(point for point, _ in tagged)))
    for point in vertices:
        tags[point] = None  # a vertex of an input ring ends a run, never extends it
    union = select_backend(operation="union").union(polygons)
    if len(union) != 1 or union[0].holes:
        raise GeometryError(
            f"the union of {label} is not one ring without holes",
            points=tuple(min(ring.points) for ring in group),
        )
    outer = union[0].outer
    return _restore_arcs(outer, [tags.get(point) for point in outer])


def merge_groups(
    rings: Sequence[CurvedRing], *, tol: int = MERGE_TOL, names: Sequence[str] | None = None
) -> tuple[MergedGroup, ...]:
    """``overlap_groups`` of ``rings`` with each group of two or more united as ``merge_rings`` says. A
    group of one keeps its ring unchanged. ``BackendUnavailable`` when no installed backend unites,
    ``GeometryError`` naming the group's rings (by ``names``, else ``ring <index>``) when a union is not one
    ring without holes."""
    found: list[MergedGroup] = []
    for members in overlap_groups(rings, tol=tol):
        if len(members) == 1:
            found.append(MergedGroup(members, rings[members[0]]))
            continue
        merged = _merge([rings[i] for i in members], _names(members, names), tol)
        found.append(MergedGroup(members, merged))
    return tuple(found)


def merge_rings(
    rings: Sequence[CurvedRing], *, tol: int = MERGE_TOL, names: Sequence[str] | None = None
) -> tuple[CurvedRing, ...]:
    """The union of ``rings``, one ring per group of overlapping rings, in the order of each group's first
    ring. A ring that overlaps no other is returned unchanged. A group is polygonised at ``tol``, united by
    ``select_backend(operation="union")``, and each maximal run of result vertices that are interior points
    of arcs of one circle (the two round ends of an L share theirs) becomes one arc of that circle from the
    vertex before the run to the vertex after it, through the run's middle point; a vertex of an input ring
    always ends a run. A merged ring starts at its least vertex with a positive orientation. The result is
    deterministic and lies within ``tol`` of the exact union. Errors as ``merge_groups``."""
    return tuple(group.ring for group in merge_groups(rings, tol=tol, names=names))


__all__ = [
    "CurvedRing",
    "MERGE_TOL",
    "MergedGroup",
    "interiors_intersect",
    "merge_groups",
    "merge_rings",
    "open_boxes_overlap",
    "overlap_groups",
    "ring_edges",
    "ring_locations",
    "rings_cross",
    "zone_ring",
]
