# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Is a placement legal? Courtyard overlaps, parts outside the outline and the edge clearance (capability
placement, "Placement legality"; ``docs/placement.md``).

``check`` works on plain data: the placed extents of ``backends.base`` and the outline rings. Every
predicate is exact integer geometry. Whether courtyards that only touch overlap is KiCad's decision,
recorded by the probe ``place-touch`` (``H-K-PLACE-TOUCH``): they do not.
"""

from __future__ import annotations

from collections.abc import Iterator, Mapping, Sequence

from fenolite.backends.base import PlacedExtent
from fenolite.core.coords import Point
from fenolite.core.errors import Issue
from fenolite.core.units import Nm
from fenolite.geometry import (
    BBox,
    Location,
    Polygon,
    SegmentRelation,
    classify_segments,
    orient2d,
    point_in_ring,
    polygons_intersect,
    segments_closer_than,
)
from fenolite.model.design import Design
from fenolite.placement.codes import issue

TOUCHING_OVERLAPS = False
"""Whether courtyards that share only boundary points overlap. The probe files record ``absent`` for
``place-touch`` on 9.0.9 and 10.0.6: KiCad reports no ``courtyards_overlap`` for them."""
APPROXIMATE = " (approximate extent)"
Ring = Sequence[Point]


def _edges(ring: Ring) -> Iterator[tuple[Point, Point]]:
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
    for a, b in _edges(ring):
        cuts = [v for v in other if _strictly_between(v, a, b)]
        cuts.sort(key=lambda v: (v.x - a.x) * (b.x - a.x) + (v.y - a.y) * (b.y - a.y))
        stops = [a, *cuts, b]
        for p, q in zip(stops, stops[1:], strict=False):
            if p != q:
                yield Point(p.x + q.x, p.y + q.y)


def _locations(ring: Ring, other: Ring) -> set[Location]:
    doubled = _doubled(other)
    return {point_in_ring(m, doubled) for m in _midpoints(ring, other)}


def _cross(a: Ring, b: Ring) -> bool:
    """Whether two edges cross at a point interior to both."""
    return any(
        classify_segments(p, q, r, s) is SegmentRelation.PROPER for p, q in _edges(a) for r, s in _edges(b)
    )


def _boxes_overlap(a: BBox, b: BBox) -> bool:
    """Whether the open boxes intersect."""
    return a.x0 < b.x1 and b.x0 < a.x1 and a.y0 < b.y1 and b.y0 < a.y1


def interiors_intersect(a: Ring, b: Ring) -> bool:
    """Whether the interiors of two simple rings share a point; rings that only touch do not."""
    if not _boxes_overlap(BBox.of_points(a), BBox.of_points(b)):
        return False
    if _cross(a, b):
        return True
    a_in_b, b_in_a = _locations(a, b), _locations(b, a)
    if Location.INSIDE in a_in_b or Location.INSIDE in b_in_a:
        return True
    return a_in_b == {Location.BOUNDARY} and b_in_a == {Location.BOUNDARY}  # the same region


def rings_overlap(a: Ring, b: Ring, *, touching_overlaps: bool = TOUCHING_OVERLAPS) -> bool:
    """Whether two courtyard rings overlap: their interiors intersect, or, with ``touching_overlaps``,
    their closed regions share a point."""
    if touching_overlaps:
        return polygons_intersect(Polygon(tuple(a)), Polygon(tuple(b)))
    return interiors_intersect(a, b)


def ring_inside(ring: Ring, region: Ring) -> bool:
    """Whether ``ring`` lies in the closed region of ``region`` (touching its boundary is inside)."""
    if not BBox.of_points(region).contains_bbox(BBox.of_points(ring)):
        return False
    return not _cross(ring, region) and Location.OUTSIDE not in _locations(ring, region)


def ring_enters(ring: Ring, cutout: Ring) -> bool:
    """Whether a point of ``ring`` lies inside ``cutout``, or the two are the same region."""
    if not _boxes_overlap(BBox.of_points(ring), BBox.of_points(cutout)):
        return False
    if _cross(ring, cutout):
        return True
    found = _locations(ring, cutout)
    return Location.INSIDE in found or found == {Location.BOUNDARY}


def _closer(ring: Ring, other: Ring, limit: Nm) -> bool:
    return any(segments_closer_than(p, q, r, s, limit) for p, q in _edges(ring) for r, s in _edges(other))


def edge_clearance(design: Design) -> Nm:
    """The smallest ``min`` of the design's board-wide ``edge_clearance`` rules (first selector ``all``),
    or 0 without one."""
    rules = design.rules.rules if design.rules is not None else ()
    found = [
        rule.min
        for rule in rules
        if rule.kind == "edge_clearance" and rule.selector_a.op == "all" and rule.min is not None
    ]
    return max(0, min(found)) if found else 0


def check(
    extents: Sequence[PlacedExtent],
    outline_rings: Sequence[Ring],
    *,
    edge_clearance: Nm = 0,
    names: Mapping[str, str],
    touching_overlaps: bool = TOUCHING_OVERLAPS,
) -> tuple[Issue, ...]:
    """The placement issues of a layout, sorted by code and then ``where``.

    ``extents`` are the footprints to judge (the caller leaves staged parts out), ``outline_rings`` the
    board ring followed by its cut-outs (empty when the board has no closed outline), and ``names`` maps a
    footprint id to its reference. Front rings are judged against front rings and back against back.
    """
    issues: list[Issue] = []

    def ref(extent: PlacedExtent) -> str:
        return names.get(extent.footprint_id, extent.footprint_id)

    judged: list[PlacedExtent] = []
    for extent in extents:
        if extent.source == "none" or not (extent.front or extent.back):
            issues.append(
                issue(
                    "place.no-extent",
                    f"{ref(extent)} has neither a courtyard nor pad copper and is not judged",
                    ref(extent),
                )
            )
        else:
            judged.append(extent)
    boxes = {
        (index, face): [BBox.of_points(ring) for ring in rings]
        for index, extent in enumerate(judged)
        for face, rings in (("front", extent.front), ("back", extent.back))
    }
    for i, first in enumerate(judged):
        for j in range(i + 1, len(judged)):
            second = judged[j]
            if first.footprint_id == second.footprint_id:
                continue
            hit = any(
                (box_a.intersects(box_b) and rings_overlap(a, b, touching_overlaps=touching_overlaps))
                for face in ("front", "back")
                for a, box_a in zip(getattr(first, face), boxes[i, face], strict=True)
                for b, box_b in zip(getattr(second, face), boxes[j, face], strict=True)
            )
            if hit:
                pair = sorted((ref(first), ref(second)))
                note = APPROXIMATE if not (first.exact and second.exact) else ""
                issues.append(
                    issue(
                        "place.courtyard-overlap",
                        f"the courtyards of {pair[0]} and {pair[1]} overlap{note}",
                        ",".join(pair),
                        "move one of the parts",
                    )
                )
    if not outline_rings:
        issues.append(
            issue(
                "place.no-outline",
                "the board has no closed outline; only courtyard overlaps are judged",
                "board",
            )
        )
    else:
        board, cutouts = outline_rings[0], outline_rings[1:]
        for extent in judged:
            rings = (*extent.front, *extent.back)
            note = "" if extent.exact else APPROXIMATE
            outside = any(not ring_inside(ring, board) for ring in rings)
            in_cutout = any(ring_enters(ring, cutout) for ring in rings for cutout in cutouts)
            if outside or in_cutout:
                what = "leaves the board outline" if outside else "enters a cut-out of the board"
                issues.append(
                    issue(
                        "place.outside-outline", f"the courtyard of {ref(extent)} {what}{note}", ref(extent)
                    )
                )
            elif edge_clearance > 0 and any(
                _closer(ring, other, edge_clearance) for ring in rings for other in outline_rings
            ):
                issues.append(
                    issue(
                        "place.edge-clearance",
                        f"the courtyard of {ref(extent)} is closer to the board edge than "
                        f"{edge_clearance / 1e6:g} mm{note}",
                        ref(extent),
                    )
                )
    return tuple(sorted(issues, key=lambda found: (found.code, found.where)))


__all__ = [
    "TOUCHING_OVERLAPS",
    "check",
    "edge_clearance",
    "interiors_intersect",
    "ring_enters",
    "ring_inside",
    "rings_overlap",
]
