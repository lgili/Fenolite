# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The edge rings of a conversion verified (capability design-conversion, "Edge rings verified after a
conversion"; change c0170).

The rings of the source's board edge and those of the written project read back (``BoardFrame.board_edges``
of each backend) are compared as sets after one translation, the frame of the written board being its
own: each ring is polygonised within ``CHORD`` and a ring matches another when every vertex of each lies
within ``RING_TOL`` plus ``CHORD`` of the other's edges. A written ring that unites several source rings
(the merge of overlapping cut-outs) is matched against their union. What does not match is a
``RingDifference``; the report explains one when it counts the ring lost or changed (the ids ``cutout/<k>``
of ring ``edge ring <k>``, a merged group joined by ``+``, and any ``outline`` change or loss for the
board ring). A ring that the report does not explain is a difference of the verification, which
``fenolite.api.convert`` gives as ``convert.unexplained``.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from fenolite.backends.altium.cutouts import CUTOUT_TOL
from fenolite.backends.base import EdgeRing
from fenolite.convert.report import ConversionReport
from fenolite.core.coords import Point
from fenolite.geometry.errors import BackendUnavailable, GeometryError
from fenolite.geometry.predicates import dist2_point_segment
from fenolite.geometry.rings import MERGE_TOL, CurvedRing, merge_rings

RING_TOL = 1_000
"""How far, in nanometres, a written ring may lie from the source's: 1 µm."""
CHORD = CUTOUT_TOL
"""The polygonisation of an arc, here and in a written Altium region (``cutouts.CUTOUT_TOL``, 1 µm)."""
BOARD = "board"
EDGE_RING = "edge ring "
RING_KIND = "edge-ring"
"""The kind of a ring difference: the conversion's own comparison, outside the levels of
``checks.equivalence``."""


@dataclass(frozen=True, slots=True)
class RingDifference:
    """A ring of one side that matches none of the other: ``side`` ``source`` (a ring the written project
    does not hold) or ``written`` (a ring the source does not hold), the ring's name on that side, its
    vertices as text, and the report's kind that explains it (``None`` when none does)."""

    side: str
    name: str
    text: str
    explained_by: str | None = None


ORIGIN = Point(0, 0)


def _polygon(ring: EdgeRing, shift: Point = ORIGIN) -> tuple[Point, ...]:
    points = CurvedRing(ring.points, ring.mids).polygonize(CHORD)
    return tuple(Point(p.x + shift.x, p.y + shift.y) for p in points)


def _near(point: Point, ring: Sequence[Point], tol: int) -> bool:
    """Whether ``point`` lies within ``tol`` of an edge of the closed ring ``ring``."""
    limit = tol * tol
    n = len(ring)
    for k in range(n):
        a, b = ring[k], ring[(k + 1) % n]
        if not (min(a.x, b.x) - tol <= point.x <= max(a.x, b.x) + tol):
            continue
        if not (min(a.y, b.y) - tol <= point.y <= max(a.y, b.y) + tol):
            continue
        if dist2_point_segment(point, a, b) <= limit:
            return True
    return False


def same_ring(a: Sequence[Point], b: Sequence[Point], tol: int = RING_TOL + CHORD) -> bool:
    """Whether every vertex of each polygon lies within ``tol`` of the other's edges."""
    return all(_near(p, b, tol) for p in a) and all(_near(p, a, tol) for p in b)


def translation(source: EdgeRing, written: EdgeRing) -> Point:
    """The shift that takes the source's board ring onto the written one: of the shifts that take the
    least vertex of the source's ring onto a vertex of the written ring, the one under which most source
    vertices meet a written vertex within ``RING_TOL`` (the first on a tie); ``(0, 0)`` when none does."""
    anchor = min(source.points)
    best, score = Point(0, 0), 0
    for target in written.points:
        shift = Point(target.x - anchor.x, target.y - anchor.y)
        found = sum(
            1
            for p in source.points
            if any(
                abs(p.x + shift.x - q.x) <= RING_TOL and abs(p.y + shift.y - q.y) <= RING_TOL
                for q in written.points
            )
        )
        if found > score:
            best, score = shift, found
    return best


def _index(name: str) -> int | None:
    return int(name.removeprefix(EDGE_RING)) if name.startswith(EDGE_RING) else None


def _groups(report: ConversionReport) -> dict[int, tuple[str, tuple[int, ...]]]:
    """Ring index → (the outcome of its ``cutout`` id, the indices of its group), from the report."""
    row = report.row("cutout")
    found: dict[int, tuple[str, tuple[int, ...]]] = {}
    for reason in row.reasons if row is not None else ():
        for ident in reason.ids:
            members = tuple(
                int(part.removeprefix("cutout/")) for part in ident.split("+") if part.startswith("cutout/")
            )
            for k in members:
                found[k] = (reason.outcome, members)
    return found


def _text(ring: EdgeRing) -> str:
    return " ".join(f"({p.x},{p.y})" for p in ring.points)


def compare_rings(
    source: Sequence[EdgeRing] | None, written: Sequence[EdgeRing] | None, report: ConversionReport
) -> tuple[RingDifference, ...]:
    """The rings of ``source`` and ``written`` that match none of the other side, each with the kind of
    ``report`` that explains it, or ``None``. A source without a closed board ring is not compared."""
    if not source:
        return ()
    written = tuple(written or ())
    shift = translation(source[0], written[0]) if written else Point(0, 0)
    a = [_polygon(ring, shift) for ring in source]
    b = [_polygon(ring) for ring in written]
    free = list(range(len(b)))
    unmatched: list[int] = []
    for i, ring in enumerate(a):
        hit = next((j for j in free if same_ring(ring, b[j])), None)
        if hit is None:
            unmatched.append(i)
        else:
            free.remove(hit)
    groups = _groups(report)
    outline = report.row("outline")
    merges: dict[tuple[int, ...], str | None] = {}
    differences: list[RingDifference] = []
    for i in unmatched:
        ring = source[i]
        k = _index(ring.name)
        why: str | None = None
        if i == 0 and outline is not None and (outline.changed or outline.lost):
            why = "outline"
        elif k is not None and k in groups:
            outcome, members = groups[k]
            if outcome == "lost":
                why = "cutout"
            elif len(members) > 1:
                if members not in merges:
                    merges[members] = _merged(source, members, shift, b, free)
                why = merges[members]
        differences.append(RingDifference("source", ring.name, _text(ring), why))
    for j in free:
        ring = written[j]
        why = "outline" if j == 0 and outline is not None and (outline.changed or outline.lost) else None
        differences.append(RingDifference("written", ring.name, _text(ring), why))
    return tuple(differences)


def _merged(
    source: Sequence[EdgeRing], members: tuple[int, ...], shift: Point, written: list[tuple[Point, ...]],
    free: list[int],
) -> str | None:  # fmt: skip
    """``cutout`` when the union of the source rings ``members`` matches a written ring that is still
    free (which is then taken), else ``None``. Without a geometry backend the union cannot be formed, and
    the report's count of the merge stands for it (``cutout``)."""
    rings = [source[k] for k in members if 0 < k < len(source)]
    try:
        (union,) = merge_rings([CurvedRing(r.points, r.mids) for r in rings], tol=MERGE_TOL)
    except BackendUnavailable:
        return "cutout"
    except (GeometryError, ValueError):
        return None
    polygon = tuple(Point(p.x + shift.x, p.y + shift.y) for p in union.polygonize(CHORD))
    hit = next((j for j in free if same_ring(polygon, written[j])), None)
    if hit is None:
        return None
    free.remove(hit)
    return "cutout"


__all__ = [
    "BOARD",
    "CHORD",
    "RING_KIND",
    "RING_TOL",
    "RingDifference",
    "compare_rings",
    "same_ring",
    "translation",
]
