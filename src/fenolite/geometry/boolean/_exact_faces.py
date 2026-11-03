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
from math import gcd, lcm

from fenolite.geometry.boolean._exact_noding import Budget, ExactPoint, Segment, node_segments
from fenolite.geometry.boolean._exact_seed_index import ClosedYIndex
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


def _face_sign(ring: Ring, budget: Budget) -> int:
    counts: dict[ExactPoint, int] = {}
    for point in ring:
        budget.visit(1)
        for coordinate in point:
            budget.coordinate(coordinate)
        require(point in counts or len(counts) < budget.limits.nodes, "face sign point budget exceeded")
        counts[point] = counts.get(point, 0) + 1
    anchor = min(counts, key=lambda point: (-counts[point], point))
    lower = upper = 0
    positive = negative = False
    for a, b in zip(ring, ring[1:] + ring[:1], strict=True):
        budget.visit(1)
        a, b = sub(a, anchor), sub(b, anchor)
        term = checked(a[0] * b[1] - b[0] * a[1], 4096)
        positive |= term > 0
        negative |= term < 0
        scaled = term.numerator * (1 << 32)
        require(abs(scaled).bit_length() <= 4096, "face sign product bit budget exceeded")
        q, remainder = divmod(scaled, term.denominator)
        lower += q
        upper += q + bool(remainder)
        require(
            max(abs(lower).bit_length(), abs(upper).bit_length()) <= 4096, "face sign sum bit budget exceeded"
        )
    if lower > 0 or (positive and not negative):
        return 1
    if upper < 0 or (negative and not positive):
        return -1
    require(not positive and not negative, "face area sign certificate unresolved")
    return 0


def _face_area(ring: Ring, budget: Budget) -> tuple[Fraction | None, int]:
    """None denotes a proven sign only; strict area2 and Loss areas stay unchanged."""
    require(len(ring) <= budget.limits.halfedges, "face area walk budget exceeded")
    total = Fraction(0)
    for i, (a, b) in enumerate(zip(ring, ring[1:] + ring[:1], strict=True)):
        if i % 256 == 0:
            budget.check()
        total += checked(a[0] * b[1] - b[0] * a[1], 4096)
        if max(abs(total.numerator).bit_length(), total.denominator.bit_length()) > 4096:
            return None, _face_sign(ring, budget)
    return total, sign(total)


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
    areas: list[Fraction | None] = []
    directions: list[int] = []
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
        area, direction = _face_area(tuple(a for a, _ in cycle), budget)
        require(direction != 0, "zero-area face walk")
        cycles.append(tuple(cycle))
        areas.append(area)
        directions.append(direction)
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
        values = tuple(value for i in ids if (value := areas[i]) is not None)
        total = global_area_sum(values, budget) if len(values) == len(ids) else None
        if total is None:
            _component_current_identity((), tuple(cycles[i] for i in ids), budget)
        else:
            require(total == 0, "component face areas do not cancel")
        outside = [i for i in ids if directions[i] < 0]
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
    budget.check()
    # Keep the original exact producer whenever its complete scan fits. This
    # avoids imposing tree storage on previously affordable connected inputs.
    index = (
        ClosedYIndex(segments, budget)
        if len(segments) * len(frame.exteriors) > budget.remaining_visits
        else None
    )
    for outside in frame.exteriors:
        edge = frame.cycles[outside][0]
        y = (edge[0][1] + edge[1][1]) / 2
        selected = exact if index is None else tuple(exact[i] for i in index.query(y))
        values[outside] = winding(edge, selected, budget)
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
    _area_identity(frame, tuple(loops), selected, budget)
    return tuple(loops)


def global_area_sum(areas: Sequence[Fraction], budget: Budget) -> Fraction | None:
    """Only a too-wide GLOBAL sum requests the alternative exact certificate."""
    total = Fraction(0)
    for value in areas:
        budget.check()
        total += value
        if max(abs(total.numerator).bit_length(), total.denominator.bit_length()) > 4096:
            return None
    return total


def _component_current_identity(
    loops: Sequence[Ring], cycles: Sequence[Sequence[Edge]], budget: Budget
) -> None:
    """Exact finite oriented interval currents, independent of a summed denominator."""
    balances: dict[tuple[tuple[int, int, int], ExactPoint], int] = {}

    def add(a: ExactPoint, b: ExactPoint, direction: int) -> None:
        budget.visit(1)
        for point in (a, b):
            for coordinate in point:
                budget.coordinate(coordinate)
        require(a != b, "zero current edge")
        coefficients = (a[1] - b[1], b[0] - a[0], a[0] * b[1] - b[0] * a[1])
        common = lcm(*(value.denominator for value in coefficients))
        require(common.bit_length() <= 4096, "current line denominator bit budget exceeded")
        integers = tuple(value.numerator * (common // value.denominator) for value in coefficients)
        require(
            max(abs(value).bit_length() for value in integers) <= 4096, "current line bit budget exceeded"
        )
        divisor = gcd(*integers)
        sign = 1 if next(value for value in integers if value) > 0 else -1
        line = (sign * integers[0] // divisor, sign * integers[1] // divisor, sign * integers[2] // divisor)
        for point, delta in ((a, direction), (b, -direction)):
            budget.visit(1)
            key = (line, point)
            value = balances.get(key, 0) + delta
            if value:
                require(
                    key in balances or len(balances) < budget.limits.nodes, "current endpoint budget exceeded"
                )
                require(abs(value).bit_length() <= 4096, "current count bit budget exceeded")
                balances[key] = value
            else:
                balances.pop(key, None)

    for ring in loops:
        for a, b in zip(ring, ring[1:] + ring[:1], strict=True):
            add(a, b, 1)
    for cycle in cycles:
        for a, b in cycle:
            add(a, b, -1)
    require(not balances, "component boundary/selected face current mismatch")


def _area_identity(frame: Frame, loops: Sequence[Ring], selected: dict[int, bool], budget: Budget) -> None:
    require(len(loops) <= budget.limits.halfedges, "area loop budget exceeded")
    require(len(frame.cycles) <= budget.limits.faces, "area component face budget exceeded")
    loop_areas = tuple(area2(ring, budget) for ring in loops)
    face_areas = {
        i: area2(tuple(a for a, _ in cycle), budget) for i, cycle in enumerate(frame.cycles) if selected[i]
    }
    total = global_area_sum(loop_areas, budget)
    expected = global_area_sum(tuple(face_areas.values()), budget)
    if total is not None and expected is not None:
        require(total == expected and total >= 0, "boundary/selected face area mismatch")
        return
    # Finite additivity permits exact equality component by component, without
    # constructing the product denominator across independent nested supports.
    require(len(frame.cycles) <= budget.limits.faces, "area component face budget exceeded")
    components: dict[int, int] = {}
    points: dict[ExactPoint, int] = {}
    for start in range(len(frame.cycles)):
        if start in components:
            continue
        owner = start
        todo = [start]
        pending = {start}
        while todo:
            budget.visit(1)
            face = todo.pop()
            pending.remove(face)
            require(face not in components and 0 <= face < len(frame.cycles), "invalid area component face")
            components[face] = owner
            for a, _ in frame.cycles[face]:
                budget.visit(1)
                require(a not in points or points[a] == owner, "ambiguous area point ownership")
                require(a in points or len(points) < budget.limits.nodes, "area point budget exceeded")
                points[a] = owner
            for other, _ in frame.dual.get(face, ()):
                budget.visit(1)
                require(0 <= other < len(frame.cycles), "invalid area dual owner")
                if other in components:
                    require(components[other] == owner, "conflicting area component")
                elif other not in pending:
                    require(len(todo) < budget.limits.faces, "area component stack budget exceeded")
                    pending.add(other)
                    todo.append(other)
    require(set(components) == set(range(len(frame.cycles))), "incomplete area component coverage")
    totals: dict[int, list[Fraction]] = defaultdict(list)
    component_loops: dict[int, list[Ring]] = defaultdict(list)
    for ring, area in zip(loops, loop_areas, strict=True):
        budget.visit(1)
        require(bool(ring) and ring[0] in points, "unbound area loop")
        owner = points[ring[0]]
        for point in ring:
            budget.visit(1)
            require(points.get(point) == owner, "ambiguous area loop ownership")
        totals[owner].append(area)
        component_loops[owner].append(ring)
    targets: dict[int, list[Fraction]] = defaultdict(list)
    component_cycles: dict[int, list[Sequence[Edge]]] = defaultdict(list)
    for face, area in face_areas.items():
        budget.visit(1)
        owner = components[face]
        targets[owner].append(area)
        component_cycles[owner].append(frame.cycles[face])
    owners = set(components.values())
    lower = upper = 0
    for owner in sorted(owners):
        budget.visit(1)
        terms = totals.get(owner, [])
        value = global_area_sum(terms, budget)
        target = global_area_sum(targets.get(owner, []), budget)
        if value is None or target is None:
            _component_current_identity(
                component_loops.get(owner, []), component_cycles.get(owner, []), budget
            )
        else:
            require(value == target, "component boundary/selected face area mismatch")
            terms = [value]
        # Directed integer enclosure is a logical sign proof, NOT a tolerance.
        # Negative hole components remain signed and exterior baselines intact.
        for term in terms:
            budget.visit(1)
            scaled = term.numerator * (1 << 32)
            require(abs(scaled).bit_length() <= 4096, "area enclosure bit budget exceeded")
            q, remainder = divmod(scaled, term.denominator)
            lower += q
            upper += q + bool(remainder)
            require(
                max(abs(lower).bit_length(), abs(upper).bit_length()) <= 4096, "area sum bit budget exceeded"
            )
    require(lower >= 0, "global area nonnegative certificate unresolved")


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
