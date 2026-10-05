# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Schematic sheets: what one schematic file holds (normative text: openspec capability ``design-model``,
"Schematic sheet definitions", change c0060).

A ``SchematicSheet`` is a definition outside ``Design``, like a ``DrawingSheet``: a generated sheet is
derived from the circuit, and a sheet read from a file is checked and compared, so it is never stored
in the ``.fenolite/`` layer files. Wires, junctions and buses are not modelled: a backend keeps them as
opaque slots of the sheet, and Fenolite derives no net from a schematic it did not write.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

from fenolite.core.coords import Point, Size
from fenolite.core.units import Udeg
from fenolite.model.base import Entity
from fenolite.model.library import SymbolDef
from fenolite.model.presentation import SheetFrameRef, TitleBlock

SymbolMirror = Literal["", "x", "y"]
LabelKind = Literal["local", "global", "hierarchical"]
LabelShape = Literal["", "input", "output", "bidirectional", "tri_state", "passive"]
ORDERED = {"ordered": True}
SYMBOL_ROTATIONS: frozenset[int] = frozenset({0, 90_000_000, 180_000_000, 270_000_000})


@dataclass(frozen=True, slots=True)
class SymbolUse:
    """One use of a symbol in a hierarchy: the project, the sheet path, and the reference and unit there."""

    project: str
    path: str
    ref: str
    unit: int = 1


@dataclass(frozen=True, slots=True)
class SheetUse:
    """One use of a sheet reference in a hierarchy: the project, the sheet path and the page there."""

    project: str
    path: str
    page: str


@dataclass(frozen=True, slots=True)
class SheetPage:
    """The page of one sheet path, as the root sheet lists it."""

    path: str
    page: str


@dataclass(frozen=True, slots=True)
class SymbolInstance(Entity):
    """A placed symbol. ``ref``, ``value`` and ``footprint`` repeat the properties of these names."""

    lib_ref: str
    position: Point
    rotation: Udeg = 0
    mirror: SymbolMirror = ""
    unit: int = 1
    body_style: int = 1
    ref: str = ""
    value: str = ""
    footprint: str = ""
    properties: dict[str, str] = field(default_factory=lambda: {})
    dnp: bool = False
    in_bom: bool = True
    on_board: bool = True
    exclude_from_sim: bool = False
    lib_name: str = ""
    uses: tuple[SymbolUse, ...] = field(default=(), metadata=ORDERED)

    def __post_init__(self) -> None:
        if self.rotation not in SYMBOL_ROTATIONS:
            raise ValueError(f"symbol rotation {self.rotation} µdeg is not 0, 90, 180 or 270 degrees")
        if self.mirror not in ("", "x", "y"):
            raise ValueError(f"symbol mirror {self.mirror!r} is not '', 'x' or 'y'")


@dataclass(frozen=True, slots=True)
class NetLabel(Entity):
    """A net label. ``kind`` has no default, so it is always written; ``shape`` is ``""`` when local."""

    kind: LabelKind
    name: str
    position: Point
    rotation: Udeg = 0
    shape: LabelShape = ""


@dataclass(frozen=True, slots=True)
class NoConnectFlag(Entity):
    """A no-connect flag at a pin end."""

    position: Point


@dataclass(frozen=True, slots=True)
class SheetRef(Entity):
    """A reference to a sub-sheet: its name, the file as written, its box and its uses."""

    name: str
    file: str
    position: Point
    size: Size
    uses: tuple[SheetUse, ...] = field(default=(), metadata=ORDERED)


@dataclass(frozen=True, slots=True, kw_only=True)
class SchematicSheet(Entity):
    """One schematic file: embedded symbols, placed symbols, labels, flags and sub-sheet references."""

    name: str
    paper: SheetFrameRef = SheetFrameRef("A4")
    title_block: TitleBlock | None = None
    lib_symbols: tuple[SymbolDef, ...] = field(default=(), metadata=ORDERED)
    symbols: tuple[SymbolInstance, ...] = field(default=(), metadata=ORDERED)
    labels: tuple[NetLabel, ...] = field(default=(), metadata=ORDERED)
    no_connects: tuple[NoConnectFlag, ...] = field(default=(), metadata=ORDERED)
    sheets: tuple[SheetRef, ...] = field(default=(), metadata=ORDERED)
    pages: tuple[SheetPage, ...] = field(default=(), metadata=ORDERED)


__all__ = [
    "SYMBOL_ROTATIONS",
    "LabelKind",
    "LabelShape",
    "NetLabel",
    "NoConnectFlag",
    "SchematicSheet",
    "SheetPage",
    "SheetRef",
    "SheetUse",
    "SymbolInstance",
    "SymbolMirror",
    "SymbolUse",
]
