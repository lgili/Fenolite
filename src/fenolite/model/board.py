# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Board layer: stack-up, layers, footprints, pads, copper and mechanical objects (all in nm)."""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from typing import Literal

from fenolite.core.coords import Point, Size
from fenolite.core.evidence import Evidence, Level
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
PadFabProperty = Literal[
    "bga",
    "fiducial_global",
    "fiducial_local",
    "test_point",
    "heatsink",
    "castellated",
    "mechanical",
    "press_fit",
]
"""The fabrication mark of a pad: what KiCad calls the fabrication property of a pad."""
HoleShape = Literal["round", "square", "slot"]
BodyKind = Literal["extruded", "model"]
ZoneFillMode = Literal["solid", "hatched"]
IslandRemoval = Literal["always", "never", "below_area"]
ZoneSmoothing = Literal["none", "chamfer", "fillet"]
HatchBorder = Literal["hatch_thickness", "min_thickness"]
FieldJustifyH = Literal["left", "center", "right"]
FieldJustifyV = Literal["top", "center", "bottom"]
DimensionKind = Literal["aligned", "orthogonal", "radial", "leader", "center"]
"""``radial``, ``leader`` and ``center`` since change c0277: a radius with its leader, a note with an arrow,
and the cross of a circle's centre."""
DimensionFrame = Literal["none", "rect", "circle"]
"""The frame drawn around a leader's text (change c0277)."""
DimensionDirection = Literal["horizontal", "vertical"]
DimensionUnits = Literal["mm", "in", "mils", "auto"]
"""The units of a dimension's text; ``auto`` follows the units the board editor shows (change c0277 adds
``mils`` and ``auto``)."""
ORDERED = {"ordered": True}


@dataclass(frozen=True, slots=True)
class MechanicalIntent:
    """Declared mechanical provenance; a measured coordinate is still not a qualified fit."""

    key: str
    frame: Literal["board"] = "board"
    tolerance: Nm = 0
    source: str = ""
    status: Literal["measured", "estimated", "proposed"] = "proposed"
    evidence: Evidence = Evidence(Level.UNKNOWN)

    def __post_init__(self) -> None:
        if not self.key or not self.key.isprintable() or self.key != self.key.strip():
            raise ValueError("mechanical key must be nonempty printable text without surrounding spaces")
        if self.frame != "board":
            raise ValueError("only the board-relative mechanical frame is supported")
        if type(self.tolerance) is not int or self.tolerance < 0:
            raise ValueError("mechanical tolerance must be nonnegative integer nm")
        if self.status not in ("measured", "estimated", "proposed"):
            raise ValueError("mechanical status must be measured, estimated or proposed")


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
class OutlineArc:
    """One edge of a board outline that is an arc through ``mid``.

    Edge ``edge`` of ring ``ring`` runs from its first vertex through ``mid`` to its second. Ring 0 is
    ``Outline.points`` and ring k is ``Outline.cutouts[k - 1]``; edge i of a ring of n vertices joins
    vertex i to vertex (i + 1) mod n."""

    ring: int
    edge: int
    mid: Point


@dataclass(frozen=True, slots=True)
class OutlineSlot(Entity):
    """A milled slot of the board (change c0167): a non-plated stadium cut out of the board, ``length``
    long overall (both round ends included) and ``width`` wide, its length's axis turned by ``rotation``
    about ``center`` in the sense of ``Transform.placement``. Its ring is ``core.stadium.stadium(center,
    length, width, rotation)``; for every reader of rings it is one more cut-out after
    ``Outline.cutouts``. ``width`` is positive and even and ``length`` exceeds it. ``name`` is the script's
    name of the slot, empty when none is known (a slot recognised in a read board). Not the opaque
    round-trip ``model.base.Slot``."""

    center: Point
    length: Nm
    width: Nm
    rotation: Udeg = 0
    name: str = ""


@dataclass(frozen=True, slots=True)
class Outline(Entity):
    """Board outline polygon and cut-outs (points in order), and the board's milled slots.

    An edge is straight unless ``arcs`` holds an entry for it; ``arcs`` is sorted by ``(ring, edge)`` and
    holds at most one entry per edge. A ring has three vertices or more, or two when one of its two edges
    is an arc (a circle is two arcs). ``arcs`` names the rings of ``points`` and ``cutouts`` only; the
    rings of ``slots`` follow from their parameters. Overlapping cut-outs and slots mean their union."""

    points: tuple[Point, ...] = field(default=(), metadata=ORDERED)
    cutouts: tuple[tuple[Point, ...], ...] = field(default=(), metadata=ORDERED)
    arcs: tuple[OutlineArc, ...] = field(default=(), metadata=ORDERED)
    slots: tuple[OutlineSlot, ...] = field(default=(), metadata=ORDERED)


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
ChamferCorner = Literal["top_left", "top_right", "bottom_left", "bottom_right"]
CHAMFER_CORNERS: tuple[ChamferCorner, ...] = ("top_left", "top_right", "bottom_left", "bottom_right")
"""The corners a pad's chamfer may cut, in KiCad's order (S-0001)."""
PadPrimitiveKind = Literal["poly", "segment", "circle", "arc"]
PadAnchor = Literal["circle", "rect"]


@dataclass(frozen=True, slots=True)
class PadPrimitive:
    """One shape of a custom pad, in the pad's own frame (change c0277): a ``poly`` (its corners), a
    ``segment`` (start, end), a ``circle`` (centre, a point of the circle) or an ``arc`` (start, middle,
    end), drawn ``width`` wide; ``filled`` for a closed shape."""

    kind: PadPrimitiveKind
    points: tuple[Point, ...] = field(default=(), metadata=ORDERED)
    width: Nm = 0
    filled: bool = False


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
    fab_property: PadFabProperty | None = None
    """The fabrication mark of the pad (fiducial, test point, BGA ball and the like); ``None`` for no mark.
    The model does not check it against the pad's kind or layers."""
    mask_margin: Nm | None = None
    """The growth of the pad's solder-mask opening beyond its copper, which may be negative (change c0223);
    ``None`` follows the board. A KiCad reader projects the pad's margin child into the field and keeps the
    child as read, so a write keeps it unless the field disagrees (refused) or is ``None`` (kept)."""
    paste_margin: Nm | None = None
    """The growth of the pad's paste opening beyond its copper, as ``mask_margin``."""
    teardrop: Teardrop | None = None
    """The pad's teardrop settings (change c0277); ``None`` keeps what the pad's footprint says. A KiCad
    reader does not project the pad's ``teardrops`` child, which stays in its slot."""
    trapezoid_delta: Point | None = None
    """How much a ``trapezoid`` pad's opposite sides differ, along x or along y (KiCad's ``rect_delta``;
    change c0277); ``None`` for the other shapes."""
    chamfer_ratio: int | None = None
    """The chamfer of the pad's corners ``chamfer_corners`` in parts per million of the shorter side of
    ``size``, 0 to ``MAX_CORNER_RATIO`` (change c0277); ``None``: no chamfer."""
    chamfer_corners: tuple[ChamferCorner, ...] = field(default=(), metadata=ORDERED)
    """The corners the chamfer cuts, in ``CHAMFER_CORNERS`` order (change c0277)."""
    anchor_shape: PadAnchor | None = None
    """The anchor of a ``custom`` pad, ``circle`` or ``rect`` of ``size`` (change c0277)."""
    primitives: tuple[PadPrimitive, ...] = field(default=(), metadata=ORDERED)
    """The shapes a ``custom`` pad adds to its anchor (change c0277). A KiCad reader projects the four
    shape fields from the pad's children and keeps the children as read."""


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
    bold: bool | None = None
    """A bold font for the field (change c0277); ``None`` keeps the font the footprint gives. A KiCad reader
    does not project it: the field's ``effects`` stay as read, and a value set here is written into them."""
    italic: bool | None = None
    """An italic font for the field, as ``bold`` (change c0277)."""
    face: str | None = None
    """The font face of the field, as ``bold`` (change c0277)."""


@dataclass(frozen=True, slots=True)
class ModelRef:
    """A 3D model of a placed footprint named by a script (change c0277): ``name`` is a reference only (a
    path or ``${KICAD10_3DMODEL_DIR}/…``), never read; ``offset`` ``(x, y, z)`` in nm in the footprint
    frame (Y down, Z up from the footprint's face), ``rotation`` ``(x, y, z)`` in µdeg counter-clockwise,
    ``scale`` ``(x, y, z)`` as positive decimal strings, and ``hidden`` for a model the 3D view leaves out."""

    name: str
    offset: tuple[Nm, Nm, Nm] = (0, 0, 0)
    rotation: tuple[Udeg, Udeg, Udeg] = (0, 0, 0)
    scale: tuple[str, str, str] = ("1", "1", "1")
    hidden: bool = False


@dataclass(frozen=True, slots=True)
class ComponentBody(Entity):
    """The physical body of a part: a volume above the side its footprint is placed on.

    ``height`` is the distance from the board surface to the top of the body and ``standoff`` the distance
    to its underside. ``outline`` is the body's footprint as a polygon in the footprint frame (empty when
    the source gives none), ``layer`` the layer it is drawn on, and ``model`` the name of a 3D model for
    the kind ``model``. Optional signed ``z_min``/``z_max`` bound the extrusion away from the mounted
    face. ``projection_unknown`` retains source information without claiming volume geometry.
    No model data is carried."""

    kind: BodyKind
    height: Nm
    standoff: Nm = 0
    outline: tuple[Point, ...] = field(default=(), metadata=ORDERED)
    layer: str = ""
    model: str = ""
    name: str = ""
    z_min: Nm | None = None
    z_max: Nm | None = None
    projection_unknown: bool = False


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
    net_ties: tuple[tuple[str, ...], ...] = field(default=(), metadata=ORDERED)
    """The net-tie groups of the footprint (change c0114): each group lists the numbers of pads of
    different nets that the footprint joins on purpose, in the order its source lists them."""
    anchor: MechanicalIntent | None = None
    models: tuple[ModelRef, ...] = field(default=(), metadata=ORDERED)
    """The 3D models a script gives this instance (change c0277): any replaces the footprint's own models
    for the instance; empty keeps them. Left out of the canonical JSON when empty."""


def outward_height(footprint: FootprintInstance) -> Nm | None:
    """The height of a placed part above the board surface on its own side, or ``None`` when unknown.

    The largest upper bound of the footprint's known bodies (change c0140): a body is known when its
    ``projection_unknown`` is false, and its upper bound is its ``z_max`` when it has signed bounds (change
    c0099), its ``height`` otherwise. ``None`` when the footprint has no known body or that bound is not
    positive. The one place of the package that computes a part's height: it reads neither the component,
    nor a property, nor a 3D model, nor ``standoff``, nor ``z_min``."""
    tops = [
        body.height if body.z_max is None else body.z_max
        for body in footprint.bodies
        if not body.projection_unknown
    ]
    if not tops:
        return None
    top = max(tops)
    return top if top > 0 else None


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
class Teardrop:
    """The teardrop settings of a pad or a via (change c0277): the tool that fills the board draws the
    teardrop copper from them; the model holds no teardrop shape.

    ``enabled`` says whether the item gets teardrops. Every other field of ``None`` is left to the tool's
    own default. Lengths are nanometres; ``length_ratio``, ``width_ratio`` and ``filter_ratio`` are parts per
    million of the pad or via size (500 000 is one half)."""

    enabled: bool = True
    max_length: Nm | None = None
    max_width: Nm | None = None
    length_ratio: int | None = None
    width_ratio: int | None = None
    curved: bool | None = None
    filter_ratio: int | None = None
    two_segments: bool | None = None
    prefer_zones: bool | None = None


@dataclass(frozen=True, slots=True)
class Via(Entity):
    """A via between ``layers`` (the two outermost copper layers it spans). ``locked`` as for a track.

    ``protection`` holds the via's own protection values; a field of ``None`` follows
    ``Board.via_protection``. ``locked`` stays the last field of change c0108; ``teardrop`` (change c0277)
    follows it and is left out of the canonical JSON when ``None``."""

    position: Point
    diameter: Nm
    drill: Nm
    layers: tuple[str, ...] = field(default=(), metadata=ORDERED)
    net_id: str | None = None
    via_type: ViaType = "through"
    protection: ViaProtection = ViaProtection()
    locked: bool = False
    teardrop: Teardrop | None = None
    free: bool = False
    """KiCad's ``(free yes)``: the via keeps its net when no track joins it (change c0277). Left out of the
    canonical JSON when false; a KiCad reader keeps a read via's ``free`` in its slots."""


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
    arcs: tuple[OutlineArc, ...] = ()
    """The edges of ``outline`` that are arcs (ring 0; change c0277); left out of the canonical JSON when
    empty. A consumer that needs the polygon takes ``CurvedRing``'s polygonisation of the ring."""


@dataclass(frozen=True, slots=True)
class Keepout(Entity):
    """A rule area: an area where some kinds of objects are not allowed, or, with every setting false,
    a named area that only rules select (``Selector("area", name)``)."""

    outline: tuple[Point, ...] = field(metadata=ORDERED)
    layers: tuple[str, ...] = field(default=(), metadata=ORDERED)
    no_tracks: bool = False
    no_vias: bool = False
    no_pads: bool = False
    no_copper_pour: bool = False
    no_footprints: bool = False
    name: str = ""
    intent: MechanicalIntent | None = None
    placement: str | None = None
    """The sheet whose parts KiCad's multichannel tool places in the area (a placement rule area, KiCad 9 and
    10), as KiCad names the sheet (``/CH1/``); change c0277. Left out of the canonical JSON when ``None``; a
    KiCad reader keeps a read area's ``placement`` in its slots."""


@dataclass(frozen=True, slots=True)
class Text(Entity):
    text: str
    position: Point
    layer: str
    size: Size
    thickness: Nm
    rotation: Udeg = 0
    h_justify: FieldJustifyH = "center"
    v_justify: FieldJustifyV = "center"
    """The justification, in the reading frame of the text."""
    knockout: bool = False
    """The text is cut out of a filled box on its layer, a copper or silkscreen layer (change c0277). The
    four fields from here are left out of the canonical JSON when unset; a KiCad reader keeps them in the
    text's slots and does not project them."""
    bold: bool = False
    italic: bool = False
    face: str = ""
    """A font face by name; ``""`` is the tool's own stroke font."""


@dataclass(frozen=True, slots=True)
class Graphic(Entity):
    """A drawing primitive on a non-copper or copper layer; ``points`` meaning depends on ``kind``."""

    kind: GraphicKind
    layer: str
    points: tuple[Point, ...] = field(metadata=ORDERED)
    width: Nm = 0
    filled: bool = False
    net_id: str | None = None
    """The net of a graphic on a copper layer (change c0277); ``None``: copper of no net, or a graphic off
    copper. Left out of the canonical JSON when ``None``; a KiCad reader keeps a read graphic's ``net`` in
    its slots and does not project it."""


@dataclass(frozen=True, slots=True)
class Dimension(Entity):
    """A dimension between two points. The measured value is not a field: it follows from the points.
    ``offset`` is the signed distance of the dimension line from the measured points of a linear one
    (``aligned``, ``orthogonal``), 0 for the other kinds; ``None`` for ``size``, ``thickness`` and
    ``width`` means the backend's default. A ``radial`` one measures from its centre ``start`` to the edge
    point ``end``; a ``leader`` points from ``start`` to its knee ``end`` and shows ``text``; a ``center``
    mark draws a cross at ``start`` reaching ``end`` (change c0277)."""

    kind: DimensionKind
    layer: str
    start: Point
    end: Point
    offset: Nm
    direction: DimensionDirection | None = None
    units: DimensionUnits = "mm"
    precision: int = 4
    size: Size | None = None
    thickness: Nm | None = None
    width: Nm | None = None
    extension_offset: Nm | None = None
    """The gap between a measured point and the start of its extension line (change c0277); ``None`` is the
    backend's default. Left out of the canonical JSON when ``None``."""
    text_position: Point | None = None
    """Where the text of the dimension stands when it is placed by hand (KiCad's ``text_position_mode 2``;
    change c0277); ``None``: KiCad places it. Left out of the canonical JSON when ``None``."""
    leader_length: Nm | None = None
    """The length of a radial dimension's leader (change c0277); ``None`` for the other kinds."""
    text: str | None = None
    """The text a leader shows (change c0277); ``None`` for the other kinds."""
    frame: DimensionFrame | None = None
    """The frame around a leader's text (change c0277); ``None`` for the other kinds."""


@dataclass(frozen=True, slots=True)
class Image(Entity):
    """A picture on a board layer (change c0277): the PNG bytes of ``data`` (base64 text) at ``position``,
    KiCad's ``at`` of the image, drawn ``scale`` times its own size (a positive decimal string)."""

    position: Point
    layer: str
    data: str
    scale: str = "1"


@dataclass(frozen=True, slots=True)
class Hole(Entity):
    """A mechanical hole that is not part of a footprint.

    With ``length`` (change c0168) the hole is a drilled slot: ``drill`` wide and ``length`` long overall
    (both round ends included), its length's axis turned by ``rotation`` about ``position`` in the sense of
    ``Transform.placement``. ``None`` is a round hole, whose ``rotation`` is 0. ``length`` must exceed
    ``drill``. A milled slot of the board is ``OutlineSlot``, not a ``Hole``."""

    position: Point
    drill: Nm
    plated: bool = False
    intent: MechanicalIntent | None = None
    length: Nm | None = None
    rotation: Udeg = 0

    def __post_init__(self) -> None:
        if self.length is not None and self.length <= self.drill:
            raise ValueError(f"a slotted hole is longer than its drill: length {self.length} <= {self.drill}")


@dataclass(frozen=True, slots=True)
class Group(Entity):
    """A group of board items (change c0277): its name (``""`` for an unnamed group), the ids of its members
    and whether it is locked. A member is a component (its footprint), a text, a graphic, a dimension, a
    zone, a rule area or another group of the board."""

    name: str = ""
    member_ids: tuple[str, ...] = ()
    locked: bool = False


VerbatimTarget = Literal["kicad_pcb", "kicad_dru", "footprint"]
"""Where a verbatim item goes: a child of the board root, a rule of the rules file, or a child of the
footprint of ``VerbatimItem.component_id`` (change c0277)."""


@dataclass(frozen=True, slots=True)
class VerbatimItem(Entity):
    """One item a script keeps as KiCad text (change c0277): ``design.verbatim()`` and ``part.verbatim()``.
    The model does not parse ``text``; the KiCad build parses it, checks it and writes it with uuids of its
    own (``backends/kicad/verbatim.py``)."""

    key: str
    text: str
    target: VerbatimTarget = "kicad_pcb"
    component_id: str | None = None


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
    dimensions: tuple[Dimension, ...] = ()
    sheet: SheetFrameRef | None = None
    title_block: TitleBlock | None = None
    via_protection: ViaProtection | None = None
    """The board's default protection for every via; ``None`` is the backend's own default."""
    groups: tuple[Group, ...] = ()
    """The groups a script declares (change c0277); a KiCad reader keeps the groups of a board in its
    slots and does not project them."""
    verbatim: tuple[VerbatimItem, ...] = ()
    """The verbatim items a script declares, in key order (change c0277)."""
    images: tuple[Image, ...] = ()
    """The board images (change c0277): a script's in key order, a read board's in file order."""


__all__ = [
    "Arc",
    "Board",
    "CHAMFER_CORNERS",
    "ChamferCorner",
    "Image",
    "ModelRef",
    "PadAnchor",
    "PadPrimitive",
    "PadPrimitiveKind",
    "BodyKind",
    "ComponentBody",
    "DielectricKind",
    "Dimension",
    "DimensionDirection",
    "DimensionFrame",
    "DimensionKind",
    "DimensionUnits",
    "FieldJustifyH",
    "FieldJustifyV",
    "FootprintAttribute",
    "FootprintField",
    "FootprintInstance",
    "Graphic",
    "GraphicKind",
    "Group",
    "HatchBorder",
    "VerbatimItem",
    "VerbatimTarget",
    "Hole",
    "HoleShape",
    "IslandRemoval",
    "Keepout",
    "MAX_CORNER_RATIO",
    "PPM_PER_PERCENT",
    "Layer",
    "LayerKind",
    "MechanicalIntent",
    "Outline",
    "OutlineArc",
    "OutlineSlot",
    "Pad",
    "PadFabProperty",
    "PadKind",
    "PadShape",
    "Padstack",
    "PadstackLayer",
    "Side",
    "StackKind",
    "StackLayer",
    "Stackup",
    "Teardrop",
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
    "outward_height",
]
