# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Record frames of binary streams and lines of the ASCII form (``docs/formats/altium/schematic-binary.md``).

A binary stream is a plain sequence of frames: a 4-byte little-endian word whose low 24 bits are the payload
length and whose top byte is the kind, then the payload (S-0130, S-0147, S-0148). The ASCII form holds one
record per line, ending with CR LF or LF (S-0131, S-0143).
"""

from __future__ import annotations

import struct
from collections.abc import Iterable
from dataclasses import dataclass

from fenolite.core.errors import FormatError

MAX_PAYLOAD = 0xFFFFFF


@dataclass(frozen=True, slots=True)
class Frame:
    """One framed record: ``kind`` (top byte), ``payload`` (exact bytes), ``offset`` (of its length word)."""

    kind: int
    payload: bytes
    offset: int


def deframe(stream: bytes, *, where: str, file: str = "") -> tuple[Frame, ...]:
    """Split ``stream`` into frames. A length word or a payload cut by the end of the stream raises
    ``FormatError`` located at ``<where>/record <n>`` and the offset of the length word."""
    frames: list[Frame] = []
    offset = 0
    size = len(stream)
    while offset < size:
        locator = f"{where}/record {len(frames)}"
        if offset + 4 > size:
            raise FormatError(
                f"the length word is cut: {size - offset} byte(s) left",
                file=file,
                locator=locator,
                offset=offset,
            )
        (word,) = struct.unpack_from("<I", stream, offset)
        length, kind = word & MAX_PAYLOAD, word >> 24
        end = offset + 4 + length
        if end > size:
            raise FormatError(
                f"the payload of {length} bytes is cut: {size - offset - 4} byte(s) left",
                file=file,
                locator=locator,
                offset=offset,
            )
        frames.append(Frame(kind, stream[offset + 4 : end], offset))
        offset = end
    return tuple(frames)


def enframe(frames: Iterable[Frame | tuple[int, bytes]]) -> bytes:
    """The inverse of ``deframe``: each payload behind its length word."""
    out = bytearray()
    for item in frames:
        kind, payload = (item.kind, item.payload) if isinstance(item, Frame) else item
        if len(payload) > MAX_PAYLOAD or not 0 <= kind <= 0xFF:
            raise ValueError(f"cannot frame a payload of {len(payload)} bytes with kind {kind}")
        out += struct.pack("<I", (kind << 24) | len(payload))
        out += payload
    return bytes(out)


def split_lines(data: bytes) -> tuple[bytes, ...]:
    """The lines of ``data``, each with its line end (LF, or CR LF) kept; a last line may have none."""
    lines = data.split(b"\n")
    out = [line + b"\n" for line in lines[:-1]]
    if lines[-1]:
        out.append(lines[-1])
    return tuple(out)


def line_end(line: bytes) -> bytes:
    """The line end of ``line``: ``b"\\r\\n"``, ``b"\\n"`` or ``b""``."""
    if line.endswith(b"\r\n"):
        return b"\r\n"
    if line.endswith(b"\n"):
        return b"\n"
    return b""


def join_lines(lines: Iterable[bytes]) -> bytes:
    """The inverse of ``split_lines``."""
    return b"".join(lines)


__all__ = ["MAX_PAYLOAD", "Frame", "deframe", "enframe", "join_lines", "line_end", "split_lines"]
