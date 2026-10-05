# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Library definitions: footprints and symbols as reference data, independent of any ``Design``.

Definitions are read-only projections of library files. Footprints reuse the board ``Pad`` and
``Graphic`` entities with positions relative to the definition's origin and no net. Symbol pins,
units and alternates are plain value objects; a pin is identified by ``(unit, body_style, number)``.
Unit 0 and body style 0 mean "common to all units" and "common to all body styles".
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

from fenolite.core.coords import Point
from fenolite.core.units import Nm, Udeg
from fenolite.model.base import Entity
from fenolite.model.board import ORDERED, ComponentBody, Graphic, Pad
from fenolite.model.circuit import PinType

FootprintKind = Literal["smd", "through_hole", "unspecified"]
PinShape = Literal[
    "line", "inverted", "clock", "inverted_clock", "input_low",
    "clock_low", "output_low", "edge_clock_high", "non_logic",
]  # fmt: skip
PowerKind = Literal["", "global", "local"]


def _lib_id(library: str, name: str) -> str:
    return f"{library}:{name}" if library else name


@dataclass(frozen=True, slots=True)
class FootprintDef(Entity):
    """A footprint of a library. ``properties`` is sorted by key in the canonical form."""

    name: str
    library: str = ""
    description: str = ""
    keywords: tuple[str, ...] = field(default=(), metadata=ORDERED)
    kind: FootprintKind = "unspecified"
    flags: tuple[str, ...] = field(default=(), metadata=ORDERED)
    properties: dict[str, str] = field(default_factory=lambda: {})
    pads: tuple[Pad, ...] = field(default=(), metadata=ORDERED)
    graphics: tuple[Graphic, ...] = field(default=(), metadata=ORDERED)
    models: tuple[str, ...] = field(default=(), metadata=ORDERED)
    bodies: tuple[ComponentBody, ...] = field(default=(), metadata=ORDERED)

    @property
    def lib_id(self) -> str:
        """``"<library>:<name>"``, or the bare name when ``library`` is empty."""
        return _lib_id(self.library, self.name)

    @property
    def reference(self) -> str:
        return self.properties.get("Reference", "")

    @property
    def value(self) -> str:
        return self.properties.get("Value", "")

    def graphics_on(self, layer: str) -> tuple[Graphic, ...]:
        """The graphics drawn on ``layer`` (a backend layer name such as ``F.CrtYd``), in order."""
        return tuple(g for g in self.graphics if g.layer == layer)


@dataclass(frozen=True, slots=True)
class PinAlternate:
    """An alternate function of a pin."""

    name: str
    etype: PinType
    shape: PinShape


@dataclass(frozen=True, slots=True)
class SymbolPin:
    """A pin of a symbol; ``position`` is its connection point, ``rotation`` 0/90/180/270 degrees."""

    number: str
    name: str
    etype: PinType
    position: Point
    shape: PinShape = "line"
    rotation: Udeg = 0
    length: Nm = 0
    unit: int = 0
    body_style: int = 0
    hidden: bool = False
    alternates: tuple[PinAlternate, ...] = field(default=(), metadata=ORDERED)


@dataclass(frozen=True, slots=True)
class SymbolUnit:
    """One unit/body-style combination of a symbol."""

    unit: int
    body_style: int
    name: str = ""


@dataclass(frozen=True, slots=True)
class SymbolGraphic:
    """A vector primitive in symbol-local coordinates (nanometres)."""

    kind: Literal["line", "circle", "rect", "polygon"]
    points: tuple[Point, ...] = field(metadata=ORDERED)
    width: Nm = 254_000
    filled: bool = False


@dataclass(frozen=True, slots=True)
class SymbolDef(Entity):
    """A symbol of a library. A derived symbol read as written has ``extends`` set and no pins."""

    name: str
    library: str = ""
    extends: str = ""
    power: PowerKind = ""
    properties: dict[str, str] = field(default_factory=lambda: {})
    in_bom: bool = True
    on_board: bool = True
    exclude_from_sim: bool = False
    pin_names_hidden: bool = False
    pin_numbers_hidden: bool = False
    pin_name_offset: Nm | None = None
    units: tuple[SymbolUnit, ...] = field(default=(), metadata=ORDERED)
    pins: tuple[SymbolPin, ...] = field(default=(), metadata=ORDERED)
    graphics: tuple[SymbolGraphic, ...] = field(default=(), metadata=ORDERED)

    @property
    def lib_id(self) -> str:
        return _lib_id(self.library, self.name)

    @property
    def reference(self) -> str:
        return self.properties.get("Reference", "")

    @property
    def value(self) -> str:
        return self.properties.get("Value", "")

    @property
    def footprint(self) -> str:
        return self.properties.get("Footprint", "")

    @property
    def datasheet(self) -> str:
        return self.properties.get("Datasheet", "")

    @property
    def description(self) -> str:
        return self.properties.get("Description", "")

    @property
    def keywords(self) -> tuple[str, ...]:
        return tuple(self.properties.get("ki_keywords", "").split())

    @property
    def footprint_filters(self) -> tuple[str, ...]:
        return tuple(self.properties.get("ki_fp_filters", "").split())

    @property
    def unit_count(self) -> int:
        """The number of units (at least 1; unit 0 is common to all units)."""
        return max([u.unit for u in self.units] + [p.unit for p in self.pins] + [1])

    @property
    def body_style_count(self) -> int:
        """The number of body styles (at least 1; body style 0 is common to all styles)."""
        return max([u.body_style for u in self.units] + [p.body_style for p in self.pins] + [1])

    def pins_of(self, unit: int, body_style: int = 1) -> tuple[SymbolPin, ...]:
        """The pins of one unit drawn in one body style, common pins (unit or style 0) included."""
        return tuple(p for p in self.pins if p.unit in (0, unit) and p.body_style in (0, body_style))


@dataclass(frozen=True, slots=True)
class Library:
    """A set of definitions under one name (the schema root of ``library.json``)."""

    name: str = ""
    footprints: tuple[FootprintDef, ...] = ()
    symbols: tuple[SymbolDef, ...] = ()


__all__ = [
    "FootprintDef",
    "FootprintKind",
    "Library",
    "PinAlternate",
    "PinShape",
    "PowerKind",
    "SymbolDef",
    "SymbolGraphic",
    "SymbolPin",
    "SymbolUnit",
]
