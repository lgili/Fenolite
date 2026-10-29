# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Exact electrical values of a script (``docs/dsl.md``, "Quantities").

A ``Quantity`` is a unit and a ``Fraction`` of it, so ``ohm("4k7")``, ``ohm("4.7k")`` and ``ohm(4700)`` are
one value and print one way. Quantities are script values: a part stores the text, and nothing of this
module reaches the model.

A ``Range`` (``docs/dsl.md``, "Ranges"; change c0246) is an exact interval of one unit with worst-case
arithmetic and no solver. The one range that reaches the model is a part value, which ``dsl/convert.py``
lowers to a ``ValueRange``.
"""

from __future__ import annotations

import math
import re
from dataclasses import dataclass
from fractions import Fraction
from types import MappingProxyType
from typing import overload

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

    @overload
    def __add__(self, other: Range) -> Range: ...
    @overload
    def __add__(self, other: Quantity) -> Quantity: ...
    def __add__(self, other: object) -> Quantity | Range:
        if isinstance(other, Range):
            return self.as_range() + other
        return Quantity(self.unit, self.value + self._same(other, "+").value)

    @overload
    def __sub__(self, other: Range) -> Range: ...
    @overload
    def __sub__(self, other: Quantity) -> Quantity: ...
    def __sub__(self, other: object) -> Quantity | Range:
        if isinstance(other, Range):
            return self.as_range() - other
        return Quantity(self.unit, self.value - self._same(other, "-").value)

    @staticmethod
    def _factor(other: object, what: str) -> Fraction:
        if isinstance(other, bool) or not isinstance(other, int | Fraction):
            raise TypeError(f"{what} takes an int or a Fraction, not {type(other).__name__}")
        return Fraction(other)

    @overload
    def __mul__(self, other: Range) -> Range: ...
    @overload
    def __mul__(self, other: int | Fraction) -> Quantity: ...
    def __mul__(self, other: object) -> Quantity | Range:
        if isinstance(other, Range):
            return self.as_range() * other
        return Quantity(self.unit, self.value * self._factor(other, "*"))

    def __rmul__(self, other: int | Fraction) -> Quantity:
        return Quantity(self.unit, self._factor(other, "*") * self.value)

    @overload
    def __truediv__(self, other: Range) -> Range: ...
    @overload
    def __truediv__(self, other: int | Fraction) -> Quantity: ...
    def __truediv__(self, other: object) -> Quantity | Range:
        if isinstance(other, Range):
            return self.as_range() / other
        return Quantity(self.unit, self.value / self._factor(other, "/"))

    def as_range(self) -> Range:
        """The degenerate range ``[q, q]`` with nominal ``q``: what a quantity counts as where a range is
        expected."""
        return Range(self.unit, self.value, self.value, self.value)

    def pct(self, lo: int | Fraction | str | Tolerance, hi: int | Fraction | str | None = None) -> Range:
        """The range of a per-cent tolerance around this value, which is its nominal: ``pct(p)`` is
        ``±p %``, ``pct(lo, hi)`` from ``lo %`` to ``hi %`` (``lo <= 0 <= hi``), ``pct(t)`` from a
        ``Tolerance``."""
        if isinstance(lo, Tolerance):
            if hi is not None:
                raise DslError(f"pct({lo!r}, {hi!r}): give a Tolerance alone")
            tolerance = lo
        else:
            tolerance = pct(lo, hi)
        size = abs(self.value)
        return Range(
            self.unit,
            self.value + size * tolerance.lo / 100,
            self.value + size * tolerance.hi / 100,
            self.value,
        )

    def max(self) -> Range:
        """The range from zero to this value, without nominal (``amp("1.5").max()``: at most 1.5 A)."""
        if self.value < 0:
            raise DslError(f"{self.text()}.max(): the value is negative; use between() for a negative range")
        return Range(self.unit, Fraction(0), self.value)

    def min(self) -> Range:
        """The range from this value up, unbounded above, without nominal (``volt("4.5").min()``)."""
        return Range(self.unit, self.value, None)

    def within(self, other: Range | Quantity) -> bool:
        """Whether this value lies in ``other`` (``Range.within`` of ``[q, q]``)."""
        return self.as_range().within(other)

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


RATIO = "ratio"
"""The unit of a dimensionless range (``ohm / ohm``); it exists only as the unit of a ``Range``."""


def _unit_products() -> dict[tuple[str, str], str]:
    table: dict[tuple[str, str], str] = {(RATIO, RATIO): RATIO}
    for unit in UNITS:
        table[(unit, RATIO)] = table[(RATIO, unit)] = unit
    for left, right, result in (
        ("volt", "ampere", "watt"),
        ("ampere", "ohm", "volt"),
        ("ohm", "farad", "second"),
        ("hertz", "second", RATIO),
    ):
        table[(left, right)] = table[(right, left)] = result
    return table


def _unit_quotients() -> dict[tuple[str, str], str]:
    table: dict[tuple[str, str], str] = {(RATIO, RATIO): RATIO}
    for unit in UNITS:
        table[(unit, unit)] = RATIO
        table[(unit, RATIO)] = unit
    for left, right, result in (
        ("volt", "ohm", "ampere"),
        ("volt", "ampere", "ohm"),
        ("watt", "volt", "ampere"),
        ("watt", "ampere", "volt"),
        ("henry", "ohm", "second"),
        (RATIO, "second", "hertz"),
        (RATIO, "hertz", "second"),
    ):
        table[(left, right)] = result
    return table


UNIT_PRODUCTS: MappingProxyType[tuple[str, str], str] = MappingProxyType(_unit_products())
"""(unit, unit) → the unit of their product; a pair outside the table is refused (``docs/dsl.md``,
"Ranges"). These are definitions of SI derived units (P = V·I, V = I·R, τ = R·C, f·t = 1)."""
UNIT_QUOTIENTS: MappingProxyType[tuple[str, str], str] = MappingProxyType(_unit_quotients())
"""(dividend unit, divisor unit) → the unit of the quotient; a pair outside the table is refused."""


def _percent(value: object) -> Fraction:
    if isinstance(value, bool) or isinstance(value, float):
        raise DslError(f"per-cent {value!r} is not exact; give an int, a Fraction or a text such as '0.5'")
    if isinstance(value, int | Fraction):
        return Fraction(value)
    if isinstance(value, str) and re.fullmatch(r"\s*[+-]?(?:\d+(?:\.\d+)?|\.\d+)\s*", value):
        return Fraction(value.strip())
    raise DslError(f"per-cent {value!r} is not an int, a Fraction or a decimal text such as '0.5'")


@dataclass(frozen=True, slots=True)
class Tolerance:
    """A per-cent tolerance without unit, from ``lo`` % to ``hi`` % (``lo <= 0 <= hi``); build one with
    ``pct()``."""

    lo: Fraction
    hi: Fraction

    def __post_init__(self) -> None:
        for bound in (self.lo, self.hi):
            if not isinstance(bound, Fraction):  # pyright: ignore[reportUnnecessaryIsInstance]
                raise DslError(f"a tolerance holds Fractions, not {bound!r}")
        if not self.lo <= 0 <= self.hi:
            raise DslError(
                f"a tolerance runs from a per-cent <= 0 to a per-cent >= 0, not {self.lo}..{self.hi}"
            )


def pct(lo: int | Fraction | str, hi: int | Fraction | str | None = None) -> Tolerance:
    """A per-cent tolerance: ``pct(5)`` is ``±5 %``, ``pct(-20, 80)`` from −20 % to +80 %."""
    if hi is None:
        size = _percent(lo)
        if size < 0:
            raise DslError(f"pct({lo!r}): a symmetric per-cent is >= 0; write pct(lo, hi) for another range")
        return Tolerance(-size, size)
    low, high = _percent(lo), _percent(hi)
    if not low <= 0 <= high:
        raise DslError(f"pct({lo!r}, {hi!r}): the low per-cent is <= 0 and the high one >= 0")
    return Tolerance(low, high)


def _rounded(value: Fraction, digits: int, mode: str) -> tuple[int, int]:
    """``value`` (non-zero, positive) as ``n · 10^e`` with ``n`` of ``digits`` digits, rounded ``down``,
    ``up`` or to ``near``est with ties to even; exact when ``value`` has at most ``digits`` digits."""
    k = len(str(value.numerator)) - len(str(value.denominator))
    if value < _power(k):
        k -= 1
    if value >= _power(k + 1):
        k += 1
    exponent = k - digits + 1
    scaled = value / _power(exponent)
    if scaled.denominator == 1:
        whole = scaled.numerator
    elif mode == "down":
        whole = math.floor(scaled)
    elif mode == "up":
        whole = math.ceil(scaled)
    else:
        whole = round(scaled)
    return whole, exponent


_FLIP = {"down": "up", "up": "down", "near": "near"}


def _bound_text(unit: str, value: Fraction | None, mode: str) -> str:
    """One value of ``Range.text()``: exact when it terminates at its prefix, else rounded ``mode`` to four
    significant digits after a ``~``; ``""`` for ``None``. Never raises."""
    if value is None:
        return ""
    size = abs(value)
    prefix, exponent = "", 0
    if size and unit != RATIO:
        prefix, exponent = PREFIXES[0]
        for name, power in PREFIXES:
            if size >= _power(power):
                prefix, exponent = name, power
    scaled = size / _power(exponent)
    sign = "-" if value < 0 else ""
    symbol = "" if unit == RATIO else UNITS[unit]
    try:
        return f"{sign}{decimal_text(scaled, '')}{prefix}{symbol}"
    except DslError:
        whole, power = _rounded(scaled, 4, mode if value >= 0 else _FLIP[mode])
        return f"~{sign}{decimal_text(whole * _power(power), '')}{prefix}{symbol}"


def _operand(value: object) -> Range | None:
    """``value`` as a range for arithmetic, or ``None`` when it is no operand of a range."""
    if isinstance(value, Range):
        return value
    if isinstance(value, Quantity):
        return value.as_range()
    if isinstance(value, int | Fraction) and not isinstance(value, bool):
        exact = Fraction(value)
        return Range(RATIO, exact, exact, exact)
    return None


@dataclass(frozen=True, slots=True, init=False)
class Range:
    """An exact interval of one unit (a unit of ``UNITS``, or ``"ratio"``) with an optional nominal.

    ``low`` and ``high`` are the raw bounds (``None``: unbounded on that side); ``min``, ``max`` and
    ``nominal`` read them back as quantities. Build one with ``Quantity.pct()``, ``Quantity.min()``,
    ``Quantity.max()`` or ``between()``; ``+ - * /`` give the exact worst-case range (``docs/dsl.md``,
    "Ranges").
    """

    unit: str
    low: Fraction | None
    high: Fraction | None
    _nominal: Fraction | None

    def __init__(
        self, unit: str, low: Fraction | None, high: Fraction | None, nominal: Fraction | None = None
    ) -> None:
        if unit != RATIO and unit not in UNITS:
            raise DslError(f"unknown unit {unit!r}; use one of: {', '.join((*UNITS, RATIO))}")
        for name, value in (("low", low), ("high", high), ("nominal", nominal)):
            if value is not None and not isinstance(value, Fraction):  # pyright: ignore[reportUnnecessaryIsInstance]
                raise DslError(f"a range holds Fractions, not {name}={value!r}")
        if low is None and high is None:
            raise DslError("a range needs at least one bound")
        if low is not None and high is not None and low > high:
            raise DslError(f"a range runs from low to high, not from {low} to {high}")
        if nominal is not None and (
            (low is not None and nominal < low) or (high is not None and nominal > high)
        ):
            raise DslError(f"the nominal {nominal} lies outside the range {low}..{high}")
        object.__setattr__(self, "unit", unit)
        object.__setattr__(self, "low", low)
        object.__setattr__(self, "high", high)
        object.__setattr__(self, "_nominal", nominal)

    def __repr__(self) -> str:
        return f"Range({self.unit!r}, {self.low!r}, {self.high!r}, {self._nominal!r})"

    def _read(self, value: Fraction | None) -> Quantity | Fraction | None:
        if value is None or self.unit == RATIO:
            return value
        return Quantity(self.unit, value)

    @property
    def min(self) -> Quantity | Fraction | None:
        """The lower bound as a ``Quantity`` (a ``Fraction`` for a ratio); ``None`` when unbounded."""
        return self._read(self.low)

    @property
    def max(self) -> Quantity | Fraction | None:
        """The upper bound as a ``Quantity`` (a ``Fraction`` for a ratio); ``None`` when unbounded."""
        return self._read(self.high)

    @property
    def nominal(self) -> Quantity | Fraction | None:
        """The nominal as a ``Quantity`` (a ``Fraction`` for a ratio); ``None`` without one."""
        return self._read(self._nominal)

    @property
    def nominal_value(self) -> Fraction | None:
        """The raw nominal, like ``low`` and ``high``."""
        return self._nominal

    def _refuse_order(self, other: object) -> bool:
        raise TypeError("ranges have no order; ask a.within(b)")

    __lt__ = __le__ = __gt__ = __ge__ = _refuse_order

    # ------------------------------------------------------------------------------------ arithmetic

    def _bounded(self) -> tuple[Fraction, Fraction]:
        if self.low is None or self.high is None:
            raise DslError(f"the range {self.text()} is unbounded; an unbounded range may only be compared")
        return self.low, self.high

    @staticmethod
    def _sum(left: Range, right: Range, sign: int) -> Range:
        what = "+" if sign > 0 else "-"
        if left.unit != right.unit:
            raise TypeError(f"{what} takes two ranges of one unit, not {left.unit} and {right.unit}")
        (a0, a1), (b0, b1) = left._bounded(), right._bounded()
        nominal = None
        if left._nominal is not None and right._nominal is not None:
            nominal = left._nominal + sign * right._nominal
        if sign > 0:
            return Range(left.unit, a0 + b0, a1 + b1, nominal)
        return Range(left.unit, a0 - b1, a1 - b0, nominal)

    @staticmethod
    def _product(left: Range, right: Range) -> Range:
        unit = UNIT_PRODUCTS.get((left.unit, right.unit))
        if unit is None:
            raise TypeError(f"* has no unit for {left.unit} times {right.unit}; see quantity.UNIT_PRODUCTS")
        (a0, a1), (b0, b1) = left._bounded(), right._bounded()
        products = (a0 * b0, a0 * b1, a1 * b0, a1 * b1)
        nominal = None
        if left._nominal is not None and right._nominal is not None:
            nominal = left._nominal * right._nominal
        return Range(unit, min(products), max(products), nominal)

    @staticmethod
    def _quotient(left: Range, right: Range) -> Range:
        unit = UNIT_QUOTIENTS.get((left.unit, right.unit))
        if unit is None:
            raise TypeError(f"/ has no unit for {left.unit} over {right.unit}; see quantity.UNIT_QUOTIENTS")
        (a0, a1), (b0, b1) = left._bounded(), right._bounded()
        if b0 <= 0 <= b1:
            raise DslError(
                f"the divisor {right.text()} holds zero; a range can only be divided by one that does not"
            )
        quotients = (a0 / b0, a0 / b1, a1 / b0, a1 / b1)
        nominal = None
        if left._nominal is not None and right._nominal is not None:
            nominal = left._nominal / right._nominal
        return Range(unit, min(quotients), max(quotients), nominal)

    def __add__(self, other: object) -> Range:
        operand = _operand(other)
        return NotImplemented if operand is None else Range._sum(self, operand, 1)

    def __radd__(self, other: object) -> Range:
        operand = _operand(other)
        return NotImplemented if operand is None else Range._sum(operand, self, 1)

    def __sub__(self, other: object) -> Range:
        operand = _operand(other)
        return NotImplemented if operand is None else Range._sum(self, operand, -1)

    def __rsub__(self, other: object) -> Range:
        operand = _operand(other)
        return NotImplemented if operand is None else Range._sum(operand, self, -1)

    def __mul__(self, other: object) -> Range:
        operand = _operand(other)
        return NotImplemented if operand is None else Range._product(self, operand)

    def __rmul__(self, other: object) -> Range:
        operand = _operand(other)
        return NotImplemented if operand is None else Range._product(operand, self)

    def __truediv__(self, other: object) -> Range:
        operand = _operand(other)
        return NotImplemented if operand is None else Range._quotient(self, operand)

    def __rtruediv__(self, other: object) -> Range:
        operand = _operand(other)
        return NotImplemented if operand is None else Range._quotient(operand, self)

    def __neg__(self) -> Range:
        low, high = self._bounded()
        nominal = None if self._nominal is None else -self._nominal
        return Range(self.unit, -high, -low, nominal)

    # ------------------------------------------------------------------------------------ comparison

    def within(self, other: Range | Quantity) -> bool:
        """Whether every value of this range lies in ``other`` (a quantity counts as ``[q, q]``); an
        unbounded side of ``other`` holds every value on that side."""
        outer = other.as_range() if isinstance(other, Quantity) else other
        if not isinstance(outer, Range):  # pyright: ignore[reportUnnecessaryIsInstance]
            raise TypeError(f"within() takes a Range or a Quantity, not {type(other).__name__}")
        if outer.unit != self.unit:
            raise TypeError(f"within() takes two ranges of one unit, not {self.unit} and {outer.unit}")
        if outer.low is not None and (self.low is None or self.low < outer.low):
            return False
        return outer.high is None or (self.high is not None and self.high <= outer.high)

    # ------------------------------------------------------------------------------------------ text

    def text(self) -> str:
        """``3.3V (3.201V..3.399V)``, or ``3V..3.6V`` without a nominal; ``4.5V..`` when unbounded above. A
        value that does not terminate is rounded outward to four significant digits after a ``~``."""
        span = f"{_bound_text(self.unit, self.low, 'down')}..{_bound_text(self.unit, self.high, 'up')}"
        if self._nominal is None:
            return span
        return f"{_bound_text(self.unit, self._nominal, 'near')} ({span})"

    def __str__(self) -> str:
        return self.text()


def between(a: Quantity, b: Quantity, *, nominal: Quantity | None = None) -> Range:
    """The range from ``a`` to ``b``, two quantities of one unit with ``a <= b``, with an optional nominal
    of that unit between them."""
    for value in (a, b, nominal):
        if value is not None and not isinstance(value, Quantity):  # pyright: ignore[reportUnnecessaryIsInstance]
            raise DslError(f"between() takes quantities, not {value!r}")
    if a.unit != b.unit or (nominal is not None and nominal.unit != a.unit):
        units = ", ".join(q.unit for q in (a, b, nominal) if q is not None)
        raise DslError(f"between() takes quantities of one unit, not {units}")
    if a.value > b.value:
        raise DslError(f"between({a.text()}, {b.text()}): the first value is above the second")
    if nominal is not None and not a.value <= nominal.value <= b.value:
        raise DslError(f"between(): the nominal {nominal.text()} lies outside {a.text()}..{b.text()}")
    return Range(a.unit, a.value, b.value, None if nominal is None else nominal.value)


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


__all__ = [
    "RATIO",
    "UNITS",
    "UNIT_PRODUCTS",
    "UNIT_QUOTIENTS",
    "Quantity",
    "Range",
    "Tolerance",
    "amp",
    "between",
    "decimal_text",
    "farad",
    "henry",
    "hertz",
    "ohm",
    "pct",
    "second",
    "volt",
    "watt",
]
