# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Grooves narrower than the user's groove width are bridged on the creepage path (capability
board-analyses, "Creepage grooves"; ``docs/analyses.md``, "Grooves"; ``H-G-AN-GROOVE``).

A cut-out is bridged whole, that is left out of the boundary, when it has a double normal shorter than
the width: a chord inside it that meets its boundary at right angles at both ends. An end at a vertex
counts as at right angles when the chord's direction lies between the inward normals of the vertex's two
edges. For a slot that chord is its width. A pocket of the outer ring is filled when its mouth is
shorter than the width. Bridging only removes obstacles, so it can only shorten a creepage.

Pockets come from the convex hull of the outer ring, the hull keeping every ring vertex on its edges: a
pocket lies between a hull segment that is not a ring edge, its mouth, and the chain of the ring between
the segment's ends. The chain of a pocket has pockets of its own, taken the same way; those at the next
level are board material that reaches into the pocket, and those below them are air again. Pockets are
decided from the deepest.

Lengths are compared as exact squares. Fenolite ships no groove width: the user gives it.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, replace
from fractions import Fraction

from fenolite.analysis.boundary import BoardBoundary
from fenolite.core.coords import Point
from fenolite.core.evidence import Evidence, Level
from fenolite.core.units import Nm
from fenolite.geometry import Location, area2, convex_hull, dist2_point_segment, point_in_ring

EVIDENCE = Evidence(Level.INFERRED, hypotheses=("H-G-AN-GROOVE",))
"""``INFERRED``: KiCad applies no groove width to a cut-out (``H-K-AN-GROOVE``), so nothing brackets it."""
Ring = tuple[Point, ...]
_F = tuple[Fraction, Fraction]


@dataclass(frozen=True, slots=True)
class GrooveResult:
    """The boundary on which narrow grooves are bridged, and the counts of cut-outs and pockets bridged
    and kept."""

    boundary: BoardBoundary
    bridged: int
    counted: int


@dataclass(frozen=True, slots=True)
class Pocket:
    """A pocket of a ring: the chain of ring points from one end of its mouth to the other, both ends
    included, and the mouth, the segment that joins the two ends."""

    chain: Ring
    mouth: tuple[Point, Point]


# --- double normals -------------------------------------------------------------------------------


def _cross(ax: int, ay: int, bx: int, by: int) -> int:
    return ax * by - ay * bx


def _in_cone(ring: Ring, index: int, dx: Fraction | int, dy: Fraction | int, sign: int) -> bool:
    """Whether the direction ``(dx, dy)`` lies between the inward normals of the two edges at the vertex
    ``index``; ``sign`` is 1 for a ring of positive orientation."""
    count = len(ring)
    before, here, after = ring[index - 1], ring[index], ring[(index + 1) % count]
    # inward normals: the edge direction turned to the side of the interior
    n1 = (-(here.y - before.y) * sign, (here.x - before.x) * sign)
    n2 = (-(after.y - here.y) * sign, (after.x - here.x) * sign)
    turn = _cross(n1[0], n1[1], n2[0], n2[1])
    first = n1[0] * dy - n1[1] * dx  # n1 × d
    second = dx * n2[1] - dy * n2[0]  # d × n2
    if turn == 0:  # the two edges are collinear: the one normal
        return first == 0 and dx * n1[0] + dy * n1[1] > 0
    if turn > 0:
        return first >= 0 and second >= 0
    return first <= 0 and second <= 0


def _inside(ring: Ring, p: _F, q: _F) -> bool:
    """Whether the open segment ``p–q`` lies inside the ring: its middle is strictly inside, and no ring
    edge crosses it."""
    scale = 1
    for value in (*p, *q):
        scale = scale * value.denominator // _gcd(scale, value.denominator)
    scale *= 2
    px, py, qx, qy = (int(value * scale) for value in (*p, *q))
    scaled = [Point(point.x * scale, point.y * scale) for point in ring]
    if point_in_ring(Point((px + qx) // 2, (py + qy) // 2), scaled) is not Location.INSIDE:
        return False
    for i, u in enumerate(scaled):
        v = scaled[(i + 1) % len(scaled)]
        d1 = _cross(qx - px, qy - py, u.x - px, u.y - py)
        d2 = _cross(qx - px, qy - py, v.x - px, v.y - py)
        d3 = _cross(v.x - u.x, v.y - u.y, px - u.x, py - u.y)
        d4 = _cross(v.x - u.x, v.y - u.y, qx - u.x, qy - u.y)
        if d1 * d2 < 0 and d3 * d4 < 0:
            return False
    return True


def _gcd(a: int, b: int) -> int:
    while b:
        a, b = b, a % b
    return a


def double_normal2(ring: Sequence[Point]) -> Fraction | None:
    """The squared length of the shortest double normal of the ring: a chord inside it whose two ends
    meet its boundary at right angles. ``None`` when the ring has none (it has no area)."""
    points = tuple(ring)
    count = len(points)
    if count < 3 or area2(points) == 0:
        return None
    sign = 1 if area2(points) > 0 else -1
    found: list[tuple[Fraction, _F, _F]] = []

    def q(point: Point) -> _F:
        return Fraction(point.x), Fraction(point.y)

    for i in range(count):
        a, b = points[i], points[(i + 1) % count]
        ex, ey = b.x - a.x, b.y - a.y
        length2 = ex * ex + ey * ey
        for j in range(count):
            v = points[j]
            # a vertex and the foot of its perpendicular on an edge
            if j not in (i, (i + 1) % count):
                along = (v.x - a.x) * ex + (v.y - a.y) * ey
                if 0 <= along <= length2:
                    t = Fraction(along, length2)
                    foot = (a.x + t * ex, a.y + t * ey)
                    dx, dy = foot[0] - v.x, foot[1] - v.y
                    if (dx or dy) and _in_cone(points, j, dx, dy, sign):
                        found.append((dx * dx + dy * dy, q(v), foot))
            # two parallel edges that face each other: a chord at right angles to both, in the middle
            # of the stretch where one lies over the other
            if j > i:
                c, d = points[j], points[(j + 1) % count]
                if _cross(ex, ey, d.x - c.x, d.y - c.y) == 0 and length2:
                    params = sorted(Fraction((p.x - a.x) * ex + (p.y - a.y) * ey, length2) for p in (c, d))
                    low, high = max(params[0], Fraction(0)), min(params[1], Fraction(1))
                    offset = _cross(ex, ey, c.x - a.x, c.y - a.y)
                    if low < high and offset:
                        t = (low + high) / 2
                        start = (a.x + t * ex, a.y + t * ey)
                        shift = Fraction(offset, length2)
                        found.append(
                            (shift * shift * length2, start, (start[0] - shift * ey, start[1] + shift * ex))
                        )
            # two vertices
            if j > i:
                dx, dy = v.x - a.x, v.y - a.y
                if _in_cone(points, i, dx, dy, sign) and _in_cone(points, j, -dx, -dy, sign):
                    found.append((Fraction(dx * dx + dy * dy), q(a), q(v)))
    for squared, p, r in sorted(found, key=lambda item: item[0]):
        if _inside(points, p, r):
            return squared
    return None


# --- pockets --------------------------------------------------------------------------------------


def _spans(ring: Sequence[Point]) -> list[tuple[int, int]]:
    """The pockets of a closed ring as ``(index of the first point, number of edges)``: the stretches of
    more than one edge between two consecutive points of the ring that lie on its convex hull, the points
    on the hull's edges included. A stretch may run past the end of the ring."""
    count = len(ring)
    hull = convex_hull(ring)
    edges = [(a, hull[(k + 1) % len(hull)]) for k, a in enumerate(hull)]
    stops: list[int] = []
    for index, point in enumerate(ring):
        for a, b in edges:
            if _cross(b.x - a.x, b.y - a.y, point.x - a.x, point.y - a.y) == 0 and (
                min(a.x, b.x) <= point.x <= max(a.x, b.x) and min(a.y, b.y) <= point.y <= max(a.y, b.y)
            ):
                stops.append(index)
                break
    found: list[tuple[int, int]] = []
    for k, first in enumerate(stops):
        span = (stops[(k + 1) % len(stops)] - first) % count
        if span > 1:
            found.append((first, span))
    return found


def pockets(outer: Sequence[Point]) -> tuple[Pocket, ...]:
    """The pockets of the outer ring: the chains of the ring between two consecutive vertices of its
    convex hull that are not one ring edge, each with its mouth."""
    ring = tuple(outer)
    if len(ring) < 4 or area2(ring) == 0:
        return ()
    found: list[Pocket] = []
    for first, span in _spans(ring):
        chain = tuple(ring[(first + step) % len(ring)] for step in range(span + 1))
        found.append(Pocket(chain, (chain[0], chain[-1])))
    return tuple(found)


def _fill(chain: Ring, width2: int, air: bool, counts: list[int]) -> Ring:
    """The chain of a pocket, from one end of its mouth to the other, with its narrow pockets of air
    filled, decided from the deepest. ``air`` says whether the pocket itself is air (a pocket of a pocket
    is board material that reaches into it); ``counts`` holds the pockets of air bridged and kept."""
    result = chain
    first, last = chain[0], chain[-1]
    if len(chain) >= 4 and area2(chain) != 0:
        spans = dict(_spans(chain))  # both ends of the mouth lie on the hull, so no stretch passes them
        out: list[Point] = []
        index = 0
        while index < len(chain):
            span = spans.get(index)
            if span is None or index + span >= len(chain):
                out.append(chain[index])
                index += 1
            else:
                out += _fill(chain[index : index + span + 1], width2, not air, counts)[:-1]
                index += span
        result = tuple(out)
    if not air:
        return result
    dx, dy = last.x - first.x, last.y - first.y
    if dx * dx + dy * dy < width2:
        counts[0] += 1
        return (first, last)
    counts[1] += 1
    return result


def bridge_grooves(boundary: BoardBoundary, width: Nm) -> GrooveResult:
    """The boundary on which a creepage path crosses every groove narrower than ``width``: a cut-out with
    a double normal shorter than ``width`` is left out, and a pocket of the outer ring whose mouth is
    shorter is filled, the ring following its mouth."""
    if width <= 0 or not boundary.outer:
        return GrooveResult(boundary, 0, len(boundary.cutouts))
    width2 = width * width
    counts = [0, 0]
    kept: list[Ring] = []
    for ring in boundary.cutouts:
        shortest = double_normal2(ring)
        if shortest is not None and shortest < width2:
            counts[0] += 1
        else:
            counts[1] += 1
            kept.append(ring)
    outer = boundary.outer
    spans = _spans(outer) if len(outer) >= 4 and area2(outer) != 0 else []
    if spans:
        start = spans[0][0]  # a point of the hull: from it no stretch runs past the end of the ring
        turned = (*outer[start:], *outer[:start])
        table = {(first - start) % len(outer): span for first, span in spans}
        out: list[Point] = []
        index = 0
        while index < len(turned):
            span = table.get(index)
            if span is None:
                out.append(turned[index])
                index += 1
                continue
            chain = tuple(turned[(index + step) % len(turned)] for step in range(span + 1))
            filled = _fill(chain, width2, True, counts)
            out += filled[:-1]
            index += span
        if len(out) >= 3 and area2(out) != 0:
            outer = tuple(out)
    return GrooveResult(replace(boundary, outer=outer, cutouts=tuple(kept)), counts[0], counts[1])


def groove_points(boundary: BoardBoundary) -> frozenset[Point]:
    """The vertices of the cut-outs and of the chains of the pockets of the outer ring, the two ends of
    each mouth left out: a creepage path that bends at one of them passes a groove."""
    found = {point for ring in boundary.cutouts for point in ring}
    for pocket in pockets(boundary.outer):
        found.update(pocket.chain[1:-1])
    return frozenset(found)


def passes_groove(points: Sequence[Point], boundary: BoardBoundary) -> bool:
    """Whether a creepage path with these points bends at a vertex of a cut-out or of a pocket, or
    crosses the wall of one: one of its points between the two ends lies on a cut-out's ring or on the
    chain of a pocket, within a nanometre."""
    middle = points[1:-1]
    if not middle:
        return False
    chains: list[Ring] = [(*ring, ring[0]) for ring in boundary.cutouts]
    chains += [pocket.chain for pocket in pockets(boundary.outer)]
    for chain in chains:
        ends = () if chain[0] == chain[-1] else (chain[0], chain[-1])
        for point in middle:
            if point in ends:
                continue
            for u, v in zip(chain, chain[1:], strict=False):
                if dist2_point_segment(point, u, v) <= 2:
                    return True
    return False


__all__ = [
    "EVIDENCE",
    "GrooveResult",
    "Pocket",
    "bridge_grooves",
    "double_normal2",
    "groove_points",
    "passes_groove",
    "pockets",
]
