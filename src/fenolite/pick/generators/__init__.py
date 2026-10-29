# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Generators: pure, exact functions that choose the values of a small circuit (change c0254,
``docs/picking.md``, "Generators").

A generator call of the DSL creates its parts as query parts carrying a ``GeneratorRequest``. The build
groups the parts of one call and gives ``solve`` the request and, per role, the rows that meet the part's
constraints. ``solve`` is pure: exact ``Fraction`` arithmetic, every irrational constant replaced by a
rational enclosure of 12 decimal digits (``PI``, ``LN_7_3``), a bounded search in a fixed order, and
explicit tie rules. It returns a ``Solution``: the row of each role, the ``gen.achieved`` text, the lock's
``achieved`` text, or why nothing was accepted (``gen.unachievable``). ``evaluate`` judges locked rows
against new inputs without searching again.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from fractions import Fraction
from types import MappingProxyType

from fenolite.core.partquery import Bounds, GeneratorRequest
from fenolite.pick.rows import Row, value_text

PI = (Fraction("3.14159265358"), Fraction("3.14159265359"))
"""A rational enclosure of π: two decimal fractions of 12 significant digits around it."""
LN_7_3 = (Fraction("0.847297860387"), Fraction("0.847297860388"))
"""A rational enclosure of ln(7/3), the factor of the I2C rise time (0.3·VDD to 0.7·VDD of an RC charge;
S-0941 prints it as 0.8473)."""


@dataclass(frozen=True, slots=True)
class Solution:
    """What a generator gives: the chosen row of each role (empty when nothing was accepted), the
    ``gen.achieved`` or ``gen.unachievable`` message, the lock's ``achieved`` text and the hint."""

    rows: Mapping[str, Row] = field(default_factory=lambda: MappingProxyType({}))
    message: str = ""
    achieved: str = ""
    hint: str = ""

    @property
    def ok(self) -> bool:
        return bool(self.rows)


Solver = Callable[[GeneratorRequest, Mapping[str, Sequence[Row]]], Solution]
Evaluator = Callable[[GeneratorRequest, Mapping[str, Row]], Solution]


# ------------------------------------------------------------------------------------- arithmetic


def bounded(value: object, what: str) -> tuple[Fraction, Fraction]:
    """The two bounds of an input range; a generator's inputs are bounded (the DSL checks it)."""
    if not isinstance(value, Bounds) or value.low is None or value.high is None:
        raise ValueError(f"{what} is not a bounded range")
    return value.low, value.high


def span(row: Row) -> tuple[Fraction, Fraction]:
    """The worst-case span of a row's value: nominal ± its tolerance (the nominal when it states none)."""
    tolerance = row.tolerance
    if tolerance is None:
        return row.value, row.value
    return row.value + row.value * tolerance.lo / 100, row.value + row.value * tolerance.hi / 100


def bracket(values: Sequence[Fraction], ideal: Fraction) -> tuple[Fraction, ...]:
    """The one or two values of the rising ``values`` around ``ideal`` (one when it is a value)."""
    below = [value for value in values if value <= ideal]
    above = [value for value in values if value >= ideal]
    found = ([below[-1]] if below else []) + ([above[0]] if above else [])
    return tuple(sorted(set(found)))


def overshoot(target: Bounds, low: Fraction, high: Fraction) -> Fraction:
    """How far ``[low, high]`` leaves ``target`` (0 when it lies within)."""
    out = Fraction(0)
    if target.low is not None:
        out = max(out, target.low - low)
    if target.high is not None:
        out = max(out, high - target.high)
    return out


# ---------------------------------------------------------------------------------------- texts


def _decimal(value: Fraction, places: int, mode: str) -> str:
    scaled = value * 10**places
    whole = scaled.__floor__() if mode == "down" else scaled.__ceil__()
    sign = "-" if whole < 0 else ""
    digits = str(abs(whole)).rjust(places + 1, "0")
    head, tail = digits[:-places], digits[-places:].rstrip("0")
    return f"{sign}{head}{'.' + tail if tail else ''}"


def range_text(low: Fraction, high: Fraction, *, places: int = 6, scale: int = 0) -> str:
    """``3.224694–3.399373``: ``low`` rounded down and ``high`` rounded up at ``places`` decimals, after
    multiplying both by ``10 ** scale`` (``scale=6`` prints micro-units)."""
    factor = Fraction(10) ** scale
    return f"{_decimal(low * factor, places, 'down')}–{_decimal(high * factor, places, 'up')}"


def describe(row: Row) -> str:
    """``61.9kΩ``: the value of a row as a message shows it."""
    from fenolite.core.partquery import VALUE_UNITS

    return value_text(VALUE_UNITS[row.kind], row.value)


def family_text(rows: Sequence[Row]) -> str:
    """``E96, 1 %``: the series and tolerance the rows share, as messages name a family."""
    series = sorted({str(row.attributes.get("series", "")) for row in rows} - {""})
    tolerances = sorted(
        {row.tolerance.text().replace("%", " %") for row in rows if row.tolerance is not None}
    )
    return ", ".join([*series, *tolerances]) or "the rows"


def registry() -> Mapping[str, tuple[Solver, Evaluator]]:
    """Generator name → its ``solve`` and ``evaluate``."""
    from fenolite.pick.generators import divider, led, pullup, rc, shunt

    return MappingProxyType(
        {
            "voltage_divider": (divider.solve, divider.evaluate),
            "rc_lowpass": (rc.solve, rc.evaluate),
            "led_resistor": (led.solve, led.evaluate),
            "i2c_pull_ups": (pullup.solve, pullup.evaluate),
            "shunt": (shunt.solve, shunt.evaluate),
        }
    )


__all__ = [
    "LN_7_3",
    "PI",
    "Evaluator",
    "Solution",
    "Solver",
    "bounded",
    "bracket",
    "describe",
    "family_text",
    "overshoot",
    "range_text",
    "registry",
    "span",
]
