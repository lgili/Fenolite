# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The issue codes of a conversion (capability design-conversion; change c0159)."""

from __future__ import annotations

from collections.abc import Mapping
from types import MappingProxyType

from fenolite.core.errors import Issue, Severity

ISSUE_CODES: Mapping[str, tuple[Severity, ...]] = MappingProxyType(
    {
        "convert.changed": ("info",),
        "convert.kept": ("info",),
        "convert.lossy": ("warning",),
        "convert.no-verify": ("warning",),
        "convert.schematic-unverified": ("warning",),
        "convert.unexplained": ("error",),
    }
)
"""Every ``convert.*`` code with its only severity: ``convert.lossy`` per kind with losses, whatever its loss
class (change c0429; a ``refuse`` kind's loss also needs ``allow_lossy``), ``convert.changed`` per kind with
changes, ``convert.kept`` per kind with items kept in the model for the
source's format (change c0424), ``convert.no-verify`` for a conversion that was not read back,
``convert.schematic-unverified`` for a written schematic that could not be compared with the source's (a KiCad
downgrade whose sheets need ``kicad-cli`` for their netlist and found none), and ``convert.unexplained`` per
difference of the read-back that no loss and no rule explains."""


DRAWING_STAND_IN = (
    "an Altium record without a KiCad item of its kind is drawn as a KiCad shape; its record travels in the "
    "sheet carrier"
)
DRAWING_CARRIED = "an Altium record that KiCad cannot draw travels in the sheet carrier and is not drawn"
DRAWING_HARNESS = (
    "a harness is drawn as a bus group, local labels and a rectangle; its records travel in the sheet carrier"
)
DRAWING_POWER = "a power port is drawn by an authored KiCad power symbol of its style"
DRAWING_REFUSED = (
    "the source drawing could not be written; positions and wires are regenerated from the circuit"
)
KICAD_LABEL_STAND_IN = (
    "a KiCad global label is written as an Altium power port; the sheet carrier keeps its kind and shape"
)
KICAD_POWER_STAND_IN = (
    "a KiCad power symbol is written as an Altium power port; the sheet carrier keeps its symbol and field "
    "poses"
)
KICAD_FLAG_CARRIED = "a KiCad power flag names no net: it travels in the sheet carrier and is not drawn"
KICAD_CARRIED = "a KiCad item that Altium cannot draw travels in the sheet carrier and is not drawn"
DRAWING_BOARD_ONLY = (
    "the component is on the PCB document only: no sheet draws it, and KiCad keeps its footprint without a "
    "symbol"
)
DRAWING_REASONS: tuple[str, ...] = (
    DRAWING_STAND_IN, DRAWING_CARRIED, DRAWING_HARNESS, DRAWING_POWER, DRAWING_REFUSED,
    KICAD_LABEL_STAND_IN, KICAD_POWER_STAND_IN, KICAD_FLAG_CARRIED, KICAD_CARRIED, DRAWING_BOARD_ONLY,
)  # fmt: skip
"""The reasons of the rows of a converted drawing (change c0470, design D5); the ``symbol-graphic`` reasons
are ``backends.altium.drawn_symbols.CHANGED``."""


def issue(code: str, message: str, *, where: str = "", hint: str = "") -> Issue:
    """An ``Issue`` of a code of ``ISSUE_CODES``, with its only severity."""
    return Issue(code, ISSUE_CODES[code][0], message, where=where, hint=hint)


__all__ = [
    "DRAWING_CARRIED",
    "DRAWING_HARNESS",
    "DRAWING_POWER",
    "DRAWING_REASONS",
    "DRAWING_REFUSED",
    "DRAWING_STAND_IN",
    "ISSUE_CODES",
    "KICAD_CARRIED",
    "KICAD_FLAG_CARRIED",
    "KICAD_LABEL_STAND_IN",
    "KICAD_POWER_STAND_IN",
    "issue",
]
