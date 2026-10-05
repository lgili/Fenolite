# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Binary pin records (``docs/formats/altium/schematic-library.md``, "Pin fields").

A binary pin payload holds fixed little-endian fields, the description, three fixed bytes and three integers,
then up to five short strings: name, designator, swap group, part and sequence, default value (S-0131, S-0148,
S-0150 version 1). The strings after the designator are optional from the end, and any byte after the last
known field is kept in ``tail``. ``encode_pin`` rebuilds the payload from the decoded fields.
"""

from __future__ import annotations

import struct
from typing import Literal

from fenolite.backends.altium.read.sch.props import DEFAULT_CODEPAGE
from fenolite.backends.altium.read.sch.records import Pin, PinFields, RecordRef

PIN_RECORD_ID = 2
FIXED_HEAD = struct.Struct("<iBhBBBBB")
"""Record id, unknown byte, owner part, display mode, inner edge, outer edge, inside, outside: 12 bytes."""
FIXED_BODY = struct.Struct("<BBBhhhI")
"""Formal type, electrical type, conglomerate, length, X, Y, colour: 13 bytes."""
OPTIONAL_STRINGS = 3

PinDecode = PinFields | Literal["not-pin", "malformed"]


def _short(payload: bytes, offset: int) -> tuple[bytes, int] | None:
    """A short string at ``offset`` and the offset after it, or ``None`` when it is cut."""
    if offset >= len(payload):
        return None
    end = offset + 1 + payload[offset]
    if end > len(payload):
        return None
    return payload[offset + 1 : end], end


def decode_fields(payload: bytes, *, codepage: str = DEFAULT_CODEPAGE) -> PinDecode:
    """The fields of a binary pin payload; ``"not-pin"`` when its record id is not 2, ``"malformed"`` when it
    is cut inside a fixed field, the description, the name or the designator."""
    if len(payload) < 4:
        return "malformed"
    (record_id,) = struct.unpack_from("<i", payload, 0)
    if record_id != PIN_RECORD_ID:
        return "not-pin"
    if len(payload) < FIXED_HEAD.size:
        return "malformed"
    _, unknown, part, mode, inner, outer, inside, outside = FIXED_HEAD.unpack_from(payload, 0)
    description = _short(payload, FIXED_HEAD.size)
    if description is None:
        return "malformed"
    text, offset = description
    if offset + FIXED_BODY.size > len(payload):
        return "malformed"
    formal, electrical, conglomerate, length, x, y, color = FIXED_BODY.unpack_from(payload, offset)
    offset += FIXED_BODY.size
    required: list[bytes] = []
    for _ in range(2):
        found = _short(payload, offset)
        if found is None:
            return "malformed"
        value, offset = found
        required.append(value)
    optional: list[bytes] = []
    for _ in range(OPTIONAL_STRINGS):
        if offset >= len(payload):
            break
        found = _short(payload, offset)
        if found is None:
            break
        value, offset = found
        optional.append(value)
    strings_read = 2 + len(optional)
    optional += [b""] * (OPTIONAL_STRINGS - len(optional))
    return PinFields(
        record_id,
        unknown,
        part,
        mode,
        inner,
        outer,
        inside,
        outside,
        text,
        formal,
        electrical,
        conglomerate,
        length,
        x,
        y,
        color,
        required[0],
        required[1],
        optional[0],
        optional[1],
        optional[2],
        strings_read,
        payload[offset:],
        codepage,
    )


def decode_pin(
    payload: bytes,
    *,
    ref: RecordRef | None = None,
    offset: int = 0,
    kind: int = 1,
    codepage: str = DEFAULT_CODEPAGE,
) -> Pin | None:
    """A ``Pin`` record from a binary pin payload, or ``None`` when the payload is not a well-formed pin."""
    fields = decode_fields(payload, codepage=codepage)
    if isinstance(fields, str):
        return None
    return Pin(ref or RecordRef("data", 0), kind, payload, offset, None, pin_fields=fields)


def _pack_short(value: bytes) -> bytes:
    if len(value) > 0xFF:
        raise ValueError("a short string holds at most 255 bytes")
    return bytes([len(value)]) + value


def encode_fields(fields: PinFields) -> bytes:
    """The payload of ``fields``: the fixed fields, the present strings and the tail."""
    out = bytearray(
        FIXED_HEAD.pack(
            fields.record_id,
            fields.unknown_byte,
            fields.owner_part,
            fields.display_mode,
            fields.inner_edge,
            fields.outer_edge,
            fields.inside,
            fields.outside,
        )
    )
    out += _pack_short(fields.description)
    out += FIXED_BODY.pack(
        fields.formal_type,
        fields.electrical,
        fields.conglomerate,
        fields.length,
        fields.x,
        fields.y,
        fields.color,
    )
    strings = (
        fields.name,
        fields.designator,
        fields.swap_group,
        fields.part_and_sequence,
        fields.default_value,
    )
    for value in strings[: fields.strings_read]:
        out += _pack_short(value)
    out += fields.tail
    return bytes(out)


def encode_pin(pin: Pin | PinFields) -> bytes:
    """The payload a binary pin was read from, rebuilt from its fields."""
    fields = pin if isinstance(pin, PinFields) else pin.pin_fields
    if fields is None:
        raise ValueError("encode_pin needs a binary pin")
    return encode_fields(fields)


__all__ = ["PIN_RECORD_ID", "PinDecode", "decode_fields", "decode_pin", "encode_fields", "encode_pin"]
