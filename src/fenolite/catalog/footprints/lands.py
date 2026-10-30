# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The land calculator and its Fenolite-authored, versioned constants (change c0260, decisions 4 and 5).

Worst-case and exact: every number is an integer of nanometres, no float and no square root of a sum of
squared tolerances is used. For two facing land rows with lead-tip span ``L``, lead length ``T`` and lead
width ``W`` and the goals ``toe``, ``heel`` and ``side`` of the land class::

    Z = L.max + 2 toe          outer extent of the two lands, rounded up to the grid
    G = L.min - 2 T.max - 2 heel   inner gap, rounded down to the grid
    X = W.max + 2 side         land width, rounded up to the grid

The constants are published with their derivation in ``docs/formats/library/lands.md`` (``INFERRED``).
No value comes from IPC-7351 tables or its calculator. A released table never changes: a new calibration
is a new version.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from fractions import Fraction
from math import isqrt

from fenolite.core.quantities import LengthRange
from fenolite.core.units import Nm

LAND_CLASSES = ("chip", "molded", "gullwing", "gullwing-fine", "nolead", "smd-tab")
"""The classes of facing-row lands that have toe, heel and side goals."""
FINE_PITCH = 650_000
"""A gull-wing package whose pitch is below this belongs to the class ``gullwing-fine``."""


@dataclass(frozen=True, slots=True)
class Goals:
    """The toe, heel and side goals of one land class, in nanometres (may be negative)."""

    toe: Nm
    heel: Nm
    side: Nm


@dataclass(frozen=True, slots=True)
class LandTable:
    """One version of the land constants. A class or a constant left out has no calibration: generating
    it without a manufacturer ``[land]`` gives ``package.no-goals``."""

    version: int
    goals: Mapping[str, Goals] = field(default_factory=lambda: {})
    pad_gap: Nm = 200_000
    grid: Nm = 10_000
    courtyard: Nm = 500_000
    hole_clearance: Nm | None = None
    annular_ring: Nm | None = None
    ball_ratio: Mapping[str, Fraction] = field(default_factory=lambda: {})
    paste_cell: Nm = 2_000_000
    paste_window: Fraction = Fraction(4, 5)
    calibration: Mapping[str, tuple[str, ...]] = field(default_factory=lambda: {})
    """The records each calibrated value was derived from, by class."""


def ceil_to(value: int, grid: int) -> int:
    """``value`` rounded up to a multiple of ``grid``."""
    return -(-value // grid) * grid


def floor_to(value: int, grid: int) -> int:
    """``value`` rounded down to a multiple of ``grid``."""
    return value // grid * grid


@dataclass(frozen=True, slots=True)
class RowLand:
    """Two facing land rows: ``z`` outer extent, ``g`` inner gap, ``x`` land width."""

    z: Nm
    g: Nm
    x: Nm

    @property
    def length(self) -> Nm:
        """The land length ``(Z - G) / 2``."""
        return (self.z - self.g) // 2

    @property
    def spacing(self) -> Nm:
        """The distance between the two row centres, ``(Z + G) / 2``."""
        return (self.z + self.g) // 2


class MissingBound(Exception):
    """The calculator needs a bound that the record does not give: ``key`` and ``bound`` name it."""

    def __init__(self, key: str, bound: str) -> None:
        super().__init__(f"{key} has no {bound}")
        self.key = key
        self.bound = bound


def bound(value: LengthRange, key: str, which: str) -> Nm:
    """``value.min`` or ``value.max``; ``MissingBound`` naming ``key`` when it is not given."""
    found = value.min if which == "min" else value.max
    if found is None:
        raise MissingBound(key, which)
    return found


def facing_rows(
    span: tuple[str, LengthRange],
    lead: tuple[str, LengthRange],
    width: tuple[str, LengthRange],
    goals: Goals,
    grid: Nm,
) -> RowLand:
    """The worst-case land of two facing rows (``Z``, ``G``, ``X`` on the grid). Each argument is the key
    that names a dimension in the record and its range, so that ``MissingBound`` names the key."""
    z = ceil_to(bound(span[1], span[0], "max") + 2 * goals.toe, grid)
    g = floor_to(bound(span[1], span[0], "min") - 2 * bound(lead[1], lead[0], "max") - 2 * goals.heel, grid)
    x = ceil_to(bound(width[1], width[0], "max") + 2 * goals.side, grid)
    return RowLand(z, g, x)


def back_solve(span: LengthRange, lead: LengthRange, width: LengthRange, land: RowLand) -> Goals:
    """The goals a manufacturer's land implies (calibration, decision 5): ``toe = (Z - L.max) / 2``,
    ``heel = (L.min - 2 T.max - G) / 2``, ``side = (X - W.max) / 2``, each floored to the nanometre."""
    toe = (land.z - bound(span, "span", "max")) // 2
    heel = (bound(span, "span", "min") - 2 * bound(lead, "lead", "max") - land.g) // 2
    side = (land.x - bound(width, "width", "max")) // 2
    return Goals(toe, heel, side)


def lead_diagonal(width: Nm, thickness: Nm | None) -> Nm:
    """The diagonal of a rectangular lead, rounded up to the nanometre; ``width`` for a round lead."""
    if thickness is None:
        return width
    square = width * width + thickness * thickness
    root = isqrt(square)
    return root if root * root == square else root + 1


def drill_for(width: Nm, thickness: Nm | None, table: LandTable) -> Nm | None:
    """The drill of a through-hole lead: its diagonal plus ``hole_clearance`` up to the grid, or ``None``
    when the table has no hole clearance."""
    if table.hole_clearance is None:
        return None
    return ceil_to(lead_diagonal(width, thickness) + table.hole_clearance, table.grid)


def corner_ratio(short_side: Nm) -> int:
    """The ``roundrect`` corner ratio (parts per million of the shorter side) of the ``drawing/1`` pads:
    20 % of the shorter side, the radius capped at 100 µm."""
    if short_side <= 0:
        return 200_000
    return min(200_000, 100_000 * 1_000_000 // short_side)


def land_table(version: int) -> LandTable:
    """The released table ``version``; ``KeyError`` for an unknown version."""
    return LANDS[version]


from fenolite.catalog.footprints._table1 import TABLE as _TABLE1  # noqa: E402  (it imports the classes above)

LANDS: Mapping[int, LandTable] = {1: _TABLE1}
"""The released tables by version; ``lands/1`` is written by ``tools/calibrate_lands.py`` into ``_table1``."""


__all__ = [
    "FINE_PITCH",
    "LANDS",
    "LAND_CLASSES",
    "Goals",
    "LandTable",
    "MissingBound",
    "RowLand",
    "back_solve",
    "bound",
    "ceil_to",
    "corner_ratio",
    "drill_for",
    "facing_rows",
    "floor_to",
    "land_table",
    "lead_diagonal",
]
