# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Test-only complete native zone identity and conservative continuous10nm proof."""

from __future__ import annotations

from collections.abc import Mapping, Sequence

from fenolite.backends.altium.pour import PolygonPour
from fenolite.core.coords import Point
from fenolite.geometry import Polygon
from fenolite.geometry.boolean._exact_faces import difference_loops
from fenolite.geometry.boolean._exact_noding import Budget, Segment
from fenolite.geometry.polygon import convex_hull
from fenolite.model.board import Zone


def matched_zones(
    zones: Sequence[Zone], names: Mapping[str, str], pours: Sequence[PolygonPour]
) -> tuple[tuple[Zone, PolygonPour], ...]:
    """The authored probe has one zone per net/layer; never lose or reuse an owner."""
    assert len(zones) == len(pours), "native zone count changed"
    matched: list[tuple[Zone, PolygonPour]] = []
    used: set[str] = set()
    for pour in pours:
        matches = [z for z in zones if z.layers == (pour.layer,) and names.get(z.net_id or "") == pour.net]
        assert len(matches) == 1, ("native zone identity", pour.layer, pour.net, len(matches))
        zone = matches[0]
        assert zone.id not in used, "native zone reused"
        used.add(zone.id)
        assert all(fill.layer == pour.layer for fill in zone.fills), "native fill layer changed"
        if not pour.poured or not pour.pieces:
            assert not zone.fills, "refused/empty pour gained copper"
        matched.append((zone, pour))
    return tuple(matched)


def within_written_boundary_band(
    written: Sequence[Polygon], native: Sequence[Polygon], *, budget: Budget | None = None
) -> bool:
    """Certify ALL changed copper is within10nm; no realization, sampling or small-piece filter.

    The disk hull is contained in the exact radius10 disk. Each edge capsule is
    its Minkowski sum with that hull, hence a SUBSET of the true Euclidean band.
    Empty exact differences are therefore sufficient; an undecidable/refused
    operation propagates its failure. Both directions share the supplied Budget.
    """
    budget = budget if budget is not None else Budget()
    disk = convex_hull(Point(x, y) for x in range(-10, 11) for y in range(-10, 11) if x * x + y * y <= 100)
    capsules: list[Polygon] = []
    for polygon in written:
        for ring in polygon.rings():
            for a, b in zip(ring, (*ring[1:], ring[0]), strict=True):
                budget.visit(1)
                capsules.append(
                    Polygon(convex_hull(Point(p.x + d.x, p.y + d.y) for p in (a, b) for d in disk))
                )

    def outside(subject: Sequence[Polygon], cut: Sequence[Polygon]) -> bool:
        segments: list[Segment] = []
        for channel, polygons in enumerate((subject, cut)):
            for polygon in polygons:
                for ring in polygon.rings():
                    for a, b in zip(ring, (*ring[1:], ring[0]), strict=True):
                        budget.visit(1)
                        segments.append(Segment((a.x, a.y), (b.x, b.y), channel))
        return bool(difference_loops(segments, budget))

    return not outside(native, (*written, *capsules)) and not outside(written, (*native, *capsules))
