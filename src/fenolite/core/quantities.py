# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Exact values with a unit, read from text (stdlib only; change c0248).

The DSL (``fenolite.dsl.quantity``) and the device records of the catalog (``fenolite.catalog.devices``)
both read units here, so the two read ``"4k7"``, ``"2.7V"`` or ``"-40degC"`` alike. A value is an exact
``Fraction``: no float is created. ``micro_units`` turns a value into the integer units that device ratings
are stored in (µV, µA, µW and mK).

A temperature is a value in kelvin (change c0274): ``"233.15K"`` reads as itself and ``"-40degC"`` as
233.15 K exactly; ``celsius_text`` prints an absolute temperature back in degrees Celsius.
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
    "kelvin": "K",
}
"""Unit name → the symbol a canonical text prints."""
SYMBOLS: dict[str, tuple[str, ...]] = {
    **{unit: (symbol,) for unit, symbol in UNITS.items()},
    "ohm": ("Ω", "ohm", "R"),
}
"""Unit name → the symbols a text may end with."""
CELSIUS_SYMBOLS: tuple[str, ...] = ("degC", "°C")
"""The symbols of a text in degrees Celsius, which a value in kelvin also reads (change c0274)."""
ZERO_CELSIUS = Fraction(27315, 100)
"""0 °C in kelvin, exactly: the definition of the Celsius scale."""
SIGNED: frozenset[str] = frozenset({"volt", "ampere"})
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
    "kelvin": ("mK", 3),
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
    ``QuantityError``. The sign is not judged here: ``SIGNED`` names the units that take one. A value in
    kelvin also reads a text in degrees Celsius (``-40degC``, no prefix), which is an absolute temperature
    and cannot lie below 0 K."""
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
    if unit == "kelvin" and plain is not None and plain.group(3) in CELSIUS_SYMBOLS:
        if plain.group(2):
            raise QuantityError(f"{text!r}: a temperature in degrees Celsius takes no prefix")
        value = Fraction(plain.group(1)) + ZERO_CELSIUS
        if value < 0:
            raise QuantityError(f"{text!r} lies below absolute zero (-273.15degC)")
        return value
    if plain is None or plain.group(3) not in ("", *SYMBOLS[unit]):
        raise QuantityError(
            f"{text!r} is not a value in {unit}: write a number, an optional prefix (p n u m k M G) "
            f"and optionally {' or '.join(_symbols(unit))}"
        )
    return Fraction(plain.group(1)) * power(_EXPONENT[plain.group(2)])


def _symbols(unit: str) -> tuple[str, ...]:
    return (*SYMBOLS[unit], *CELSIUS_SYMBOLS) if unit == "kelvin" else SYMBOLS[unit]


def celsius_text(kelvin: Fraction, symbol: str = "°C") -> str:
    """The absolute temperature ``kelvin`` in degrees Celsius, exactly (``-40°C``, ``26.85°C``), with
    ``symbol`` (``degC`` for an ASCII record); ``QuantityError`` when it is not a terminating decimal."""
    value = kelvin - ZERO_CELSIUS
    whole, part = decimal_digits(abs(value), f"{kelvin} K")
    return f"{'-' if value < 0 else ''}{whole}{'.' + part if part else ''}{symbol}"


def micro_units(unit: str, text: str) -> int:
    """The value of ``text`` in ``unit`` as an exact integer of its stored unit (``MICRO_UNITS``): µV, µA,
    µW or mK. A value that is not a whole number of that unit, or a negative value of an unsigned unit,
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


LENGTH_UNITS: dict[str, Fraction] = {
    "mm": Fraction(1_000_000),
    "um": Fraction(1_000),
    "µm": Fraction(1_000),
    "nm": Fraction(1),
    "mil": Fraction(25_400),
    "in": Fraction(25_400_000),
}
"""Length unit → nanometres in one of it (change c0259: lengths of library records)."""


_SCALED = re.compile(r"([+-]?)(\d*)(?:\.(\d+))?\s*([a-zµ]+)")


def _scaled(text: str, units: dict[str, int], what: str, step: str) -> int:
    """``text`` (a decimal and a unit of ``units``) in integer steps; integer arithmetic only, so that a
    library of thousands of lengths reads fast."""
    match = _SCALED.fullmatch(text.strip()) if isinstance(text, str) else None  # pyright: ignore[reportUnnecessaryIsInstance]
    if match is None or match.group(4) not in units or not (match.group(2) or match.group(3)):
        raise QuantityError(f"{text!r} is not {what}: write a number and one of {', '.join(units)}")
    sign, whole, part, unit = match.groups()
    part = part or ""
    numerator = int((whole or "0") + part) * units[unit]
    scale = 10 ** len(part)
    if numerator % scale:
        raise QuantityError(f"{text!r} is not a whole number of {step}")
    value = numerator // scale
    return -value if sign == "-" else value


_LENGTH_STEPS = {unit: int(value) for unit, value in LENGTH_UNITS.items()}


def parse_length(text: str) -> int:
    """The length ``text`` (``"1.27mm"``, ``"25mil"``, ``"500um"``) in integer nanometres; a value that is
    not a whole number of nanometres raises ``QuantityError``."""
    return _scaled(text, _LENGTH_STEPS, "a length", "nanometres")


def parse_angle(text: str) -> int:
    """The angle ``text`` (``"90deg"``) in integer microdegrees; a value that is not a whole number of
    microdegrees raises ``QuantityError``."""
    return _scaled(text, {"deg": 1_000_000}, "an angle", "microdegrees")


def _decimal_of(value: int, scale: int, unit: str) -> str:
    whole, part = decimal_digits(Fraction(abs(value), scale), unit)
    return f"{'-' if value < 0 else ''}{whole}{'.' + part if part else ''}{unit}"


def length_text(nm: int) -> str:
    """The canonical text of a length of ``nm`` nanometres: millimetres with the fewest exact digits."""
    return _decimal_of(nm, 1_000_000, "mm")


def angle_text(udeg: int) -> str:
    """The canonical text of an angle of ``udeg`` microdegrees: degrees with the fewest exact digits."""
    return _decimal_of(udeg, 1_000_000, "deg")


__all__ = [
    "CELSIUS_SYMBOLS",
    "CODED",
    "LENGTH_UNITS",
    "MICRO_UNITS",
    "PREFIXES",
    "SIGNED",
    "SYMBOLS",
    "UNITS",
    "ZERO_CELSIUS",
    "QuantityError",
    "angle_text",
    "celsius_text",
    "decimal_digits",
    "length_text",
    "micro_units",
    "parse",
    "parse_angle",
    "parse_length",
    "power",
]
