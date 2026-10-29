# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Library definitions: footprints and symbols as reference data, independent of any ``Design``.

Definitions are read-only projections of library files. Footprints reuse the board ``Pad`` and
``Graphic`` entities with positions relative to the definition's origin and no net. Symbol pins,
units and alternates are plain value objects; a pin is identified by ``(unit, body_style, number)``.
Unit 0 and body style 0 mean "common to all units" and "common to all body styles".
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field, replace
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


PPM = 1_000_000
"""The scale 1 of a ``ModelPlacement``, in parts per million."""


@dataclass(frozen=True, slots=True)
class ModelPlacement:
    """A 3D model of a footprint with its placement (change c0223). ``path`` names the model file as the
    target writes it; ``offset`` is ``(x, y, z)`` in nm in the footprint frame (Y down, as every point of the
    model; Z up from the face the footprint is on); ``rotation`` the turns ``(x, y, z)`` in µdeg,
    counter-clockwise seen from the positive axis; ``scale`` ``(x, y, z)`` in ppm."""

    path: str
    offset: tuple[Nm, Nm, Nm] = (0, 0, 0)
    rotation: tuple[Udeg, Udeg, Udeg] = (0, 0, 0)
    scale: tuple[int, int, int] = (PPM, PPM, PPM)


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
    net_ties: tuple[tuple[str, ...], ...] = field(default=(), metadata=ORDERED)
    """The net-tie groups of the footprint (change c0114), as ``FootprintInstance.net_ties``."""
    placements: tuple[ModelPlacement, ...] = field(default=(), metadata=ORDERED)
    """The 3D models of a footprint read from another format, each with its placement (change c0223); a
    footprint read from KiCad keeps its ``model`` children as read in ``models`` and holds none here."""

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
    """A vector primitive in symbol-local coordinates (nanometres). ``unit`` and ``body_style`` say which
    unit and body style draw it; 0 (the default) is common to all (change c0261)."""

    kind: Literal["line", "circle", "rect", "polygon"]
    points: tuple[Point, ...] = field(metadata=ORDERED)
    width: Nm = 254_000
    filled: bool = False
    unit: int = 0
    body_style: int = 0


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


def flatten_symbol(symbol: SymbolDef, parents: Sequence[SymbolDef] = ()) -> SymbolDef:
    """``symbol`` with the body of the root of its ``extends`` chain (change c0261): the root's flags, units,
    pins and graphics, ``extends`` cleared, and the properties of the chain, the nearest first. ``parents``
    holds the symbols it may extend, in any order; a symbol without ``extends`` is returned as it is.
    ``ValueError`` names a missing parent or a loop."""
    by_name = {parent.name: parent for parent in parents}
    chain = [symbol]
    while chain[-1].extends:
        parent = by_name.get(chain[-1].extends)
        if parent is None or parent in chain:
            raise ValueError(f"{symbol.lib_id}: cannot resolve the symbol {chain[-1].extends!r} it extends")
        chain.append(parent)
    if len(chain) == 1:
        return symbol
    properties: dict[str, str] = {}
    for item in reversed(chain):
        properties.update(item.properties)
    return replace(
        chain[-1],
        id=symbol.id,
        native_ids=symbol.native_ids,
        name=symbol.name,
        library=symbol.library,
        properties=properties,
    )


PinGroup = Literal["", "supply", "ground", "input", "control", "output", "io", "passive", "nc"]
"""The function group of a pin-table row (change c0261); ``""`` takes the default group of its type."""
PinSide = Literal["", "left", "right", "top", "bottom"]
"""The side of a generated symbol a row is drawn on; ``""`` takes the side of its group."""


@dataclass(frozen=True, slots=True)
class PinRow:
    """One row of a pin table (``fenolite.pins.v0``, change c0261): the facts of one pin. ``unit`` is
    ``None`` when the table leaves the split to the generator; ``stacked`` holds further pad numbers of the
    same pin."""

    number: str
    name: str
    etype: PinType
    group: PinGroup = ""
    side: PinSide = ""
    bus: str = ""
    unit: int | None = None
    shape: PinShape = "line"
    hidden: bool = False
    stacked: tuple[str, ...] = field(default=(), metadata=ORDERED)
    alternates: tuple[PinAlternate, ...] = field(default=(), metadata=ORDERED)


@dataclass(frozen=True, slots=True)
class PinVariant:
    """A ``[[variant]]`` row of a pin table: a derived symbol with only its own properties."""

    name: str
    value: str = ""
    description: str = ""
    datasheet: str = ""
    footprint: str = ""
    keywords: tuple[str, ...] = field(default=(), metadata=ORDERED)
    fp_filters: tuple[str, ...] = field(default=(), metadata=ORDERED)


@dataclass(frozen=True, slots=True)
class PinTable:
    """A parsed pin table (``fenolite.pins.v0``, change c0261), rows in table order.

    ``namespace``, ``version``, ``summary``, ``licence``, ``evidence``, ``sources`` and ``category`` are the
    minimum of the record header that change c0259 owns; the rest is the body: the ``[symbol]`` settings,
    ``unit_names`` as ``(unit, name)`` pairs and the variants."""

    name: str
    rows: tuple[PinRow, ...] = field(default=(), metadata=ORDERED)
    namespace: str = ""
    version: str = ""
    summary: str = ""
    licence: str = ""
    evidence: str = ""
    sources: tuple[str, ...] = field(default=(), metadata=ORDERED)
    category: str = ""
    reference: str = "U"
    description: str = ""
    keywords: tuple[str, ...] = field(default=(), metadata=ORDERED)
    split_above: int = 100
    unit_pins: int = 48
    auto_bus: bool = True
    unit_names: tuple[tuple[int, str], ...] = field(default=(), metadata=ORDERED)
    variants: tuple[PinVariant, ...] = field(default=(), metadata=ORDERED)


@dataclass(frozen=True, slots=True)
class Library:
    """A set of definitions under one name (the schema root of ``library.json``)."""

    name: str = ""
    footprints: tuple[FootprintDef, ...] = ()
    symbols: tuple[SymbolDef, ...] = ()


__all__ = [
    "PPM",
    "FootprintDef",
    "FootprintKind",
    "Library",
    "ModelPlacement",
    "PinAlternate",
    "PinGroup",
    "PinRow",
    "PinShape",
    "PinSide",
    "PinTable",
    "PinVariant",
    "PowerKind",
    "SymbolDef",
    "SymbolGraphic",
    "SymbolPin",
    "SymbolUnit",
    "flatten_symbol",
]
