# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""``led_resistor``: the series resistor of an LED (change c0254, ``docs/picking.md``, "led_resistor").

``I = (VS − VF) / R`` over the supply range, the forward-voltage range and the resistor's tolerance: from
``(VS,min − VF,max) / Rmax`` to ``(VS,max − VF,min) / Rmin``. A row is accepted when that range lies in
``current`` and its power rating covers the worst dissipation ``(VS,max − VF,min)² / Rmin`` times the
derating factor of the request (1 until change c0253 gives ``design.derating``). Every resistor row is
evaluated; the nominal current closest to the range's nominal wins, then the larger resistor, then the
device id.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from fractions import Fraction
from types import MappingProxyType

from fenolite.core.partquery import Bounds, GeneratorRequest
from fenolite.pick.generators import Solution, bounded, describe, overshoot, range_text, span
from fenolite.pick.lockpicks import micro_text
from fenolite.pick.rows import Row

ROLES = ("r",)


def _derating(request: GeneratorRequest) -> Fraction:
    found = request.input("derating")
    return found if isinstance(found, Fraction) else Fraction(1)


def _eval(request: GeneratorRequest, r: Row) -> tuple[Fraction, Fraction, Fraction, Fraction] | None:
    vs0, vs1 = bounded(request.input("vs"), "vs")
    vf0, vf1 = bounded(request.input("vf"), "vf")
    r0, r1 = span(r)
    low, high = (vs0 - vf1) / r1, (vs1 - vf0) / r0
    if low <= 0:
        return None
    vs, vf = request.input("vs"), request.input("vf")
    assert isinstance(vs, Bounds) and isinstance(vf, Bounds)
    nominal = (vs.center() - vf.center()) / r.value
    return low, high, nominal, (vs1 - vf0) ** 2 / r0


def _powered(request: GeneratorRequest, r: Row, dissipation: Fraction) -> bool:
    rating = r.attributes.get("power")
    return isinstance(rating, Fraction) and rating * _derating(request) >= dissipation


def _texts(request: GeneratorRequest, r: Row) -> tuple[str, str]:
    found = _eval(request, r)
    assert found is not None
    low, high, _, dissipation = found
    message = (
        f"{request.group}: led_resistor R {describe(r)}: LED current "
        f"{range_text(low, high, places=3, scale=3)} mA, "
        "resistor dissipation at most "
        f"{range_text(dissipation, dissipation, places=3, scale=3).split('–')[1]} mW"
    )
    return message, micro_text("I", "A", low, high)


def solve(request: GeneratorRequest, rows: Mapping[str, Sequence[Row]]) -> Solution:
    current = request.input("current")
    assert isinstance(current, Bounds)
    goal = current.center()
    accepted: list[tuple[tuple[object, ...], Row]] = []
    failed: list[tuple[tuple[object, ...], Row]] = []
    for r in sorted(rows.get("r", ()), key=lambda row: (row.value, row.device)):
        found = _eval(request, r)
        if found is None:
            continue
        low, high, nominal, dissipation = found
        order = (abs(nominal - goal), -r.value, r.device)
        if current.contains(low, high) and _powered(request, r, dissipation):
            accepted.append((order, r))
        else:
            failed.append(((overshoot(current, low, high), *order), r))
    if accepted:
        _, r = min(accepted, key=lambda item: item[0])
        message, achieved = _texts(request, r)
        return Solution(MappingProxyType({"r": r}), message, achieved)
    c0, c1 = bounded(current, "current")
    detail = ""
    if failed:
        _, r = min(failed, key=lambda item: item[0])
        closest = _eval(request, r)
        assert closest is not None
        detail = (
            f"; the closest, {describe(r)}, gives {range_text(closest[0], closest[1], places=3, scale=3)} mA"
        )
    return Solution(
        message=(
            f"{request.group}: no resistor keeps the LED current within "
            f"{range_text(c0, c1, places=3, scale=3)} mA with its power rating{detail}"
        ),
        hint="a wider current range, a tighter supply, or rows with a larger power rating",
    )


def evaluate(request: GeneratorRequest, chosen: Mapping[str, Row]) -> Solution:
    r = chosen["r"]
    current = request.input("current")
    assert isinstance(current, Bounds)
    found = _eval(request, r)
    if found is None:
        return Solution(
            message=f"{request.group}: the locked resistor {describe(r)} gives no forward current"
        )
    message, achieved = _texts(request, r)
    if current.contains(found[0], found[1]) and _powered(request, r, found[3]):
        return Solution(MappingProxyType(dict(chosen)), message, achieved)
    return Solution(message=message, achieved=achieved)


__all__ = ["ROLES", "evaluate", "solve"]
