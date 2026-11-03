# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Bounded exact-curve subdivision proposals; only the caller's full certificate can accept them."""

from __future__ import annotations

from collections.abc import Iterator, Sequence
from dataclasses import dataclass
from fractions import Fraction as F

from fenolite.geometry.boolean._exact_cells import cell_point
from fenolite.geometry.boolean._exact_contacts import contacts
from fenolite.geometry.boolean._exact_distance import (
    _envelope,  # pyright: ignore[reportPrivateUsage]
    distance_squared,
)
from fenolite.geometry.boolean._exact_faces import Ring, area2, clean, require
from fenolite.geometry.boolean._exact_noding import Budget, ExactPoint, IntPoint, ResourceLimit, Segment
from fenolite.geometry.boolean._exact_noding import candidate_pairs as indexed_pairs
from fenolite.geometry.boolean._exact_realization import (
    Projection,
    point_ring,
    project_boundaries,
    project_nodes,
    projection_bound,
    rational,
    ring_key,
)
from fenolite.geometry.errors import GeometryError
from fenolite.geometry.polygon import Polygon, normalize_polygons


def _retained(projection: Projection, result: Sequence[Polygon], budget: Budget) -> set[int]:
    """Strict policy-bound ring identification; the original certificate still judges every obligation."""
    require(tuple(result) == normalize_polygons(result), "refinement policy output is not normalized")
    require(all(poly.area2 > 0 for poly in result), "refinement policy keeps zero-area piece")
    inverted = {
        i
        for i, ring in enumerate(projection.integer_loops)
        if area2(projection.loops[i], budget) * area2(rational(ring), budget) < 0
    }
    keys = {
        ring_key(tuple(reversed(ring)) if i in inverted else ring): i
        for i, ring in enumerate(projection.integer_loops)
        if i not in projection.collapsed
    }
    require(
        len(keys) == len(projection.integer_loops) - len(projection.collapsed),
        "refinement duplicate policy boundary",
    )
    retained: set[int] = set()
    for poly in result:
        key = ring_key(point_ring(poly.outer))
        require(key in keys, "refinement policy changes outer boundary")
        outer = keys[key]
        require(outer in projection.outers and outer not in retained, "refinement outer ownership")
        retained.add(outer)
        for hole in poly.holes:
            key = ring_key(point_ring(hole))
            require(key in keys, "refinement policy changes hole boundary")
            child = keys[key]
            require(
                projection.parent.get(child) == outer and child not in retained,
                "refinement hole ownership",
            )
            retained.add(child)
    require(not retained.intersection(inverted), "refinement retained orientation")
    return retained


def _bad_probes(source: Ring, target: Ring, budget: Budget) -> tuple[int, ...]:
    """Necessary endpoint/midpoint pruning only; NEVER continuous coverage or acceptance."""
    if len(target) < 3:
        return tuple(range(len(source)))
    edges = tuple(zip(target, target[1:] + target[:1], strict=True))
    probes = tuple((p, (i,)) for i, p in enumerate(source)) + tuple(
        (((a[0] + b[0]) / 2, (a[1] + b[1]) / 2), (i, (i + 1) % len(source)))
        for i, (a, b) in enumerate(zip(source, source[1:] + source[:1], strict=True))
    )
    # Midpoints are necessary probes on the SAME exact curve, never a sampled certificate.
    boxes = tuple(_envelope(p, p, 0) for p, _ in probes) + tuple(_envelope(a, b, 1) for a, b in edges)
    pairs = indexed_pairs(boxes, budget, edge_limit=budget.limits.halfedges, start_stage=False)
    options: dict[int, list[int]] = {i: [] for i in range(len(probes))}
    for i, j in pairs:
        if i < len(probes) <= j:
            options[i].append(j - len(probes))
    bad: set[int] = set()
    for i, (point, owners) in enumerate(probes):
        if not any(distance_squared(point, edges[j][0], edges[j][1], budget) <= F(1, 2) for j in options[i]):
            bad.update(owners)
    return tuple(sorted(bad))


def _integer_ring(
    owner: int,
    ring: Ring,
    omitted: frozenset[tuple[int, int]],
    projected: dict[ExactPoint, IntPoint],
    budget: Budget,
) -> Ring:
    return clean(
        rational(tuple(projected[p] for j, p in enumerate(ring) if (owner, j) not in omitted)), budget
    )


def _subdivide(ring: Ring, edge: int, point: ExactPoint, budget: Budget) -> Ring:
    require(0 <= edge < len(ring), "refinement edge outside ring")
    a, b = ring[edge], ring[(edge + 1) % len(ring)]
    dx, dy = b[0] - a[0], b[1] - a[1]
    px, py = point[0] - a[0], point[1] - a[1]
    require(dx * py == dy * px, "refinement point is not collinear")
    require(0 < dx * px + dy * py < dx * dx + dy * dy, "refinement point is not interior")
    require(point not in ring, "refinement repeats an existing node")
    refined = ring[: edge + 1] + (point,) + ring[edge + 1 :]
    require(clean(refined, budget) == clean(ring, budget), "refinement changes exact curve")
    return refined


@dataclass(slots=True)
class _TrialState:
    projected: dict[ExactPoint, IntPoint]
    omitted: frozenset[tuple[int, int]]
    points: dict[ExactPoint, IntPoint]
    loops: tuple[Ring, ...]

    def adopt(
        self,
        projected: dict[ExactPoint, IntPoint],
        omitted: frozenset[tuple[int, int]],
        loops: tuple[Ring, ...],
    ) -> None:
        self.projected = projected
        self.omitted = omitted
        self.loops = loops


def _first_pressure(
    owners: Sequence[int],
    loops: tuple[Ring, ...],
    omitted: frozenset[tuple[int, int]],
    projected: dict[ExactPoint, IntPoint],
    budget: Budget,
    remaining: int,
) -> tuple[dict[int, tuple[int, ...]], bool]:
    initial: dict[int, tuple[int, ...]] = {}
    for owner in owners:
        ring = loops[owner]
        bad = _bad_probes(ring, _integer_ring(owner, ring, omitted, projected, budget), budget)
        if len(initial) >= budget.limits.faces:
            raise ResourceLimit("exact refinement initial-probe storage budget exceeded")
        initial[owner] = bad
        targets = tuple(j for j in bad if (owner, j) in omitted)
        if bad and not targets:
            return initial, False
        if targets:
            return initial, 26 * len(targets) > remaining
    return initial, False


def refinement_candidates(
    projection: Projection,
    source: Sequence[Segment],
    result: Sequence[Polygon],
    budget: Budget,
) -> Iterator[Projection]:
    """Yield at most one endpoint-pruned proposal, never a qualified result or an alternate certificate.

    The real caller supplies its actual debris output, then reapplies its policy and the ORIGINAL
    global certificate to the yielded projection. No cache, budget reset or source-dependent dispatch.
    """
    budget.check()
    projection_bound({p for ring in projection.loops for p in ring}, projection.projected)
    if budget.limits.repair_nodes <= 0:
        raise ResourceLimit("exact geometry repair-node budget disables refinement")
    original_pool = len(projection.omitted)
    if original_pool > budget.limits.repair_proposal_nodes:
        raise ResourceLimit("exact geometry refinement proposal-node budget exceeded")
    require(
        projection.source == frozenset((F(p[0]), F(p[1])) for s in source for p in (s.a, s.b)),
        "refinement source context differs",
    )
    original = projection.loops
    state = _TrialState(dict(projection.projected), projection.omitted, {}, original)
    retained = _retained(projection, result, budget)
    owners: list[int] = sorted({i for i, _ in state.omitted} & retained, key=lambda i: min(state.loops[i]))
    # Consume probes once in original owner order; this is a LOCAL pressure
    # estimate, not a global work bound or a certificate.
    initial_bad: dict[int, tuple[int, ...]]
    use_cells: bool
    initial_bad, use_cells = _first_pressure(
        owners,
        original,
        projection.omitted,
        state.projected,
        budget,
        budget.limits.repair_proposal_nodes - original_pool,
    )
    for owner in owners:
        for _ in range(budget.limits.repair_proposal_nodes + 1):
            ring: Ring = state.loops[owner]
            bad: tuple[int, ...] = (
                initial_bad.pop(owner)
                if owner in initial_bad
                else _bad_probes(
                    ring, _integer_ring(owner, ring, state.omitted, state.projected, budget), budget
                )
            )
            if not bad:
                break
            variables: list[int] = sorted(
                (j for j in bad if (owner, j) in state.omitted), key=lambda j: ring[j]
            )
            if not variables:
                return  # Unmodeled cleanup needs a separate reviewed proposal, not an implicit waiver.
            selected: tuple[Ring, dict[ExactPoint, IntPoint], frozenset[tuple[int, int]]] | None = None
            for j in variables:
                if selected is not None:
                    break
                for power in range(1 if use_cells else 13):
                    if selected is not None:
                        break
                    radius = F(2**power, 4)
                    adjacent = (((j - 1) % len(ring), True), (j, False))
                    for edge, ending in sorted(
                        adjacent,
                        key=lambda item: tuple(sorted((ring[item[0]], ring[(item[0] + 1) % len(ring)]))),
                    ):
                        if selected is not None:
                            break
                        if use_cells:
                            point = cell_point(ring, j, ending, state.omitted, state.projected, budget, owner)
                            if point is None:
                                continue
                        else:
                            a, b = ring[edge], ring[(edge + 1) % len(ring)]
                            length = max(abs(a[0] - b[0]), abs(a[1] - b[1]))
                            if radius >= length:
                                continue
                            t = 1 - radius / length if ending else radius / length
                            point = (a[0] + t * (b[0] - a[0]), a[1] + t * (b[1] - a[1]))
                        if point in ring:
                            continue
                        budget.coordinate(point[0])
                        budget.coordinate(point[1])
                        if point not in state.projected and point not in state.points:
                            if original_pool + len(state.points) >= budget.limits.repair_proposal_nodes:
                                raise ResourceLimit("exact geometry refinement proposal-node budget exceeded")
                            if len(state.projected) + len(state.points) >= budget.limits.nodes:
                                raise ResourceLimit(
                                    "exact geometry refinement canonical-node budget exceeded"
                                )
                            state.points.update(project_nodes(((point,),), budget))
                        q = state.projected[point] if point in state.projected else state.points[point]
                        candidate_projection: dict[ExactPoint, IntPoint] = {**state.projected, point: q}
                        refined = _subdivide(ring, edge, point, budget)
                        for restore in (True, False):
                            budget.repair_trial()
                            shifted = frozenset(
                                (i, k + int(k >= edge + 1)) if i == owner else (i, k)
                                for i, k in state.omitted
                                if not (restore and (i, k) == (owner, j))
                            )
                            integer = _integer_ring(owner, refined, shifted, candidate_projection, budget)
                            try:
                                contacts((integer,), {0}, budget, only_simple=True)
                                require(
                                    area2(integer, budget) * area2(refined, budget) > 0,
                                    "refinement local orientation",
                                )
                                remaining = _bad_probes(refined, integer, budget)
                            except ResourceLimit:
                                raise
                            except GeometryError:
                                continue
                            # Construction progress only; all whole-curve/topology obligations stay global.
                            restored_index = j + int(j >= edge + 1)
                            if restored_index in remaining or edge + 1 in remaining:
                                continue
                            selected = refined, candidate_projection, shifted
                            break
                        if selected is not None:
                            break
            if selected is None:
                return
            refined, next_projection, next_omitted = selected
            state.adopt(
                next_projection, next_omitted, state.loops[:owner] + (refined,) + state.loops[owner + 1 :]
            )
        else:
            raise ResourceLimit("exact geometry refinement iteration budget exceeded")
    if state.loops == original:
        return
    require(
        all(clean(a, budget) == clean(b, budget) for a, b in zip(original, state.loops, strict=True)),
        "refinement changes complete exact curve",
    )
    budget.repair_trial()
    try:
        candidate = project_boundaries(
            state.loops, source, budget, projected=state.projected, omitted=state.omitted
        )
    except ResourceLimit:
        raise
    except GeometryError:
        return  # A rejected global proposal does not disable the original bounded fallback.
    yield candidate
