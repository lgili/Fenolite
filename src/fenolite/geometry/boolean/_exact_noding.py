# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Private conservative indexing and exact signed edge splitting (c0332).

Closed AABBs include endpoint contacts. Rational intersections never snap to a
grid. Multiplicity and every source-edge direction survive coincident edges,
including edges whose total current cancels. There is no process-global state.
"""

from __future__ import annotations

import time
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from fractions import Fraction
from math import ceil, floor

from fenolite.geometry.boolean.base import COORD_LIMIT
from fenolite.geometry.errors import OUT_OF_RANGE, GeometryError
from fenolite.geometry.index import SpatialIndex
from fenolite.geometry.shapes import BBox


class Q(Fraction):
    """A node coordinate: a ``Fraction`` whose hash is computed once and whose comparisons with another
    ``Q`` or an ``int`` skip the generic numeric dispatch. Its value, hash and order are the Fraction's."""

    __slots__ = ("_hash",)

    def __hash__(self) -> int:
        try:
            return self._hash
        except AttributeError:
            value = self._hash = Fraction.__hash__(self)
            return value

    def __eq__(self, other: object) -> bool:
        if type(other) is Q:
            return self.numerator == other.numerator and self.denominator == other.denominator
        if type(other) is int:
            return self.denominator == 1 and self.numerator == other
        return Fraction.__eq__(self, other)

    def __lt__(self, other: object) -> bool:  # pyright: ignore[reportIncompatibleMethodOverride]
        if type(other) is Q:
            return self.numerator * other.denominator < other.numerator * self.denominator
        return bool(Fraction.__lt__(self, other))  # pyright: ignore[reportArgumentType]

    def __gt__(self, other: object) -> bool:  # pyright: ignore[reportIncompatibleMethodOverride]
        if type(other) is Q:
            return self.numerator * other.denominator > other.numerator * self.denominator
        return bool(Fraction.__gt__(self, other))  # pyright: ignore[reportArgumentType]

    def __le__(self, other: object) -> bool:  # pyright: ignore[reportIncompatibleMethodOverride]
        if type(other) is Q:
            return self.numerator * other.denominator <= other.numerator * self.denominator
        return bool(Fraction.__le__(self, other))  # pyright: ignore[reportArgumentType]

    def __ge__(self, other: object) -> bool:  # pyright: ignore[reportIncompatibleMethodOverride]
        if type(other) is Q:
            return self.numerator * other.denominator >= other.numerator * self.denominator
        return bool(Fraction.__ge__(self, other))  # pyright: ignore[reportArgumentType]


def _q(value: Fraction | int) -> Q:
    result = object.__new__(Q)
    if type(value) is int:
        result._numerator, result._denominator = value, 1  # pyright: ignore[reportAttributeAccessIssue]
    else:
        result._numerator, result._denominator = value.numerator, value.denominator  # pyright: ignore[reportAttributeAccessIssue]
    return result


IntPoint = tuple[int, int]
ExactPoint = tuple[Fraction, Fraction]
SourcePoint = tuple[int | Fraction, int | Fraction]


class ResourceLimit(GeometryError):
    """A per-operation bound, still using the existing geometry/FEN-3005 error."""


@dataclass(frozen=True, slots=True)
class Limits:
    """Deterministic storage/work caps; deadlines bound the remaining arithmetic."""

    # Explicit input coverage: min(nodes, fragments, halfedges // 2, incidences // 2).
    # All downstream work/storage/deadline caps still apply independently.
    input_edges: int = 100_000
    comparisons: int = 1_000_000
    candidates: int = 250_000
    nodes: int = 100_000
    fragments: int = 100_000
    incidences: int = 1_000_000
    coordinate_bits: int = 256
    halfedges: int = 200_000
    faces: int = 100_000
    winding_visits: int = 10_000_000
    repair_nodes: int = 16
    repair_proposal_nodes: int = 256
    repair_candidates: int = 4096
    distance_predicates: int = 1_000_000
    distance_intervals: int = 16_384
    distance_depth: int = 32
    distance_bits: int = 1024
    total_seconds: int = 240
    stage_seconds: int = 120


@dataclass(slots=True)
class Budget:
    limits: Limits = field(default_factory=Limits)
    clock: Callable[[], float] = time.monotonic
    _started: float = field(init=False)
    _stage_started: float = field(init=False)
    _stage: str = field(default="start", init=False)
    _visits: int = field(default=0, init=False)
    _distance_predicates: int = field(default=0, init=False)
    _distance_intervals: int = field(default=0, init=False)
    _repair_trials: int = field(default=0, init=False)

    def __post_init__(self) -> None:
        self._started = self._stage_started = self.clock()

    def check(self) -> None:
        now = self.clock()
        if (
            now - self._started > self.limits.total_seconds
            or now - self._stage_started > self.limits.stage_seconds
        ):
            raise ResourceLimit(f"exact geometry deadline exceeded during {self._stage}")

    def stage(self, name: str) -> None:
        self.check()
        self._stage = name
        self._stage_started = self.clock()

    def coordinate(self, value: Fraction) -> None:
        if (
            max(abs(value.numerator).bit_length(), value.denominator.bit_length())
            > self.limits.coordinate_bits
        ):
            raise ResourceLimit("exact geometry coordinate bit budget exceeded")

    @property
    def remaining_visits(self) -> int:
        return self.limits.winding_visits - self._visits

    def visit(self, count: int) -> None:
        self._visits += count
        if self._visits > self.limits.winding_visits:
            raise ResourceLimit("exact geometry winding visit budget exceeded")
        self.check()

    def distance_value(self, value: Fraction) -> Fraction:
        if max(abs(value.numerator).bit_length(), value.denominator.bit_length()) > self.limits.distance_bits:
            raise ResourceLimit("exact geometry distance bit budget exceeded")
        return value

    def distance_probe(self) -> None:
        self._distance_predicates += 1
        if self._distance_predicates > self.limits.distance_predicates:
            raise ResourceLimit("exact geometry distance predicate budget exceeded")
        if self._distance_predicates % 256 == 0:
            self.check()

    def distance_interval(self) -> None:
        self._distance_intervals += 1
        if self._distance_intervals > self.limits.distance_intervals:
            raise ResourceLimit("exact geometry distance interval budget exceeded")

    def repair_trial(self) -> None:
        self._repair_trials += 1
        if self._repair_trials > self.limits.repair_candidates:
            raise ResourceLimit("exact geometry repair candidate budget exceeded")
        self.check()


@dataclass(frozen=True, slots=True)
class Segment:
    """A signed source edge; its ends are integers, or rationals where a caller clipped it exactly."""

    a: SourcePoint
    b: SourcePoint
    channel: int


@dataclass(frozen=True, slots=True)
class Fragment:
    a: ExactPoint
    b: ExactPoint
    current: tuple[int, int]
    provenance: tuple[tuple[int, int], ...]


@dataclass(frozen=True, slots=True)
class NodeGraph:
    fragments: tuple[Fragment, ...]
    nodes: int
    candidate_pairs: int
    intersecting_pairs: int


def _validate(segments: Sequence[Segment], budget: Budget, edge_limit: int) -> None:
    if len(segments) > edge_limit:
        raise GeometryError("exact geometry input-edge budget exceeded")
    for s in segments:
        if type(s.channel) is not int or s.channel not in (0, 1):
            raise GeometryError("exact geometry requires operand channel 0 or 1")
        for p in (s.a, s.b):
            if any(type(c) is not int and type(c) is not Fraction for c in p):
                raise GeometryError("exact geometry requires integer or Fraction input coordinates")
            if any(abs(c) > COORD_LIMIT for c in p):
                raise GeometryError("exact geometry input outside coordinate domain", code=OUT_OF_RANGE)
            for c in p:
                if isinstance(c, int):  # the numerator of Fraction(c), over denominator 1
                    if abs(c).bit_length() > budget.limits.coordinate_bits:
                        raise ResourceLimit("exact geometry coordinate bit budget exceeded")
                else:
                    budget.coordinate(c)


def candidate_pairs(
    segments: Sequence[Segment], budget: Budget, *, edge_limit: int | None = None, start_stage: bool = True
) -> tuple[tuple[int, int], ...]:
    """Every pair of overlapping closed AABBs, with bounded integer-only work."""
    _validate(segments, budget, budget.limits.input_edges if edge_limit is None else edge_limit)
    if start_stage:
        budget.stage("index")
    level = len(segments)
    tree_nodes = 0
    while level:
        level = (level + 3) // 4
        tree_nodes += level
        if tree_nodes > budget.limits.nodes:
            raise GeometryError("exact geometry tree-node storage budget exceeded")
        if level == 1:
            break
    # Closed integer boxes; a rational endpoint widens its box outward, which only over-includes.
    index = SpatialIndex[int].build(
        (
            (
                BBox(
                    floor(min(s.a[0], s.b[0])),
                    floor(min(s.a[1], s.b[1])),
                    ceil(max(s.a[0], s.b[0])),
                    ceil(max(s.a[1], s.b[1])),
                ),
                i,
            )
            for i, s in enumerate(segments)
        ),
        capacity=4,
    )
    budget.check()
    comparisons = 0

    def visit() -> None:
        nonlocal comparisons
        comparisons += 1
        if comparisons > budget.limits.comparisons:
            raise GeometryError("exact geometry index-comparison budget exceeded")
        if comparisons % 1024 == 0:
            budget.check()

    def reserve(count: int) -> None:
        if count > budget.limits.nodes:
            raise GeometryError("exact geometry index-stack budget exceeded")
        budget.check()

    result: list[tuple[int, int]] = []
    for i, j in index._join_pairs(visit, reserve):  # pyright: ignore[reportPrivateUsage]
        if len(result) >= budget.limits.candidates:
            raise GeometryError("exact geometry candidate-pair budget exceeded")
        result.append((i, j))
    ordered = tuple(sorted(result))
    budget.check()
    return ordered


def _on(p: SourcePoint, s: Segment) -> bool:
    return (
        (p[0] - s.a[0]) * (s.b[1] - s.a[1]) == (p[1] - s.a[1]) * (s.b[0] - s.a[0])
        and min(s.a[0], s.b[0]) <= p[0] <= max(s.a[0], s.b[0])
        and min(s.a[1], s.b[1]) <= p[1] <= max(s.a[1], s.b[1])
    )


def _hits(s: Segment, t: Segment) -> set[ExactPoint]:
    rx, ry = s.b[0] - s.a[0], s.b[1] - s.a[1]
    ux, uy = t.b[0] - t.a[0], t.b[1] - t.a[1]
    det = rx * uy - ry * ux
    if det:
        dx, dy = t.a[0] - s.a[0], t.a[1] - s.a[1]
        first = Fraction(dx * uy - dy * ux, det)
        second = Fraction(dx * ry - dy * rx, det)
        if 0 <= first <= 1 and 0 <= second <= 1:
            return {(Fraction(s.a[0]) + first * rx, Fraction(s.a[1]) + first * ry)}
        return set()
    return {(Fraction(p[0]), Fraction(p[1])) for p in (s.a, s.b, t.a, t.b) if _on(p, s) and _on(p, t)}


def node_segments(segments: Sequence[Segment], budget: Budget | None = None) -> NodeGraph:
    """Split the indexed arrangement, retaining signed multiplicity and provenance."""
    budget = budget if budget is not None else Budget()
    pairs = candidate_pairs(segments, budget)
    budget.stage("noding")
    # Every node is one shared tuple of ``Q`` coordinates: later dictionaries hash each coordinate once.
    canonical: dict[ExactPoint, ExactPoint] = {}

    def node(p: SourcePoint) -> ExactPoint:
        found = canonical.get(p)  # pyright: ignore[reportArgumentType]
        if found is None:
            found = (_q(p[0]), _q(p[1]))
            canonical[found] = found
        return found

    cuts: list[set[ExactPoint]] = [{node(s.a), node(s.b)} for s in segments]
    incidence_count = sum(map(len, cuts))
    if incidence_count > budget.limits.incidences:
        raise GeometryError("exact geometry cut-incidence budget exceeded")
    hits_count = 0
    for k, (i, j) in enumerate(pairs):
        if k % 1024 == 0:
            budget.check()
        hits = _hits(segments[i], segments[j])
        if hits:
            hits_count += 1
            for hit in hits:
                budget.coordinate(hit[0])
                budget.coordinate(hit[1])
                q = node(hit)
                for source in (i, j):
                    if q not in cuts[source]:
                        cuts[source].add(q)
                        incidence_count += 1
            if incidence_count > budget.limits.incidences:
                raise GeometryError("exact geometry cut-incidence budget exceeded")
    nodes: set[ExactPoint] = set()
    counts: dict[tuple[ExactPoint, ExactPoint], list[int]] = {}
    provenance: dict[tuple[ExactPoint, ExactPoint], list[tuple[int, int]]] = {}
    for i, (s, points) in enumerate(zip(segments, cuts, strict=True)):
        if i % 256 == 0:
            budget.check()
        nodes.update(points)
        if len(nodes) > budget.limits.nodes:
            raise GeometryError("exact geometry node budget exceeded")
        if s.a == s.b:
            continue
        direction = 1 if s.a < s.b else -1
        ordered = sorted(points)
        for a, b in zip(ordered, ordered[1:], strict=False):
            key = (a, b)
            if key not in counts:
                if len(counts) >= budget.limits.fragments:
                    raise GeometryError("exact geometry fragment budget exceeded")
                counts[key] = [0, 0]
                provenance[key] = []
            counts[key][s.channel] += direction
            provenance[key].append((i, direction))
    budget.check()
    return NodeGraph(
        tuple(
            Fragment(a, b, (counts[a, b][0], counts[a, b][1]), tuple(provenance[a, b]))
            for a, b in sorted(counts)
        ),
        len(nodes),
        len(pairs),
        hits_count,
    )
