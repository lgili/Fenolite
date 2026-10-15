# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Fixed-point trigonometry in integer microdegrees, with no floating point (moved here from
``fenolite.geometry.transform`` by change c0167 without a change of value, so that ``core.stadium`` and the
DSL, which may not import ``geometry``, share it).

``cos_sin_fixed(udeg) = (round(cos θ·2**128), round(sin θ·2**128))`` is computed with ``decimal`` series in
a private context (the caller's decimal context cannot change it), exact at multiples of 90° and where the
sine or cosine is ±1/2. ``angle_of`` is its inverse on a direction: the microdegree angle whose unit vector
in the Y-down frame of ``Transform.placement`` is nearest to it.
"""

from __future__ import annotations

import decimal
from functools import lru_cache

TRIG_BITS = 128
FULL_TURN = 360_000_000
HALF_TURN = 180_000_000
QUARTER_TURN = 90_000_000
ONE = 1 << TRIG_BITS
"""1 in the fixed point of ``cos_sin_fixed``."""
_HALF = 1 << (TRIG_BITS - 1)


def _require_int(value: int, name: str) -> None:
    if type(value) is not int:
        raise TypeError(f"{name} must be an int, got {type(value).__name__} {value!r}")


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
        return ONE, 0
    with decimal.localcontext(_context()) as ctx:
        x = decimal.Decimal(t) * _pi() / 180_000_000
        cos, sin = _series(x)
        scale = decimal.Decimal(ONE)
        c = int((cos * scale).to_integral_value(rounding=decimal.ROUND_HALF_EVEN, context=ctx))
        s = int((sin * scale).to_integral_value(rounding=decimal.ROUND_HALF_EVEN, context=ctx))
    if t == 30_000_000:
        s = _HALF  # sin 30° = 1/2 exactly
    return c, s


@lru_cache(maxsize=4096)
def table(u: int) -> tuple[int, int]:
    """``cos_sin_fixed`` for ``0 ≤ u < FULL_TURN``, memoised."""
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
    _require_int(udeg, "udeg")
    return table(udeg % FULL_TURN)


def angle_of(dx: int, dy: int) -> int:
    """The angle in ``[0, FULL_TURN)`` microdegrees whose unit vector ``(cos θ, −sin θ)`` (the image of the
    X axis under a rotation of ``Transform.placement``, Y down) is nearest to the direction ``(dx, dy)``:
    exact at multiples of 90°, otherwise within one microdegree. ``ValueError`` for ``(0, 0)``."""
    _require_int(dx, "dx")
    _require_int(dy, "dy")
    if dx == 0 and dy == 0:
        raise ValueError("the direction (0, 0) has no angle")
    flip = dy > 0 or (dy == 0 and dx < 0)
    if flip:
        dx, dy = -dx, -dy  # now in the half turn [0°, 180°): −sin θ ≤ 0

    def cross(theta: int) -> int:
        # cross((cos θ, −sin θ), d) = cos θ·dy + sin θ·dx, which is sin(θ − φ)·|d| and rises through 0 at φ
        c, s = table(theta)
        return c * dy + s * dx

    low, high = 0, HALF_TURN  # cross(low) ≤ 0 < cross(high)
    if cross(0) == 0 and dx > 0:
        return HALF_TURN if flip else 0
    while high - low > 1:
        middle = (low + high) // 2
        if cross(middle) <= 0:
            low = middle
        else:
            high = middle
    best = low if abs(cross(low)) <= abs(cross(high % FULL_TURN)) else high
    best %= HALF_TURN
    return (best + HALF_TURN) % FULL_TURN if flip else best


__all__ = ["FULL_TURN", "HALF_TURN", "ONE", "QUARTER_TURN", "TRIG_BITS", "angle_of", "cos_sin_fixed", "table"]
