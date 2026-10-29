# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Exact electrical values of a script (``docs/dsl.md``, "Quantities").

A ``Quantity`` is a unit and a ``Fraction`` of it, so ``ohm("4k7")``, ``ohm("4.7k")`` and ``ohm(4700)`` are
one value and print one way. Quantities are script values: a part stores the text, and nothing of this
module reaches the model.
"""

from __future__ import annotations

from dataclasses import dataclass
from fractions import Fraction

from fenolite.core import quantities as core
from fenolite.dsl.errors import DslError

UNITS: dict[str, str] = {unit: symbol for unit, symbol in core.UNITS.items() if unit != "celsius"}
"""Unit name → the symbol ``text()`` prints (the units of ``fenolite.core.quantities`` that a script
value takes: a temperature is a device rating, not a part value)."""
SYMBOLS: dict[str, tuple[str, ...]] = {unit: core.SYMBOLS[unit] for unit in UNITS}
"""Unit name → the symbols a text may end with."""
SIGNED: frozenset[str] = frozenset({"volt", "ampere"})
"""The units that take a negative value."""
CODED: frozenset[str] = core.CODED
"""The units that have a letter code."""
PREFIXES: tuple[tuple[str, int], ...] = core.PREFIXES
"""SI prefix → power of ten, rising; ``u`` is micro."""
_power = core.power


def _decimal(value: Fraction, what: str) -> tuple[str, str]:
    """The whole and fractional digits of the shortest exact decimal of a non-negative ``value``."""
    try:
        return core.decimal_digits(value, what)
    except core.QuantityError as error:
        raise DslError(str(error)) from None


def decimal_text(value: Fraction, what: str) -> str:
    """The shortest exact decimal text of a non-negative ``value`` (``42.5``); ``DslError`` naming
    ``what`` when it does not terminate."""
    whole, part = _decimal(value, what)
    return f"{whole}.{part}" if part else whole


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
    try:
        return core.parse(unit, text)
    except core.QuantityError as error:
        raise DslError(str(error)) from None


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


__all__ = [
    "UNITS",
    "Quantity",
    "amp",
    "decimal_text",
    "farad",
    "henry",
    "hertz",
    "ohm",
    "second",
    "volt",
    "watt",
]
