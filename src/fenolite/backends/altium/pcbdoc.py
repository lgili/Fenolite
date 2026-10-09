# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The experimental Altium PCB document (``.PcbDoc``) of the Altium writer (change c0035, capability
altium-pcb-writer, "PCB document file", "PCB document placement" and "PCB document links and nets").

Written from ``docs/formats/altium/pcb-document.md`` and ``pcb-records.md``. A document is a compound file:
two header streams, then one storage per object kind holding ``Header`` (the record count) and ``Data``.
The storages, the ``Board6`` record (``docboard``) and the net and component records follow the form
Altium saves ("The document as Altium saves it"); Altium Designer refuses the shorter form of the public
writers. Footprint primitives are placed as KiCad places them (``Transform.placement``), then Y is negated
and the board shifted so that its lower-left corner lies at (1000 mil, 1000 mil). Components link to the
schematic through ``SOURCEUNIQUEID=\\<unique id>``, or, for a part on a module sheet of a hierarchical
project (change c0037), through ``\\<sheet symbol id>\\<unique id>`` with ``SOURCEHIERARCHICALPATH`` set to
``<design name>\\<module name>``, the design name being the stem the document shares with the top sheet.

Change c0038 adds the copper, written from ``docs/formats/altium/pcb-copper.md``: routed tracks and arcs
as free primitives with their net, through vias in the 321-byte form Altium saves, and each zone as one
unpoured polygon pour per layer, which Altium fills on a repour; one ``KIND=0`` class per net class; and
Clearance, Width and Routing Via Style rules from the net classes and Fenolite's defaults.

Change c0085 completes the board: copper stacks of any even count up to 32 layers, blind and buried
vias with one drill pair per span, the free texts, graphics, keep-outs and holes of the board
(``pcb-records.md``, "Regions and keep-outs" and "Free pads as holes"). Polygons stay unpoured.

Change c0048 adds one ``KIND=1`` class per schematic sheet with the refs of its components, the component
class that Altium's change order derives from the sheet (``H-A-ECO-COMPCLASS``): named after the module
for a module sheet, and after the sheet for the top sheet or the single sheet of a flat build.
"""

from __future__ import annotations

import dataclasses
import struct
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Literal

import fenolite.backends.altium.pcbrecords as rec
import fenolite.backends.altium.rulemap as rulemap
from fenolite.backends.altium.ascii import Field, text_problem
from fenolite.backends.altium.cfb import Entry, Storage, write_compound
from fenolite.backends.altium.docboard import (
    StackSpec,
    angle_text,
    board_text,
    common_fields,
    name_codes,
    polygon_fields,
)
from fenolite.backends.altium.libboard import guid
from fenolite.backends.altium.pcblib import (
    BODY_IS_MODEL,
    BODY_NO_OUTLINE,
    LibFootprint,
    PadExtras,
    body_problem,
    check_footprint,
    graphic_records,
    pad_bytes,
)
from fenolite.core.coords import Point
from fenolite.core.evidence import Evidence, Level
from fenolite.geometry.transform import FULL_TURN, Transform
from fenolite.model.board import (
    Arc,
    ComponentBody,
    Graphic,
    Hole,
    Keepout,
    Pad,
    Side,
    Text,
    Track,
    Via,
    ViaProtection,
    Zone,
)

FILE_HEADER_TEXT = "PCB 5.0 Binary File"
"""``FileHeader``: the 32-bit value 19, then the first ten characters of this text in UTF-16LE."""
FILE_HEADER_SIX_TEXT = "PCB 6.0 Binary File"
FILE_HEADER_SIX_VERSION = 5.01
BOARD_OFFSET_MIL = 1000
"""The board's lower-left corner and ``ORIGINX``/``ORIGINY`` lie at (1000 mil, 1000 mil)."""
_OFFSET_NM = BOARD_OFFSET_MIL * 25_400
DEFAULT_FILENAME = "Fenolite.PcbDoc"
COPPER_STORAGES: tuple[str, ...] = ("Vias6", "Polygons6", "Classes6", "Rules6")
"""Storages of the copper (change c0038): ``Header`` is the record count, and ``Data`` is empty when the
spec holds no such object."""
EMPTY_STORAGES: tuple[str, ...] = (
    "Fills6",
    "Regions6",
    "ShapeBasedRegions6",
    "Dimensions6",
    "ComponentBodies6",
    "ShapeBasedComponentBodies6",
    "DifferentialPairs6",
    "Connections6",
    "FromTos6",
    "Textures",
    "Embeddeds6",
    "Coordinates6",
    "Models",
    "ModelsNoEmbed",
    "EmbeddedBoards6",
    "PinPairsSection",
    "PadViaLibraryLinks",
    "ExtendedPrimitiveInformation",
    "WaivedViolations",
    "PrimitiveParameters",
    "SmartUnions",
)
"""Storages written with ``Header`` 0 and an empty ``Data``: the kinds KiCad looks for and the ones every
Altium-saved document holds, empty in a document without such objects. Three of them are filled when the
spec holds such an object: the two region storages (change c0085) and the two body storages (change
c0121, ``PcbDocSpec.bodies``)."""
BODY_STORAGES: tuple[str, str] = ("ComponentBodies6", "ShapeBasedComponentBodies6")
"""The plain and the shape-based storage of the component bodies: record ``i`` of one is the twin of record
``i`` of the other (``pcb-bodies.md``, "Written form of an extruded body")."""
_TAIL_ORDER: tuple[str, ...] = (
    "Vias6",
    *EMPTY_STORAGES[:3],
    "Polygons6",
    EMPTY_STORAGES[3],
    "Classes6",
    "Rules6",
    *EMPTY_STORAGES[4:],
)
"""The copper and the empty storages in the order they are written (the order of c0035's document)."""
OPTION_STORAGES: tuple[str, ...] = (
    "Advanced Placer Options6",
    "Pin Swap Options6",
    "Design Rule Checker Options6",
    "PadViaLibrary",
    "PadViaLibraryCache",
    "LayerKindMapping",
    "ConstraintManager",
    "SignalClasses",
)
"""Storages with the fixed content of a document without rules, classes or pad templates."""
UNIQUE_STORAGE = "UniqueIDPrimitiveInformation"
NET_COLOR = "7709086"
NO_CONSTRAINTS = "eNoDAAAAAAE="
"""``ConstraintManager``: the base64 text of a zlib stream (best compression) that holds no data."""
_PLACER: tuple[Field, ...] = (
    ("RECORD", "AdvancedPlacerOptions"),
    ("PLACELARGECLEAR", "50mil"),
    ("PLACESMALLCLEAR", "20mil"),
    ("PLACEUSEROTATION", "TRUE"),
    ("PLACEUSELAYERSWAP", "FALSE"),
    ("PLACEBYPASSNET1", ""),
    ("PLACEBYPASSNET2", ""),
    ("PLACEUSEADVANCEDPLACE", "TRUE"),
    ("PLACEUSEGROUPING", "TRUE"),
)
_PIN_SWAP: tuple[Field, ...] = (
    ("RECORD", "PinSwapOptions"),
    ("QUIET", "FALSE"),
    ("APPROXIMATEPINPOSITIONS", "FALSE"),
    ("ALLOWPARTIALLYROUTEDCONNECTIONS", "TRUE"),
    ("VIAPENALTYSTATE", "TRUE"),
    ("CROSSOVERRATIO", "50"),
    ("VIAPENALTYVALUE", "0"),
    ("IGNORENETS", ""),
    ("IGNORENETCLASSES", ""),
    ("IGNORECOMPONENTS", ""),
    ("IGNOREDIFFERENTIALPAIRS", ""),
    ("HEURISTICNAME", ""),
    ("HEURISTICONOFFSTATE", ""),
    ("HEURISTICWEIGHTVALUE", ""),
)
_RULE_KINDS = "0,1,2,3,4,5,6,15,16,18,19,21,22,23,26,42,45,46,47,50,52,53,54,55,56,60,62,63,64"
_ONLINE_RULE_KINDS = "0,1,2,3,4,5,9,11,15,17,18,22,23,24,45,46,47,50,51,55,60,62"
_RULE_CHECKER: tuple[Field, ...] = (
    ("RECORD", "DesignRuleCheckerOptions"),
    ("DOMAKEDRCFILE", "FALSE"),
    ("DOMAKEDRCERRORLIST", "TRUE"),
    ("DOSUBNETDETAILS", "TRUE"),
    ("REPORTFILENAME", ""),
    ("EXTERNALNETLISTFILENAME", ""),
    ("CHECKEXTERNALNETLIST", "FALSE"),
    ("MAXVIOLATIONCOUNT", "500"),
    ("REPORTDRILLEDSMTPADS", "TRUE"),
    ("REPORTINVALIDMULTILAYERPADS", "TRUE"),
    ("RULESETTOCHECK", _RULE_KINDS),
    ("ONLINERULESETTOCHECK", _ONLINE_RULE_KINDS),
    ("INTERNALPLANEWARNINGS", "TRUE"),
    ("VERIFYSHORTINGCOPPER", "TRUE"),
    ("REPORTBROKENPLANES", "TRUE"),
    ("REPORTDEADCOPPER", "TRUE"),
    ("DEADCOPPERMINAREA", "10000000000.000000"),
    ("REPORTSTARVEDTHERMALS", "TRUE"),
    ("MINSTARVEDCOPPERPERCENT", "50"),
    ("REPORTSTRADLINGHOLES", "FALSE"),
    ("REPORTHOLESINVOIDS", "FALSE"),
)
TOP, BOTTOM = 1, 32
TEXT_SIZE = 137
DESIGNATOR_HEIGHT = 1_000_000
DESIGNATOR_STROKE = 150_000
DESIGNATOR_RISE = 500_000
COMMENT_DROP = 1_500_000
EVIDENCE = Evidence(
    Level.INFERRED,
    hypotheses=(
        "H-A-ECO-COMPCLASS",
        "H-A-ECO-SHEETCLASS",
        "H-A-PCB-CU-CLASS",
        "H-A-PCB-CU-KICAD",
        "H-A-PCB-CU-LOCK",
        "H-A-PCB-CU-PLANE",
        "H-A-PCB-CU-REPOUR",
        "H-A-PCB-CU-ROUNDTRIP",
        "H-A-PCB-CU-RULES",
        "H-A-PCB-CU-STACK",
        "H-A-PCB-CU-TRACK",
        "H-A-PCB-CU-VIA",
        "H-A-PCB-CU-VIATENT",
        "H-A-PCB-CU-VIEWER",
        "H-A-PCB-DOC-BOTTOM",
        "H-A-PCB-DOC-LINK",
        "H-A-PCB-DOC-NETS",
        "H-A-PCB-DOC-OPEN",
        "H-A-PCB-DOC-VIEWER",
        "H-A-PCB-KICAD-DOC",
        "H-A-PCBX-BODY-2D",
        "H-A-PCBX-BODY-FORM",
        "H-A-PCBX-BODY-ID",
        "H-A-PCBX-BODY-KICAD",
        "H-A-PCBX-BODY-OPEN",
        "H-A-PCBX-BODY-READBACK",
        "H-A-PCBX-BODY-SHORT",
        "H-A-PCBX-BUILD-LOWER",
        "H-A-PCBX-FPGFX",
        "H-A-PCBX-FPGFX-AD",
        "H-A-PCBX-FPGFX-KICAD",
        "H-A-PCBX-FPTEXT",
        "H-A-PCBX-HOLE",
        "H-A-PCBX-KEEPOUT",
        "H-A-PCBX-KICAD",
        "H-A-PCBX-MECH",
        "H-A-PCBX-READBACK",
        "H-A-PCBX-REPOUR",
        "H-A-PCBX-STACK",
        "H-A-PCBX-TEXT",
        "H-A-PCBX-VIA-FULL",
        "H-A-PCBX-VIASPAN",
    ),
)
"""The PCB document is inferred from public sources; ``pcb import`` checks only what KiCad reads. The
``H-A-PCB-CU-*`` rows are those of the copper (change c0038), and ``H-A-ECO-COMPCLASS`` and
``H-A-ECO-SHEETCLASS`` those of the component classes of the sheets (change c0048). The
``H-A-PCBX-BODY-*`` rows are those a written component body rests on (change c0121): the saved form is
measured on public documents, thinly, and Altium took the two stand-in values of a body in an author
report (step X8, 2026-10-09), so a build writes bodies by default since change c0155.
``H-A-PCBX-FPGFX``, ``-FPTEXT``, ``-MECH`` and ``-BUILD-LOWER`` are those of the items of a footprint
instance and of the build through the lowering (change c0126); ``-FPGFX-KICAD`` and ``-FPGFX-AD`` wait
for KiCad's importer and for the author."""


@dataclass(frozen=True, slots=True)
class TextPlace:
    """Where a text of a component is drawn (change c0126): ``position`` in the pad frame of the
    component's placement (footprint-local, no mirror), ``layer`` the Altium id of the layer it lies on,
    ``height`` and ``stroke`` in nanometres, ``rotation`` relative to the component (microdegrees),
    ``shown`` whether the text is visible (``NAMEON`` or ``COMMENTON`` for a designator or a comment) and
    ``mirrored`` the mirror flag of the record."""

    position: Point
    layer: int
    height: int
    stroke: int
    rotation: int = 0
    shown: bool = True
    mirrored: bool = False


@dataclass(frozen=True, slots=True)
class ComponentGraphic:
    """A graphic of a component that is written as the instance holds it (change c0126): ``graphic`` in
    the pad frame of the placement, placed without a mirror, on the layer ``layer`` (an Altium id), with
    no layer flip. A drawn line, rectangle, polygon, circle or arc gives tracks and arcs with the
    component's index; a filled rectangle or polygon gives one region. ``arc`` is the kept record of an
    arc that was read (``PcbDocSpec.arc_records`` for a free arc)."""

    graphic: Graphic
    layer: int
    arc: rec.ArcGeometry | None = None


@dataclass(frozen=True, slots=True)
class ComponentText:
    """A text of a component that is neither its designator nor its comment (change c0126)."""

    text: str
    place: TextPlace


@dataclass(frozen=True, slots=True)
class PlacedComponent:
    """One component on the board: its schematic link, its footprint and its placement (KiCad frame).
    ``sheet`` (change c0037) is ``(sheet symbol unique id, module name)`` for a component on a module sheet
    of a hierarchical project, and ``None`` for a component on the top sheet or on a single sheet. For a
    module below the first level (change c0086) both items hold one entry per level from the top sheet
    down, joined by a backslash: the unique ids of the sheet symbols, and their names."""

    ref: str
    unique_id: str
    comment: str
    footprint: LibFootprint
    footprint_library: str
    lib_reference: str
    component_library: str
    at: Point
    rotation: int = 0
    side: Side = "top"
    locked: bool = False
    pad_nets: Mapping[str, str] = field(default_factory=lambda: {})
    sheet: tuple[str, str] | None = None
    record_unique_id: str | None = None
    """The unique id of the component record itself (change c0090): the id that an imported model keeps
    as the footprint's native id. ``None``: derived from the file name and ``unique_id``."""
    nets_by_pad: Mapping[str, str] | None = None
    """Pad id → net name (change c0090), for a footprint that comes from a model: two pads of one number
    may then lie on different nets. ``None``: ``pad_nets`` decides, by pad number."""
    designator_place: TextPlace | None = None
    """Where the designator is drawn and whether it is shown (change c0126). ``None``: above the box of
    the component on its overlay, shown, as a build writes it."""
    comment_place: TextPlace | None = None
    """The same for the comment. ``None``: below the box on the overlay, hidden."""
    arc_records: Mapping[str, rec.ArcGeometry] = field(default_factory=lambda: {})
    """Graphic id → the kept record of an ``arc`` graphic of ``footprint.defn`` (change c0127 for a
    footprint's arc): written instead of the record derived from the three points."""
    items: tuple[ComponentGraphic, ...] = ()
    """The graphics of the component that the definition does not hold (change c0126): those on a layer
    without another side (a mechanical layer of a board that was read, paste, solder mask) and the filled
    ones. Written after the definition's graphics."""
    texts: tuple[ComponentText, ...] = ()
    """The free texts of the component (change c0126), written after its designator and comment."""


@dataclass(frozen=True, slots=True)
class NetClassSpec:
    """One net class: its name, the names of its nets, and its rule values in nanometres (``None``: the
    class sets no such value)."""

    name: str
    nets: tuple[str, ...] = ()
    clearance: int | None = None
    track_width: int | None = None
    via_diameter: int | None = None
    via_drill: int | None = None


@dataclass(frozen=True, slots=True)
class FreePad:
    """A pad that belongs to no component (change c0090): ``pad`` is a model pad whose ``position`` and
    ``rotation`` are those on the board (KiCad frame) and whose layers are the layers it lies on;
    ``net`` is its net's name."""

    pad: Pad
    extras: PadExtras = PadExtras()
    net: str | None = None


BodyMode = Literal["off", "extruded"]
BODY_MODES: tuple[BodyMode, ...] = ("off", "extruded")
"""What a write does with component bodies (change c0121, ``--altium-bodies``): ``off`` writes none, and
``extruded`` writes the extruded bodies that ``body_problem`` passes. The writers default to ``off``; the
build (``fenolite build``, ``lens.altium.build_altium``) defaults to ``extruded`` since change c0155, after
step X8 of the author report (``H-A-PCBX-BODY-OPEN``)."""
BODIES_OFF = "component bodies are not written without --altium-bodies extruded"
BODY_NO_FOOTPRINT = "its footprint is not written"


def body_mode(value: str) -> BodyMode:
    """``value`` as a body mode; ``ValueError`` for another value."""
    if value == "off":
        return "off"
    if value == "extruded":
        return "extruded"
    raise ValueError(f"unknown body mode {value!r}: {', '.join(BODY_MODES)}")


@dataclass(frozen=True, slots=True)
class PlacedBody:
    """One component body to write (change c0121): ``component`` is the index of its component in
    ``PcbDocSpec.components``, ``layer`` the Altium id of a mechanical layer 1 to 16, ``outline`` its
    polygon in the frame of the placements (nanometres), ``height`` and ``standoff`` its two heights from
    the board surface, ``bottom`` the side of its footprint, ``identifier`` its name and ``model_id`` the
    ``MODELID`` stand-in (``pcbrecords.body_model_id``). ``body_id`` is the id of the model's body, for the
    caller's accounts; no record holds it."""

    component: int
    layer: int
    outline: tuple[Point, ...]
    height: int
    standoff: int = 0
    bottom: bool = False
    identifier: str = ""
    model_id: str = ""
    body_id: str = ""


def body_vertices(outline: Sequence[Point], frame: Frame) -> list[tuple[int, int]]:
    """The vertices of a body outline as the record holds them: each point in ``frame``, as whole units,
    without a point that equals the one before it and without a last point that repeats the first."""
    vertices: list[tuple[int, int]] = []
    for point in outline:
        vertex = _units(frame(point))
        if not vertices or vertices[-1] != vertex:
            vertices.append(vertex)
    while len(vertices) > 1 and vertices[-1] == vertices[0]:
        vertices.pop()
    return vertices


def place_body(
    body: ComponentBody, *, component: int, at: Point, rotation: int, bottom: bool, frame: Frame
) -> PlacedBody | str:
    """``body`` as the document writes it, or the reason it has no record. ``at`` and ``rotation`` are the
    placement of the body's component in the document and ``bottom`` its side: the outline of a footprint
    instance is held as seen from the top, as the instance's pads are, so it is placed without a mirror.
    The layer is ``pcbrecords.body_layer`` of ``ComponentBody.layer``. A body that ``body_problem`` passes
    and whose placed outline keeps fewer than three vertices in whole units has no outline."""
    problem = body_problem(body)
    if problem is not None:
        return problem
    transform = Transform.placement(at, rotation)
    outline = tuple(transform.apply(point) for point in body.outline)
    if len(body_vertices(outline, frame)) < 3:
        return BODY_NO_OUTLINE
    return PlacedBody(
        component=component,
        layer=rec.body_layer(body.layer, bottom=bottom),
        outline=outline,
        height=body.height,
        standoff=body.standoff,
        bottom=bottom,
        identifier=body.name,
        model_id=rec.body_model_id(body.id),
        body_id=body.id,
    )


def body_records(spec: PcbDocSpec, frame: Frame) -> tuple[list[bytes], list[bytes]]:
    """The records of ``spec.bodies`` for ``ComponentBodies6`` and for ``ShapeBasedComponentBodies6``:
    record ``i`` of each from body ``i``. ``ValueError`` names the body whose component index is outside
    ``spec.components`` or whose outline keeps fewer than three vertices."""
    plain: list[bytes] = []
    shape: list[bytes] = []
    for index, body in enumerate(spec.bodies):
        where = body.body_id or f"body {index}"
        if not 0 <= body.component < len(spec.components):
            raise ValueError(f"{where}: the component index {body.component} names no component")
        vertices = body_vertices(body.outline, frame)
        if len(vertices) < 3:
            raise ValueError(f"{where}: {BODY_NO_OUTLINE}")
        fields = {
            "component": body.component,
            "standoff": rec.to_units(body.standoff),
            "overall": rec.to_units(body.height),
            "bottom": body.bottom,
            "identifier": body.identifier,
            "model_id": body.model_id,
            "form": spec.body_form,
        }
        try:
            plain.append(rec.body_record(body.layer, vertices, **fields))  # type: ignore[arg-type]
            shape.append(rec.body_record(body.layer, vertices, shape_based=True, **fields))  # type: ignore[arg-type]
        except (ValueError, UnicodeEncodeError) as error:
            raise ValueError(f"{where}: {error}") from error
    return plain, shape


@dataclass(frozen=True, slots=True)
class PcbDocSpec:
    """A board: its outline (KiCad frame, in order), its components, its net names and its copper.

    ``copper_layers`` are the copper layers from top to bottom (``pcbrecords.COPPER_STACKS``); ``stack``
    holds their Altium ids, thicknesses, dielectrics and plane nets (``None``: ``StackSpec.default`` for
    ``copper_layers`` without planes). ``tracks``, ``zones``,
    ``arcs`` and ``vias`` are model entities in the frame of the placements whose ``net_id`` holds the
    net's **name** (``None`` without a net); the lens puts it there."""

    outline: tuple[Point, ...]
    components: tuple[PlacedComponent, ...] = ()
    nets: tuple[str, ...] = ()
    copper_layers: tuple[str, ...] = ("F.Cu", "B.Cu")
    stack: StackSpec | None = None
    tracks: tuple[Track, ...] = ()
    arcs: tuple[Arc, ...] = ()
    vias: tuple[Via, ...] = ()
    zones: tuple[Zone, ...] = ()
    net_classes: tuple[NetClassSpec, ...] = ()
    rules: bool = True
    """``False`` leaves ``Rules6`` empty (the bisection variants without rules)."""
    texts: tuple[Text, ...] = ()
    graphics: tuple[Graphic, ...] = ()
    keepouts: tuple[Keepout, ...] = ()
    holes: tuple[Hole, ...] = ()
    """The free items of the board (change c0085), model entities in the frame of the placements, as
    ``lens.altium_copper.lower_items`` checked them: texts and graphics on layers of
    ``pcbrecords.BOARD_LAYER_MAP``, keep-outs on copper layers of the board, round holes."""
    design_rules: tuple[rulemap.LoweredRule, ...] = ()
    """The lowered rules of the design (``rulemap.lower``, change c0084), written before the rules of the
    net classes."""
    frame: Frame | None = None
    """Where the board lies in the document (change c0090). ``None``: ``Frame.of(outline)``, the frame of
    a build. A model that was read from a PCB document is written with ``Frame.document()``, so every
    coordinate keeps its value."""
    origin: Point | None = None
    """The document's origin in the Altium frame, nanometres (``None``: the outline's lower-left corner
    of a build, at 1000 mil)."""
    free_pads: tuple[FreePad, ...] = ()
    """The pads without a component (change c0090), written after the holes."""
    layer_ids: Mapping[str, int] = field(default_factory=lambda: {})
    """Layer name → Altium layer id for the free texts and graphics on layers beside
    ``pcbrecords.BOARD_LAYER_MAP`` (change c0126): ``Mech.1`` … ``Mech.16`` of a board that was read from an
    Altium document. Empty for a build."""
    arc_records: Mapping[str, rec.ArcGeometry] = field(default_factory=lambda: {})
    """Entity id → the centre, radius and angles that an arc of ``arcs`` or a graphic of kind ``arc`` is
    written with instead of the ones derived from its three points (change c0127): the record that an
    imported arc was read from, when the caller found that it still says the entity's points. Empty: every
    arc is derived from its points, as a build writes it."""
    via_protection: ViaProtection | None = None
    """The board's default via protection (change c0112): a tenting side that a via of ``vias`` leaves at
    ``None`` takes its flag from here, and from nothing (a clear flag) when this states none either."""
    allow_full_drill: bool = False
    """``True`` writes a via whose drill equals its diameter (change c0128): a document that Altium saved
    can hold one (``pcb-copper.md``, "Via"), and the rewrite of a document that was read gives it back.
    ``False``, the value of every build, refuses it. A drill above the diameter is refused in both cases."""
    bodies: tuple[PlacedBody, ...] = ()
    """The component bodies to write (change c0121), in the order of the components and, within one, of
    its bodies: body ``i`` is record ``i`` of ``ComponentBodies6`` and of ``ShapeBasedComponentBodies6``.
    Empty, the value of every write without ``--altium-bodies extruded``: both storages are empty and the
    document is the one of change c0085, byte for byte."""
    body_form: rec.BodyForm = "saved"
    """The form of the body records: ``saved``, the 35 keys of a saved body with the two stand-ins, or
    ``short``, the first 21 keys. ``short`` exists for the second file set of step X8 of the author report
    (``H-A-PCBX-BODY-SHORT``); no command and no option of a build selects it."""


def _u32(value: int) -> bytes:
    return struct.pack("<I", value)


def _bool(value: bool) -> str:
    return "TRUE" if value else "FALSE"


def degrees_text(udeg: int) -> str:
    """Microdegrees as degrees in ``[0, 360)`` with at most six decimals."""
    whole, rest = divmod(udeg % 360_000_000, 1_000_000)
    return f"{whole}.{f'{rest:06d}'.rstrip('0')}" if rest else str(whole)


@dataclass(frozen=True, slots=True)
class Frame:
    """KiCad's Y-down board frame → Altium's: Y negated, the outline's lowest X and highest Y moved to
    (1000 mil, 1000 mil); points in nanometres."""

    min_x: int
    max_y: int
    offset: int = _OFFSET_NM

    @classmethod
    def of(cls, outline: Sequence[Point]) -> Frame:
        if len(outline) < 3:
            raise ValueError("a board outline needs at least three points")
        return cls(min(p.x for p in outline), max(p.y for p in outline))

    @classmethod
    def document(cls) -> Frame:
        """The frame of a model that was read from a PCB document (change c0090): Y negated and nothing
        moved, the inverse of the import's ``Point(x, -y)``."""
        return cls(0, 0, 0)

    def __call__(self, point: Point) -> Point:
        return Point(point.x - self.min_x + self.offset, self.max_y - point.y + self.offset)


def file_header() -> bytes:
    return _u32(19) + FILE_HEADER_TEXT[:10].encode("utf-16-le")


def file_header_six(key: str = "") -> bytes:
    """``FileHeaderSix``: the header text, the version double and the document's GUID, each text as a
    32-bit length and a length byte that both hold the text length. ``key`` names the document."""
    text = FILE_HEADER_SIX_TEXT.encode("ascii")
    unique = guid(f"pcbdoc:{key}").encode("ascii")
    return (
        _u32(len(text))
        + bytes((len(text),))
        + text
        + struct.pack("<d", FILE_HEADER_SIX_VERSION)
        + _u32(len(unique))
        + bytes((len(unique),))
        + unique
    )


def board_record(
    outline: Sequence[Point],
    *,
    filename: str = DEFAULT_FILENAME,
    used_layers: Sequence[int] = (),
    stack: StackSpec | None = None,
    frame: Frame | None = None,
    origin: Point | None = None,
) -> bytes:
    """The one ``Board6`` record (``docboard``): the outline in the Altium frame, the origin at the board's
    lower-left corner, the layers that primitives lie on. ``frame`` and ``origin`` (change c0090) replace
    the frame of a build and its origin."""
    from fenolite.backends.altium.project import unique_id  # project imports this module

    frame = frame if frame is not None else Frame.of(outline)
    at = (rec.to_units(_OFFSET_NM), rec.to_units(_OFFSET_NM))
    if origin is not None:
        at = (rec.to_units(origin.x), rec.to_units(origin.y))
    vertices: list[tuple[int, int]] = []
    for point in outline:
        placed = frame(point)
        vertices.append((rec.to_units(placed.x), rec.to_units(placed.y)))
    text = board_text(
        filename,
        vertices,
        at,
        unique_id=unique_id(f"pcbdoc:{filename}:board"),
        used_layers=used_layers,
        stack=stack,
    )
    return rec.text_block(text)


def _net_record(name: str, filename: str) -> bytes:
    from fenolite.backends.altium.project import unique_id  # project imports this module

    fields: list[Field] = [
        *common_fields("TOP"),
        ("PRIMITIVELOCK", "FALSE"),
        ("NAME", name),
        ("VISIBLE", "TRUE"),
        ("COLOR", NET_COLOR),
        ("LOOPREMOVAL", "TRUE"),
        ("OVERRIDECOLORFORDRAW", "FALSE"),
        ("UNIQUEID", unique_id(f"pcbdoc:{filename}:net:{name}")),
        ("JUMPERSVISIBLE", "TRUE"),
    ]
    return rec.property_block(fields)


def channel_offsets(components: Sequence[PlacedComponent]) -> list[int]:
    """``CHANNELOFFSET`` of each component: its index among the components of its own sheet, in the order
    given, from 0 on every sheet (``docs/formats/altium/pcb-document.md``, ``H-A-SCH-HIER-ECO``). The
    components without a sheet (a ``flat`` build, or the top sheet) count together, so a ``flat`` build
    numbers them 0, 1, 2, … as before."""
    seen: dict[str | None, int] = {}
    offsets: list[int] = []
    for component in components:
        sheet = component.sheet[1] if component.sheet is not None else None
        offsets.append(seen.get(sheet, 0))
        seen[sheet] = offsets[-1] + 1
    return offsets


def _component_record(component: PlacedComponent, offset: int, frame: Frame, filename: str) -> bytes:
    from fenolite.backends.altium.project import unique_id  # project imports this module

    at = frame(component.at)
    link, path = "\\" + component.unique_id, ""
    if component.sheet is not None:
        symbol, module = component.sheet
        link = f"\\{symbol}{link}"
        path = f"{filename.rsplit('.', 1)[0]}\\{module}"
    fields: list[Field] = [
        ("SELECTION", "FALSE"),
        ("LAYER", "BOTTOM" if component.side == "bottom" else "TOP"),
        ("LOCKED", _bool(component.locked)),
        ("POLYGONOUTLINE", "FALSE"),
        ("USERROUTED", "TRUE"),
        ("KEEPOUT", "FALSE"),
        ("PRIMITIVELOCK", "TRUE"),
        ("X", rec.mil_text(rec.to_units(at.x))),
        ("Y", rec.mil_text(rec.to_units(at.y))),
        ("PATTERN", component.footprint.defn.name),
        ("NAMEON", _bool(component.designator_place.shown) if component.designator_place else "TRUE"),
        ("COMMENTON", _bool(component.comment_place.shown) if component.comment_place else "FALSE"),
        ("GROUPNUM", "0"),
        ("COUNT", "0"),
        ("ROTATION", angle_text(component.rotation)),
        ("UNIONINDEX", "0"),
        ("CHANNELOFFSET", str(offset)),
        ("SOURCEDESIGNATOR", component.ref),
        ("SOURCEUNIQUEID", link),
        ("SOURCEHIERARCHICALPATH", path),
        ("SOURCEFOOTPRINTLIBRARY", component.footprint_library),
        ("SOURCECOMPONENTLIBRARY", component.component_library),
        ("SOURCELIBREFERENCE", component.lib_reference),
        (
            "UNIQUEID",
            component.record_unique_id or unique_id(f"pcbdoc:{filename}:component:{component.unique_id}"),
        ),
        ("JUMPERSVISIBLE", "TRUE"),
    ]
    return rec.property_block(fields)


def text_record(
    text: str,
    *,
    layer: int,
    at: Point,
    component: int,
    designator: bool,
    wide_index: int,
    mirrored: bool = False,
    free: bool = False,
    height: int = DESIGNATOR_HEIGHT,
    stroke: int = DESIGNATOR_STROKE,
    rotation: int = 0,
) -> bytes:
    """A stroke text (type 5) in the 137-byte long form, ``at`` in nanometres in the Altium frame. A
    component's text is its designator or its comment; a ``free`` text (change c0085, ``component`` is
    ``pcbrecords.NO_INDEX``) is neither, has its own ``height`` and ``stroke`` (nanometres) and ``rotation``
    (microdegrees), and its 8-bit string is ``short_text(text)``: the text itself is the wide string at
    ``wide_index``."""
    body = rec.prefix(layer, component=component)
    body += struct.pack(
        "<3iHdBi",
        rec.to_units(at.x),
        rec.to_units(at.y),
        rec.to_units(height),
        1,
        rec.degrees_of(rotation % 360_000_000),
        1 if mirrored else 0,
        rec.to_units(stroke),
    )
    flags = (0, 0) if free else (0 if designator else 1, 1 if designator else 0)
    body += bytes((*flags, 0, 0, 0, 0))
    body += bytes(64) + b"\0" + struct.pack("<iI", 0, wide_index) + bytes(TEXT_SIZE - 119)
    assert len(body) == TEXT_SIZE
    # a component text outside 7-bit ASCII (change c0090, a model that was read) is written like a free one
    string = short_text(text) if free or text_problem(text) is not None else rec.short_string(text)
    return bytes((rec.TEXT,)) + rec.subrecord(body) + rec.subrecord(string)


def short_text(text: str) -> bytes:
    """The 8-bit string of a free text: one length byte and at most 255 characters in ISO-8859-1, a
    character outside it written ``?`` (``pcb-records.md``, "Text": a reader that knows the wide string
    takes that one)."""
    data = text.encode("iso-8859-1", errors="replace")[:255]
    return bytes((len(data),)) + data


def text_problem_of(text: Text) -> str | None:
    """Why a free text cannot be written, or ``None``: an empty string, a control character or a line
    break, or a height or stroke width that is not positive."""
    if not text.text:
        return "the text is empty"
    if any(ord(ch) < 0x20 or ord(ch) == 0x7F for ch in text.text):
        return "the text holds a control character or a line break"
    if text.size.h <= 0:
        return f"a height of {text.size.h} nm is not positive"
    if text.thickness <= 0:
        return f"a stroke width of {text.thickness} nm is not positive"
    return None


def _wide_entry(index: int, text: str) -> bytes:
    data = text.encode("utf-16-le") + b"\0\0"
    return struct.pack("<2I", index, len(data)) + data


@dataclass
class _Placed:
    pads: list[bytes]
    tracks: list[bytes]
    arcs: list[bytes]
    box: tuple[int, int, int, int]
    regions: list[bytes] = field(default_factory=lambda: [])
    shapes: list[bytes] = field(default_factory=lambda: [])


def _extend(box: list[int], x: int, y: int, reach: int = 0) -> None:
    box[0], box[1] = min(box[0], x - reach), min(box[1], y - reach)
    box[2], box[3] = max(box[2], x + reach), max(box[3], y + reach)


def place_component(component: PlacedComponent, index: int, frame: Frame, nets: Mapping[str, int]) -> _Placed:
    """The pads, tracks and arcs of one component at absolute Altium coordinates, and the box of its pads
    and graphics (nanometres, Altium frame)."""
    footprint = component.footprint
    check = check_footprint(footprint.defn, footprint.extras, texts=footprint.texts)
    if check.refusal is not None:
        raise ValueError(f"{component.ref}: {check.refusal}")
    bottom = component.side == "bottom"
    transform = Transform.placement(component.at, component.rotation, mirror=bottom)

    def to_frame(point: Point) -> Point:
        return frame(transform.apply(point))

    box = [2**62, 2**62, -(2**62), -(2**62)]
    pads: list[bytes] = []
    for pad in check.pads:
        at = to_frame(pad.position)
        if component.nets_by_pad is not None:
            net = nets.get(component.nets_by_pad.get(pad.id, ""), rec.NO_INDEX)
        else:
            net = nets.get(component.pad_nets.get(pad.number, ""), rec.NO_INDEX)
        pads.append(
            pad_bytes(
                pad,
                footprint.extras.get(pad.id, PadExtras()),
                at=at,
                rotation_udeg=transform.apply_angle(pad.rotation),
                flip=bottom,
                net=net,
                component=index,
            )
        )
        _extend(box, at.x, at.y, max(pad.size.w, pad.size.h) // 2)
    tracks: list[bytes] = []
    arcs: list[bytes] = []
    for graphic in check.graphics:
        kept = component.arc_records.get(graphic.id) if graphic.kind == "arc" else None
        if kept is not None:  # an arc that was read is written from its record (change c0127)
            layer = rec.LAYER_MAP[graphic.layer]
            layer = rec.FLIP_PAIRS[layer] if bottom else layer
            arcs.append(rec.arc_record(layer, kept, rec.to_units(graphic.width), component=index))
        else:
            for record in graphic_records(graphic, to_frame, flip=bottom, component=index):
                (tracks if record[0] == rec.TRACK else arcs).append(record)
        points = [to_frame(p) for p in graphic.points]
        if graphic.kind == "circle":
            centre, edge = points
            reach = max(abs(edge.x - centre.x), abs(edge.y - centre.y))
            _extend(box, centre.x, centre.y, reach)
        else:
            for point in points:
                _extend(box, point.x, point.y)
    if box[0] > box[2]:
        at = frame(component.at)
        box = [at.x, at.y, at.x, at.y]
    placed = _Placed(pads, tracks, arcs, (box[0], box[1], box[2], box[3]))
    plain = Transform.placement(component.at, component.rotation)
    for item in component.items:  # as the instance holds them: no mirror, no layer flip (change c0126)
        graphic = item.graphic
        where = [frame(plain.apply(p)) for p in graphic.points]
        if graphic.kind in ("rect", "polygon"):
            if graphic.kind == "rect":
                s, e = graphic.points
                ring = [frame(plain.apply(p)) for p in (s, Point(e.x, s.y), e, Point(s.x, e.y))]
            else:
                ring = _ring(where)
            corners = [_units(point) for point in ring]
            if graphic.filled:
                placed.regions.append(rec.region_record(item.layer, corners, component=index))
                placed.shapes.append(
                    rec.region_record(item.layer, corners, shape_based=True, component=index)
                )
            else:
                width = rec.to_units(graphic.width)
                for number, corner in enumerate(corners):
                    following = corners[(number + 1) % len(corners)]
                    tracks.append(rec.track_record(item.layer, corner, following, width, component=index))
        elif graphic.kind == "line":
            a, b = (_units(point) for point in where)
            tracks.append(rec.track_record(item.layer, a, b, rec.to_units(graphic.width), component=index))
        elif graphic.kind == "circle":
            geometry = rec.circle_geometry(where[0], where[1])
            arcs.append(rec.arc_record(item.layer, geometry, rec.to_units(graphic.width), component=index))
        else:
            geometry = item.arc or rec.arc_from_points(*where)
            arcs.append(rec.arc_record(item.layer, geometry, rec.to_units(graphic.width), component=index))
    return placed


def _xy(point: Point) -> tuple[int, int]:
    return (point.x, point.y)


def _units(point: Point) -> tuple[int, int]:
    return (rec.to_units(point.x), rec.to_units(point.y))


@dataclass(frozen=True, slots=True)
class _Copper:
    """What the copper records need: the frame, the net indexes and the Altium id of each copper layer
    (a plane has an id from ``pcbrecords.FIRST_PLANE``)."""

    frame: Frame
    nets: Mapping[str, int]
    layers: Mapping[str, int]

    def position(self, layer: str) -> int:
        names = list(self.layers)
        return names.index(layer) if layer in self.layers else len(names)

    def net(self, ident: str, name: str | None) -> int:
        if name is None:
            return rec.NO_INDEX
        if name not in self.nets:
            raise ValueError(f"{ident}: the net {name!r} is not a net of the document")
        return self.nets[name]

    def signal_layer(self, ident: str, layer: str) -> int:
        if layer not in self.layers:
            raise ValueError(
                f"{ident}: the layer {layer} is not a copper layer of the board ({', '.join(self.layers)})"
            )
        if self.layers[layer] >= rec.FIRST_PLANE:
            raise ValueError(f"{ident}: the layer {layer} is an internal plane, which holds no primitive")
        return self.layers[layer]


def routed_tracks(tracks: Sequence[Track], copper: _Copper) -> list[bytes]:
    """The free 36-byte tracks of the board (``pcb-copper.md``, "Tracks and arcs"), sorted by stack
    position of the layer, net name, start, end, width and entity id. ``ValueError`` names the id of a
    track on an unknown or plane layer, of zero length, without a positive width or on an unknown net."""
    out: list[bytes] = []
    ordered = sorted(
        tracks,
        key=lambda t: (copper.position(t.layer), t.net_id or "", _xy(t.start), _xy(t.end), t.width, t.id),
    )
    for track in ordered:
        layer = copper.signal_layer(track.id, track.layer)
        if track.width <= 0:
            raise ValueError(f"{track.id}: a track needs a positive width, not {track.width} nm")
        if track.start == track.end:
            raise ValueError(f"{track.id}: the track has zero length")
        net = copper.net(track.id, track.net_id)
        a, b = _units(copper.frame(track.start)), _units(copper.frame(track.end))
        out.append(rec.track_record(layer, a, b, rec.to_units(track.width), net=net, locked=track.locked))
    return out


def routed_arcs(
    arcs: Sequence[Arc], copper: _Copper, records: Mapping[str, rec.ArcGeometry] | None = None
) -> list[bytes]:
    """The free 47-byte arcs of the board, sorted like the tracks (start, then end); ``ValueError`` as for
    a track, and for collinear points. An arc whose id ``records`` names (``PcbDocSpec.arc_records``,
    change c0127) is written with that geometry, and its points are not looked at."""
    known = records or {}
    out: list[bytes] = []
    ordered = sorted(
        arcs,
        key=lambda a: (copper.position(a.layer), a.net_id or "", _xy(a.start), _xy(a.end), a.width, a.id),
    )
    for arc in ordered:
        layer = copper.signal_layer(arc.id, arc.layer)
        if arc.width <= 0:
            raise ValueError(f"{arc.id}: an arc needs a positive width, not {arc.width} nm")
        net = copper.net(arc.id, arc.net_id)
        geometry = known.get(arc.id)
        if geometry is None:
            try:
                geometry = rec.arc_from_points(*(copper.frame(p) for p in (arc.start, arc.mid, arc.end)))
            except ValueError as error:
                raise ValueError(f"{arc.id}: {error}") from error
        out.append(rec.arc_record(layer, geometry, rec.to_units(arc.width), net=net, locked=arc.locked))
    return out


def via_span(via: Via, layers: Sequence[str]) -> tuple[str, str]:
    """The two copper layers a via spans, the upper one first; ``ValueError`` names the id of a micro via
    or of a via whose ``layers`` are not two different copper layers of ``layers`` (top to bottom)."""
    if via.via_type == "micro":
        raise ValueError(f"{via.id}: a micro via is not written")
    names = list(layers)
    if len(via.layers) != 2 or via.layers[0] == via.layers[1] or any(n not in names for n in via.layers):
        spans = ", ".join(via.layers) or "no layer"
        raise ValueError(f"{via.id}: the via spans {spans}, not two copper layers of {', '.join(names)}")
    upper, lower = sorted(via.layers, key=names.index)
    return upper, lower


def drill_pairs(vias: Sequence[Via], copper: _Copper) -> tuple[tuple[int, int], ...]:
    """The drill pairs of the board besides the pair of its outer layers: one per distinct span of a blind
    or buried via, as Altium ids, in stack order of the upper and then of the lower layer."""
    names = list(copper.layers)
    spans = {via_span(via, names) for via in vias} - {(names[0], names[-1])}
    ordered = sorted(spans, key=lambda span: (names.index(span[0]), names.index(span[1])))
    return tuple((copper.layers[upper], copper.layers[lower]) for upper, lower in ordered)


def via_records(
    vias: Sequence[Via],
    copper: _Copper,
    *,
    allow_full_drill: bool = False,
    default: ViaProtection | None = None,
) -> list[bytes]:
    """The vias of the board (``pcb-copper.md``, "Via"), sorted by net name, position, diameter and entity
    id: a through via with the start layer 1 and the end layer 32, a blind or buried via (change c0085)
    with the ids of the two layers it spans. ``ValueError`` names the id of a via that ``via_span``
    refuses, whose drill is not below its diameter, or on an unknown net. ``allow_full_drill``
    (``PcbDocSpec.allow_full_drill``, change c0128) accepts a drill equal to the diameter. Each tenting
    flag is that of ``via_tenting(via, default)`` (change c0112; ``default`` is
    ``PcbDocSpec.via_protection``); every other value of the protection writes nothing."""
    names = list(copper.layers)
    out: list[bytes] = []
    ordered = sorted(vias, key=lambda v: (v.net_id or "", _xy(v.position), v.diameter, v.id))
    for via in ordered:
        upper, lower = via_span(via, names)
        full = allow_full_drill and via.drill == via.diameter
        if not (0 < via.drill < via.diameter or (full and via.drill > 0)):
            raise ValueError(
                f"{via.id}: the drill of {via.drill} nm is not below the diameter of {via.diameter} nm"
            )
        net = copper.net(via.id, via.net_id)
        x, y = _units(copper.frame(via.position))
        top, bottom = via_tenting(via, default)
        out.append(
            rec.via_record(
                x,
                y,
                rec.to_units(via.diameter),
                rec.to_units(via.drill),
                net=net,
                start=copper.layers[upper],
                end=copper.layers[lower],
                locked=via.locked,
                tented_top=top,
                tented_bottom=bottom,
            )
        )
    return out


def via_tenting(via: Via, default: ViaProtection | None) -> tuple[bool, bool]:
    """The two tenting flags (top, bottom) an Altium document holds for ``via`` (altium-build, "Via
    protection in an Altium build"): for each side the via's own value, else the board default's when it
    states one, else ``False``, the clear flag that is this backend's own default. Covering, plugging,
    capping and filling have no flag: no Altium fact is recorded for them."""

    def side(name: str) -> bool:
        value = getattr(via.protection, name)
        if value is None and default is not None:
            value = getattr(default, name)
        return value is True

    return side("tenting_front"), side("tenting_back")


def unstated_tenting(via: Via, default: ViaProtection | None) -> bool:
    """True when a tenting side of ``via`` is stated neither by the via nor by the board default: KiCad
    tents such a side, and the Altium document leaves its flag clear."""
    return any(
        getattr(via.protection, name) is None and (default is None or getattr(default, name) is None)
        for name in ("tenting_front", "tenting_back")
    )


UNWRITTEN_FEATURES: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("covering", ("covering_front", "covering_back")),
    ("plugging", ("plugging_front", "plugging_back")),
    ("capping", ("capping",)),
    ("filling", ("filling",)),
)
"""The features of ``ViaProtection`` that no Altium document holds, each with its fields."""


def unwritten_features(via: Via, default: ViaProtection | None) -> tuple[str, ...]:
    """The features among covering, plugging, capping and filling that ``via`` has, by its own value or
    by the board default: what stays in the model only."""
    found: list[str] = []
    for feature, fields in UNWRITTEN_FEATURES:
        for name in fields:
            value = getattr(via.protection, name)
            if value is None and default is not None:
                value = getattr(default, name)
            if value is True:
                found.append(feature)
                break
    return tuple(found)


# --- free items of the board (change c0085) ---------------------------------------------------------------

KEEPOUT_BITS: Mapping[str, int] = MappingProxyType(
    {"no_vias": 0x01, "no_tracks": 0x02, "no_copper_pour": 0x04, "no_pads": 0x18}
)
"""Restriction of a model keep-out → its bits of the keep-out restrictions value (``pcb-records.md``,
"Regions and keep-outs"): vias, tracks, copper, and pads as surface-mount and through-hole pads. The
restriction ``no_footprints`` has no bit."""


def keepout_restrictions(keepout: Keepout) -> int:
    """The restrictions value of ``keepout``: the bits of ``KEEPOUT_BITS`` of the restrictions it sets."""
    return sum(bits for name, bits in KEEPOUT_BITS.items() if getattr(keepout, name))


def _ring(points: Sequence[Point]) -> list[Point]:
    ring = list(points)
    if len(ring) > 1 and ring[0] == ring[-1]:
        ring.pop()
    return ring


def board_layer(name: str, extra: Mapping[str, int] | None = None) -> int | None:
    """The Altium id of the layer ``name`` for a free text or graphic: ``pcbrecords.BOARD_LAYER_MAP``, else
    ``extra`` (``PcbDocSpec.layer_ids``); ``None`` for a layer without a layer in the document."""
    found = rec.BOARD_LAYER_MAP.get(name)
    return found if found is not None or extra is None else extra.get(name)


def graphic_problem(
    graphic: Graphic, *, arc_known: bool = False, layers: Mapping[str, int] | None = None
) -> str | None:
    """Why a board graphic cannot be written, or ``None``: a layer outside ``BOARD_LAYER_MAP``, a point
    count that does not fit its kind, collinear arc points, or a drawn outline without a positive width.
    ``arc_known`` says that the arc is written from a record of its own (``PcbDocSpec.arc_records``, change
    c0127), so its three points need not give a circle."""
    if board_layer(graphic.layer, layers) is None:
        return f"the layer {graphic.layer} has no layer in the document for a graphic"
    wanted = {"line": 2, "rect": 2, "circle": 2, "arc": 3}.get(graphic.kind)
    count = len(_ring(graphic.points)) if graphic.kind == "polygon" else len(graphic.points)
    if (wanted is not None and count != wanted) or (wanted is None and count < 3):
        return f"a {graphic.kind} of {count} points is not written"
    if graphic.kind in ("line", "circle") and graphic.points[0] == graphic.points[1]:
        return f"the {graphic.kind} has no extent"
    if graphic.kind == "rect" and (
        graphic.points[0].x == graphic.points[1].x or graphic.points[0].y == graphic.points[1].y
    ):
        return "the rect has no area"
    if graphic.kind == "arc" and not arc_known:
        try:
            rec.arc_from_points(*graphic.points)
        except ValueError:
            return "the three points of the arc lie on one line"
    drawn = graphic.kind in ("line", "arc") or not graphic.filled
    if drawn and graphic.width <= 0:
        return f"a drawn {graphic.kind} needs a positive width, not {graphic.width} nm"
    if graphic.filled and graphic.kind == "circle":
        return "a filled circle has no record: a region holds straight edges only"
    return None


def keepout_problem(keepout: Keepout, layers: Sequence[str]) -> str | None:
    """Why a keep-out cannot be written, or ``None``: fewer than three outline points, no layer, a layer
    that is not a copper layer of the board, or no restriction that the record carries."""
    if len(_ring(keepout.outline)) < 3:
        return "the keep-out has an outline of fewer than three points"
    if not keepout.layers:
        return "the keep-out names no layer"
    outside = [layer for layer in keepout.layers if layer not in layers]
    if outside:
        return f"the layer {outside[0]} is not a copper layer of the board"
    if not keepout_restrictions(keepout):
        return "the keep-out sets no restriction that the record carries (tracks, vias, pads, copper)"
    return None


@dataclass
class _Free:
    """The records of the free items, per storage."""

    tracks: list[bytes] = field(default_factory=lambda: [])
    arcs: list[bytes] = field(default_factory=lambda: [])
    regions: list[bytes] = field(default_factory=lambda: [])
    shapes: list[bytes] = field(default_factory=lambda: [])
    pads: list[bytes] = field(default_factory=lambda: [])

    def region(self, layer: int, ring: Sequence[Point], frame: Frame, keepout: int | None = None) -> None:
        vertices = [_units(frame(point)) for point in ring]
        self.regions.append(rec.region_record(layer, vertices, keepout=keepout))
        self.shapes.append(rec.region_record(layer, vertices, keepout=keepout, shape_based=True))


def free_records(spec: PcbDocSpec, copper: _Copper) -> _Free:
    """The records of the graphics, keep-outs and holes of ``spec`` (``pcb-records.md``, "Regions and
    keep-outs" and "Free pads as holes"), each kind sorted by layer id, points and entity id. A drawn
    graphic is tracks and arcs without a net; a filled rectangle or polygon is one region, written in
    ``Regions6`` and in ``ShapeBasedRegions6``. A keep-out that names every copper layer of the board is one
    keep-out region on the Keep-Out layer; otherwise it is one keep-out region per layer it names. A hole
    is a free pad. ``ValueError`` names the id of an item that ``graphic_problem`` or ``keepout_problem``
    refuses, or of a hole without a positive drill."""
    out = _Free()
    frame = copper.frame
    for graphic in sorted(
        spec.graphics,
        key=lambda g: (board_layer(g.layer, spec.layer_ids) or 0, [_xy(p) for p in g.points], g.id),
    ):
        kept = spec.arc_records.get(graphic.id) if graphic.kind == "arc" else None
        problem = graphic_problem(graphic, arc_known=kept is not None, layers=spec.layer_ids)
        if problem is not None:
            raise ValueError(f"{graphic.id}: {problem}")
        layer = board_layer(graphic.layer, spec.layer_ids)
        assert layer is not None
        if graphic.filled and graphic.kind in ("rect", "polygon"):
            if graphic.kind == "rect":
                s, e = graphic.points
                ring = [s, Point(e.x, s.y), e, Point(s.x, e.y)]
            else:
                ring = _ring(graphic.points)
            out.region(layer, ring, frame)
            continue
        width = rec.to_units(graphic.width)
        if graphic.kind in ("polygon", "rect"):
            if graphic.kind == "rect":
                s, e = graphic.points
                ring = [s, Point(e.x, s.y), e, Point(s.x, e.y)]
            else:
                ring = _ring(graphic.points)
            for index, point in enumerate(ring):
                a, b = _units(frame(point)), _units(frame(ring[(index + 1) % len(ring)]))
                out.tracks.append(rec.track_record(layer, a, b, width))
        elif graphic.kind == "line":
            a, b = (_units(frame(point)) for point in graphic.points)
            out.tracks.append(rec.track_record(layer, a, b, width))
        elif graphic.kind == "circle":
            centre, edge = (frame(point) for point in graphic.points)
            out.arcs.append(rec.arc_record(layer, rec.circle_geometry(centre, edge), width))
        else:
            start, mid, end = (frame(point) for point in graphic.points)
            out.arcs.append(rec.arc_record(layer, kept or rec.arc_from_points(start, mid, end), width))
    names = list(copper.layers)
    for keepout in sorted(spec.keepouts, key=lambda k: ([_xy(p) for p in k.outline], k.layers, k.id)):
        problem = keepout_problem(keepout, names)
        if problem is not None:
            raise ValueError(f"{keepout.id}: {problem}")
        value = keepout_restrictions(keepout)
        ring = _ring(keepout.outline)
        if set(keepout.layers) == set(names):
            out.region(rec.KEEPOUT_LAYER, ring, frame, value)
        else:
            for name in sorted(set(keepout.layers), key=names.index):
                out.region(copper.layers[name], ring, frame, value)
    for hole in sorted(spec.holes, key=lambda h: (_xy(h.position), h.drill, h.id)):
        if hole.drill <= 0:
            raise ValueError(f"{hole.id}: a hole needs a positive drill, not {hole.drill} nm")
        x, y = _units(frame(hole.position))
        out.pads.append(rec.hole_record(x, y, rec.to_units(hole.drill), plated=hole.plated))
    for free in spec.free_pads:
        net = rec.NO_INDEX if free.net is None else copper.net(free.pad.id, free.net)
        at = frame(free.pad.position)
        out.pads.append(pad_bytes(free.pad, free.extras, at=at, rotation_udeg=free.pad.rotation, net=net))
    return out


def free_texts(spec: PcbDocSpec, frame: Frame, first: int) -> tuple[list[bytes], list[bytes]]:
    """The free stroke texts of ``spec`` and their wide strings, numbered from ``first``, sorted by layer
    id, position, string and entity id (``pcb-records.md``, "Text"). A text on a bottom-side layer is
    mirrored. ``ValueError`` names the id of a text on a layer outside ``BOARD_LAYER_MAP`` or one that
    ``text_problem_of`` refuses."""
    texts: list[bytes] = []
    wide: list[bytes] = []
    ordered = sorted(
        spec.texts,
        key=lambda t: (board_layer(t.layer, spec.layer_ids) or 0, _xy(t.position), t.text, t.id),
    )
    for text in ordered:
        layer = board_layer(text.layer, spec.layer_ids)
        if layer is None:
            raise ValueError(f"{text.id}: the layer {text.layer} has no layer in the document for a text")
        problem = text_problem_of(text)
        if problem is not None:
            raise ValueError(f"{text.id}: {problem}")
        number = first + len(texts)
        texts.append(
            text_record(
                text.text,
                layer=layer,
                at=frame(text.position),
                component=rec.NO_INDEX,
                designator=False,
                wide_index=number,
                mirrored=layer in rec.BOTTOM_SIDE,
                free=True,
                height=text.size.h,
                stroke=text.thickness,
                rotation=text.rotation,
            )
        )
        wide.append(_wide_entry(number, text.text))
    return texts, wide


NO_NET_NAME = "NONET"
"""What stands for the net in the generated name of a polygon without a net."""


def polygon_name(text: str) -> str:
    """The ``NAME`` value of a polygon named ``text``: its character codes in decimal, joined by commas
    (``71,78,68`` for ``GND``)."""
    return name_codes(text)


def polygon_records(zones: Sequence[Zone], copper: _Copper) -> list[bytes]:
    """One unpoured polygon pour per zone layer (``pcb-copper.md``, "Polygon pour"), in pour order: by
    falling zone priority, then net name, first outline point, zone id and stack position; the pour index
    is the record's position. A zone without a name gets ``<NET>_L<layer position>_P<pour index>``.
    ``ValueError`` names the id of a zone with fewer than three outline points, on a layer that is not a
    signal copper layer of the board, on an unknown net or with a name that cannot be written."""
    pours: list[tuple[Zone, str, list[Point]]] = []
    for zone in zones:
        outline = list(zone.outline)
        if len(outline) > 1 and outline[0] == outline[-1]:
            outline.pop()
        if len(outline) < 3:
            raise ValueError(f"{zone.id}: a zone needs an outline of at least three points")
        if not zone.layers:
            raise ValueError(f"{zone.id}: the zone names no layer")
        problem = text_problem(zone.name) if zone.name else None
        if problem is not None:
            raise ValueError(f"{zone.id}: the zone name {zone.name!r} {problem}")
        copper.net(zone.id, zone.net_id)
        for layer in zone.layers:
            copper.signal_layer(zone.id, layer)
            pours.append((zone, layer, outline))
    pours.sort(
        key=lambda pour: (
            -pour[0].priority,
            pour[0].net_id or "",
            _xy(pour[2][0]),
            pour[0].id,
            copper.position(pour[1]),
        )
    )
    out: list[bytes] = []
    for index, (zone, layer, outline) in enumerate(pours):
        generated = f"{zone.net_id or NO_NET_NAME}_L{copper.position(layer) + 1:02d}_P{index:03d}".upper()
        net = copper.net(zone.id, zone.net_id)
        fields = polygon_fields(
            rec.layer_text(copper.layers[layer]),
            [_units(copper.frame(point)) for point in outline],
            name=zone.name or generated,
            pour_index=index,
            net=None if net == rec.NO_INDEX else net,
            auto_name=not zone.name,
            remove_dead=zone.settings.island_removal != "never",
        )
        out.append(rec.property_block(fields))
    return out


def class_records(classes: Sequence[NetClassSpec], nets: Mapping[str, int], filename: str) -> list[bytes]:
    """One ``Classes6`` record per net class, in name order (``pcb-copper.md``, "Net classes"): a ``KIND=0``
    class that is no super class, its nets as members ``M0``, ``M1`` … in name order. ``ValueError`` for a
    class name that cannot be written or holds ``'`` (a rule scope quotes it), a repeated name, or a
    member that is not a net of the document."""
    from fenolite.backends.altium.project import unique_id  # project imports this module

    out: list[bytes] = []
    seen: set[str] = set()
    for item in sorted(classes, key=lambda c: c.name):
        problem = text_problem(item.name)
        if problem is not None or "'" in item.name:
            raise ValueError(f"the net class name {item.name!r} {problem or 'holds an apostrophe'}")
        if item.name in seen:
            raise ValueError(f"the net class {item.name!r} is given twice")
        seen.add(item.name)
        members = sorted(set(item.nets))
        for net in members:
            if net not in nets:
                raise ValueError(
                    f"the net class {item.name}: the member {net!r} is not a net of the document"
                )
        fields: list[Field] = [
            *common_fields("MULTILAYER"),
            ("NAME", item.name),
            ("KIND", "0"),
            ("SUPERCLASS", "FALSE"),
            *((f"M{index}", net) for index, net in enumerate(members)),
            ("SELECTED", "FALSE"),
            ("SCHAUTOGENERATEDCLUSTER", "FALSE"),
            ("UNIQUEID", unique_id(f"pcbdoc:{filename}:class:{item.name}")),
        ]
        out.append(rec.property_block(fields))
    return out


def component_class_records(components: Sequence[PlacedComponent], filename: str) -> list[bytes]:
    """One ``Classes6`` record per schematic sheet that holds a component (change c0048, ``pcb-copper.md``,
    "Classes and rules of the change order"): the component class Altium derives from the sheet. A
    ``KIND=1`` class that is no super class, its members ``M0``, ``M1`` … the refs of the sheet's
    components, each once, in code-point order; the records are in code-point order of the class names.
    The class of a module sheet is named after the module (the second item of ``PlacedComponent.sheet``,
    the name of its sheet symbol); the class of the top sheet, or of the single sheet of a flat build
    (``sheet`` is ``None``), is named after that sheet: the stem that ``filename`` shares with it. A module
    of that same name shares the class. ``ValueError`` for a class name that cannot be written."""
    from fenolite.backends.altium.project import unique_id  # project imports this module

    top = filename.rsplit(".", 1)[0]
    members: dict[str, set[str]] = {}
    for component in components:
        # a sheet below the first level is named by its own sheet symbol, the last one (change c0086)
        sheet = top if component.sheet is None else component.sheet[1].rsplit("\\", 1)[-1]
        members.setdefault(sheet, set()).add(component.ref)
    out: list[bytes] = []
    for module in sorted(members):
        problem = text_problem(module)
        if problem is not None:
            raise ValueError(f"the component class name {module!r} {problem}")
        fields: list[Field] = [
            *common_fields("MULTILAYER"),
            ("NAME", module),
            ("KIND", "1"),
            ("SUPERCLASS", "FALSE"),
            *((f"M{index}", ref) for index, ref in enumerate(sorted(members[module]))),
            ("SELECTED", "FALSE"),
            ("SCHAUTOGENERATEDCLUSTER", "FALSE"),
            ("UNIQUEID", unique_id(f"pcbdoc:{filename}:component-class:{module}")),
        ]
        out.append(rec.property_block(fields))
    return out


DEFAULT_CLEARANCE = 200_000
DEFAULT_TRACK_WIDTH = 250_000
DEFAULT_VIA_DIAMETER = 600_000
DEFAULT_VIA_DRILL = 300_000
"""The values of the ``All`` rules in nanometres: Fenolite's choices (``pcb-copper.md``)."""
RULE_CLEARANCE, RULE_WIDTH, RULE_VIAS = 0, 2, 11
"""The rule-kind numbers that open a ``Rules6`` record."""
ALL_SCOPE = "All"


def _mil(nm: int) -> str:
    return rec.mil_text(rec.to_units(nm))


def _rule(
    kind: int,
    kind_name: str,
    name: str,
    scope: str,
    priority: int,
    keys: Sequence[Field],
    filename: str,
    *,
    second: str = ALL_SCOPE,
    net_scope: str = "",
) -> bytes:
    from fenolite.backends.altium.project import unique_id  # project imports this module

    fields: list[Field] = [
        *common_fields("TOP"),
        ("RULEKIND", kind_name),
        ("NETSCOPE", net_scope or ("DifferentNets" if kind == RULE_CLEARANCE else "AnyNet")),
        ("LAYERKIND", "SameLayer"),
        ("SCOPE1EXPRESSION", scope),
        ("SCOPE2EXPRESSION", second),
        ("NAME", name),
        ("ENABLED", "TRUE"),
        ("PRIORITY", str(priority)),
        ("COMMENT", ""),
        ("UNIQUEID", unique_id(f"pcbdoc:{filename}:rule:{name}")),
        ("DEFINEDBYLOGICALDOCUMENT", "FALSE"),
        *keys,
    ]
    return struct.pack("<H", kind) + rec.property_block(fields)


_Planned = tuple[int, str, str, str, str, str, Sequence[Field]]
"""A rule before its priority: kind number, kind text, name, the two scopes, ``NETSCOPE`` and the keys."""


def _class_rules(spec: PcbDocSpec) -> list[_Planned]:
    """The rules of the net classes and Fenolite's ``All`` defaults (change c0038): per kind, one rule per
    class that holds the value, in class-name order, then the ``All`` rule."""
    classes = sorted(spec.net_classes, key=lambda c: c.name)
    widths = [(item.net_id, item.width) for item in (*spec.tracks, *spec.arcs)]
    vias = [(via.net_id, via.diameter, via.drill) for via in spec.vias]

    def scoped(item: NetClassSpec | None) -> str:
        return ALL_SCOPE if item is None else f"InNetClass('{item.name}')"

    def named(kind: str, item: NetClassSpec | None) -> str:
        return kind if item is None else f"{kind}_{item.name}"

    def inside(net: str | None, item: NetClassSpec | None) -> bool:
        return item is None or net in item.nets

    out: list[_Planned] = []
    clearances = [(c, c.clearance) for c in classes if c.clearance is not None]
    for item, gap in [*clearances, (None, DEFAULT_CLEARANCE)]:
        keys: list[Field] = [
            ("GAP", _mil(gap)),
            ("GENERICCLEARANCE", _mil(gap)),
            ("IGNOREPADTOPADCLEARANCEINFOOTPRINT", "FALSE"),
            ("OBJECTCLEARANCES", ""),
        ]
        name = named("Clearance", item)
        out.append((RULE_CLEARANCE, "Clearance", name, scoped(item), ALL_SCOPE, "DifferentNets", keys))
    preferred = [(c, c.track_width) for c in classes if c.track_width is not None]
    for item, width in [*preferred, (None, DEFAULT_TRACK_WIDTH)]:
        found = [width, *(w for net, w in widths if inside(net, item))]
        keys = [
            ("MAXLIMIT", _mil(max(found))),
            ("MINLIMIT", _mil(min(found))),
            ("PREFEREDWIDTH", _mil(width)),
        ]
        out.append((RULE_WIDTH, "Width", named("Width", item), scoped(item), ALL_SCOPE, "AnyNet", keys))
    styles = [
        (c, c.via_diameter, c.via_drill)
        for c in classes
        if c.via_diameter is not None and c.via_drill is not None
    ]
    for item, diameter, drill in [*styles, (None, DEFAULT_VIA_DIAMETER, DEFAULT_VIA_DRILL)]:
        diameters = [diameter, *(d for net, d, _h in vias if inside(net, item))]
        holes = [drill, *(h for net, _d, h in vias if inside(net, item))]
        keys = [
            ("HOLEWIDTH", _mil(drill)),
            ("WIDTH", _mil(diameter)),
            ("VIASTYLE", "Through Hole"),
            ("MINHOLEWIDTH", _mil(min(holes))),
            ("MINWIDTH", _mil(min(diameters))),
            ("MAXHOLEWIDTH", _mil(max(holes))),
            ("MAXWIDTH", _mil(max(diameters))),
        ]
        name = named("RoutingVias", item)
        out.append((RULE_VIAS, "RoutingVias", name, scoped(item), ALL_SCOPE, "AnyNet", keys))
    return out


def rule_records(spec: PcbDocSpec, filename: str) -> list[bytes]:
    """The ``Rules6`` records (``pcb-copper.md``, "Rules" and "Rule kinds lowered"), by kind in the order of
    ``rulemap.KIND_ORDER``. Per kind, first the lowered rules of the design (``spec.design_rules``) in
    their order, then the rules of change c0038: one rule ``<Kind>_<class>`` scoped
    ``InNetClass('<class>')`` for each net class that holds the kind's value, in class-name order, and one
    rule named after the kind with the scope ``All`` and Fenolite's default. A rule of c0038 whose two
    scopes are those of a rule of the design is left out: the design's rule replaces it. Priorities count
    from 1 within a kind. The limits of a width or via rule of c0038 span its preferred value and the
    written copper of its scope. The rules of c0038 are written only for a spec with copper or net
    classes; no rule is written with ``rules`` off."""
    if not spec.rules:
        return []
    has_copper = bool(spec.tracks or spec.arcs or spec.vias or spec.zones or spec.net_classes)
    planned: list[_Planned] = []
    planned.extend(
        (r.number, r.kind, r.name, r.scope1, r.scope2, r.net_scope, r.keys) for r in spec.design_rules
    )
    taken = {(kind, first, second) for _n, kind, _name, first, second, _net, _keys in planned}
    names = {name for _n, _kind, name, _first, _second, _net, _keys in planned}
    for rule in _class_rules(spec) if has_copper else []:
        if (rule[1], rule[3], rule[4]) in taken:
            continue
        name = f"{rule[2]}_class" if rule[2] in names else rule[2]  # a net named like a class rule
        planned.append((rule[0], rule[1], name, *rule[3:]))
    order = {kind: position for position, kind in enumerate(rulemap.KIND_ORDER)}
    out: list[bytes] = []
    for kind in sorted({rule[1] for rule in planned}, key=lambda k: order[k]):
        of_kind = [rule for rule in planned if rule[1] == kind]
        for priority, (number, _kind, name, first, second, net_scope, keys) in enumerate(of_kind, start=1):
            out.append(
                _rule(number, kind, name, first, priority, keys, filename, second=second, net_scope=net_scope)
            )
    return out


def document_stack(spec: PcbDocSpec) -> StackSpec:
    """The copper stack of ``spec``: ``spec.stack``, or the default stack of its copper layers without
    planes. ``ValueError`` when the stack does not hold one id per copper layer (a signal layer's id of
    ``pcbrecords.LAYER_MAP``, or a plane on an inner layer), or when a plane's net is not a net of the
    document."""
    signal = rec.copper_stack(spec.copper_layers)
    if spec.stack is None:
        return StackSpec.default(signal)
    stack = spec.stack
    planes = [
        name
        for name, layer in zip(spec.copper_layers, stack.copper, strict=False)
        if layer >= rec.FIRST_PLANE and name not in (spec.copper_layers[0], spec.copper_layers[-1])
    ]
    if len(stack.copper) != len(signal) or rec.copper_stack(spec.copper_layers, planes) != stack.copper:
        raise ValueError(
            f"the stack {stack.copper!r} does not hold one id per copper layer of {spec.copper_layers!r}"
        )
    for layer, net in zip(stack.planes, stack.plane_nets, strict=True):
        if net not in spec.nets:
            raise ValueError(f"the net {net!r} of {rec.LAYER_NAMES[layer]} is not a net of the document")
    return stack


def _storage(name: str, records: Sequence[bytes], *, count: int | None = None) -> Storage:
    header = len(records) if count is None else count
    return Storage(name, (("Header", _u32(header)), ("Data", b"".join(records))))


def _wide_string(text: str) -> bytes:
    """A wide string: a 32-bit byte length that counts the 2-byte NUL, then UTF-16LE and the NUL."""
    data = text.encode("utf-16-le") + b"\0\0"
    return _u32(len(data)) + data


def record_layer(record: bytes) -> int:
    """The layer byte of a primitive record (the first byte of its common prefix); for a pad the prefix
    opens the fifth subrecord. A via lies on Multi-Layer."""
    body = record[1:]
    if record[0] == rec.PAD:
        for _ in range(4):
            (length,) = struct.unpack_from("<I", body)
            body = body[4 + length :]
    return body[4]


def _option_storages(filename: str) -> list[Storage]:
    """The storages of ``OPTION_STORAGES`` in that order (``pcb-document.md``, "Storages")."""
    from fenolite.backends.altium.project import unique_id  # project imports this module

    def pad_via(key: str) -> bytes:
        return rec.property_block(
            (
                ("PADVIALIBRARY.LIBRARYID", guid(f"pcbdoc:{filename}:{key}")),
                ("PADVIALIBRARY.LIBRARYNAME", "<Local>"),
                ("PADVIALIBRARY.DISPLAYUNITS", "1"),
            )
        )

    signals: list[Field] = [
        *common_fields("MULTILAYER"),
        ("NAME", "All xSignals"),
        ("KIND", "10"),
        ("SUPERCLASS", "TRUE"),
        ("SELECTED", "FALSE"),
        ("SCHAUTOGENERATEDCLUSTER", "FALSE"),
        ("UNIQUEID", unique_id(f"pcbdoc:{filename}:signals")),
    ]
    contents: tuple[tuple[int, bytes], ...] = (
        (1, rec.property_block(_PLACER)),
        (1, rec.property_block(_PIN_SWAP)),
        (1, rec.property_block(_RULE_CHECKER)),
        (0, pad_via("padvia")),
        (0, pad_via("padviacache")),
        (1, _wide_string("1.0") + _u32(0) + _u32(0)),
        (1, _wide_string(NO_CONSTRAINTS)),
        (1, rec.property_block(signals)),
    )
    pairs = zip(OPTION_STORAGES, contents, strict=True)
    return [_storage(name, [data], count=count) for name, (count, data) in pairs]


def write_pcbdoc(spec: PcbDocSpec, *, filename: str = DEFAULT_FILENAME) -> bytes:
    """The bytes of the PCB document of ``spec`` (``pcb-document.md``, "Fenolite's choices"); ``filename``
    is the document's file name (no folder), written into the board record and the source of its ids.
    ``ValueError`` for an outline of fewer than three points, a refused footprint, copper layers that are
    not a stack of ``pcbrecords.COPPER_STACKS`` or copper that cannot be written exactly (the entity's id
    is named); ``cfb.CompoundTooLarge`` past the size limit. The bodies of ``spec.bodies`` (change c0121) go
    into the two body storages; no entry of ``Models``, ``ModelsNoEmbed``, ``Textures`` or
    ``UniqueIDPrimitiveInformation`` is written for a body."""
    from fenolite.backends.altium.project import unique_id  # project imports this module

    frame = spec.frame if spec.frame is not None else Frame.of(spec.outline)
    net_names = sorted(spec.nets)
    nets = {name: index for index, name in enumerate(net_names)}
    stack = document_stack(spec)
    copper = _Copper(frame, nets, dict(zip(spec.copper_layers, stack.copper, strict=True)))
    components: list[bytes] = []
    pads: list[bytes] = []
    tracks: list[bytes] = []
    arcs: list[bytes] = []
    texts: list[bytes] = []
    wide: list[bytes] = []
    regions: list[bytes] = []
    shapes: list[bytes] = []
    offsets = channel_offsets(spec.components)
    for index, component in enumerate(spec.components):
        components.append(_component_record(component, offsets[index], frame, filename))
        placed = place_component(component, index, frame, nets)
        pads += placed.pads
        tracks += placed.tracks
        arcs += placed.arcs
        regions += placed.regions
        shapes += placed.shapes
        local = Transform.placement(component.at, component.rotation)
        x0, y0, x1, y1 = placed.box
        middle = (x0 + x1) // 2
        bottom = component.side == "bottom"
        overlay = rec.LAYER_MAP["B.SilkS" if bottom else "F.SilkS"]
        for text, designator, at in (
            (component.ref, True, Point(middle, y1 + DESIGNATOR_RISE)),
            (component.comment, False, Point(middle, y0 - COMMENT_DROP)),
        ):
            if not text:  # a component of a model that was read may have no designator or comment
                continue
            number = len(texts)
            place = component.designator_place if designator else component.comment_place
            if place is None:
                texts.append(
                    text_record(
                        text,
                        layer=overlay,
                        at=at,
                        component=index,
                        designator=designator,
                        wide_index=number,
                        mirrored=bottom,
                    )
                )
            else:  # where the model's field says (change c0126)
                texts.append(
                    text_record(
                        text,
                        layer=place.layer,
                        at=frame(local.apply(place.position)),
                        component=index,
                        designator=designator,
                        wide_index=number,
                        mirrored=place.mirrored,
                        height=place.height,
                        stroke=place.stroke,
                        rotation=(place.rotation + component.rotation) % FULL_TURN,
                    )
                )
            wide.append(_wide_entry(number, text))
        for item in component.texts:  # the free texts of the component (change c0126)
            number = len(texts)
            texts.append(
                text_record(
                    item.text,
                    layer=item.place.layer,
                    at=frame(local.apply(item.place.position)),
                    component=index,
                    designator=False,
                    wide_index=number,
                    mirrored=item.place.mirrored,
                    free=True,
                    height=item.place.height,
                    stroke=item.place.stroke,
                    rotation=(item.place.rotation + component.rotation) % FULL_TURN,
                )
            )
            wide.append(_wide_entry(number, item.text))
    tracks += routed_tracks(spec.tracks, copper)
    arcs += routed_arcs(spec.arcs, copper, spec.arc_records)
    filled: dict[str, list[bytes]] = {name: [] for name in COPPER_STORAGES}
    filled["Vias6"] = via_records(
        spec.vias, copper, allow_full_drill=spec.allow_full_drill, default=spec.via_protection
    )
    pairs = drill_pairs(spec.vias, copper)
    if pairs:
        stack = dataclasses.replace(stack, drill_pairs=pairs)
    free = free_records(spec, copper)
    tracks += free.tracks
    arcs += free.arcs
    pads += free.pads
    filled["Regions6"] = [*regions, *free.regions]
    filled["ShapeBasedRegions6"] = [*shapes, *free.shapes]
    more_texts, more_wide = free_texts(spec, frame, len(texts))
    texts += more_texts
    wide += more_wide
    filled["Polygons6"] = polygon_records(spec.zones, copper)
    filled["Classes6"] = [
        *class_records(spec.net_classes, nets, filename),
        *component_class_records(spec.components, filename),
    ]
    filled["Rules6"] = rule_records(spec, filename)
    filled[BODY_STORAGES[0]], filled[BODY_STORAGES[1]] = body_records(spec, frame)
    poured = {copper.layers[layer] for zone in spec.zones for layer in zone.layers}
    used = sorted(
        {
            record_layer(record)
            for record in (*pads, *tracks, *arcs, *texts, *filled["Vias6"], *regions, *free.regions)
        }
        | poured
        | {body.layer for body in spec.bodies}
    )
    unique = [
        rec.property_block(
            (
                ("PRIMITIVEINDEX", str(index)),
                ("PRIMITIVEOBJECTID", "Pad"),
                ("UNIQUEID", unique_id(f"pcbdoc:{filename}:pad:{index}")),
            )
        )
        for index in range(len(pads))
    ]
    entries: list[Entry] = [
        ("FileHeader", file_header()),
        ("FileHeaderSix", file_header_six(",".join(c.unique_id for c in spec.components))),
        _storage(
            "Board6",
            [
                board_record(
                    spec.outline,
                    filename=filename,
                    used_layers=used,
                    stack=stack,
                    frame=spec.frame,
                    origin=spec.origin,
                )
            ],
        ),
        _storage("Nets6", [_net_record(name, filename) for name in net_names]),
        _storage("Components6", components),
        _storage("Pads6", pads),
        _storage("Tracks6", tracks),
        _storage("Arcs6", arcs),
        _storage("Texts6", texts),
        _storage("WideStrings6", wide),
        _storage(UNIQUE_STORAGE, unique),
    ]
    entries += _option_storages(filename)
    entries += [_storage(name, filled.get(name, [])) for name in _TAIL_ORDER]
    return write_compound(entries)


__all__ = [
    "BODIES_OFF",
    "BODY_IS_MODEL",
    "BODY_MODES",
    "BODY_NO_FOOTPRINT",
    "BODY_NO_OUTLINE",
    "BODY_STORAGES",
    "BOARD_OFFSET_MIL",
    "BodyMode",
    "PlacedBody",
    "body_mode",
    "body_problem",
    "body_records",
    "body_vertices",
    "place_body",
    "COPPER_STORAGES",
    "DEFAULT_CLEARANCE",
    "DEFAULT_FILENAME",
    "DEFAULT_TRACK_WIDTH",
    "DEFAULT_VIA_DIAMETER",
    "DEFAULT_VIA_DRILL",
    "EMPTY_STORAGES",
    "EVIDENCE",
    "FILE_HEADER_SIX_TEXT",
    "FILE_HEADER_TEXT",
    "Frame",
    "FreePad",
    "NetClassSpec",
    "OPTION_STORAGES",
    "PcbDocSpec",
    "ComponentGraphic",
    "ComponentText",
    "PlacedComponent",
    "TextPlace",
    "board_layer",
    "board_record",
    "channel_offsets",
    "class_records",
    "component_class_records",
    "KEEPOUT_BITS",
    "degrees_text",
    "document_stack",
    "drill_pairs",
    "free_records",
    "free_texts",
    "graphic_problem",
    "keepout_problem",
    "keepout_restrictions",
    "short_text",
    "text_problem_of",
    "via_span",
    "via_tenting",
    "unstated_tenting",
    "unwritten_features",
    "UNWRITTEN_FEATURES",
    "file_header",
    "file_header_six",
    "place_component",
    "polygon_name",
    "polygon_records",
    "record_layer",
    "routed_arcs",
    "routed_tracks",
    "rule_records",
    "text_record",
    "via_records",
    "write_pcbdoc",
]
