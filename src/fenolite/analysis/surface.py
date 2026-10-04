# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The shortest path along the surface of a board between two conductors (capability board-analyses,
"Creepage on the board surface"; definitions and limits: ``docs/analyses.md``).

The surface is the two outer faces inside the outline, less the cut-outs, joined by a wall of the board
thickness along every boundary edge. A path is a chain of legs: a straight segment on one face that stays
on the board, a wall drop at a boundary vertex, or a wall crossing through the interior of one boundary
edge, straight in the plane that unfolds the two faces and the wall. Paths bend only at boundary vertices
and meet a conductor at the point of a core piece nearest to the other end of the leg (``H-G-AN-PATH``).

Whether a leg stays on the board is decided exactly: rational points are scaled to integers and given to
the kernel's ``classify_segments`` and ``point_in_ring``. A length is a sum of rounded-down square roots,
each scaled by ``2**SCALE_BITS`` per nanometre, so the reported integer is below the length of the path
by less than 2 nm. The direction across a wall uses a unit normal rounded at ``2**-NORMAL_BITS``.

Copper does not block a leg; holes, solder mask, components and copper of other nets are ignored.
"""

from __future__ import annotations

import heapq
from collections.abc import Sequence
from dataclasses import dataclass
from fractions import Fraction
from math import ceil, floor, lcm
from typing import Literal

from fenolite.analysis.boundary import BoardBoundary
from fenolite.core.coords import Point
from fenolite.geometry import (
    Location,
    SegmentRelation,
    Thick,
    area2,
    classify_segments,
    dist2_segment_segment,
    floor_sqrt,
    point_in_ring,
    round_point,
)

Face = Literal["top", "bottom"]
FACES: tuple[Face, Face] = ("top", "bottom")
SCALE_BITS = 20
NORMAL_BITS = 64
_ONE = 1 << NORMAL_BITS
_Q = tuple[Fraction, Fraction]
_Piece = tuple[Point, Point]
_Stop = tuple[_Q, Face]
_Entry = tuple[int, _Piece, int, int, int, int, int]


@dataclass(frozen=True, slots=True)
class Terminal:
    """A conductor on a face: a thick shape, and the band of its approximation."""

    shape: Thick
    face: Face
    band: int = 0


@dataclass(frozen=True, slots=True)
class SurfacePath:
    """A shortest surface path: its ``length`` in nanometres (the path's length ``d`` satisfies
    ``length ≤ d < length + 2`` on a boundary without curved edges), ``band`` (the boundary's band per
    bend, plus the bands of the two conductors), the ``points`` with their faces, and the indices of the
    two terminals it joins."""

    length: int
    band: int
    points: tuple[tuple[Point, Face], ...]
    ends: tuple[int, int] = (0, 0)


# --- exact helpers --------------------------------------------------------------------------------


def _q(point: Point) -> _Q:
    return Fraction(point.x), Fraction(point.y)


def _pieces(shape: Thick) -> tuple[_Piece, ...]:
    core = shape.core
    if len(core) == 1:
        return ((core[0], core[0]),)
    if shape.filled:
        return tuple((core[i], core[(i + 1) % len(core)]) for i in range(len(core)))
    return tuple((core[i], core[i + 1]) for i in range(len(core) - 1))


def _nearest(p: _Q, a: _Q, b: _Q) -> _Q:
    """The point of the closed segment ``a–b`` nearest to ``p``."""
    dx, dy = b[0] - a[0], b[1] - a[1]
    length2 = dx * dx + dy * dy
    if length2 == 0:
        return a
    t = ((p[0] - a[0]) * dx + (p[1] - a[1]) * dy) / length2
    t = min(max(t, Fraction(0)), Fraction(1))
    return a[0] + t * dx, a[1] + t * dy


def _dist2(p: _Q, q: _Q) -> Fraction:
    dx, dy = p[0] - q[0], p[1] - q[1]
    return dx * dx + dy * dy


def _cross(o: _Q, a: _Q, b: _Q) -> Fraction:
    return (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0])


def _meet(a: _Q, b: _Q, c: _Q, d: _Q) -> _Q | None:
    """A common point of the closed segments ``a–b`` and ``c–d``, when their interiors cross."""
    d1, d2 = _cross(a, b, c), _cross(a, b, d)
    d3, d4 = _cross(c, d, a), _cross(c, d, b)
    if d1 * d2 < 0 and d3 * d4 < 0:
        t = d3 / (d3 - d4)
        return a[0] + t * (b[0] - a[0]), a[1] + t * (b[1] - a[1])
    return None


def _closest(a: _Q, b: _Q, c: _Q, d: _Q) -> tuple[Fraction, _Q, _Q]:
    """The squared distance of the closed segments ``a–b`` and ``c–d`` and a closest pair of points."""
    common = _meet(a, b, c, d)
    if common is not None:
        return Fraction(0), common, common
    best: tuple[Fraction, _Q, _Q] | None = None
    for p, on_first in ((a, True), (b, True), (c, False), (d, False)):
        q = _nearest(p, c, d) if on_first else _nearest(p, a, b)
        found = (_dist2(p, q), p, q) if on_first else (_dist2(p, q), q, p)
        if best is None or found[0] < best[0]:
            best = found
    assert best is not None
    return best


def _scaled(points: Sequence[_Q]) -> tuple[int, list[Point]]:
    """The points as integer ``Point``s after multiplying by the least common denominator."""
    scale = 1
    for x, y in points:
        scale = lcm(scale, x.denominator, y.denominator)
    return scale, [Point(int(x * scale), int(y * scale)) for x, y in points]


def _weight(dist2: Fraction, half_widths2: int) -> int:
    """``dist − half_widths2 / 2`` scaled by ``2**SCALE_BITS``, rounded down and not below 0."""
    scaled = floor_sqrt(dist2 * (1 << (2 * SCALE_BITS))) - (half_widths2 << (SCALE_BITS - 1))
    return max(0, scaled)


# --- the board ------------------------------------------------------------------------------------


class _Board:
    """The boundary in the form the search needs: rings with the material on the left of every edge, the
    edges with their boxes, and the vertices."""

    def __init__(self, boundary: BoardBoundary) -> None:
        self.outer = boundary.outer
        self.cutouts = boundary.cutouts
        self.thickness = boundary.thickness
        self.band = boundary.band
        rings: list[tuple[Point, ...]] = []
        if self.outer:
            rings.append(self.outer if area2(self.outer) > 0 else tuple(reversed(self.outer)))
        for ring in self.cutouts:
            rings.append(ring if area2(ring) < 0 else tuple(reversed(ring)))
        self.edges: list[_Piece] = []
        self.vertices: list[Point] = []
        for ring in rings:
            for i, point in enumerate(ring):
                self.vertices.append(point)
                self.edges.append((point, ring[(i + 1) % len(ring)]))
        self.boxes = [(min(u.x, v.x), min(u.y, v.y), max(u.x, v.x), max(u.y, v.y)) for u, v in self.edges]
        self.normals = [_normal(u, v) for u, v in self.edges]

    def on_board(self, point: Point, scale: int = 1) -> bool:
        """Whether ``point / scale`` is on the board: not strictly outside the outline and not strictly
        inside a cut-out."""
        if point_in_ring(point, _times(self.outer, scale)) is Location.OUTSIDE:
            return False
        return all(point_in_ring(point, _times(ring, scale)) is not Location.INSIDE for ring in self.cutouts)

    def allowed(self, p: _Q, q: _Q) -> bool:
        """Whether the leg ``p–q`` stays on the board. It may touch the boundary and run along it."""
        scale, (ip, iq) = _scaled((p, q))
        if ip == iq:
            return self.on_board(ip, scale)
        low_x, high_x = floor(min(p[0], q[0])), ceil(max(p[0], q[0]))
        low_y, high_y = floor(min(p[1], q[1])), ceil(max(p[1], q[1]))
        dx, dy = iq.x - ip.x, iq.y - ip.y
        length2 = dx * dx + dy * dy
        stops = {Fraction(0), Fraction(1)}
        for (u, v), box in zip(self.edges, self.boxes, strict=True):
            if box[2] < low_x or box[0] > high_x or box[3] < low_y or box[1] > high_y:
                continue
            iu, iv = (
                (u, v) if scale == 1 else (Point(u.x * scale, u.y * scale), Point(v.x * scale, v.y * scale))
            )
            relation = classify_segments(ip, iq, iu, iv)
            if relation is SegmentRelation.PROPER:
                return False
            if relation is SegmentRelation.DISJOINT:
                continue
            for end in (iu, iv):
                t = Fraction((end.x - ip.x) * dx + (end.y - ip.y) * dy, length2)
                if 0 < t < 1 and (end.x - ip.x) * dy == (end.y - ip.y) * dx:
                    stops.add(t)
        ordered = sorted(stops)
        for first, second in zip(ordered, ordered[1:], strict=False):
            t = (first + second) / 2
            middle = (p[0] + t * (q[0] - p[0]), p[1] + t * (q[1] - p[1]))
            factor, (point,) = _scaled((middle,))
            if not self.on_board(point, factor):
                return False
        return True


def _times(ring: Sequence[Point], scale: int) -> Sequence[Point]:
    return ring if scale == 1 else [Point(p.x * scale, p.y * scale) for p in ring]


def _normal(u: Point, v: Point) -> tuple[int, int]:
    """The unit normal of the edge ``u–v`` that points away from the material on its left, as integers
    over ``2**NORMAL_BITS``."""
    dx, dy = v.x - u.x, v.y - u.y
    length = floor_sqrt((dx * dx + dy * dy) << (2 * NORMAL_BITS))
    return (dy << (2 * NORMAL_BITS)) // length, -((dx << (2 * NORMAL_BITS)) // length)


def _usable(terminal: Terminal, board: _Board | None) -> bool:
    return board is None or all(board.on_board(point) for point in terminal.shape.core)


def usable_terminals(
    terminals: Sequence[Terminal], boundary: BoardBoundary | None
) -> tuple[tuple[Terminal, ...], int]:
    """The terminals that lie on the board, and the count of those left out: a terminal with a core point
    strictly outside the outline or strictly inside a cut-out is not searched."""
    board = _Board(boundary) if boundary is not None and boundary.source != "none" else None
    kept = tuple(terminal for terminal in terminals if _usable(terminal, board))
    return kept, len(terminals) - len(kept)


def boundary_distance(shape: Thick, boundary: BoardBoundary) -> int:
    """The smallest distance from ``shape`` to the boundary, in nanometres, rounded down."""
    best: Fraction | None = None
    for ring in boundary.rings():
        if shape.filled and any(point_in_ring(p, shape.core) is not Location.OUTSIDE for p in ring):
            return 0
        for i, u in enumerate(ring):
            v = ring[(i + 1) % len(ring)]
            for a, b in _pieces(shape):
                found = dist2_segment_segment(a, b, u, v)
                if best is None or found < best:
                    best = found
    if best is None:
        return 0
    return max(0, floor_sqrt(4 * best) - shape.width) // 2


# --- legs -----------------------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class _Leg:
    """One leg: its scaled weight, its points in order with their faces, and the indices of the terminals
    of the two sets that it starts or ends at (−1 when it does not)."""

    weight: int
    stops: tuple[_Stop, ...]
    index_a: int = -1
    index_b: int = -1

    def reversed(self) -> _Leg:
        return _Leg(self.weight, tuple(reversed(self.stops)), self.index_a, self.index_b)


def _inside(point: Point, shape: Thick) -> bool:
    return shape.filled and point_in_ring(point, shape.core) is not Location.OUTSIDE


def _to_vertex(terminal: Terminal, vertex: Point) -> list[tuple[Fraction, _Q]]:
    """Candidate legs from the terminal to a vertex of its face: ``(squared distance, point of a core
    piece nearest to the vertex)``, the nearest first."""
    if _inside(vertex, terminal.shape):
        return [(Fraction(0), _q(vertex))]
    target = _q(vertex)
    pieces = _pieces(terminal.shape)
    found = [(_dist2(n, target), n) for n in (_nearest(target, _q(a), _q(b)) for a, b in pieces)]
    return sorted(found, key=lambda item: item[0])


def _plan_gap(piece: _Piece, terminals: Sequence[Terminal]) -> int:
    """A lower bound, scaled, of the length of any path from ``piece`` to a terminal of the set: their
    distance in plan view less the half width. Walls and obstacles only lengthen a path."""
    best: int | None = None
    for terminal in terminals:
        shape = terminal.shape
        if _inside(piece[0], shape) or _inside(piece[1], shape):
            return 0
        for a, b in _pieces(shape):
            dist2 = dist2_segment_segment(piece[0], piece[1], a, b)
            found = max(0, floor_sqrt(dist2 * (1 << (2 * SCALE_BITS))) - (shape.width << (SCALE_BITS - 1)))
            if best is None or found < best:
                best = found
    return best or 0


class _Search:
    """Dijkstra over the two terminal sets and the boundary vertices of both faces, with integer weights
    and a deterministic order of ties. Vertex ``i`` is node ``i`` on the top face and ``count + i`` on the
    bottom face; the two terminal sets are the nodes ``source`` and ``sink``."""

    def __init__(self, a: Sequence[Terminal], b: Sequence[Terminal], board: _Board | None) -> None:
        self.a, self.b, self.board = a, b, board
        self.count = len(board.vertices) if board is not None else 0
        self.source, self.sink = 2 * self.count, 2 * self.count + 1
        self.extra: dict[int, dict[int, _Leg]] = {}
        self._terminal: dict[bool, dict[int, _Leg]] = {}
        self._visible: dict[tuple[int, int], bool] = {}
        vertices = board.vertices if board is not None else []
        # lower bounds of the path from each vertex to the two terminal sets (the same on both faces)
        self.near_a = [_plan_gap((v, v), a) for v in vertices]
        self.near_b = [_plan_gap((v, v), b) for v in vertices]

    def _face(self, node: int) -> Face:
        return "top" if node < self.count else "bottom"

    def _vertex(self, node: int) -> Point:
        assert self.board is not None
        return self.board.vertices[node % self.count]

    def _add(self, first: int, second: int, leg: _Leg) -> None:
        for one, other, value in ((first, second, leg), (second, first, leg.reversed())):
            held = self.extra.setdefault(one, {})
            if other not in held or value.weight < held[other].weight:
                held[other] = value

    # --- legs on one face -------------------------------------------------------------------------

    def direct(self) -> None:
        """The leg between the two terminal sets on one face: the closest pair of core pieces whose leg
        stays on the board."""
        best: _Leg | None = None
        for i, first in enumerate(self.a):
            for j, second in enumerate(self.b):
                if first.face != second.face:
                    continue
                found = self._direct_pair(first, second, None if best is None else best.weight)
                if found is not None and (best is None or found[0] < best.weight):
                    best = _Leg(found[0], found[1], i, j)
        if best is not None:
            self._add(self.source, self.sink, best)

    def _direct_pair(
        self, first: Terminal, second: Terminal, bound: int | None
    ) -> tuple[int, tuple[_Stop, ...]] | None:
        half = first.shape.width + second.shape.width
        face = first.face
        for inner, outer in ((first.shape, second.shape), (second.shape, first.shape)):
            for point in inner.core:
                if _inside(point, outer):
                    return 0, ((_q(point), face), (_q(point), face))
        candidates: list[tuple[Fraction, _Q, _Q]] = []
        for a1, a2 in _pieces(first.shape):
            for b1, b2 in _pieces(second.shape):
                candidates.append(_closest(_q(a1), _q(a2), _q(b1), _q(b2)))
        candidates.sort(key=lambda item: item[0])
        for dist2, p, q in candidates:
            weight = _weight(dist2, half)
            if bound is not None and weight >= bound:
                return None
            if self.board is None or self.board.allowed(p, q):
                return weight, ((p, face), (q, face))
        return None

    def terminal_legs(self, of_a: bool) -> dict[int, _Leg]:
        """For each vertex node, the shortest allowed leg from a terminal of one set on the node's face.
        The leg runs from the terminal to the vertex."""
        if of_a in self._terminal:
            return self._terminal[of_a]
        found: dict[int, _Leg] = {}
        board = self.board
        if board is not None:
            terminals = self.a if of_a else self.b
            for node in range(2 * self.count):
                face, vertex = self._face(node), self._vertex(node)
                options: list[tuple[int, int, _Q]] = []
                for index, terminal in enumerate(terminals):
                    if terminal.face != face:
                        continue
                    for dist2, near in _to_vertex(terminal, vertex):
                        options.append((_weight(dist2, terminal.shape.width), index, near))
                options.sort(key=lambda item: (item[0], item[1]))
                for weight, index, near in options:
                    if board.allowed(near, _q(vertex)):
                        stops: tuple[_Stop, ...] = ((near, face), (_q(vertex), face))
                        found[node] = _Leg(weight, stops, index if of_a else -1, -1 if of_a else index)
                        break
        self._terminal[of_a] = found
        return found

    def _sees(self, i: int, j: int) -> bool:
        """Whether the leg between the vertices ``i`` and ``j`` stays on the board (the same on both
        faces)."""
        key = (i, j) if i < j else (j, i)
        if key not in self._visible:
            board = self.board
            assert board is not None
            self._visible[key] = board.allowed(_q(board.vertices[key[0]]), _q(board.vertices[key[1]]))
        return self._visible[key]

    def vertex_legs(self, node: int, here: int, cap: int | None) -> list[tuple[int, _Leg]]:
        """The legs from a vertex node to the other vertices of its face that it sees, and its wall drop.
        A leg that cannot lead to a path shorter than ``cap`` is left out: the node lies ``here`` from
        the source, and no path from a vertex to the sink is shorter than its distance in plan view."""
        board = self.board
        assert board is not None
        face, this = self._face(node), self._vertex(node)
        own = node % self.count
        base = 0 if node < self.count else self.count
        legs: list[tuple[int, _Leg]] = []
        for index, there in enumerate(board.vertices):
            if index == own:
                continue
            dx, dy = there.x - this.x, there.y - this.y
            weight = floor_sqrt((dx * dx + dy * dy) << (2 * SCALE_BITS))
            if cap is not None and here + weight + self.near_b[index] >= cap:
                continue
            if self._sees(own, index):
                legs.append((base + index, _Leg(weight, ((_q(this), face), (_q(there), face)))))
        if board.thickness is not None:
            other = node + self.count if node < self.count else node - self.count
            stops: tuple[_Stop, ...] = ((_q(this), face), (_q(this), self._face(other)))
            legs.append((other, _Leg(board.thickness << SCALE_BITS, stops)))
        return legs

    # --- wall crossings ---------------------------------------------------------------------------

    def crossing(self, first: _Piece, second: _Piece, edge: int, half: int) -> _Leg | None:
        """The leg from a piece on the top face to a piece on the bottom face through the interior of
        one boundary edge, straight in the unfolded plane; ``None`` when no such leg exists."""
        board = self.board
        assert board is not None and board.thickness is not None
        u, v = board.edges[edge]
        nx, ny = board.normals[edge]
        normal = (Fraction(nx, _ONE), Fraction(ny, _ONE))
        thickness = board.thickness

        def unfold(point: Point) -> _Q:
            side = Fraction((point.x - u.x) * nx + (point.y - u.y) * ny, _ONE)
            shift = thickness - 2 * side
            return point.x + shift * normal[0], point.y + shift * normal[1]

        dist2, p, q_unfolded = _closest(_q(first[0]), _q(first[1]), unfold(second[0]), unfold(second[1]))
        start = (p[0] - u.x) * normal[0] + (p[1] - u.y) * normal[1]
        end = (q_unfolded[0] - u.x) * normal[0] + (q_unfolded[1] - u.y) * normal[1]
        if start > 0 or end < thickness:
            return None
        span = end - start
        dx, dy = v.x - u.x, v.y - u.y
        length2 = dx * dx + dy * dy

        def along(t: Fraction) -> Fraction:
            x = p[0] + t * (q_unfolded[0] - p[0])
            y = p[1] + t * (q_unfolded[1] - p[1])
            return ((x - u.x) * dx + (y - u.y) * dy) / length2

        enter, leave = along(-start / span), along((thickness - start) / span)
        if not (0 < enter < 1 and 0 < leave < 1):
            return None
        top = (u.x + enter * dx, u.y + enter * dy)
        bottom = (u.x + leave * dx, u.y + leave * dy)
        back = end - thickness  # how far the bottom point lies inside the edge's line
        q = _nearest(
            (bottom[0] - back * normal[0], bottom[1] - back * normal[1]), _q(second[0]), _q(second[1])
        )
        if not board.allowed(p, top) or not board.allowed(bottom, q):
            return None
        stops: tuple[_Stop, ...] = ((p, "top"), (top, "top"), (bottom, "bottom"), (q, "bottom"))
        return _Leg(_weight(dist2, half), stops)

    def crossings(self, bound: int | None) -> None:
        """Every wall crossing that can shorten a path below ``bound``: between the two terminal sets,
        from a terminal to a vertex of the other face, and between vertices of the two faces."""
        board = self.board
        if board is None or board.thickness is None:
            return
        wall = board.thickness << SCALE_BITS
        if bound is not None and wall >= bound:
            return
        # node, piece, width, terminal of a, terminal of b, lower bounds of the path to the two sets
        tops: list[_Entry] = []
        bottoms: list[_Entry] = []
        for of_a, node, terminals in ((True, self.source, self.a), (False, self.sink, self.b)):
            others = self.b if of_a else self.a
            for index, terminal in enumerate(terminals):
                for piece in _pieces(terminal.shape):
                    far = _plan_gap(piece, others)
                    entry: _Entry = (
                        node,
                        piece,
                        terminal.shape.width,
                        index if of_a else -1,
                        -1 if of_a else index,
                        0 if of_a else far,
                        far if of_a else 0,
                    )
                    (tops if terminal.face == "top" else bottoms).append(entry)
        for index, vertex in enumerate(board.vertices):
            near = (self.near_a[index], self.near_b[index])
            tops.append((index, (vertex, vertex), 0, -1, -1, *near))
            bottoms.append((self.count + index, (vertex, vertex), 0, -1, -1, *near))
        shift = NORMAL_BITS - SCALE_BITS
        widest_top = max(entry[2] for entry in tops)
        widest_bottom = max(entry[2] for entry in bottoms)
        for edge, ((u, _), (nx, ny)) in enumerate(zip(board.edges, board.normals, strict=True)):
            sides: list[list[tuple[_Entry, int]]] = []
            for entries, widest in ((tops, widest_bottom), (bottoms, widest_top)):
                kept: list[tuple[_Entry, int]] = []
                for entry in entries:
                    # how far the piece lies inside the edge's line, scaled; left out when it is outside
                    inside = [-((p.x - u.x) * nx + (p.y - u.y) * ny) for p in entry[1]]
                    if max(inside) < 0:
                        continue
                    depth = max(0, min(inside)) >> shift
                    reach = wall + depth - ((entry[2] + widest) << (SCALE_BITS - 1))
                    if bound is None or reach + min(entry[5], entry[6]) < bound:
                        kept.append((entry, depth))
                sides.append(kept)
            for (first, piece_a, width_a, a1, b1, to_a1, to_b1), depth_a in sides[0]:
                for (second, piece_b, width_b, a2, b2, to_a2, to_b2), depth_b in sides[1]:
                    if first == second:
                        continue
                    lower = wall + depth_a + depth_b - ((width_a + width_b) << (SCALE_BITS - 1))
                    ends = min(to_a1 + to_b2, to_b1 + to_a2)
                    if bound is not None and lower + ends >= bound:
                        continue
                    held = self.extra.get(first, {}).get(second)
                    if held is not None and held.weight <= lower:
                        continue
                    leg = self.crossing(piece_a, piece_b, edge, width_a + width_b)
                    if leg is None or (bound is not None and leg.weight + ends >= bound):
                        continue
                    self._add(first, second, _Leg(leg.weight, leg.stops, max(a1, a2), max(b1, b2)))

    # --- the search -------------------------------------------------------------------------------

    def links(self, node: int, here: int, cap: int | None) -> list[tuple[int, _Leg]]:
        """The legs that leave ``node``, in a fixed order."""
        found = sorted(self.extra.get(node, {}).items())
        if node == self.source:
            found += sorted(self.terminal_legs(True).items())
        elif node != self.sink:
            found += self.vertex_legs(node, here, cap)
            last = self.terminal_legs(False).get(node)
            if last is not None:
                found.append((self.sink, last.reversed()))
        return found

    def run(self, bound: int | None) -> tuple[int, list[_Leg]] | None:
        """Dijkstra from the source to the sink: the scaled length and the legs of a shortest path, or
        ``None`` when no path is shorter than ``bound``."""
        dist: dict[int, int] = {self.source: 0}
        before: dict[int, tuple[int, _Leg]] = {}
        done: set[int] = set()
        heap: list[tuple[int, int]] = [(0, self.source)]
        while heap:
            here, node = heapq.heappop(heap)
            if node in done:
                continue
            done.add(node)
            if node == self.sink:
                break
            cap = dist.get(self.sink, bound)
            if cap is not None and node < 2 * self.count and here + self.near_b[node % self.count] >= cap:
                continue  # no path through this vertex is shorter than the best one known
            for other, leg in self.links(node, here, cap):
                total = here + leg.weight
                if other in done or (cap is not None and total >= cap):
                    continue
                if other not in dist or total < dist[other]:
                    dist[other] = total
                    before[other] = (node, leg)
                    heapq.heappush(heap, (total, other))
        if self.sink not in dist:
            return None
        legs: list[_Leg] = []
        node = self.sink
        while node != self.source:
            node, leg = before[node]
            legs.append(leg)
        legs.reverse()
        return dist[self.sink], legs


def surface_distance(
    a: Sequence[Terminal],
    b: Sequence[Terminal],
    boundary: BoardBoundary | None,
    *,
    limit: int | None = None,
) -> SurfacePath | None:
    """The shortest surface path from a terminal of ``a`` to a terminal of ``b``; ``None`` when the two
    cannot be joined, or when no path is shorter than ``limit``.

    Without a boundary (or with ``source == "none"``) each face is an unbounded plane: only terminals of
    the same face are joined, by their gap. Without a thickness no leg crosses a wall.
    """
    board = _Board(boundary) if boundary is not None and boundary.source != "none" else None
    keep_a = [(i, t) for i, t in enumerate(a) if _usable(t, board)]
    keep_b = [(i, t) for i, t in enumerate(b) if _usable(t, board)]
    if not keep_a or not keep_b:
        return None
    bound = None if limit is None else limit << SCALE_BITS
    search = _Search([t for _, t in keep_a], [t for _, t in keep_b], board)
    search.direct()
    first = search.run(bound)
    search.crossings(bound if first is None else first[0])
    found = search.run(bound)
    if found is None:
        return None
    total, legs = found
    stops: list[_Stop] = []
    for leg in legs:
        for stop in leg.stops:
            if not stops or stops[-1] != stop:
                stops.append(stop)
    index_a = keep_a[max(leg.index_a for leg in legs)][0]
    index_b = keep_b[max(leg.index_b for leg in legs)][0]
    bends = max(0, len(stops) - 2)
    band = (board.band * bends if board is not None else 0) + a[index_a].band + b[index_b].band
    points: tuple[tuple[Point, Face], ...] = tuple((round_point(x, y), face) for (x, y), face in stops)
    return SurfacePath(total >> SCALE_BITS, band, points, (index_a, index_b))


__all__ = [
    "FACES",
    "NORMAL_BITS",
    "SCALE_BITS",
    "Face",
    "SurfacePath",
    "Terminal",
    "boundary_distance",
    "surface_distance",
    "usable_terminals",
]
