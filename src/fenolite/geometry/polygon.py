# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Polygons with holes, their normal form, convex hull and clip, and mixed line/arc contours.

Fill rule: non-zero by default (even-odd on request). ``area2`` is the exact shoelace sum, twice the
signed area; a ring with positive ``area2`` has positive orientation (see ``predicates``).

Normal form of one polygon: outer ring with positive ``area2``, holes with negative ``area2``, every
ring starting at its lexicographically smallest vertex, collinear vertices removed, holes sorted by
their vertex tuples. ``normalize_polygons`` is the canonical form of a polygon set: rings are first
split at repeated vertices so that every ring is simple, then each polygon is normalised and the set
is sorted by ``(bbox, outer ring, holes)``.

``keyhole_ring`` is the other way to hold a polygon with holes: one ring in which each hole is reached by
a bridge of zero width that is walked once in each direction. Both fill rules read it as the outline
without its holes.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from fractions import Fraction

from fenolite.core.units import round_half_even_div
from fenolite.geometry.errors import BRANCHING_CONTOUR, DEGENERATE, OPEN_CONTOUR, GeometryError, format_point
from fenolite.geometry.index import SpatialIndex
from fenolite.geometry.predicates import (
    FillRule,
    Location,
    SegmentRelation,
    classify_segments,
    point_in_ring,
    round_point,
)
from fenolite.geometry.shapes import DEFAULT_TOL, Arc, BBox, Segment
from fenolite.geometry.vector import Point, require_point

Ring = tuple[Point, ...]


def _orient(a: Point, b: Point, c: Point) -> int:
    return (b.x - a.x) * (c.y - a.y) - (b.y - a.y) * (c.x - a.x)


def area2(ring: Sequence[Point]) -> int:
    """Twice the signed area of a closed ring (exact shoelace sum)."""
    n = len(ring)
    total = 0
    for i in range(n):
        a, b = ring[i], ring[(i + 1) % n]
        total += a.x * b.y - b.x * a.y
    return total


def _coerce_ring(ring: Iterable[Point], name: str) -> Ring:
    out: list[Point] = []
    for i, v in enumerate(ring):
        if isinstance(v, tuple):  # convenience: (x, y) pairs
            v = Point(*v)  # pyright: ignore[reportUnknownArgumentType]
        require_point(v, f"{name}[{i}]")
        out.append(v)
    return tuple(out)


def _validate_ring(ring: Ring, name: str) -> None:
    if len(ring) < 3:
        raise GeometryError(f"{name} has {len(ring)} vertices; a ring needs at least 3", points=ring)
    if ring[0] == ring[-1]:
        raise GeometryError(f"{name} repeats its first vertex {format_point(ring[0])} at the end",
                            points=(ring[0],))  # fmt: skip
    for i in range(len(ring) - 1):
        if ring[i] == ring[i + 1]:
            raise GeometryError(f"{name} has consecutive duplicate vertices {format_point(ring[i])}",
                                points=(ring[i],))  # fmt: skip
    if area2(ring) == 0:
        raise GeometryError(f"{name} has zero area", points=ring)


def _remove_collinear(ring: Sequence[Point]) -> list[Point]:
    out = list(ring)
    changed = True
    while changed and len(out) >= 3:
        changed = False
        kept: list[Point] = []
        n = len(out)
        for i in range(n):
            prev = kept[-1] if kept else out[i - 1]
            if _orient(prev, out[i], out[(i + 1) % n]) == 0:
                changed = True
                continue
            kept.append(out[i])
        out = kept
    return out


def _normalize_ring(ring: Sequence[Point], positive: bool) -> Ring:
    out = _remove_collinear(ring)
    if len(out) < 3:
        raise GeometryError("ring collapses after removing collinear vertices", points=tuple(ring))
    if (area2(out) > 0) != positive:
        out.reverse()
    start = out.index(min(out))
    return tuple(out[start:] + out[:start])


@dataclass(frozen=True, slots=True)
class Polygon:
    """An outer ring and zero or more holes; ``(x, y)`` tuples are accepted and converted to ``Point``."""

    outer: Ring
    holes: tuple[Ring, ...] = ()

    def __post_init__(self) -> None:
        outer = _coerce_ring(self.outer, "outer")
        holes = tuple(_coerce_ring(h, f"holes[{i}]") for i, h in enumerate(self.holes))
        object.__setattr__(self, "outer", outer)
        object.__setattr__(self, "holes", holes)
        _validate_ring(outer, "outer ring")
        for i, hole in enumerate(holes):
            _validate_ring(hole, f"hole {i}")

    @property
    def area2(self) -> int:
        """Sum of the rings' doubled signed areas (the doubled net area once normalised)."""
        return area2(self.outer) + sum(area2(h) for h in self.holes)

    def rings(self) -> tuple[Ring, ...]:
        return (self.outer, *self.holes)

    def bbox(self) -> BBox:
        return BBox.of_points(self.outer)

    def locate(self, p: Point, rule: FillRule = FillRule.NONZERO) -> Location:
        """``INSIDE``, ``OUTSIDE`` or ``BOUNDARY``; points inside a hole are ``OUTSIDE``."""
        where = point_in_ring(p, self.outer, rule)
        if where != Location.INSIDE:
            return where
        for hole in self.holes:
            in_hole = point_in_ring(p, hole, rule)
            if in_hole == Location.BOUNDARY:
                return Location.BOUNDARY
            if in_hole == Location.INSIDE:
                return Location.OUTSIDE
        return Location.INSIDE

    def is_convex(self) -> bool:
        """Hole-free, every turn of one sign (collinear vertices allowed) and a single winding."""
        if self.holes:
            return False
        ring = self.outer
        n = len(ring)
        sign = 0
        for i in range(n):
            a, b, c = ring[i - 1], ring[i], ring[(i + 1) % n]
            o = _orient(a, b, c)
            if o == 0:
                if (b.x - a.x) * (c.x - b.x) + (b.y - a.y) * (c.y - b.y) < 0:
                    return False  # a spike reverses direction
                continue
            s = 1 if o > 0 else -1
            if sign and s != sign:
                return False
            sign = s
        # With turns of one sign, the edges' x-direction changes sign twice per full turn: more
        # changes mean the ring winds more than once (a star).
        signs = [_sign(ring[(i + 1) % n].x - ring[i].x) for i in range(n)]
        signs = [s for s in signs if s]
        return sum(1 for i in range(len(signs)) if signs[i] != signs[i - 1]) <= 2

    def is_simple(self) -> bool:
        """No two edges meet except consecutive edges at their shared vertex (holes included)."""
        edges: list[tuple[int, int, int, Point, Point]] = []
        for r, ring in enumerate(self.rings()):
            n = len(ring)
            edges.extend((r, i, n, ring[i], ring[(i + 1) % n]) for i in range(n))
        index = SpatialIndex[int].build((BBox.of_points((e[3], e[4])), k) for k, e in enumerate(edges))
        for i, j in index.pairs():
            ri, ii, n, a, b = edges[i]
            rj, jj, _, c, d = edges[j]
            relation = classify_segments(a, b, c, d)
            adjacent = ri == rj and ((ii + 1) % n == jj or (jj + 1) % n == ii)
            if adjacent:
                if relation == SegmentRelation.COLLINEAR_OVERLAP:
                    return False
            elif relation != SegmentRelation.DISJOINT:
                return False
        return True

    def normalize(self) -> Polygon:
        outer = _normalize_ring(self.outer, True)
        holes = tuple(sorted(_normalize_ring(h, False) for h in self.holes))
        return Polygon(outer, holes)


def convex_hull(points: Iterable[Point]) -> Ring:
    """Hull vertices in normal form (positive orientation, smallest vertex first, no collinear points).

    Fewer than three non-collinear points give their one or two extreme points.
    """
    pts: list[Point] = []
    for p in points:
        require_point(p, "points")
        pts.append(p)
    pts = sorted(set(pts))
    if len(pts) <= 2:
        return tuple(pts)
    lower: list[Point] = []
    for p in pts:
        while len(lower) >= 2 and _orient(lower[-2], lower[-1], p) <= 0:
            lower.pop()
        lower.append(p)
    upper: list[Point] = []
    for p in reversed(pts):
        while len(upper) >= 2 and _orient(upper[-2], upper[-1], p) <= 0:
            upper.pop()
        upper.append(p)
    hull = lower[:-1] + upper[:-1]
    return tuple(hull) if len(hull) >= 3 else (pts[0], pts[-1])


_FPoint = tuple[Fraction, Fraction]


def _side(a: Point, b: Point, p: _FPoint) -> Fraction:
    return (b.x - a.x) * (p[1] - a.y) - (b.y - a.y) * (p[0] - a.x)


def _finish_ring(points: Iterable[Point]) -> Ring | None:
    """Drop consecutive duplicates and collinear vertices; ``None`` if no area is left."""
    out: list[Point] = []
    for p in points:
        if not out or out[-1] != p:
            out.append(p)
    while len(out) > 1 and out[-1] == out[0]:
        out.pop()
    out = _remove_collinear(out)
    if len(out) < 3 or area2(out) == 0:
        return None
    return tuple(out)


def clip_convex(subject: Polygon, clip: Polygon) -> Polygon | None:
    """Intersection of two convex hole-free polygons (Sutherland–Hodgman), rounded to nanometres.

    Returns the normalised polygon, or ``None`` when the rounded result has no area (disjoint or
    touching operands, slivers that collapse). ``ValueError`` if an operand is not convex.
    """
    for name, poly in (("subject", subject), ("clip", clip)):
        if not poly.is_convex():
            raise ValueError(f"{name} is not a convex hole-free polygon")
    ring = _normalize_ring(clip.outer, True)
    out: list[_FPoint] = [(Fraction(p.x), Fraction(p.y)) for p in subject.outer]
    n = len(ring)
    for i in range(n):
        if not out:
            return None
        a, b = ring[i], ring[(i + 1) % n]
        current, out = out, []
        for j in range(len(current)):
            p, q = current[j - 1], current[j]
            sp, sq = _side(a, b, p), _side(a, b, q)
            if sq >= 0:
                if sp < 0:
                    t = sp / (sp - sq)
                    out.append((p[0] + t * (q[0] - p[0]), p[1] + t * (q[1] - p[1])))
                out.append(q)
            elif sp > 0:
                t = sp / (sp - sq)
                out.append((p[0] + t * (q[0] - p[0]), p[1] + t * (q[1] - p[1])))
    result = _finish_ring(round_point(x, y) for x, y in out)
    return None if result is None else Polygon(result).normalize()


def _edges(poly: Polygon) -> list[tuple[Point, Point]]:
    edges: list[tuple[Point, Point]] = []
    for ring in poly.rings():
        n = len(ring)
        edges.extend((ring[i], ring[(i + 1) % n]) for i in range(n))
    return edges


def polygons_intersect(a: Polygon, b: Polygon) -> bool:
    """Whether the closed regions of ``a`` and ``b`` share at least one point."""
    if not a.bbox().intersects(b.bbox()):
        return False
    b_edges = _edges(b)
    index = SpatialIndex[tuple[Point, Point]].build((BBox.of_points(e), e) for e in b_edges)
    for p, q in _edges(a):
        for c, d in index.query(BBox.of_points((p, q))):
            if classify_segments(p, q, c, d) != SegmentRelation.DISJOINT:
                return True
    # Boundaries are disjoint: each ring lies wholly inside or wholly outside the other region.
    return any(b.locate(ring[0]) != Location.OUTSIDE for ring in a.rings()) or any(
        a.locate(ring[0]) != Location.OUTSIDE for ring in b.rings()
    )


def _split_ring(ring: Ring) -> list[Ring]:
    """Split a ring at repeated vertices into loops that visit each vertex once (zero-area loops dropped)."""
    loops: list[Ring] = []
    stack: list[Point] = []
    position: dict[Point, int] = {}
    for v in ring:
        j = position.get(v)
        if j is None:
            position[v] = len(stack)
            stack.append(v)
            continue
        loop = stack[j:]
        for w in loop[1:]:
            del position[w]
        del stack[j + 1 :]
        loops.append(tuple(loop))
    loops.append(tuple(stack))
    return [loop for loop in loops if len(loop) >= 3 and area2(loop) != 0]


def _scaled(ring: Ring) -> Ring:
    return tuple(Point(2 * p.x, 2 * p.y) for p in ring)


def _ring_inside(inner: Ring, outer: Ring) -> bool | None:
    """Whether simple ring ``inner`` lies inside ``outer``; ``None`` if no vertex or edge midpoint decides."""
    for v in inner:
        where = point_in_ring(v, outer)
        if where != Location.BOUNDARY:
            return where == Location.INSIDE
    big = _scaled(outer)
    n = len(inner)
    for i in range(n):
        a, b = inner[i], inner[(i + 1) % n]
        where = point_in_ring(Point(a.x + b.x, a.y + b.y), big)
        if where != Location.BOUNDARY:
            return where == Location.INSIDE
    return None


def _parent(hole: Ring, outers: Sequence[Ring]) -> int:
    if len(outers) == 1:
        return 0
    for i, outer in enumerate(outers):
        if _ring_inside(hole, outer):
            return i
    box = BBox.of_points(hole)
    return next((i for i, o in enumerate(outers) if BBox.of_points(o).contains_bbox(box)), 0)


def _sign(v: int) -> int:
    return (v > 0) - (v < 0)


def _canonical_parts(poly: Polygon) -> list[Polygon]:
    sign = _sign(area2(poly.outer))
    outers: list[Ring] = []
    holes: list[Ring] = []
    for loop in _split_ring(poly.outer):
        (outers if _sign(area2(loop)) == sign else holes).append(loop)
    islands: list[Ring] = []
    for hole in poly.holes:
        hole_sign = _sign(area2(hole))
        for loop in _split_ring(hole):
            (holes if _sign(area2(loop)) == hole_sign else islands).append(loop)
    if not outers:
        return []
    assigned: list[list[Ring]] = [[] for _ in outers]
    for hole in holes:
        assigned[_parent(hole, outers)].append(hole)
    parts = [Polygon(o, tuple(h)).normalize() for o, h in zip(outers, assigned, strict=True)]
    parts.extend(Polygon(i).normalize() for i in islands)
    return parts


def _sort_key(poly: Polygon) -> tuple[tuple[int, int, int, int], Ring, tuple[Ring, ...]]:
    return poly.bbox().as_tuple(), poly.outer, poly.holes


def normalize_polygons(polys: Iterable[Polygon]) -> tuple[Polygon, ...]:
    """Canonical form of a polygon set: simple rings, each polygon normalised, sorted."""
    parts: list[Polygon] = []
    for poly in polys:
        parts.extend(_canonical_parts(poly))
    return tuple(sorted(parts, key=_sort_key))


# --- one ring for a polygon with holes ----------------------------------------------------------


@dataclass(frozen=True, slots=True)
class Keyhole:
    """What ``keyhole_ring`` returns: the ring, the number of holes it holds and the number of holes that
    were dropped because they lie outside the outline."""

    ring: Ring
    merged: int
    outside: int


def _distinct(ring: Sequence[Point]) -> list[Point]:
    """``ring`` without equal neighbours and without a closing copy of its first point."""
    out: list[Point] = []
    for point in ring:
        if not out or out[-1] != point:
            out.append(point)
    while len(out) > 1 and out[0] == out[-1]:
        out.pop()
    return out


def _anchor(ring: Sequence[Point], hx: int, hy: int) -> tuple[int, Point | None] | None:
    """Where the ray from ``(hx, hy)`` towards smaller ``x`` first meets ``ring``: ``(index, None)`` for
    the vertex ``ring[index]``, ``(index, point)`` for a point to insert after ``ring[index]``, ``None``
    when the ray meets nothing. Among equal crossings the first in ring order is kept."""
    best: tuple[int, Point | None] | None = None
    num, den = 0, 1  # the x of the best crossing is num / den, den above 0
    count = len(ring)
    for i in range(count):
        a = ring[i]
        b = ring[i + 1 - count]
        ay, by = a.y, b.y
        if (ay < hy and by < hy) or (ay > hy and by > hy):
            continue
        ax, bx = a.x, b.x
        found: tuple[int, Point | None]
        if ay == by:  # the edge lies on the line of the ray
            low, high = (ax, bx) if ax <= bx else (bx, ax)
            if low > hx:
                continue
            if high >= hx:  # the start of the ray is on the edge
                n, d = hx, 1
                at_a, at_b = ax == hx, bx == hx
            else:
                n, d = high, 1
                at_a, at_b = ax == high, bx == high
            found = (i, None) if at_a else ((i + 1) % count, None) if at_b else (i, Point(hx, hy))
        elif ay == hy:
            if ax > hx:
                continue
            n, d, found = ax, 1, (i, None)
        elif by == hy:
            if bx > hx:
                continue
            n, d, found = bx, 1, ((i + 1) % count, None)
        else:
            d = by - ay
            n = ax * d + (hy - ay) * (bx - ax)
            if d < 0:
                n, d = -n, -d
            if n > hx * d:
                continue
            found = (i, Point(round_half_even_div(n, d), hy))
        if best is None or n * den > num * d:
            best, num, den = found, n, d
    return best


def _keyhole(outer: Sequence[Point], holes: Iterable[Sequence[Point]]) -> tuple[Keyhole, int]:
    """``keyhole_ring`` and the number of edges its anchor searches tested."""
    ring = list(_coerce_ring(outer, "outer"))
    sign = _sign(area2(ring))
    usable: list[tuple[Point, Ring]] = []
    for i, given in enumerate(holes):
        hole = _distinct(_coerce_ring(given, f"holes[{i}]"))
        turn = _sign(area2(hole))
        if len(hole) < 3 or turn == 0:
            continue
        if turn == sign:
            hole.reverse()
        start = hole.index(min(hole))
        usable.append((hole[start], tuple(hole[start:] + hole[:start])))
    if sign == 0 or len(ring) < 3:
        return Keyhole(tuple(ring), 0, len(usable)), 0
    first = tuple(ring)
    merged = outside = tested = 0
    for left, hole in sorted(usable):
        if point_in_ring(left, first) == Location.OUTSIDE:
            outside += 1
            continue
        tested += len(ring)
        found = _anchor(ring, left.x, left.y)
        if found is None:  # not reachable for a vertex that is not outside; kept as a guard
            outside += 1
            continue
        index, inserted = found
        anchor = ring[index] if inserted is None else inserted
        spliced = ring[: index + 1]
        for point in (*(() if inserted is None else (inserted,)), *hole, left, anchor):
            if spliced[-1] != point:
                spliced.append(point)
        rest = ring[index + 1 :]
        if rest and rest[0] == spliced[-1]:
            rest = rest[1:]
        ring = spliced + rest
        while len(ring) > 1 and ring[0] == ring[-1]:
            ring.pop()
        merged += 1
    return Keyhole(tuple(ring), merged, outside), tested


def keyhole_ring(outer: Sequence[Point], holes: Iterable[Sequence[Point]]) -> Keyhole:
    """One ring that bounds ``outer`` without ``holes``: each hole is joined to the ring around it by a
    bridge of zero width that is walked once in each direction.

    ``outer`` is kept as given, neither reversed nor rotated, and every hole runs against it, so a point
    inside a hole is ``OUTSIDE`` of the ring under the non-zero and the even-odd rule and a point on a
    bridge is ``BOUNDARY``. Holes are merged by ascending leftmost vertex: a ray towards smaller ``x``
    from that vertex meets the ring built so far at the anchor, a vertex of the ring or a point put into
    an edge with its ``x`` rounded half to even. A hole with fewer than three distinct points or without
    area is dropped; a hole whose leftmost vertex is outside ``outer`` is dropped and counted in
    ``outside``. The result does not depend on the order of ``holes``.
    """
    return _keyhole(outer, holes)[0]


Piece = Segment | Arc


def _check_piece(piece: Piece, name: str) -> None:
    if not isinstance(piece, (Segment, Arc)):  # pyright: ignore[reportUnnecessaryIsInstance]
        raise TypeError(f"{name} must be a Segment or an Arc, got {piece!r}")


@dataclass(frozen=True, slots=True)
class Path:
    """An ordered chain of segments and arcs whose consecutive endpoints are equal."""

    pieces: tuple[Piece, ...]
    closed: bool

    def __post_init__(self) -> None:
        pieces = tuple(self.pieces)
        object.__setattr__(self, "pieces", pieces)
        if not pieces:
            raise GeometryError("a path needs at least one piece")
        for i, piece in enumerate(pieces):
            _check_piece(piece, f"pieces[{i}]")
        for i in range(len(pieces) - 1):
            if pieces[i].end != pieces[i + 1].start:
                raise GeometryError(
                    f"pieces {i} and {i + 1} do not meet: {format_point(pieces[i].end)} ≠ "
                    f"{format_point(pieces[i + 1].start)}",
                    code=OPEN_CONTOUR,
                    points=(pieces[i].end, pieces[i + 1].start),
                )
        if self.closed and pieces[-1].end != pieces[0].start:
            raise GeometryError(
                f"closed path ends at {format_point(pieces[-1].end)}, not at its start "
                f"{format_point(pieces[0].start)}",
                code=OPEN_CONTOUR,
                points=(pieces[-1].end, pieces[0].start),
            )

    @property
    def start(self) -> Point:
        return self.pieces[0].start

    def bbox(self) -> BBox:
        box = self.pieces[0].bbox()
        for piece in self.pieces[1:]:
            box = box.union(piece.bbox())
        return box

    def polygonize(self, tol: int = DEFAULT_TOL) -> tuple[Point, ...]:
        """Vertices of the chain (arcs polygonised with ``tol``); a closed path gives a ring."""
        vertices: list[Point] = []
        for piece in self.pieces:
            part = (piece.a, piece.b) if isinstance(piece, Segment) else piece.polygonize(tol)
            for p in part:
                if not vertices or vertices[-1] != p:
                    vertices.append(p)
        if self.closed:
            while len(vertices) > 1 and vertices[-1] == vertices[0]:
                vertices.pop()
        return tuple(vertices)

    def reversed(self) -> Path:
        return Path(tuple(p.reversed() for p in reversed(self.pieces)), self.closed)


def _first_key(piece: Piece) -> tuple[Point, Point]:
    return piece.end, (piece.mid if isinstance(piece, Arc) else piece.end)


def _canonical_ring(chain: list[Piece]) -> Path:
    first = min(range(len(chain)), key=lambda i: chain[i].start)
    path = Path(tuple(chain[first:] + chain[:first]), True)
    back = path.reversed()
    doubled = area2(path.polygonize(DEFAULT_TOL))
    if doubled < 0 or (doubled == 0 and _first_key(back.pieces[0]) < _first_key(path.pieces[0])):
        return back
    return path


def assemble_rings(pieces: Iterable[Piece]) -> tuple[Path, ...]:
    """Chain unordered segments and arcs into closed paths by exact endpoint equality.

    Each ring starts at its smallest endpoint and runs so that its polygonisation at ``DEFAULT_TOL``
    has positive ``area2``; rings are sorted by their start. The result does not depend on the input
    order or on the direction of the input pieces.
    """
    items = list(pieces)
    ends: dict[Point, list[int]] = {}
    for i, piece in enumerate(items):
        _check_piece(piece, f"pieces[{i}]")
        if isinstance(piece, Segment) and piece.is_degenerate:
            raise GeometryError(f"zero-length segment at {format_point(piece.a)}", code=DEGENERATE,
                                points=(piece.a,))  # fmt: skip
        ends.setdefault(piece.start, []).append(i)
        ends.setdefault(piece.end, []).append(i)
    branching = sorted(p for p, users in ends.items() if len(users) > 2)
    if branching:
        raise GeometryError(
            "more than two pieces meet at " + ", ".join(format_point(p) for p in branching),
            code=BRANCHING_CONTOUR,
            points=tuple(branching),
        )
    dangling = sorted(p for p, users in ends.items() if len(users) == 1)
    if dangling:
        raise GeometryError(
            "open contour: loose endpoints " + ", ".join(format_point(p) for p in dangling),
            code=OPEN_CONTOUR,
            points=tuple(dangling),
        )
    used = [False] * len(items)
    rings: list[Path] = []
    for i, piece in enumerate(items):
        if used[i]:
            continue
        used[i] = True
        chain: list[Piece] = [piece]
        current = i
        at = piece.end
        while at != piece.start:
            a, b = ends[at]
            nxt = b if a == current else a
            used[nxt] = True
            following = items[nxt] if items[nxt].start == at else items[nxt].reversed()
            chain.append(following)
            current, at = nxt, following.end
        rings.append(_canonical_ring(chain))
    return tuple(sorted(rings, key=lambda r: r.start))


__all__ = [
    "Keyhole",
    "Path",
    "Piece",
    "Polygon",
    "Ring",
    "area2",
    "assemble_rings",
    "clip_convex",
    "convex_hull",
    "keyhole_ring",
    "normalize_polygons",
    "polygons_intersect",
]
