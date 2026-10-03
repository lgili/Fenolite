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
as free primitives with their net, and through vias in the 321-byte form Altium saves.
"""

from __future__ import annotations

import struct
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field

import fenolite.backends.altium.pcbrecords as rec
from fenolite.backends.altium.ascii import Field
from fenolite.backends.altium.cfb import Entry, Storage, write_compound
from fenolite.backends.altium.docboard import StackSpec, angle_text, board_text, common_fields
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
from fenolite.model.board import Arc, Side, Track, Via

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
    ),
)
"""The PCB document is inferred from public sources; ``pcb import`` checks only what KiCad reads. The
``H-A-PCB-CU-*`` rows are those of the copper (change c0038)."""


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
class PcbDocSpec:
    """A board: its outline (KiCad frame, in order), its components, its net names and its copper.

    ``copper_layers`` are the copper layers from top to bottom (``pcbrecords.COPPER_STACKS``); ``stack``
    holds their Altium ids, thicknesses, dielectrics and plane nets (``None``: ``StackSpec.default`` for
    ``copper_layers`` without planes). ``tracks``,
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


def _component_record(component: PlacedComponent, index: int, frame: Frame, filename: str) -> bytes:
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
        ("CHANNELOFFSET", str(index)),
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
) -> bytes:
    """A text (type 5) in the 123-byte long form, ``at`` in nanometres in the Altium frame."""
    body = rec.prefix(layer, component=component)
    body += struct.pack(
        "<3iHdBi",
        rec.to_units(at.x),
        rec.to_units(at.y),
        rec.to_units(DESIGNATOR_HEIGHT),
        1,
        0.0,
        1 if mirrored else 0,
        rec.to_units(DESIGNATOR_STROKE),
    )
    body += bytes((0 if designator else 1, 1 if designator else 0, 0, 0, 0, 0))
    body += bytes(64) + b"\0" + struct.pack("<iI", 0, wide_index) + bytes(TEXT_SIZE - 119)
    assert len(body) == TEXT_SIZE
    return bytes((rec.TEXT,)) + rec.subrecord(body) + rec.subrecord(rec.short_string(text))


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


def via_records(vias: Sequence[Via], copper: _Copper) -> list[bytes]:
    """The through vias of the board (``pcb-copper.md``, "Via"), sorted by net name, position, diameter and
    entity id. ``ValueError`` names the id of a via that is not a through via from the top to the bottom
    copper layer, whose drill is not below its diameter, or on an unknown net."""
    names = list(copper.layers)
    ends = {names[0], names[-1]}
    out: list[bytes] = []
    ordered = sorted(vias, key=lambda v: (v.net_id or "", _xy(v.position), v.diameter, v.id))
    for via in ordered:
        if via.via_type != "through":
            raise ValueError(f"{via.id}: a {via.via_type} via is not written; only through vias are")
        if len(via.layers) != 2 or set(via.layers) != ends:
            spans = ", ".join(via.layers) or "no layer"
            raise ValueError(f"{via.id}: the via spans {spans}, not {names[0]} to {names[-1]}")
        if not 0 < via.drill < via.diameter:
            raise ValueError(
                f"{via.id}: the drill of {via.drill} nm is not below the diameter of {via.diameter} nm"
            )
        net = copper.net(via.id, via.net_id)
        x, y = _units(copper.frame(via.position))
        out.append(rec.via_record(x, y, rec.to_units(via.diameter), rec.to_units(via.drill), net=net))
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
        if layer >= rec.FIRST_PLANE
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
    for index, component in enumerate(spec.components):
        components.append(_component_record(component, index, frame, filename))
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
    used = sorted({record_layer(record) for record in (*pads, *tracks, *arcs, *texts, *filled["Vias6"])})
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
    "DEFAULT_FILENAME",
    "EMPTY_STORAGES",
    "EVIDENCE",
    "FILE_HEADER_SIX_TEXT",
    "FILE_HEADER_TEXT",
    "Frame",
    "OPTION_STORAGES",
    "PcbDocSpec",
    "PlacedComponent",
    "board_record",
    "degrees_text",
    "document_stack",
    "file_header",
    "file_header_six",
    "place_component",
    "record_layer",
    "routed_arcs",
    "routed_tracks",
    "text_record",
    "via_records",
    "write_pcbdoc",
]
