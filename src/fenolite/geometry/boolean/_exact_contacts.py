# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Private bounded contact/ray-word certificates for exact and projected loops."""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Sequence
from fractions import Fraction
from functools import cmp_to_key
from math import ceil, floor

from fenolite.geometry.boolean._exact_faces import ExactSegment, Ring, angular, cross, require, sub, winding
from fenolite.geometry.boolean._exact_noding import Budget, ExactPoint, Segment, candidate_pairs

Word = tuple[tuple[int, int], ...]


def on(p: ExactPoint, a: ExactPoint, b: ExactPoint) -> bool:
    return cross(sub(p, a), sub(b, a)) == 0 and all(
        min(a[k], b[k]) <= p[k] <= max(a[k], b[k]) for k in (0, 1)
    )


def hits(a: ExactPoint, b: ExactPoint, c: ExactPoint, d: ExactPoint) -> set[ExactPoint]:
    first, second = sub(b, a), sub(d, c)
    det = cross(first, second)
    if det:
        delta = sub(c, a)
        t, u = cross(delta, second) / det, cross(delta, first) / det
        if 0 <= t <= 1 and 0 <= u <= 1:
            return {(a[0] + t * first[0], a[1] + t * first[1])}
        return set()
    return {p for p in (a, b, c, d) if on(p, a, b) and on(p, c, d)}


def contacts(
    loops: Sequence[Ring],
    ids: set[int],
    budget: Budget,
    *,
    only_simple: bool = False,
    conflicts: list[tuple[int, int, int]] | None = None,
) -> dict[ExactPoint, Word]:
    edges: list[tuple[int, int, ExactPoint, ExactPoint]] = []
    boxes: list[Segment] = []
    for i in sorted(ids):
        for position, (a, b) in enumerate(zip(loops[i], loops[i][1:] + loops[i][:1], strict=True)):
            edges.append((i, position, a, b))
            boxes.append(
                Segment(
                    (floor(min(a[0], b[0])), floor(min(a[1], b[1]))),
                    (ceil(max(a[0], b[0])), ceil(max(a[1], b[1]))),
                    0,
                )
            )
    pairs = candidate_pairs(boxes, budget, edge_limit=budget.limits.fragments, start_stage=False)
    touching: dict[ExactPoint, set[int]] = defaultdict(set)
    for k, (first, second) in enumerate(pairs):
        if k % 256 == 0:
            budget.check()
        i, position, a, b = edges[first]
        j, other_position, c, d = edges[second]
        if only_simple and i != j:
            continue
        common = hits(a, b, c, d)
        if not common:
            continue
        if i == j:
            distance = abs(position - other_position)
            valid = distance in (1, len(loops[i]) - 1) and len(common) == 1
            if not valid and conflicts is not None:
                conflicts.append((i, position, other_position))
            else:
                require(valid, "nonsimple projected/retained ring")
        else:
            require(len(common) == 1, "retained loops overlap along an edge")
            touching[next(iter(common))].update((i, j))
    result: dict[ExactPoint, Word] = {}
    zero = (Fraction(0), Fraction(0))
    for p, members in touching.items():
        rays: list[tuple[ExactPoint, tuple[int, int]]] = []
        for i in sorted(members):
            for k, (a, b) in enumerate(zip(loops[i], loops[i][1:] + loops[i][:1], strict=True)):
                if k % 256 == 0:
                    budget.check()
                if on(p, a, b):
                    if p != a:
                        rays.append((sub(a, p), (i, -1)))
                    if p != b:
                        rays.append((sub(b, p), (i, 1)))
        require(len(rays) == 2 * len(members), "contact incidence is not two rays per loop")
        rays.sort(key=cmp_to_key(lambda a, b: angular(zero, a[0], b[0])))
        word = tuple(label for _, label in rays)
        result[p] = min(word[k:] + word[:k] for k in range(len(word)))
    return result


def parents(loops: Sequence[Ring], budget: Budget) -> tuple[tuple[int, ...], dict[int, int]]:
    from fenolite.geometry.boolean._exact_faces import area2

    areas = tuple(area2(r, budget) for r in loops)
    positive = tuple(i for i, area in enumerate(areas) if area > 0)
    sources = {
        i: tuple(ExactSegment(a, b, 0) for a, b in zip(loops[i], loops[i][1:] + loops[i][:1], strict=True))
        for i in positive
    }
    boxes = {
        i: (
            min(p[0] for p in loops[i]),
            min(p[1] for p in loops[i]),
            max(p[0] for p in loops[i]),
            max(p[1] for p in loops[i]),
        )
        for i in positive
    }
    result: dict[int, int] = {}
    for i, ring in enumerate(loops):
        if areas[i] >= 0:
            continue
        # The reversed negative edge probes the hole's interior. Strictly
        # outside a candidate box stays outside at every small enough epsilon.
        edge = (ring[1], ring[0])
        x, y = (edge[0][0] + edge[1][0]) / 2, (edge[0][1] + edge[1][1]) / 2
        found = [
            j
            for j in positive
            if boxes[j][0] <= x <= boxes[j][2]
            and boxes[j][1] <= y <= boxes[j][3]
            and winding(edge, sources[j], budget)[0] != 0
        ]
        require(bool(found), "negative boundary has no parent")
        result[i] = min(found, key=lambda j: areas[j])
    return positive, result
