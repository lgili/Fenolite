# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""``shunt``: a current-sense resistor for an amplifier's full-scale input (change c0254,
``docs/picking.md``, "shunt").

A row is accepted when its worst-case drop at the largest load current, ``I,max · R,max``, stays within the
smallest full-scale input ``VFS,min`` and its power rating covers ``I,max² · R,max`` times the derating
factor of the request (1 until change c0253 gives ``design.derating``). The largest value wins (the best
resolution), then the smaller case, then the device id. The DSL declares the part's class ``shunt`` for
net roles (change c0222).
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from fractions import Fraction
from types import MappingProxyType

from fenolite.core.partquery import GeneratorRequest
from fenolite.pick.generators import Solution, bounded, describe, range_text, span
from fenolite.pick.lockpicks import micro_text
from fenolite.pick.rows import Row, case_rank

ROLES = ("r",)


def _derating(request: GeneratorRequest) -> Fraction:
    found = request.input("derating")
    return found if isinstance(found, Fraction) else Fraction(1)


def _eval(request: GeneratorRequest, row: Row) -> tuple[Fraction, Fraction, bool]:
    _, i_max = bounded(request.input("current"), "current")
    vfs_min, _ = bounded(request.input("full_scale"), "full_scale")
    _, r_max = span(row)
    drop, dissipation = i_max * r_max, i_max**2 * r_max
    rating = row.attributes.get("power")
    powered = isinstance(rating, Fraction) and rating * _derating(request) >= dissipation
    return drop, dissipation, drop <= vfs_min and powered


def _texts(request: GeneratorRequest, row: Row) -> tuple[str, str]:
    drop, dissipation, _ = _eval(request, row)
    vfs_min, _ = bounded(request.input("full_scale"), "full_scale")
    message = (
        f"{request.group}: shunt {describe(row)}: drop at most "
        f"{range_text(drop, drop, places=3, scale=3).split('–')[1]} mV "
        f"of {range_text(vfs_min, vfs_min, places=3, scale=3).split('–')[0]} mV full scale, "
        "dissipation at most "
        f"{range_text(dissipation, dissipation, places=3, scale=3).split('–')[1]} mW"
    )
    return message, micro_text("drop", "V", Fraction(0), drop)


def solve(request: GeneratorRequest, rows: Mapping[str, Sequence[Row]]) -> Solution:
    good = [row for row in rows.get("r", ()) if _eval(request, row)[2]]
    if good:
        row = min(
            good, key=lambda found: (-found.value, case_rank(found.attributes.get("case")), found.device)
        )
        message, achieved = _texts(request, row)
        return Solution(MappingProxyType({"r": row}), message, achieved)
    return Solution(
        message=f"{request.group}: no shunt row keeps the drop within the full scale with its power rating",
        hint="add smaller shunt values, or rows with a larger power rating",
    )


def evaluate(request: GeneratorRequest, chosen: Mapping[str, Row]) -> Solution:
    row = chosen["r"]
    message, achieved = _texts(request, row)
    if _eval(request, row)[2]:
        return Solution(MappingProxyType(dict(chosen)), message, achieved)
    return Solution(message=message, achieved=achieved)


__all__ = ["ROLES", "evaluate", "solve"]
