# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Authored long-form Altium PCB records and files for the reader's unit tests (change c0041).

Each long record is Fenolite's short record (``fenolite.backends.altium.pcbrecords``), cut or extended
to a length with the counting byte pattern ``01 02 03 …``; fills, texts, regions, wide strings, rules,
classes, documents and libraries are authored here from ``docs/formats/altium/pcb-read.md``. Nothing is
copied from a corpus file.
"""

from __future__ import annotations

import struct
from collections.abc import Mapping, Sequence

from fenolite.backends.altium import pcbrecords as rec
from fenolite.backends.altium.cfb import Entry, Storage, write_compound

NO_INDEX = 0xFFFF
TRACK_XY = (100_000, 200_000, 300_000, -400_000)
TRACK_WIDTH = 25_000
ARC = rec.ArcGeometry(cx=1_000, cy=-2_000, radius=50_000, start=0.0, end=90.0)
ARC_WIDTH = 10_000
WORKED_PAD = {"x": -314961, "y": 0, "size": (354331, 374016)}
"""The worked pad of ``pcb-records.md``: pad ``1`` of the mini 0603 resistor."""


def pattern(count: int) -> bytes:
    """``01 02 03 …`` for ``count`` bytes."""
    return bytes((i + 1) & 0xFF for i in range(count))


def fit(body: bytes, length: int) -> bytes:
    """``body`` cut to ``length`` bytes, or extended with :func:`pattern`."""
    return body[:length] if length <= len(body) else body + pattern(length - len(body))


def frame(kind: int, *subrecords: bytes) -> bytes:
    """A primitive: the type byte and each subrecord with its 32-bit length."""
    return bytes((kind,)) + b"".join(struct.pack("<I", len(s)) + s for s in subrecords)


def subrecords(record: bytes) -> list[bytes]:
    """The subrecords of one framed primitive."""
    out: list[bytes] = []
    at = 1
    while at < len(record):
        (length,) = struct.unpack_from("<I", record, at)
        out.append(record[at + 4 : at + 4 + length])
        at += 4 + length
    return out


def long_track(length: int = 36, *, layer: int = 1, net: int = NO_INDEX, component: int = NO_INDEX) -> bytes:
    x1, y1, x2, y2 = TRACK_XY
    short = rec.track_record(layer, (x1, y1), (x2, y2), TRACK_WIDTH, net=net, component=component)
    return frame(rec.TRACK, fit(subrecords(short)[0], length))


def long_arc(length: int = 47, *, layer: int = 1, net: int = NO_INDEX, component: int = NO_INDEX) -> bytes:
    short = rec.arc_record(layer, ARC, ARC_WIDTH, net=net, component=component)
    return frame(rec.ARC, fit(subrecords(short)[0], length))


def long_via(length: int = 321, *, net: int = NO_INDEX) -> bytes:
    return frame(rec.VIA, fit(subrecords(rec.via_record(0, 0, 236220, 118110, net=net))[0], length))


def long_fill(
    length: int = 50,
    *,
    corners: tuple[int, int, int, int] = (0, 0, 1_000_000, 500_000),
    rotation: float = 90.0,
    layer: int = 1,
    net: int = NO_INDEX,
) -> bytes:
    body = rec.prefix(layer, net=net) + struct.pack("<4id", *corners, rotation)
    return frame(6, fit(body, length))


def long_text(
    length: int = 137,
    *,
    text: str = "R1",
    font: str = "",
    bold: bool = False,
    designator: bool = False,
    wide_index: int = 0xFFFFFFFF,
    component: int = NO_INDEX,
    layer: int = 33,
) -> bytes:
    body = rec.prefix(layer, component=component)
    body += struct.pack("<3iHdBi", 500_000, -600_000, 393701, 1, 90.0, 0, 39370)
    long = bytes((0, 1 if designator else 0, 0, 1 if font else 0, 1 if bold else 0, 0))
    long += font.encode("utf-16-le").ljust(64, b"\0")[:64] + b"\0" + struct.pack("<iI", 0, wide_index)
    assert len(body + long) == 119
    return frame(rec.TEXT, fit(body + long, length), rec.short_string(text))


def long_pad(geometry: int = 114, layers: int = 596, **kwargs: object) -> bytes:
    """The worked pad with a fifth subrecord of ``geometry`` bytes and a sixth of ``layers`` (0 for none)."""
    options: dict[str, object] = {
        "name": "1", "layer": 1, "x": WORKED_PAD["x"], "y": WORKED_PAD["y"], "size": WORKED_PAD["size"],
        "shape": 1, "rotation": 0.0, "corner": 50 if layers else None,
    }  # fmt: skip
    options.update(kwargs)
    subs = subrecords(rec.pad_record(**options))  # type: ignore[arg-type]
    subs[4] = fit(subs[4], geometry)
    if layers:
        subs[5] = fit(subs[5], layers)
    return frame(rec.PAD, *subs)


def region(
    outline: Sequence[tuple[float, float]],
    holes: Sequence[Sequence[tuple[float, float]]] = (),
    *,
    shape_based: bool = False,
    properties: bytes = b"V7_LAYER=TOP|KIND=0",
    layer: int = 1,
    net: int = NO_INDEX,
    polygon: int = NO_INDEX,
    tail: bytes = b"",
) -> bytes:
    """A region (type 11) in the plain form or the shape-based one (37-byte vertices, the first vertex
    stored again at the end)."""
    head = bytearray(rec.prefix(layer, net=net))
    struct.pack_into("<H", head, 5, polygon)
    text = properties + b"\0"
    body = bytes(head) + b"\0" + struct.pack("<HH", len(holes), 0) + struct.pack("<I", len(text)) + text
    body += struct.pack("<I", len(outline))
    if shape_based:
        for x, y in (*outline, outline[0]):
            body += struct.pack("<B5i2d", 0, int(x), int(y), 0, 0, 0, 0.0, 0.0)
    else:
        body += b"".join(struct.pack("<2d", x, y) for x, y in outline)
    for hole in holes:
        body += struct.pack("<I", len(hole)) + b"".join(struct.pack("<2d", x, y) for x, y in hole)
    return frame(11, body + tail)


def block(text: str, *, lead: bytes = b"") -> bytes:
    """A property block of ``text`` (ISO-8859-1) with its NUL, after ``lead``."""
    payload = text.encode("iso-8859-1") + b"\0"
    return lead + struct.pack("<I", len(payload)) + payload


def rule(number: int, text: str) -> bytes:
    """A rule of ``Rules6``: the 16-bit kind number and one property block."""
    return block(text, lead=struct.pack("<H", number))


def wide_strings(entries: Mapping[int, str]) -> bytes:
    """A ``WideStrings6/Data`` table; an empty entry has the length 2 and no bytes, as Altium saves it."""
    out = b""
    for index, text in entries.items():
        data = text.encode("utf-16-le") + b"\0\0"
        out += struct.pack("<2I", index, len(data)) + (data if text else b"")
    return out


BOARD = (
    "|KIND=Protel_Advanced_PCB|VERSION=5.01|ORIGINX=1000mil|ORIGINY=1000mil|DISPLAYUNIT=1"
    "|LAYER1NAME=Top Layer|LAYER1PREV=0|LAYER1NEXT=32"
    + "".join(f"|LAYER{i}NAME=L{i}|LAYER{i}PREV=0|LAYER{i}NEXT=0" for i in range(2, 32))
    + "|LAYER32NAME=Bottom Layer|LAYER32PREV=1|LAYER32NEXT=0"
)
"""An authored two-layer board record."""

Storages = Mapping[str, Sequence[bytes] | tuple[int, bytes]]


def document(storages: Storages | None = None, *, board: str = BOARD, root: Sequence[Entry] = ()) -> bytes:
    """A PCB document: ``Board6`` and each storage of ``storages`` with ``Header`` and ``Data``. A list of
    records gives ``Data`` (joined) and ``Header`` (their count); a pair gives both explicitly."""
    entries: list[Entry] = [
        *root,
        Storage("Board6", (("Header", struct.pack("<I", 1)), ("Data", block(board)))),
    ]
    for name, value in (storages or {}).items():
        if isinstance(value, tuple) and len(value) == 2 and isinstance(value[0], int):
            count, data = value
        else:
            items = list(value)
            count, data = len(items), b"".join(items)  # type: ignore[arg-type]
        entries.append(Storage(name, (("Header", struct.pack("<I", count)), ("Data", data))))
    return write_compound(entries)


def string_block(text: str) -> bytes:
    """A 32-bit length, one length byte and the characters."""
    data = text.encode("iso-8859-1")
    return struct.pack("<IB", len(data) + 1, len(data)) + data


LIBRARY_BOARD = (
    "|KIND=Protel_Advanced_PCB_Library|VERSION=3.00|LAYER1NAME=Top Layer|LAYER1PREV=0|LAYER1NEXT=0"
)


def library(
    footprints: Mapping[str, Sequence[bytes]],
    *,
    names: Sequence[str] | None = None,
    storage_names: Mapping[str, str] | None = None,
    section_keys: bool = False,
    header_counts: Mapping[str, int] | None = None,
    unique_ids: Mapping[str, Sequence[tuple[int, str]]] | None = None,
    patterns: Mapping[str, str] | None = None,
    wide: Mapping[str, str] | None = None,
) -> bytes:
    """A PCB library: ``FileHeader``, ``Library`` with its board record and the name list, and one root
    storage per footprint (``Header``, ``Parameters``, ``WideStrings``, ``Data`` and
    ``UniqueIDPrimitiveInformation``). ``storage_names`` maps a footprint to a shortened storage name,
    listed in ``SectionKeys`` when ``section_keys``."""
    listed = list(footprints) if names is None else list(names)
    storage_names = dict(storage_names or {})
    header = struct.pack("<IB", 27, 27) + b"PCB 6.0 Binary Library File" + struct.pack("<d", 5.01)
    header += struct.pack("<IB", 8, 8) + b"ABCDEFGH"
    data = block(LIBRARY_BOARD) + struct.pack("<I", len(listed)) + b"".join(string_block(n) for n in listed)
    entries: list[Entry] = [("FileHeader", header)]
    if section_keys:
        keyed = list(storage_names.items())
        keys = struct.pack("<i", len(keyed))
        for full, short in keyed:
            raw = full.encode("iso-8859-1") + b"\0"
            keys += struct.pack("<I", len(raw)) + raw + string_block(short)
        entries.append(("SectionKeys", keys))
    entries.append(Storage("Library", (("Header", struct.pack("<I", 1)), ("Data", data))))
    for name, primitives in footprints.items():
        count = (header_counts or {}).get(name, len(primitives))
        ids = (unique_ids or {}).get(name, ())
        uid = b"".join(
            block(f"|PRIMITIVEINDEX={i}|PRIMITIVEOBJECTID={kind}|UNIQUEID=ID{i:06d}") for i, kind in ids
        )
        pattern = (patterns or {}).get(name, name)
        params = block(f"|PATTERN={pattern}|HEIGHT=10mil|DESCRIPTION=d|ITEMGUID=|REVISIONGUID=")
        entries.append(
            Storage(
                storage_names.get(name, name),
                (
                    ("Header", struct.pack("<I", count)),
                    ("Parameters", params),
                    ("WideStrings", block((wide or {}).get(name, ""))),
                    ("Data", string_block(name) + b"".join(primitives)),
                    Storage(
                        "UniqueIDPrimitiveInformation",
                        (("Header", struct.pack("<I", len(ids))), ("Data", uid)),
                    ),
                ),
            )
        )
    return write_compound(entries)
