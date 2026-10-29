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


RatingUnit = Literal["uV", "uA", "uW", "mK"]
"""The integer units of a device rating: µV, µA, µW and millikelvin (changes c0248 and c0274)."""
LimitKind = Literal["abs_max", "operating"]
"""The kind of a device limit (change c0274): ``abs_max``, beyond which the part may be damaged, or
``operating``, the range in which the part works as specified."""
ThresholdKey = Literal[
    "input_high_min", "input_low_max", "output_current_max", "output_high_min", "output_low_max"
]
"""The logic thresholds of a device pin (change c0274)."""


@dataclass(frozen=True, slots=True)
class Rating:
    """One limit of a device, of a device pin or of a pair of pins: ``key`` (``voltage``, ``current``,
    ``power`` or ``temperature``), its integer ``unit``, the bounds, each an ``int`` in that unit or
    ``None``, and its ``limit`` kind (change c0274)."""

    key: str
    unit: RatingUnit
    min: int | None = None
    max: int | None = None
    limit: LimitKind = "abs_max"


@dataclass(frozen=True, slots=True)
class Threshold:
    """One logic threshold of a device pin (change c0274): ``key``, its integer ``unit`` (``uV`` for a
    voltage measured from the device's ``ground``, ``uA`` for ``output_current_max``) and the value."""

    key: ThresholdKey
    unit: RatingUnit
    value: int


@dataclass(frozen=True, slots=True)
class DevicePin:
    """One function of a device: its name, the symbol pins it joins and their pads as ordered
    ``(pin, pad)`` pairs in the form of ``Component.pin_pad_map``, its limits (``voltage`` measured from the
    device's ``ground``; sorted by key then kind), its logic thresholds (sorted by key) and whether it must
    be connected."""

    function: str
    pin_pads: tuple[tuple[str, str], ...] = field(default=(), metadata=ORDERED)
    ratings: tuple[Rating, ...] = field(default=(), metadata=ORDERED)
    thresholds: tuple[Threshold, ...] = field(default=(), metadata=ORDERED)
    must_connect: bool = False

    @property
    def pins(self) -> tuple[str, ...]:
        """The symbol pins of the function, in map order, without repeats."""
        return tuple(dict.fromkeys(pin for pin, _ in self.pin_pads))

    @property
    def pads(self) -> tuple[str, ...]:
        """The pads of the function, in map order."""
        return tuple(pad for _, pad in self.pin_pads)

    def rating(self, key: str, limit: LimitKind = "abs_max") -> Rating | None:
        """The pin limit of ``key`` and kind ``limit``, or ``None``."""
        return next((found for found in self.ratings if (found.key, found.limit) == (key, limit)), None)

    def threshold(self, key: str) -> Threshold | None:
        """The logic threshold ``key``, or ``None``."""
        return next((found for found in self.thresholds if found.key == key), None)


@dataclass(frozen=True, slots=True)
class PinPairLimit:
    """A limit between two functions of a device (change c0274): ``between`` names them, the voltage being
    the first's minus the second's; ``ratings`` are ``voltage`` limits, sorted by kind."""

    between: tuple[str, ...] = field(default=(), metadata=ORDERED)
    ratings: tuple[Rating, ...] = field(default=(), metadata=ORDERED)


@dataclass(frozen=True, slots=True)
class DeviceProvenance:
    """The stamp of a device written by a tool: the tool, its source (lib ids, never a path), the ISO 8601
    date and the SHA-256 of the record as written (``fenolite.catalog.devices.device_digest``)."""

    tool: str
    source: str
    date: str
    sha256: str


@dataclass(frozen=True, slots=True)
class DeviceDef:
    """A device (change c0248): one reviewed record that joins a symbol, a footprint, the map from pin
    function to pins and pads, an identity, ratings and an evidence label. ``pins`` are in code-point order
    of their functions and ``ratings`` in order of their keys then kinds. A device is library data: it is
    never part of a ``Design``, and a built component names it only through the properties
    ``fenolite.device`` and ``fenolite.device.sha256``."""

    id: str
    summary: str = ""
    symbol: str = ""
    footprint: str = ""
    manufacturer: str = ""
    mpn: str = ""
    datasheet: str = ""
    ref_prefix: str = ""
    value: str = ""
    evidence: str = "UNVERIFIED"
    sources: tuple[str, ...] = field(default=(), metadata=ORDERED)
    ground: str = ""
    unused_pads: tuple[str, ...] = field(default=(), metadata=ORDERED)
    ends: tuple[str, ...] = field(default=(), metadata=ORDERED)
    """Two function names that the named ends of a part (``part.a`` and ``part.b``) resolve to, or ``()``."""
    properties: dict[str, str] = field(default_factory=lambda: {})
    pins: tuple[DevicePin, ...] = field(default=(), metadata=ORDERED)
    ratings: tuple[Rating, ...] = field(default=(), metadata=ORDERED)
    limits: tuple[PinPairLimit, ...] = field(default=(), metadata=ORDERED)
    """The limits between two functions, sorted by ``between`` (change c0274)."""
    cls: str = ""
    """The part class of the roles' vocabulary (TOML key ``class``), evidence for ``roles.classify``, or
    ``""`` (change c0274)."""
    provenance: DeviceProvenance | None = None

    @property
    def pad_map(self) -> tuple[tuple[str, str], ...]:
        """The derived pad map: every ``(pin, pad)`` pair of every function, sorted by pin then in map
        order, the form of ``Component.pin_pad_map``."""
        pairs = [pair for pin in self.pins for pair in pin.pin_pads]
        order = {pin: index for index, pin in enumerate(sorted({pin for pin, _ in pairs}))}
        return tuple(sorted(pairs, key=lambda pair: order[pair[0]]))

    def pin(self, function: str) -> DevicePin:
        """The function named ``function``; ``KeyError`` when the device has none."""
        for found in self.pins:
            if found.function == function:
                return found
        raise KeyError(function)

    def rating(self, key: str, limit: LimitKind = "abs_max") -> Rating | None:
        """The device rating of ``key`` and kind ``limit``, or ``None``."""
        return next((found for found in self.ratings if (found.key, found.limit) == (key, limit)), None)


@dataclass(frozen=True, slots=True)
class Library:
    """A set of definitions under one name (the schema root of ``library.json``). ``devices`` are sorted
    by id (change c0248)."""

    name: str = ""
    footprints: tuple[FootprintDef, ...] = ()
    symbols: tuple[SymbolDef, ...] = ()
    devices: tuple[DeviceDef, ...] = field(default=(), metadata=ORDERED)


__all__ = [
    "PPM",
    "DeviceDef",
    "DevicePin",
    "DeviceProvenance",
    "FootprintDef",
    "FootprintKind",
    "Library",
    "LimitKind",
    "ModelPlacement",
    "PinAlternate",
    "PinPairLimit",
    "PinShape",
    "PowerKind",
    "Rating",
    "RatingUnit",
    "SymbolDef",
    "SymbolGraphic",
    "SymbolPin",
    "SymbolUnit",
    "Threshold",
    "ThresholdKey",
]
