# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""``voltage_divider``: two resistors for a feedback or a plain divider (change c0254, ``docs/picking.md``,
"voltage_divider").

Feedback mode (``ref`` given): ``VOUT = VREF · (1 + Rt / Rb)`` at ``hi``. Divider mode: ``VMID = VIN · Rb /
(Rt + Rb)`` at ``mid``. Both are monotonic in each resistor, so the worst case over the reference (or input)
range and both tolerances is exact at the corners. The search takes every bottom row whose nominal current
lies in the ``current`` window, and for each the one or two values that bracket the ideal top resistor.
Among accepted pairs: the nominal output closest to the target's nominal, then the narrowest range, then
the smaller ``Rb``, then the smaller ``Rt`` (then the device ids).
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from fractions import Fraction
from types import MappingProxyType

from fenolite.core.partquery import Bounds, GeneratorRequest
from fenolite.pick.generators import (
    Solution,
    bounded,
    bracket,
    describe,
    family_text,
    overshoot,
    range_text,
    span,
)
from fenolite.pick.lockpicks import micro_text
from fenolite.pick.rows import Row

ROLES = ("top", "bot")


def _feedback(request: GeneratorRequest) -> bool:
    return request.input("ref") is not None


def _outputs(
    request: GeneratorRequest, top: Row, bot: Row
) -> tuple[Fraction, Fraction, Fraction, Fraction, Fraction]:
    """The output range, its nominal and the divider current range of the pair."""
    t0, t1 = span(top)
    b0, b1 = span(bot)
    if _feedback(request):
        ref = request.input("ref")
        r0, r1 = bounded(ref, "ref")
        nominal_ref = ref.center() if isinstance(ref, Bounds) else r0
        low, high = r0 * (1 + t0 / b1), r1 * (1 + t1 / b0)
        nominal = nominal_ref * (1 + top.value / bot.value)
        return low, high, nominal, r0 / b1, r1 / b0
    vin = request.input("vin")
    v0, v1 = bounded(vin, "vin")
    nominal_in = vin.center() if isinstance(vin, Bounds) else v0
    low, high = v0 * b0 / (t1 + b0), v1 * b1 / (t0 + b1)
    nominal = nominal_in * bot.value / (top.value + bot.value)
    return low, high, nominal, v0 / (t1 + b1), v1 / (t0 + b0)


def _name(request: GeneratorRequest) -> str:
    return "VOUT" if _feedback(request) else "VMID"


def _texts(request: GeneratorRequest, top: Row, bot: Row) -> tuple[str, str]:
    low, high, _, i0, i1 = _outputs(request, top, bot)
    target = request.input("target")
    assert isinstance(target, Bounds)
    t0, t1 = bounded(target, "target")
    name = _name(request)
    message = (
        f"{request.group}: voltage_divider top {describe(top)}, bottom {describe(bot)} "
        f"({family_text((top, bot))}): {name} {range_text(low, high)} V within {range_text(t0, t1)} V; "
        f"divider current {range_text(i0, i1, places=2, scale=6)} µA"
    )
    return message, micro_text(name, "V", low, high)


def _accepted(request: GeneratorRequest, top: Row, bot: Row) -> bool:
    target = request.input("target")
    assert isinstance(target, Bounds)
    low, high, *_ = _outputs(request, top, bot)
    return target.contains(low, high)


def solve(request: GeneratorRequest, rows: Mapping[str, Sequence[Row]]) -> Solution:
    """The pair of ``request`` from the rows of each role (``top``, ``bot``)."""
    target = request.input("target")
    current = request.input("current")
    assert isinstance(target, Bounds) and isinstance(current, Bounds)
    tops = sorted(rows.get("top", ()), key=lambda row: (row.value, row.device))
    bots = sorted(rows.get("bot", ()), key=lambda row: (row.value, row.device))
    top_values = sorted({row.value for row in tops})
    by_value: dict[Fraction, list[Row]] = {}
    for row in tops:
        by_value.setdefault(row.value, []).append(row)
    goal = target.center()
    feedback = _feedback(request)
    source = request.input("ref" if feedback else "vin")
    assert isinstance(source, Bounds)
    level = source.center()
    accepted: list[tuple[tuple[object, ...], Row, Row]] = []
    failed: list[tuple[tuple[object, ...], Row, Row]] = []
    for bot in bots:
        if feedback:
            if goal <= level:
                continue
            nominal_current = level / bot.value
            ideal = bot.value * (goal / level - 1)
        else:
            if not 0 < goal < level:
                continue
            nominal_current = goal / bot.value
            ideal = bot.value * (level / goal - 1)
        if not current.contains(nominal_current, nominal_current):
            continue
        for value in bracket(top_values, ideal):
            for top in by_value[value]:
                low, high, nominal, *_ = _outputs(request, top, bot)
                order = (abs(nominal - goal), high - low, bot.value, top.value, top.device, bot.device)
                if target.contains(low, high):
                    accepted.append((order, top, bot))
                else:
                    failed.append(((overshoot(target, low, high), *order), top, bot))
    if accepted:
        _, top, bot = min(accepted, key=lambda item: item[0])
        message, achieved = _texts(request, top, bot)
        return Solution(MappingProxyType({"top": top, "bot": bot}), message, achieved)
    t0, t1 = bounded(target, "target")
    name = _name(request)
    hint = "a tighter resistor family (a smaller tolerance), a wider target, or a tighter reference"
    if not failed:
        return Solution(
            message=(
                f"{request.group}: voltage_divider: no resistor value gives a divider current within "
                f"{range_text(*bounded(current, 'current'), places=2, scale=6)} µA"
            ),
            hint="widen the current window, or add rows whose values reach it",
        )
    _, top, bot = min(failed, key=lambda item: item[0])
    low, high, *_ = _outputs(request, top, bot)
    above = high - t1 if target.high is not None and high > t1 else Fraction(0)
    below = t0 - low if target.low is not None and low < t0 else Fraction(0)
    miss = max(above, below)
    side = "above" if above >= below else "below"
    microvolts = (miss * 10**6).__ceil__()
    message = (
        f"{request.group}: no {family_text((top, bot))} pair keeps {name} within "
        f"{range_text(t0, t1)} V; the best, "
        f"top {describe(top)} / bottom {describe(bot)}, reaches {range_text(low, high)} V "
        f"({microvolts} µV {side})"
    )
    return Solution(message=message, hint=hint)


def evaluate(request: GeneratorRequest, chosen: Mapping[str, Row]) -> Solution:
    """The locked pair judged with the inputs of ``request``: its texts when accepted, else no rows."""
    top, bot = chosen["top"], chosen["bot"]
    message, achieved = _texts(request, top, bot)
    if _accepted(request, top, bot):
        return Solution(MappingProxyType(dict(chosen)), message, achieved)
    return Solution(message=message, achieved=achieved)


__all__ = ["ROLES", "evaluate", "solve"]
