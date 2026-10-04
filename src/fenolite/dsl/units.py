# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Lengths and angles of the DSL: a length always carries a unit, and no float reaches the model.

A ``Length`` holds exact integer nanometres. The helpers take an ``int``, a ``str`` or a ``float``; a
float is read exactly from ``repr(x)``, its shortest round-trip form (S-0073), so ``mm(0.1)`` is
100 000 nm and ``mm(1/3)`` is refused. A bare number given as a length is refused, so ``place(10, 5)``
never silently means 10 nm (``docs/dsl.md``, "Units").
"""

from __future__ import annotations

from dataclasses import dataclass
from fractions import Fraction

from fenolite.core.units import Nm, Udeg, parse_angle, parse_length
from fenolite.dsl.errors import DslError

FULL_TURN = 360_000_000


@dataclass(frozen=True, slots=True)
class Length:
    """An exact length in integer nanometres."""

    nm: int

    def __post_init__(self) -> None:
        if isinstance(self.nm, bool) or not isinstance(self.nm, int):  # pyright: ignore[reportUnnecessaryIsInstance]
            raise DslError(f"a Length holds integer nanometres, not {self.nm!r}")

    def __add__(self, other: Length) -> Length:
        return Length(self.nm + _length(other, "other").nm)

    def __sub__(self, other: Length) -> Length:
        return Length(self.nm - _length(other, "other").nm)

    def __neg__(self) -> Length:
        return Length(-self.nm)

    def __mul__(self, factor: int) -> Length:
        return Length(self.nm * _int(factor, "factor"))

    __rmul__ = __mul__

    def __floordiv__(self, divisor: int) -> Length:
        return Length(self.nm // _int(divisor, "divisor"))


def _int(value: object, name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise DslError(f"{name} must be an int, not {value!r}")
    return value


def _length(value: object, name: str) -> Length:
    if not isinstance(value, Length):
        raise DslError(f"{name} must be a Length, not {value!r}")
    return value


def _number(value: object, name: str) -> str:
    """The decimal text of an ``int``, ``str`` or ``float`` (floats through ``repr``)."""
    if isinstance(value, bool):
        raise DslError(f"{name}: a bool is not a number")
    if isinstance(value, int):
        return str(value)
    if isinstance(value, float):
        return repr(value)
    if isinstance(value, str):
        return value.strip()
    raise DslError(f"{name}: expected an int, a str or a float, not {type(value).__name__}")


def _make(value: int | str | float, unit: str, name: str) -> Length:
    text = _number(value, name)
    try:
        return Length(parse_length(f"{text}{unit}"))
    except ValueError as error:
        raise DslError(f"{name}: {error}") from None


def mm(value: int | str | float) -> Length:
    """``value`` millimetres (``mm(0.1)`` is 100 000 nm)."""
    return _make(value, "mm", "mm()")


def mil(value: int | str | float) -> Length:
    """``value`` mils (thousandths of an inch)."""
    return _make(value, "mil", "mil()")


def inch(value: int | str | float) -> Length:
    """``value`` inches."""
    return _make(value, "in", "inch()")


def nm(value: int) -> Length:
    """``value`` nanometres; only an ``int`` is accepted."""
    return Length(_int(value, "nm()"))


def as_nm(value: object, *, name: str) -> Nm:
    """A ``Length`` or a string with a unit as nanometres; anything else raises ``DslError``."""
    if isinstance(value, Length):
        return value.nm
    if isinstance(value, str):
        try:
            return parse_length(value)
        except ValueError as error:
            raise DslError(f"{name}: {error}; write a unit, for example '2.54mm' or mm(2.54)") from None
    raise DslError(
        f"{name}: {value!r} has no unit; pass a Length (mm(), mil(), inch(), nm()) "
        "or a string such as '2.54mm'"
    )


AREA_UNIT = "mm2"
NM2_PER_MM2 = 10**12


def as_nm2(value: object, *, name: str) -> int:
    """An area written as a string with the unit ``mm2`` (``"2.5mm2"``) as whole square nanometres.

    The conversion is exact: an area that is negative or not a whole number of square nanometres, a bare
    number and any other unit raise ``DslError`` naming ``name``.
    """
    if not isinstance(value, str):
        raise DslError(f"{name}: {value!r} is not an area; write a string such as '2.5mm2'")
    text = value.strip()
    if not text.endswith(AREA_UNIT):
        raise DslError(f"{name}: {value!r} has no unit; write a string such as '2.5mm2'")
    number = text[: -len(AREA_UNIT)].strip()
    try:
        if not number or number[0] in "+-" or not number.replace(".", "", 1).isdigit():
            raise ValueError(number)
        area = Fraction(number) * NM2_PER_MM2
    except (ValueError, ZeroDivisionError):
        raise DslError(f"{name}: {value!r} is not a decimal number of mm2, such as '2.5mm2'") from None
    if area.denominator != 1:
        raise DslError(f"{name}: {value!r} is not a whole number of square nanometres")
    return area.numerator


def as_udeg(value: object, *, name: str) -> Udeg:
    """Degrees (``int``, ``float`` through ``repr``, or a string with or without ``deg``) as whole
    microdegrees, normalised to [0°, 360°)."""
    text = _number(value, name)
    try:
        udeg = parse_angle(text, default_unit="deg")
    except ValueError as error:
        raise DslError(f"{name}: {error}") from None
    return udeg % FULL_TURN


__all__ = ["FULL_TURN", "Length", "as_nm", "as_nm2", "as_udeg", "inch", "mil", "mm", "nm"]
