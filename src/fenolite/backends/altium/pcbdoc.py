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
    LibFootprint,
    PadExtras,
    check_footprint,
    graphic_records,
    pad_bytes,
)
from fenolite.core.coords import Point
from fenolite.core.evidence import Evidence, Level
from fenolite.geometry.transform import Transform
from fenolite.model.board import Arc, Graphic, Hole, Keepout, Side, Text, Track, Via, Zone

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
Altium-saved document holds, empty in a document without such objects."""
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
        "H-A-PCB-CU-PLANE",
        "H-A-PCB-CU-REPOUR",
        "H-A-PCB-CU-ROUNDTRIP",
        "H-A-PCB-CU-RULES",
        "H-A-PCB-CU-STACK",
        "H-A-PCB-CU-TRACK",
        "H-A-PCB-CU-VIA",
        "H-A-PCB-CU-VIEWER",
        "H-A-PCB-DOC-BOTTOM",
        "H-A-PCB-DOC-LINK",
        "H-A-PCB-DOC-NETS",
        "H-A-PCB-DOC-OPEN",
        "H-A-PCB-DOC-VIEWER",
        "H-A-PCB-KICAD-DOC",
        "H-A-PCBX-HOLE",
        "H-A-PCBX-KEEPOUT",
        "H-A-PCBX-KICAD",
        "H-A-PCBX-READBACK",
        "H-A-PCBX-REPOUR",
        "H-A-PCBX-STACK",
        "H-A-PCBX-TEXT",
        "H-A-PCBX-VIASPAN",
    ),
)
"""The PCB document is inferred from public sources; ``pcb import`` checks only what KiCad reads. The
``H-A-PCB-CU-*`` rows are those of the copper (change c0038), and ``H-A-ECO-COMPCLASS`` and
``H-A-ECO-SHEETCLASS`` those of the component classes of the sheets (change c0048)."""


@dataclass(frozen=True, slots=True)
class PlacedComponent:
    """One component on the board: its schematic link, its footprint and its placement (KiCad frame).
    ``sheet`` (change c0037) is ``(sheet symbol unique id, module name)`` for a component on a module sheet
    of a hierarchical project, and ``None`` for a component on the top sheet or on a single sheet."""

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

    @classmethod
    def of(cls, outline: Sequence[Point]) -> Frame:
        if len(outline) < 3:
            raise ValueError("a board outline needs at least three points")
        return cls(min(p.x for p in outline), max(p.y for p in outline))

    def __call__(self, point: Point) -> Point:
        return Point(point.x - self.min_x + _OFFSET_NM, self.max_y - point.y + _OFFSET_NM)


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
) -> bytes:
    """The one ``Board6`` record (``docboard``): the outline in the Altium frame, the origin at the board's
    lower-left corner, the layers that primitives lie on."""
    from fenolite.backends.altium.project import unique_id  # project imports this module

    frame = Frame.of(outline)
    origin = rec.to_units(_OFFSET_NM)
    vertices: list[tuple[int, int]] = []
    for point in outline:
        placed = frame(point)
        vertices.append((rec.to_units(placed.x), rec.to_units(placed.y)))
    text = board_text(
        filename,
        vertices,
        (origin, origin),
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
        ("NAMEON", "TRUE"),
        ("COMMENTON", "FALSE"),
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
        ("UNIQUEID", unique_id(f"pcbdoc:{filename}:component:{component.unique_id}")),
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
    string = short_text(text) if free else rec.short_string(text)
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
    return _Placed(pads, tracks, arcs, (box[0], box[1], box[2], box[3]))


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
        out.append(rec.track_record(layer, a, b, rec.to_units(track.width), net=net))
    return out


def routed_arcs(arcs: Sequence[Arc], copper: _Copper) -> list[bytes]:
    """The free 47-byte arcs of the board, sorted like the tracks (start, then end); ``ValueError`` as for
    a track, and for collinear points."""
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
        try:
            geometry = rec.arc_from_points(*(copper.frame(p) for p in (arc.start, arc.mid, arc.end)))
        except ValueError as error:
            raise ValueError(f"{arc.id}: {error}") from error
        out.append(rec.arc_record(layer, geometry, rec.to_units(arc.width), net=net))
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


def via_records(vias: Sequence[Via], copper: _Copper) -> list[bytes]:
    """The vias of the board (``pcb-copper.md``, "Via"), sorted by net name, position, diameter and entity
    id: a through via with the start layer 1 and the end layer 32, a blind or buried via (change c0085)
    with the ids of the two layers it spans. ``ValueError`` names the id of a via that ``via_span``
    refuses, whose drill is not below its diameter, or on an unknown net."""
    names = list(copper.layers)
    out: list[bytes] = []
    ordered = sorted(vias, key=lambda v: (v.net_id or "", _xy(v.position), v.diameter, v.id))
    for via in ordered:
        upper, lower = via_span(via, names)
        if not 0 < via.drill < via.diameter:
            raise ValueError(
                f"{via.id}: the drill of {via.drill} nm is not below the diameter of {via.diameter} nm"
            )
        net = copper.net(via.id, via.net_id)
        x, y = _units(copper.frame(via.position))
        out.append(
            rec.via_record(
                x,
                y,
                rec.to_units(via.diameter),
                rec.to_units(via.drill),
                net=net,
                start=copper.layers[upper],
                end=copper.layers[lower],
            )
        )
    return out


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


def graphic_problem(graphic: Graphic) -> str | None:
    """Why a board graphic cannot be written, or ``None``: a layer outside ``BOARD_LAYER_MAP``, a point
    count that does not fit its kind, collinear arc points, or a drawn outline without a positive width."""
    if graphic.layer not in rec.BOARD_LAYER_MAP:
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
    if graphic.kind == "arc":
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
        spec.graphics, key=lambda g: (rec.BOARD_LAYER_MAP.get(g.layer, 0), [_xy(p) for p in g.points], g.id)
    ):
        problem = graphic_problem(graphic)
        if problem is not None:
            raise ValueError(f"{graphic.id}: {problem}")
        layer = rec.BOARD_LAYER_MAP[graphic.layer]
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
            out.arcs.append(rec.arc_record(layer, rec.arc_from_points(start, mid, end), width))
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
    return out


def free_texts(spec: PcbDocSpec, frame: Frame, first: int) -> tuple[list[bytes], list[bytes]]:
    """The free stroke texts of ``spec`` and their wide strings, numbered from ``first``, sorted by layer
    id, position, string and entity id (``pcb-records.md``, "Text"). A text on a bottom-side layer is
    mirrored. ``ValueError`` names the id of a text on a layer outside ``BOARD_LAYER_MAP`` or one that
    ``text_problem_of`` refuses."""
    texts: list[bytes] = []
    wide: list[bytes] = []
    ordered = sorted(
        spec.texts, key=lambda t: (rec.BOARD_LAYER_MAP.get(t.layer, 0), _xy(t.position), t.text, t.id)
    )
    for text in ordered:
        if text.layer not in rec.BOARD_LAYER_MAP:
            raise ValueError(f"{text.id}: the layer {text.layer} has no layer in the document for a text")
        problem = text_problem_of(text)
        if problem is not None:
            raise ValueError(f"{text.id}: {problem}")
        layer = rec.BOARD_LAYER_MAP[text.layer]
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
        sheet = top if component.sheet is None else component.sheet[1]
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
    is named); ``cfb.CompoundTooLarge`` past the size limit."""
    from fenolite.backends.altium.project import unique_id  # project imports this module

    frame = Frame.of(spec.outline)
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
    offsets = channel_offsets(spec.components)
    for index, component in enumerate(spec.components):
        components.append(_component_record(component, offsets[index], frame, filename))
        placed = place_component(component, index, frame, nets)
        pads += placed.pads
        tracks += placed.tracks
        arcs += placed.arcs
        x0, y0, x1, y1 = placed.box
        middle = (x0 + x1) // 2
        bottom = component.side == "bottom"
        overlay = rec.LAYER_MAP["B.SilkS" if bottom else "F.SilkS"]
        for text, designator, at in (
            (component.ref, True, Point(middle, y1 + DESIGNATOR_RISE)),
            (component.comment, False, Point(middle, y0 - COMMENT_DROP)),
        ):
            number = len(texts)
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
            wide.append(_wide_entry(number, text))
    tracks += routed_tracks(spec.tracks, copper)
    arcs += routed_arcs(spec.arcs, copper)
    filled: dict[str, list[bytes]] = {name: [] for name in COPPER_STORAGES}
    filled["Vias6"] = via_records(spec.vias, copper)
    pairs = drill_pairs(spec.vias, copper)
    if pairs:
        stack = dataclasses.replace(stack, drill_pairs=pairs)
    free = free_records(spec, copper)
    tracks += free.tracks
    arcs += free.arcs
    pads += free.pads
    filled["Regions6"] = free.regions
    filled["ShapeBasedRegions6"] = free.shapes
    more_texts, more_wide = free_texts(spec, frame, len(texts))
    texts += more_texts
    wide += more_wide
    filled["Polygons6"] = polygon_records(spec.zones, copper)
    filled["Classes6"] = [
        *class_records(spec.net_classes, nets, filename),
        *component_class_records(spec.components, filename),
    ]
    filled["Rules6"] = rule_records(spec, filename)
    poured = {copper.layers[layer] for zone in spec.zones for layer in zone.layers}
    used = sorted(
        {record_layer(record) for record in (*pads, *tracks, *arcs, *texts, *filled["Vias6"], *free.regions)}
        | poured
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
            [board_record(spec.outline, filename=filename, used_layers=used, stack=stack)],
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
    "BOARD_OFFSET_MIL",
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
    "NetClassSpec",
    "OPTION_STORAGES",
    "PcbDocSpec",
    "PlacedComponent",
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
