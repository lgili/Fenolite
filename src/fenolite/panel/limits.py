# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The limits of the panel checks and the public figures they come from (capability board-panels, "Panel
limits cite their sources"; ``H-G-PANEL-LIMITS``; change c0173, design Decision 6).

Each default of ``DEFAULTS`` names the fact row of ``docs/formats/kicad/panel.md`` it comes from (a text the
row holds), the sources of that row, and the figure of the row it equals. Fabricators differ: where two
publish different figures, the stricter one is the error and the other the warning. ``Panel(limits=…)``
replaces any default by the user's value (``resolved``); the docs say to confirm with the fabricator.
No figure comes from a panelisation tool (S-0802 is prior art only).
"""

from __future__ import annotations

import dataclasses
from dataclasses import dataclass

from fenolite.model.panel import PanelLimits

MM = 1_000_000


@dataclass(frozen=True, slots=True)
class Default:
    """A default limit: ``value`` (nm, or a count), the ``row`` of ``panel.md`` it comes from (a text that
    row holds), the row's ``sources`` it relies on, and the ``figure`` of the row it equals."""

    value: int
    row: str
    sources: tuple[str, ...]
    figure: str


DEFAULTS: dict[str, Default] = {
    "vscore_copper": Default(
        450_000, "Copper is kept at least 0.45 mm from a V-score", ("S-0799",), "0.45 mm"
    ),
    "vscore_spacing": Default(2 * MM, "Two V-score lines are at least", ("S-0796",), "2 mm"),
    "vscore_spacing_warn": Default(5 * MM, "Two V-score lines are at least", ("S-0798", "S-0801"), "5.00 mm"),
    "vscore_thickness": Default(600_000, "V-score needs a board of at least", ("S-0794",), "0.6 mm"),
    "vscore_thickness_warn": Default(800_000, "V-score needs a board of at least", ("S-0801",), "0.8 mm"),
    "tab_copper_outer": Default(
        250_000, "Copper is kept at least 0.25 mm (outer layers)", ("S-0799",), "0.25 mm"
    ),
    "tab_copper_inner": Default(
        400_000, "Copper is kept at least 0.25 mm (outer layers)", ("S-0799",), "0.40 mm"
    ),
    "gap": Default(1_200_000, "Routed gaps between boards are typically", ("S-0795",), "1.2 mm"),
    "gap_warn": Default(2 * MM, "Routed gaps between boards are typically", ("S-0798",), "2.00 mm"),
    "tab_holes": Default(5, "A mouse bite is a set of", ("S-0795",), "5 to 8 holes"),
    "tab_spacing": Default(60 * MM, "Two tab sets per board", ("S-0795",), "60 mm"),
    "fiducial_edge": Default(3_850_000, "A fiducial's centre is at least 3.85 mm", ("S-0794",), "3.85 mm"),
    "fiducial_count": Default(3, "three in an L", ("S-0797",), "three"),
    "size_min": Default(50 * MM, "Panel sizes:", ("S-0800",), "50 × 50 mm"),
    "size_max": Default(250 * MM, "Panel sizes:", ("S-0795",), "250 mm"),
    "vscore_size_min": Default(70 * MM, "Panel sizes:", ("S-0794",), "70 × 70 mm"),
}
"""Every limit of ``PanelLimits`` with its default and the row it comes from."""


@dataclass(frozen=True, slots=True)
class Limits:
    """Every limit resolved to a value: the user's, else the default."""

    vscore_copper: int
    vscore_spacing: int
    vscore_spacing_warn: int
    vscore_thickness: int
    vscore_thickness_warn: int
    tab_copper_outer: int
    tab_copper_inner: int
    gap: int
    gap_warn: int
    tab_holes: int
    tab_spacing: int
    fiducial_edge: int
    fiducial_count: int
    size_min: int
    size_max: int
    vscore_size_min: int


def resolved(limits: PanelLimits) -> Limits:
    """``limits`` with each ``None`` replaced by its default."""
    values = {
        f.name: (DEFAULTS[f.name].value if getattr(limits, f.name) is None else getattr(limits, f.name))
        for f in dataclasses.fields(limits)
    }
    return Limits(**values)


def user_values(limits: PanelLimits) -> dict[str, int]:
    """The limits the user set, by name."""
    return {
        f.name: getattr(limits, f.name)
        for f in dataclasses.fields(limits)
        if getattr(limits, f.name) is not None
    }


__all__ = ["DEFAULTS", "Default", "Limits", "resolved", "user_values"]
