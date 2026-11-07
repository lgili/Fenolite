# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Private exact directed-subchain witnesses; capsule intervals remain separate."""

from __future__ import annotations

from collections import Counter
from collections.abc import Sequence
from dataclasses import dataclass
from fractions import Fraction as F

from fenolite.geometry.boolean._exact_faces import Ring, require
from fenolite.geometry.boolean._exact_noding import Budget, ExactPoint, ResourceLimit

Edge = tuple[ExactPoint, ExactPoint]


@dataclass(frozen=True, slots=True)
class IdentityRun:
    source_start: int
    target_start: int
    count: int


def _reserve(entries: int, budget: Budget) -> None:
    if entries > budget.limits.nodes:
        raise ResourceLimit("exact identity storage budget exceeded")
    budget.check()


def identity_matches(
    first: Sequence[Edge], second: Sequence[Edge], budget: Budget
) -> tuple[dict[int, int], tuple[IdentityRun, ...]]:
    if len(first) + len(second) > budget.limits.halfedges:
        raise ResourceLimit("exact identity halfedge budget exceeded")
    target: dict[Edge, int] = {}
    sources: Counter[Edge] = Counter()
    targets: Counter[Edge] = Counter()
    for edge in first:
        budget.visit(1)
        _reserve(len(sources) + int(edge not in sources), budget)
        sources[edge] += 1
    for j, edge in enumerate(second):
        budget.visit(1)
        _reserve(len(sources) + len(targets) + len(target) + 2 * int(edge not in targets), budget)
        targets[edge] += 1
        target[edge] = j
    equal: dict[int, int] = {}
    fixed = len(sources) + len(targets) + len(target)
    for i, edge in enumerate(first):
        budget.visit(1)
        if sources[edge] == 1 and targets[edge] == 1:
            j = target[edge]
            require(edge == second[j], "identity endpoint equality failed")
            _reserve(fixed + len(equal) + 1, budget)
            equal[i] = j
    runs: list[IdentityRun] = []
    for i, j in sorted(equal.items()):
        budget.visit(1)
        if (
            runs
            and runs[-1].source_start + runs[-1].count == i
            and (runs[-1].target_start + runs[-1].count) % len(second) == j
        ):
            old = runs.pop()
            runs.append(IdentityRun(old.source_start, old.target_start, old.count + 1))
        else:
            _reserve(fixed + len(equal) + len(runs) + 1, budget)
            runs.append(IdentityRun(i, j, 1))
    return equal, tuple(runs)


def verify_identities(
    source: Ring, target: Ring, runs: Sequence[object], budget: Budget
) -> dict[int, list[tuple[F, F]]]:
    groups: dict[int, list[tuple[F, F]]] = {}
    used_target: set[int] = set()
    for run in runs:
        require(isinstance(run, IdentityRun), "invalid identity run descriptor")
        # require() does not narrow a Python object for static analysis.
        if not isinstance(run, IdentityRun):
            raise AssertionError("unreachable identity descriptor")
        require(
            type(run.source_start) is int and type(run.target_start) is int and type(run.count) is int,
            "invalid identity run field type",
        )
        require(
            0 <= run.source_start < len(source)
            and 0 <= run.target_start < len(target)
            and 0 < run.count <= min(len(source), len(target)),
            "invalid identity run bounds",
        )
        for offset in range(run.count):
            budget.visit(1)
            i = (run.source_start + offset) % len(source)
            j = (run.target_start + offset) % len(target)
            require(i not in groups and j not in used_target, "identity ownership/multiplicity overlap")
            for a, b in (
                (source[i], target[j]),
                (source[(i + 1) % len(source)], target[(j + 1) % len(target)]),
            ):
                budget.distance_probe()
                for value in (*a, *b):
                    budget.distance_value(value)
                require(a == b, "identity edge coordinate mismatch")
            _reserve(len(groups) + len(used_target) + 2, budget)
            groups[i] = [(F(0), F(1))]
            used_target.add(j)
    return groups
