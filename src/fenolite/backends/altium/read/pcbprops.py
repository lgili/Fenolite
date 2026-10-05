# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Property text of Altium PCB files, kept byte for byte (``docs/formats/altium/pcb-read.md``,
"Property text"; change c0041).

A property block is a 32-bit word whose low 24 bits are the payload length, then the payload, whose last
byte is a NUL. The text is ``KEY=VALUE`` fields separated by ``|``, decoded as ISO-8859-1 so that every
byte is one character; a ``%UTF8%<KEY>`` field holds UTF-8 and is preferred by :meth:`PropertyRecord.get`.
"""

from __future__ import annotations

import re
import struct
from dataclasses import dataclass
from fractions import Fraction
from typing import Literal

from fenolite.core.errors import Issue, Severity

PCB_READ_ISSUE_CODES: dict[str, Severity] = {
    "altium.pcb-read.truncated": "error",
    "altium.pcb-read.unknown-type": "error",
    "altium.pcb-read.missing-stream": "error",
    "altium.pcb-read.bad-stack": "error",
    "altium.pcb-read.short-record": "warning",
    "altium.pcb-read.count-mismatch": "warning",
    "altium.pcb-read.bad-index": "warning",
    "altium.pcb-read.wrong-type": "warning",
    "altium.pcb-read.bad-frame": "warning",
    "altium.pcb-read.bad-value": "warning",
    "altium.pcb-read.unlisted-footprint": "info",
}
"""Every issue code of the PCB reader and its severity (re-exported by ``read.pcbprims``)."""

UTF8_PREFIX = "%UTF8%"
CODEC: Literal["iso-8859-1"] = "iso-8859-1"
_MIL = re.compile(r"\s*([+-]?(?:\d+(?:\.\d*)?|\.\d+))\s*mil\s*", re.IGNORECASE)
UNITS_PER_MIL = 10_000


def issue(code: str, message: str, where: str) -> Issue:
    """An issue of the PCB reader; ``message`` holds no value of the file."""
    return Issue(code, PCB_READ_ISSUE_CODES[code], message, where)


@dataclass(frozen=True, slots=True)
class PropertyRecord:
    """One property block: ``raw`` is the lead bytes, the length word and the payload with its NUL."""

    raw: bytes
    fields: tuple[tuple[str, str], ...]
    lead: bytes = b""

    def keys(self) -> tuple[str, ...]:
        return tuple(key for key, _ in self.fields)

    def get_all(self, key: str) -> tuple[str, ...]:
        """Every value of ``key``, compared without case, in order."""
        wanted = key.upper()
        return tuple(value for name, value in self.fields if name.upper() == wanted)

    def get(self, key: str) -> str | None:
        """The first value of ``key`` (without case), the decoded ``%UTF8%<key>`` value when it exists."""
        for value in self.get_all(UTF8_PREFIX + key):
            try:
                return value.encode(CODEC).decode("utf-8")
            except UnicodeDecodeError:
                break
        values = self.get_all(key)
        return values[0] if values else None

    def text(self, key: str, default: str = "") -> str:
        value = self.get(key)
        return default if value is None else value


def parse_text(text: bytes) -> tuple[tuple[str, str], ...]:
    """The fields of a property text (without its NUL): split on ``|``; a CR or LF before a ``|`` or at
    the end belongs to the separator; a non-empty piece without ``=`` is a key with an empty value."""
    out: list[tuple[str, str]] = []
    for piece in text.decode(CODEC).split("|"):
        piece = piece.rstrip("\r\n")
        if not piece:
            continue
        key, _, value = piece.partition("=")
        out.append((key, value))
    return tuple(out)


def parse_blocks(
    data: bytes, *, lead: int = 0, where: str
) -> tuple[tuple[PropertyRecord, ...], bytes, list[Issue]]:
    """Every property block of ``data``, each after ``lead`` bytes; the bytes after the last whole block
    (``trailing``) and the issues. A block that runs past the end stops the parse."""
    records: list[PropertyRecord] = []
    offset = 0
    while offset < len(data):
        head = offset + lead + 4
        if head > len(data):
            return tuple(records), data[offset:], [_cut(where, offset, len(data) - offset)]
        (word,) = struct.unpack_from("<I", data, offset + lead)
        end = head + (word & 0xFFFFFF)
        if end > len(data):
            return tuple(records), data[offset:], [_cut(where, offset, len(data) - offset)]
        payload = data[head:end]
        text = payload[:-1] if payload.endswith(b"\0") else payload
        records.append(PropertyRecord(data[offset:end], parse_text(text), data[offset : offset + lead]))
        offset = end
    return tuple(records), b"", []


def _cut(where: str, offset: int, remaining: int) -> Issue:
    return issue(
        "altium.pcb-read.truncated",
        f"a property block at byte {offset} runs past the end; {remaining} bytes kept as trailing",
        f"{where}@{offset}",
    )


def parse_mil(text: str | None) -> Fraction | None:
    """A length in mil text (``10mil``, ``-0.0001mil``) in units of 1/10 000 mil, exact; else ``None``."""
    if text is None:
        return None
    match = _MIL.fullmatch(text)
    return None if match is None else Fraction(match.group(1)) * UNITS_PER_MIL


def parse_bool(text: str | None) -> bool | None:
    """``TRUE``/``T`` and ``FALSE``/``F`` (any case); else ``None``."""
    if text is None:
        return None
    value = text.strip().upper()
    if value in ("TRUE", "T"):
        return True
    if value in ("FALSE", "F"):
        return False
    return None


def parse_int(text: str | None) -> int | None:
    """A decimal integer; else ``None``."""
    if text is None:
        return None
    try:
        return int(text.strip())
    except ValueError:
        return None


def parse_angle(text: str | None) -> float | None:
    """An angle in degrees, also in Altium's scientific form with a leading space
    (`` 2.70000000000000E+0002``); else ``None``."""
    if text is None:
        return None
    try:
        return float(text.strip())
    except ValueError:
        return None


__all__ = [
    "CODEC",
    "PCB_READ_ISSUE_CODES",
    "UNITS_PER_MIL",
    "UTF8_PREFIX",
    "PropertyRecord",
    "issue",
    "parse_angle",
    "parse_blocks",
    "parse_bool",
    "parse_int",
    "parse_mil",
    "parse_text",
]
