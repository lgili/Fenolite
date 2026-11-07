# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Private bounded candidates for a projected self-crossing; every result needs certification."""

from __future__ import annotations

from collections.abc import Iterator, Sequence
from itertools import combinations

from fenolite.geometry.boolean._exact_contacts import contacts
from fenolite.geometry.boolean._exact_faces import Ring, clean
from fenolite.geometry.boolean._exact_noding import Budget, ExactPoint, IntPoint, ResourceLimit, Segment
from fenolite.geometry.boolean._exact_realization import Projection, project_boundaries, rational
from fenolite.geometry.errors import GeometryError


def candidates(
    loops: Sequence[Ring], source: Sequence[Segment], projected: dict[ExactPoint, IntPoint], budget: Budget
) -> Iterator[Projection]:
    budget.stage("boundary repair")
    integer = tuple(clean(rational(tuple(projected[p] for p in r)), budget) for r in loops)
    conflicts: list[tuple[int, int, int]] = []
    contacts(
        integer,
        {i for i, r in enumerate(integer) if len(r) >= 3},
        budget,
        only_simple=True,
        conflicts=conflicts,
    )
    implicated: dict[int, set[ExactPoint]] = {}
    for i, a, b in conflicts:
        implicated.setdefault(i, set()).update(
            integer[i][j % len(integer[i])] for edge in (a, b) for j in (edge, edge + 1)
        )
    variables = tuple(
        sorted(
            (i, j)
            for i, ring in enumerate(loops)
            for j, p in enumerate(ring)
            if i in implicated and projected[p] in implicated[i] and any(c.denominator != 1 for c in p)
        )
    )
    if not variables:
        return
    if budget.limits.repair_nodes <= 0:
        raise ResourceLimit("exact geometry repair-node budget disables repair")
    if len(variables) > budget.limits.repair_proposal_nodes:
        raise ResourceLimit("exact geometry implicated proposal-node budget exceeded")
    budget.repair_trial()  # Count the already-refused nearest candidate.
    # One fully certified proposal avoids enumerating combinations of unrelated
    # hairlines. The caller still applies its real policy and all certificates.
    budget.repair_trial()
    try:
        projection = project_boundaries(
            loops, source, budget, projected=projected, omitted=frozenset(variables)
        )
    except ResourceLimit:
        raise
    except GeometryError:
        pass
    else:
        yield projection
    if len(variables) > budget.limits.repair_nodes:
        raise ResourceLimit("exact geometry implicated enumeration-node budget exceeded")
    for count in range(1, len(variables) + 1):
        if count == len(variables):
            continue  # The complete set has already been proposed exactly once.
        for subset in combinations(variables, count):
            budget.repair_trial()
            try:
                projection = project_boundaries(
                    loops, source, budget, projected=projected, omitted=frozenset(subset)
                )
            except ResourceLimit:
                raise
            except GeometryError:
                continue
            yield projection
