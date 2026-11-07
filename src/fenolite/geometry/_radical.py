# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Small exact sums of square roots, for derived circular distances and coordinates.

Signs use guarded squaring in a tower of rational quadratic extensions. The roots need not be
independent or square-free: numerical zero, including dependent-root cancellation, is decided by
the same recursion. No precision limit or approximate equality enters a geometry decision.
"""

from __future__ import annotations

from dataclasses import dataclass
from fractions import Fraction

from fenolite.geometry.predicates import floor_sqrt


def _multiply(
    a: tuple[Fraction, ...], b: tuple[Fraction, ...], roots: tuple[Fraction, ...]
) -> tuple[Fraction, ...]:
    out = [Fraction(0)] * len(a)
    for i, x in enumerate(a):
        if not x:
            continue
        for j, y in enumerate(b):
            if not y:
                continue
            value = x * y
            shared = i & j
            for k, root in enumerate(roots):
                if shared & (1 << k):
                    value *= root
            out[i ^ j] += value
    return tuple(out)


def _sign(values: tuple[Fraction, ...], roots: tuple[Fraction, ...]) -> int:
    if not roots:
        return (values[0] > 0) - (values[0] < 0)
    half = len(values) // 2
    a, b, rest = values[:half], values[half:], roots[:-1]
    sa, sb = _sign(a, rest), _sign(b, rest)
    if not sb or not roots[-1]:
        return sa
    if not sa or sa == sb:
        return sb
    aa, bb = _multiply(a, a, rest), _multiply(b, b, rest)
    difference = tuple(x - roots[-1] * y for x, y in zip(aa, bb, strict=True))
    return sa * _sign(difference, rest)


@dataclass(frozen=True, slots=True)
class Real:
    """``constant + Σ coefficient·√radicand``; only exact rational constituents."""

    constant: Fraction = Fraction(0)
    terms: tuple[tuple[Fraction, Fraction], ...] = ()

    @classmethod
    def root(cls, radicand: Fraction | int, coefficient: Fraction | int = 1) -> Real:
        value, scale = Fraction(radicand), Fraction(coefficient)
        if value < 0:
            raise ValueError("a real square root needs a non-negative radicand")
        whole = floor_sqrt(value)
        if whole * whole == value:
            return cls(scale * whole)
        return cls(terms=((value, scale),)) if scale else cls()

    def __add__(self, other: Real | Fraction | int) -> Real:
        if not isinstance(other, Real):
            return Real(self.constant + other, self.terms)
        terms = dict(self.terms)
        for q, coefficient in other.terms:
            terms[q] = terms.get(q, Fraction(0)) + coefficient
        return Real(self.constant + other.constant, tuple((q, c) for q, c in sorted(terms.items()) if c))

    def __neg__(self) -> Real:
        return Real(-self.constant, tuple((q, -c) for q, c in self.terms))

    def __sub__(self, other: Real | Fraction | int) -> Real:
        return self + (-other)

    def scaled(self, value: Fraction | int) -> Real:
        return Real(self.constant * value, tuple((q, c * value) for q, c in self.terms if c * value))

    def sign(self) -> int:
        roots = tuple(q for q, _ in self.terms)
        values = [Fraction(0)] * (1 << len(roots))
        values[0] = self.constant
        for k, (_, coefficient) in enumerate(self.terms):
            values[1 << k] = coefficient
        return _sign(tuple(values), roots)

    def __abs__(self) -> Real:
        return -self if self.sign() < 0 else self

    def floor(self) -> int:
        bound = sum(abs(c) * (floor_sqrt(q) + 1) for q, c in self.terms)
        low = (self.constant - bound).__floor__()
        high = (self.constant + bound).__ceil__() + 1
        while high - low > 1:
            mid = (low + high) // 2
            if (self - mid).sign() >= 0:
                low = mid
            else:
                high = mid
        return low

    def rounded(self) -> int:
        low = self.floor()
        side = (self - Fraction(2 * low + 1, 2)).sign()
        return low + int(side > 0 or (side == 0 and low % 2 != 0))
