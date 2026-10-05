# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Generic component bodies: a rectangle with the pins a design uses (capability
altium-schematic-writer, "Generic component bodies").

The geometry is a Fenolite choice, in mils on a 100-mil grid, in the layout frame (X rightwards, Y
downwards from the body's top-left corner). The pin facts it relies on are in
``docs/formats/altium/schematic-ascii.md``: a pin's location is its body end, and its electrical end lies
the pin length further out, away from the body.
"""

# evidence: see project

from __future__ import annotations

import re
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Literal

GRID = 100
PIN_LENGTH = 200
PIN_PITCH = 100
BODY_MIN_WIDTH = 600
BODY_MIN_HEIGHT = 200
CHAR_WIDTH = 70
"""Estimated width of one character of the 10-point sheet font, in mils (a Fenolite estimate)."""
NAME_ROOM = 100
"""Room left in the body besides the pin names drawn inside it, in mils."""

Side = Literal["left", "right"]
_RUNS = re.compile(r"[0-9]+|[^0-9]+")


def natural_key(text: str) -> tuple[tuple[int, int | str], ...]:
    """Sort key of a designator: runs of ASCII digits compare as integers and before other runs
    (``2`` < ``10`` < ``A1`` < ``B``)."""
    return tuple((0, int(run)) if "0" <= run[0] <= "9" else (1, run) for run in _RUNS.findall(text))


def _round_up(value: int, step: int = GRID) -> int:
    return -(-value // step) * step


@dataclass(frozen=True)
class GenericPin:
    """One pin of a generic body: its texts, its edge and its row on that edge (0 is the top row)."""

    designator: str
    name: str
    side: Side
    row: int

    @property
    def name_shown(self) -> bool:
        """The name is drawn only when it differs from the designator, so it is never drawn twice."""
        return self.name != self.designator

    def body_end(self, width: int) -> tuple[int, int]:
        """The pin's body end, relative to the body's top-left corner (layout frame)."""
        return (0 if self.side == "left" else width), PIN_PITCH * (self.row + 1)

    def hot_end(self, width: int) -> tuple[int, int]:
        """The pin's electrical end, ``PIN_LENGTH`` away from the body (layout frame)."""
        x, y = self.body_end(width)
        return (x - PIN_LENGTH if self.side == "left" else x + PIN_LENGTH), y


@dataclass(frozen=True)
class GenericSymbol:
    """A rectangular body of ``width`` × ``height`` mils and its pins in natural order."""

    pins: tuple[GenericPin, ...]
    width: int
    height: int

    @property
    def rows(self) -> int:
        return max((p.row + 1 for p in self.pins), default=0)


def generic_symbol(pins: Sequence[tuple[str, str]]) -> GenericSymbol:
    """The generic body of ``(designator, name)`` pins: natural order, the first half (rounded up) on the
    left edge and the rest on the right edge, both from top to bottom."""
    designators = [d for d, _ in pins]
    if len(set(designators)) != len(designators):
        raise ValueError(f"a designator repeats in {sorted(designators)}")
    ordered = sorted(pins, key=lambda p: (natural_key(p[0]), p[0]))
    left = -(-len(ordered) // 2)
    placed = tuple(
        GenericPin(d, n, "left", i) if i < left else GenericPin(d, n, "right", i - left)
        for i, (d, n) in enumerate(ordered)
    )
    longest = max((len(p.name) for p in placed if p.name_shown), default=0)
    width = max(BODY_MIN_WIDTH, _round_up(NAME_ROOM + 2 * CHAR_WIDTH * longest))
    height = max(BODY_MIN_HEIGHT, PIN_PITCH * (left + 1))
    return GenericSymbol(placed, width, height)


__all__ = [
    "BODY_MIN_HEIGHT",
    "BODY_MIN_WIDTH",
    "CHAR_WIDTH",
    "GRID",
    "PIN_LENGTH",
    "PIN_PITCH",
    "GenericPin",
    "GenericSymbol",
    "Side",
    "generic_symbol",
    "natural_key",
]
