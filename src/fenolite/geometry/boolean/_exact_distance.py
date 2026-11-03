# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Private exact continuous curve certificates by convex segment capsules (c0332).

Each rational parameter interval is assigned to one target segment. Both
endpoints lie in its closed radius-sqrt(1/2) capsule, so convexity covers every
interior point. Gap-free intervals cover whole edges; both directions cover
whole boundaries. Merely close vertices never establish this certificate.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from fractions import Fraction as F
from math import ceil, floor

from fenolite.geometry.boolean._exact_faces import Ring, require
from fenolite.geometry.boolean._exact_noding import Budget, ExactPoint, Segment, candidate_pairs
from fenolite.geometry.boolean.base import COORD_LIMIT


@dataclass(frozen=True, slots=True)
class Interval:
    edge: int
    lo: F
    hi: F
    target: int


@dataclass(frozen=True, slots=True)
class Cover:
    intervals: tuple[Interval, ...]
    maximum_squared_distance: F


def distance_squared(p: ExactPoint, a: ExactPoint, b: ExactPoint, budget: Budget) -> F:
    budget.distance_probe()
    check = budget.distance_value
    dx, dy = check(b[0] - a[0]), check(b[1] - a[1])
    zx, zy = check(p[0] - a[0]), check(p[1] - a[1])
    length = check(dx * dx + dy * dy)
    dot = check(zx * dx + zy * dy)
    if not length or dot <= 0:
        return check(zx * zx + zy * zy)
    if dot >= length:
        return check((p[0] - b[0]) ** 2 + (p[1] - b[1]) ** 2)
    determinant = check(zx * dy - zy * dx)
    return check(determinant * determinant / length)


def _envelope(a: ExactPoint, b: ExactPoint, channel: int) -> Segment:
    # The actual curves stay inside the input domain. Clipping an expanded
    # query box to that domain cannot exclude any actual target point.
    return Segment(
        (max(-COORD_LIMIT, floor(min(a[0], b[0])) - 1), max(-COORD_LIMIT, floor(min(a[1], b[1])) - 1)),
        (min(COORD_LIMIT, ceil(max(a[0], b[0])) + 1), min(COORD_LIMIT, ceil(max(a[1], b[1])) + 1)),
        channel,
    )


def cover(source: Ring, target: Ring, budget: Budget) -> Cover:
    require(len(source) >= 2 and len(target) >= 2, "continuous cover needs nonempty curves")
    first = tuple(zip(source, source[1:] + source[:1], strict=True))
    second = tuple(zip(target, target[1:] + target[:1], strict=True))
    boxes = tuple(_envelope(a, b, channel) for channel, edges in enumerate((first, second)) for a, b in edges)
    pairs = candidate_pairs(boxes, budget, edge_limit=budget.limits.halfedges, start_stage=False)
    candidates: dict[int, list[int]] = defaultdict(list)
    for i, j in pairs:
        if i < len(first) <= j:
            candidates[i].append(j - len(first))
    proof: list[Interval] = []
    maximum = F(0)
    for edge, (start, end) in enumerate(first):
        options = candidates[edge]
        require(bool(options), "continuous edge has no capsule candidates")
        todo = [(start, end, F(0), F(1), 0)]
        while todo:
            budget.check()
            p, q, lo, hi, depth = todo.pop()
            selected: tuple[int, F, F] | None = None
            first_inside = last_inside = False
            for j in options:
                a, b = second[j]
                d0, d1 = distance_squared(p, a, b, budget), distance_squared(q, a, b, budget)
                first_inside |= d0 <= F(1, 2)
                last_inside |= d1 <= F(1, 2)
                if d0 <= F(1, 2) and d1 <= F(1, 2):
                    selected = (j, d0, d1)
                    break
            require(first_inside and last_inside, "uncovered continuous interval endpoint")
            if selected is not None:
                budget.distance_interval()
                j, d0, d1 = selected
                maximum = max(maximum, d0, d1)
                proof.append(Interval(edge, lo, hi, j))
            else:
                require(depth < budget.limits.distance_depth, "distance subdivision depth budget exceeded")
                middle = ((p[0] + q[0]) / 2, (p[1] + q[1]) / 2)
                parameter = (lo + hi) / 2
                todo.extend(((middle, q, parameter, hi, depth + 1), (p, middle, lo, parameter, depth + 1)))
    certificate = Cover(tuple(proof), maximum)
    verify_cover(source, target, certificate, budget)
    return certificate


def verify_cover(source: Ring, target: Ring, certificate: Cover, budget: Budget) -> None:
    require(len(source) >= 2 and len(target) >= 2, "continuous cover needs nonempty curves")
    require(
        len(certificate.intervals) <= budget.limits.distance_intervals, "distance interval budget exceeded"
    )
    groups: dict[int, list[tuple[F, F]]] = defaultdict(list)
    maximum = F(0)
    for part in certificate.intervals:
        budget.check()
        require(
            0 <= part.edge < len(source) and 0 <= part.target < len(target), "invalid cover segment reference"
        )
        require(0 <= part.lo < part.hi <= 1, "invalid cover parameter interval")
        start, end = source[part.edge], source[(part.edge + 1) % len(source)]
        for t in (part.lo, part.hi):
            p = (start[0] + t * (end[0] - start[0]), start[1] + t * (end[1] - start[1]))
            value = distance_squared(p, target[part.target], target[(part.target + 1) % len(target)], budget)
            require(value <= F(1, 2), "continuous interval exceeds precision bound")
            maximum = max(maximum, value)
        groups[part.edge].append((part.lo, part.hi))
    require(set(groups) == set(range(len(source))), "continuous source edge lacks a cover")
    for intervals in groups.values():
        cursor = F(0)
        for lo, hi in sorted(intervals):
            require(lo == cursor, "continuous parameter gap or overlap")
            cursor = hi
        require(cursor == 1, "continuous parameter cover is incomplete")
    require(maximum == certificate.maximum_squared_distance, "continuous distance summary mismatch")


def boundary_bound(source: Ring, target: Ring, budget: Budget) -> tuple[Cover, Cover]:
    return cover(source, target, budget), cover(target, source, budget)
