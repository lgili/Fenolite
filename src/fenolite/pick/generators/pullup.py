# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""``i2c_pull_ups``: one pull-up value for both lines of an I2C bus (change c0254, ``docs/picking.md``,
"i2c_pull_ups").

The window of the I2C specification (S-0941, section 7.1): ``Rp,min = (VDD,max − VOL) / IOL`` and
``Rp,max = tr / (k · Cb,max)`` with ``k = ln(7/3)`` (the rise from 0.3·VDD to 0.7·VDD of an RC charge), its
upper enclosure used so that the window is never wider than the exact one. ``VOL``, ``IOL`` and ``tr`` are
the specification's values for the speed mode (``MODES``). The largest resistor value whose worst-case span
lies inside the window wins (the least current), then the device id.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from fractions import Fraction
from types import MappingProxyType

from fenolite.core.partquery import GeneratorRequest
from fenolite.pick.generators import LN_7_3, Solution, bounded, describe, range_text, span
from fenolite.pick.rows import Row

ROLES = ("sda", "scl")
MODES: Mapping[str, tuple[Fraction, Fraction, Fraction]] = MappingProxyType(
    {
        "standard": (Fraction("0.4"), Fraction(3, 1000), Fraction(1000, 10**9)),
        "fast": (Fraction("0.4"), Fraction(3, 1000), Fraction(300, 10**9)),
        "fast-plus": (Fraction("0.4"), Fraction(20, 1000), Fraction(120, 10**9)),
    }
)
"""Speed mode → ``(VOL, IOL, tr max)`` in V, A and s: S-0941, table 10 (``VOL1`` at the sink current of the
mode, ``VDD > 2 V``) and the rise time of SDA and SCL."""
SOURCE = "S-0941"


def window(request: GeneratorRequest) -> tuple[Fraction, Fraction]:
    """``(Rp,min, Rp,max)`` of the request, in ohms."""
    mode = str(request.input("mode") or "fast")
    vol, iol, rise = MODES[mode]
    _, vdd_max = bounded(request.input("vdd"), "vdd")
    _, cb_max = bounded(request.input("bus_capacitance"), "bus_capacitance")
    return (vdd_max - vol) / iol, rise / (LN_7_3[1] * cb_max)


def _texts(request: GeneratorRequest, row: Row) -> tuple[str, str]:
    low, high = window(request)
    r0, r1 = span(row)
    message = (
        f"{request.group}: i2c_pull_ups {describe(row)} on both lines: window "
        f"{range_text(low, high, places=1)} Ω "
        f"({request.input('mode') or 'fast'} mode), the part spans {range_text(r0, r1, places=1)} Ω"
    )
    return message, f"Rp {(r0 * 10**6).__floor__()}uohm..{(r1 * 10**6).__ceil__()}uohm"


def solve(request: GeneratorRequest, rows: Mapping[str, Sequence[Row]]) -> Solution:
    low, high = window(request)
    scl = {row.device for row in rows.get("scl", ())}
    shared = [row for row in rows.get("sda", ()) if row.device in scl]
    inside = [
        row for row in shared if row.tolerance is not None and low <= span(row)[0] and span(row)[1] <= high
    ]
    if inside:
        row = min(inside, key=lambda found: (-found.value, found.device))
        message, achieved = _texts(request, row)
        return Solution(MappingProxyType({"sda": row, "scl": row}), message, achieved)
    return Solution(
        message=(
            f"{request.group}: no resistor row lies inside the pull-up window "
            f"{range_text(low, high, places=1)} Ω "
            f"({request.input('mode') or 'fast'} mode)"
        ),
        hint="a tighter resistor family, a smaller bus capacitance, or a slower mode",
    )


def evaluate(request: GeneratorRequest, chosen: Mapping[str, Row]) -> Solution:
    row = chosen["sda"]
    low, high = window(request)
    message, achieved = _texts(request, row)
    r0, r1 = span(row)
    if chosen["scl"].device == row.device and low <= r0 and r1 <= high:
        return Solution(MappingProxyType(dict(chosen)), message, achieved)
    return Solution(message=message, achieved=achieved)


__all__ = ["MODES", "ROLES", "SOURCE", "evaluate", "solve", "window"]
