# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Pin types and pin shapes of Altium schematic records as the model's (capability altium-import,
"Schematic components and pins" and "Symbol libraries"; ``docs/formats/altium/schematic-library.md``;
change c0043)."""

# evidence: see import_evidence

from __future__ import annotations

from collections.abc import Mapping
from types import MappingProxyType

from fenolite.backends.altium.read.sch import Pin
from fenolite.model.circuit import PinType
from fenolite.model.library import PinShape

PIN_TYPES: Mapping[int, PinType] = MappingProxyType(
    {
        0: "input",
        1: "bidirectional",
        2: "output",
        3: "open_collector",
        4: "passive",
        5: "tri_state",
        6: "open_emitter",
        7: "power_in",
    }
)
"""The closed table of electrical type numbers; any other number reads as ``unspecified``."""
EDGE_DOT, EDGE_CLOCK = 1, 3


def pin_etype(pin: Pin) -> tuple[PinType, list[tuple[str, str]]]:
    """The model type of a pin and, for a number outside the table, the pair ``electrical``."""
    found = PIN_TYPES.get(pin.electrical)
    if found is None:
        return "unspecified", [("electrical", str(pin.electrical))]
    return found, []


def pin_shape(pin: Pin) -> tuple[PinShape, str]:
    """The model shape of a pin from its edge codes, and the text of its symbols when they say more than
    the shape does (``<inner edge>,<outer edge>,<inside>,<outside>``, else ``""``)."""
    dot, clock = pin.outer_edge == EDGE_DOT, pin.inner_edge == EDGE_CLOCK
    shape: PinShape = (
        "inverted_clock" if dot and clock else ("inverted" if dot else ("clock" if clock else "line"))
    )
    other = (
        pin.inner_edge not in (0, EDGE_CLOCK)
        or pin.outer_edge not in (0, EDGE_DOT)
        or pin.inside != 0
        or pin.outside != 0
    )
    return shape, f"{pin.inner_edge},{pin.outer_edge},{pin.inside},{pin.outside}" if other else ""


__all__ = ["PIN_TYPES", "pin_etype", "pin_shape"]
