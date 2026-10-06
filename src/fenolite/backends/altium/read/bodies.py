# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Component-body records of Altium PCB files, kept byte for byte (``docs/formats/altium/pcb-bodies.md``;
change c0043).

The PCB reader (c0041) keeps the ``Data`` streams of ``ComponentBodies6`` and ``ShapeBasedComponentBodies6``
as bytes, and a library footprint's body primitives as ``RawPrimitive``. ``read_bodies`` frames those bytes
into ``BodyRecord`` values: the common prefix, the property text and the outline, as a region is framed. A
key is typed only when its row of the fact page has a source; every key stays in ``properties``.
``encode(read_bodies(data)) == data``.
"""

# evidence: see import_evidence

from __future__ import annotations

import struct
from dataclasses import dataclass
from fractions import Fraction

from fenolite.backends.altium.read.pcb import decode_name
from fenolite.backends.altium.read.pcbprims import (
    BODY,
    NO_INDEX,
    PLAIN_VERTEX,
    SHAPE_VERTEX,
    RawPrimitive,
    RegionVertex,
    decode_primitives,
)
from fenolite.backends.altium.read.pcbprops import (
    PropertyRecord,
    issue,
    parse_bool,
    parse_int,
    parse_mil,
    parse_text,
)
from fenolite.core.errors import Issue

COMPONENT_AT = 7
HOLES_AT = 14
TEXT_AT = 18
MINIMUM = 26
"""The shortest subrecord that frames: the prefix, five bytes, a text length and a vertex count."""
TYPED_KEYS = (
    "STANDOFFHEIGHT",
    "OVERALLHEIGHT",
    "BODYPROJECTION",
    "IDENTIFIER",
    "MODEL.NAME",
    "MODELID",
    "MODEL.EMBED",
)
"""The keys with a typed view; each is a row of "Typed keys" of ``pcb-bodies.md``."""
_EMPTY = PropertyRecord(b"", ())


@dataclass(frozen=True, slots=True)
class BodyRecord:
    """One component body. ``raw`` is the whole primitive (type byte, length word, subrecord). A record
    that does not frame has ``framed`` false, ``layer`` ``None`` and empty views. ``outline`` holds the
    counted vertices as a region's does; ``closing`` is the extra vertex of the shape-based form. Heights
    are exact units of 1/10 000 mil."""

    index: int
    raw: bytes
    layer: int | None = None
    component: int | None = None
    properties: PropertyRecord = _EMPTY
    outline: tuple[RegionVertex, ...] = ()
    holes: tuple[tuple[RegionVertex, ...], ...] = ()
    closing: RegionVertex | None = None
    shape_based: bool = False
    tail: bytes = b""
    framed: bool = False

    @property
    def standoff_height(self) -> Fraction | None:
        return parse_mil(self.properties.get("STANDOFFHEIGHT"))

    @property
    def overall_height(self) -> Fraction | None:
        return parse_mil(self.properties.get("OVERALLHEIGHT"))

    @property
    def body_projection(self) -> int | None:
        return parse_int(self.properties.get("BODYPROJECTION"))

    @property
    def identifier(self) -> str:
        """The identifier: a list of decimal character codes decoded, any other value as written."""
        return decode_name(self.properties.text("IDENTIFIER"))

    @property
    def model_name(self) -> str:
        return self.properties.text("MODEL.NAME")

    @property
    def model_id(self) -> str:
        return self.properties.text("MODELID")

    @property
    def model_embedded(self) -> bool | None:
        return parse_bool(self.properties.get("MODEL.EMBED"))


def _frame(index: int, raw: bytes, body: bytes, shape_based: bool) -> BodyRecord | None:
    """The body of one subrecord, or ``None`` when a length or a count runs past its end."""
    if len(body) < MINIMUM:
        return None
    (component,) = struct.unpack_from("<H", body, COMPONENT_AT)
    (hole_count,) = struct.unpack_from("<H", body, HOLES_AT)
    (length,) = struct.unpack_from("<I", body, TEXT_AT)
    at = TEXT_AT + 4 + length
    if at + 4 > len(body):
        return None
    text = body[TEXT_AT + 4 : at]
    properties = PropertyRecord(body[TEXT_AT:at], parse_text(text[:-1] if text.endswith(b"\0") else text))
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
        holes.append(
            tuple(RegionVertex(*struct.unpack_from("<2d", body, at + k * PLAIN_VERTEX)) for k in range(n))
        )
        at += n * PLAIN_VERTEX
    closing = vertices.pop() if shape_based and vertices else None
    return BodyRecord(
        index=index,
        raw=raw,
        layer=body[0],
        component=None if component == NO_INDEX else component,
        properties=properties,
        outline=tuple(vertices),
        holes=tuple(holes),
        closing=closing,
        shape_based=shape_based,
        tail=body[at:],
        framed=True,
    )


def read_bodies(
    data: bytes, *, shape_based: bool = False, storage: str = "", issues: list[Issue] | None = None
) -> tuple[BodyRecord, ...]:
    """The body records of ``data``: the ``Data`` stream of ``ComponentBodies6``, of
    ``ShapeBasedComponentBodies6`` (``shape_based``), or the joined bytes of a library footprint's type 12
    primitives. A record that does not frame, a primitive of another type and the bytes after the last
    whole record are returned raw (``framed`` false), each with one ``altium.pcb-read.short-record``
    warning, so that ``encode`` gives ``data`` back."""
    where = f"{storage}/Data" if storage else "Data"
    primitives, trailing, _problems = decode_primitives(data, where=where, shape_based=shape_based)
    found: list[Issue] = []
    out: list[BodyRecord] = []

    def raw_record(raw: bytes, why: str) -> None:
        found.append(issue("altium.pcb-read.short-record", f"{why}; kept raw", f"{where}#{len(out)}"))
        out.append(BodyRecord(index=len(out), raw=raw))

    for primitive in primitives:
        if not isinstance(primitive, RawPrimitive) or primitive.type != BODY:
            raw_record(primitive.raw, "a record of another type lies among the component bodies")
            continue
        record = _frame(len(out), primitive.raw, primitive.subrecords[0], shape_based)
        if record is None:
            size = len(primitive.subrecords[0])
            raw_record(primitive.raw, f"a component body subrecord of {size} bytes does not frame")
        else:
            out.append(record)
    if trailing:
        raw_record(trailing, f"{len(trailing)} bytes after the last whole component body do not frame")
    if issues is not None:
        issues.extend(found)
    return tuple(out)


def encode(records: tuple[BodyRecord, ...] | list[BodyRecord]) -> bytes:
    """The stream the records were read from: their bytes, joined."""
    return b"".join(record.raw for record in records)


__all__ = ["TYPED_KEYS", "BodyRecord", "encode", "read_bodies"]
