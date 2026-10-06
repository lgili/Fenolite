# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Exact electrical values of a script (``docs/dsl.md``, "Quantities").

A ``Quantity`` is a unit and a ``Fraction`` of it, so ``ohm("4k7")``, ``ohm("4.7k")`` and ``ohm(4700)`` are
one value and print one way. Quantities are script values: a part stores the text, and nothing of this
module reaches the model.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from fractions import Fraction

from fenolite.dsl.errors import DslError

UNITS: dict[str, str] = {
    "ohm": "Ω",
    "farad": "F",
    "henry": "H",
    "volt": "V",
    "ampere": "A",
    "hertz": "Hz",
    "watt": "W",
    "second": "s",
}
"""Unit name → the symbol ``text()`` prints."""
SYMBOLS: dict[str, tuple[str, ...]] = {
    **{unit: (symbol,) for unit, symbol in UNITS.items()},
    "ohm": ("Ω", "ohm", "R"),
}
"""Unit name → the symbols a text may end with."""
SIGNED: frozenset[str] = frozenset({"volt", "ampere"})
"""The units that take a negative value."""
CODED: frozenset[str] = frozenset({"ohm", "farad", "henry"})
"""The units that have a letter code."""
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
_EXPONENT = {**dict(PREFIXES), "µ": -6}
_PREFIX = "[pnuµmkMG]"
_ALIASES = str.maketrans({"\u2126": "Ω", "\u03bc": "µ"})
"""The ohm sign and the Greek mu, read as the omega and the micro sign."""
_NUMBER = re.compile(rf"([+-]?(?:\d+(?:\.\d+)?|\.\d+))\s*({_PREFIX}?)(.*)")
_CODE = re.compile(rf"(\d+)({_PREFIX}|R)(\d+)")


def _power(exponent: int) -> Fraction:
    return Fraction(10**exponent) if exponent >= 0 else Fraction(1, 10**-exponent)


def _decimal(value: Fraction, what: str) -> tuple[str, str]:
    """The whole and fractional digits of the shortest exact decimal of a non-negative ``value``."""
    places, rest = 0, value.denominator
    for factor in (2, 5):
        count = 0
        while rest % factor == 0:
            rest //= factor
            count += 1
        places = max(places, count)
    if rest != 1:
        raise DslError(f"{what} is not a terminating decimal; give a value that is")
    digits = str(value.numerator * 10**places // value.denominator).rjust(places + 1, "0")
    return (digits[:-places], digits[-places:]) if places else (digits, "")


@dataclass(frozen=True, slots=True)
class Quantity:
    """An exact value of one unit; build one with ``ohm()``, ``farad()`` and the other constructors."""

    unit: str
    value: Fraction

    def __post_init__(self) -> None:
        if self.unit not in UNITS:
            raise DslError(f"unknown unit {self.unit!r}; use one of: {', '.join(UNITS)}")
        if not isinstance(self.value, Fraction):  # pyright: ignore[reportUnnecessaryIsInstance]
            raise DslError(f"a quantity holds a Fraction, not {self.value!r}")
        if self.value < 0 and self.unit not in SIGNED:
            raise DslError(f"a value in {self.unit} cannot be negative: {self.value}")

    def _same(self, other: object, what: str) -> Quantity:
        if not isinstance(other, Quantity):
            raise TypeError(f"{what} takes two quantities, not a quantity and {type(other).__name__}")
        if other.unit != self.unit:
            raise TypeError(f"{what} takes two quantities of one unit, not {self.unit} and {other.unit}")
        return other

    def __lt__(self, other: object) -> bool:
        return self.value < self._same(other, "an ordering").value

    def __le__(self, other: object) -> bool:
        return self.value <= self._same(other, "an ordering").value

    def __gt__(self, other: object) -> bool:
        return self.value > self._same(other, "an ordering").value

    def __ge__(self, other: object) -> bool:
        return self.value >= self._same(other, "an ordering").value

    def __add__(self, other: object) -> Quantity:
        return Quantity(self.unit, self.value + self._same(other, "+").value)

    def __sub__(self, other: object) -> Quantity:
        return Quantity(self.unit, self.value - self._same(other, "-").value)

    @staticmethod
    def _factor(other: object, what: str) -> Fraction:
        if isinstance(other, bool) or not isinstance(other, int | Fraction):
            raise TypeError(f"{what} takes an int or a Fraction, not {type(other).__name__}")
        return Fraction(other)

    def __mul__(self, other: object) -> Quantity:
        return Quantity(self.unit, self.value * self._factor(other, "*"))

    __rmul__ = __mul__

    def __truediv__(self, other: object) -> Quantity:
        return Quantity(self.unit, self.value / self._factor(other, "/"))

    def _scaled(self) -> tuple[str, str, str]:
        """The digits before and after the point at the prefix of ``text()``, and that prefix."""
        size = abs(self.value)
        prefix, exponent = "", 0
        if size:
            prefix, exponent = PREFIXES[0]
            for name, power in PREFIXES:
                if size >= _power(power):
                    prefix, exponent = name, power
        whole, part = _decimal(size / _power(exponent), f"{self.value} {self.unit}")
        return whole, part, prefix

    def text(self, *, code: bool = False) -> str:
        """The canonical text, ``4.7kΩ``; with ``code`` the letter code, ``4k7``."""
        whole, part, prefix = self._scaled()
        if not code:
            sign = "-" if self.value < 0 else ""
            return f"{sign}{whole}{'.' + part if part else ''}{prefix}{UNITS[self.unit]}"
        if self.unit not in CODED:
            raise DslError(f"a value in {self.unit} has no letter code; use text()")
        letter = prefix or ("R" if self.unit == "ohm" else "")
        if not letter:
            raise DslError(f"{whole}{'.' + part if part else ''} {self.unit} has no letter code; use text()")
        return f"{whole}{letter}{part}"

    def __str__(self) -> str:
        return self.text()


def _parse(unit: str, text: str) -> Fraction:
    body = text.strip().translate(_ALIASES)
    coded = _CODE.fullmatch(body)
    if coded is not None and unit in CODED:
        whole, letter, part = coded.groups()
        if letter != "R" or unit == "ohm":
            exponent = 0 if letter == "R" else _EXPONENT[letter]
            return Fraction(int(whole + part), 10 ** len(part)) * _power(exponent)
    plain = _NUMBER.fullmatch(body)
    if plain is None or plain.group(3) not in ("", *SYMBOLS[unit]):
        raise DslError(
            f"{text!r} is not a value in {unit}: write a number, an optional prefix (p n u m k M G) "
            f"and optionally {' or '.join(SYMBOLS[unit])}"
        )
    return Fraction(plain.group(1)) * _power(_EXPONENT[plain.group(2)])


def _make(unit: str, value: object) -> Quantity:
    if isinstance(value, bool) or isinstance(value, float):
        raise DslError(f"{unit}: {value!r} is not exact; give an int, a Fraction or a text such as '4k7'")
    if isinstance(value, int | Fraction):
        return Quantity(unit, Fraction(value))
    if isinstance(value, str):
        return Quantity(unit, _parse(unit, value))
    raise DslError(f"{unit}: a value is an int, a Fraction or a text, not {value!r}")


def ohm(value: int | Fraction | str) -> Quantity:
    """A resistance: ``ohm("4k7")``, ``ohm("4.7 kΩ")``, ``ohm(4700)``."""
    return _make("ohm", value)


def farad(value: int | Fraction | str) -> Quantity:
    """A capacitance: ``farad("100n")``."""
    return _make("farad", value)


def henry(value: int | Fraction | str) -> Quantity:
    """An inductance: ``henry("4u7")``."""
    return _make("henry", value)


def volt(value: int | Fraction | str) -> Quantity:
    """A voltage: ``volt("3.3")``; may be negative."""
    return _make("volt", value)


def amp(value: int | Fraction | str) -> Quantity:
    """A current in amperes: ``amp("500m")``; may be negative."""
    return _make("ampere", value)


def hertz(value: int | Fraction | str) -> Quantity:
    """A frequency: ``hertz("16M")``."""
    return _make("hertz", value)


def watt(value: int | Fraction | str) -> Quantity:
    """A power: ``watt("250m")``."""
    return _make("watt", value)


def second(value: int | Fraction | str) -> Quantity:
    """A time: ``second("10u")``."""
    return _make("second", value)


__all__ = ["UNITS", "Quantity", "amp", "farad", "henry", "hertz", "ohm", "second", "volt", "watt"]
