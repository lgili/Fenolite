# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Authored Altium schematic streams and files for the reader's tests (change c0040).

Built from ``docs/formats/altium/schematic-binary.md``, ``schematic-ascii.md``, ``schematic-library.md`` and
``schematic-records.md`` only: frames, property lists, binary pins and side streams, placed in a compound file
by the product's writer ``fenolite.backends.altium.cfb.write_compound``. Every value is authored for Fenolite.
"""

from __future__ import annotations

import struct
import zlib
from collections.abc import Iterable, Sequence

from fenolite.backends.altium.cfb import Entry, Storage, write_compound

BINARY_HEADER = "Protel for Windows - Schematic Capture Binary File Version 5.0"
ASCII_HEADER = "Protel for Windows - Schematic Capture Ascii File Version 5.0"
LIBRARY_HEADER = "Protel for Windows - Schematic Library Editor Binary File Version 5.0"
SHEET = "|RECORD=31|FONTIDCOUNT=1|SIZE1=10|FONTNAME1=Times New Roman|SYSTEMFONT=1|SHEETSTYLE=0"

Frame = tuple[int, bytes]


def text(value: str | bytes) -> bytes:
    return value if isinstance(value, bytes) else value.encode("latin-1")


def prop_frame(value: str | bytes) -> Frame:
    """A property-list frame: kind 0, the text and one NUL."""
    return (0, text(value) + b"\0")


def frame_bytes(kind: int, payload: bytes) -> bytes:
    return struct.pack("<I", (kind << 24) | len(payload)) + payload


def stream(frames: Iterable[Frame | str | bytes]) -> bytes:
    """Frames behind their length words; a ``str`` or ``bytes`` item is a property list."""
    out = bytearray()
    for item in frames:
        kind, payload = item if isinstance(item, tuple) else prop_frame(item)
        out += frame_bytes(kind, payload)
    return bytes(out)


def header(title: str = BINARY_HEADER, weight: int | None = None, extra: str = "") -> str:
    fields = f"|HEADER={title}"
    if weight is not None:
        fields += f"|WEIGHT={weight}"
    return fields + extra


def schdoc(
    records: Sequence[Frame | str | bytes],
    *,
    weight: int | None | str = "auto",
    additional: Sequence[Frame | str | bytes] | None = None,
    additional_weight: int | None | str = "auto",
    storage: bytes | None = None,
    extra: Sequence[Entry] = (),
    file_header: bytes | None = None,
) -> bytes:
    """A binary schematic: ``FileHeader`` (header and ``records``), optional ``Additional``, ``Storage``."""
    count = len(records) if weight == "auto" else weight
    assert count is None or isinstance(count, int)
    entries: list[Entry] = []
    entries.append(
        ("FileHeader", file_header if file_header is not None else stream([header(weight=count), *records]))
    )
    if additional is not None:
        add_count = len(additional) if additional_weight == "auto" else additional_weight
        assert add_count is None or isinstance(add_count, int)
        entries.append(("Additional", stream([header(weight=add_count), *additional])))
    entries.append(("Storage", storage if storage is not None else stream(["|HEADER=Icon storage"])))
    entries.extend(extra)
    return write_compound(entries)


def ascii_doc(
    lines: Sequence[str | bytes], *, eol: bytes = b"\r\n", weight: int | None | str = "auto"
) -> bytes:
    """An ASCII schematic: the header line, then ``lines``, each ending with ``eol``."""
    count = len(lines) if weight == "auto" else weight
    assert count is None or isinstance(count, int)
    head = text(header(ASCII_HEADER, count))
    return b"".join(line + eol for line in [head, *(text(line) for line in lines)])


def short(value: bytes) -> bytes:
    return bytes([len(value)]) + value


def pin_payload(
    *,
    designator: bytes = b"1",
    name: bytes = b"IN",
    part: int = 1,
    mode: int = 0,
    electrical: int = 4,
    conglomerate: int = 0x1A,
    length: int = 20,
    x: int = -30,
    y: int = 10,
    description: bytes = b"",
    formal: int = 1,
    edges: tuple[int, int, int, int] = (0, 0, 0, 0),
    color: int = 0,
    unknown: int = 0,
    strings: Sequence[bytes] = (b"", b"", b""),
) -> bytes:
    """A binary pin payload by the table "Pin fields" of ``schematic-library.md``; ``strings`` are the swap
    group, the part-and-sequence string and the default value that follow the designator (any number, 0 to
    3). The defaults give the worked pin of that page (34 bytes)."""
    out = struct.pack("<iBhB", 2, unknown, part, mode) + bytes(edges)
    out += short(description)
    out += struct.pack("<BBBhhhI", formal, electrical, conglomerate, length, x, y, color)
    out += short(name) + short(designator)
    for value in strings:
        out += short(value)
    return out


WORKED_PIN = bytes.fromhex(
    "02000000 00 0100 00 00000000 00 01 04 1a 1400 e2ff 0a00 00000000 02494e 0131 00 00 00".replace(" ", "")
)
"""The 34-byte payload of the worked pin of ``schematic-library.md``."""


def component_text(
    name: str = "PART", *, part_count: int = 2, display_modes: int = 1, extra: str = ""
) -> str:
    return (
        f"|RECORD=1|LIBREFERENCE={name}|PARTCOUNT={part_count}|DISPLAYMODECOUNT={display_modes}|OWNERPARTID=-1"
        f"|CURRENTPARTID=1{extra}"
    )


def pin_frac_stream(entries: Sequence[tuple[int, int, int, int]]) -> bytes:
    """A ``PinFrac`` stream: its header record, then per entry ``(pin index, x, y, length)`` the record 0xD0,
    the index as a short string, the size and the zlib data of three 4-byte integers."""
    frames: list[Frame | str] = [f"|HEADER=PinFrac|Weight={len(entries)}"]
    for index, x, y, length in entries:
        packed = zlib.compress(struct.pack("<3i", x, y, length))
        payload = bytes([0xD0]) + short(str(index).encode()) + struct.pack("<I", len(packed)) + packed
        frames.append((1, payload))
    return stream(frames)


def schlib(
    components: Sequence[
        tuple[str, Sequence[Frame | str | bytes]] | tuple[str, Sequence[Frame | str | bytes], Sequence[Entry]]
    ],
    *,
    header_fields: str | None = None,
    section_keys: dict[str, str] | None = None,
    extra: Sequence[Entry] = (),
    tail: bytes = b"",
) -> bytes:
    """A schematic library. ``components`` are ``(storage name, Data records[, other streams])``; the header
    lists them by storage name unless ``header_fields`` is given (then it is the whole field text after
    ``HEADER``)."""
    if header_fields is None:
        total = sum(len(item[1]) for item in components) + 1
        header_fields = (
            f"|WEIGHT={total}|FONTIDCOUNT=1|SIZE1=10|FONTNAME1=Times New Roman|COMPCOUNT={len(components)}"
        )
        for index, item in enumerate(components):
            header_fields += f"|LIBREF{index}={item[0]}|PARTCOUNT{index}=2"
    entries: list[Entry] = [("FileHeader", stream([f"|HEADER={LIBRARY_HEADER}{header_fields}"]) + tail)]
    entries.append(("Storage", stream(["|HEADER=Icon storage"])))
    if section_keys is not None:
        fields = f"|KEYCOUNT={len(section_keys)}"
        for index, (lib_ref, key) in enumerate(section_keys.items()):
            fields += f"|LIBREF{index}={lib_ref}|SECTIONKEY{index}={key}"
        entries.append(("SectionKeys", stream([fields])))
    for item in components:
        name, records = item[0], item[1]
        others: Sequence[Entry] = item[2] if len(item) == 3 else ()  # type: ignore[misc]
        entries.append(Storage(name, (("Data", stream(records)), *others)))
    entries.extend(extra)
    return write_compound(entries)


__all__ = [
    "ASCII_HEADER",
    "BINARY_HEADER",
    "LIBRARY_HEADER",
    "SHEET",
    "WORKED_PIN",
    "ascii_doc",
    "component_text",
    "frame_bytes",
    "header",
    "pin_frac_stream",
    "pin_payload",
    "prop_frame",
    "schdoc",
    "schlib",
    "short",
    "stream",
]
