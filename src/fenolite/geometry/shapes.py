# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Closed integer boxes, segments, three-point arcs and circles, and their polygonisation.

An ``Arc`` is its three stored points; the centre and squared radius are exact derived values that
no rule decision should rely on (they are badly conditioned for shallow arcs). Polygonisation never
uses floating-point trigonometry: parts of the curve are bisected uniformly, each new vertex is the
projection of a chord midpoint on the circle computed with ``math.isqrt`` on numbers scaled by 2**64
and rounded half to even, until the exact sagitta of every chord is at most ``tol``.
"""

from __future__ import annotations

import math
from collections.abc import Iterable
from dataclasses import dataclass, field
from fractions import Fraction

from fenolite.geometry.errors import DEGENERATE, GeometryError, format_point
from fenolite.geometry.predicates import ceil_sqrt, floor_sqrt, round_point
from fenolite.geometry.vector import Point, require_int, require_point

DEFAULT_TOL = 5000
"""Default maximum chord error in nm: KiCad's default arc approximation error, 0.005 mm (S-0010)."""
MAX_BISECTION_DEPTH = 32
_SCALE_BITS = 64


@dataclass(frozen=True, slots=True)
class BBox:
    """A closed axis-aligned box with integer bounds ``x0 ≤ x1``, ``y0 ≤ y1``."""

    x0: int
    y0: int
    x1: int
    y1: int

    def __post_init__(self) -> None:
        for name in ("x0", "y0", "x1", "y1"):
            require_int(getattr(self, name), name)
        if self.x0 > self.x1 or self.y0 > self.y1:
            raise ValueError(f"inverted box {self}")

    @classmethod
    def of_points(cls, points: Iterable[Point]) -> BBox:
        xs: list[int] = []
        ys: list[int] = []
        for p in points:
            require_point(p, "points")
            xs.append(p.x)
            ys.append(p.y)
        if not xs:
            raise ValueError("bounding box of no points")
        return cls(min(xs), min(ys), max(xs), max(ys))

    @property
    def width(self) -> int:
        return self.x1 - self.x0

    @property
    def height(self) -> int:
        return self.y1 - self.y0

    def as_tuple(self) -> tuple[int, int, int, int]:
        return self.x0, self.y0, self.x1, self.y1

    def union(self, other: BBox) -> BBox:
        return BBox(
            min(self.x0, other.x0), min(self.y0, other.y0), max(self.x1, other.x1), max(self.y1, other.y1)
        )

    def intersects(self, other: BBox) -> bool:
        """Closed boxes: boxes that only touch intersect."""
        return self.x0 <= other.x1 and other.x0 <= self.x1 and self.y0 <= other.y1 and other.y0 <= self.y1

    def contains_point(self, p: Point) -> bool:
        return self.x0 <= p.x <= self.x1 and self.y0 <= p.y <= self.y1

    def contains_bbox(self, other: BBox) -> bool:
        return self.x0 <= other.x0 and other.x1 <= self.x1 and self.y0 <= other.y0 and other.y1 <= self.y1

    def inflate(self, d: int) -> BBox:
        """Grow by ``d`` on every side (shrink for ``d < 0``; ``ValueError`` if that would invert it)."""
        require_int(d, "d")
        return BBox(self.x0 - d, self.y0 - d, self.x1 + d, self.y1 + d)


@dataclass(frozen=True, slots=True)
class Segment:
    """The closed segment ``a–b`` (``a == b`` is a degenerate segment, i.e. a point)."""

    a: Point
    b: Point

    def __post_init__(self) -> None:
        require_point(self.a, "a")
        require_point(self.b, "b")

    @property
    def start(self) -> Point:
        return self.a

    @property
    def end(self) -> Point:
        return self.b

    @property
    def length2(self) -> int:
        dx, dy = self.b.x - self.a.x, self.b.y - self.a.y
        return dx * dx + dy * dy

    @property
    def is_degenerate(self) -> bool:
        return self.a == self.b

    def bbox(self) -> BBox:
        return BBox.of_points((self.a, self.b))

    def reversed(self) -> Segment:
        return Segment(self.b, self.a)


def _sign(v: Fraction | int) -> int:
    return (v > 0) - (v < 0)


def _sign_minus_sqrt(a: Fraction, b: Fraction | int, q: Fraction | int) -> int:
    """Sign of ``a − b·√q`` (``q ≥ 0``), exactly."""
    t_sign = _sign(b) if q > 0 else 0
    if t_sign == 0:
        return _sign(a)
    if a >= 0 > t_sign:
        return 1
    if a <= 0 < t_sign:
        return -1
    diff = a * a - b * b * q
    return _sign(diff) if t_sign > 0 else -_sign(diff)


def _sqrt_sum_le(a: Fraction, b: Fraction, sign_b: int, k: Fraction | int) -> bool:
    """Decide ``√a + sign_b·√b ≤ k`` exactly (``a, b ≥ 0``, ``sign_b`` is ±1)."""
    if sign_b > 0:
        if k < 0:
            return False
        c = k * k - a - b
        return c >= 0 and 4 * a * b <= c * c
    if k >= 0:  # √a ≤ k + √b
        c = a - b - k * k
        return c <= 0 or c * c <= 4 * k * k * b
    c = b - a - k * k  # √b ≥ √a + |k|
    return c >= 0 and c * c >= 4 * k * k * a


def _floor_minus_sqrt(c: Fraction, q: Fraction) -> int:
    """``⌊c − √q⌋``."""
    n = math.floor(c - floor_sqrt(q))
    while not (c - n >= 0 and (c - n) ** 2 >= q):
        n -= 1
    return n


def _ceil_plus_sqrt(c: Fraction, q: Fraction) -> int:
    """``⌈c + √q⌉``."""
    n = math.ceil(c + floor_sqrt(q))
    while not (n - c >= 0 and (n - c) ** 2 >= q):
        n += 1
    return n


def _round_sqrt(q: Fraction | int) -> int:
    """``√q`` rounded half to even."""
    value = Fraction(q)
    n = floor_sqrt(value)
    half = (Fraction(2 * n + 1, 2)) ** 2
    if value > half or (value == half and n % 2 == 1):
        return n + 1
    return n


def _scaled_sqrt(q: Fraction) -> int:
    """``⌊√q · 2**64⌋`` for ``q ≥ 0``."""
    scaled = q * (1 << (2 * _SCALE_BITS))
    return math.isqrt(scaled.numerator // scaled.denominator)


class _Circle:
    """Exact circle used during polygonisation: centre ``c``, radius ``√r2 + extra``."""

    __slots__ = ("cx", "cy", "extra", "k", "r2")

    def __init__(self, cx: Fraction, cy: Fraction, r2: Fraction, extra: int, tol: int) -> None:
        self.cx, self.cy, self.r2, self.extra = cx, cy, r2, extra
        self.k = tol - extra  # a chord is good when √r2 − h_s ≤ k, h_s the signed centre distance

    def chord_ok(self, u: Point, v: Point, sigma: int) -> bool:
        if u == v:
            return True
        wx, wy = v.x - u.x, v.y - u.y
        cr = wx * (self.cy - u.y) - wy * (self.cx - u.x)  # orient2d(u, v, centre)
        h2 = cr * cr / (wx * wx + wy * wy)
        # The part's points x satisfy sign(orient2d(u, x, v)) = sigma, i.e. orient2d(u, v, x) = −sigma.
        if _sign(cr) == sigma:  # centre opposite the arc: sagitta = R − h
            return _sqrt_sum_le(self.r2, h2, -1, self.k)
        return _sqrt_sum_le(self.r2, h2, 1, self.k)  # centre on the arc side or on the chord: R + h

    def midpoint(self, u: Point, v: Point, sigma: int) -> Point:
        """The point of the circle halfway along the part from ``u`` to ``v`` (orientation ``sigma``)."""
        if u == v:
            return u
        wx, wy = v.x - u.x, v.y - u.y
        cr = wx * (self.cy - u.y) - wy * (self.cx - u.x)
        tau = _sign(cr)
        if tau == 0:
            dx, dy = Fraction(sigma * wy), Fraction(-sigma * wx)
        else:
            dx = Fraction(u.x + v.x, 2) - self.cx
            dy = Fraction(u.y + v.y, 2) - self.cy
            if tau == -sigma:  # centre on the arc side: the part is longer than half a turn
                dx, dy = -dx, -dy
        n = dx * dx + dy * dy
        scale = 1 << _SCALE_BITS
        ox = Fraction(_scaled_sqrt(self.r2 * dx * dx / n) + _scaled_sqrt(self.extra**2 * dx * dx / n), scale)
        oy = Fraction(_scaled_sqrt(self.r2 * dy * dy / n) + _scaled_sqrt(self.extra**2 * dy * dy / n), scale)
        return round_point(self.cx + _sign(dx) * ox, self.cy + _sign(dy) * oy)

    def polygonize_part(self, u: Point, v: Point, sigma: int) -> list[Point]:
        vertices = [u, v]
        for _ in range(MAX_BISECTION_DEPTH):
            if all(self.chord_ok(vertices[i], vertices[i + 1], sigma) for i in range(len(vertices) - 1)):
                break
            refined = [vertices[0]]
            for i in range(len(vertices) - 1):
                refined.append(self.midpoint(vertices[i], vertices[i + 1], sigma))
                refined.append(vertices[i + 1])
            vertices = refined
        return vertices


def _dedupe(points: Iterable[Point], *, ring: bool) -> tuple[Point, ...]:
    out: list[Point] = []
    for p in points:
        if not out or out[-1] != p:
            out.append(p)
    if ring:
        while len(out) > 1 and out[-1] == out[0]:
            out.pop()
    return tuple(out)


def _check_tol(tol: int) -> None:
    require_int(tol, "tol")
    if tol < 1:
        raise ValueError(f"tol must be at least 1 nm, got {tol}")


@dataclass(frozen=True, slots=True)
class Arc:
    """A circular arc through ``start``, ``mid`` and ``end`` (all three kept exactly as given).

    ``orientation`` is the sign of ``orient2d(start, mid, end)``. KiCad does not preserve it: a re-save
    swaps ``start`` and ``end`` of negatively oriented graphic arcs (``H-G-ARC-DIR``), so no rule may
    depend on it for an arc read from a file.
    """

    start: Point
    mid: Point
    end: Point
    _centre: tuple[Fraction, Fraction] | None = field(init=False, repr=False, compare=False)
    _radius2: Fraction | None = field(init=False, repr=False, compare=False)
    _orientation: int = field(init=False, repr=False, compare=False)

    def __post_init__(self) -> None:
        require_point(self.start, "start")
        require_point(self.mid, "mid")
        require_point(self.end, "end")
        s, m, e = self.start, self.mid, self.end
        if s == e:
            raise GeometryError(
                f"arc start equals end {format_point(s)}; a full circle is a Circle", points=(s,)
            )
        if m in (s, e):
            raise GeometryError(f"arc mid {format_point(m)} equals an endpoint", points=(m,))
        bx, by = m.x - s.x, m.y - s.y
        cx, cy = e.x - s.x, e.y - s.y
        orient = bx * cy - by * cx
        object.__setattr__(self, "_orientation", _sign(orient))
        if orient == 0:
            between = bx * cx + by * cy > 0 and (m.x - e.x) * (s.x - e.x) + (m.y - e.y) * (s.y - e.y) > 0
            if not between:
                raise GeometryError(
                    f"collinear arc points with mid {format_point(m)} outside start–end",
                    points=(s, m, e),
                )
            object.__setattr__(self, "_centre", None)
            object.__setattr__(self, "_radius2", None)
            return
        b2, c2 = bx * bx + by * by, cx * cx + cy * cy
        d = 2 * orient
        ux = Fraction(cy * b2 - by * c2, d)
        uy = Fraction(bx * c2 - cx * b2, d)
        object.__setattr__(self, "_centre", (s.x + ux, s.y + uy))
        object.__setattr__(self, "_radius2", ux * ux + uy * uy)

    @property
    def centre(self) -> tuple[Fraction, Fraction] | None:
        """Exact circumcentre; ``None`` for a straight arc."""
        return self._centre

    @property
    def radius2(self) -> Fraction | None:
        """Exact squared radius; ``None`` for a straight arc."""
        return self._radius2

    @property
    def orientation(self) -> int:
        """``+1``, ``-1``, or ``0`` for a straight arc: the sign of ``orient2d(start, mid, end)``."""
        return self._orientation

    @property
    def is_straight(self) -> bool:
        return self._orientation == 0

    def reversed(self) -> Arc:
        return Arc(self.end, self.mid, self.start)

    def _chord_side(self, x: Fraction | int, y: Fraction | int) -> Fraction | int:
        s, e = self.start, self.end
        return (e.x - s.x) * (y - s.y) - (e.y - s.y) * (x - s.x)

    def contains_point_on_circle(self, p: Point) -> bool:
        """For ``p`` on the arc's circle (or line, if straight): whether ``p`` lies on the arc."""
        require_point(p, "p")
        if p in (self.start, self.end):
            return True
        if self._centre is None:
            s, e = self.start, self.end
            on_line = (e.x - s.x) * (p.y - s.y) - (e.y - s.y) * (p.x - s.x) == 0
            return on_line and min(s.x, e.x) <= p.x <= max(s.x, e.x) and min(s.y, e.y) <= p.y <= max(s.y, e.y)
        side = _sign(self._chord_side(self.mid.x, self.mid.y))
        return _sign(self._chord_side(p.x, p.y)) == side

    def bbox(self) -> BBox:
        """The smallest integer box containing every point of the true arc."""
        s, e = self.start, self.end
        x0, x1 = min(s.x, e.x), max(s.x, e.x)
        y0, y1 = min(s.y, e.y), max(s.y, e.y)
        if self._centre is None or self._radius2 is None:
            return BBox(x0, y0, x1, y1)
        cx, cy = self._centre
        r2 = self._radius2
        side = _sign(self._chord_side(self.mid.x, self.mid.y))
        k = self._chord_side(cx, cy)
        # orient2d(start, end, centre + δ·(r, 0)) = k − δ·(e.y − s.y)·r, and for (0, δ·r): k + δ·(e.x − s.x)·r
        if _sign_minus_sqrt(Fraction(k), e.y - s.y, r2) == side:
            x1 = max(x1, _ceil_plus_sqrt(cx, r2))
        if _sign_minus_sqrt(Fraction(k), -(e.y - s.y), r2) == side:
            x0 = min(x0, _floor_minus_sqrt(cx, r2))
        if _sign_minus_sqrt(Fraction(k), -(e.x - s.x), r2) == side:
            y1 = max(y1, _ceil_plus_sqrt(cy, r2))
        if _sign_minus_sqrt(Fraction(k), e.x - s.x, r2) == side:
            y0 = min(y0, _floor_minus_sqrt(cy, r2))
        return BBox(x0, y0, x1, y1)

    def polygonize(self, tol: int = DEFAULT_TOL) -> tuple[Point, ...]:
        """Vertices from ``start`` to ``end`` through ``mid``, each within 1 nm of the circle; every
        chord's exact sagitta is at most ``tol`` (unless 32 bisection levels are reached)."""
        _check_tol(tol)
        if self._centre is None or self._radius2 is None:
            return (self.start, self.mid, self.end)
        circle = _Circle(self._centre[0], self._centre[1], self._radius2, 0, tol)
        sigma = self._orientation
        first = circle.polygonize_part(self.start, self.mid, sigma)
        second = circle.polygonize_part(self.mid, self.end, sigma)
        return _dedupe([*first, *second], ring=False)


@dataclass(frozen=True, slots=True)
class Circle:
    """A circle with an integer centre and an exact integer squared radius."""

    centre: Point
    radius2: int

    def __post_init__(self) -> None:
        require_point(self.centre, "centre")
        require_int(self.radius2, "radius2")
        if self.radius2 < 0:
            raise ValueError(f"negative squared radius {self.radius2}")
        if self.radius2 == 0:
            raise GeometryError(f"circle of zero radius at {format_point(self.centre)}", code=DEGENERATE,
                                points=(self.centre,))  # fmt: skip

    @classmethod
    def from_kicad(cls, center: Point, end: Point) -> Circle:
        """KiCad's encoding: the centre and a point on the circle (no square root is taken)."""
        require_point(center, "center")
        require_point(end, "end")
        dx, dy = end.x - center.x, end.y - center.y
        return cls(center, dx * dx + dy * dy)

    @classmethod
    def from_radius(cls, centre: Point, r: int) -> Circle:
        require_int(r, "r")
        if r < 0:
            raise ValueError(f"negative radius {r}")
        return cls(centre, r * r)

    def bbox(self) -> BBox:
        k = ceil_sqrt(self.radius2)
        c = self.centre
        return BBox(c.x - k, c.y - k, c.x + k, c.y + k)

    def polygonize(self, tol: int = DEFAULT_TOL, *, outer: bool = False) -> tuple[Point, ...]:
        """A ring of vertices in positive orientation starting at the rounded ``(cx + R, cy)``.

        Default: ``R = r``, vertices within 1 nm of the circle, sagitta ≤ ``tol``. ``outer=True``:
        ``R = r + tol + 1`` nm, sagitta measured at ``R`` ≤ ``tol``, so the polygon contains the disc.
        """
        _check_tol(tol)
        extra = tol + 1 if outer else 0
        c = self.centre
        rr = _round_sqrt(self.radius2) + extra
        extremes = (
            Point(c.x + rr, c.y),
            Point(c.x, c.y + rr),
            Point(c.x - rr, c.y),
            Point(c.x, c.y - rr),
        )
        circle = _Circle(Fraction(c.x), Fraction(c.y), Fraction(self.radius2), extra, tol)
        vertices: list[Point] = []
        for i in range(4):
            vertices.extend(circle.polygonize_part(extremes[i], extremes[(i + 1) % 4], 1))
        return _dedupe(vertices, ring=True)


__all__ = ["DEFAULT_TOL", "MAX_BISECTION_DEPTH", "Arc", "BBox", "Circle", "Segment"]
