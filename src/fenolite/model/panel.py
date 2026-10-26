# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""A panel: several copies of one built board in rows and columns, with rails, separations, fiducials and
tooling holes (capability design-model, "Panels in the model"; change c0173).

The panel is a definition outside ``Design``, as a drawing sheet is: written as canonical JSON
``<name>.panel.json`` (schema ``schemas/fenolite.model.v0/panel.json``), lengths in nanometres and angles
in microdegrees. Its coordinates are panel-relative: the origin is the panel's top-left corner and Y points
down, as ``board()`` of a design script. ``fenolite.panel.layout`` turns a panel and its board into the
places of every copy, tab, hole and score line; nothing here is laid out.
"""

from __future__ import annotations

from dataclasses import dataclass, field, fields
from typing import Literal

from fenolite.core.coords import Point
from fenolite.core.trig import FULL_TURN, QUARTER_TURN
from fenolite.core.units import Nm, Udeg
from fenolite.model.base import Entity
from fenolite.model.board import Side

MM = 1_000_000
PanelBackend = Literal["kicad", "altium"]
Between = Literal["columns", "rows", "rails"]
Method = Literal["vscore", "tabs"]
BETWEEN: tuple[Between, ...] = ("columns", "rows", "rails")
METHODS: tuple[Method, ...] = ("vscore", "tabs")
DEFAULT_GAP: Nm = 2 * MM
"""The routed gap of a tabbed edge set, 2 mm: the break-routing tool of S-0798 (``panel.md``)."""
DEFAULT_METHOD: Method = "tabs"
"""The separation of an edge set that the script does not name: routed with tabs, which any shape takes."""
ORDERED = {"ordered": True}


def _length(name: str, value: object, *, positive: bool = False) -> None:
    if type(value) is not int:
        raise ValueError(f"{name} must be an integer number of nanometres, got {value!r}")
    if value < 0 or (positive and value == 0):
        raise ValueError(f"{name} must be {'above' if positive else 'at least'} 0, got {value}")


@dataclass(frozen=True, slots=True)
class PanelSource:
    """The built board the panel repeats: its path as the script names it (relative to the script), the
    SHA-256 of its bytes when it was read, and its backend (``kicad`` for a ``.kicad_pcb``, ``altium`` for
    a ``.PcbDoc``)."""

    path: str
    sha256: str = ""
    backend: PanelBackend = "kicad"


@dataclass(frozen=True, slots=True)
class PanelArray:
    """``rows`` × ``cols`` copies, ``gap_x`` between columns and ``gap_y`` between rows where the edge set
    is tabbed (a V-scored set has no gap), each copy turned by ``rotation`` (a quarter turn) and, for
    Altium's array only, ``mirrored``."""

    rows: int = 1
    cols: int = 1
    gap_x: Nm = DEFAULT_GAP
    gap_y: Nm = DEFAULT_GAP
    rotation: Udeg = 0
    mirrored: bool = False

    def __post_init__(self) -> None:
        for name in ("rows", "cols"):
            value = getattr(self, name)
            if type(value) is not int or value < 1:
                raise ValueError(f"{name} must be an integer of at least 1, got {value!r}")
        _length("gap_x", self.gap_x)
        _length("gap_y", self.gap_y)
        if (
            type(self.rotation) is not int
            or self.rotation % QUARTER_TURN
            or not 0 <= self.rotation < FULL_TURN
        ):
            raise ValueError(
                f"rotation must be 0, 90, 180 or 270 degrees in µdeg, got {self.rotation!r} µdeg"
            )


@dataclass(frozen=True, slots=True)
class PanelFit:
    """Fit as many copies as ``width`` × ``height`` holds (``Panel.fit``); ``auto_rotate`` tries the
    quarter turn too and keeps the one that holds more, 0° on a tie. The layout gives the counts."""

    width: Nm
    height: Nm
    auto_rotate: bool = False

    def __post_init__(self) -> None:
        _length("width", self.width, positive=True)
        _length("height", self.height, positive=True)


@dataclass(frozen=True, slots=True)
class PanelFrame:
    """The widths of the four rails; 0 is no rail on that side."""

    top: Nm = 0
    bottom: Nm = 0
    left: Nm = 0
    right: Nm = 0

    def __post_init__(self) -> None:
        for f in fields(self):
            _length(f.name, getattr(self, f.name))


@dataclass(frozen=True, slots=True)
class Separation:
    """How the boundaries of one edge set are separated: between ``columns``, between ``rows``, or between
    the copies and the ``rails``; by ``vscore`` (boards touch) or ``tabs`` (a routed gap)."""

    between: Between
    method: Method

    def __post_init__(self) -> None:
        if self.between not in BETWEEN:
            raise ValueError(f"between must be one of {', '.join(BETWEEN)}, got {self.between!r}")
        if self.method not in METHODS:
            raise ValueError(f"method must be one of {', '.join(METHODS)}, got {self.method!r}")


@dataclass(frozen=True, slots=True)
class TabSpec:
    """The tabs of a routed edge: ``width`` wide, one per ``pitch`` of edge length (at least one), each
    with a row of ``holes`` holes of ``drill`` at a board edge, ``hole_gap`` from hole edge to hole edge;
    the holes are tangent to the board edge outside it, or reach ``inset`` into the board (at most a third
    of the drill)."""

    width: Nm = 5 * MM
    pitch: Nm = 55 * MM
    drill: Nm = 600_000
    hole_gap: Nm = 400_000
    holes: int = 5
    inset: Nm = 0

    def __post_init__(self) -> None:
        for name in ("width", "pitch", "drill"):
            _length(name, getattr(self, name), positive=True)
        _length("hole_gap", self.hole_gap)
        _length("inset", self.inset)
        if type(self.holes) is not int or self.holes < 0:
            raise ValueError(f"holes must be an integer of at least 0, got {self.holes!r}")
        if 3 * self.inset > self.drill:
            raise ValueError(
                f"inset must be at most a third of the drill ({self.drill} nm), got {self.inset}"
            )


@dataclass(frozen=True, slots=True)
class VScoreSpec:
    """The score lines: drawn ``line_width`` wide on the layer named ``layer_name``; copper is kept
    ``clearance`` from them (the default of ``panel.vscore-copper``)."""

    layer_name: str = "V-Score"
    line_width: Nm = 100_000
    clearance: Nm = 450_000

    def __post_init__(self) -> None:
        if not self.layer_name or not self.layer_name.isprintable():
            raise ValueError(f"layer_name must be printable text, got {self.layer_name!r}")
        _length("line_width", self.line_width, positive=True)
        _length("clearance", self.clearance)


@dataclass(frozen=True, slots=True)
class PanelFiducial:
    """A fiducial of the panel at ``at`` (panel-relative), on ``side``: a copper disc ``copper`` wide in a
    mask opening ``mask`` wide."""

    ref: str
    at: Point
    side: Side = "top"
    copper: Nm = MM
    mask: Nm = 2 * MM

    def __post_init__(self) -> None:
        _length("copper", self.copper, positive=True)
        _length("mask", self.mask, positive=True)
        if self.mask <= self.copper:
            raise ValueError(f"mask must be above copper ({self.copper} nm), got {self.mask}")


@dataclass(frozen=True, slots=True)
class PanelHole:
    """A non-plated tooling hole of the panel at ``at`` (panel-relative)."""

    ref: str
    at: Point
    drill: Nm = 3 * MM

    def __post_init__(self) -> None:
        _length("drill", self.drill, positive=True)


@dataclass(frozen=True, slots=True)
class FiducialSet:
    """Fiducials placed by the layout (``Panel.fiducials()`` of a script): three in an L on the rails per
    side of ``sides``, each ``copper`` wide in a mask opening ``mask`` wide."""

    copper: Nm = MM
    mask: Nm = 2 * MM
    sides: tuple[Side, ...] = field(default=("top",), metadata=ORDERED)

    def __post_init__(self) -> None:
        _length("copper", self.copper, positive=True)
        _length("mask", self.mask, positive=True)
        if self.mask <= self.copper:
            raise ValueError(f"mask must be above copper ({self.copper} nm), got {self.mask}")
        if not self.sides or any(side not in ("top", "bottom") for side in self.sides):
            raise ValueError(f"sides must name 'top' and/or 'bottom', got {self.sides!r}")
        if len(set(self.sides)) != len(self.sides):
            raise ValueError(f"sides names a side twice: {self.sides!r}")


@dataclass(frozen=True, slots=True)
class ToolingSet:
    """Tooling holes placed by the layout (``Panel.tooling_holes()``): four of ``drill`` at the corners
    of the rails."""

    drill: Nm = 3 * MM

    def __post_init__(self) -> None:
        _length("drill", self.drill, positive=True)


@dataclass(frozen=True, slots=True)
class PanelLimits:
    """The limits of the panel checks; ``None`` takes the default of ``panel.limits.DEFAULTS``, which names
    its source. Lengths in nanometres, counts as integers."""

    vscore_copper: Nm | None = None
    vscore_spacing: Nm | None = None
    vscore_spacing_warn: Nm | None = None
    vscore_thickness: Nm | None = None
    vscore_thickness_warn: Nm | None = None
    tab_copper_outer: Nm | None = None
    tab_copper_inner: Nm | None = None
    gap: Nm | None = None
    gap_warn: Nm | None = None
    tab_holes: int | None = None
    tab_spacing: Nm | None = None
    fiducial_edge: Nm | None = None
    fiducial_count: int | None = None
    size_min: Nm | None = None
    size_max: Nm | None = None
    vscore_size_min: Nm | None = None

    def __post_init__(self) -> None:
        for f in fields(self):
            value = getattr(self, f.name)
            if value is not None:
                _length(f.name, value)


@dataclass(frozen=True, slots=True, kw_only=True)
class Panel(Entity):
    """A panel of copies of one built board (``panel.json``)."""

    name: str
    source: PanelSource
    array: PanelArray = PanelArray()
    fit: PanelFit | None = None
    frame: PanelFrame = PanelFrame()
    separations: tuple[Separation, ...] = field(default=(), metadata=ORDERED)
    tabs: TabSpec = TabSpec()
    vscore: VScoreSpec = VScoreSpec()
    fiducials: tuple[PanelFiducial, ...] = field(default=(), metadata=ORDERED)
    tooling_holes: tuple[PanelHole, ...] = field(default=(), metadata=ORDERED)
    fiducial_set: FiducialSet | None = None
    tooling_set: ToolingSet | None = None
    limits: PanelLimits = PanelLimits()

    def __post_init__(self) -> None:
        seen: set[str] = set()
        for separation in self.separations:
            if separation.between in seen:
                raise ValueError(f"the edge set {separation.between!r} is separated twice")
            seen.add(separation.between)
        refs = [item.ref for item in (*self.fiducials, *self.tooling_holes)]
        for ref in refs:
            if refs.count(ref) > 1:
                raise ValueError(f"the reference {ref!r} names two fiducials or tooling holes")

    def method(self, between: Between) -> Method:
        """The separation of the edge set ``between``: the script's, else ``DEFAULT_METHOD``."""
        for separation in self.separations:
            if separation.between == between:
                return separation.method
        return DEFAULT_METHOD


__all__ = [
    "BETWEEN",
    "DEFAULT_GAP",
    "DEFAULT_METHOD",
    "FiducialSet",
    "METHODS",
    "Between",
    "Method",
    "Panel",
    "PanelArray",
    "PanelBackend",
    "PanelFiducial",
    "PanelFit",
    "PanelFrame",
    "PanelHole",
    "PanelLimits",
    "PanelSource",
    "Separation",
    "TabSpec",
    "ToolingSet",
    "VScoreSpec",
]
