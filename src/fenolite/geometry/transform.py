# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Deterministic microdegree rotation and placement transforms.

Rotation uses a fixed-point table ``cos_sin_fixed(udeg) = (round(cos θ·2**128), round(sin θ·2**128))``
computed with ``decimal`` series in a private context (the caller's decimal context cannot change it),
exact at multiples of 90° and where the sine or cosine is ±1/2. No floating-point trigonometry is
used. In the Y-down frame a positive angle displays counter-clockwise, as KiCad's (``H-G-ROT-DIR``):

    x' = x·cos θ + y·sin θ        y' = −x·sin θ + y·cos θ

A ``Transform`` is ``p ↦ R(θ)·M^m·p + t`` with ``M`` the mirror about the local X axis (``y ↦ −y``),
applied first. Its translation is kept in units of 2**-128 nm, so a composition rounds only once.
"""

from __future__ import annotations

import decimal
from dataclasses import dataclass
from fractions import Fraction
from functools import lru_cache

from fenolite.core.units import round_half_even_div
from fenolite.geometry.polygon import Polygon
from fenolite.geometry.shapes import Arc, BBox, Segment
from fenolite.geometry.vector import Point, require_int, require_point

TRIG_BITS = 128
FULL_TURN = 360_000_000
QUARTER_TURN = 90_000_000
_ONE = 1 << TRIG_BITS
_HALF = 1 << (TRIG_BITS - 1)


def _context() -> decimal.Context:
    return decimal.Context(
        prec=70,
        rounding=decimal.ROUND_HALF_EVEN,
        Emin=-999_999,
        Emax=999_999,
        capitals=1,
        clamp=0,
        flags=[],
        traps=[decimal.InvalidOperation, decimal.DivisionByZero, decimal.Overflow],
    )


def _arctan_inverse(n: int) -> decimal.Decimal:
    """``arctan(1/n)`` by its power series (current context)."""
    x = decimal.Decimal(1) / n
    x2 = x * x
    total, power, k = x, x, 1
    while True:
        power *= -x2
        term = power / (2 * k + 1)
        if total + term == total:
            return total
        total += term
        k += 1


@lru_cache(maxsize=1)
def _pi() -> decimal.Decimal:
    with decimal.localcontext(_context()):
        return 16 * _arctan_inverse(5) - 4 * _arctan_inverse(239)  # Machin's formula


def _series(x: decimal.Decimal) -> tuple[decimal.Decimal, decimal.Decimal]:
    """``(cos x, sin x)`` by their power series (current context), for ``0 ≤ x ≤ π/4``."""
    x2 = x * x
    cos, sin = decimal.Decimal(1), x
    c_term, s_term = decimal.Decimal(1), x
    i = 1
    while True:
        c_term = -c_term * x2 / ((2 * i - 1) * (2 * i))
        s_term = -s_term * x2 / ((2 * i) * (2 * i + 1))
        if cos + c_term == cos and sin + s_term == sin:
            return cos, sin
        cos += c_term
        sin += s_term
        i += 1


def _octant(t: int) -> tuple[int, int]:
    """Fixed-point ``(C, S)`` for ``0 ≤ t ≤ 45°`` (microdegrees)."""
    if t == 0:
        return _ONE, 0
    with decimal.localcontext(_context()) as ctx:
        x = decimal.Decimal(t) * _pi() / 180_000_000
        cos, sin = _series(x)
        scale = decimal.Decimal(_ONE)
        c = int((cos * scale).to_integral_value(rounding=decimal.ROUND_HALF_EVEN, context=ctx))
        s = int((sin * scale).to_integral_value(rounding=decimal.ROUND_HALF_EVEN, context=ctx))
    if t == 30_000_000:
        s = _HALF  # sin 30° = 1/2 exactly
    return c, s


@lru_cache(maxsize=4096)
def _table(u: int) -> tuple[int, int]:
    quarter, r = divmod(u, QUARTER_TURN)
    if r <= QUARTER_TURN // 2:
        c, s = _octant(r)
    else:
        s, c = _octant(QUARTER_TURN - r)  # cos r = sin(90° − r), sin r = cos(90° − r)
    for _ in range(quarter):
        c, s = -s, c  # (cos(θ + 90°), sin(θ + 90°)) = (−sin θ, cos θ)
    return c, s


def cos_sin_fixed(udeg: int) -> tuple[int, int]:
    """``(round(cos θ·2**128), round(sin θ·2**128))`` for ``θ = udeg`` microdegrees."""
    require_int(udeg, "udeg")
    return _table(udeg % FULL_TURN)


def _rotate_fixed(x: int, y: int, udeg: int) -> tuple[int, int]:
    """Rotate an integer vector; the result is scaled by 2**128 (exact, not rounded)."""
    c, s = _table(udeg % FULL_TURN)
    return x * c + y * s, -x * s + y * c


def rotate_point(p: Point, udeg: int) -> Point:
    """Rotate ``p`` about the origin by ``udeg``; each coordinate within 0.5 nm, ties to even."""
    require_point(p, "p")
    require_int(udeg, "udeg")
    x, y = _rotate_fixed(p.x, p.y, udeg)
    return Point(round_half_even_div(x, _ONE), round_half_even_div(y, _ONE))


@dataclass(frozen=True, slots=True)
class Transform:
    """``p ↦ R(rot_udeg)·M^mirror·p + (tx_fixed, ty_fixed)/2**128``; build it with the class methods."""

    rot_udeg: int = 0
    mirror: bool = False
    tx_fixed: int = 0
    ty_fixed: int = 0

    def __post_init__(self) -> None:
        require_int(self.rot_udeg, "rot_udeg")
        require_int(self.tx_fixed, "tx_fixed")
        require_int(self.ty_fixed, "ty_fixed")
        if type(self.mirror) is not bool:
            raise TypeError(f"mirror must be a bool, got {self.mirror!r}")
        object.__setattr__(self, "rot_udeg", self.rot_udeg % FULL_TURN)

    @classmethod
    def identity(cls) -> Transform:
        return cls()

    @classmethod
    def translation(cls, dx: int, dy: int) -> Transform:
        require_int(dx, "dx")
        require_int(dy, "dy")
        return cls(0, False, dx * _ONE, dy * _ONE)

    @classmethod
    def rotation(cls, udeg: int) -> Transform:
        require_int(udeg, "udeg")
        return cls(udeg)

    @classmethod
    def mirror_x_axis(cls) -> Transform:
        """``(x, y) ↦ (x, −y)``. A mirror about the Y axis is this composed with a 180° rotation."""
        return cls(0, True)

    @classmethod
    def placement(cls, at: Point, rot_udeg: int, mirror: bool = False) -> Transform:
        """Local → board: mirror (if any), rotate by ``rot_udeg``, then translate to ``at``."""
        require_point(at, "at")
        require_int(rot_udeg, "rot_udeg")
        return cls(rot_udeg, mirror, at.x * _ONE, at.y * _ONE)

    @property
    def dx(self) -> Fraction:
        return Fraction(self.tx_fixed, _ONE)

    @property
    def dy(self) -> Fraction:
        return Fraction(self.ty_fixed, _ONE)

    def _exact(self, x: int, y: int) -> tuple[int, int]:
        """The image of an integer point, scaled by 2**128 (exact)."""
        if self.mirror:
            y = -y
        rx, ry = _rotate_fixed(x, y, self.rot_udeg)
        return rx + self.tx_fixed, ry + self.ty_fixed

    def apply(self, p: Point) -> Point:
        require_point(p, "p")
        x, y = self._exact(p.x, p.y)
        return Point(round_half_even_div(x, _ONE), round_half_even_div(y, _ONE))

    def apply_angle(self, udeg: int) -> int:
        """A local angle as seen after the transform: ``(−u if mirror else u) + θ`` modulo a turn."""
        require_int(udeg, "udeg")
        return ((-udeg if self.mirror else udeg) + self.rot_udeg) % FULL_TURN

    def apply_segment(self, segment: Segment) -> Segment:
        return Segment(self.apply(segment.a), self.apply(segment.b))

    def apply_arc(self, arc: Arc) -> Arc:
        """``geometry.degenerate`` if the rounded points no longer form an arc."""
        return Arc(self.apply(arc.start), self.apply(arc.mid), self.apply(arc.end))

    def apply_polygon(self, polygon: Polygon) -> Polygon:
        """Vertex by vertex (not normalised); ``geometry.degenerate`` if a rounded ring is invalid."""
        return Polygon(
            tuple(self.apply(p) for p in polygon.outer),
            tuple(tuple(self.apply(p) for p in hole) for hole in polygon.holes),
        )

    def apply_bbox(self, bbox: BBox) -> BBox:
        """The smallest integer box containing the exact image of ``bbox`` (rounded outward)."""
        corners = [
            self._exact(x, y)
            for x, y in ((bbox.x0, bbox.y0), (bbox.x1, bbox.y0), (bbox.x1, bbox.y1), (bbox.x0, bbox.y1))
        ]
        xs = [c[0] for c in corners]
        ys = [c[1] for c in corners]
        return BBox(min(xs) // _ONE, min(ys) // _ONE, -(-max(xs) // _ONE), -(-max(ys) // _ONE))

    def _linear_fixed(self, vx: int, vy: int) -> tuple[int, int]:
        """The linear part applied to a fixed-point vector, rounded back to 2**-128 nm."""
        if self.mirror:
            vy = -vy
        x, y = _rotate_fixed(vx, vy, self.rot_udeg)
        return round_half_even_div(x, _ONE), round_half_even_div(y, _ONE)

    def compose(self, inner: Transform) -> Transform:
        """``self ∘ inner``: apply ``inner`` first. ``M·R(θ) = R(−θ)·M``, so angles add (or subtract)."""
        rot = self.rot_udeg + (-inner.rot_udeg if self.mirror else inner.rot_udeg)
        tx, ty = self._linear_fixed(inner.tx_fixed, inner.ty_fixed)
        return Transform(rot, self.mirror != inner.mirror, tx + self.tx_fixed, ty + self.ty_fixed)

    def inverse(self) -> Transform:
        """Exact for quarter turns with an integer translation; otherwise a round trip of an integer
        point is within 1 nm per axis."""
        linear = Transform(self.rot_udeg if self.mirror else -self.rot_udeg, self.mirror)
        tx, ty = linear._linear_fixed(self.tx_fixed, self.ty_fixed)
        return Transform(linear.rot_udeg, self.mirror, -tx, -ty)


__all__ = ["FULL_TURN", "QUARTER_TURN", "TRIG_BITS", "Transform", "cos_sin_fixed", "rotate_point"]
