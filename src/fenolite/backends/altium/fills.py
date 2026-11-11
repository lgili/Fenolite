# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The KiCad uuid that marks a fill of an Altium document through a conversion to KiCad (change c0450).

KiCad holds no fill: a conversion writes an Altium fill as a filled rectangle or polygon. Its uuid says it
was a fill, so a conversion back writes it as a fill record again (``pcbdoc.fill_geometry``). The marker is
a version-8 uuid (RFC 9562, S-0110), as ``backends.kicad.boarditems`` marks a script's items, whose first 48
bits spell ``altfil``. KiCad keeps an item's uuid on a save and on an edit of the item; a copy gets a new
uuid and is written as a region.
"""

from __future__ import annotations

import dataclasses

from fenolite.core.evidence import Evidence, Level
from fenolite.core.ids import ALTIUM_FILL_MARKER as FILL_MARKER
from fenolite.core.ids import altium_fill_uuid as fill_uuid
from fenolite.core.ids import is_altium_fill_uuid as is_fill_uuid
from fenolite.model.board import Graphic

EVIDENCE = Evidence(Level.INFERRED, hypotheses=("H-A-CONV-FILL",))
"""A conversion's claim: the fill record written for a tagged rectangle opens in Altium as the source's fill
(``docs/hypotheses.md``; settled by the kit request of c0450 task 4.2)."""

FILLS_LOCATOR = "Fills6/Data#"
"""The locator prefix of a graphic read from a fill record."""


def is_fill(graphic: Graphic) -> bool:
    """Whether a filled graphic carries the fill marker in its KiCad uuid."""
    return graphic.filled and is_fill_uuid(graphic.native_ids.get("kicad", ""))


def read_fill(graphic: Graphic) -> bool:
    """Whether a filled graphic of an Altium design was read from a fill record."""
    where = graphic.provenance
    return graphic.filled and where is not None and where.locator.startswith(FILLS_LOCATOR)


def marked(graphic: Graphic) -> Graphic:
    """``graphic`` with the fill marker as its KiCad uuid; a filled graphic only."""
    if not graphic.filled:
        return graphic
    return dataclasses.replace(graphic, native_ids={**graphic.native_ids, "kicad": fill_uuid(graphic.id)})


__all__ = [
    "EVIDENCE",
    "FILLS_LOCATOR",
    "FILL_MARKER",
    "fill_uuid",
    "is_fill",
    "is_fill_uuid",
    "marked",
    "read_fill",
]
