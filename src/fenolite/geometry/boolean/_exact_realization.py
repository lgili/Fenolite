# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Private half-even projection and retained-boundary/whole-face certificates.

The caller applies its existing debris policy to ``Projection.polygons`` and
then submits the result to ``certify``. This module neither imports a backend
nor writes files. A certificate failure always raises GeometryError.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from fractions import Fraction as F
from itertools import chain
from math import gcd

from fenolite.geometry.boolean._exact_contacts import contacts, on, parents
from fenolite.geometry.boolean._exact_distance import boundary_bound
from fenolite.geometry.boolean._exact_faces import Ring, area2, checked, clean, cross, require, sub
from fenolite.geometry.boolean._exact_noding import Budget, ExactPoint, IntPoint, Segment
from fenolite.geometry.polygon import Polygon, normalize_polygons
from fenolite.geometry.predicates import round_point
from fenolite.geometry.vector import Point

IntRing = tuple[IntPoint, ...]
Line = tuple[int, int, int]
Cover = tuple[tuple[Line, tuple[tuple[int, int], ...]], ...]
LineCurrent = tuple[tuple[Line, int, int, int], ...]


def sum_areas(values: Iterable[F], budget: Budget) -> F:
    total = F(0)
    for i, value in enumerate(values):
        if i % 256 == 0:
            budget.check()
        total = checked(total + value, 4096)
    return total


def rational(ring: IntRing) -> Ring:
    return tuple((F(x), F(y)) for x, y in ring)


def ring_key(ring: IntRing) -> IntRing:
    require(bool(ring), "empty boundary key")
    k = ring.index(min(ring))
    return ring[k:] + ring[:k]


def point_ring(ring: Sequence[Point]) -> IntRing:
    return tuple((p.x, p.y) for p in ring)


def _lines(ring: IntRing, budget: Budget) -> dict[Line, list[tuple[int, int]]]:
    lines: dict[Line, list[tuple[int, int]]] = defaultdict(list)
    for i, (a, b) in enumerate(zip(ring, ring[1:] + ring[:1], strict=True)):
        if i % 256 == 0:
            budget.check()
        dx, dy = b[0] - a[0], b[1] - a[1]
        if dx == dy == 0:
            continue
        divisor = gcd(abs(dx), abs(dy))
        u, v = dx // divisor, dy // divisor
        if u < 0 or (u == 0 and v < 0):
            u, v = -u, -v
        lines[u, v, u * a[1] - v * a[0]].append((u * a[0] + v * a[1], u * b[0] + v * b[1]))
    return dict(lines)


def line_cover(ring: IntRing, budget: Budget) -> Cover:
    """Exact point set of a projected closed polyline, including backtracking spikes."""
    result: list[tuple[Line, tuple[tuple[int, int], ...]]] = []
    for line, intervals in sorted(_lines(ring, budget).items()):
        merged: list[tuple[int, int]] = []
        for lo, hi in sorted((min(a, b), max(a, b)) for a, b in intervals):
            if merged and lo <= merged[-1][1]:
                merged[-1] = (merged[-1][0], max(hi, merged[-1][1]))
            else:
                merged.append((lo, hi))
        result.append((line, tuple(merged)))
        budget.check()
    return tuple(result)


def line_current(ring: IntRing, budget: Budget) -> LineCurrent:
    """Oriented local interval currents; zero shoelace area alone cannot prove collapse."""
    result: list[tuple[Line, int, int, int]] = []
    for line, intervals in sorted(_lines(ring, budget).items()):
        events: dict[int, int] = defaultdict(int)
        for a, b in intervals:
            lo, hi = min(a, b), max(a, b)
            direction = 1 if b > a else -1
            events[lo] += direction
            events[hi] -= direction
        current = 0
        previous: int | None = None
        for position, delta in sorted((p, d) for p, d in events.items() if d):
            if previous is not None and position > previous and current:
                result.append((line, previous, position, current))
            current += delta
            previous = position
        require(current == 0, "open signed line current")
        budget.check()
    return tuple(result)


def _half_even(value: F) -> int:
    q, r = divmod(value.numerator, value.denominator)
    return q + int(2 * r > value.denominator or (2 * r == value.denominator and q % 2 != 0))


def projection_bound(nodes: set[ExactPoint], projected: dict[ExactPoint, IntPoint]) -> None:
    require(nodes == projected.keys(), "projection does not cover canonical nodes")
    for p in nodes:
        q = projected[p]
        require(all(type(c) is int for c in q), "projection is not integer")
        dx, dy = F(q[0]) - p[0], F(q[1]) - p[1]
        require(
            abs(dx) <= F(1, 2) and abs(dy) <= F(1, 2) and dx * dx + dy * dy <= F(1, 2),
            "projection exceeds quantization bound",
        )
        require(q == (_half_even(p[0]), _half_even(p[1])), "projection is not prescribed half-even")


@dataclass(frozen=True, slots=True)
class Loss:
    kind: str
    identity: int
    owned_holes: tuple[int, ...]
    exact_area: F
    integer_area: F
    orientation_changed: bool = False


@dataclass(frozen=True, slots=True)
class Certificate:
    canonical_nodes: int
    protected_vertices: int
    local_sign_changes: int
    contact_points: int
    losses: tuple[Loss, ...]


@dataclass(frozen=True, slots=True)
class Projection:
    loops: tuple[Ring, ...]
    projected: dict[ExactPoint, IntPoint]
    integer_loops: tuple[IntRing, ...]
    outers: tuple[int, ...]
    parent: dict[int, int]
    collapsed: frozenset[int]
    source: frozenset[ExactPoint]
    polygons: tuple[Polygon, ...]
    omitted: frozenset[tuple[int, int]] = frozenset()

    def certify(self, result: Sequence[Polygon], tol: int, budget: Budget) -> Certificate:
        require(type(tol) is int and tol >= 0, "debris tolerance must be a nonnegative integer")
        require(tuple(result) == normalize_polygons(result), "policy result is not in normal form")
        require(all(p.area2 > 0 for p in result), "policy keeps a zero-area piece")
        for i, j in self.omitted:
            require(0 <= i < len(self.loops) and 0 <= j < len(self.loops[i]), "invalid omitted node")
            require(any(c.denominator != 1 for c in self.loops[i][j]), "integer boundary node omitted")
        exact_areas = tuple(area2(r, budget) / 2 for r in self.loops)
        integer = tuple(rational(r) for r in self.integer_loops)
        raw_areas = tuple(area2(r, budget) / 2 for r in integer)
        inverted = {i for i in range(len(self.loops)) if exact_areas[i] * raw_areas[i] < 0}
        integer_areas = tuple(
            abs(value) if exact_areas[i] > 0 else -abs(value) for i, value in enumerate(raw_areas)
        )
        keys = {
            ring_key(tuple(reversed(r)) if i in inverted else r): i
            for i, r in enumerate(self.integer_loops)
            if i not in self.collapsed
        }
        retained: set[int] = set()
        for poly in result:
            key = ring_key(point_ring(poly.outer))
            require(key in keys, "policy invents or changes an outer boundary")
            outer = keys[key]
            require(outer in self.outers and outer not in retained, "policy changes outer ownership")
            retained.add(outer)
            for hole in poly.holes:
                key = ring_key(point_ring(hole))
                require(key in keys, "policy invents or changes a hole boundary")
                i = keys[key]
                require(self.parent.get(i) == outer and i not in retained, "policy changes hole ownership")
                retained.add(i)
        require(not retained.intersection(inverted), "retained whole-ring orientation changed")
        floor = tol * tol
        losses: list[Loss] = []
        owned = set(retained)
        for i in self.outers:
            holes = tuple(j for j, owner in self.parent.items() if owner == i)
            exact = sum_areas(chain((exact_areas[i],), (exact_areas[j] for j in holes)), budget)
            net = sum_areas(chain((integer_areas[i],), (integer_areas[j] for j in holes)), budget)
            require(exact >= 0 and net >= 0, "negative piece net area")
            if i in self.collapsed or net < floor:
                require(
                    i not in retained and not retained.intersection(holes), "policy keeps an ineligible piece"
                )
                require(exact < floor and net < floor, "whole-piece loss is not eligible")
                losses.append(
                    Loss(
                        "collapsed-piece" if i in self.collapsed else "debris-piece",
                        i,
                        holes,
                        exact,
                        net,
                        bool(inverted.intersection((i, *holes))),
                    )
                )
                require(not owned.intersection((i, *holes)), "whole-piece ownership overlaps")
                owned.update((i, *holes))
                continue
            require(i in retained, "policy removes a qualified whole piece")
            for j in holes:
                if j in self.collapsed or -integer_areas[j] < floor:
                    require(j not in retained, "policy keeps an ineligible hole")
                    require(
                        0 <= -exact_areas[j] < floor and 0 <= -integer_areas[j] < floor,
                        "whole-hole loss is not eligible",
                    )
                    losses.append(
                        Loss(
                            "collapsed-hole" if j in self.collapsed else "debris-hole",
                            j,
                            (),
                            -exact_areas[j],
                            -integer_areas[j],
                            j in inverted,
                        )
                    )
                    require(j not in owned, "whole-hole ownership overlaps")
                    owned.add(j)
                else:
                    require(j in retained, "policy removes a qualified whole hole")
        require(owned == set(range(len(self.loops))), "uncertified boundary loss")
        for i in retained:
            changed = any(loop == i for loop, _ in self.omitted)
            if not changed:
                raw = tuple(self.projected[p] for p in self.loops[i])
                changed = line_cover(raw, budget) != line_cover(self.integer_loops[i], budget)
            if changed:
                vertices = set(integer[i])
                for p in self.loops[i]:
                    if any(c.denominator != 1 for c in p) or p in vertices:
                        continue
                    budget.visit(len(integer[i]))
                    require(
                        any(
                            on(p, a, b)
                            for a, b in zip(integer[i], integer[i][1:] + integer[i][:1], strict=True)
                        ),
                        "cleanup loses projected boundary points at an integer node",
                    )
                boundary_bound(self.loops[i], integer[i], budget)
        exact_contacts = contacts(self.loops, retained, budget)
        integer_contacts = contacts(integer, retained, budget)
        require(
            all(p in self.projected for p in exact_contacts), "contact is not a canonical projection node"
        )
        expected = {
            (F(self.projected[p][0]), F(self.projected[p][1])): word for p, word in exact_contacts.items()
        }
        require(
            len(expected) == len(exact_contacts) and expected == integer_contacts,
            "retained contact topology changed",
        )
        ids = sorted(retained)
        _, integer_parent = parents(tuple(integer[i] for i in ids), budget)
        require(
            {ids[j]: ids[i] for j, i in integer_parent.items()}
            == {j: i for j, i in self.parent.items() if j in retained},
            "retained parentage changed",
        )
        protected = flips = 0
        for i in retained:
            ring, final = self.loops[i], integer[i]
            positions = {p: j for j, p in enumerate(final)}
            for j, p in enumerate(ring):
                turn = cross(sub(p, ring[j - 1]), sub(ring[(j + 1) % len(ring)], p))
                if p not in self.source or turn == 0:
                    continue
                q = (F(self.projected[p][0]), F(self.projected[p][1]))
                require(q in positions, "protected source vertex missing")
                k = positions[q]
                actual = cross(sub(q, final[k - 1]), sub(final[(k + 1) % len(final)], q))
                require(actual != 0, "protected source turn erased")
                protected += 1
                flips += int((turn > 0) != (actual > 0))
            budget.check()
        return Certificate(len(self.projected), protected, flips, len(integer_contacts), tuple(losses))


def project_nodes(loops: Sequence[Ring], budget: Budget) -> dict[ExactPoint, IntPoint]:
    nodes = {p for ring in loops for p in ring}
    projected: dict[ExactPoint, IntPoint] = {}
    for i, p in enumerate(sorted(nodes)):
        if i % 256 == 0:
            budget.check()
        q = round_point(*p)
        projected[p] = (q.x, q.y)
    projection_bound(nodes, projected)
    return projected


def project_boundaries(
    loops: Sequence[Ring],
    source: Sequence[Segment],
    budget: Budget,
    *,
    projected: dict[ExactPoint, IntPoint] | None = None,
    omitted: frozenset[tuple[int, int]] = frozenset(),
) -> Projection:
    loops = tuple(loops)
    projected = project_nodes(loops, budget) if projected is None else projected
    projection_bound({p for ring in loops for p in ring}, projected)
    for i, j in omitted:
        require(0 <= i < len(loops) and 0 <= j < len(loops[i]), "invalid omitted node")
        require(any(c.denominator != 1 for c in loops[i][j]), "integer boundary node omitted")
    raw = tuple(
        tuple(projected[p] for j, p in enumerate(ring) if (i, j) not in omitted)
        for i, ring in enumerate(loops)
    )
    integer = tuple(tuple((int(x), int(y)) for x, y in clean(rational(r), budget)) for r in raw)
    exact_integer = tuple(rational(r) for r in integer)
    areas = tuple(area2(r, budget) for r in exact_integer)
    collapsed: set[int] = set()
    for i, ring in enumerate(integer):
        require(
            line_current(raw[i], budget) == line_current(ring, budget),
            "cleanup changes signed boundary current",
        )
        if len(ring) < 3 or areas[i] == 0:
            require(not line_current(raw[i], budget), "zero area does not prove collapsed winding")
            collapsed.add(i)
    live = set(range(len(loops))) - collapsed
    contacts(exact_integer, live, budget, only_simple=True)
    outers, parent = parents(loops, budget)
    polys: list[Polygon] = []
    for i in outers:
        holes = tuple(j for j, owner in parent.items() if owner == i)
        if i in collapsed:
            require(all(j in collapsed for j in holes), "collapsed outer owns a live hole")
            continue
        require(
            sum_areas(chain((abs(areas[i]),), (-abs(areas[j]) for j in holes)), budget) >= 0,
            "negative projected piece net area",
        )
        polys.append(
            Polygon(
                tuple(Point(*p) for p in integer[i]),
                tuple(tuple(Point(*p) for p in integer[j]) for j in holes if j not in collapsed),
            )
        )
    normalized = normalize_polygons(polys)
    actual = [ring_key(point_ring(ring)) for poly in normalized for ring in poly.rings()]
    expected = [
        ring_key(tuple(reversed(integer[i])) if area2(loops[i], budget) * areas[i] < 0 else integer[i])
        for i in live
    ]
    require(
        len(actual) == len(expected) == len(set(expected)) and set(actual) == set(expected),
        "normalization changes projected boundaries",
    )
    return Projection(
        loops,
        projected,
        integer,
        outers,
        parent,
        frozenset(collapsed),
        frozenset((F(c[0]), F(c[1])) for s in source for c in (s.a, s.b)),
        normalized,
        omitted,
    )
