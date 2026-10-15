# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Bounded orthogonal local connections; labelled stubs remain the safe fallback."""

from __future__ import annotations

from dataclasses import replace

from fenolite.core.errors import Issue
from fenolite.schematic.composition import GRID, WIRE_BUDGET, Box, CompositionPlan, Placement, Wire, rotate

Point = tuple[int, int]


def on_segment(point: Point, start: Point, end: Point) -> bool:
    x, y = point
    return (start[0] == end[0] == x and min(start[1], end[1]) <= y <= max(start[1], end[1])) or (
        start[1] == end[1] == y and min(start[0], end[0]) <= x <= max(start[0], end[0])
    )


def intersects_box(start: Point, end: Point, box: Box) -> bool:
    if start[0] == end[0]:
        return (
            box.x0 <= start[0] <= box.x1
            and max(start[1], end[1]) >= box.y0
            and min(start[1], end[1]) <= box.y1
        )
    return (
        box.y0 <= start[1] <= box.y1 and max(start[0], end[0]) >= box.x0 and min(start[0], end[0]) <= box.x1
    )


def segments_intersect(a: Point, b: Point, c: Point, d: Point) -> bool:
    return intersects_box(a, b, Box(min(c[0], d[0]), min(c[1], d[1]), max(c[0], d[0]), max(c[1], d[1])))


def pin_point(placement: Placement, number: str) -> Point:
    pin = next(p for p in placement.unit.pins if p.number == number)
    x, y = rotate(pin.at, placement.rotation // 90_000_000)
    return x + placement.origin[0], y + placement.origin[1]


def paths(start: Point, end: Point) -> tuple[tuple[Point, ...], ...]:
    raw: list[tuple[Point, ...]] = []
    if start[0] == end[0] or start[1] == end[1]:
        raw.append((start, end))
    raw.extend(((start, (start[0], end[1]), end), (start, (end[0], start[1]), end)))
    lanes_x = [(start[0] + end[0]) // (2 * GRID) * GRID]
    lanes_y = [(start[1] + end[1]) // (2 * GRID) * GRID]
    for step in range(1, 9):
        lanes_x.extend((min(start[0], end[0]) - step * GRID, max(start[0], end[0]) + step * GRID))
        lanes_y.extend((min(start[1], end[1]) - step * GRID, max(start[1], end[1]) + step * GRID))
    raw.extend((start, (x, start[1]), (x, end[1]), end) for x in lanes_x)
    raw.extend((start, (start[0], y), (end[0], y), end) for y in lanes_y)
    found = {tuple(p for i, p in enumerate(path) if i == 0 or path[i - 1] != p) for path in raw}
    return tuple(
        sorted(
            found,
            key=lambda p: (
                len(p),
                sum(abs(a[0] - b[0]) + abs(a[1] - b[1]) for a, b in zip(p, p[1:], strict=False)),
                p,
            ),
        )
    )


def route_local(plan: CompositionPlan, *, budget: int = WIRE_BUDGET) -> CompositionPlan:
    nets: dict[tuple[str, str], list[tuple[Placement, str]]] = {}
    for placement in plan.placements:
        for pin in placement.unit.pins:
            if pin.net is not None and not pin.power:
                nets.setdefault((placement.block, pin.net), []).append((placement, pin.number))
    wires: list[Wire] = []
    attempted = 0
    issues = list(plan.issues)
    for (block, net), endpoints in sorted(nets.items()):
        if len(endpoints) < 2:
            continue
        endpoints.sort(key=lambda pair: (pair[0].unit.key, pair[1]))
        reason = "fanout retains labelled stubs"
        if len(endpoints) == 2 and endpoints[0][0].unit.key != endpoints[1][0].unit.key:
            (a, ap), (b, bp) = endpoints
            start, end = pin_point(a, ap), pin_point(b, bp)
            allowed = {(a.unit.key, ap), (b.unit.key, bp)}
            excluded_stubs = {f"{key}/{pin}" for key, pin in allowed}
            obstacles = list(plan.reserved)
            for item in plan.placements:
                obstacles.extend(
                    v.box
                    for v in item.visible
                    if v.kind in ("body", "reference", "value", "net-label", "stub")
                    and not (v.kind == "stub" and v.key in excluded_stubs)
                )
            pins = [
                pin_point(p, pin.number)
                for p in plan.placements
                for pin in p.unit.pins
                if (p.unit.key, pin.number) not in allowed
            ]
            reason = "no safe straight/one-bend/two-bend candidate"
            for candidate in paths(start, end)[: max(0, budget)]:
                attempted += 1
                segments = tuple(zip(candidate, candidate[1:], strict=False))
                if any(not plan.region.contains(Box(p[0], p[1], p[0], p[1])) for p in candidate):
                    continue
                if any(intersects_box(x, y, box) for x, y in segments for box in obstacles):
                    continue
                if any(on_segment(p, x, y) for x, y in segments for p in pins):
                    continue
                if any(
                    segments_intersect(x, y, c, d)
                    for x, y in segments
                    for w in wires
                    for c, d in zip(w.points, w.points[1:], strict=False)
                ):
                    continue
                wires.append(Wire(net, (a.unit.key, ap), (b.unit.key, bp), candidate))
                reason = ""
                break
        if reason:
            where = f"{plan.sheet}/{block}/{net}:" + ",".join(f"{p.unit.key}/{n}" for p, n in endpoints)
            issues.append(
                Issue(
                    "composition.label-fallback",
                    "info",
                    reason,
                    where=where,
                    hint="inspect endpoints in the generated baseline preview; labels retain connectivity",
                )
            )
    return replace(plan, wires=tuple(wires), issues=tuple(issues), connection_candidates=attempted)
