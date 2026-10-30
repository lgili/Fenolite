# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The plain records of a part query and of a generator request (change c0254, ``docs/picking.md``).

``fenolite.dsl`` builds these records (``resistor(...)``, ``voltage_divider(...)``) and ``fenolite.pick``
resolves them; neither package imports the other, so the records and the closed key table live here, in
the standard-library core that both may import. A record holds exact ``Fraction`` values and the canonical
text the DSL computed; nothing of it reaches the model.
"""

from __future__ import annotations

from dataclasses import dataclass
from fractions import Fraction

KINDS: tuple[str, ...] = ("resistor", "capacitor", "inductor")
"""The query kinds, in the order messages list them."""
VALUE_UNITS: dict[str, str] = {"resistor": "ohm", "capacitor": "farad", "inductor": "henry"}
"""Kind → the unit of its value."""
PREFIXES: dict[str, str] = {"resistor": "R", "capacitor": "C", "inductor": "L"}
"""Kind → the reference prefix of a query part."""
SYMBOLS: dict[str, str] = {
    "resistor": "Fenolite:Resistor",
    "capacitor": "Fenolite:Capacitor",
    "inductor": "Fenolite:Inductor",
}
"""Kind → the catalog symbol a query part shows until the build picks its device."""
LOCK_KEYS: tuple[str, ...] = ("query", "device", "row", "catalog", "sha256", "by", "achieved")
"""The keys of one ``[picks."<path>"]`` entry of the design lock, in the order the file writes them;
``achieved`` belongs to a generator's part only."""
LOCK_REQUIRED: tuple[str, ...] = LOCK_KEYS[:-1]
PINS: tuple[str, str] = ("1", "2")
"""The generic pins of a query part; every pickable row maps exactly these two symbol pins."""


@dataclass(frozen=True, slots=True)
class Key:
    """One constraint key of a kind: its ``name``, how a row meets it (``op``: ``>=`` a rating at least
    as large, ``<=`` a value at most as large, ``=`` equality) and the ``unit`` of its value: a unit of
    ``fenolite.core.quantities``, ``percent`` (a tolerance), ``ppm`` (ppm/K), ``text`` or ``texts`` (one
    or several names, any of which matches)."""

    name: str
    op: str
    unit: str


_TOL = Key("tolerance", "<=", "percent")
_CASE = Key("case", "=", "text")
_SERIES = Key("series", "=", "text")
_ROW = Key("row", "=", "text")
KEYS: dict[str, tuple[Key, ...]] = {
    "resistor": (
        _TOL,
        Key("power", ">=", "watt"),
        Key("voltage", ">=", "volt"),
        _CASE,
        _SERIES,
        Key("tempco", "<=", "ppm"),
        _ROW,
    ),
    "capacitor": (
        _TOL,
        Key("rating", ">=", "volt"),
        _CASE,
        Key("dielectric", "=", "texts"),
        _SERIES,
        _ROW,
    ),
    "inductor": (
        _TOL,
        Key("current", ">=", "ampere"),
        Key("saturation", ">=", "ampere"),
        Key("dcr", "<=", "ohm"),
        _CASE,
        _ROW,
    ),
}
"""Kind → its closed constraint keys, in the order of the canonical text (``design.md``, decision 3).
``row`` pins the query to one row or device id: the only way to pick an ``UNVERIFIED`` row."""


def key(kind: str, name: str) -> Key:
    """The key ``name`` of ``kind``; ``KeyError`` when the kind has none."""
    for found in KEYS[kind]:
        if found.name == name:
            return found
    raise KeyError(name)


@dataclass(frozen=True, slots=True)
class Percent:
    """A per-cent tolerance from ``lo`` % to ``hi`` % (``lo <= 0 <= hi``)."""

    lo: Fraction
    hi: Fraction

    def within(self, other: Percent) -> bool:
        """Whether this tolerance is at most as wide as ``other`` on both sides."""
        return self.lo >= other.lo and self.hi <= other.hi

    def size(self) -> Fraction:
        """The larger side, the number a ranking compares."""
        return max(-self.lo, self.hi)

    def text(self) -> str:
        """``1%``, or ``-20%..+80%`` for an asymmetric tolerance."""
        if -self.lo == self.hi:
            return f"{_decimal(self.hi)}%"
        return f"-{_decimal(-self.lo)}%..+{_decimal(self.hi)}%"


def _decimal(value: Fraction) -> str:
    from fenolite.core.quantities import decimal_digits

    whole, part = decimal_digits(value, "a per-cent")
    return f"{whole}.{part}" if part else whole


@dataclass(frozen=True, slots=True)
class Bounds:
    """An exact interval in one ``unit`` with an optional nominal; ``None`` is unbounded on that side."""

    unit: str
    low: Fraction | None
    high: Fraction | None
    nominal: Fraction | None = None

    def center(self) -> Fraction:
        """The nominal, else the middle of a bounded interval, else its one bound."""
        if self.nominal is not None:
            return self.nominal
        if self.low is not None and self.high is not None:
            return (self.low + self.high) / 2
        return self.low if self.low is not None else self.high or Fraction(0)

    def contains(self, low: Fraction, high: Fraction) -> bool:
        """Whether ``[low, high]`` lies within these bounds."""
        return (self.low is None or low >= self.low) and (self.high is None or high <= self.high)


Constraint = Fraction | Percent | str | tuple[str, ...]
"""The value of one constraint: a quantity of the key's unit, a tolerance, a name or several names."""


@dataclass(frozen=True, slots=True)
class GeneratorRequest:
    """What a generator call recorded for one of its parts: the generator ``name``, the ``group`` (the path
    of the instance, shared by its parts), the part's ``role``, the ``inputs`` by key and the ``canonical``
    text of the inputs (without the role)."""

    name: str
    group: str
    role: str
    inputs: tuple[tuple[str, object], ...]
    canonical: str

    def input(self, name: str) -> object:
        return dict(self.inputs).get(name)

    def text(self) -> str:
        """The lock's query text of this part: the inputs and the role."""
        head, _, tail = self.canonical.partition("(")
        inner = tail[:-1]
        return f"{head}({inner}{', ' if inner else ''}role={self.role})"


@dataclass(frozen=True, slots=True)
class PartQuery:
    """A query: ``kind``, the ``value`` (``None`` for a generator's part), whether it was given as one
    exact quantity (``exact``), the ``constraints`` in the key order of the kind, the keys the call clears
    (``cleared``, a ``None`` of the call or of a defaults level), the ``canonical`` text and the generator
    request of a generator's part."""

    kind: str
    value: Bounds | None
    exact: bool
    constraints: tuple[tuple[str, Constraint], ...]
    canonical: str
    cleared: tuple[str, ...] = ()
    generator: GeneratorRequest | None = None
    value_text: str = ""

    def get(self, name: str) -> Constraint | None:
        return dict(self.constraints).get(name)

    def text(self) -> str:
        """The canonical text the lock compares (``resistor(10kΩ, tolerance<=1%, case=0603)``)."""
        if self.generator is not None:
            return self.generator.text()
        return self.canonical


__all__ = [
    "KEYS",
    "KINDS",
    "LOCK_KEYS",
    "LOCK_REQUIRED",
    "PINS",
    "PREFIXES",
    "SYMBOLS",
    "VALUE_UNITS",
    "Bounds",
    "Constraint",
    "GeneratorRequest",
    "Key",
    "PartQuery",
    "Percent",
    "key",
]
