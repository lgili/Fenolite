# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""``rc_lowpass``: a resistor and a capacitor for a first-order low-pass corner (change c0254,
``docs/picking.md``, "rc_lowpass").

``f = 1 / (2πRC)`` with π replaced by its enclosure ``PI``: the worst-case corner runs from
``1 / (2·π_hi·Rmax·Cmax)`` to ``1 / (2·π_lo·Rmin·Cmin)``, so the reported range contains the true one. For
each capacitor row, in value order, the resistor values that bracket the ideal ``R`` are tried. Among
accepted pairs: the nominal corner (at the enclosure's midpoint) closest to the target's nominal, then the
smaller capacitor, then the smaller resistor (then the device ids). A fixed ``r=`` or ``c=`` query of the
call limits that role's rows to the ones it matches.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from fractions import Fraction
from types import MappingProxyType

from fenolite.core.partquery import Bounds, GeneratorRequest
from fenolite.pick.generators import PI, Solution, bounded, bracket, describe, overshoot, range_text, span
from fenolite.pick.lockpicks import micro_text
from fenolite.pick.rows import Row

ROLES = ("r", "c")
_PI_MID = (PI[0] + PI[1]) / 2


def _corner(r: Row, c: Row) -> tuple[Fraction, Fraction, Fraction]:
    r0, r1 = span(r)
    c0, c1 = span(c)
    return 1 / (2 * PI[1] * r1 * c1), 1 / (2 * PI[0] * r0 * c0), 1 / (2 * _PI_MID * r.value * c.value)


def _texts(request: GeneratorRequest, r: Row, c: Row) -> tuple[str, str]:
    low, high, _ = _corner(r, c)
    target = request.input("corner")
    t0, t1 = bounded(target, "corner")
    message = (
        f"{request.group}: rc_lowpass R {describe(r)}, C {describe(c)}: corner "
        f"{range_text(low, high, places=3)} Hz "
        f"within {range_text(t0, t1, places=3)} Hz"
    )
    return message, micro_text("corner", "Hz", low, high)


def solve(request: GeneratorRequest, rows: Mapping[str, Sequence[Row]]) -> Solution:
    target = request.input("corner")
    assert isinstance(target, Bounds)
    goal = target.center()
    resistors = sorted(rows.get("r", ()), key=lambda row: (row.value, row.device))
    capacitors = sorted(rows.get("c", ()), key=lambda row: (row.value, row.device))
    values = sorted({row.value for row in resistors})
    by_value: dict[Fraction, list[Row]] = {}
    for row in resistors:
        by_value.setdefault(row.value, []).append(row)
    accepted: list[tuple[tuple[object, ...], Row, Row]] = []
    failed: list[tuple[tuple[object, ...], Row, Row]] = []
    for c in capacitors:
        ideal = 1 / (2 * _PI_MID * goal * c.value)
        for value in bracket(values, ideal):
            for r in by_value[value]:
                low, high, nominal = _corner(r, c)
                order = (abs(nominal - goal), c.value, r.value, r.device, c.device)
                if target.contains(low, high):
                    accepted.append((order, r, c))
                else:
                    failed.append(((overshoot(target, low, high), *order), r, c))
    if accepted:
        _, r, c = min(accepted, key=lambda item: item[0])
        message, achieved = _texts(request, r, c)
        return Solution(MappingProxyType({"r": r, "c": c}), message, achieved)
    t0, t1 = bounded(target, "corner")
    hint = "tighter tolerances, a wider corner range, or another fixed part"
    if not failed:
        return Solution(
            message=f"{request.group}: rc_lowpass: no resistor and capacitor rows to search", hint=hint
        )
    _, r, c = min(failed, key=lambda item: item[0])
    low, high, _ = _corner(r, c)
    return Solution(
        message=(
            f"{request.group}: no pair keeps the corner within {range_text(t0, t1, places=3)} Hz; "
            "the best, R "
            f"{describe(r)} / C {describe(c)}, reaches {range_text(low, high, places=3)} Hz"
        ),
        hint=hint,
    )


def evaluate(request: GeneratorRequest, chosen: Mapping[str, Row]) -> Solution:
    r, c = chosen["r"], chosen["c"]
    target = request.input("corner")
    assert isinstance(target, Bounds)
    message, achieved = _texts(request, r, c)
    low, high, _ = _corner(r, c)
    if target.contains(low, high):
        return Solution(MappingProxyType(dict(chosen)), message, achieved)
    return Solution(message=message, achieved=achieved)


__all__ = ["ROLES", "evaluate", "solve"]
