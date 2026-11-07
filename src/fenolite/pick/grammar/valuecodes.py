# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The value codes of ordering-code grammars (change c0263, ``docs/formats/library/value-codes.md``).

A value field spells the value of a part in one of four schemes, each with one canonical spelling per
value; ``decode_value`` accepts only that spelling, so ``decode_value(encode_value(v)) == v`` on the domain
of a scheme and nothing else decodes. ``unit`` is the value of one unit of the field (``1 pF`` for a
capacitor field in pF), so ``x = value / unit`` is what is spelled. Every step is exact: integers and
``Fraction``, never a float.

- ``eia3``: two significant digits and a multiplier digit (the number of zeros): ``104`` = 10 · 10⁴;
  below 10 units ``R`` marks the decimal point: ``4R7`` = 4.7, ``R47`` = 0.47. Always three characters.
- ``eia4``: three significant digits and a multiplier digit: ``1002`` = 100 · 10²; ``49R9``, ``4R99``,
  ``R499`` below 100 units. Always four characters.
- ``eia96``: a two-digit index (``01`` … ``96``) into the E96 mantissas of ``pick.series.SERIES`` and a
  multiplier letter: ``Y`` 0.01, ``X`` 0.1, ``A`` 1, ``B`` 10, ``C`` 100, ``D`` 1000, ``E`` 10000.
  Always three characters.
- ``rkm``: the letter ``R``, ``K``, ``M`` or ``G`` (×1, ×10³, ×10⁶, ×10⁹) in place of the decimal point, the
  largest letter that keeps the number at least 1, no trailing zero after the letter: ``4K7``, ``100R``,
  ``1K``, ``R47``. Its width varies, so a grammar's domain must be prefix-free (the lint checks it).
"""

from __future__ import annotations

import re
from collections.abc import Mapping
from fractions import Fraction
from types import MappingProxyType

from fenolite.core.quantities import QuantityError, decimal_digits
from fenolite.pick.series import SERIES

SCHEMES: tuple[str, ...] = ("eia3", "eia4", "eia96", "rkm")
"""The value-code schemes, in the order messages list them."""
WIDTHS: Mapping[str, int] = MappingProxyType({"eia3": 3, "eia4": 4, "eia96": 3})
"""The fixed width of a scheme's spellings; ``rkm`` has none."""
EIA96_LETTERS: Mapping[str, int] = MappingProxyType(
    {"Y": -2, "X": -1, "A": 0, "B": 1, "C": 2, "D": 3, "E": 4}
)
"""The multiplier letters of ``eia96`` and their powers of ten (the letters both registered sources agree
on; ``R``, ``S``, ``H``, ``Z`` and ``F`` are not read)."""
RKM_LETTERS: tuple[tuple[str, int], ...] = (("R", 0), ("K", 3), ("M", 6), ("G", 9))
"""The letters of ``rkm`` and their powers of ten, from the smallest."""
_RKM = re.compile(r"([0-9]*)([RKMG])([0-9]*)")


def _ten(exponent: int) -> Fraction:
    return Fraction(10) ** exponent


def _digits(x: Fraction, significant: int) -> str | None:
    """The fixed-width spelling of ``x`` with ``significant`` digits and a multiplier digit, ``R`` as the
    decimal point below ``10 ** (significant - 1)``; ``None`` when ``x`` has no such spelling."""
    top = 10 ** (significant - 1)
    if x >= top:
        for exponent in range(10):
            mantissa = x / _ten(exponent)
            if mantissa.denominator == 1 and top <= mantissa.numerator < top * 10:
                return f"{mantissa.numerator}{exponent}"
        return None
    for point in range(significant + 1):
        # ``point`` digits before the R: 4R7 (one), R47 (none)
        scaled = x * _ten(significant - point)
        if scaled.denominator != 1 or not top <= scaled.numerator < top * 10:
            continue
        text = str(scaled.numerator)
        return f"{text[:point]}R{text[point:]}"
    return None


def _read_digits(text: str, significant: int) -> Fraction | None:
    if len(text) != significant + 1:
        return None
    if text.isdigit():
        if text[0] == "0":
            return None
        return Fraction(int(text[:-1])) * _ten(int(text[-1]))
    point = text.find("R")
    if point < 0 or text.count("R") != 1:
        return None
    digits = text[:point] + text[point + 1 :]
    if not digits.isdigit() or digits[0] == "0":
        return None
    return Fraction(int(digits), 10 ** (significant - point))


def _eia96(x: Fraction) -> str | None:
    table = SERIES["E96"]
    for letter, exponent in EIA96_LETTERS.items():
        mantissa = x / _ten(exponent)
        if mantissa.denominator == 1 and mantissa.numerator in table:
            return f"{table.index(mantissa.numerator) + 1:02d}{letter}"
    return None


def _read_eia96(text: str) -> Fraction | None:
    if len(text) != 3 or not text[:2].isdigit() or text[2] not in EIA96_LETTERS:
        return None
    index = int(text[:2])
    if not 1 <= index <= len(SERIES["E96"]):
        return None
    return SERIES["E96"][index - 1] * _ten(EIA96_LETTERS[text[2]])


def _rkm(x: Fraction) -> str | None:
    letter, exponent = RKM_LETTERS[0]
    for name, size in RKM_LETTERS:
        if x >= _ten(size):
            letter, exponent = name, size
    try:
        whole, part = decimal_digits(x / _ten(exponent), "a value")
    except QuantityError:  # a value without a finite decimal spelling
        return None
    part = part.rstrip("0")
    return f"{'' if whole == '0' else whole}{letter}{part}"


def _read_rkm(text: str) -> Fraction | None:
    found = _RKM.fullmatch(text)
    if found is None:
        return None
    whole, letter, part = found.groups()
    number = Fraction(int(whole or "0")) + (Fraction(int(part), 10 ** len(part)) if part else 0)
    return number * _ten(dict(RKM_LETTERS)[letter])


def encode_value(scheme: str, value: Fraction, unit: Fraction) -> str | None:
    """The canonical spelling of ``value`` in ``scheme`` (``unit`` is one unit of the field), or ``None``
    when the scheme cannot spell it; ``ValueError`` for an unknown scheme."""
    if value <= 0:
        return None
    x = value / unit
    if scheme == "eia3":
        return _digits(x, 2)
    if scheme == "eia4":
        return _digits(x, 3)
    if scheme == "eia96":
        return _eia96(x)
    if scheme == "rkm":
        return _rkm(x)
    raise ValueError(f"unknown value-code scheme {scheme!r}; schemes: {', '.join(SCHEMES)}")


def decode_value(scheme: str, text: str, unit: Fraction) -> Fraction | None:
    """The value of the canonical spelling ``text`` in ``scheme``, or ``None`` when ``text`` is not one."""
    if scheme == "eia3":
        x = _read_digits(text, 2)
    elif scheme == "eia4":
        x = _read_digits(text, 3)
    elif scheme == "eia96":
        x = _read_eia96(text)
    elif scheme == "rkm":
        x = _read_rkm(text)
    else:
        raise ValueError(f"unknown value-code scheme {scheme!r}; schemes: {', '.join(SCHEMES)}")
    if x is None or x <= 0:
        return None
    value = x * unit
    return value if encode_value(scheme, value, unit) == text else None


__all__ = ["EIA96_LETTERS", "RKM_LETTERS", "SCHEMES", "WIDTHS", "decode_value", "encode_value"]
