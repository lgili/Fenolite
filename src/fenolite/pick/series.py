# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The E series of preferred values (change c0254, ``docs/picking.md``, "Series values").

The mantissas of E6 to E192 as integers (three digits for E48 and finer, two for the coarser series), as
published for IEC 60063 on the public page registered as S-0940. E6, E12 and E24 are transcribed as listed;
E48 is every other value of E96, and E96 and E192 are transcribed and agree with the rounding rule of the
source (``10 ** (i / n)`` to three significant digits) except the one value the source names: E192 holds
920 where the rule gives 919 (index 185). ``tests/unit/pick/test_series.py`` checks the rule exactly.
"""

from __future__ import annotations

from collections.abc import Iterator, Mapping
from fractions import Fraction
from types import MappingProxyType

SOURCE = "S-0940"
# fmt: off
_E24: tuple[int, ...] = (
    10, 11, 12, 13, 15, 16, 18, 20, 22, 24, 27, 30, 33, 36, 39, 43, 47, 51, 56, 62, 68, 75, 82, 91,
)
_E12: tuple[int, ...] = _E24[::2]
_E6: tuple[int, ...] = _E24[::4]
_E96: tuple[int, ...] = (
    100, 102, 105, 107, 110, 113, 115, 118, 121, 124, 127, 130, 133, 137, 140, 143, 147, 150, 154, 158,
    162, 165, 169, 174, 178, 182, 187, 191, 196, 200, 205, 210, 215, 221, 226, 232, 237, 243, 249, 255,
    261, 267, 274, 280, 287, 294, 301, 309, 316, 324, 332, 340, 348, 357, 365, 374, 383, 392, 402, 412,
    422, 432, 442, 453, 464, 475, 487, 499, 511, 523, 536, 549, 562, 576, 590, 604, 619, 634, 649, 665,
    681, 698, 715, 732, 750, 768, 787, 806, 825, 845, 866, 887, 909, 931, 953, 976,
)
_E192: tuple[int, ...] = (
    100, 101, 102, 104, 105, 106, 107, 109, 110, 111, 113, 114, 115, 117, 118, 120, 121, 123, 124, 126,
    127, 129, 130, 132, 133, 135, 137, 138, 140, 142, 143, 145, 147, 149, 150, 152, 154, 156, 158, 160,
    162, 164, 165, 167, 169, 172, 174, 176, 178, 180, 182, 184, 187, 189, 191, 193, 196, 198, 200, 203,
    205, 208, 210, 213, 215, 218, 221, 223, 226, 229, 232, 234, 237, 240, 243, 246, 249, 252, 255, 258,
    261, 264, 267, 271, 274, 277, 280, 284, 287, 291, 294, 298, 301, 305, 309, 312, 316, 320, 324, 328,
    332, 336, 340, 344, 348, 352, 357, 361, 365, 370, 374, 379, 383, 388, 392, 397, 402, 407, 412, 417,
    422, 427, 432, 437, 442, 448, 453, 459, 464, 470, 475, 481, 487, 493, 499, 505, 511, 517, 523, 530,
    536, 542, 549, 556, 562, 569, 576, 583, 590, 597, 604, 612, 619, 626, 634, 642, 649, 657, 665, 673,
    681, 690, 698, 706, 715, 723, 732, 741, 750, 759, 768, 777, 787, 796, 806, 816, 825, 835, 845, 856,
    866, 876, 887, 898, 909, 920, 931, 942, 953, 965, 976, 988,
)
# fmt: on
_E48: tuple[int, ...] = _E96[::2]

SERIES: Mapping[str, tuple[int, ...]] = MappingProxyType(
    {"E6": _E6, "E12": _E12, "E24": _E24, "E48": _E48, "E96": _E96, "E192": _E192}
)
"""Series name → its mantissas, rising: two digits (``10`` … ``91``) for E6 to E24, three (``100`` …) for
E48 to E192."""
EXCEPTIONS: Mapping[str, tuple[tuple[int, int, int], ...]] = MappingProxyType(
    {"E48": (), "E96": (), "E192": ((185, 920, 919),)}
)
"""Series → ``(index, listed value, value of the rule)`` of every value the source lists apart from its
rounding rule."""


def digits(name: str) -> int:
    """The number of digits of the mantissas of series ``name``."""
    return len(str(SERIES[name][0]))


def values(name: str, low: Fraction, high: Fraction) -> Iterator[Fraction]:
    """Every value of series ``name`` in ``[low, high]`` (both ends included), rising; ``low > 0``."""
    table = SERIES[name]
    scale = 10 ** (digits(name) - 1)
    exponent = 0
    while Fraction(table[0], scale) * Fraction(10) ** exponent > low:
        exponent -= 1
    while True:
        decade = Fraction(10) ** exponent
        if Fraction(table[0], scale) * decade > high:
            return
        for mantissa in table:
            value = Fraction(mantissa, scale) * decade
            if low <= value <= high:
                yield value
        exponent += 1


def member(name: str, value: Fraction) -> bool:
    """Whether ``value`` (> 0) is a value of series ``name``."""
    return any(found == value for found in values(name, value, value))


__all__ = ["EXCEPTIONS", "SERIES", "SOURCE", "digits", "member", "values"]
