# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Exact schematic lengths, colours and angles (``docs/formats/altium/schematic-records.md``, "Units").

A schematic length is an integer number of units of 10 mil, plus an optional ``_FRAC`` integer in 1/100 000
of a unit (S-0130, S-0131). ``SchLength.value`` holds the whole length as one integer count of 1/100 000 unit,
so it is exact; ``nm()`` converts it to nanometres, rounding half to even, and ``exact`` says whether that
rounded. No float is used anywhere.
"""

# evidence: see read.sch

from __future__ import annotations

import re
from dataclasses import dataclass
from fractions import Fraction

UNIT_NM = 254_000
"""One schematic unit of 10 mil in nanometres."""
FRAC_PER_UNIT = 100_000
"""``_FRAC`` steps per unit."""
UDEG_PER_DEGREE = 1_000_000
_DECIMAL = re.compile(r"^\s*([+-]?)(\d*)(?:\.(\d*))?\s*$")


@dataclass(frozen=True, slots=True, order=True)
class SchLength:
    """A length as an integer count of 1/100 000 of the 10-mil unit (2.54 nm per step)."""

    value: int

    @staticmethod
    def of(units: int, frac: int = 0) -> SchLength:
        """``units × 100 000 + frac``, each integer keeping its own sign."""
        return SchLength(units * FRAC_PER_UNIT + frac)

    @property
    def units(self) -> int:
        """Whole units, rounded towards negative infinity."""
        return self.value // FRAC_PER_UNIT

    @property
    def frac(self) -> int:
        """The remainder after ``units``, 0 to 99 999."""
        return self.value % FRAC_PER_UNIT

    def nm(self) -> int:
        """Nanometres (``value × 127 / 50``), rounded half to even."""
        quotient, remainder = divmod(self.value * 127, 50)
        if remainder * 2 > 50 or (remainder * 2 == 50 and quotient % 2 == 1):
            quotient += 1
        return quotient

    @property
    def exact(self) -> bool:
        """``True`` when ``nm()`` did not round."""
        return self.value % 50 == 0

    def mils(self) -> Fraction:
        return Fraction(self.value, 10_000)

    def __add__(self, other: SchLength) -> SchLength:
        return SchLength(self.value + other.value)

    def __sub__(self, other: SchLength) -> SchLength:
        return SchLength(self.value - other.value)

    def __neg__(self) -> SchLength:
        return SchLength(-self.value)


Point = tuple[SchLength, SchLength]
"""A point in the file's frame: X rightwards, Y upwards."""


@dataclass(frozen=True, slots=True)
class Color:
    """A colour from an integer: red in bits 0 to 7, green in 8 to 15, blue in 16 to 23 (S-0130)."""

    red: int
    green: int
    blue: int

    @staticmethod
    def of(value: int) -> Color:
        return Color(value & 0xFF, (value >> 8) & 0xFF, (value >> 16) & 0xFF)


def parse_udeg(text: str) -> int | None:
    """Integer microdegrees from a decimal number of degrees (``45.500`` → 45 500 000), without a float.
    Digits past the sixth decimal round half to even. ``None`` when the text is not a decimal number."""
    match = _DECIMAL.match(text)
    if match is None:
        return None
    sign, whole, decimals = match.group(1), match.group(2), match.group(3) or ""
    if not whole and not decimals:
        return None
    value = Fraction(int(whole or "0")) + (Fraction(int(decimals), 10 ** len(decimals)) if decimals else 0)
    micro = value * UDEG_PER_DEGREE
    result = round(micro)
    return -result if sign == "-" else result


__all__ = ["FRAC_PER_UNIT", "UDEG_PER_DEGREE", "UNIT_NM", "Color", "Point", "SchLength", "parse_udeg"]
