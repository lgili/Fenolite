# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Binary primitives of Altium PCB files, kept byte for byte (``docs/formats/altium/pcb-read.md``,
"Record lengths" and "Fields"; change c0041).

A primitive is a type byte and a fixed number of subrecords, each a 32-bit length and its bytes. A
subrecord at or above its minimum is typed; a field past its end is ``None``; the bytes after the last
field the reader knows are the record's ``tail``. Every record keeps ``raw``, so the records of a stream,
joined, give the stream back.
"""

# evidence: see read.pcb, read.pcblib

from __future__ import annotations

import struct
from dataclasses import dataclass, fields, is_dataclass
from fractions import Fraction

from fenolite.backends.altium.read.pcbprops import (
    CODEC,
    PCB_READ_ISSUE_CODES,
    PropertyRecord,
    issue,
    parse_text,
)
from fenolite.core.errors import FormatError, Issue
from fenolite.core.evidence import Level
from fenolite.core.units import u_to_nm

ARC, PAD, VIA, TRACK, TEXT, FILL, REGION, BODY = 1, 2, 3, 4, 5, 6, 11, 12
SUBRECORDS: dict[int, int] = {ARC: 1, PAD: 6, VIA: 1, TRACK: 1, TEXT: 2, FILL: 1, REGION: 1, BODY: 1}
"""Record type → its number of subrecords."""
MINIMUMS: dict[str, int] = {
    "track": 33,
    "arc": 45,
    "via": 31,
    "fill": 37,
    "text": 40,
    "pad": 110,
    "pad-layers": 596,
    "region": 26,
}
"""The shortest subrecord the reader types (the pad's sixth subrecord may also be empty)."""
NO_INDEX = 0xFFFF
TEXT_LONG = 123
PAD_HOLE_ROTATION = 114
PLAIN_VERTEX = 16
SHAPE_VERTEX = 37


class PcbReadError(FormatError):
    """A PCB file the reader cannot read, or the first error of a strict read."""


def to_nm_exact(units: int) -> Fraction:
    """Units of 1/10 000 mil → nanometres, exactly (``units · 127 / 50``)."""
    return Fraction(units * 127, 50)


def to_nm(units: int) -> int:
    """Units of 1/10 000 mil → nanometres rounded half to even (``fenolite.core.units.u_to_nm``)."""
    return u_to_nm(units)


def error_of(found: Issue, *, file: str = "") -> PcbReadError:
    """The exception a strict read raises for ``found``: ``where`` split into locator and offset."""
    locator, _, rest = found.where.partition("#")
    offset: int | None = None
    if "@" in locator:
        locator, _, at = locator.partition("@")
        offset = int(at)
    elif "@" in rest:
        offset = int(rest.partition("@")[2])
    return PcbReadError(f"{found.code}: {found.message}", file=file, locator=locator, offset=offset)


# --- records -----------------------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class Prefix:
    """The first 13 bytes of the geometry subrecord; ``None`` for an index of ``0xFFFF``."""

    layer: int
    flags1: int
    flags2: int
    net: int | None
    polygon: int | None
    component: int | None
    locked: bool


@dataclass(frozen=True, slots=True)
class RawPrimitive:
    """A primitive the reader does not type: a component body, or a record shorter than its minimum."""

    type: int
    subrecords: tuple[bytes, ...]
    raw: bytes


@dataclass(frozen=True, slots=True)
class TrackRecord:
    raw: bytes
    prefix: Prefix
    x1: int
    y1: int
    x2: int
    y2: int
    width: int
    sub_polygon: int | None
    tail: bytes


@dataclass(frozen=True, slots=True)
class ArcRecord:
    raw: bytes
    prefix: Prefix
    cx: int
    cy: int
    radius: int
    start_angle: float
    end_angle: float
    width: int
    sub_polygon: int | None
    tail: bytes


@dataclass(frozen=True, slots=True)
class ViaRecord:
    raw: bytes
    prefix: Prefix
    x: int
    y: int
    diameter: int
    hole: int
    start_layer: int
    end_layer: int
    tented_top: bool
    tented_bottom: bool
    tail: bytes


@dataclass(frozen=True, slots=True)
class FillRecord:
    raw: bytes
    prefix: Prefix
    x1: int
    y1: int
    x2: int
    y2: int
    rotation: float
    tail: bytes


@dataclass(frozen=True, slots=True)
class PadRecord:
    """A pad; the fields of the sixth subrecord are ``None`` when it is empty. ``tail`` holds the bytes of
    the fifth subrecord after offset 114 and of the sixth after offset 596."""

    raw: bytes
    name: str
    prefix: Prefix
    x: int
    y: int
    size_top: tuple[int, int]
    size_mid: tuple[int, int]
    size_bottom: tuple[int, int]
    hole: int
    shape_top: int
    shape_mid: int
    shape_bottom: int
    rotation: float
    plated: bool
    stack_mode: int
    paste_expansion: int
    solder_expansion: int
    paste_mode: int
    solder_mode: int
    hole_rotation: float | None
    inner_sizes: tuple[tuple[int, int], ...] | None
    inner_shapes: tuple[int, ...] | None
    hole_shape: int | None
    slot_length: int | None
    slot_rotation: float | None
    hole_offsets: tuple[tuple[int, int], ...] | None
    alternate_shapes: tuple[int, ...] | None
    corner_percentages: tuple[int, ...] | None
    tail: tuple[bytes, bytes]


@dataclass(frozen=True, slots=True)
class TextRecord:
    """A text; the long-form fields are ``None`` below 123 bytes. ``text`` is the shown string: the wide
    string at ``wide_index`` once a document or footprint resolved it, else ``short_text``."""

    raw: bytes
    prefix: Prefix
    x: int
    y: int
    height: int
    stroke_font: int
    rotation: float
    mirrored: bool
    stroke_width: int
    is_comment: bool | None
    is_designator: bool | None
    font_type: int | None
    bold: bool | None
    italic: bool | None
    font_name: str | None
    inverted: bool | None
    margin: int | None
    wide_index: int | None
    short_text: str
    text: str
    tail: bytes


@dataclass(frozen=True, slots=True)
class RegionVertex:
    """A region vertex as stored: doubles ``x``, ``y`` in the plain form; in the shape-based form integer
    positions, a round flag, a centre, a radius and two angles."""

    x: float | int
    y: float | int
    is_round: bool | None = None
    cx: int | None = None
    cy: int | None = None
    radius: int | None = None
    start_angle: float | None = None
    end_angle: float | None = None


@dataclass(frozen=True, slots=True)
class RegionRecord:
    """A region; ``closing`` is the extra outline vertex that the shape-based form stores."""

    raw: bytes
    prefix: Prefix
    hole_count: int
    properties: PropertyRecord
    outline: tuple[RegionVertex, ...]
    holes: tuple[tuple[RegionVertex, ...], ...]
    closing: RegionVertex | None
    shape_based: bool
    tail: bytes


Primitive = (
    TrackRecord | ArcRecord | ViaRecord | FillRecord | PadRecord | TextRecord | RegionRecord | RawPrimitive
)
TYPE_OF: dict[type, int] = {
    TrackRecord: TRACK,
    ArcRecord: ARC,
    ViaRecord: VIA,
    FillRecord: FILL,
    PadRecord: PAD,
    TextRecord: TEXT,
    RegionRecord: REGION,
}


def primitive_type(item: Primitive) -> int:
    """The record type byte of ``item``."""
    return item.type if isinstance(item, RawPrimitive) else TYPE_OF[type(item)]


# --- decoding ----------------------------------------------------------------------------------------


def _prefix(body: bytes) -> Prefix:
    layer, flags1, flags2, net, polygon, component = struct.unpack_from("<BBBHHH", body, 0)
    return Prefix(
        layer,
        flags1,
        flags2,
        None if net == NO_INDEX else net,
        None if polygon == NO_INDEX else polygon,
        None if component == NO_INDEX else component,
        not flags1 & 0x04,
    )


def _short(kind: str, length: int, where: str) -> Issue:
    return issue(
        "altium.pcb-read.short-record",
        f"a {kind} subrecord of {length} bytes is shorter than the reader's minimum; kept raw",
        where,
    )


def _track(body: bytes, raw: bytes) -> TrackRecord:
    x1, y1, x2, y2, width = struct.unpack_from("<5i", body, 13)
    long = len(body) >= 35
    sub = struct.unpack_from("<H", body, 33)[0] if long else None
    return TrackRecord(raw, _prefix(body), x1, y1, x2, y2, width, sub, body[36:] if long else body[33:])


def _arc(body: bytes, raw: bytes) -> ArcRecord:
    cx, cy, radius = struct.unpack_from("<3i", body, 13)
    start, end = struct.unpack_from("<2d", body, 25)
    (width,) = struct.unpack_from("<i", body, 41)
    long = len(body) >= 47
    sub = struct.unpack_from("<H", body, 45)[0] if long else None
    return ArcRecord(
        raw, _prefix(body), cx, cy, radius, start, end, width, sub, body[47:] if long else body[45:]
    )


def _via(body: bytes, raw: bytes) -> ViaRecord:
    pre = _prefix(body)
    x, y, diameter, hole = struct.unpack_from("<4i", body, 13)
    return ViaRecord(
        raw, pre, x, y, diameter, hole, body[29], body[30], bool(pre.flags1 & 0x20), bool(pre.flags1 & 0x40),
        body[31:],
    )  # fmt: skip


VIA_PAD_TABLE = (209, 32)
"""Where a via subrecord of at least ``VIA_PAD_TABLE_FROM`` bytes holds one byte per layer id from 1: the
offset and the number of bytes (``docs/formats/altium/pcb-copper.md``, "Via"; ``H-A-IMP-VIA-PADLESS``)."""
VIA_PAD_TABLE_FROM = 321
"""The shortest via subrecord in which the rows of the facts page place that table."""


def via_pad_removed(record: ViaRecord) -> tuple[int, ...]:
    """The layer ids on which the via record says that the via has no pad shape, in ascending order
    (change c0132): the ids whose byte in the table of ``VIA_PAD_TABLE`` is not zero. Empty for a
    subrecord shorter than ``VIA_PAD_TABLE_FROM`` bytes. The meaning is ``INFERRED``
    (``H-A-IMP-VIA-PADLESS``): Altium's "Remove Unused Pad Shapes" takes the pad shape of a via off the
    layers on which nothing touches it, and a polygon then keeps its clearance to the hole. Read from
    ``record.tail``, the bytes of the subrecord from offset 31."""
    offset, count = VIA_PAD_TABLE
    tail = record.tail
    if len(tail) + 31 < VIA_PAD_TABLE_FROM:
        return ()
    return tuple(index + 1 for index, value in enumerate(tail[offset - 31 : offset - 31 + count]) if value)


def _fill(body: bytes, raw: bytes) -> FillRecord:
    x1, y1, x2, y2 = struct.unpack_from("<4i", body, 13)
    (rotation,) = struct.unpack_from("<d", body, 29)
    return FillRecord(raw, _prefix(body), x1, y1, x2, y2, rotation, body[37:])


def _string(sub: bytes) -> str:
    """One length byte and the 8-bit characters."""
    return sub[1 : 1 + sub[0]].decode(CODEC) if sub else ""


def _pairs(data: bytes, xs: int, ys: int, count: int) -> tuple[tuple[int, int], ...]:
    return tuple(
        zip(
            struct.unpack_from(f"<{count}i", data, xs),
            struct.unpack_from(f"<{count}i", data, ys),
            strict=True,
        )
    )


def _pad(subs: list[bytes], raw: bytes) -> PadRecord:
    name, geo, layers = subs[0], subs[4], subs[5]
    x, y, tx, ty, mx, my, bx, by, hole = struct.unpack_from("<9i", geo, 13)
    (rotation,) = struct.unpack_from("<d", geo, 52)
    paste, solder = struct.unpack_from("<2i", geo, 86)
    hole_rotation = struct.unpack_from("<d", geo, 106)[0] if len(geo) >= PAD_HOLE_ROTATION else None
    full = len(layers) >= MINIMUMS["pad-layers"]
    return PadRecord(
        raw=raw,
        name=_string(name),
        prefix=_prefix(geo),
        x=x,
        y=y,
        size_top=(tx, ty),
        size_mid=(mx, my),
        size_bottom=(bx, by),
        hole=hole,
        shape_top=geo[49],
        shape_mid=geo[50],
        shape_bottom=geo[51],
        rotation=rotation,
        plated=bool(geo[60]),
        stack_mode=geo[62],
        paste_expansion=paste,
        solder_expansion=solder,
        paste_mode=geo[101],
        solder_mode=geo[102],
        hole_rotation=hole_rotation,
        inner_sizes=_pairs(layers, 0, 116, 29) if full else None,
        inner_shapes=tuple(layers[232:261]) if full else None,
        hole_shape=layers[262] if full else None,
        slot_length=struct.unpack_from("<i", layers, 263)[0] if full else None,
        slot_rotation=struct.unpack_from("<d", layers, 267)[0] if full else None,
        hole_offsets=_pairs(layers, 275, 403, 32) if full else None,
        alternate_shapes=tuple(layers[532:564]) if full else None,
        corner_percentages=tuple(layers[564:596]) if full else None,
        tail=(geo[PAD_HOLE_ROTATION:], layers[MINIMUMS["pad-layers"] :]),
    )


def _font_name(data: bytes) -> str:
    return data.decode("utf-16-le", errors="replace").split("\0", 1)[0]


def _text(subs: list[bytes], raw: bytes) -> TextRecord:
    body, string = subs
    x, y, height = struct.unpack_from("<3i", body, 13)
    (stroke_font,) = struct.unpack_from("<H", body, 25)
    (rotation,) = struct.unpack_from("<d", body, 27)
    (stroke_width,) = struct.unpack_from("<i", body, 36)
    long = len(body) >= TEXT_LONG
    short = _string(string)
    return TextRecord(
        raw=raw,
        prefix=_prefix(body),
        x=x,
        y=y,
        height=height,
        stroke_font=stroke_font,
        rotation=rotation,
        mirrored=bool(body[35]),
        stroke_width=stroke_width,
        is_comment=bool(body[40]) if long else None,
        is_designator=bool(body[41]) if long else None,
        font_type=body[43] if long else None,
        bold=bool(body[44]) if long else None,
        italic=bool(body[45]) if long else None,
        font_name=_font_name(body[46:110]) if long else None,
        inverted=bool(body[110]) if long else None,
        margin=struct.unpack_from("<i", body, 111)[0] if long else None,
        wide_index=struct.unpack_from("<I", body, 115)[0] if long else None,
        short_text=short,
        text=short,
        tail=body[119:] if long else body[40:],
    )


def _region(body: bytes, raw: bytes, shape_based: bool) -> RegionRecord | None:
    """The region, or ``None`` when a count runs past the subrecord."""
    (hole_count,) = struct.unpack_from("<H", body, 14)
    (length,) = struct.unpack_from("<I", body, 18)
    at = 22 + length
    if at + 4 > len(body):
        return None
    text = body[22:at]
    properties = PropertyRecord(body[18:at], parse_text(text[:-1] if text.endswith(b"\0") else text))
    (count,) = struct.unpack_from("<I", body, at)
    at += 4
    stored = count + 1 if shape_based else count
    size = SHAPE_VERTEX if shape_based else PLAIN_VERTEX
    if at + stored * size > len(body):
        return None
    vertices: list[RegionVertex] = []
    for _ in range(stored):
        if shape_based:
            is_round, x, y, cx, cy, radius, a1, a2 = struct.unpack_from("<B5i2d", body, at)
            vertices.append(RegionVertex(x, y, bool(is_round), cx, cy, radius, a1, a2))
        else:
            vx, vy = struct.unpack_from("<2d", body, at)
            vertices.append(RegionVertex(vx, vy))
        at += size
    holes: list[tuple[RegionVertex, ...]] = []
    for _ in range(hole_count):
        if at + 4 > len(body):
            return None
        (n,) = struct.unpack_from("<I", body, at)
        at += 4
        if at + n * PLAIN_VERTEX > len(body):
            return None
        hole = [RegionVertex(*struct.unpack_from("<2d", body, at + k * PLAIN_VERTEX)) for k in range(n)]
        holes.append(tuple(hole))
        at += n * PLAIN_VERTEX
    closing = vertices.pop() if shape_based else None
    return RegionRecord(
        raw,
        _prefix(body),
        hole_count,
        properties,
        tuple(vertices),
        tuple(holes),
        closing,
        shape_based,
        body[at:],
    )


_SIMPLE = {TRACK: ("track", _track), ARC: ("arc", _arc), VIA: ("via", _via), FILL: ("fill", _fill)}


def _typed(
    kind: int, subs: list[bytes], raw: bytes, shape_based: bool, where: str
) -> tuple[Primitive, Issue | None]:
    keep = RawPrimitive(kind, tuple(subs), raw)
    if kind == BODY:
        return keep, None
    if kind in _SIMPLE:
        name, make = _SIMPLE[kind]
        if len(subs[0]) < MINIMUMS[name]:
            return keep, _short(name, len(subs[0]), where)
        return make(subs[0], raw), None
    if kind == PAD:
        if len(subs[4]) < MINIMUMS["pad"]:
            return keep, _short("pad", len(subs[4]), where)
        if subs[5] and len(subs[5]) < MINIMUMS["pad-layers"]:
            return keep, _short("pad layer", len(subs[5]), where)
        return _pad(subs, raw), None
    if kind == TEXT:
        if len(subs[0]) < MINIMUMS["text"]:
            return keep, _short("text", len(subs[0]), where)
        return _text(subs, raw), None
    if len(subs[0]) < MINIMUMS["region"]:
        return keep, _short("region", len(subs[0]), where)
    region = _region(subs[0], raw, shape_based)
    if region is None:
        return keep, _short("region", len(subs[0]), where)
    return region, None


def decode_primitives(
    data: bytes, *, where: str, shape_based: bool = False, start: int = 0
) -> tuple[tuple[Primitive, ...], bytes, list[Issue]]:
    """The primitives of ``data`` from ``start``, the bytes after the last whole record (``trailing``) and
    the issues. An unknown type byte or a cut subrecord ends the stream with an error; a record shorter
    than its minimum is a :class:`RawPrimitive` with a warning."""
    out: list[Primitive] = []
    issues: list[Issue] = []
    offset = start
    while offset < len(data):
        kind = data[offset]
        here = f"{where}#{len(out)}@{offset}"
        if kind not in SUBRECORDS:
            issues.append(
                issue(
                    "altium.pcb-read.unknown-type",
                    f"record type {kind} is not a primitive type; the stream stops",
                    here,
                )
            )
            return tuple(out), data[offset:], issues
        at = offset + 1
        subs: list[bytes] = []
        for number in range(1, SUBRECORDS[kind] + 1):
            length = struct.unpack_from("<I", data, at)[0] if at + 4 <= len(data) else None
            if length is None or at + 4 + length > len(data):
                issues.append(
                    issue(
                        "altium.pcb-read.truncated",
                        f"subrecord {number} of a type {kind} record runs past the end; the stream stops",
                        here,
                    )
                )
                return tuple(out), data[offset:], issues
            subs.append(data[at + 4 : at + 4 + length])
            at += 4 + length
        record, problem = _typed(kind, subs, data[offset:at], shape_based, f"{where}#{len(out)}")
        if problem is not None:
            issues.append(problem)
        out.append(record)
        offset = at
    return tuple(out), b"", issues


# --- evidence ----------------------------------------------------------------------------------------

UNTYPED = frozenset({"raw", "tail", "prefix", "type", "subrecords", "shape_based"})
"""Fields of the binary records that are not typed views of the bytes: they have no row of "Fields"."""
BINARY_RECORDS = (
    Prefix, TrackRecord, ArcRecord, ViaRecord, FillRecord, PadRecord, TextRecord, RegionRecord, RegionVertex,
)  # fmt: skip


def typed_fields() -> tuple[str, ...]:
    """``<record>.<field>`` for every typed field of every binary record."""
    out: list[str] = []
    for record in BINARY_RECORDS:
        assert is_dataclass(record)
        out += [f"{record.__name__}.{f.name}" for f in fields(record) if f.name not in UNTYPED]
    return tuple(out)


_INFERRED = Level.INFERRED
_CORPUS = Level.CORPUS_VERIFIED
_ORACLE = Level.ORACLE_VERIFIED
FIELD_LEVELS: dict[str, Level] = {
    "Prefix.layer": _ORACLE,
    "Prefix.flags1": _INFERRED,
    "Prefix.flags2": _INFERRED,
    "Prefix.net": _ORACLE,
    "Prefix.polygon": _INFERRED,
    "Prefix.component": _ORACLE,
    "Prefix.locked": _INFERRED,
    "TrackRecord.x1": _ORACLE,
    "TrackRecord.y1": _ORACLE,
    "TrackRecord.x2": _ORACLE,
    "TrackRecord.y2": _ORACLE,
    "TrackRecord.width": _ORACLE,
    "TrackRecord.sub_polygon": _INFERRED,
    "ArcRecord.cx": _INFERRED,
    "ArcRecord.cy": _INFERRED,
    "ArcRecord.radius": _INFERRED,
    "ArcRecord.start_angle": _INFERRED,
    "ArcRecord.end_angle": _INFERRED,
    "ArcRecord.width": _INFERRED,
    "ArcRecord.sub_polygon": _INFERRED,
    "ViaRecord.x": _ORACLE,
    "ViaRecord.y": _ORACLE,
    "ViaRecord.diameter": _ORACLE,
    "ViaRecord.hole": _ORACLE,
    "ViaRecord.start_layer": _INFERRED,
    "ViaRecord.end_layer": _INFERRED,
    "ViaRecord.tented_top": _INFERRED,
    "ViaRecord.tented_bottom": _INFERRED,
    "FillRecord.x1": _INFERRED,
    "FillRecord.y1": _INFERRED,
    "FillRecord.x2": _INFERRED,
    "FillRecord.y2": _INFERRED,
    "FillRecord.rotation": _INFERRED,
    "PadRecord.name": _ORACLE,
    "PadRecord.x": _ORACLE,
    "PadRecord.y": _ORACLE,
    "PadRecord.size_top": _ORACLE,
    "PadRecord.size_mid": _INFERRED,
    "PadRecord.size_bottom": _INFERRED,
    "PadRecord.hole": _ORACLE,
    "PadRecord.shape_top": _ORACLE,
    "PadRecord.shape_mid": _INFERRED,
    "PadRecord.shape_bottom": _INFERRED,
    "PadRecord.rotation": _INFERRED,
    "PadRecord.plated": _ORACLE,
    "PadRecord.stack_mode": _INFERRED,
    "PadRecord.paste_expansion": _INFERRED,
    "PadRecord.solder_expansion": _INFERRED,
    "PadRecord.paste_mode": _INFERRED,
    "PadRecord.solder_mode": _INFERRED,
    "PadRecord.hole_rotation": _INFERRED,
    "PadRecord.inner_sizes": _INFERRED,
    "PadRecord.inner_shapes": _INFERRED,
    "PadRecord.hole_shape": _INFERRED,
    "PadRecord.slot_length": _INFERRED,
    "PadRecord.slot_rotation": _INFERRED,
    "PadRecord.hole_offsets": _INFERRED,
    "PadRecord.alternate_shapes": _ORACLE,
    "PadRecord.corner_percentages": _ORACLE,
    "TextRecord.x": _INFERRED,
    "TextRecord.y": _INFERRED,
    "TextRecord.height": _INFERRED,
    "TextRecord.stroke_font": _INFERRED,
    "TextRecord.rotation": _INFERRED,
    "TextRecord.mirrored": _INFERRED,
    "TextRecord.stroke_width": _INFERRED,
    "TextRecord.is_comment": _INFERRED,
    "TextRecord.is_designator": _ORACLE,
    "TextRecord.font_type": _INFERRED,
    "TextRecord.bold": _INFERRED,
    "TextRecord.italic": _INFERRED,
    "TextRecord.font_name": _INFERRED,
    "TextRecord.inverted": _INFERRED,
    "TextRecord.margin": _INFERRED,
    "TextRecord.wide_index": _ORACLE,
    "TextRecord.short_text": _INFERRED,
    "TextRecord.text": _ORACLE,
    "RegionRecord.hole_count": _CORPUS,
    "RegionRecord.properties": _CORPUS,
    "RegionRecord.outline": _CORPUS,
    "RegionRecord.holes": _CORPUS,
    "RegionRecord.closing": _CORPUS,
    "RegionVertex.x": _INFERRED,
    "RegionVertex.y": _INFERRED,
    "RegionVertex.is_round": _INFERRED,
    "RegionVertex.cx": _INFERRED,
    "RegionVertex.cy": _INFERRED,
    "RegionVertex.radius": _INFERRED,
    "RegionVertex.start_angle": _INFERRED,
    "RegionVertex.end_angle": _INFERRED,
}
"""``<record>.<field>`` → the label of its row in "Fields" of ``docs/formats/altium/pcb-read.md``."""


def field_level(record: str, field: str) -> Level:
    """The evidence level of a typed field; ``KeyError`` for a field without a row."""
    return FIELD_LEVELS[f"{record}.{field}"]


__all__ = [
    "ARC",
    "BODY",
    "FIELD_LEVELS",
    "FILL",
    "MINIMUMS",
    "PAD",
    "PCB_READ_ISSUE_CODES",
    "REGION",
    "SUBRECORDS",
    "TEXT",
    "TRACK",
    "VIA",
    "VIA_PAD_TABLE",
    "VIA_PAD_TABLE_FROM",
    "ArcRecord",
    "FillRecord",
    "PadRecord",
    "PcbReadError",
    "Prefix",
    "Primitive",
    "RawPrimitive",
    "RegionRecord",
    "RegionVertex",
    "TextRecord",
    "TrackRecord",
    "ViaRecord",
    "decode_primitives",
    "error_of",
    "field_level",
    "primitive_type",
    "to_nm",
    "to_nm_exact",
    "typed_fields",
    "via_pad_removed",
]
