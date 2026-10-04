# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Thick shapes: an integer core swept by a disc, and exact gaps between two of them.

A ``Thick`` is the set of points within ``width / 2`` of its core, boundary included. The core is one
point (a disc), an open polyline (a stadium, or a chain of them) or a filled ring (a region grown by
``width / 2``). The gap of two shapes is ``dist(core_a, core_b) − (width_a + width_b) / 2``. Doubling
every length makes the half-widths integers, so each question is a comparison between ``4·dist²``, an
exact rational, and the square of an integer: nothing here forms a floating-point number or takes a
square root other than an exact integer one. See ``docs/geometry.md``, "Thick shapes".
"""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass, field
from fractions import Fraction

from fenolite.geometry.errors import GeometryError
from fenolite.geometry.index import SpatialIndex
from fenolite.geometry.polygon import Polygon
from fenolite.geometry.predicates import Location, floor_sqrt, point_in_ring, round_point
from fenolite.geometry.shapes import BBox
from fenolite.geometry.vector import Point, require_point

INDEX_FROM = 16
"""A core with at least this many pieces gets a spatial index of its pieces, built on first use."""
_Seg = tuple[int, int, int, int]
_Frac = tuple[Fraction, Fraction]


@dataclass(frozen=True, slots=True)
class Thick:
    """The points within ``width / 2`` of ``core``: one point, an open polyline (``filled`` false), or the
    closed region of a ring under the non-zero rule (``filled`` true)."""

    core: tuple[Point, ...]
    width: int
    filled: bool = False
    _pieces: tuple[_Seg, ...] | None = field(default=None, init=False, repr=False, compare=False)
    _tree: SpatialIndex[int] | None = field(default=None, init=False, repr=False, compare=False)
    _box: BBox | None = field(default=None, init=False, repr=False, compare=False)

    def __post_init__(self) -> None:
        if type(self.width) is not int or self.width < 0:
            raise ValueError(f"the width of a thick shape is an int of at least 0, got {self.width!r}")
        core = tuple(self.core)
        object.__setattr__(self, "core", core)
        for i, point in enumerate(core):
            require_point(point, f"core[{i}]")
        if not core:
            raise GeometryError("a thick shape needs a core of at least one point")
        if self.filled:
            Polygon(core)  # refuses fewer than three points, repeated points and a zero area
        elif len(core) == 1 and self.width == 0:
            raise GeometryError("a core of one point with width 0 is empty", points=core)


def _segments(t: Thick) -> tuple[_Seg, ...]:
    """The core's pieces as ``(ax, ay, bx, by)``: the edges of a ring, the segments of a polyline, or one
    degenerate segment for a single point. Built on first use."""
    found = t._pieces  # pyright: ignore[reportPrivateUsage]
    if found is None:
        core = t.core
        count = len(core)
        if count == 1:
            found = ((core[0].x, core[0].y, core[0].x, core[0].y),)
        else:
            last = count if t.filled else count - 1
            found = tuple(
                (core[i].x, core[i].y, core[(i + 1) % count].x, core[(i + 1) % count].y) for i in range(last)
            )
        object.__setattr__(t, "_pieces", found)
    return found


def _index(t: Thick) -> SpatialIndex[int] | None:
    """The index of the core's pieces, built on first use, or ``None`` for a core with few pieces."""
    segments = _segments(t)
    if len(segments) < INDEX_FROM:
        return None
    found = t._tree  # pyright: ignore[reportPrivateUsage]
    if found is None:
        found = SpatialIndex[int].build((_piece_box(s, 0), i) for i, s in enumerate(segments))
        object.__setattr__(t, "_tree", found)
    return found


def _core_box(t: Thick) -> BBox:
    found = t._box  # pyright: ignore[reportPrivateUsage]
    if found is None:
        found = BBox.of_points(t.core)
        object.__setattr__(t, "_box", found)
    return found


def _piece_box(s: _Seg, grow: int) -> BBox:
    return BBox(
        min(s[0], s[2]) - grow, min(s[1], s[3]) - grow, max(s[0], s[2]) + grow, max(s[1], s[3]) + grow
    )


def thick_bbox(t: Thick) -> BBox:
    """The box of the core grown by ``⌈width / 2⌉`` on every side: it contains the shape."""
    return _core_box(t).inflate((t.width + 1) // 2)


# --- exact comparisons on integers ----------------------------------------------------------------


def _orient(ax: int, ay: int, bx: int, by: int, cx: int, cy: int) -> int:
    return (bx - ax) * (cy - ay) - (by - ay) * (cx - ax)


def _sign(value: int) -> int:
    return (value > 0) - (value < 0)


def _on(px: int, py: int, s: _Seg) -> bool:
    """``(px, py)`` on the closed segment ``s`` (a degenerate segment is its point)."""
    if _orient(s[0], s[1], s[2], s[3], px, py) != 0:
        return False
    return min(s[0], s[2]) <= px <= max(s[0], s[2]) and min(s[1], s[3]) <= py <= max(s[1], s[3])


def _meet(s: _Seg, t: _Seg) -> bool:
    """Whether two closed segments share a point."""
    if (s[0], s[1]) == (s[2], s[3]):
        return _on(s[0], s[1], t)
    if (t[0], t[1]) == (t[2], t[3]):
        return _on(t[0], t[1], s)
    o1 = _sign(_orient(s[0], s[1], s[2], s[3], t[0], t[1]))
    o2 = _sign(_orient(s[0], s[1], s[2], s[3], t[2], t[3]))
    if o1 == 0 and o2 == 0:  # collinear: compare the ranges along the line, lexicographically
        s0, s1 = sorted(((s[0], s[1]), (s[2], s[3])))
        t0, t1 = sorted(((t[0], t[1]), (t[2], t[3])))
        return max(s0, t0) <= min(s1, t1)
    if o1 == o2:
        return False
    o3 = _sign(_orient(t[0], t[1], t[2], t[3], s[0], s[1]))
    o4 = _sign(_orient(t[0], t[1], t[2], t[3], s[2], s[3]))
    return o3 != o4


def _point_within(px: int, py: int, s: _Seg, reach2: int, strict: bool) -> bool:
    """``4·dist²((px, py), s)`` below ``reach2`` (strictly, or at most)."""
    dx, dy = s[2] - s[0], s[3] - s[1]
    ex, ey = px - s[0], py - s[1]
    length2 = dx * dx + dy * dy
    along = ex * dx + ey * dy
    if length2 == 0 or along <= 0:
        value, scale = 4 * (ex * ex + ey * ey), 1
    elif along >= length2:
        fx, fy = px - s[2], py - s[3]
        value, scale = 4 * (fx * fx + fy * fy), 1
    else:
        cr = dx * ey - dy * ex
        value, scale = 4 * cr * cr, length2
    return value < reach2 * scale if strict else value <= reach2 * scale


def _pair_within(s: _Seg, t: _Seg, reach2: int, strict: bool) -> bool:
    """``4·dist²(s, t)`` below ``reach2`` (strictly, or at most); segments that meet are at distance 0."""
    if _meet(s, t):
        return reach2 > 0 or not strict
    return (
        _point_within(s[0], s[1], t, reach2, strict)
        or _point_within(s[2], s[3], t, reach2, strict)
        or _point_within(t[0], t[1], s, reach2, strict)
        or _point_within(t[2], t[3], s, reach2, strict)
    )


def _dist2_point(px: int, py: int, s: _Seg) -> Fraction:
    dx, dy = s[2] - s[0], s[3] - s[1]
    ex, ey = px - s[0], py - s[1]
    length2 = dx * dx + dy * dy
    along = ex * dx + ey * dy
    if length2 == 0 or along <= 0:
        return Fraction(ex * ex + ey * ey)
    if along >= length2:
        fx, fy = px - s[2], py - s[3]
        return Fraction(fx * fx + fy * fy)
    cr = dx * ey - dy * ex
    return Fraction(cr * cr, length2)


def _dist2(s: _Seg, t: _Seg) -> Fraction:
    """The exact squared distance between two closed segments (0 when they meet)."""
    if _meet(s, t):
        return Fraction(0)
    return min(
        _dist2_point(s[0], s[1], t),
        _dist2_point(s[2], s[3], t),
        _dist2_point(t[0], t[1], s),
        _dist2_point(t[2], t[3], s),
    )


# --- pieces that can matter -----------------------------------------------------------------------


def _candidates(a: Thick, b: Thick, reach: int) -> Iterator[tuple[int, int]]:
    """Index pairs ``(i, j)`` of the pieces of ``a`` and ``b`` whose boxes are within ``reach`` of each
    other. Every pair of pieces closer than ``reach`` is among them."""
    sa, sb = _segments(a), _segments(b)
    index_a, index_b = _index(a), _index(b)
    if index_b is not None and (index_a is None or len(sb) >= len(sa)):
        for i, s in enumerate(sa):
            for j in index_b.query(_piece_box(s, reach)):
                yield i, j
        return
    if index_a is not None:
        for j, s in enumerate(sb):
            for i in index_a.query(_piece_box(s, reach)):
                yield i, j
        return
    for i, s in enumerate(sa):
        x0, y0 = min(s[0], s[2]) - reach, min(s[1], s[3]) - reach
        x1, y1 = max(s[0], s[2]) + reach, max(s[1], s[3]) + reach
        for j, t in enumerate(sb):
            if min(t[0], t[2]) > x1 or max(t[0], t[2]) < x0 or min(t[1], t[3]) > y1 or max(t[1], t[3]) < y0:
                continue
            yield i, j


def _inside(point: Point, t: Thick) -> bool:
    """``point`` in the closed region of a filled core."""
    box = _core_box(t)
    if not t.filled or not box.contains_point(point):
        return False
    index = _index(t)
    if index is None:
        return point_in_ring(point, t.core) != Location.OUTSIDE
    # The winding number, from the edges that the horizontal line through the point meets: the same
    # half-open crossing rule as ``point_in_ring``, without visiting every edge of a large ring.
    px, py = point.x, point.y
    segments = _segments(t)
    winding = 0
    for i in index.query(BBox(box.x0, py, box.x1, py)):
        s = segments[i]
        side = _orient(s[0], s[1], s[2], s[3], px, py)
        if (
            side == 0
            and min(s[0], s[2]) <= px <= max(s[0], s[2])
            and min(s[1], s[3]) <= py <= max(s[1], s[3])
        ):
            return True  # on the ring
        if s[1] <= py:
            if s[3] > py and side > 0:
                winding += 1
        elif s[3] <= py and side < 0:
            winding -= 1
    return winding != 0


def _contained(a: Thick, b: Thick) -> bool:
    """One core lies inside the other's filled region. Called when no pieces meet: a core is connected,
    so it is then wholly inside or wholly outside, and one of its points decides."""
    return _inside(b.core[0], a) or _inside(a.core[0], b)


def _within(a: Thick, b: Thick, reach: int, strict: bool) -> bool:
    """``2·dist(core_a, core_b)`` below ``reach`` (strictly, or at most), ``reach`` at least 0."""
    if strict and reach == 0:
        return False
    grow = reach // 2 + 1
    if not _core_box(a).inflate(grow).intersects(_core_box(b)):
        return False  # the cores are farther apart than reach / 2 along an axis
    sa, sb = _segments(a), _segments(b)
    reach2 = reach * reach
    for i, j in _candidates(a, b, grow):
        if _pair_within(sa[i], sb[j], reach2, strict):
            return True
    return _contained(a, b)


def thick_touch(a: Thick, b: Thick) -> bool:
    """Whether the two shapes share a point: the gap is at most 0."""
    return _within(a, b, a.width + b.width, strict=False)


def thick_closer_than(a: Thick, b: Thick, limit: int) -> bool:
    """Whether the gap is strictly below ``limit`` nanometres (``limit`` an ``int`` of at least 0)."""
    if type(limit) is not int or limit < 0:
        raise ValueError(f"the limit is an int of at least 0, got {limit!r}")
    return _within(a, b, 2 * limit + a.width + b.width, strict=True)


# --- the exact distance and where it is ---------------------------------------------------------


def _ordered(a: Thick, b: Thick) -> tuple[Thick, Thick]:
    """The two shapes in one order whichever way they were given."""
    return (a, b) if (a.core, a.width, a.filled) <= (b.core, b.width, b.filled) else (b, a)


def _closest(a: Thick, b: Thick) -> tuple[Fraction, int, int]:
    """``(dist², i, j)`` of the first closest pair of pieces, the pieces taken in core order.

    For cores with many pieces the search widens: the pairs whose boxes are within ``reach`` hold every
    pair closer than ``reach``, so once their smallest distance is at most ``reach`` it is the smallest
    of all, and no pair outside them can tie with it."""
    sa, sb = _segments(a), _segments(b)
    if len(sa) * len(sb) <= INDEX_FROM * INDEX_FROM or (_index(a) is None and _index(b) is None):
        best, at = _dist2(sa[0], sb[0]), (0, 0)
        for i, s in enumerate(sa):
            for j, t in enumerate(sb):
                found = _dist2(s, t)
                if found < best:
                    best, at = found, (i, j)
        return best, at[0], at[1]
    box_a, box_b = _core_box(a), _core_box(b)
    apart = max(box_a.x0 - box_b.x1, box_b.x0 - box_a.x1, box_a.y0 - box_b.y1, box_b.y0 - box_a.y1, 0)
    reach = apart + 1
    while True:
        closest: tuple[Fraction, int, int] | None = None
        for i, j in _candidates(a, b, reach):
            found = _dist2(sa[i], sb[j])
            if closest is None or (found, i, j) < closest:
                closest = (found, i, j)
        if closest is not None and closest[0] <= reach * reach:
            return closest
        reach *= 4


def _distance2(a: Thick, b: Thick) -> tuple[Fraction, int, int]:
    """``_closest``, with distance 0 when one core lies inside the other's filled region."""
    best, i, j = _closest(a, b)
    if best > 0 and _contained(a, b):
        return Fraction(0), -1, -1
    return best, i, j


def thick_gap_floor(a: Thick, b: Thick) -> int:
    """``⌊gap⌋`` in nanometres when the gap is positive, and 0 otherwise."""
    first, second = _ordered(a, b)
    quadruple = 4 * _distance2(first, second)[0]
    total = a.width + b.width
    if quadruple <= total * total:
        return 0
    return (floor_sqrt(quadruple) - total) // 2


def _nearest_on(px: Fraction | int, py: Fraction | int, s: _Seg) -> _Frac:
    """The point of the closed segment ``s`` nearest to ``(px, py)``."""
    dx, dy = s[2] - s[0], s[3] - s[1]
    length2 = dx * dx + dy * dy
    if length2 == 0:
        return Fraction(s[0]), Fraction(s[1])
    along = Fraction((px - s[0]) * dx + (py - s[1]) * dy, length2)
    along = min(max(along, Fraction(0)), Fraction(1))
    return s[0] + along * dx, s[1] + along * dy


def _common(s: _Seg, t: _Seg) -> _Frac:
    """A point that two meeting segments share: their crossing, or for collinear segments the first
    point of the shared piece in lexicographic order."""
    rx, ry = s[2] - s[0], s[3] - s[1]
    qx, qy = t[2] - t[0], t[3] - t[1]
    denominator = rx * qy - ry * qx
    if denominator != 0:
        along = Fraction((t[0] - s[0]) * qy - (t[1] - s[1]) * qx, denominator)
        return s[0] + along * rx, s[1] + along * ry
    for px, py in sorted(((s[0], s[1]), (s[2], s[3]), (t[0], t[1]), (t[2], t[3]))):
        if _on(px, py, s) and _on(px, py, t):
            return Fraction(px), Fraction(py)
    raise AssertionError("the segments do not meet")


def _closest_points(s: _Seg, t: _Seg, dist2: Fraction) -> tuple[_Frac, _Frac]:
    """The first pair of points of two disjoint segments at their distance: an end of one segment and
    its nearest point on the other, the ends taken in order."""
    for px, py, other, flip in (
        (s[0], s[1], t, False),
        (s[2], s[3], t, False),
        (t[0], t[1], s, True),
        (t[2], t[3], s, True),
    ):
        if _dist2_point(px, py, other) == dist2:
            end = (Fraction(px), Fraction(py))
            near = _nearest_on(px, py, other)
            return (near, end) if flip else (end, near)
    raise AssertionError("no end of the segments is at their distance")


def thick_witness(a: Thick, b: Thick) -> Point:
    """Where the two shapes are closest: the rounded midpoint of the first closest pair of core points,
    the pieces taken in core order; for cores that meet, a rounded common point."""
    first, second = _ordered(a, b)
    dist2, i, j = _distance2(first, second)
    if i < 0:  # one core inside the other's region
        inner = second.core[0] if _inside(second.core[0], first) else first.core[0]
        return inner
    s, t = _segments(first)[i], _segments(second)[j]
    if dist2 == 0:
        return round_point(*_common(s, t))
    (ax, ay), (bx, by) = _closest_points(s, t, dist2)
    return round_point((ax + bx) / 2, (ay + by) / 2)


__all__ = ["Thick", "thick_bbox", "thick_closer_than", "thick_gap_floor", "thick_touch", "thick_witness"]
