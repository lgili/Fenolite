# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Exact values with a unit, read from text (stdlib only; change c0248).

The DSL (``fenolite.dsl.quantity``) and the device records of the catalog (``fenolite.catalog.devices``)
both read units here, so the two read ``"4k7"``, ``"2.7V"`` or ``"-40degC"`` alike. A value is an exact
``Fraction``: no float is created. ``micro_units`` turns a value into the integer units that device ratings
are stored in (µV, µA, µW and m°C).
"""

from __future__ import annotations

import re
from fractions import Fraction


class QuantityError(ValueError):
    """A text that is not a value of its unit, or a value that is not exact in the units asked for."""


UNITS: dict[str, str] = {
    "ohm": "Ω",
    "farad": "F",
    "henry": "H",
    "volt": "V",
    "ampere": "A",
    "hertz": "Hz",
    "watt": "W",
    "second": "s",
    "celsius": "degC",
}
"""Unit name → the symbol a canonical text prints."""
SYMBOLS: dict[str, tuple[str, ...]] = {
    **{unit: (symbol,) for unit, symbol in UNITS.items()},
    "ohm": ("Ω", "ohm", "R"),
    "celsius": ("degC", "°C"),
}
"""Unit name → the symbols a text may end with."""
SIGNED: frozenset[str] = frozenset({"volt", "ampere", "celsius"})
"""The units that take a negative value."""
CODED: frozenset[str] = frozenset({"ohm", "farad", "henry"})
"""The units that have a letter code (``4k7``)."""
PREFIXES: tuple[tuple[str, int], ...] = (
    ("p", -12),
    ("n", -9),
    ("u", -6),
    ("m", -3),
    ("", 0),
    ("k", 3),
    ("M", 6),
    ("G", 9),
)
"""SI prefix → power of ten, rising; ``u`` is micro."""
MICRO_UNITS: dict[str, tuple[str, int]] = {
    "volt": ("uV", 6),
    "ampere": ("uA", 6),
    "watt": ("uW", 6),
    "celsius": ("mdegC", 3),
}
"""Unit name → the name of the integer unit it is stored in and the power of ten of one unit in it."""
_EXPONENT = {**dict(PREFIXES), "µ": -6}
_PREFIX = "[pnuµmkMG]"
_ALIASES = str.maketrans({"Ω": "Ω", "μ": "µ"})
"""The ohm sign and the Greek mu, read as the omega and the micro sign."""
_NUMBER = re.compile(rf"([+-]?(?:\d+(?:\.\d+)?|\.\d+))\s*({_PREFIX}?)(.*)")
_CODE = re.compile(rf"(\d+)({_PREFIX}|R)(\d+)")


def power(exponent: int) -> Fraction:
    """``10 ** exponent`` as an exact ``Fraction``."""
    return Fraction(10**exponent) if exponent >= 0 else Fraction(1, 10**-exponent)


def decimal_digits(value: Fraction, what: str) -> tuple[str, str]:
    """The whole and fractional digits of the shortest exact decimal of a non-negative ``value``;
    ``QuantityError`` naming ``what`` when it does not terminate."""
    places, rest = 0, value.denominator
    for factor in (2, 5):
        count = 0
        while rest % factor == 0:
            rest //= factor
            count += 1
        places = max(places, count)
    if rest != 1:
        raise QuantityError(f"{what} is not a terminating decimal; give a value that is")
    digits = str(value.numerator * 10**places // value.denominator).rjust(places + 1, "0")
    return (digits[:-places], digits[-places:]) if places else (digits, "")


def parse(unit: str, text: str) -> Fraction:
    """The exact value of ``text`` in ``unit``: a number, an optional SI prefix and optionally a symbol of
    the unit, or a letter code (``4k7``, ``2R2``) for the coded units; any other text raises
    ``QuantityError``. The sign is not judged here: ``SIGNED`` names the units that take one."""
    if unit not in UNITS:
        raise QuantityError(f"unknown unit {unit!r}; use one of: {', '.join(UNITS)}")
    body = text.strip().translate(_ALIASES)
    coded = _CODE.fullmatch(body)
    if coded is not None and unit in CODED:
        whole, letter, part = coded.groups()
        if letter != "R" or unit == "ohm":
            exponent = 0 if letter == "R" else _EXPONENT[letter]
            return Fraction(int(whole + part), 10 ** len(part)) * power(exponent)
    plain = _NUMBER.fullmatch(body)
    if plain is None or plain.group(3) not in ("", *SYMBOLS[unit]):
        raise QuantityError(
            f"{text!r} is not a value in {unit}: write a number, an optional prefix (p n u m k M G) "
            f"and optionally {' or '.join(SYMBOLS[unit])}"
        )
    return Fraction(plain.group(1)) * power(_EXPONENT[plain.group(2)])


def micro_units(unit: str, text: str) -> int:
    """The value of ``text`` in ``unit`` as an exact integer of its stored unit (``MICRO_UNITS``): µV, µA,
    µW or m°C. A value that is not a whole number of that unit, or a negative value of an unsigned unit,
    raises ``QuantityError``."""
    if unit not in MICRO_UNITS:
        raise QuantityError(f"a value in {unit} has no integer unit; use one of: {', '.join(MICRO_UNITS)}")
    name, exponent = MICRO_UNITS[unit]
    value = parse(unit, text)
    if value < 0 and unit not in SIGNED:
        raise QuantityError(f"a value in {unit} cannot be negative: {text!r}")
    scaled = value * power(exponent)
    if scaled.denominator != 1:
        raise QuantityError(f"{text!r} is not a whole number of {name}")
    return scaled.numerator


__all__ = [
    "CODED",
    "MICRO_UNITS",
    "PREFIXES",
    "SIGNED",
    "SYMBOLS",
    "UNITS",
    "QuantityError",
    "decimal_digits",
    "micro_units",
    "parse",
    "power",
]
