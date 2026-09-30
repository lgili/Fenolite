# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Integer units of the model: lengths in nanometres, angles in microdegrees.

Parsing is exact (``fractions.Fraction``): a value that is not a whole number of nanometres or
microdegrees is rejected instead of rounded. The conversion to and from the 1/10 000 mil unit used
by the second backend is integer-only with round-half-even (see ``docs/formats/units.md``).
"""

from __future__ import annotations

import re
from fractions import Fraction

Nm = int
"""A length or coordinate in nanometres."""
Udeg = int
"""An angle in microdegrees."""

NM_PER_MIL = 25_400
LENGTH_UNITS: dict[str, int] = {
    "nm": 1,
    "um": 1_000,
    "µm": 1_000,
    "mm": 1_000_000,
    "cm": 10_000_000,
    "m": 1_000_000_000,
    "mil": NM_PER_MIL,
    "thou": NM_PER_MIL,
    "in": 25_400_000,
}
ANGLE_UNITS: dict[str, int] = {"udeg": 1, "µdeg": 1, "deg": 1_000_000}

_QUANTITY = re.compile(r"^\s*([+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?)\s*([A-Za-zµ]*)\s*$")


def _parse(text: str, units: dict[str, int], default_unit: str | None, what: str) -> int:
    match = _QUANTITY.match(text)
    if not match:
        raise ValueError(f"not a {what}: {text!r}")
    number, unit = match.group(1), match.group(2) or default_unit
    if not unit:
        raise ValueError(f"missing unit in {text!r} (one of {', '.join(units)})")
    if unit not in units:
        raise ValueError(f"unknown unit {unit!r} in {text!r} (one of {', '.join(units)})")
    value = Fraction(number) * units[unit]
    if value.denominator != 1:
        base = "nanometres" if what == "length" else "microdegrees"
        raise ValueError(f"{text!r} is not representable in {base}")
    return value.numerator


def parse_length(text: str, *, default_unit: str | None = None) -> Nm:
    """``"0.25mm"`` → ``250000``. Rejects values that are not a whole number of nanometres."""
    return _parse(text, LENGTH_UNITS, default_unit, "length")


def parse_angle(text: str, *, default_unit: str | None = None) -> Udeg:
    """``"90deg"`` → ``90000000``. Rejects values that are not a whole number of microdegrees."""
    return _parse(text, ANGLE_UNITS, default_unit, "angle")


def round_half_even_div(numerator: int, denominator: int) -> int:
    """``numerator / denominator`` rounded half to even, with integers only (``denominator > 0``)."""
    if denominator <= 0:
        raise ValueError("denominator must be positive")
    quotient, remainder = divmod(numerator, denominator)
    twice = 2 * remainder
    if twice > denominator or (twice == denominator and quotient % 2 == 1):
        return quotient + 1
    return quotient


def _terminating_decimal(value: Fraction) -> str | None:
    denominator = value.denominator
    places = 0
    while denominator % 10 == 0 or denominator % 2 == 0 or denominator % 5 == 0:
        if denominator == 1:
            break
        places += 1
        if (10**places) % denominator == 0:
            break
        if places > 40:
            return None
    if (10**places) % value.denominator != 0:
        return None
    return _fixed(value.numerator * (10**places) // value.denominator, places)


def _fixed(scaled: int, places: int) -> str:
    sign = "-" if scaled < 0 else ""
    digits = str(abs(scaled)).rjust(places + 1, "0")
    whole, frac = (digits[:-places], digits[-places:]) if places else (digits, "")
    frac = frac.rstrip("0")
    return f"{sign}{whole}.{frac}" if frac else f"{sign}{whole}"


def _format(value: int, unit: str, units: dict[str, int], places: int | None) -> str:
    if unit not in units:
        raise ValueError(f"unknown unit {unit!r} (one of {', '.join(units)})")
    factor = units[unit]
    if places is not None:
        return _fixed(round_half_even_div(value * 10**places, factor), places) + unit
    exact = _terminating_decimal(Fraction(value, factor))
    if exact is None:
        raise ValueError(f"{value} is not exactly representable in {unit}; pass places=")
    return exact + unit


def format_length(nm: Nm, unit: str = "mm", *, places: int | None = None) -> str:
    """``250000`` → ``"0.25mm"`` (shortest exact form); ``places`` rounds half to even instead."""
    return _format(nm, unit, LENGTH_UNITS, places)


def format_angle(udeg: Udeg, unit: str = "deg", *, places: int | None = None) -> str:
    """``90000000`` → ``"90deg"``."""
    return _format(udeg, unit, ANGLE_UNITS, places)


def u_to_nm(u: int) -> Nm:
    """1/10 000 mil → nanometres (× 2.54), rounded half to even. Error ≤ 0.5 nm."""
    return round_half_even_div(u * 127, 50)


def nm_to_u(nm: Nm) -> int:
    """Nanometres → 1/10 000 mil (÷ 2.54), rounded half to even. Error ≤ 1.27 nm; never a tie."""
    return round_half_even_div(nm * 50, 127)


__all__ = [
    "ANGLE_UNITS",
    "LENGTH_UNITS",
    "NM_PER_MIL",
    "Nm",
    "Udeg",
    "format_angle",
    "format_length",
    "nm_to_u",
    "parse_angle",
    "parse_length",
    "round_half_even_div",
    "u_to_nm",
]
