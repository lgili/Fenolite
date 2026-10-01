# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Board layer: stack-up, layers, footprints, pads, copper and mechanical objects (all in nm)."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

from fenolite.core.coords import Point, Size
from fenolite.core.units import Nm, Udeg
from fenolite.model.base import Entity

LayerKind = Literal[
    "copper",
    "silkscreen",
    "soldermask",
    "solderpaste",
    "courtyard",
    "fabrication",
    "edge",
    "user",
    "mechanical",
]
StackKind = Literal["copper", "dielectric", "soldermask", "silkscreen", "solderpaste"]
PadShape = Literal["circle", "rect", "oval", "roundrect", "trapezoid", "custom"]
PadKind = Literal["smd", "thru_hole", "np_thru_hole", "connect"]
Side = Literal["top", "bottom"]
GraphicKind = Literal["line", "arc", "circle", "rect", "polygon"]
FootprintAttribute = Literal[
    "smd",
    "through_hole",
    "board_only",
    "exclude_from_pos_files",
    "exclude_from_bom",
    "dnp",
    "allow_missing_courtyard",
    "allow_soldermask_bridges",
]
ViaType = Literal["through", "blind", "buried", "micro"]
ORDERED = {"ordered": True}


@dataclass(frozen=True, slots=True)
class Layer(Entity):
    """A board layer. Names are free-form; backends map them to their own names."""

    name: str
    kind: LayerKind
    ordinal: int


@dataclass(frozen=True, slots=True)
class StackLayer(Entity):
    """One physical layer of the stack-up. Dielectric constants are decimal strings, never floats."""

    name: str
    kind: StackKind
    thickness: Nm
    material: str = ""
    epsilon_r: str = ""
    loss_tangent: str = ""


@dataclass(frozen=True, slots=True)
class Stackup(Entity):
    """The stack-up, from top to bottom (order is semantic)."""

    layers: tuple[StackLayer, ...] = field(default=(), metadata=ORDERED)
    finish: str = ""


@dataclass(frozen=True, slots=True)
class Outline(Entity):
    """Board outline polygon and cut-outs (points in order)."""

    points: tuple[Point, ...] = field(default=(), metadata=ORDERED)
    cutouts: tuple[tuple[Point, ...], ...] = field(default=(), metadata=ORDERED)


@dataclass(frozen=True, slots=True)
class PadstackLayer:
    """Pad shape on one layer (for pads whose shape differs per layer)."""

    layer: str
    shape: PadShape
    size: Size


@dataclass(frozen=True, slots=True)
class Padstack(Entity):
    """Per-layer shapes of a pad; absent when the pad has one shape on all its layers."""

    layers: tuple[PadstackLayer, ...] = field(default=(), metadata=ORDERED)


@dataclass(frozen=True, slots=True)
class Pad(Entity):
    """A pad of a footprint; ``position`` and ``rotation`` are relative to the footprint."""

    number: str
    shape: PadShape
    size: Size
    position: Point
    kind: PadKind = "smd"
    rotation: Udeg = 0
    drill: Nm | None = None
    layers: tuple[str, ...] = field(default=(), metadata=ORDERED)
    net_id: str | None = None
    padstack: Padstack | None = None


@dataclass(frozen=True, slots=True)
class FootprintInstance(Entity):
    """A placed footprint of a component. ``attributes`` are the backend's footprint flags, in order."""

    component_id: str
    lib_ref: str
    position: Point
    rotation: Udeg = 0
    side: Side = "top"
    locked: bool = False
    attributes: tuple[FootprintAttribute, ...] = field(default=(), metadata=ORDERED)
    pads: tuple[Pad, ...] = ()


@dataclass(frozen=True, slots=True)
class Track(Entity):
    start: Point
    end: Point
    width: Nm
    layer: str
    net_id: str | None = None


@dataclass(frozen=True, slots=True)
class Arc(Entity):
    start: Point
    mid: Point
    end: Point
    width: Nm
    layer: str
    net_id: str | None = None


@dataclass(frozen=True, slots=True)
class Via(Entity):
    """A via between ``layers`` (the two outermost copper layers it spans)."""

    position: Point
    diameter: Nm
    drill: Nm
    layers: tuple[str, ...] = field(default=(), metadata=ORDERED)
    net_id: str | None = None
    via_type: ViaType = "through"


@dataclass(frozen=True, slots=True)
class ZoneFill:
    """Filled copper of a zone on one layer (a derived artefact); a zone may have several per layer."""

    layer: str
    polygon: tuple[Point, ...]
    island: bool = False


@dataclass(frozen=True, slots=True)
class Zone(Entity):
    """A copper zone (pour). ``fills`` are derived and discarded when the zone changes.

    An empty ``outline`` on an imported zone means the backend keeps the outline as an opaque slot.
    """

    outline: tuple[Point, ...] = field(metadata=ORDERED)
    name: str = ""
    layers: tuple[str, ...] = field(default=(), metadata=ORDERED)
    net_id: str | None = None
    priority: int = 0
    fills: tuple[ZoneFill, ...] = field(default=(), metadata=ORDERED)


@dataclass(frozen=True, slots=True)
class Keepout(Entity):
    """An area where some kinds of objects are not allowed."""

    outline: tuple[Point, ...] = field(metadata=ORDERED)
    layers: tuple[str, ...] = field(default=(), metadata=ORDERED)
    no_tracks: bool = False
    no_vias: bool = False
    no_pads: bool = False
    no_copper_pour: bool = False
    no_footprints: bool = False


@dataclass(frozen=True, slots=True)
class Text(Entity):
    text: str
    position: Point
    layer: str
    size: Size
    thickness: Nm
    rotation: Udeg = 0


@dataclass(frozen=True, slots=True)
class Graphic(Entity):
    """A drawing primitive on a non-copper or copper layer; ``points`` meaning depends on ``kind``."""

    kind: GraphicKind
    layer: str
    points: tuple[Point, ...] = field(metadata=ORDERED)
    width: Nm = 0
    filled: bool = False


@dataclass(frozen=True, slots=True)
class Hole(Entity):
    """A mechanical hole that is not part of a footprint."""

    position: Point
    drill: Nm
    plated: bool = False


@dataclass(frozen=True, slots=True)
class Board(Entity):
    """The board layer of a design (``board.json``)."""

    outline: Outline | None = None
    layers: tuple[Layer, ...] = field(default=(), metadata=ORDERED)
    stackup: Stackup | None = None
    footprints: tuple[FootprintInstance, ...] = ()
    tracks: tuple[Track, ...] = ()
    arcs: tuple[Arc, ...] = ()
    vias: tuple[Via, ...] = ()
    zones: tuple[Zone, ...] = ()
    keepouts: tuple[Keepout, ...] = ()
    texts: tuple[Text, ...] = ()
    graphics: tuple[Graphic, ...] = ()
    holes: tuple[Hole, ...] = ()


__all__ = [
    "Arc",
    "Board",
    "FootprintAttribute",
    "FootprintInstance",
    "Graphic",
    "GraphicKind",
    "Hole",
    "Keepout",
    "Layer",
    "LayerKind",
    "Outline",
    "Pad",
    "PadKind",
    "PadShape",
    "Padstack",
    "PadstackLayer",
    "Side",
    "StackKind",
    "StackLayer",
    "Stackup",
    "Text",
    "Track",
    "Via",
    "ViaType",
    "Zone",
    "ZoneFill",
]
