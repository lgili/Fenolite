# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The narrowest copper section of a fill region between two ports (capability board-analyses, "Narrowest
copper section"; ``docs/analyses.md``, "Power paths"; ``H-G-AN-SECTION``).

The section is the smallest length, inside the copper, of a closed curve that enters neither port's hull
and holds one hull inside it and the other outside: the whole current between the ports crosses every such
curve. A shortest curve is a chain of straight chords through copper and of free runs through the holes
and around the outer ring, which cost nothing. The search works on exact points:

- every ring is cut where a hull meets it, and the parts strictly inside a hull are left out;
- points joined at no cost (along a ring, or along a hull edge that lies in a hole or outside) form one
  node, kept by a union-find that also holds, per point, the parity of the crossings of a seam drawn
  from a point inside one hull to a point inside the other;
- chords join the closest points of two ring edges, of a hull vertex and a ring edge, and of two hull
  vertices, and never pass strictly inside a hull; a hull edge in copper is a chord too;
- a closed walk of odd parity separates the ports, so the answer is the shortest odd cycle, found by
  Dijkstra on the graph doubled by the parity.

Sides, crossings and squared lengths are exact (integers and ``Fraction``s). Lengths are compared as
rounded-down square roots scaled by ``2**SCALE_BITS`` per nanometre; the reported interval sums the
rounded-down and the rounded-up chord lengths. A point on the seam's line counts as on its positive side,
which is the seam moved by an infinitesimal step, so no crossing is counted twice.
"""

from __future__ import annotations

import heapq
from bisect import bisect_right
from collections.abc import Sequence
from dataclasses import dataclass
from fractions import Fraction
from math import ceil, floor, lcm

from fenolite.analysis.copper import ARC_TOL_NM
from fenolite.analysis.fills import FillRegion
from fenolite.analysis.report import Measure
from fenolite.core.coords import Point
from fenolite.geometry import (
    FULL_TURN,
    TRIG_BITS,
    BBox,
    Location,
    SpatialIndex,
    Thick,
    area2,
    ceil_sqrt,
    convex_hull,
    cos_sin_fixed,
    floor_sqrt,
    point_in_ring,
    round_point,
    thick_closer_than,
    thick_touch,
)

SCALE_BITS = 20
Ring = tuple[Point, ...]
N = Fraction | int
Q = tuple[N, N]
"""An exact point: integers where the point is a stored one, ``Fraction``s where it was computed. An ``int``
and a ``Fraction`` of one value are equal and hash alike, so both name one node."""
_Ints = tuple[int, int, int, int]
_Chord = tuple[int, N, Q, Q]  # scaled weight, squared length, the two ends
_ZERO = Fraction(0)
_ONE = Fraction(1)


@dataclass(frozen=True, slots=True)
class Port:
    """The copper of one piece or via group inside a region, as thick shapes; ``band`` bounds their
    approximation (the band of a polygonised arc), else 0."""

    where: str
    shapes: tuple[Thick, ...]
    band: int = 0


@dataclass(frozen=True, slots=True)
class Section:
    """The narrowest section as a measure (``points`` are the ends of its chords in order). ``hull_free``
    is false when a hole of the region lies inside a port's hull and outside its shapes: the measure is
    then only an upper bound of the section of the port's own copper."""

    measure: Measure
    hull_free: bool = True


# --- hulls ----------------------------------------------------------------------------------------


def _toward_zero(value: int, bits: int) -> int:
    return value >> bits if value >= 0 else -((-value) >> bits)


def _disc(centre: Point, diameter: int, arc_tol: int) -> list[Point]:
    """Points on or inside the disc: the corners of a polygon whose sagitta is at most ``arc_tol``."""
    if diameter <= 0:
        return [centre]
    count = max(8, ceil_sqrt(Fraction(5 * diameter, 2 * max(1, arc_tol))) + 1)
    count += -count % 4
    points: list[Point] = []
    for index in range(count):
        cos, sin = cos_sin_fixed((FULL_TURN * index) // count)
        dx = _toward_zero(diameter * cos, TRIG_BITS + 1)
        dy = _toward_zero(diameter * sin, TRIG_BITS + 1)
        while 4 * (dx * dx + dy * dy) > diameter * diameter:
            if abs(dx) >= abs(dy):
                dx -= 1 if dx > 0 else -1
            else:
                dy -= 1 if dy > 0 else -1
        points.append(Point(centre.x + dx, centre.y + dy))
    return points


def port_hull(port: Port, *, arc_tol: int = ARC_TOL_NM) -> Ring:
    """The convex hull of the port's shapes, each polygonised with every point on or inside its copper,
    so the hull never exceeds the exact hull of the copper. Positive orientation."""
    points: list[Point] = []
    for shape in port.shapes:
        for point in shape.core:
            points += _disc(point, shape.width, arc_tol)
    return convex_hull(points)


# --- exact helpers --------------------------------------------------------------------------------


def _q(point: Point) -> Q:
    return point.x, point.y


def _side(a: Q, b: Q, p: Q) -> N:
    return (b[0] - a[0]) * (p[1] - a[1]) - (b[1] - a[1]) * (p[0] - a[0])


def sq_dist(p: Q, q: Q) -> N:
    dx, dy = p[0] - q[0], p[1] - q[1]
    return dx * dx + dy * dy


def nearest(p: Q, a: Q, b: Q) -> Q:
    dx, dy = b[0] - a[0], b[1] - a[1]
    length2 = dx * dx + dy * dy
    if length2 == 0:
        return a
    t = Fraction((p[0] - a[0]) * dx + (p[1] - a[1]) * dy, length2)
    t = min(max(t, _ZERO), _ONE)
    return a[0] + t * dx, a[1] + t * dy


def closest(a: Q, b: Q, c: Q, d: Q) -> tuple[N, Q, Q]:
    """The squared distance of the closed segments ``a–b`` and ``c–d`` and a closest pair of points."""
    d1, d2 = _side(a, b, c), _side(a, b, d)
    d3, d4 = _side(c, d, a), _side(c, d, b)
    if d1 * d2 < 0 and d3 * d4 < 0:
        t = Fraction(d3, d3 - d4)
        common: Q = (a[0] + t * (b[0] - a[0]), a[1] + t * (b[1] - a[1]))
        return 0, common, common
    best: tuple[N, Q, Q] | None = None
    for p, on_first in ((a, True), (b, True), (c, False), (d, False)):
        q = nearest(p, c, d) if on_first else nearest(p, a, b)
        found = (sq_dist(p, q), p, q) if on_first else (sq_dist(p, q), q, p)
        if best is None or found[0] < best[0]:
            best = found
    assert best is not None
    return best


def _point_segment2(px: int, py: int, sx: int, sy: int, tx: int, ty: int) -> tuple[int, int]:
    ex, ey = tx - sx, ty - sy
    wx, wy = px - sx, py - sy
    length2 = ex * ex + ey * ey
    along = wx * ex + wy * ey
    if along <= 0 or length2 == 0:
        return wx * wx + wy * wy, 1
    if along >= length2:
        return (px - tx) ** 2 + (py - ty) ** 2, 1
    across = ex * wy - ey * wx
    return across * across, length2


def _closest_ints(a: _Ints, b: _Ints) -> tuple[N, Q, Q]:
    """``closest`` of two segments with integer ends, in integers but for the one projected point: the same
    distance and the same pair of points, candidates tried in the same order (change c0503)."""
    ax, ay, bx, by = a
    cx, cy, dx, dy = b
    d1 = (bx - ax) * (cy - ay) - (by - ay) * (cx - ax)
    d2 = (bx - ax) * (dy - ay) - (by - ay) * (dx - ax)
    d3 = (dx - cx) * (ay - cy) - (dy - cy) * (ax - cx)
    d4 = (dx - cx) * (by - cy) - (dy - cy) * (bx - cx)
    if d1 * d2 < 0 and d3 * d4 < 0:
        t = Fraction(d3, d3 - d4)
        common: Q = (ax + t * (bx - ax), ay + t * (by - ay))
        return 0, common, common
    tries = (
        (ax, ay, cx, cy, dx, dy),
        (bx, by, cx, cy, dx, dy),
        (cx, cy, ax, ay, bx, by),
        (dx, dy, ax, ay, bx, by),
    )
    found, best = 0, _point_segment2(*tries[0])
    for k in (1, 2, 3):
        top, bottom = _point_segment2(*tries[k])
        if top * best[1] < best[0] * bottom:
            found, best = k, (top, bottom)
    px, py, sx, sy, tx, ty = tries[found]
    ex, ey = tx - sx, ty - sy
    length2 = ex * ex + ey * ey
    along = (px - sx) * ex + (py - sy) * ey
    if along <= 0 or length2 == 0:
        q: Q = (sx, sy)
    elif along >= length2:
        q = (tx, ty)
    else:
        t = Fraction(along, length2)
        q = (sx + t * ex, sy + t * ey)
    dist2: N = best[0] if best[1] == 1 else Fraction(best[0], best[1])
    return (dist2, (px, py), q) if found < 2 else (dist2, q, (px, py))


def _dist2_int(a: _Ints, b: _Ints) -> tuple[int, int]:
    """The squared distance of two closed segments with integer ends, as a numerator and a denominator
    above 0."""
    ax, ay, bx, by = a
    cx, cy, dx, dy = b
    d1 = (bx - ax) * (cy - ay) - (by - ay) * (cx - ax)
    d2 = (bx - ax) * (dy - ay) - (by - ay) * (dx - ax)
    d3 = (dx - cx) * (ay - cy) - (dy - cy) * (ax - cx)
    d4 = (dx - cx) * (by - cy) - (dy - cy) * (bx - cx)
    if d1 * d2 < 0 and d3 * d4 < 0:
        return 0, 1
    best = _point_segment2(ax, ay, cx, cy, dx, dy)
    for found in (
        _point_segment2(bx, by, cx, cy, dx, dy),
        _point_segment2(cx, cy, ax, ay, bx, by),
        _point_segment2(dx, dy, ax, ay, bx, by),
    ):
        if found[0] * best[1] < best[0] * found[1]:
            best = found
    return best


def cuts(a: Point, b: Point, c: Point, d: Point) -> list[Fraction]:
    """The parameters along ``a–b``, within 0 and 1, where it meets the closed segment ``c–d``: one for a
    crossing or a touch, the two ends of the overlap for collinear segments."""
    rx, ry = b.x - a.x, b.y - a.y
    sx, sy = d.x - c.x, d.y - c.y
    denom = rx * sy - ry * sx
    wx, wy = c.x - a.x, c.y - a.y
    if denom != 0:
        t = Fraction(wx * sy - wy * sx, denom)
        u = Fraction(wx * ry - wy * rx, denom)
        return [t] if 0 <= t <= 1 and 0 <= u <= 1 else []
    if wx * ry - wy * rx != 0:
        return []
    length2 = rx * rx + ry * ry
    found = sorted(Fraction((p.x - a.x) * rx + (p.y - a.y) * ry, length2) for p in (c, d))
    low, high = max(found[0], _ZERO), min(found[1], _ONE)
    return [low, high] if low <= high else []


def _strictly_inside(point: Q, hull: Sequence[Q]) -> bool:
    return all(_side(hull[i - 1], hull[i], point) > 0 for i in range(len(hull)))


def _enters(x: Q, y: Q, hull: Ring) -> bool:
    """Whether the open segment ``x–y`` has a point strictly inside the convex ``hull`` (positive
    orientation). The sides are integers: the two points are scaled by their common denominator."""
    scale = lcm(x[0].denominator, x[1].denominator, y[0].denominator, y[1].denominator)
    x0, y0, x1, y1 = int(x[0] * scale), int(x[1] * scale), int(y[0] * scale), int(y[1] * scale)
    low, high = _ZERO, _ONE
    a = hull[-1]
    for b in hull:
        ex, ey = b.x - a.x, b.y - a.y
        s0 = ex * (y0 - a.y * scale) - ey * (x0 - a.x * scale)
        s1 = ex * (y1 - a.y * scale) - ey * (x1 - a.x * scale)
        a = b
        if s0 > 0 and s1 > 0:
            continue
        if s0 <= 0 and s1 <= 0:
            return False
        if s0 <= 0:
            low = max(low, Fraction(s0, s0 - s1))
        else:
            high = min(high, Fraction(s0, s0 - s1))
        if low >= high:
            return False
    return True


def _box(points: Sequence[Q]) -> tuple[int, int, int, int]:
    return (
        floor(min(p[0] for p in points)),
        floor(min(p[1] for p in points)),
        ceil(max(p[0] for p in points)),
        ceil(max(p[1] for p in points)),
    )


def _boxes_meet(a: tuple[int, int, int, int], b: tuple[int, int, int, int], grow: int = 0) -> bool:
    return a[0] - grow <= b[2] and b[0] - grow <= a[2] and a[1] - grow <= b[3] and b[1] - grow <= a[3]


def located(point: Q, ring: Ring) -> Location:
    scale = lcm(point[0].denominator, point[1].denominator)
    target = Point(int(point[0] * scale), int(point[1] * scale))
    scaled = ring if scale == 1 else [Point(p.x * scale, p.y * scale) for p in ring]
    return point_in_ring(target, scaled)


# --- the search -----------------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class _Site:
    """A place where a chord may end: a kept part of a ring edge, or a hull vertex (``a == b``)."""

    a: Q
    b: Q
    node: int
    box: tuple[int, int, int, int]
    hull: int = -1
    ints: _Ints | None = None
    side: int = 0


class _Search:
    def __init__(self, region: FillRegion, hulls: tuple[Ring, Ring]) -> None:
        self.rings: tuple[Ring, ...] = (region.outer, *region.holes)
        self.hulls = hulls
        self.qhulls = tuple(tuple(_q(p) for p in hull) for hull in hulls)
        self.hull_boxes = tuple(_box(hull) for hull in self.qhulls)
        # the seam joins a point strictly inside each hull: the centroid of three of its corners,
        # kept as integers scaled by 3
        self.seam_scale = 3
        self.seam_ints: tuple[int, int, int, int] = (
            hulls[0][0].x + hulls[0][1].x + hulls[0][2].x,
            hulls[0][0].y + hulls[0][1].y + hulls[0][2].y,
            hulls[1][0].x + hulls[1][1].x + hulls[1][2].x,
            hulls[1][0].y + hulls[1][1].y + hulls[1][2].y,
        )
        px, py, qx, qy = self.seam_ints
        self.seam_box = (min(px, qx) // 3, min(py, qy) // 3, -(-max(px, qx) // 3), -(-max(py, qy) // 3))
        self.nodes: dict[Q, int] = {}
        self.parent: list[int] = []
        self.flip: list[int] = []
        self.zero = False  # a closed run at no cost separates the ports
        self.sites: list[_Site] = []
        self.chords: dict[tuple[int, int, int], _Chord] = {}
        self.hull_chords: list[tuple[Q, Q]] = []  # the parts of hull edges that lie in copper
        self.near_edges: tuple[list[tuple[int, Point, Point]], list[tuple[int, Point, Point]]] = ([], [])

    # --- union-find with parity -------------------------------------------------------------------

    def node(self, point: Q) -> int:
        found = self.nodes.get(point)
        if found is None:
            found = self.nodes[point] = len(self.parent)
            self.parent.append(found)
            self.flip.append(0)
        return found

    def find(self, node: int) -> tuple[int, int]:
        """The root of ``node`` and the parity of the run at no cost from the root to it."""
        if self.parent[node] == node:
            return node, 0
        path: list[int] = []
        while self.parent[node] != node:
            path.append(node)
            node = self.parent[node]
        parity = 0
        for item in reversed(path):
            parity ^= self.flip[item]
            self.parent[item], self.flip[item] = node, parity
        return node, self.flip[path[0]]

    def link(self, first: int, second: int, odd: int) -> None:
        """The nodes are joined by a run at no cost that crosses the seam ``odd`` times."""
        (root_x, par_x), (root_y, par_y) = self.find(first), self.find(second)
        odd ^= par_x ^ par_y
        if root_x == root_y:
            self.zero = self.zero or bool(odd)
            return
        self.parent[root_y], self.flip[root_y] = root_x, odd

    def join(self, x: Q, y: Q) -> None:
        self.link(self.node(x), self.node(y), self.odd(x, y))

    def sign(self, x: N, y: N) -> N:
        """The side of the seam's line on which the point lies, scaled: 0 counts as positive."""
        px, py, qx, qy = self.seam_ints
        return (qx - px) * (y * self.seam_scale - py) - (qy - py) * (x * self.seam_scale - px)

    def odd(self, x: Q, y: Q) -> int:
        """1 when the segment ``x–y`` crosses the seam, a point on a line counting as on its positive
        side."""
        if (self.sign(x[0], x[1]) >= 0) == (self.sign(y[0], y[1]) >= 0):
            return 0
        px, py, qx, qy = self.seam_ints
        scale = self.seam_scale
        dx, dy = y[0] - x[0], y[1] - x[1]
        at_p = dx * (py - x[1] * scale) - dy * (px - x[0] * scale)
        at_q = dx * (qy - x[1] * scale) - dy * (qx - x[0] * scale)
        return int((at_p >= 0) != (at_q >= 0))

    def side(self, box: tuple[int, int, int, int]) -> int:
        """1 or −1 when the box lies strictly on one side of the seam's line, else 0. A chord between two
        sites of the same side crosses no seam."""
        signs = set[int]()
        for x, y in ((box[0], box[1]), (box[2], box[1]), (box[2], box[3]), (box[0], box[3])):
            value = self.sign(x, y)
            signs.add((value > 0) - (value < 0))
        return signs.pop() if len(signs) == 1 else 0

    def site(self, a: Q, b: Q, hull: int = -1) -> None:
        box = _box((a, b))
        whole = all(value.denominator == 1 for value in (*a, *b))
        ints = (int(a[0]), int(a[1]), int(b[0]), int(b[1])) if whole else None
        self.sites.append(_Site(a, b, self.node(a), box, hull, ints, self.side(box)))

    # --- the pieces -------------------------------------------------------------------------------

    def cut_rings(self) -> None:
        """Every ring edge, cut where a hull meets it; the parts not strictly inside a hull are runs at
        no cost and sites."""
        for r, ring in enumerate(self.rings):
            count = len(ring)
            positive = [self.sign(p.x, p.y) >= 0 for p in ring]
            ids = [self.node((p.x, p.y)) for p in ring]
            for i, u in enumerate(ring):
                j = (i + 1) % count
                v = ring[j]
                box = (min(u.x, v.x), min(u.y, v.y), max(u.x, v.x), max(u.y, v.y))
                near = [k for k in (0, 1) if _boxes_meet(box, self.hull_boxes[k])]
                if not near:  # the usual edge: far from both hulls, its ends stored points
                    a, b = (u.x, u.y), (v.x, v.y)
                    self.link(ids[i], ids[j], 0 if positive[i] == positive[j] else self.odd(a, b))
                    side = 0
                    if positive[i] == positive[j]:
                        side = self.side(box)
                    self.sites.append(_Site(a, b, ids[i], box, -1, (u.x, u.y, v.x, v.y), side))
                    continue
                if any(
                    _strictly_inside((u.x, u.y), self.qhulls[k])
                    and _strictly_inside((v.x, v.y), self.qhulls[k])
                    for k in near
                ):  # change c0503: an edge strictly inside a convex hull has no part outside it
                    for k in near:
                        self.near_edges[k].append((r, u, v))
                    continue
                stops = {_ZERO, _ONE}
                for k in near:
                    self.near_edges[k].append((r, u, v))
                    hull = self.hulls[k]
                    for h, c in enumerate(hull):
                        stops.update(cuts(u, v, c, hull[(h + 1) % len(hull)]))
                ordered = sorted(stops)
                dx, dy = v.x - u.x, v.y - u.y
                points: list[Q] = [(u.x + t * dx, u.y + t * dy) for t in ordered]
                for first, second in zip(points, points[1:], strict=False):
                    middle: Q = (Fraction(first[0] + second[0], 2), Fraction(first[1] + second[1], 2))
                    if any(_strictly_inside(middle, self.qhulls[k]) for k in near):
                        continue
                    self.join(first, second)
                    self.site(first, second)

    def cut_hulls(self) -> None:
        """Every hull edge, cut where a ring meets it: a part in a hole or outside the outer ring is a run
        at no cost, a part in copper is a chord; every hull vertex is a site."""
        for k, hull in enumerate(self.hulls):
            cutting: set[int] = set()  # the rings that meet the boundary of this hull
            parts: list[tuple[Q, Q]] = []
            for h, c in enumerate(hull):
                d = hull[(h + 1) % len(hull)]
                box = (min(c.x, d.x), min(c.y, d.y), max(c.x, d.x), max(c.y, d.y))
                stops = {_ZERO, _ONE}
                for r, u, v in self.near_edges[k]:
                    if max(u.x, v.x) < box[0] or min(u.x, v.x) > box[2]:
                        continue
                    if max(u.y, v.y) < box[1] or min(u.y, v.y) > box[3]:
                        continue
                    found = cuts(c, d, u, v)
                    if found:
                        cutting.add(r)
                        stops.update(found)
                ordered = sorted(stops)
                dx, dy = d.x - c.x, d.y - c.y
                points: list[Q] = [(c.x + t * dx, c.y + t * dy) for t in ordered]
                self.site((c.x, c.y), (c.x, c.y), k)
                parts += zip(points, points[1:], strict=False)
            # a ring that does not meet the hull's boundary has the whole hull on one side
            apart = [r for r in range(len(self.rings)) if r not in cutting]
            if any(self.in_free(_q(hull[0]), r) for r in apart if self.may_hold(r, k)):
                for first, second in parts:
                    self.join(first, second)
                continue
            for first, second in parts:
                middle: Q = (Fraction(first[0] + second[0], 2), Fraction(first[1] + second[1], 2))
                if any(self.in_free(middle, r) for r in sorted(cutting)):
                    self.join(first, second)
                else:
                    self.node(first)
                    self.node(second)
                    self.hull_chords.append((first, second))

    def may_hold(self, r: int, k: int) -> bool:
        """Whether the hull can lie in the free space of ring ``r``: always for the outer ring, and for a
        hole only when its box meets the hull's."""
        if r == 0:
            return True
        ring = self.rings[r]
        box = (min(p.x for p in ring), min(p.y for p in ring), max(p.x for p in ring), max(p.y for p in ring))
        return _boxes_meet(box, self.hull_boxes[k])

    def in_free(self, point: Q, r: int) -> bool:
        """Whether ``point`` lies strictly outside the outer ring (``r`` 0) or strictly inside hole ``r``."""
        where = located(point, self.rings[r])
        return where is Location.OUTSIDE if r == 0 else where is Location.INSIDE

    # --- chords -----------------------------------------------------------------------------------

    def end(self, site: _Site, point: Q) -> int:
        """The parity of the run at no cost from the site's root to ``point`` on it."""
        parity = self.find(site.node)[1]
        return parity ^ (0 if point == site.a else self.odd(site.a, point))

    def store(self, first: int, second: int, odd: int, dist2: N, x: Q, y: Q) -> None:
        if first == second and not odd:
            return
        if first > second:
            first, second, x, y = second, first, y, x
        key = (first, second, odd)
        held = self.chords.get(key)
        if held is None or dist2 < held[1]:
            self.chords[key] = (floor_sqrt(dist2 * (1 << (2 * SCALE_BITS))), dist2, x, y)

    def find_chords(self, reach: int) -> None:
        """The shortest chord of each parity between each two nodes, among the closest points of every
        two sites nearer than ``reach``.

        Change c0503: a first pass keeps, from the integer distances alone, the pairs that may hold the
        shortest chord of their nodes and parity; a second pass measures those in order of distance, then
        of the pair's sites, so each chord kept is the first shortest in the order of the sites, as a
        single pass over the sites in order keeps."""
        for x, y in self.hull_chords:
            (root_x, par_x), (root_y, par_y) = self.find(self.nodes[x]), self.find(self.nodes[y])
            self.store(root_x, root_y, par_x ^ par_y ^ self.odd(x, y), sq_dist(x, y), x, y)
        sites = self.sites
        index = SpatialIndex[int].build((BBox(*site.box), i) for i, site in enumerate(sites))
        found = [self.find(site.node) for site in sites]
        roots = [item[0] for item in found]
        parities = [item[1] for item in found]
        reach2 = reach * reach
        seam = self.seam_box
        hull_boxes = self.hull_boxes
        # the distance, as a numerator and a denominator, of the nearest pair seen whose chord surely counts
        # (its sites' boxes miss both hulls), per pair of nodes and parity
        nearest: dict[tuple[int, int, int], tuple[int, int]] = {
            key: (chord[1].numerator, chord[1].denominator) for key, chord in self.chords.items()
        }
        candidates: list[tuple[int, int, int, int, int, int, int, int | None, tuple[N, Q, Q] | None]] = []
        boxes = [site.box for site in sites]
        sides = [site.side for site in sites]
        hull_of = [site.hull for site in sites]
        ints_of = [site.ints for site in sites]
        h0, h1 = hull_boxes
        s0, s1, s2, s3 = seam
        for i, site in enumerate(sites):
            box = boxes[i]
            bx0, by0, bx1, by1 = box
            grown = BBox(bx0 - reach, by0 - reach, bx1 + reach, by1 + reach)
            root_i, par_i, side_i, ints_i, hull_i = roots[i], parities[i], sides[i], ints_of[i], hull_of[i]
            near = index.query(grown)
            for j in near[bisect_right(near, i) :]:
                far = boxes[j]
                fx0, fy0, fx1, fy1 = far
                gx = fx0 - bx1 if fx0 > bx1 else bx0 - fx1 if bx0 > fx1 else 0
                gy = fy0 - by1 if fy0 > by1 else by0 - fy1 if by0 > fy1 else 0
                gap2 = gx * gx + gy * gy
                if gap2 >= reach2:
                    continue
                root_j = roots[j]
                known: int | None = None
                if side_i != 0 and side_i == sides[j]:
                    known = par_i ^ parities[j]
                elif (
                    min(bx0, fx0) > s2 or max(bx1, fx1) < s0 or min(by0, fy0) > s3 or max(by1, fy1) < s1
                ):  # a chord inside a box that the seam's box does not meet crosses no seam either
                    known = par_i ^ parities[j]
                if known == 0 and root_i == root_j:
                    continue
                if hull_i >= 0 and hull_i == hull_of[j]:
                    continue  # two vertices of one hull: its edge is a chord already, a diagonal enters it
                span = (min(bx0, fx0), min(by0, fy0), max(bx1, fx1), max(by1, fy1))
                clear: bool | None = None
                if known is None:
                    clear = not (_boxes_meet(span, h0) or _boxes_meet(span, h1))
                    if clear:
                        # the loop a_i, x, y, a_j lies in the sites' boxes, which hold neither end of the
                        # seam, so it crosses the seam an even number of times: the chord has the parity
                        # of a_i–a_j
                        known = par_i ^ parities[j] ^ self.odd(site.a, sites[j].a)
                        if known == 0 and root_i == root_j:
                            continue
                pair = (root_i, root_j) if root_i <= root_j else (root_j, root_i)
                if known is not None:
                    held = nearest.get((*pair, known))
                    if held is not None and gap2 * held[1] >= held[0]:
                        continue
                    helds = [held]
                else:
                    helds = [nearest.get((*pair, odd)) for odd in ((1,) if root_i == root_j else (0, 1))]
                    if all(held is not None and gap2 * held[1] >= held[0] for held in helds):
                        continue
                cached: tuple[N, Q, Q] | None = None
                ints_j = ints_of[j]
                if ints_i is not None and ints_j is not None:
                    top, bottom = _dist2_int(ints_i, ints_j)
                else:
                    other = sites[j]
                    cached = closest(site.a, site.b, other.a, other.b)
                    top, bottom = cached[0].numerator, cached[0].denominator
                if top >= reach2 * bottom or (top == 0 and root_i == root_j):
                    continue
                if all(held is not None and top * held[1] >= held[0] * bottom for held in helds):
                    continue
                if known is not None:
                    if clear is None:
                        clear = not (_boxes_meet(span, h0) or _boxes_meet(span, h1))
                    if clear:
                        nearest[(*pair, known)] = (top, bottom)
                candidates.append(((top << 64) // bottom, *pair, i, j, top, bottom, known, cached))
        candidates.sort(key=lambda item: (item[1], item[2], item[0], item[3], item[4]))
        chords = self.chords
        for _, first, second, i, j, top, bottom, known, cached in candidates:
            site, other = sites[i], sites[j]
            odds = (known,) if known is not None else (1,) if first == second else (0, 1)
            helds = [chords.get((first, second, odd)) for odd in odds]
            if all(
                held is not None and top * held[1].denominator >= held[1].numerator * bottom for held in helds
            ):
                continue
            if cached is not None:
                dist2, x, y = cached
            else:
                ints_a, ints_b = site.ints, other.ints
                assert ints_a is not None and ints_b is not None
                dist2, x, y = _closest_ints(ints_a, ints_b)
            span = _box((x, y))
            if any(_boxes_meet(span, hull_boxes[k]) and _enters(x, y, self.hulls[k]) for k in (0, 1)):
                continue
            if known is None:
                known = self.end(site, x) ^ self.end(other, y) ^ self.odd(x, y)
            self.store(roots[i], roots[j], known, dist2, x, y)

    # --- the shortest odd cycle -------------------------------------------------------------------

    def shortest(self, bound: int) -> tuple[int, list[_Chord]] | None:
        """The chords of the shortest closed walk of odd parity whose scaled length is below ``bound``."""
        links: dict[int, list[tuple[int, int, _Chord]]] = {}
        starts: set[int] = set()
        best: tuple[int, list[_Chord]] | None = None
        for (first, second, odd), chord in sorted(self.chords.items(), key=lambda item: item[0]):
            if first == second:
                if chord[0] < bound:
                    bound, best = chord[0], (chord[0], [chord])
                continue
            links.setdefault(first, []).append((second, odd, chord))
            links.setdefault(second, []).append((first, odd, (chord[0], chord[1], chord[3], chord[2])))
            if odd:
                starts.add(first)
        removed: set[int] = set()
        for start in sorted(starts):
            found = self._cycle(start, links, removed, bound)
            if found is not None:
                bound, best = found[0], found
            removed.add(start)
        return best

    def _cycle(
        self, start: int, links: dict[int, list[tuple[int, int, _Chord]]], removed: set[int], bound: int
    ) -> tuple[int, list[_Chord]] | None:
        origin, goal = (start, 0), (start, 1)
        dist: dict[tuple[int, int], int] = {origin: 0}
        before: dict[tuple[int, int], tuple[tuple[int, int], _Chord]] = {}
        done: set[tuple[int, int]] = set()
        heap: list[tuple[int, int, int]] = [(0, start, 0)]
        while heap:
            here, node, parity = heapq.heappop(heap)
            state = (node, parity)
            if state in done:
                continue
            done.add(state)
            if state == goal:
                break
            for other, odd, chord in links.get(node, ()):
                if other in removed:
                    continue
                reached = (other, parity ^ odd)
                total = here + chord[0]
                if total >= bound or reached in done or reached == origin:
                    continue
                if reached not in dist or total < dist[reached]:
                    dist[reached] = total
                    before[reached] = (state, chord)
                    heapq.heappush(heap, (total, other, parity ^ odd))
        if goal not in dist:
            return None
        chords: list[_Chord] = []
        state = goal
        while state != origin:
            state, chord = before[state]
            chords.append(chord)
        chords.reverse()
        return dist[goal], chords


def _covered(point: Q, shapes: Sequence[Thick]) -> bool:
    """Whether ``point`` (rounded to a nanometre) lies on the copper of one of the shapes."""
    spot = Thick((round_point(point[0], point[1]),), 2)
    return any(thick_touch(spot, shape) or thick_closer_than(spot, shape, 2) for shape in shapes)


def _hull_free(region: FillRegion, port: Port, hull: Ring) -> bool:
    """False when a ring of the region has a part strictly inside the hull that the port's own shapes do
    not cover: a hole, or the outside, then lies inside the hull between the shapes."""
    if len(port.shapes) == 1 and len(port.shapes[0].core) <= 2:
        return True  # a disc or a straight track is convex: its hull is its own copper
    qhull = tuple(_q(p) for p in hull)
    box = _box(qhull)
    for ring in (region.outer, *region.holes):
        for i, u in enumerate(ring):
            v = ring[(i + 1) % len(ring)]
            if not _boxes_meet((min(u.x, v.x), min(u.y, v.y), max(u.x, v.x), max(u.y, v.y)), box):
                continue
            stops = {_ZERO, _ONE}
            for j, c in enumerate(hull):
                stops.update(cuts(u, v, c, hull[(j + 1) % len(hull)]))
            ordered = sorted(stops)
            for first, second in zip(ordered, ordered[1:], strict=False):
                t = (first + second) / 2
                middle: Q = (u.x + t * (v.x - u.x), u.y + t * (v.y - u.y))
                if _strictly_inside(middle, qhull) and not _covered(middle, port.shapes):
                    return False
    return True


def _perimeter(hull: Ring) -> int:
    """The scaled perimeter of a hull, rounded up."""
    total = 0
    for i, point in enumerate(hull):
        dx, dy = point.x - hull[i - 1].x, point.y - hull[i - 1].y
        total += ceil_sqrt((dx * dx + dy * dy) << (2 * SCALE_BITS))
    return total


def narrowest_section(
    region: FillRegion, a: Port, b: Port, *, arc_tol: int = ARC_TOL_NM, limit: int | None = None
) -> Section:
    """The narrowest copper section of ``region`` between the ports ``a`` and ``b``. With ``limit``, a
    section of at least ``limit`` is reported as bounded: ``low == limit`` and ``high`` ``None``."""
    hull_a, hull_b = port_hull(a, arc_tol=arc_tol), port_hull(b, arc_tol=arc_tol)
    items = (a.where, b.where)
    bands = a.band + b.band
    if len(hull_a) < 3 or len(hull_b) < 3 or area2(hull_a) == 0 or area2(hull_b) == 0:
        return Section(Measure(0, 0, region.layer, (), items), True)
    if thick_touch(Thick(hull_a, 0, filled=True), Thick(hull_b, 0, filled=True)):
        return Section(Measure(0, 0, region.layer, (), items), True)
    free = _hull_free(region, a, hull_a) and _hull_free(region, b, hull_b)
    search = _Search(region, (hull_a, hull_b))
    search.cut_rings()
    search.cut_hulls()
    if search.zero:
        return Section(Measure(0, 0, region.layer, (), items), free)
    around = min(_perimeter(hull_a), _perimeter(hull_b))
    bound = around + 1
    if limit is not None:
        bound = min(bound, limit << SCALE_BITS)
    search.find_chords((bound >> SCALE_BITS) + 1)
    found = search.shortest(bound)
    if found is None:
        if limit is not None and (limit << SCALE_BITS) <= around:
            return Section(Measure(limit, None, region.layer, (), items, True), free)
        smaller = hull_a if _perimeter(hull_a) <= _perimeter(hull_b) else hull_b
        ring = [_q(p) for p in smaller]
        chords = [(0, sq_dist(ring[i - 1], p), ring[i - 1], p) for i, p in enumerate(ring)]
    else:
        chords = found[1]
    low = sum(floor_sqrt(chord[1]) for chord in chords)
    high = sum(ceil_sqrt(chord[1]) for chord in chords)
    points = tuple(round_point(end[0], end[1]) for chord in chords for end in (chord[2], chord[3]))
    return Section(Measure(max(0, low - bands), high + bands, region.layer, points, items), free)


__all__ = ["SCALE_BITS", "Port", "Section", "narrowest_section", "port_hull"]
