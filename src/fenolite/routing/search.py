# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Read-only sparse search on the existing routing world (c0365).

The grid is an explicit algorithmic input, never a fabrication/electrical default.
Only ordinary connection subjects are supported; pairs and critical groups stay atomic.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from math import isqrt
from typing import cast

from fenolite.core.coords import Point
from fenolite.core.units import parse_length
from fenolite.geometry import Location, point_in_ring
from fenolite.model.pairs import net_bases, pair_nets
from fenolite.routing.octilinear import Polyline, World, length, shapes, simplify
from fenolite.routing.protocol import JobSubject, RoutingJob
from fenolite.routing.search_fields import Evaluator, Fields, board_fingerprint
from fenolite.routing.search_grid import SearchResult, State, Stop, astar

DIRECTIONS = ((1, 0), (1, 1), (0, 1), (-1, 1), (-1, 0), (-1, -1), (0, -1), (1, -1))
SEARCH_OPTIONS = ("search", "search-grid", "search-max-states", "search-max-vias")


@dataclass(frozen=True, slots=True)
class Limits:
    """Explicit resource bounds; none is a board manufacturing constraint."""

    grid: int
    max_states: int
    max_vias: int

    def __post_init__(self) -> None:
        for name, value in (
            ("grid", self.grid),
            ("max_states", self.max_states),
            ("max_vias", self.max_vias),
        ):
            if type(value) is not int or value < (0 if name == "max_vias" else 1):
                raise ValueError(f"{name} has no valid search bound")


def options(given: Mapping[str, str]) -> tuple[str, Limits | None]:
    """Strict parsing shared by direct routing jobs and CLI preflight."""
    mode = given.get("search", "off")
    if mode not in ("off", "fallback", "only"):
        raise ValueError("search must be off, fallback or only")
    bounds = SEARCH_OPTIONS[1:]
    if mode == "off":
        if any(key in given for key in bounds):
            raise ValueError("search bounds require search=fallback or search=only")
        return mode, None
    if any(key not in given for key in bounds):
        raise ValueError("search requires explicit search-grid, search-max-states and search-max-vias")
    try:
        grid = parse_length(given["search-grid"], default_unit="mm")
        raw_states, raw_vias = given["search-max-states"], given["search-max-vias"]
        if (
            not raw_states.isascii()
            or not raw_states.isdigit()
            or not raw_vias.isascii()
            or not raw_vias.isdigit()
        ):
            raise ValueError("state and via bounds must be decimal integers")
        limits = Limits(grid, int(raw_states), int(raw_vias))
    except ValueError as exc:
        raise ValueError(f"invalid search bounds: {exc}") from None
    return mode, limits


@dataclass(frozen=True, slots=True)
class Outcome:
    """Complete geometry or an honest reason; diagnostics are not a recommendation."""

    runs: tuple[tuple[str, Polyline], ...] = ()
    vias: tuple[Point, ...] = ()
    reason: str = ""
    stats: SearchResult | None = None


def _direction(a: Point, b: Point) -> int:
    dx, dy = b.x - a.x, b.y - a.y
    return DIRECTIONS.index(((dx > 0) - (dx < 0), (dy > 0) - (dy < 0)))


def _turn(a: int, b: int) -> bool:
    return a < 0 or a == 8 or sum(x * y for x, y in zip(DIRECTIONS[a], DIRECTIONS[b], strict=True)) >= 0


def _cost(points: Polyline) -> int:
    return max(
        1,
        sum(
            isqrt(1_000_000 * ((q.x - p.x) ** 2 + (q.y - p.y) ** 2))
            for p, q in zip(points, points[1:], strict=False)
        ),
    )


def _anchors(at: Point, grid: int) -> tuple[Point, ...]:
    return tuple(
        Point(x, y)
        for x in sorted({at.x // grid * grid, -(-at.x // grid) * grid})
        for y in sorted({at.y // grid * grid, -(-at.y // grid) * grid})
    )


class _Graph:
    def __init__(
        self,
        job: RoutingJob,
        subject: JobSubject,
        world: World,
        limits: Limits,
        rings: tuple[tuple[Point, ...], ...],
        stop: Stop,
    ) -> None:
        self.job, self.subject, self.world, self.limits = job, subject, world, limits
        self.rings, self.stop = rings, stop
        fields = job.extra.get("search_fields")
        self.fields = Evaluator(fields) if isinstance(fields, Fields) else None
        self.allowed = tuple(
            i for i, layer in enumerate(job.layers) if layer in subject.layers and layer not in world.planes
        )
        self.firsts = tuple(i for i in self.allowed if job.layers[i] in subject.a.layers)
        self.lasts = tuple(i for i in self.allowed if job.layers[i] in subject.b.layers)
        self.heads = _anchors(subject.a.at, limits.grid)
        self.tails = _anchors(subject.b.at, limits.grid)
        self.edges: dict[tuple[State, State], Polyline] = {}

    def inside(self, at: Point) -> bool:
        positions = tuple(point_in_ring(at, ring) for ring in self.rings)
        return Location.BOUNDARY not in positions and sum(p is Location.INSIDE for p in positions) % 2 == 1

    def fits(self, layer: int, points: Polyline, width: int, incoming: int = -1) -> bool:
        if self.stop() is not None or not all(self.inside(p) for p in points):
            return False
        if self.fields is not None and not self.fields.allows(
            self.subject.net, self.job.layers[layer], points, width
        ):
            return False
        directions = tuple(_direction(a, b) for a, b in zip(points, points[1:], strict=False))
        if directions and (
            not _turn(incoming, directions[0])
            or any(not _turn(a, b) for a, b in zip(directions, directions[1:], strict=False))
        ):
            return False
        return len(points) < 2 or (
            self.world.fits(self.subject.net, self.job.layers[layer], points, width)
            and self.world.ends_ok(self.subject.net, self.job.layers[layer], points)
        )

    def neighbours(self, state: State) -> tuple[tuple[State, int], ...]:
        at = Point(state.x, state.y)
        found: dict[State, tuple[int, Polyline]] = {}

        def add(there: State, points: Polyline, cost: int | None = None) -> None:
            value = _cost(points) if cost is None else cost
            if cost is None and self.fields is not None:
                value += (
                    1000
                    * self.fields.measure(
                        self.subject.net, self.job.layers[state.layer], points, self.subject.width
                    ).penalty
                )
            previous = found.get(there)

            def key(entry: tuple[int, Polyline]) -> tuple[int, tuple[tuple[int, int], ...]]:
                return entry[0], tuple((p.x, p.y) for p in entry[1])

            if previous is None or key((value, points)) < key(previous):
                found[there] = (value, points)

        if state.direction == -2:
            for anchor in self.heads:
                stubs = shapes(at, anchor) if at != anchor else ((at,),)
                for points in stubs:
                    if self.fits(state.layer, points, self.subject.width):
                        direction = _direction(points[-2], points[-1]) if len(points) > 1 else -1
                        add(State(anchor.x, anchor.y, state.layer, direction, 0), points)
        else:
            if at in self.tails and state.layer in self.lasts:
                end = self.subject.b.at
                stubs = shapes(at, end) if at != end else ((at,),)
                for points in stubs:
                    if self.fits(state.layer, points, self.subject.width, state.direction):
                        add(State(end.x, end.y, state.layer, -3, state.vias), points)
            for direction, (dx, dy) in enumerate(DIRECTIONS):
                there = Point(at.x + dx * self.limits.grid, at.y + dy * self.limits.grid)
                points = (at, there)
                if _turn(state.direction, direction) and self.fits(state.layer, points, self.subject.width):
                    add(State(there.x, there.y, state.layer, direction, state.vias), points)
            s = self.subject
            if (
                state.vias < self.limits.max_vias
                and state.direction != 8
                and 0 < s.via_drill < s.via_diameter
            ):
                probe = (at, Point(at.x + 1, at.y))
                # Through barrel, including inner layers not allowed for signal tracks.
                if all(self.fits(i, probe, s.via_diameter) for i in range(len(self.job.layers))):
                    for layer in self.allowed:
                        if layer != state.layer:
                            add(State(at.x, at.y, layer, 8, state.vias + 1), (), s.via_diameter * 1000)
        for there, (_, points) in found.items():
            self.edges[state, there] = points
        return tuple((there, cost) for there, (cost, _) in sorted(found.items()))

    def run(self) -> Outcome:
        s = self.subject
        result = astar(
            tuple(State(s.a.at.x, s.a.at.y, layer, -2, 0) for layer in self.firsts),
            lambda state: state.direction == -3,
            self.neighbours,
            lambda state: 1000 * max(abs(state.x - s.b.at.x), abs(state.y - s.b.at.y)),
            max_states=self.limits.max_states,
            stop=self.stop,
        )
        if not result.path:
            return Outcome(reason=result.termination, stats=result)
        runs: list[tuple[str, Polyline]] = []
        vias: list[Point] = []
        for a, b in zip(result.path, result.path[1:], strict=False):
            if a.layer != b.layer:
                vias.append(Point(a.x, a.y))
                continue
            points = self.edges[a, b]
            if len(points) < 2:
                continue
            layer = self.job.layers[a.layer]
            if runs and runs[-1][0] == layer and runs[-1][1][-1] == points[0]:
                points = (*runs.pop()[1], *points[1:])
            runs.append((layer, points))
        if not all(self.fits(self.job.layers.index(layer), points, s.width) for layer, points in runs):
            return Outcome(reason="no-room", stats=result)
        return Outcome(tuple((layer, simplify(points)) for layer, points in runs), tuple(vias), stats=result)


def coupled_nets(job: RoutingJob) -> frozenset[str]:
    """Pair membership survives a job selection that omitted the partner or its constraints."""
    names = set(net_bases(net.name for net in job.design.circuit.nets))
    names.update(name for pair in job.pairs for name in (pair.positive, pair.negative))
    ids = {ident for interface in job.design.circuit.interfaces for ident in (pair_nets(interface) or ())}
    names.update(net.name for net in job.design.circuit.nets if net.id in ids)
    return frozenset(names)


def search(
    job: RoutingJob,
    subject: JobSubject,
    world: World,
    limits: Limits,
    *,
    max_length: int,
    stop: Stop = lambda: None,
) -> Outcome:
    """Return one complete path, or an explicit refusal; never mutate the routing world."""
    if subject.kind != "connection" or subject.net in coupled_nets(job):
        return Outcome(reason="search-unsupported")
    fields = job.extra.get("search_fields")
    if fields is not None:
        if (
            not isinstance(fields, Fields)
            or fields.provenance.board != board_fingerprint(job.design)
            or fields.layers != job.layers
        ):
            return Outcome(reason="search-role-stale")
        if any(net == subject.net for net, _ in fields.missing):
            return Outcome(reason="search-role-limit")
    raw = job.extra.get("outline")
    if not isinstance(raw, tuple) or not raw:
        return Outcome(reason="search-geometry")
    for entry in cast(tuple[object, ...], raw):
        if not isinstance(entry, tuple) or len(cast(tuple[object, ...], entry)) < 3:
            return Outcome(reason="search-geometry")
        if not all(isinstance(point, Point) for point in cast(tuple[object, ...], entry)):
            return Outcome(reason="search-geometry")
    rings = cast("tuple[tuple[Point,...],...]", raw)
    graph = _Graph(job, subject, world, limits, rings, stop)
    if not graph.firsts or not graph.lasts:
        return Outcome(reason="no-layer")
    if not graph.inside(subject.a.at) or not graph.inside(subject.b.at):
        return Outcome(reason="search-geometry")
    outcome = graph.run()
    if reason := stop():
        return Outcome(reason=reason, stats=outcome.stats)
    if sum(length(points) for _, points in outcome.runs) > max_length:
        return Outcome(reason="too-long", stats=outcome.stats)
    return outcome
