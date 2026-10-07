# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The copper of a zone fill as a region with holes (capability board-analyses, "Copper fill regions";
``docs/analyses.md``, "Power paths").

A stored fill is one ring whose holes join it by slits: pairs of edges between the same two points in
opposite directions (``H-K-FILL-SLIT``). ``unfracture`` removes those pairs and chains the remaining edges
by exact endpoint equality, so every point of a region is a stored integer point. The same function undoes
``geometry.polygon.keyhole_ring``, the form in which an import stores a pour with holes. A fill whose
edges do not chain, or whose areas do not agree, is left out and counted: nothing is repaired.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from fractions import Fraction

from fenolite.core.coords import Point
from fenolite.geometry import area2
from fenolite.model.base import Entity
from fenolite.model.design import Design

Ring = tuple[Point, ...]
_Q = tuple[Fraction, Fraction]


@dataclass(frozen=True, slots=True)
class FillRegion:
    """The copper of one fill: ``outer`` less ``holes``, the rings as stored (neither turned nor rounded).
    ``where`` is the zone's locator, else its id, then ``#`` and the index of the fill in the zone;
    ``area2`` is twice the area of the copper."""

    zone_id: str
    net: str
    layer: str
    where: str
    outer: Ring
    holes: tuple[Ring, ...]
    area2: int


def _clean(points: Sequence[Point]) -> Ring:
    out: list[Point] = []
    for point in points:
        if not out or out[-1] != point:
            out.append(point)
    while len(out) > 1 and out[0] == out[-1]:
        out.pop()
    return tuple(out)


def unfracture(ring: Sequence[Point]) -> tuple[Ring, tuple[Ring, ...]] | None:
    """The outer ring and the holes of a stored ring: every slit removed, the other edges chained in the
    stored order by exact endpoint equality. ``None`` when they do not chain into rings with an area."""
    points = _clean(ring)
    count = len(points)
    if count < 3:
        return None
    edges = [(points[i], points[(i + 1) % count]) for i in range(count)]
    waiting: dict[tuple[Point, Point], list[int]] = {}
    removed = [False] * count
    for index, (u, v) in enumerate(edges):
        partners = waiting.get((v, u))
        if partners:
            removed[index] = removed[partners.pop()] = True
        else:
            waiting.setdefault((u, v), []).append(index)
    open_at: dict[Point, list[list[Point]]] = {}  # the chains that end at a point, the latest last
    rings: list[Ring] = []
    for index, (u, v) in enumerate(edges):
        if removed[index]:
            continue
        held = open_at.get(u)
        chain = held.pop() if held else [u]
        if v == chain[0]:
            rings.append(tuple(chain))
            continue
        chain.append(v)
        open_at.setdefault(v, []).append(chain)
    if any(open_at.values()) or not rings:
        return None
    if any(len(found) < 3 or area2(found) == 0 for found in rings):
        return None
    largest = max(range(len(rings)), key=lambda i: (abs(area2(rings[i])), -i))
    return rings[largest], tuple(found for i, found in enumerate(rings) if i != largest)


def _where(entity: Entity) -> str:
    provenance = entity.provenance
    return provenance.locator if provenance is not None and provenance.locator else entity.id


def fill_regions(design: Design) -> tuple[tuple[FillRegion, ...], int]:
    """One region per fill of a zone that has a net, and the count of fills left out: a fill whose edges
    do not chain, or whose stored area is not the outer ring's less the holes'."""
    board = design.board
    if board is None:
        return (), 0
    names = {net.id: net.name for net in design.circuit.nets}
    regions: list[FillRegion] = []
    left_out = 0
    for zone in board.zones:
        if zone.net_id is None:
            continue
        net = names.get(zone.net_id, zone.net_id)
        for index, fill in enumerate(zone.fills):
            stored = _clean(fill.polygon)
            found = unfracture(stored)
            if found is None:
                left_out += 1
                continue
            outer, holes = found
            twice = abs(area2(stored))
            if twice == 0 or twice != abs(area2(outer)) - sum(abs(area2(hole)) for hole in holes):
                left_out += 1
                continue
            regions.append(
                FillRegion(zone.id, net, fill.layer, f"{_where(zone)}#{index}", outer, holes, twice)
            )
    return tuple(regions), left_out


def _clipped_area2(ring: Ring, hull: Ring) -> Fraction:
    """Twice the area of ``ring`` inside the convex ``hull`` (positive orientation), not below 0. Each
    edge of the hull cuts the ring with exact rational points; on a ring that is not convex the cut leaves
    edges along the hull's lines that enclose no area, so the shoelace sum is still the area."""
    out: list[_Q] = [(Fraction(p.x), Fraction(p.y)) for p in ring]
    for i, a in enumerate(hull):
        b = hull[(i + 1) % len(hull)]
        current, out = out, []
        for j, q in enumerate(current):
            p = current[j - 1]
            sp = (b.x - a.x) * (p[1] - a.y) - (b.y - a.y) * (p[0] - a.x)
            sq = (b.x - a.x) * (q[1] - a.y) - (b.y - a.y) * (q[0] - a.x)
            if (sp < 0) != (sq < 0) and sp != sq:
                t = sp / (sp - sq)
                out.append((p[0] + t * (q[0] - p[0]), p[1] + t * (q[1] - p[1])))
            if sq >= 0:
                out.append(q)
        if not out:
            return Fraction(0)
    total = Fraction(0)
    for j, q in enumerate(out):
        p = out[j - 1]
        total += p[0] * q[1] - q[0] * p[1]
    return abs(total)


def area_outside(region: FillRegion, hulls: Sequence[Sequence[Point]]) -> Fraction:
    """The area of the region outside the convex ``hulls``, in square nanometres: the region's area less,
    for each hull, the outer ring clipped by it and plus each hole clipped by it. A hull of fewer than
    three points has no area. The hulls must not overlap each other."""
    twice = Fraction(region.area2)
    for hull in hulls:
        ring = tuple(hull)
        if len(ring) < 3 or area2(ring) == 0:
            continue
        if area2(ring) < 0:
            ring = tuple(reversed(ring))
        twice -= _clipped_area2(region.outer, ring)
        for hole in region.holes:
            twice += _clipped_area2(hole, ring)
    return max(twice, Fraction(0)) / 2


__all__ = ["FillRegion", "area_outside", "fill_regions", "unfracture"]
