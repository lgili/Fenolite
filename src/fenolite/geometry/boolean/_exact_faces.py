# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Private exact signed face selection, before integer realization (c0332).

Every halfedge has one owner. Each connected support has its own exterior
cycle, seeded against all original signed segments at a formal positive
infinitesimal displacement. This handles nested disconnected supports without
assuming every component's exterior has zero winding.
"""

from __future__ import annotations

from collections import defaultdict, deque
from collections.abc import Sequence
from dataclasses import dataclass
from fractions import Fraction
from functools import cmp_to_key

from fenolite.geometry.boolean._exact_noding import Budget, ExactPoint, Segment, node_segments
from fenolite.geometry.errors import GeometryError

Ring = tuple[ExactPoint, ...]
Edge = tuple[ExactPoint, ExactPoint]
Current = tuple[int, int]


def require(condition: bool, message: str) -> None:
    if not condition:
        raise GeometryError("exact geometry: " + message)


def sub(a: ExactPoint, b: ExactPoint) -> ExactPoint:
    return a[0] - b[0], a[1] - b[1]


def checked(value: Fraction, bits: int) -> Fraction:
    require(
        max(abs(value.numerator).bit_length(), value.denominator.bit_length()) <= bits,
        "arithmetic bit budget exceeded",
    )
    return value


def cross(a: ExactPoint, b: ExactPoint) -> Fraction:
    return checked(a[0] * b[1] - a[1] * b[0], 256)


def area2(ring: Ring, budget: Budget) -> Fraction:
    result = Fraction(0)
    for i, (a, b) in enumerate(zip(ring, ring[1:] + ring[:1], strict=True)):
        if i % 256 == 0:
            budget.check()
        result = checked(result + a[0] * b[1] - b[0] * a[1], 4096)
    return result


def sign(x: Fraction) -> int:
    return (x > 0) - (x < 0)


def angular(center: ExactPoint, a: ExactPoint, b: ExactPoint) -> int:
    x, y = sub(a, center), sub(b, center)
    first = 0 if x[1] > 0 or (x[1] == 0 and x[0] >= 0) else 1
    second = 0 if y[1] > 0 or (y[1] == 0 and y[0] >= 0) else 1
    if first != second:
        return first - second
    det = cross(x, y)
    require(det != 0 or x == y, "overlapping non-noded directions")
    return -sign(det)


@dataclass(slots=True)
class Frame:
    neighbors: dict[ExactPoint, tuple[ExactPoint, ...]]
    positions: dict[ExactPoint, dict[ExactPoint, int]]
    cycles: list[tuple[Edge, ...]]
    left: dict[Edge, int]
    exteriors: list[int]
    dual: dict[int, list[tuple[int, Current]]]


@dataclass(frozen=True, slots=True)
class ExactSegment:
    a: ExactPoint
    b: ExactPoint
    channel: int


def frames(edges: dict[Edge, Current], budget: Budget) -> Frame:
    adjacent: dict[ExactPoint, set[ExactPoint]] = defaultdict(set)
    divergence: dict[ExactPoint, list[int]] = defaultdict(lambda: [0, 0])
    for (a, b), current in edges.items():
        adjacent[a].add(b)
        adjacent[b].add(a)
        for channel in (0, 1):
            divergence[a][channel] += current[channel]
            divergence[b][channel] -= current[channel]
    require(all(value == [0, 0] for value in divergence.values()), "nonconserved signed current")
    neighbors = {
        p: tuple(sorted(qs, key=cmp_to_key(lambda a, b, p=p: angular(p, a, b)))) for p, qs in adjacent.items()
    }
    positions = {p: {q: i for i, q in enumerate(qs)} for p, qs in neighbors.items()}
    components: list[set[ExactPoint]] = []
    component: dict[ExactPoint, int] = {}
    for start in sorted(adjacent):
        if start in component:
            continue
        todo = [start]
        points: set[ExactPoint] = set()
        identity = len(components)
        while todo:
            if len(points) % 256 == 0:
                budget.check()
            p = todo.pop()
            if p in points:
                continue
            points.add(p)
            component[p] = identity
            todo.extend(q for q in adjacent[p] if q not in points)
        components.append(points)
        budget.check()
    require(2 * len(edges) <= budget.limits.halfedges, "halfedge budget exceeded")
    halves = sorted([e for e in edges] + [(b, a) for a, b in edges])
    left: dict[Edge, int] = {}
    cycles: list[tuple[Edge, ...]] = []
    areas: list[Fraction] = []
    for start in halves:
        if start in left:
            continue
        require(len(cycles) < budget.limits.faces, "face budget exceeded")
        cycle: list[Edge] = []
        current = start
        identity = len(cycles)
        while True:
            require(current not in left, "halfedge owned twice")
            left[current] = identity
            cycle.append(current)
            a, b = current
            current = (b, neighbors[b][(positions[b][a] - 1) % len(neighbors[b])])
            if current == start:
                break
            if len(cycle) % 256 == 0:
                budget.check()
        area = area2(tuple(a for a, _ in cycle), budget)
        require(area != 0, "zero-area face walk")
        cycles.append(tuple(cycle))
        areas.append(area)
    require(len(left) == len(halves), "incomplete halfedge coverage")
    groups: list[list[int]] = [[] for _ in components]
    for i, face_cycle in enumerate(cycles):
        c = component[face_cycle[0][0]]
        require(all(component[a] == c for a, _ in face_cycle), "face crosses components")
        groups[c].append(i)
    exteriors: list[int] = []
    for c, points in enumerate(components):
        edge_count = sum(len(adjacent[p]) for p in points) // 2
        ids = groups[c]
        require(len(points) - edge_count + len(ids) == 2, "Euler identity failed")
        total = Fraction(0)
        for i in ids:
            total = checked(total + areas[i], 4096)
        require(total == 0, "component face areas do not cancel")
        outside = [i for i in ids if areas[i] < 0]
        require(len(outside) == 1, "component exterior not unique")
        exteriors.append(outside[0])
    dual: dict[int, list[tuple[int, Current]]] = defaultdict(list)
    for (a, b), current in edges.items():
        left_face, right_face = left[a, b], left[b, a]
        require(left_face != right_face, "nonzero bridge current")
        dual[left_face].append((right_face, (-current[0], -current[1])))
        dual[right_face].append((left_face, current))
    return Frame(neighbors, positions, cycles, left, exteriors, dict(dual))


def winding(edge: Edge, segments: Sequence[ExactSegment], budget: Budget) -> Current:
    a, b = edge
    m = ((a[0] + b[0]) / 2, (a[1] + b[1]) / 2)
    n = (-(b[1] - a[1]), b[0] - a[0])
    budget.visit(len(segments))
    value = [0, 0]

    def lex(x: Fraction, y: Fraction) -> int:
        return sign(x) if x else sign(y)

    for i, s in enumerate(segments):
        if i % 1024 == 0:
            budget.check()
        sa = lex(s.a[1] - m[1], -n[1])
        sb = lex(s.b[1] - m[1], -n[1])
        up, down = sa <= 0 < sb, sb <= 0 < sa
        if not (up or down):
            continue
        start, end = s.a, s.b
        direction = sub(end, start)
        orientation = lex(cross(direction, sub(m, start)), cross(direction, n))
        require(orientation != 0, "infinitesimal seed remains on source line")
        if up and orientation > 0:
            value[s.channel] += 1
        if down and orientation < 0:
            value[s.channel] -= 1
    return value[0], value[1]


def solve(frame: Frame, segments: Sequence[Segment], budget: Budget) -> dict[int, Current]:
    values: dict[int, Current] = {}
    exact = tuple(
        ExactSegment((Fraction(s.a[0]), Fraction(s.a[1])), (Fraction(s.b[0]), Fraction(s.b[1])), s.channel)
        for s in segments
    )
    for outside in frame.exteriors:
        values[outside] = winding(frame.cycles[outside][0], exact, budget)
        todo = deque([outside])
        while todo:
            face = todo.popleft()
            budget.check()
            for other, delta in frame.dual.get(face, []):
                proposed = (values[face][0] + delta[0], values[face][1] + delta[1])
                if other in values:
                    require(values[other] == proposed, "contradictory face winding")
                else:
                    values[other] = proposed
                    todo.append(other)
    require(len(values) == len(frame.cycles), "unresolved face winding")
    return values


def clean(ring: Ring, budget: Budget) -> Ring:
    current = ring
    while True:
        budget.check()
        dedup = tuple(p for i, p in enumerate(current) if i == 0 or p != current[i - 1])
        if len(dedup) > 1 and dedup[0] == dedup[-1]:
            dedup = dedup[:-1]
        if len(dedup) < 3:
            return dedup
        result = tuple(
            p
            for i, p in enumerate(dedup)
            if cross(sub(p, dedup[i - 1]), sub(dedup[(i + 1) % len(dedup)], p)) != 0
        )
        if result == current:
            return result
        current = result


def split_contacts(ring: Ring, budget: Budget) -> list[Ring]:
    todo = [ring]
    result: list[Ring] = []
    while todo:
        current = todo.pop()
        seen: dict[ExactPoint, int] = {}
        for i, p in enumerate(current):
            if p in seen:
                j = seen[p]
                first, second = current[j:i], current[:j] + current[i:]
                require(len(first) >= 3 and len(second) >= 3, "degenerate contact boundary")
                todo.extend((second, first))
                break
            seen[p] = i
        else:
            result.append(current)
        budget.check()
    return result


def boundaries(frame: Frame, values: dict[int, Current], budget: Budget) -> tuple[Ring, ...]:
    selected = {i: w[0] != 0 and w[1] == 0 for i, w in values.items()}
    edges = {e for e, left in frame.left.items() if selected[left] and not selected[frame.left[e[1], e[0]]]}
    visited: set[Edge] = set()
    loops: list[Ring] = []
    for start in sorted(edges):
        if start in visited:
            continue
        points: list[ExactPoint] = []
        current = start
        while True:
            require(current not in visited, "selected boundary collision")
            visited.add(current)
            a, b = current
            points.append(a)
            following = None
            neighbors = frame.neighbors[b]
            back = frame.positions[b][a]
            for step in range(1, len(neighbors) + 1):
                if step % 256 == 0:
                    budget.check()
                candidate = (b, neighbors[(back - step) % len(neighbors)])
                if candidate in edges:
                    following = candidate
                    break
            if following is None:
                raise GeometryError("exact geometry: open selected boundary")
            current = following
            if current == start:
                break
            if len(points) % 256 == 0:
                budget.check()
        for ring in split_contacts(tuple(points), budget):
            trimmed = clean(ring, budget)
            require(len(trimmed) >= 3 and area2(trimmed, budget) != 0, "exact selected boundary collapse")
            loops.append(trimmed)
    require(visited == edges, "unvisited selected halfedge")
    total = Fraction(0)
    for ring in loops:
        total = checked(total + area2(ring, budget), 4096)
    expected = Fraction(0)
    for i, cycle in enumerate(frame.cycles):
        if selected[i]:
            expected = checked(expected + area2(tuple(a for a, _ in cycle), budget), 4096)
    require(total == expected and total >= 0, "boundary/selected face area mismatch")
    return tuple(loops)


def difference_loops(segments: Sequence[Segment], budget: Budget | None = None) -> tuple[Ring, ...]:
    budget = budget if budget is not None else Budget()
    graph = node_segments(segments, budget)
    edges = {(f.a, f.b): f.current for f in graph.fragments if f.current != (0, 0)}
    if not edges:
        return ()
    budget.stage("faces")
    frame = frames(edges, budget)
    budget.stage("winding")
    values = solve(frame, segments, budget)
    budget.stage("selection")
    return boundaries(frame, values, budget)
