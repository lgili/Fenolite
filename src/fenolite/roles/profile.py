# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The role profile: the default limits of the role checks, and their overrides (change c0222; capability
net-roles, "Role profile" and "Role limit overrides"; ``docs/roles.md``, "Default limits").

The maintainer's decision of 2026-10-28 departs, for the role checks only, from the rule that every limit
comes from the user (board-analyses, "No shipped requirement values"). The defaults live here, outside
``fenolite.analysis``, and ``fenolite analyze`` never reads them. Each default names its source (an ``S-``
id of ``docs/evidence/sources.md``, or the ``H-G-ROLE-`` hypothesis that measures a Fenolite heuristic) and
its evidence label. The profile holds no creepage or clearance value, no temperature rise, no copper
thickness and no current: those come from the user, or nothing is judged.

A ``RoleLimit`` overrides a key for the whole design, for one kind or for one net; the most specific wins.
A limit from the requirements file (a temperature rise) is the user's as well. ``resolve`` says which value
holds for a net and where it came from: ``profile``, ``override`` or ``requirements``.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass

from fenolite.model.rules import ROLE_LIMIT_UNITS, RoleLimit

MM2 = 1_000_000_000_000
"""One square millimetre in square nanometres."""


@dataclass(frozen=True, slots=True)
class Default:
    """One key of the profile: its default value (``None``: no default ships), its unit, its source and its
    evidence label, and what it means."""

    key: str
    value: int | None
    unit: str
    source: str
    label: str
    meaning: str


DEFAULTS: Mapping[str, Default] = {
    found.key: found
    for found in (
        Default(
            "width_per_amp_nm", 381_000, ROLE_LIMIT_UNITS["width_per_amp_nm"], "S-0851", "INFERRED",
            "the rule of thumb of a power track's width: 15 mil (0.381 mm) per ampere, used when no "
            "temperature rise is given",
        ),
        Default(
            "milliamps_per_via", 200, ROLE_LIMIT_UNITS["milliamps_per_via"], "S-0851", "INFERRED",
            "one standard via per 200 mA at a layer change of a power path; the via size is not stated",
        ),
        Default(
            "kelvin_inner_edge", 1, ROLE_LIMIT_UNITS["kelvin_inner_edge"], "S-0850", "INFERRED",
            "the sense branch of a Kelvin connection attaches on the inner half of the shunt's sense pad",
        ),
        Default(
            "kelvin_pair", 1, ROLE_LIMIT_UNITS["kelvin_pair"], "S-0852", "INFERRED",
            "the two sense branches of a Kelvin connection run as a coupled pair",
        ),
        Default(
            "loop_ratio_max", 2000, ROLE_LIMIT_UNITS["loop_ratio_max"], "H-G-ROLE-LOOP-RATIO", "INFERRED",
            "a hot loop's area at most twice its placement bound (Fenolite heuristic)",
        ),
        Default(
            "loop_bound_floor_nm2", MM2, ROLE_LIMIT_UNITS["loop_bound_floor_nm2"], "H-G-ROLE-LOOP-RATIO",
            "INFERRED", "below this bound (1 mm²) a loop's ratio is not judged (Fenolite heuristic)",
        ),
        Default(
            "pair_ratio_max", 2000, ROLE_LIMIT_UNITS["pair_ratio_max"], "H-G-ROLE-KELVIN-PAIR", "INFERRED",
            "the area between the sense branches at most twice its bound (Fenolite heuristic after S-0852)",
        ),
        Default(
            "switching_distance_nm", 1_000_000, ROLE_LIMIT_UNITS["switching_distance_nm"], "H-G-ROLE-NEAR-SW",
            "INFERRED", "sense, gate and sensitive copper at least 1 mm from switching copper on its layer, "
            "and none over it on an adjacent layer (Fenolite heuristic after S-0852 and S-0851)",
        ),
        Default(
            "gate_ratio_max", 2000, ROLE_LIMIT_UNITS["gate_ratio_max"], "H-G-ROLE-LOOP-RATIO", "INFERRED",
            "a gate loop's area at most twice its bound (Fenolite heuristic after S-0853 and S-0852)",
        ),
        Default(
            "shunt_max_mohm", 100, ROLE_LIMIT_UNITS["shunt_max_mohm"], "H-G-ROLE-INFER", "INFERRED",
            "a resistor of at most 100 mΩ is a shunt, for the classes only (Fenolite heuristic)",
        ),
        Default(
            "high_voltage_mv", None, ROLE_LIMIT_UNITS["high_voltage_mv"], "user", "",
            "none: no net is high voltage unless the user gives its working voltage; with this limit, only a "
            "working voltage at or above it",
        ),
        Default(
            "loop_max", None, ROLE_LIMIT_UNITS["loop_max"], "user", "",
            "none: the largest area of a hot loop is the user's",
        ),
        Default(
            "gate_max", None, ROLE_LIMIT_UNITS["gate_max"], "user", "",
            "none: the largest area of a gate loop is the user's",
        ),
        Default(
            "temp_rise_mk", None, ROLE_LIMIT_UNITS["temp_rise_mk"], "user", "",
            "none: the capacity fit of S-0269 runs only at the user's temperature rise",
        ),
    )
}  # fmt: skip
"""The whole default profile, keyed as ``ROLE_LIMIT_UNITS``."""
NO_DEFAULTS = (
    "creepage and clearance: the user's [[distance]] and [[step]] rows (no freely usable table was found; "
    "the paid standards are not copied, S-0854 gives the method only)",
    "temperature rise and copper thickness: the user's rise; the thickness from the stack-up or the option",
    "current: the role's milliamps, a [[current]] row, or --current",
)
"""What the profile deliberately leaves to the user."""


@dataclass(frozen=True, slots=True)
class Limit:
    """The limit in force for one key and one net: its value (``None``: no limit), and where it came from
    (``profile``, ``override`` or ``requirements``) with the source id of a profile default."""

    key: str
    value: int | None
    origin: str
    source: str

    def text(self) -> str:
        """``key=value (origin[, source])`` for a finding's message."""
        cited = f", {self.source}" if self.origin == "profile" else ""
        return f"{self.key}={self.value} ({self.origin}{cited})"


def resolve(
    key: str,
    limits: Sequence[RoleLimit],
    *,
    net: str | None = None,
    kind: str | None = None,
    requirements: Mapping[str, int] | None = None,
) -> Limit:
    """The value of ``key`` for a net named ``net`` of role kind ``kind``: a ``RoleLimit`` of that net, then
    one of that kind, then one of the whole design, then the requirements file (``requirements``, key →
    value), then the profile default. ``KeyError`` for an unknown key."""
    default = DEFAULTS[key]
    mine = [found for found in limits if found.key == key]
    for matched in (
        [found for found in mine if net is not None and found.net == net],
        [found for found in mine if kind is not None and found.net is None and found.kind == kind],
        [found for found in mine if found.net is None and found.kind is None],
    ):
        if matched:
            return Limit(key, matched[0].value, "override", "")
    if requirements is not None and key in requirements:
        return Limit(key, requirements[key], "requirements", "")
    return Limit(key, default.value, "profile", default.source)


__all__ = ["DEFAULTS", "MM2", "NO_DEFAULTS", "Default", "Limit", "resolve"]
