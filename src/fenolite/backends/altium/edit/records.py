# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Byte-level edits of the records of an Altium PCB document (change c0241): a primitive split into its
subrecords and joined again, fields patched in place at the offsets of ``read.pcbprims``, keys of a
property text replaced in place. Every edit keeps the record's length and form unless the edited text
itself changes length; nothing here decides what to edit.

The offsets are the reader's (``docs/formats/altium/pcb-read.md``, "Fields"), so every patched record reads
back through ``read.pcbprims`` with the patched value.
"""

# evidence: see edit.session

from __future__ import annotations

import math
import struct
from collections.abc import Callable, Mapping

from fenolite.backends.altium.read.pcbprims import (
    ARC,
    FILL,
    PAD,
    PLAIN_VERTEX,
    REGION,
    SHAPE_VERTEX,
    SUBRECORDS,
    TEXT,
    TRACK,
    VIA,
)
from fenolite.backends.altium.read.pcbprops import CODEC

NO_INDEX = 0xFFFF
LENGTH_MASK = 0xFFFFFF
GEOMETRY = {PAD: 4}
"""The subrecord that holds the 13-byte prefix and the coordinates: the fifth of a pad, else the first."""
BODY = 12
SUBRECORDS_ALL = {**SUBRECORDS, BODY: 1}

Point = tuple[float, float]
Transform = Callable[[float, float], Point]


class RecordError(ValueError):
    """A record that this module cannot edit: cut short, of another type, or a text it cannot encode."""


# --- primitives --------------------------------------------------------------------------------------


def split(raw: bytes) -> tuple[int, list[bytes]]:
    """The type byte of the primitive ``raw`` and its subrecords' bytes."""
    kind = raw[0]
    if kind not in SUBRECORDS_ALL:
        raise RecordError(f"type {kind} is not a primitive type")
    at = 1
    subs: list[bytes] = []
    for _ in range(SUBRECORDS_ALL[kind]):
        if at + 4 > len(raw):
            raise RecordError("a subrecord length runs past the record")
        (length,) = struct.unpack_from("<I", raw, at)
        if at + 4 + length > len(raw):
            raise RecordError("a subrecord runs past the record")
        subs.append(raw[at + 4 : at + 4 + length])
        at += 4 + length
    if at != len(raw):
        raise RecordError("bytes follow the last subrecord")
    return kind, subs


def join(kind: int, subs: list[bytes]) -> bytes:
    """The primitive of type ``kind`` with the subrecords ``subs``."""
    return bytes([kind]) + b"".join(struct.pack("<I", len(sub)) + sub for sub in subs)


def _geometry(kind: int) -> int:
    return GEOMETRY.get(kind, 0)


def patch(raw: bytes, offset: int, fmt: str, *values: object) -> bytes:
    """``raw`` with ``values`` packed by ``fmt`` at ``offset`` of its geometry subrecord."""
    kind, subs = split(raw)
    index = _geometry(kind)
    body = bytearray(subs[index])
    if offset + struct.calcsize(fmt) > len(body):
        raise RecordError(f"offset {offset} is past the subrecord of {len(body)} bytes")
    struct.pack_into(fmt, body, offset, *values)
    subs[index] = bytes(body)
    return join(kind, subs)


def unpack(raw: bytes, offset: int, fmt: str) -> tuple[object, ...]:
    kind, subs = split(raw)
    return struct.unpack_from(fmt, subs[_geometry(kind)], offset)


KEEP = -1
"""The value of ``set_prefix``'s index arguments that keeps the stored index."""


def set_prefix(
    raw: bytes, *, layer: int | None = None, net: int = KEEP, polygon: int = KEEP, component: int = KEEP
) -> bytes:
    """``raw`` with the prefix fields given changed (``NO_INDEX`` for none)."""
    kind, subs = split(raw)
    index = _geometry(kind)
    body = bytearray(subs[index])
    if layer is not None:
        body[0] = layer
    for offset, value in ((3, net), (5, polygon), (7, component)):
        if value != KEEP:
            struct.pack_into("<H", body, offset, value)
    subs[index] = bytes(body)
    return join(kind, subs)


def prefix_of(raw: bytes) -> tuple[int, int, int, int]:
    """``(layer, net, polygon, component)`` of ``raw``'s prefix, indices as stored (``NO_INDEX`` for none)."""
    kind, subs = split(raw)
    body = subs[_geometry(kind)]
    net, polygon, component = struct.unpack_from("<3H", body, 3)
    return body[0], net, polygon, component


LONG_LAYER: Mapping[int, tuple[int, int]] = {
    TRACK: (45, 41),
    ARC: (56, 52),
    FILL: (50, 42),
    PAD: (170, 114),
    TEXT: (232, 226),
}
"""Per primitive type, the shortest saved long form and the offset of its 32-bit long layer id in the
geometry subrecord (``pcb-records.md``, "Long forms of the eight public documents"; ``pcb-copper.md``):
a pad's at 114 of its fifth subrecord and a text's at 226 (change c0430)."""
SHORT_FORM: Mapping[int, int] = {TRACK: 36, ARC: 47, PAD: 114, TEXT: 137}
"""The short forms that hold no long layer id: the track, the arc, the pad and the text that Fenolite
writes."""


def long_layer_offset(raw: bytes) -> int | None:
    """The offset of the long layer id in ``raw``'s geometry subrecord; ``None`` for a short track, arc, pad
    or text, which holds none, and for every other type. ``RecordError`` for a track, an arc, a fill, a pad
    or a text whose length is neither a short form nor a long form with a recorded offset (a fill of 46
    bytes, for one)."""
    kind, subs = split(raw)
    if kind not in LONG_LAYER:
        return None
    length = len(subs[_geometry(kind)])
    shortest, offset = LONG_LAYER[kind]
    if length >= shortest:
        return offset
    if length == SHORT_FORM.get(kind):
        return None
    raise RecordError(f"no row records the long layer id of a type {kind} record of {length} bytes")


# --- coordinates -------------------------------------------------------------------------------------


def _round(value: float) -> int:
    return int(round(value))


def transform(
    raw: bytes, move: Transform, *, turn: float = 0.0, mirror: bool = False, shape_based: bool = False
) -> bytes:
    """``raw`` with every point moved by ``move`` (document units), its angles turned by ``turn`` degrees,
    and, with ``mirror``, mirrored in X before the turn (``move`` then holds the mirror). ``shape_based``
    says that a region or body is of the form of ``ShapeBasedRegions6`` (the storage, not a key, says it).

    A mirrored angle ``a`` reads ``−a``, but a pad's reads ``180 − a``: the same shape, since a pad's shape
    is symmetric under a half turn, in the frame Altium gives a part on the other side (change c0453,
    ``pcb-document.md``, "Frame of a bottom part")."""
    kind, subs = split(raw)
    body = bytearray(subs[_geometry(kind)])

    def point(offset: int) -> None:
        x, y = struct.unpack_from("<2i", body, offset)
        nx, ny = move(x, y)
        struct.pack_into("<2i", body, offset, _round(nx), _round(ny))

    def angle(offset: int, *, mirrored_from: float = 0.0) -> None:
        (value,) = struct.unpack_from("<d", body, offset)
        value = mirrored_from - value if mirror else value
        struct.pack_into("<d", body, offset, (value + turn) % 360.0)

    if kind == TRACK:
        point(13)
        point(21)
    elif kind == VIA:
        point(13)
    elif kind == ARC:
        point(13)
        start, end = struct.unpack_from("<2d", body, 25)
        if mirror:
            start, end = 180.0 - end, 180.0 - start
        struct.pack_into("<2d", body, 25, (start + turn) % 360.0, (end + turn) % 360.0)
    elif kind == FILL:
        x1, y1, x2, y2 = struct.unpack_from("<4i", body, 13)
        cx, cy = move((x1 + x2) / 2, (y1 + y2) / 2)
        hw, hh = (x2 - x1) / 2, (y2 - y1) / 2
        struct.pack_into("<4i", body, 13, _round(cx - hw), _round(cy - hh), _round(cx + hw), _round(cy + hh))
        angle(29)
    elif kind == PAD:
        point(13)
        angle(52, mirrored_from=180.0)
    elif kind == TEXT:
        point(13)
        angle(27)
        if mirror:
            body[35] = 0 if body[35] else 1
    elif kind in (REGION, BODY):
        _region_points(body, move, shape_based=shape_based)
    subs[_geometry(kind)] = bytes(body)
    return join(kind, subs)


def region_layout(body: bytes | bytearray, *, shape_based: bool) -> tuple[int, int, int]:
    """``(first vertex offset, stored outline vertices, vertex size)`` of a region or body subrecord."""
    (length,) = struct.unpack_from("<I", body, 18)
    at = 22 + length
    (count,) = struct.unpack_from("<I", body, at)
    size = SHAPE_VERTEX if shape_based else PLAIN_VERTEX
    return at + 4, count + 1 if shape_based else count, size


def _region_points(body: bytearray, move: Transform, *, shape_based: bool) -> None:
    (holes,) = struct.unpack_from("<H", body, 14)
    at, stored, size = region_layout(body, shape_based=shape_based)
    for _ in range(stored):
        if shape_based:
            x, y, cx, cy = struct.unpack_from("<4i", body, at + 1)
            nx, ny = move(x, y)
            ncx, ncy = move(cx, cy)
            struct.pack_into("<4i", body, at + 1, _round(nx), _round(ny), _round(ncx), _round(ncy))
        else:
            x, y = struct.unpack_from("<2d", body, at)
            struct.pack_into("<2d", body, at, *move(x, y))
        at += size
    for _ in range(holes):
        (n,) = struct.unpack_from("<I", body, at)
        at += 4
        for _ in range(n):
            x, y = struct.unpack_from("<2d", body, at)
            struct.pack_into("<2d", body, at, *move(x, y))
            at += PLAIN_VERTEX


def region_outline(raw: bytes, vertices: list[tuple[int, int]], *, shape_based: bool) -> bytes:
    """The region ``raw`` with no hole and the outline ``vertices`` (document units, no closing vertex):
    its head (prefix and property text) and the bytes after its rings are kept (change c0452). The plain
    form holds each vertex as two doubles; the shape-based form as 37 bytes, none round, the first vertex
    repeated after the last, as ``pcbrecords.region_record`` writes them."""
    kind, subs = split(raw)
    if kind != REGION:
        raise RecordError(f"type {kind} is not a region")
    body = subs[0]
    at, stored, size = region_layout(body, shape_based=shape_based)
    head = bytearray(body[: at - 4])
    end = at + stored * size
    (holes,) = struct.unpack_from("<H", body, 14)
    for _ in range(holes):
        (n,) = struct.unpack_from("<I", body, end)
        end += 4 + n * PLAIN_VERTEX
    struct.pack_into("<H", head, 14, 0)
    out = bytes(head) + struct.pack("<I", len(vertices))
    if shape_based:
        out += b"".join(
            struct.pack("<B5i2d", 0, x, y, 0, 0, 0, 0.0, 0.0) for x, y in (*vertices, vertices[0])
        )
    else:
        out += b"".join(struct.pack("<2d", float(x), float(y)) for x, y in vertices)
    return join(kind, [out + body[end:]])


def shift(dx: int, dy: int) -> Transform:
    return lambda x, y: (x + dx, y + dy)


def quarter_turn(cx: float, cy: float, degrees: float) -> Transform:
    """A turn about ``(cx, cy)`` by ``degrees``, exact for multiples of 90."""
    quarters = round(degrees / 90.0)
    if math.isclose(degrees, quarters * 90.0, abs_tol=1e-9):
        cos, sin = ((1, 0), (0, 1), (-1, 0), (0, -1))[quarters % 4]
    else:
        cos, sin = math.cos(math.radians(degrees)), math.sin(math.radians(degrees))

    def turn(x: float, y: float) -> Point:
        rx, ry = x - cx, y - cy
        return cx + rx * cos - ry * sin, cy + rx * sin + ry * cos

    return turn


def mirror_x(cx: float) -> Transform:
    return lambda x, y: (2 * cx - x, y)


# --- property texts ----------------------------------------------------------------------------------


def _encode(value: str) -> bytes:
    try:
        return value.encode(CODEC)
    except UnicodeEncodeError as error:
        raise RecordError(f"the value {value!r} cannot be written in {CODEC}") from error


def set_keys(text: bytes, changes: Mapping[str, str]) -> bytes:
    """The property text ``text`` (without its NUL) with each key of ``changes`` set: in place where the key
    is held (compared without case; its first occurrence), appended as ``|KEY=VALUE`` otherwise."""
    pieces = text.split(b"|")
    wanted = {key.upper(): (key, value) for key, value in changes.items()}
    done: set[str] = set()
    for number, piece in enumerate(pieces):
        name, sep, rest = piece.partition(b"=")
        key = name.decode(CODEC).upper()
        if not sep or key not in wanted or key in done:
            continue
        end = rest[len(rest.rstrip(b"\r\n")) :]
        pieces[number] = name + b"=" + _encode(wanted[key][1]) + end
        done.add(key)
    out = b"|".join(pieces)
    for key, (given, value) in wanted.items():
        if key not in done:
            out += b"|" + _encode(given) + b"=" + _encode(value)
    return out


def keys_of(text: bytes) -> dict[str, str]:
    """The first value of each upper-case key of a property text."""
    out: dict[str, str] = {}
    for piece in text.split(b"|"):
        name, sep, rest = piece.partition(b"=")
        if sep:
            out.setdefault(name.decode(CODEC).upper(), rest.rstrip(b"\r\n").decode(CODEC))
    return out


def property_payload(raw: bytes, *, lead: int = 0) -> tuple[bytes, bool]:
    """The property text of the block ``raw`` and whether it ends in a NUL."""
    (word,) = struct.unpack_from("<I", raw, lead)
    payload = raw[lead + 4 : lead + 4 + (word & LENGTH_MASK)]
    return (payload[:-1], True) if payload.endswith(b"\0") else (payload, False)


def set_property(raw: bytes, changes: Mapping[str, str], *, lead: int = 0) -> bytes:
    """The property block ``raw`` (``lead`` bytes, a length word, the text) with ``changes`` set; the high
    byte of the length word and the closing NUL are kept."""
    (word,) = struct.unpack_from("<I", raw, lead)
    text, nul = property_payload(raw, lead=lead)
    payload = set_keys(text, changes) + (b"\0" if nul else b"")
    if len(payload) > LENGTH_MASK:
        raise RecordError("the property text is longer than its length word holds")
    return raw[:lead] + struct.pack("<I", (word & ~LENGTH_MASK) | len(payload)) + payload


def replace_run(
    raw: bytes, dropped: Callable[[str], bool], fields: list[tuple[str, str]], *, lead: int = 0
) -> bytes:
    """The property block ``raw`` with every key for which ``dropped`` (given the upper-case key) holds
    taken out and ``fields`` written where the first of them stood, or at the end (change c0452: a
    polygon's outline keys)."""
    (word,) = struct.unpack_from("<I", raw, lead)
    text, nul = property_payload(raw, lead=lead)
    new = [_encode(key) + b"=" + _encode(value) for key, value in fields]
    out: list[bytes] = []
    placed = False
    for piece in text.split(b"|"):
        name, sep, _ = piece.partition(b"=")
        if sep and dropped(name.decode(CODEC).upper()):
            if not placed:
                out += new
                placed = True
            continue
        out.append(piece)
    if not placed:
        out += new
    payload = b"|".join(out) + (b"\0" if nul else b"")
    if len(payload) > LENGTH_MASK:
        raise RecordError("the property text is longer than its length word holds")
    return raw[:lead] + struct.pack("<I", (word & ~LENGTH_MASK) | len(payload)) + payload


def property_block(fields: Mapping[str, str]) -> bytes:
    """A new property block of ``fields`` (``|KEY=VALUE`` each) and its NUL."""
    text = b"".join(b"|" + _encode(key) + b"=" + _encode(value) for key, value in fields.items()) + b"\0"
    return struct.pack("<I", len(text)) + text


def region_keys(raw: bytes) -> dict[str, str]:
    """The property text of the region or body primitive ``raw``."""
    _, subs = split(raw)
    body = subs[0]
    (length,) = struct.unpack_from("<I", body, 18)
    text = body[22 : 22 + length]
    return keys_of(text[:-1] if text.endswith(b"\0") else text)


def set_region_keys(raw: bytes, changes: Mapping[str, str]) -> bytes:
    """The region or body primitive ``raw`` with ``changes`` set in its property text."""
    kind, subs = split(raw)
    if kind not in (REGION, BODY):
        raise RecordError(f"type {kind} has no property text")
    body = subs[0]
    (length,) = struct.unpack_from("<I", body, 18)
    text = body[22 : 22 + length]
    nul = text.endswith(b"\0")
    new = set_keys(text[:-1] if nul else text, changes) + (b"\0" if nul else b"")
    subs[0] = body[:18] + struct.pack("<I", len(new)) + new + body[22 + length :]
    return join(kind, subs)


# --- strings -----------------------------------------------------------------------------------------


def wide_entry(index: int, text: str) -> bytes:
    """One entry of ``WideStrings6/Data``: the index, the byte length and the UTF-16LE text with its NUL."""
    data = text.encode("utf-16-le") + b"\0\0"
    return struct.pack("<2I", index, len(data)) + data


def short_string(text: str) -> bytes | None:
    """One length byte and the 8-bit text, or ``None`` when it does not fit."""
    try:
        data = text.encode(CODEC)
    except UnicodeEncodeError:
        return None
    return bytes([len(data)]) + data if len(data) <= 255 else None


def set_text_string(raw: bytes, text: str) -> bytes:
    """A text primitive with its short string set to ``text`` where it fits, else kept."""
    kind, subs = split(raw)
    if kind != TEXT:
        raise RecordError(f"type {kind} is not a text")
    short = short_string(text)
    if short is not None:
        subs[1] = short
    return join(kind, subs)


def set_wide_index(raw: bytes, index: int) -> bytes:
    return patch(raw, 115, "<I", index)


__all__ = [
    "KEEP",
    "NO_INDEX",
    "RecordError",
    "join",
    "keys_of",
    "mirror_x",
    "patch",
    "prefix_of",
    "property_block",
    "property_payload",
    "quarter_turn",
    "region_keys",
    "region_outline",
    "replace_run",
    "set_keys",
    "set_prefix",
    "set_property",
    "set_region_keys",
    "set_text_string",
    "set_wide_index",
    "shift",
    "split",
    "transform",
    "unpack",
    "wide_entry",
]
