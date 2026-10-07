# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""A reader of Altium PCB libraries and documents, for tests only (change c0035, capability
altium-pcb-writer, "PCB files read back").

Written from ``docs/formats/altium/pcb-library.md``, ``pcb-records.md``, ``pcb-document.md`` and
``pcb-copper.md`` (change c0038, "Copper records read back") alone, on top of ``tests/_cfb_read.py``; it
never imports the product's PCB writers. ``read_pcblib`` and ``read_pcbdoc``
return the decoded files and raise ``PcbReadError`` naming the first rule the bytes break: subrecord
minimums (pad subrecord 5 at least 110 bytes, subrecord 6 empty or at least 596, track 36, arc 47, text
40), the pad-name length, indexes naming existing records, ``Header`` counts equal to the decoded counts,
and every ``Library/Data`` name found through a ``Parameters`` stream holding it as ``PATTERN``.
"""

from __future__ import annotations

import re
import struct
from dataclasses import dataclass, field

from _cfb_read import parse_compound

NO_INDEX = 0xFFFF
UNITS_PER_MIL = 10_000
LIBRARY_HEADER = "PCB 6.0 Binary Library File"
LIBRARY_VERSION = 5.01
LIBRARY_KIND = "Protel_Advanced_PCB_Library"
UNIQUE_STORAGE = "UniqueIDPrimitiveInformation"
PARAMETER_KEYS = ("PATTERN", "HEIGHT", "DESCRIPTION", "ITEMGUID", "REVISIONGUID")
LIBRARY_STREAMS = (
    "FileHeader",
    "Library/Header",
    "Library/Data",
    "Library/EmbeddedFonts",
    *(
        f"Library/{storage}/{stream}"
        for storage in ("Models", "ModelsNoEmbed", "Textures", "ComponentParamsTOC", "PadViaLibrary")
        for stream in ("Header", "Data")
    ),
)
"""Every stream a library holds beside its footprints (``pcb-library.md``, "Container")."""
TRACK, ARC, PAD, TEXT, VIA = 4, 1, 2, 5, 3
MINIMUMS = {TRACK: 36, ARC: 47}
VIA_MIN = 31
"""A via subrecord holds at least the prefix, x, y, diameter, hole and the two layer bytes."""
MULTI_LAYER = 74
PAD_GEOMETRY_MIN = 110
PAD_LAYERS_MIN = 596
TEXT_MIN = 40
TEXT_LONG = 123
KNOWN_TYPES = {ARC, PAD, 3, TRACK, TEXT, 6, 11, 12}


class PcbReadError(ValueError):
    """The bytes break a rule of the PCB fact pages."""


@dataclass
class Prefix:
    layer: int
    flags: tuple[int, int]
    net: int
    polygon: int
    component: int


@dataclass
class Track:
    prefix: Prefix
    x1: int
    y1: int
    x2: int
    y2: int
    width: int
    size: int


@dataclass
class ArcRecord:
    prefix: Prefix
    cx: int
    cy: int
    radius: int
    start: float
    end: float
    width: int
    size: int


@dataclass
class PadRecord:
    name: str
    prefix: Prefix
    x: int
    y: int
    sizes: tuple[tuple[int, int], tuple[int, int], tuple[int, int]]
    hole: int
    shapes: tuple[int, int, int]
    rotation: float
    plated: int
    mode: int
    tail_63: tuple[int, ...]
    expansions: tuple[int, int]
    mask_modes: tuple[int, int]
    geometry_size: int
    subrecords_2_to_4: tuple[bytes, bytes, bytes]
    layers_size: int
    hole_shape: int | None = None
    rounded: int | None = None
    alternate_shapes: tuple[int, ...] = ()
    corners: tuple[int, ...] = ()
    inner_sizes: tuple[tuple[int, int], ...] = ()
    inner_shapes: tuple[int, ...] = ()


@dataclass
class TextRecord:
    prefix: Prefix
    x: int
    y: int
    height: int
    font: int
    rotation: float
    mirrored: int
    width: int
    size: int
    text: str
    is_comment: int = 0
    is_designator: int = 0
    wide_index: int | None = None


@dataclass
class ViaRecord:
    prefix: Prefix
    x: int
    y: int
    diameter: int
    hole: int
    start_layer: int
    end_layer: int
    size: int
    body: bytes = b""


@dataclass
class PolygonRecord:
    layer: str
    net: int | None
    name: str
    pour_index: int
    vertices: list[tuple[str, str]]
    fields: dict[str, str]


@dataclass
class ClassRecord:
    name: str
    kind: str
    members: list[str]
    fields: dict[str, str]


@dataclass
class RuleRecord:
    kind: int
    name: str
    priority: int
    scope: str
    fields: dict[str, str]


RULE_KINDS = {
    0: "Clearance",
    2: "Width",
    6: "PlaneConnect",
    9: "RoutingLayers",
    11: "RoutingVias",
    12: "PlaneClearance",
    20: "PolygonConnect",
    62: "UnpouredPolygon",
}
"""Rule-kind number → ``RULEKIND`` (``pcb-copper.md``, "Rules")."""


@dataclass
class BodyRecord:
    """A component body (change c0121; ``pcb-bodies.md``, "Written form of an extruded body"): the prefix,
    the keys of its text in order, its two heights as mil texts, and its vertices in units. ``closing`` is
    the repeated first vertex of the shape-based form."""

    prefix: Prefix
    keys: list[tuple[str, str]]
    vertices: list[tuple[int, int]]
    closing: tuple[int, int] | None
    length: int

    def value(self, key: str) -> str:
        (found,) = [value for name, value in self.keys if name == key][:1]
        return found


Primitive = Track | ArcRecord | PadRecord | TextRecord | ViaRecord | BodyRecord


@dataclass
class Footprint:
    storage: str
    name: str
    parameters: dict[str, str]
    primitives: list[Primitive]
    header_count: int
    unique_ids: list[dict[str, str]]
    wide_strings: list[dict[str, str]]


@dataclass
class PcbLib:
    names: list[str]
    library_fields: dict[str, str]
    footprints: dict[str, Footprint]
    section_keys: dict[str, str]
    streams: dict[str, bytes]
    storages: list[str]
    board: list[tuple[str, str]] = field(default_factory=lambda: [])
    """The fields of the board record in order; ``RECORD`` repeats."""
    unique_id: str = ""
    toc: list[dict[str, str]] = field(default_factory=lambda: [])


@dataclass
class PcbDoc:
    file_header: bytes
    file_header_six: bytes
    board: dict[str, str]
    nets: list[dict[str, str]]
    components: list[dict[str, str]]
    pads: list[PadRecord]
    tracks: list[Track]
    arcs: list[ArcRecord]
    texts: list[TextRecord]
    wide_strings: dict[int, str]
    storages: dict[str, tuple[int, bytes]] = field(default_factory=dict)
    streams: dict[str, bytes] = field(default_factory=dict)
    board_fields: list[tuple[str, str]] = field(default_factory=lambda: [])
    """The fields of the board record in order; ``RECORD`` and the common keys repeat. ``board`` keeps the
    first value of each key."""
    unique_ids: list[dict[str, str]] = field(default_factory=lambda: [])
    options: dict[str, dict[str, str]] = field(default_factory=dict)
    """The one property block of each option storage that holds one."""
    vias: list[ViaRecord] = field(default_factory=lambda: [])
    polygons: list[PolygonRecord] = field(default_factory=lambda: [])
    classes: list[ClassRecord] = field(default_factory=lambda: [])
    rules: list[RuleRecord] = field(default_factory=lambda: [])
    copper_chain: list[int] = field(default_factory=lambda: [])
    """The numbered copper layers from top to bottom, read through ``LAYER<n>NEXT`` from layer 1."""
    plane_nets: dict[int, str] = field(default_factory=dict)
    """Plane number k → the net of ``PLANE<k>NETNAME``, for the planes of the chain."""
    bodies: list[BodyRecord] = field(default_factory=lambda: [])
    """The component bodies of ``ComponentBodies6`` (change c0121); the twin storage holds the same."""

    @property
    def free_tracks(self) -> list[Track]:
        """The routed tracks: those of no component."""
        return [t for t in self.tracks if t.prefix.component == NO_INDEX]

    @property
    def free_arcs(self) -> list[ArcRecord]:
        """The routed arcs: those of no component."""
        return [a for a in self.arcs if a.prefix.component == NO_INDEX]


def property_blocks(data: bytes, where: str) -> list[dict[str, str]]:
    """Every property block of ``data``: a 32-bit word (length in the low 24 bits, type 0), the text and
    its NUL. An empty block (only the NUL) gives an empty mapping."""
    blocks: list[dict[str, str]] = []
    offset = 0
    while offset < len(data):
        block, offset = property_block_at(data, offset, where)
        blocks.append(block)
    return blocks


def property_block_at(data: bytes, offset: int, where: str) -> tuple[dict[str, str], int]:
    if offset + 4 > len(data):
        raise PcbReadError(f"{where}: a property block's length word is cut at {offset}")
    (word,) = struct.unpack_from("<I", data, offset)
    length, kind = word & 0xFFFFFF, word >> 24
    if kind != 0:
        raise PcbReadError(f"{where}: a property block at {offset} has type {kind}")
    payload = data[offset + 4 : offset + 4 + length]
    if len(payload) != length or not payload.endswith(b"\0") or b"\0" in payload[:-1]:
        raise PcbReadError(f"{where}: the property block at {offset} does not end with its one NUL")
    text = payload[:-1].decode("ascii")
    fields: dict[str, str] = {}
    if text:
        if not text.startswith("|"):
            raise PcbReadError(f"{where}: the property block at {offset} does not start with '|'")
        for part in text[1:].split("|"):
            key, equals, value = part.partition("=")
            if not equals or not key:
                raise PcbReadError(f"{where}: field {part!r} is not KEY=VALUE")
            if key in fields:
                raise PcbReadError(f"{where}: the key {key} repeats")
            fields[key] = value
    return fields, offset + 4 + length


def string_block_at(data: bytes, offset: int, where: str) -> tuple[str, int]:
    """A 32-bit length, one length byte and the characters; the 32-bit length is 1 + the characters."""
    if offset + 5 > len(data):
        raise PcbReadError(f"{where}: a string block is cut at {offset}")
    (block,) = struct.unpack_from("<I", data, offset)
    count = data[offset + 4]
    if block != count + 1:
        raise PcbReadError(f"{where}: a string block of {block} bytes holds a {count}-byte text")
    text = data[offset + 5 : offset + 5 + count]
    if len(text) != count:
        raise PcbReadError(f"{where}: a string block's text is cut")
    return text.decode("ascii"), offset + 5 + count


def u32(data: bytes, where: str) -> int:
    if len(data) != 4:
        raise PcbReadError(f"{where}: {len(data)} bytes, not one 32-bit value")
    return struct.unpack("<I", data)[0]


def _prefix(body: bytes) -> Prefix:
    layer, f1, f2, net, polygon, component = struct.unpack_from("<BBBHHH", body, 0)
    return Prefix(layer, (f1, f2), net, polygon, component)


def _subrecords(data: bytes, offset: int, count: int, where: str) -> tuple[list[bytes], int]:
    out: list[bytes] = []
    for number in range(1, count + 1):
        if offset + 4 > len(data):
            raise PcbReadError(f"{where}: subrecord {number} is cut")
        (length,) = struct.unpack_from("<I", data, offset)
        body = data[offset + 4 : offset + 4 + length]
        if len(body) != length:
            raise PcbReadError(f"{where}: subrecord {number} of {length} bytes is cut")
        out.append(body)
        offset += 4 + length
    return out, offset


def _pad(subs: list[bytes], where: str) -> PadRecord:
    name_sub, s2, s3, s4, geometry, layers = subs
    if not name_sub or len(name_sub) != 1 + name_sub[0]:
        raise PcbReadError(f"{where}: the pad name subrecord of {len(name_sub)} bytes is not 1 + its text")
    name = name_sub[1:].decode("ascii")
    if len(geometry) < PAD_GEOMETRY_MIN:
        raise PcbReadError(f"{where}: pad {name} subrecord 5 has {len(geometry)} bytes, fewer than 110")
    if layers and len(layers) < PAD_LAYERS_MIN:
        raise PcbReadError(f"{where}: pad {name} subrecord 6 has {len(layers)} bytes, neither 0 nor 596+")
    x, y = struct.unpack_from("<2i", geometry, 13)
    sizes = struct.unpack_from("<6i", geometry, 21)
    (hole,) = struct.unpack_from("<i", geometry, 45)
    shapes = struct.unpack_from("<3B", geometry, 49)
    (rotation,) = struct.unpack_from("<d", geometry, 52)
    plated, _unknown, mode = struct.unpack_from("<3B", geometry, 60)
    tail = struct.unpack_from("<BiihiiI", geometry, 63)
    expansions = struct.unpack_from("<2i", geometry, 86)
    masks = struct.unpack_from("<2B", geometry, 101)
    if len(geometry) == PAD_GEOMETRY_MIN and struct.unpack_from("<i", geometry, 106)[0] != 0:
        raise PcbReadError(f"{where}: pad {name}: a 110-byte subrecord 5 needs 0 at offset 106")
    pad = PadRecord(
        name=name,
        prefix=_prefix(geometry),
        x=x,
        y=y,
        sizes=((sizes[0], sizes[1]), (sizes[2], sizes[3]), (sizes[4], sizes[5])),
        hole=hole,
        shapes=(shapes[0], shapes[1], shapes[2]),
        rotation=rotation,
        plated=plated,
        mode=mode,
        tail_63=tuple(tail),
        expansions=(expansions[0], expansions[1]),
        mask_modes=(masks[0], masks[1]),
        geometry_size=len(geometry),
        subrecords_2_to_4=(s2, s3, s4),
        layers_size=len(layers),
    )
    if layers:
        xs = struct.unpack_from("<29i", layers, 0)
        ys = struct.unpack_from("<29i", layers, 116)
        pad.inner_sizes = tuple(zip(xs, ys, strict=True))
        pad.inner_shapes = tuple(layers[232:261])
        pad.hole_shape = layers[262]
        pad.rounded = layers[531]
        pad.alternate_shapes = tuple(layers[532:564])
        pad.corners = tuple(layers[564:596])
    return pad


REGION = 11
REGION_STORAGES = ("Regions6", "ShapeBasedRegions6")


def count_regions(data: bytes, where: str) -> int:
    """The number of region records of a stream: each the type byte 11, a 32-bit length and that many
    bytes; the records are framed and not decoded."""
    count = at = 0
    while at < len(data):
        if data[at] != REGION or at + 5 > len(data):
            raise PcbReadError(f"{where}: byte {at} does not open a region record")
        (length,) = struct.unpack_from("<I", data, at + 1)
        at += 5 + length
        if at > len(data):
            raise PcbReadError(f"{where}: a region record runs past the end")
        count += 1
    return count


BODY = 12
BODY_STORAGES = ("ComponentBodies6", "ShapeBasedComponentBodies6")
BODY_LAYERS = range(57, 73)


def _body(body: bytes, where: str, shape_based: bool = False) -> BodyRecord:
    """One body subrecord, decoded apart from the product reader: the prefix on a mechanical layer 1 to 16
    without a net and a polygon, five zero bytes, the text and the outline, with nothing after it."""
    if len(body) < 26:
        raise PcbReadError(f"{where}: a component body subrecord of {len(body)} bytes is too short")
    pre = _prefix(body)
    if pre.layer not in BODY_LAYERS or pre.net != NO_INDEX or pre.polygon != NO_INDEX:
        raise PcbReadError(f"{where}: a component body on layer {pre.layer}, or with a net or a polygon")
    if body[9:13] != b"\xff" * 4 or body[13:18] != bytes(5):
        raise PcbReadError(f"{where}: the bytes after the prefix of a component body are not the constants")
    (length,) = struct.unpack_from("<I", body, 18)
    raw = body[22 : 22 + length]
    if len(raw) != length or not raw.endswith(b"\0") or raw.startswith(b"|"):
        raise PcbReadError(f"{where}: the text of a component body is cut, open or starts with a bar")
    keys = [tuple(piece.split("=", 1)) for piece in raw[:-1].decode("ascii").split("|")]
    if any(len(pair) != 2 for pair in keys):
        raise PcbReadError(f"{where}: a piece of the text of a component body holds no '='")
    at = 22 + length
    (count,) = struct.unpack_from("<I", body, at)
    at += 4
    vertices: list[tuple[int, int]] = []
    closing: tuple[int, int] | None = None
    if shape_based:
        for number in range(count + 1):
            is_round, x, y, cx, cy, radius, a1, a2 = struct.unpack_from("<B5i2d", body, at)
            if is_round or (cx, cy, radius, a1, a2) != (0, 0, 0, 0.0, 0.0):
                raise PcbReadError(f"{where}: a vertex of a component body is round")
            at += 37
            if number < count:
                vertices.append((x, y))
            else:
                closing = (x, y)
        if closing != vertices[0]:
            raise PcbReadError(f"{where}: the last vertex of a shape-based body is not its first")
    else:
        for _ in range(count):
            fx, fy = struct.unpack_from("<2d", body, at)
            if not fx.is_integer() or not fy.is_integer():
                raise PcbReadError(f"{where}: a vertex of a component body is not a whole unit")
            vertices.append((int(fx), int(fy)))
            at += 16
    if at != len(body) or count < 3:
        raise PcbReadError(f"{where}: a component body of {count} vertices, or with bytes after its outline")
    return BodyRecord(pre, [(str(k), str(v)) for k, v in keys], vertices, closing, len(body))


def decode_bodies(data: bytes, where: str, shape_based: bool = False) -> list[BodyRecord]:
    """The component bodies of a body storage: each the type byte 12 and one subrecord."""
    out: list[BodyRecord] = []
    at = 0
    while at < len(data):
        if data[at] != BODY:
            raise PcbReadError(f"{where}: byte {at} does not open a component body")
        (body,), at = _subrecords(data, at + 1, 1, f"{where} record {len(out)}")
        out.append(_body(body, f"{where} record {len(out)}", shape_based))
    return out


def _text(subs: list[bytes], where: str) -> TextRecord:
    body, text = subs
    if len(body) < TEXT_MIN:
        raise PcbReadError(f"{where}: a text subrecord of {len(body)} bytes is shorter than 40")
    if not text or len(text) != 1 + text[0]:
        raise PcbReadError(f"{where}: the text subrecord of {len(text)} bytes is not 1 + its text")
    x, y, height = struct.unpack_from("<3i", body, 13)
    (font,) = struct.unpack_from("<H", body, 25)
    (rotation,) = struct.unpack_from("<d", body, 27)
    mirrored = body[35]
    (width,) = struct.unpack_from("<i", body, 36)
    record = TextRecord(
        _prefix(body), x, y, height, font, rotation, mirrored, width, len(body), text[1:].decode("iso-8859-1")
    )
    if len(body) >= TEXT_LONG:
        record.is_comment, record.is_designator = body[40], body[41]
        (record.wide_index,) = struct.unpack_from("<I", body, 115)
    return record


def _via(body: bytes, where: str) -> ViaRecord:
    """A via (``pcb-copper.md``, "Via"): the prefix on Multi-Layer, x, y, diameter, hole, start and end
    layer."""
    if len(body) < VIA_MIN:
        raise PcbReadError(f"{where}: a via subrecord of {len(body)} bytes, fewer than {VIA_MIN}")
    pre = _prefix(body)
    if pre.layer != MULTI_LAYER:
        raise PcbReadError(f"{where}: a via on layer {pre.layer}, not on Multi-Layer ({MULTI_LAYER})")
    x, y, diameter, hole = struct.unpack_from("<4i", body, 13)
    if not 0 <= hole < diameter:
        raise PcbReadError(f"{where}: a via hole of {hole} units is not below its diameter of {diameter}")
    return ViaRecord(pre, x, y, diameter, hole, body[29], body[30], len(body), bytes(body))


def decode_primitives(data: bytes, where: str = "Data") -> list[Primitive]:
    """The primitive records of ``data``, one after another, until fewer than 4 bytes remain."""
    out: list[Primitive] = []
    offset = 0
    while len(data) - offset >= 4:
        kind = data[offset]
        at = f"{where} record {len(out)}"
        if kind not in KNOWN_TYPES:
            raise PcbReadError(f"{at}: unknown record type {kind}")
        offset += 1
        if kind in (TRACK, ARC):
            (body,), offset = _subrecords(data, offset, 1, at)
            if len(body) < MINIMUMS[kind]:
                what = "a track" if kind == TRACK else "an arc"
                raise PcbReadError(
                    f"{at}: a {what} subrecord of {len(body)} bytes, fewer than {MINIMUMS[kind]}"
                )
            if kind == TRACK:
                x1, y1, x2, y2, width = struct.unpack_from("<5i", body, 13)
                out.append(Track(_prefix(body), x1, y1, x2, y2, width, len(body)))
            else:
                cx, cy, r = struct.unpack_from("<3i", body, 13)
                start, end = struct.unpack_from("<2d", body, 25)
                (width,) = struct.unpack_from("<i", body, 41)
                out.append(ArcRecord(_prefix(body), cx, cy, r, start, end, width, len(body)))
        elif kind == PAD:
            subs, offset = _subrecords(data, offset, 6, at)
            out.append(_pad(subs, at))
        elif kind == TEXT:
            subs, offset = _subrecords(data, offset, 2, at)
            out.append(_text(subs, at))
        elif kind == VIA:
            (body,), offset = _subrecords(data, offset, 1, at)
            out.append(_via(body, at))
        elif kind == BODY:  # change c0121: a body of a library footprint
            (body,), offset = _subrecords(data, offset, 1, at)
            out.append(_body(body, at))
        else:
            raise PcbReadError(f"{at}: record type {kind} is not written by Fenolite")
    if offset != len(data):
        raise PcbReadError(f"{where}: {len(data) - offset} bytes are left after the last record")
    return out


def _indexes(primitives: list[Primitive], nets: int, components: int, where: str) -> None:
    for number, item in enumerate(primitives):
        pre = item.prefix
        if pre.net != NO_INDEX and pre.net >= nets:
            raise PcbReadError(f"{where} record {number}: net {pre.net} of {nets}")
        if pre.component != NO_INDEX and pre.component >= components:
            raise PcbReadError(f"{where} record {number}: component {pre.component} of {components}")


def field_block_at(data: bytes, offset: int, where: str) -> tuple[list[tuple[str, str]], int]:
    """One property block of lines as its fields in order (keys may repeat) and the offset after it; the
    length is the low 24 bits of the length word. One CR stands between the lines, and every line after
    the first starts with ``RECORD=Board``."""
    (word,) = struct.unpack_from("<I", data, offset)
    length = word & 0xFFFFFF
    raw = data[offset + 4 : offset + 4 + length]
    if word >> 24 or len(raw) != length or not raw.endswith(b"\0"):
        raise PcbReadError(f"{where}: a property block is cut short or lacks its NUL")
    text = raw[:-1].decode("ascii")
    fields: list[tuple[str, str]] = []
    for number, line in enumerate(text.split("\r")):
        if not line.startswith("|" if number == 0 else "|RECORD=Board|"):
            raise PcbReadError(f"{where}: line {number} does not start with '|' or with RECORD=Board")
        for part in line[1:].split("|"):
            key, found, value = part.partition("=")
            if not found or not key or any(not 0x20 <= ord(ch) <= 0x7E for ch in part):
                raise PcbReadError(f"{where}: the field {part[:30]!r} is not printable KEY=VALUE")
            fields.append((key, value))
    return fields, offset + 4 + length


def _file_header(header: bytes) -> str:
    """The library's unique id from the 53-byte ``FileHeader``: the counted header text, the double 5.01
    and the counted id of eight upper-case letters."""
    text = LIBRARY_HEADER.encode("ascii")
    start = struct.pack("<IB", len(text), len(text)) + text
    if not header.startswith(start):
        raise PcbReadError("FileHeader does not start with the library header text")
    rest = header[len(start) :]
    if len(rest) != 8 + 4 + 1 + 8:
        raise PcbReadError(f"FileHeader holds {len(header)} bytes, not 53")
    (version,) = struct.unpack_from("<d", rest, 0)
    if version != LIBRARY_VERSION:
        raise PcbReadError(f"FileHeader: the version is {version}, not {LIBRARY_VERSION}")
    length, short = struct.unpack_from("<IB", rest, 8)
    unique_id = rest[13:].decode("ascii")
    if length != 8 or short != 8 or not (unique_id.isalpha() and unique_id.isupper()):
        raise PcbReadError("FileHeader: the unique id is not eight upper-case letters")
    return unique_id


def _params_toc(data: bytes) -> list[dict[str, str]]:
    """The rows of ``ComponentParamsTOC/Data``: one block of CR LF lines of ``Key=value`` joined by ``|``."""
    (length,) = struct.unpack_from("<I", data, 0)
    raw = data[4:]
    if len(raw) != length or not raw.endswith(b"\0"):
        raise PcbReadError("ComponentParamsTOC/Data: the block is cut short or lacks its NUL")
    text = raw[:-1].decode("ascii")
    if text and not text.endswith("\r\n"):
        raise PcbReadError("ComponentParamsTOC/Data: the last line has no CR LF")
    rows: list[dict[str, str]] = []
    for line in text.split("\r\n")[:-1]:
        row = dict(part.partition("=")[::2] for part in line.split("|"))
        if list(row) != ["Name", "Pad Count", "Height", "Description"]:
            raise PcbReadError(f"ComponentParamsTOC/Data: the line {line[:40]!r} lacks its four keys")
        rows.append(row)
    return rows


def read_pcblib(data: bytes) -> PcbLib:
    """A PCB library (``pcb-library.md``)."""
    compound = parse_compound(data)
    streams = compound.streams
    for path in LIBRARY_STREAMS:
        if path not in streams:
            raise PcbReadError(f"the library has no stream {path}")
    unique_id = _file_header(streams["FileHeader"])
    if u32(streams["Library/Header"], "Library/Header") != 1:
        raise PcbReadError("Library/Header is not 1")
    for storage in ("Models", "ModelsNoEmbed", "Textures", "PadViaLibrary"):
        if u32(streams[f"Library/{storage}/Header"], f"Library/{storage}/Header") != 0:
            raise PcbReadError(f"Library/{storage}/Header is not 0")
    if u32(streams["Library/EmbeddedFonts"], "Library/EmbeddedFonts") != 0:
        raise PcbReadError("Library/EmbeddedFonts is not 0")
    if u32(streams["Library/ComponentParamsTOC/Header"], "Library/ComponentParamsTOC/Header") != 1:
        raise PcbReadError("Library/ComponentParamsTOC/Header is not 1")
    (pad_via,) = property_blocks(streams["Library/PadViaLibrary/Data"], "Library/PadViaLibrary/Data")
    if set(pad_via) != {"PADVIALIBRARY.LIBRARYID", "PADVIALIBRARY.LIBRARYNAME", "PADVIALIBRARY.DISPLAYUNITS"}:
        raise PcbReadError("Library/PadViaLibrary/Data does not hold its three keys")
    library = streams["Library/Data"]
    board, offset = field_block_at(library, 0, "Library/Data")
    fields: dict[str, str] = {}
    for key, value in board:
        fields.setdefault(key, value)
    for key, value in (("KIND", LIBRARY_KIND), ("VERSION", "3.00"), ("V9_MASTERSTACK_STYLE", "0")):
        if fields.get(key) != value:
            raise PcbReadError(f"Library/Data: the board record does not hold {key}={value}")
    if "HEADER" in fields or "WEIGHT" in fields:
        raise PcbReadError("Library/Data: the board record holds HEADER or WEIGHT")
    (names_count,) = struct.unpack_from("<I", library, offset)
    offset += 4
    names: list[str] = []
    for _ in range(names_count):
        name, offset = string_block_at(library, offset, "Library/Data")
        names.append(name)
    if offset != len(library):
        raise PcbReadError("Library/Data: bytes are left after the name list")
    section_keys: dict[str, str] = {}
    if "SectionKeys" in streams:
        keys = streams["SectionKeys"]
        (key_count,) = struct.unpack_from("<i", keys, 0)
        at = 4
        for _ in range(key_count):
            (length,) = struct.unpack_from("<I", keys, at)
            raw = keys[at + 4 : at + 4 + length]
            if not raw.endswith(b"\0"):
                raise PcbReadError("SectionKeys: a full name does not end with its NUL")
            storage, at = string_block_at(keys, at + 4 + length, "SectionKeys")
            section_keys[raw[:-1].decode("ascii")] = storage
        if at != len(keys):
            raise PcbReadError("SectionKeys: bytes are left after the entries")
    toc = _params_toc(streams["Library/ComponentParamsTOC/Data"])
    if [row["Name"] for row in toc] != names:
        raise PcbReadError("Library/ComponentParamsTOC/Data does not list the names of Library/Data")
    footprints: dict[str, Footprint] = {}
    roots = {path.split("/")[0] for path in streams if "/" in path} - {"Library"}
    for storage in sorted(roots):
        if f"{storage}/Parameters" not in streams:
            continue
        (parameters,) = property_blocks(streams[f"{storage}/Parameters"], f"{storage}/Parameters")
        pattern = parameters.get("PATTERN")
        if not pattern:
            raise PcbReadError(f"{storage}/Parameters holds no PATTERN")
        body = streams.get(f"{storage}/Data")
        if body is None:
            raise PcbReadError(f"footprint {pattern} has no Data")
        name, offset = string_block_at(body, 0, f"{storage}/Data")
        primitives = decode_primitives(body[offset:], f"{storage}/Data")
        _indexes(primitives, 0, 0, f"{storage}/Data")
        header_count = u32(streams[f"{storage}/Header"], f"{storage}/Header")
        if header_count != len(primitives):
            raise PcbReadError(
                f"{storage}/Header says {header_count}, Data holds {len(primitives)} primitives"
            )
        if f"{storage}/{UNIQUE_STORAGE}" not in compound.storages:
            raise PcbReadError(f"{storage} has no storage spelled {UNIQUE_STORAGE}")
        uid_count = u32(streams[f"{storage}/{UNIQUE_STORAGE}/Header"], storage)
        uids = property_blocks(streams[f"{storage}/{UNIQUE_STORAGE}/Data"], storage)
        if uid_count != len(uids):
            raise PcbReadError(f"{storage}/{UNIQUE_STORAGE}: Header {uid_count}, {len(uids)} blocks")
        if list(parameters)[:5] != list(PARAMETER_KEYS):
            raise PcbReadError(f"{storage}/Parameters does not start with {', '.join(PARAMETER_KEYS)}")
        wide = property_blocks(streams[f"{storage}/WideStrings"], f"{storage}/WideStrings")
        footprints[pattern] = Footprint(storage, name, parameters, primitives, header_count, uids, wide)
    for name in names:
        if name not in footprints:
            raise PcbReadError(f"Library/Data names {name!r}, which no Parameters stream holds as PATTERN")
    for row in toc:
        pads = sum(isinstance(p, PadRecord) for p in footprints[row["Name"]].primitives)
        if row.get("Pad Count") != str(pads):
            raise PcbReadError(
                f"ComponentParamsTOC: {row['Name']} has {pads} pads, not {row.get('Pad Count')}"
            )
    return PcbLib(
        names, fields, footprints, section_keys, dict(streams), list(compound.storages), board, unique_id, toc
    )


OPTION_BLOCKS: dict[str, tuple[int, str]] = {
    "Advanced Placer Options6": (1, "AdvancedPlacerOptions"),
    "Pin Swap Options6": (1, "PinSwapOptions"),
    "Design Rule Checker Options6": (1, "DesignRuleCheckerOptions"),
    "PadViaLibrary": (0, ""),
    "PadViaLibraryCache": (0, ""),
    "SignalClasses": (1, ""),
}
"""Storage → its ``Header`` value and the ``RECORD`` of its one property block (empty for none)."""
WIDE_STORAGES = ("LayerKindMapping", "ConstraintManager")
"""Storages with ``Header`` 1 whose ``Data`` starts with a wide string."""


def _wide_strings(data: bytes) -> dict[int, str]:
    out: dict[int, str] = {}
    offset = 0
    while offset < len(data):
        index, length = struct.unpack_from("<2I", data, offset)
        raw = data[offset + 8 : offset + 8 + length]
        if len(raw) != length or not raw.endswith(b"\0\0") or length % 2:
            raise PcbReadError(f"WideStrings6: entry {index} is cut or has no 2-byte NUL")
        out[index] = raw[:-2].decode("utf-16-le")
        offset += 8 + length
    return out


TOP_LAYER, BOTTOM_LAYER, FIRST_PLANE, LAST_PLANE = 1, 32, 39, 54
SIGNAL_GROUP, PLANE_GROUP, BOTTOM_LONG = 0x0100_0000, 0x0101_0000, 0x0100_FFFF
NO_NET = "(No Net)"


def copper_chain(board: dict[str, str]) -> list[int]:
    """The copper stack of the numbered keys (``pcb-copper.md``, "Layer stack"): ``NEXT`` followed from
    layer 1 must reach layer 32, each layer naming the one before it as ``PREV``; and the ``V9_STACK`` list
    must hold the same copper layers in that order. Empty for a board record without ``LAYER1NEXT``."""
    if "LAYER1NEXT" not in board:
        return []
    chain = [TOP_LAYER]
    while True:
        following = int(board.get(f"LAYER{chain[-1]}NEXT", "0"))
        if following == 0:
            break
        if following in chain or f"LAYER{following}PREV" not in board:
            raise PcbReadError(
                f"Board6: the copper chain {chain} goes on to layer {following}, which cannot follow"
            )
        if int(board[f"LAYER{following}PREV"]) != chain[-1]:
            raise PcbReadError(
                f"Board6: LAYER{following}PREV does not name layer {chain[-1]} of the copper chain"
            )
        chain.append(following)
    if chain[-1] != BOTTOM_LAYER:
        raise PcbReadError(f"Board6: the copper chain {chain} from layer 1 does not end at layer 32")
    listed: list[int] = []
    index = 0
    while f"V9_STACK_LAYER{index}_LAYERID" in board:
        long = int(board[f"V9_STACK_LAYER{index}_LAYERID"])
        if long == BOTTOM_LONG:
            listed.append(BOTTOM_LAYER)
        elif long & 0xFFFF_0000 == SIGNAL_GROUP:
            listed.append(long & 0xFFFF)
        elif long & 0xFFFF_0000 == PLANE_GROUP:
            listed.append(FIRST_PLANE - 1 + (long & 0xFFFF))
        index += 1
    if index and listed != chain:
        raise PcbReadError(
            f"Board6: the V9_STACK list holds the copper layers {listed}, the chain is {chain}"
        )
    return chain


def chain_planes(board: dict[str, str], chain: list[int], nets: list[dict[str, str]]) -> dict[int, str]:
    """Plane number → net name for the planes of ``chain``; each must have a ``PLANE<k>NETNAME`` that
    names a record of ``Nets6``."""
    names = {net.get("NAME") for net in nets}
    out: dict[int, str] = {}
    for layer in chain:
        if FIRST_PLANE <= layer <= LAST_PLANE:
            number = layer - FIRST_PLANE + 1
            name = board.get(f"PLANE{number}NETNAME", NO_NET)
            if name not in names:
                raise PcbReadError(
                    f"Board6: Internal Plane {number} is in the copper chain and PLANE{number}NETNAME={name} "
                    "names no net of Nets6"
                )
            out[number] = name
    return out


def decode_name(codes: str) -> str:
    """A polygon's ``NAME``: character codes in decimal, joined by commas."""
    return "".join(chr(int(code)) for code in codes.split(",")) if codes else ""


def read_polygons(data: bytes, nets: int) -> list[PolygonRecord]:
    """The polygon pours of ``Polygons6/Data`` (``pcb-copper.md``, "Polygon pour"): each closed (the first
    vertex repeated last), with a pour index that no other polygon has, a net index that names a net, and
    a layer that is not a plane."""
    out: list[PolygonRecord] = []
    seen: set[int] = set()
    for number, block in enumerate(property_blocks(data, "Polygons6/Data")):
        where = f"Polygons6 record {number}"
        vertices: list[tuple[str, str]] = []
        while f"VX{len(vertices)}" in block:
            vertices.append((block[f"VX{len(vertices)}"], block[f"VY{len(vertices)}"]))
        if len(vertices) < 4 or vertices[0] != vertices[-1]:
            raise PcbReadError(f"{where}: the polygon is not closed: its first and last vertex differ")
        net = int(block["NET"]) if "NET" in block else None
        if net is not None and not 0 <= net < nets:
            raise PcbReadError(f"{where}: net {net} of {nets}")
        index = int(block.get("POURINDEX", "-1"))
        if index in seen:
            raise PcbReadError(f"{where}: the pour index {index} is used by another polygon")
        seen.add(index)
        layer = block.get("LAYER", "")
        if layer.startswith("PLANE"):
            raise PcbReadError(f"{where}: a polygon on {layer}, a plane")
        out.append(PolygonRecord(layer, net, decode_name(block.get("NAME", "")), index, vertices, block))
    return out


def read_classes(
    data: bytes, nets: list[dict[str, str]], components: list[dict[str, str]] | None = None
) -> list[ClassRecord]:
    """The classes of ``Classes6/Data`` (``pcb-copper.md``, "Net classes"): the members ``M0``, ``M1`` … of
    a net class (``KIND=0``) must name nets of ``Nets6``, and those of a component class (``KIND=1``) must
    be the ``SOURCEDESIGNATOR`` of records of ``Components6`` (change c0048; checked when ``components`` is
    given)."""
    names = {net.get("NAME") for net in nets}
    refs = None if components is None else {c.get("SOURCEDESIGNATOR") for c in components}
    out: list[ClassRecord] = []
    for number, block in enumerate(property_blocks(data, "Classes6/Data")):
        members: list[str] = []
        while f"M{len(members)}" in block:
            members.append(block[f"M{len(members)}"])
        kind = block.get("KIND", "")
        if kind == "0":
            for member in members:
                if member not in names:
                    raise PcbReadError(f"Classes6 record {number}: the member {member} names no net of Nets6")
        if kind == "1" and refs is not None:
            for member in members:
                if member not in refs:
                    raise PcbReadError(
                        f"Classes6 record {number}: the member {member} names no component of Components6"
                    )
        out.append(ClassRecord(block.get("NAME", ""), kind, members, block))
    return out


def read_rules(data: bytes) -> list[RuleRecord]:
    """The rules of ``Rules6/Data`` (``pcb-copper.md``, "Rules"): a 16-bit rule-kind number, then one
    property block whose ``RULEKIND`` must be the kind of that number."""
    out: list[RuleRecord] = []
    offset = 0
    while offset < len(data):
        where = f"Rules6 record {len(out)}"
        if offset + 2 > len(data):
            raise PcbReadError(f"{where}: the rule-kind number is cut")
        (kind,) = struct.unpack_from("<H", data, offset)
        block, offset = property_block_at(data, offset + 2, "Rules6/Data")
        wanted = RULE_KINDS.get(kind)
        if wanted is None or block.get("RULEKIND") != wanted:
            raise PcbReadError(
                f"{where}: the rule starts with the number {kind} and its RULEKIND is {block.get('RULEKIND')}"
            )
        out.append(
            RuleRecord(
                kind,
                block.get("NAME", ""),
                int(block.get("PRIORITY", "0")),
                block.get("SCOPE1EXPRESSION", ""),
                block,
            )
        )
    return out


def _nothing_on_planes(primitives: list[Primitive], where: str) -> None:
    for number, item in enumerate(primitives):
        if FIRST_PLANE <= item.prefix.layer <= LAST_PLANE:
            raise PcbReadError(f"{where} record {number}: a primitive on layer {item.prefix.layer}, a plane")


def read_pcbdoc(data: bytes) -> PcbDoc:
    """A PCB document (``pcb-document.md``; the copper of ``pcb-copper.md``)."""
    compound = parse_compound(data)
    streams = compound.streams
    storages: dict[str, tuple[int, bytes]] = {}
    for path in compound.storages:
        header, body = streams.get(f"{path}/Header"), streams.get(f"{path}/Data")
        if header is None or body is None:
            raise PcbReadError(f"storage {path} lacks Header or Data")
        storages[path] = (u32(header, f"{path}/Header"), body)
    for name in ("FileHeader", "FileHeaderSix"):
        if name not in streams:
            raise PcbReadError(f"the document has no stream {name}")
    six = streams["FileHeaderSix"]
    start = struct.pack("<IB", 19, 19) + b"PCB 6.0 Binary File" + struct.pack("<d", LIBRARY_VERSION)
    unique = six[len(start) + 5 :].decode("ascii")
    if not six.startswith(start) or six[len(start) : len(start) + 5] != struct.pack("<IB", 38, 38):
        raise PcbReadError("FileHeaderSix is not the header text, the double 5.01 and a 38-character id")
    if not re.fullmatch(r"\{[0-9A-F]{8}(-[0-9A-F]{4}){3}-[0-9A-F]{12}\}", unique):
        raise PcbReadError("FileHeaderSix: the id is not a GUID in braces and upper case")
    if "Board6" not in storages:
        raise PcbReadError("the document has no Board6")
    board_data = storages["Board6"][1]
    if len(board_data) < 6:
        raise PcbReadError("Board6/Data holds 0 records, not one non-empty record")
    board_fields, end = field_block_at(board_data, 0, "Board6/Data")
    if end != len(board_data):
        raise PcbReadError("Board6/Data holds more than one record")
    board: dict[str, str] = {}
    for key, value in board_fields:
        board.setdefault(key, value)
    nets = property_blocks(storages.get("Nets6", (0, b""))[1], "Nets6/Data")
    components = property_blocks(storages.get("Components6", (0, b""))[1], "Components6/Data")
    decoded: dict[str, list[Primitive]] = {}
    for kind in ("Pads6", "Tracks6", "Arcs6", "Texts6", "Vias6"):
        decoded[kind] = decode_primitives(storages.get(kind, (0, b""))[1], f"{kind}/Data")
        _indexes(decoded[kind], len(nets), len(components), kind)
    chain = copper_chain(board)
    planes = chain_planes(board, chain, nets)
    for kind in ("Tracks6", "Arcs6"):
        _nothing_on_planes(decoded[kind], kind)
    polygons = read_polygons(storages.get("Polygons6", (0, b""))[1], len(nets))
    classes = read_classes(storages.get("Classes6", (0, b""))[1], nets, components)
    rules = read_rules(storages.get("Rules6", (0, b""))[1])
    counts = {
        "Board6": 1,
        "Nets6": len(nets),
        "Components6": len(components),
        **{kind: len(items) for kind, items in decoded.items()},
    }
    wide = _wide_strings(storages.get("WideStrings6", (0, b""))[1])
    counts["WideStrings6"] = len(wide)
    counts["Polygons6"] = len(polygons)
    counts["Classes6"] = len(classes)
    counts["Rules6"] = len(rules)
    for kind in REGION_STORAGES:  # change c0085: filled graphics and keep-outs
        if storages.get(kind, (0, b""))[1]:
            counts[kind] = count_regions(storages[kind][1], f"{kind}/Data")
    if counts.get(REGION_STORAGES[0], 0) != counts.get(REGION_STORAGES[1], 0):
        raise PcbReadError("Regions6 and ShapeBasedRegions6 hold different numbers of records")
    bodies: list[list[BodyRecord]] = []
    for kind, shape_based in zip(BODY_STORAGES, (False, True), strict=True):  # change c0121
        found = decode_bodies(storages.get(kind, (0, b""))[1], f"{kind}/Data", shape_based)
        bodies.append(found)
        if found:
            counts[kind] = len(found)
    if [(b.prefix, b.keys, b.vertices) for b in bodies[0]] != [
        (b.prefix, b.keys, b.vertices) for b in bodies[1]
    ]:
        raise PcbReadError("the two body storages do not hold the same bodies in the same order")
    if any(b.prefix.component == NO_INDEX or b.prefix.component >= len(components) for b in bodies[0]):
        raise PcbReadError("a component body of the document names no component")
    unique_ids = property_blocks(storages.get(UNIQUE_STORAGE, (0, b""))[1], f"{UNIQUE_STORAGE}/Data")
    if UNIQUE_STORAGE in storages:
        counts[UNIQUE_STORAGE] = len(unique_ids)
        wanted = [(str(index), "Pad") for index in range(len(decoded["Pads6"]))]
        if [(u.get("PRIMITIVEINDEX"), u.get("PRIMITIVEOBJECTID")) for u in unique_ids] != wanted:
            raise PcbReadError(f"{UNIQUE_STORAGE}/Data does not list every pad once, in order")
    options: dict[str, dict[str, str]] = {}
    for name, (header, record) in OPTION_BLOCKS.items():
        if name in storages:
            blocks = property_blocks(storages[name][1], f"{name}/Data")
            if len(blocks) != 1 or (record and blocks[0].get("RECORD") != record):
                raise PcbReadError(f"{name}/Data is not one property block of {record or 'its keys'}")
            options[name] = blocks[0]
            counts[name] = header
    for name in WIDE_STORAGES:
        if name in storages:
            body = storages[name][1]
            length = u32(body[:4], f"{name}/Data")
            text = body[4 : 4 + length]
            if length % 2 or len(text) != length or not text.endswith(b"\0\0"):
                raise PcbReadError(f"{name}/Data does not start with a wide string")
            if name == "LayerKindMapping" and (
                text[:-2].decode("utf-16-le") != "1.0" or body[4 + length :] != bytes(8)
            ):
                raise PcbReadError("LayerKindMapping/Data is not the version 1.0 and an empty table")
            if name == "ConstraintManager" and len(body) != 4 + length:
                raise PcbReadError("ConstraintManager/Data holds bytes after its wide string")
            counts[name] = 1
    for path, (header, body) in storages.items():
        expected = counts.get(path, 0 if not body else None)
        if expected is None:
            raise PcbReadError(f"{path}: a storage Fenolite does not write holds data")
        if header != expected:
            raise PcbReadError(f"{path}/Header says {header}, the data holds {expected} records")
    return PcbDoc(
        file_header=streams["FileHeader"],
        file_header_six=streams["FileHeaderSix"],
        board=board,
        nets=nets,
        components=components,
        pads=[p for p in decoded["Pads6"] if isinstance(p, PadRecord)],
        tracks=[t for t in decoded["Tracks6"] if isinstance(t, Track)],
        arcs=[a for a in decoded["Arcs6"] if isinstance(a, ArcRecord)],
        texts=[t for t in decoded["Texts6"] if isinstance(t, TextRecord)],
        wide_strings=wide,
        storages=storages,
        streams=dict(streams),
        board_fields=board_fields,
        unique_ids=unique_ids,
        options=options,
        vias=[v for v in decoded["Vias6"] if isinstance(v, ViaRecord)],
        polygons=polygons,
        classes=classes,
        rules=rules,
        copper_chain=chain,
        plane_nets=planes,
        bodies=bodies[0],
    )
