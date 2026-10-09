# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Exact relations of two simple rings: do their interiors meet, where does one lie against the other.

Moved here from ``fenolite.placement.legality`` by change c0140 without a change of behaviour, so that
``fenolite.checks`` (the height limits of the stage ``placement.rules``) judges "a part under an area" with
the predicate the legality check uses for keep-outs; ``placement.legality`` imports it from here.
"""

from __future__ import annotations

from collections.abc import Iterator, Sequence

from fenolite.geometry.predicates import Location, SegmentRelation, classify_segments, orient2d, point_in_ring
from fenolite.geometry.shapes import BBox
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


__all__ = ["interiors_intersect", "open_boxes_overlap", "ring_edges", "ring_locations", "rings_cross"]
