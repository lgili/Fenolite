# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Board layer: stack-up, layers, footprints, pads, copper and mechanical objects (all in nm)."""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from typing import Literal

from fenolite.core.coords import Point, Size
from fenolite.core.units import Nm, Udeg
from fenolite.model.base import Entity
from fenolite.model.presentation import SheetFrameRef, TitleBlock

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
DielectricKind = Literal["core", "prepreg"]
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
ZoneConnection = Literal["solid", "thermal", "none", "thru_hole_only"]
"""How a zone connects to a pad of its net; ``thru_hole_only`` means thermal reliefs on through-hole pads
and solid connections on the others."""
HoleShape = Literal["round", "square", "slot"]
BodyKind = Literal["extruded", "model"]
ZoneFillMode = Literal["solid", "hatched"]
IslandRemoval = Literal["always", "never", "below_area"]
ZoneSmoothing = Literal["none", "chamfer", "fillet"]
HatchBorder = Literal["hatch_thickness", "min_thickness"]
FieldJustifyH = Literal["left", "center", "right"]
FieldJustifyV = Literal["top", "center", "bottom"]
ORDERED = {"ordered": True}


@dataclass(frozen=True, slots=True)
class Layer(Entity):
    """A board layer. Names are free-form; backends map them to their own names."""

    name: str
    kind: LayerKind
    ordinal: int


@dataclass(frozen=True, slots=True)
class StackLayer(Entity):
    """One entry of the stack-up. Dielectric constants are decimal strings, never floats.

    ``dielectric_kind`` says whether a dielectric is a core or a prepreg (``None``: not stated), and
    ``color`` is the colour as the source names it. A dielectric made of several sheets is one entry per
    sheet, consecutive, the sheets sharing a name."""

    name: str
    kind: StackKind
    thickness: Nm
    material: str = ""
    epsilon_r: str = ""
    loss_tangent: str = ""
    dielectric_kind: DielectricKind | None = None
    color: str = ""


@dataclass(frozen=True, slots=True)
class Stackup(Entity):
    """The stack-up, from the top face to the bottom face (order is semantic).

    ``impedance_controlled`` is true when the dielectric values are requirements for the fabricator."""

    layers: tuple[StackLayer, ...] = field(default=(), metadata=ORDERED)
    finish: str = ""
    impedance_controlled: bool = False

    def thickness(self) -> Nm:
        """The sum of the entries' thicknesses: the board thickness of the model."""
        return sum(layer.thickness for layer in self.layers)

    def _index(self, name: str) -> int:
        for index, layer in enumerate(self.layers):
            if layer.name == name:
                return index
        raise KeyError(name)

    def depth(self, name: str) -> tuple[Nm, Nm]:
        """The depths, below the top face of the first entry, of the top and the bottom face of the first
        entry named ``name``. ``KeyError`` for an unknown name."""
        index = self._index(name)
        top = sum(layer.thickness for layer in self.layers[:index])
        return top, top + self.layers[index].thickness

    def between(self, upper: str, lower: str) -> tuple[StackLayer, ...]:
        """The entries strictly between the first entries named ``upper`` and ``lower``, top to bottom.
        ``KeyError`` for an unknown name, ``ValueError`` when ``upper`` does not lie above ``lower``."""
        first, last = self._index(upper), self._index(lower)
        if first >= last:
            raise ValueError(f"{upper!r} does not lie above {lower!r}")
        return self.layers[first + 1 : last]


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
    offset: Point = Point(0, 0)
    """Where the copper's centre lies on this layer relative to ``Pad.position`` (the hole's centre), in
    the footprint frame. In a library definition ``layer`` may be the wildcard ``In*.Cu``."""


@dataclass(frozen=True, slots=True)
class Padstack(Entity):
    """Per-layer shapes of a pad; absent when the pad has one shape on all its layers."""

    layers: tuple[PadstackLayer, ...] = field(default=(), metadata=ORDERED)
    hole_shape: HoleShape = "round"
    hole_length: Nm | None = None
    hole_rotation: Udeg = 0


MAX_CORNER_RATIO = 500_000
"""The largest ``Pad.corner_ratio``: half the shorter side, a pad with fully rounded ends."""
PPM_PER_PERCENT = 5_000
"""One Altium corner percentage (a percent of half the shorter side) in ``Pad.corner_ratio`` units."""


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
    zone_connection: ZoneConnection | None = None
    """How zones connect to this pad; ``None`` means that the pad follows its footprint and the zone."""
    corner_ratio: int | None = None
    """The corner radius of a ``roundrect`` pad in parts per million of the shorter side of ``size``, from 0
    to ``MAX_CORNER_RATIO`` (change c0126): 250 000 is a quarter of the shorter side. ``None`` when the model
    does not know it, and for every other shape."""


@dataclass(frozen=True, slots=True)
class FootprintField(Entity):
    """A text field of a placed footprint (Reference, Value, a user property): placement and appearance.

    The text itself stays in the component (``Component.ref``, ``value`` or ``properties[name]``).
    ``position`` and ``rotation`` follow the pad frame: the anchor on the board is the footprint's
    position plus ``position`` rotated by the footprint's angle, with no further mirror on the bottom
    side, and ``rotation`` is relative to the footprint. ``size.w`` is the glyph width and ``size.h`` the
    glyph height; ``thickness`` ``None`` means the backend's default stroke. The justifications are given
    in the reading frame of the text, and ``mirrored`` mirrors the text horizontally.
    """

    name: str
    position: Point
    layer: str
    size: Size
    rotation: Udeg = 0
    thickness: Nm | None = None
    visible: bool = True
    h_justify: FieldJustifyH = "center"
    v_justify: FieldJustifyV = "center"
    mirrored: bool = False


@dataclass(frozen=True, slots=True)
class ComponentBody(Entity):
    """The physical body of a part: a volume above the side its footprint is placed on.

    ``height`` is the distance from the board surface to the top of the body and ``standoff`` the distance
    to its underside. ``outline`` is the body's footprint as a polygon in the footprint frame (empty when
    the source gives none), ``layer`` the layer it is drawn on, and ``model`` the name of a 3D model for
    the kind ``model``. No model data is carried."""

    kind: BodyKind
    height: Nm
    standoff: Nm = 0
    outline: tuple[Point, ...] = field(default=(), metadata=ORDERED)
    layer: str = ""
    model: str = ""
    name: str = ""


@dataclass(frozen=True, slots=True)
class FootprintInstance(Entity):
    """A placed footprint of a component. ``attributes`` are the backend's footprint flags, in order;
    ``fields`` are its text fields in the backend's order, with unique names.

    ``graphics`` and ``texts`` (change c0126) are the drawings and the free texts of this footprint, in the
    order of their source. Their points are in the pad frame: a point ``p`` lies on the board at
    ``position + R(rotation)·p`` with no further mirror, so a bottom footprint holds mirrored coordinates;
    ``layer`` is the board layer the item lies on, and ``Text.rotation`` is relative to the footprint. The
    places of the reference and of the value stay in ``fields``."""

    component_id: str
    lib_ref: str
    position: Point
    rotation: Udeg = 0
    side: Side = "top"
    locked: bool = False
    attributes: tuple[FootprintAttribute, ...] = field(default=(), metadata=ORDERED)
    pads: tuple[Pad, ...] = ()
    fields: tuple[FootprintField, ...] = field(default=(), metadata=ORDERED)
    bodies: tuple[ComponentBody, ...] = field(default=(), metadata=ORDERED)
    graphics: tuple[Graphic, ...] = field(default=(), metadata=ORDERED)
    texts: tuple[Text, ...] = field(default=(), metadata=ORDERED)


@dataclass(frozen=True, slots=True)
class Track(Entity):
    """A straight track. ``locked`` marks copper that tools must not move or remove."""

    start: Point
    end: Point
    width: Nm
    layer: str
    net_id: str | None = None
    locked: bool = False


@dataclass(frozen=True, slots=True)
class Arc(Entity):
    """An arc track through ``mid``. ``locked`` as for a track."""

    start: Point
    mid: Point
    end: Point
    width: Nm
    layer: str
    net_id: str | None = None
    locked: bool = False


@dataclass(frozen=True, slots=True)
class ViaProtection:
    """How a via is protected: tenting, covering and plugging per side, capping and filling for the via.

    ``True`` means that the feature is applied (on that side), ``False`` that it is not. On a via, ``None``
    means that the field follows the board's default; in ``Board.via_protection``, ``None`` (whole, or for
    one field) means the backend's own default. Effective values are computed by the backends, never
    stored (``docs/design-model.md``, "Via protection")."""

    tenting_front: bool | None = None
    tenting_back: bool | None = None
    covering_front: bool | None = None
    covering_back: bool | None = None
    plugging_front: bool | None = None
    plugging_back: bool | None = None
    capping: bool | None = None
    filling: bool | None = None


@dataclass(frozen=True, slots=True)
class Via(Entity):
    """A via between ``layers`` (the two outermost copper layers it spans). ``locked`` as for a track.

    ``protection`` holds the via's own protection values; a field of ``None`` follows
    ``Board.via_protection``. ``locked`` stays the last field (change c0108)."""

    position: Point
    diameter: Nm
    drill: Nm
    layers: tuple[str, ...] = field(default=(), metadata=ORDERED)
    net_id: str | None = None
    via_type: ViaType = "through"
    protection: ViaProtection = ViaProtection()
    locked: bool = False


@dataclass(frozen=True, slots=True)
class ZoneFill:
    """Filled copper of a zone on one layer (a derived artefact); a zone may have several per layer."""

    layer: str
    polygon: tuple[Point, ...]
    island: bool = False


@dataclass(frozen=True, slots=True)
class ZoneHatch:
    """The pattern of a hatched fill. Ratios are decimal strings, never floats."""

    thickness: Nm = 1_000_000
    gap: Nm = 1_500_000
    orientation: Udeg = 0
    smoothing_level: int = 0
    smoothing_value: str = "0.1"
    border: HatchBorder = "hatch_thickness"
    min_hole_area: str = "0.15"


@dataclass(frozen=True, slots=True)
class ZoneSettings:
    """How a copper zone is filled. The defaults are the values KiCad gives a new zone
    (``docs/design-model.md``, "Zone settings"); ``min_island_area`` is in square nanometres."""

    clearance: Nm = 500_000
    min_thickness: Nm = 250_000
    connection: ZoneConnection = "thermal"
    thermal_gap: Nm = 500_000
    thermal_spoke_width: Nm = 500_000
    island_removal: IslandRemoval = "always"
    min_island_area: int = 10_000_000_000_000
    smoothing: ZoneSmoothing = "none"
    smoothing_radius: Nm = 0
    fill_mode: ZoneFillMode = "solid"
    hatch: ZoneHatch = ZoneHatch()

    def effective(self) -> ZoneSettings:
        """A copy in which every value that cannot change the fill is at its default: ``hatch`` of a solid
        fill, ``smoothing_radius`` without smoothing, and ``min_island_area`` unless islands are removed
        below an area."""
        default = ZoneSettings()
        return replace(
            self,
            hatch=self.hatch if self.fill_mode == "hatched" else default.hatch,
            smoothing_radius=self.smoothing_radius if self.smoothing != "none" else default.smoothing_radius,
            min_island_area=(
                self.min_island_area if self.island_removal == "below_area" else default.min_island_area
            ),
        )


@dataclass(frozen=True, slots=True)
class Zone(Entity):
    """A copper zone (pour). ``fills`` are derived and discarded when the zone changes.

    An empty ``outline`` on an imported zone means the backend keeps the outline as an opaque slot.
    ``filled`` is the board's own fill flag, kept apart from ``fills``: a zone may be filled with an empty
    result.
    """

    outline: tuple[Point, ...] = field(metadata=ORDERED)
    name: str = ""
    layers: tuple[str, ...] = field(default=(), metadata=ORDERED)
    net_id: str | None = None
    priority: int = 0
    fills: tuple[ZoneFill, ...] = field(default=(), metadata=ORDERED)
    settings: ZoneSettings = ZoneSettings()
    filled: bool = False
    locked: bool = False


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
    sheet: SheetFrameRef | None = None
    title_block: TitleBlock | None = None
    via_protection: ViaProtection | None = None
    """The board's default protection for every via; ``None`` is the backend's own default."""


__all__ = [
    "Arc",
    "Board",
    "BodyKind",
    "ComponentBody",
    "DielectricKind",
    "FieldJustifyH",
    "FieldJustifyV",
    "FootprintAttribute",
    "FootprintField",
    "FootprintInstance",
    "Graphic",
    "GraphicKind",
    "HatchBorder",
    "Hole",
    "HoleShape",
    "IslandRemoval",
    "Keepout",
    "MAX_CORNER_RATIO",
    "PPM_PER_PERCENT",
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
    "ViaProtection",
    "ViaType",
    "Zone",
    "ZoneConnection",
    "ZoneFill",
    "ZoneFillMode",
    "ZoneHatch",
    "ZoneSettings",
    "ZoneSmoothing",
]
