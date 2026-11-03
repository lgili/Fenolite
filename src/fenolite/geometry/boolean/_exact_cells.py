# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Private exact half-even cell constraints for pressure-limited proposals only."""

from __future__ import annotations

from fractions import Fraction as F

from fenolite.geometry.boolean._exact_faces import Ring, cross, require, sign, sub
from fenolite.geometry.boolean._exact_noding import Budget, ExactPoint, IntPoint, ResourceLimit


def cell_point(
    ring: Ring,
    j: int,
    ending: bool,
    omitted: frozenset[tuple[int, int]],
    projected: dict[ExactPoint, IntPoint],
    budget: Budget,
    owner: int,
) -> ExactPoint | None:
    require(len(ring) >= 3 and 0 <= j < len(ring), "invalid cell target")
    a = ring[j]
    z = ring[(j - 1) % len(ring)] if ending else ring[(j + 1) % len(ring)]
    delta = sub(z, a)
    length = max(abs(value) for value in delta)
    require(length > 0, "zero cell source edge")
    active: list[int] = []
    for k in range(len(ring)):
        budget.visit(1)
        if (owner, k) not in omitted or k == j:
            if len(active) >= budget.limits.nodes:
                raise ResourceLimit("exact cell active-node storage budget exceeded")
            active.append(k)
    pos = active.index(j)
    left, right = active[(pos - 1) % len(active)], active[(pos + 1) % len(active)]
    target_sign = sign(cross(sub(ring[left], a), sub(ring[right], a)))
    if not target_sign:
        return None
    require(a in projected and ring[right if ending else left] in projected, "unbound cell source")
    anchor = F(projected[a][0]), F(projected[a][1])
    other_integer = projected[ring[right if ending else left]]
    other = F(other_integer[0]), F(other_integer[1])
    q: list[int] = []
    for c in (0, 1):
        value = a[c] + F(1, 2)
        floor = value.numerator // value.denominator
        if value.denominator == 1 and delta[c] < 0:
            floor -= 1
        elif value.denominator == 1 and not delta[c]:
            floor = projected[a][c]  # Constant tie belongs to its HALF-EVEN parity.
        q.append(floor)
    start = F(0)
    stop = min(F(1), F(1024) / length)
    budget.coordinate(stop)
    while start < stop:
        budget.visit(1)
        times = tuple(
            (((F(q[c]) + F(1, 2) if delta[c] > 0 else F(q[c]) - F(1, 2)) - a[c]) / delta[c])
            if delta[c]
            else None
            for c in (0, 1)
        )
        end = min((stop, *(t for t in times if t is not None)))
        require(end > start, "nonprogressing cell partition")
        budget.coordinate(end)
        label = F(q[0]), F(q[1])
        turn = (
            cross(sub(label, anchor), sub(other, anchor))
            if ending
            else cross(sub(other, anchor), sub(label, anchor))
        )
        if sign(turn) == target_sign:
            parameter = (start + end) / 2
            budget.coordinate(parameter)
            point = a[0] + parameter * delta[0], a[1] + parameter * delta[1]
            budget.coordinate(point[0])
            budget.coordinate(point[1])
            return point
        for c, value in enumerate(times):
            if value == end:
                q[c] += 1 if delta[c] > 0 else -1
        start = end
    return None
