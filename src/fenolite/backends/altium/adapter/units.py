# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Lengths, points and angles of Altium records as the model's integers (``docs/formats/units.md`` and
``docs/formats/altium/import.md``, "Units and frame"; change c0043).

A binary length is an integer of 1/10 000 mil and becomes ``core.units.u_to_nm`` nanometres, half to even.
Altium's Y axis points up and the model's down, so a point is ``(x, −y)``; no origin is subtracted. A stored
angle is a double in degrees: it is converted once, through an exact fraction, to microdegrees. No float
arithmetic is used for a length, a coordinate or a stored angle.
"""

from __future__ import annotations

import math
import re
from fractions import Fraction

from fenolite.core.coords import Point
from fenolite.core.units import Nm, Udeg, round_half_even_div, u_to_nm
from fenolite.geometry.transform import FULL_TURN, TRIG_BITS, cos_sin_fixed

UNITS_PER_NM = Fraction(50, 127)
NM_PER_UNIT = Fraction(127, 50)
UDEG = 1_000_000
_ONE = 1 << TRIG_BITS
_TEXT = re.compile(r"\s*([+-]?(?:\d+(?:\.\d*)?|\.\d+))\s*(mil|mm)\s*", re.IGNORECASE)
_NM_PER = {"mil": 25_400, "mm": 1_000_000}


def round_half_even(value: Fraction) -> int:
    """``value`` rounded to the nearest integer, ties to even."""
    return round_half_even_div(value.numerator, value.denominator)


def pcb_length(u: int) -> Nm:
    """A binary PCB length of ``u`` units of 1/10 000 mil in nanometres, half to even."""
    return u_to_nm(u)


def exact_length(u: int) -> bool:
    """Whether ``pcb_length(u)`` did not round: ``u`` is a multiple of 50."""
    return u % 50 == 0


def pcb_point(x: int, y: int) -> Point:
    """A point of a PCB document or library in the model's frame: Y negated, no origin subtracted."""
    return Point(u_to_nm(x), -u_to_nm(y))


def units_length(units: Fraction) -> tuple[Nm, bool]:
    """A length given as an exact number of units (the mil text of a property record, c0041) in
    nanometres, and whether the conversion was exact."""
    value = units * NM_PER_UNIT
    return round_half_even(value), value.denominator == 1


def text_length(text: str | None) -> tuple[Nm, bool] | None:
    """A length written as property text (``10mil``, ``0.5mil``, ``1.27mm``): nanometres rounded half to
    even and whether the value was a whole number of nanometres. ``None`` for any other text."""
    if text is None:
        return None
    match = _TEXT.fullmatch(text)
    if match is None:
        return None
    value = Fraction(match.group(1)) * _NM_PER[match.group(2).lower()]
    return round_half_even(value), value.denominator == 1


def angle(degrees: float) -> tuple[Udeg, bool]:
    """A stored angle (a double, degrees, counter-clockwise) in microdegrees, reduced to ``[0, 360°)``,
    and whether the conversion was exact: the double nearest to the result is the stored one. A value
    that is not finite reads as 0 and is inexact."""
    if not math.isfinite(degrees):
        return 0, False
    micro = round_half_even(Fraction(degrees) * UDEG)
    exact = Fraction(micro, UDEG).numerator / Fraction(micro, UDEG).denominator == degrees
    return micro % FULL_TURN, exact


def _on_circle(cx: Fraction, cy: Fraction, radius: Fraction, udeg: int) -> Point:
    """The model point at ``udeg`` on the circle given in units in Altium's frame (Y up)."""
    cos, sin = cos_sin_fixed(udeg)
    x = (cx + radius * Fraction(cos, _ONE)) * NM_PER_UNIT
    y = (cy + radius * Fraction(sin, _ONE)) * NM_PER_UNIT
    return Point(round_half_even(x), -round_half_even(y))


def sweep(start: Udeg, end: Udeg) -> Udeg:
    """The counter-clockwise sweep from ``start`` to ``end``, above 0; equal angles are a full turn."""
    return (end - start) % FULL_TURN or FULL_TURN


def arc_points(
    cx: int | Fraction, cy: int | Fraction, radius: int | Fraction, start: Udeg, end: Udeg
) -> tuple[Point, Point, Point]:
    """The model's three points of an arc given by its centre and radius (units, Altium frame) and its two
    angles (microdegrees): start, middle and end along the counter-clockwise sweep from ``start`` to
    ``end``, each rounded half to even. The direction is kept under the Y flip, because the points are
    given in order."""
    centre_x, centre_y, r = Fraction(cx), Fraction(cy), Fraction(radius)
    turn = sweep(start, end)
    middle = round_half_even(Fraction(2 * start + turn, 2))
    return (
        _on_circle(centre_x, centre_y, r, start),
        _on_circle(centre_x, centre_y, r, middle),
        _on_circle(centre_x, centre_y, r, start + turn if turn != FULL_TURN else start),
    )


def circle_points(cx: int | Fraction, cy: int | Fraction, radius: int | Fraction) -> tuple[Point, Point]:
    """The model's two points of a full circle: its centre and one point on it (at angle 0)."""
    centre_x, centre_y, r = Fraction(cx), Fraction(cy), Fraction(radius)
    centre = Point(round_half_even(centre_x * NM_PER_UNIT), -round_half_even(centre_y * NM_PER_UNIT))
    return centre, _on_circle(centre_x, centre_y, r, 0)


__all__ = [
    "angle",
    "arc_points",
    "circle_points",
    "exact_length",
    "pcb_length",
    "pcb_point",
    "round_half_even",
    "sweep",
    "text_length",
    "units_length",
]
