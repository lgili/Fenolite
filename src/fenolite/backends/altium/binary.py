# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The binary form of an Altium schematic (change c0033, capability altium-schematic-writer, "Binary
schematic form"; ``docs/formats/altium/schematic-binary.md``).

A binary schematic is a compound file (``cfb.write_compound``) with two streams: ``FileHeader``, the binary
header record and then the records of ``schdoc.schdoc_records`` unchanged, and ``Storage``, the empty icon
storage. A sheet with a harness block (change c0037) has a third stream, ``Additional``, with its own header
record and the harness records of ``schdoc.additional_records``. Each record is framed as a 4-byte
little-endian word (payload length in the low 24 bits, type 0 in
the top byte) and the payload: the record's ASCII text (``ascii.format_record``) and one NUL that the length
counts. Both forms therefore share every key, value, order and text check; only the header text and the
framing differ. Pins stay text records.
"""

from __future__ import annotations

import struct
from collections.abc import Sequence

from fenolite.backends.altium.ascii import Field, format_record
from fenolite.backends.altium.cfb import write_compound
from fenolite.backends.altium.layout import SheetPlan
from fenolite.backends.altium.schdoc import additional_records, schdoc_records
from fenolite.core.evidence import Evidence, Level

HEADER_TEXT = "Protel for Windows - Schematic Capture Binary File Version 5.0"
"""The value of the binary header record's ``HEADER`` key."""
STORAGE_HEADER_TEXT = "Icon storage"
"""The ``HEADER`` of the one record of a ``Storage`` stream without images."""
MAX_PAYLOAD = 65535
"""The largest payload written: below 65 536 bytes every source agrees on the length word."""
PROPERTY_LIST = 0
"""The record type of a property list, in the top byte of the length word."""
FILE_HEADER_STREAM = "FileHeader"
STORAGE_STREAM = "Storage"
ADDITIONAL_STREAM = "Additional"
"""The stream of the harness records (215 to 218), written only when a sheet holds one."""
MINI_CUTOFF = 4096
"""A compound-file stream below this size lies in the mini stream (``compound-file.md``). ``FileHeader`` is
kept at this size or above, as in every sheet Altium saves (``H-A-SCHBIN-MINI``)."""
NOTE_NAME = "FenoliteNote"
NOTE_TEXT = "Fenolite: this hidden sheet parameter keeps the record stream at 4096 bytes or more"
NOTE_FILL = "."
EVIDENCE = Evidence(
    Level.INFERRED,
    hypotheses=(
        "H-A-SCHBIN-AD",
        "H-A-SCHBIN-CFB",
        "H-A-SCHBIN-FRAME",
        "H-A-SCHBIN-MINI",
        "H-A-SCHBIN-STORAGE",
        "H-A-SCHBIN-VIEWER",
    ),
)
"""The binary form is inferred from public sources until the maintainer's Viewer and Altium reports."""


def header_record(count: int) -> tuple[Field, ...]:
    """The binary header record of a stream holding ``count`` records after it."""
    if count < 0:
        raise ValueError(f"a record count cannot be negative ({count})")
    return (("HEADER", HEADER_TEXT), ("WEIGHT", str(count)))


def frame_record(fields: Sequence[Field]) -> bytes:
    """One property-list record: the length word with type 0, the record's text and its NUL."""
    payload = format_record(fields).encode("ascii") + b"\0"
    if len(payload) > MAX_PAYLOAD:
        raise ValueError(f"a record payload of {len(payload)} bytes is over {MAX_PAYLOAD} bytes")
    return struct.pack("<I", PROPERTY_LIST << 24 | len(payload)) + payload


def file_header_stream(records: Sequence[Sequence[Field]]) -> bytes:
    """The ``FileHeader`` stream: the binary header record with the record count, then every record."""
    return frame_record(header_record(len(records))) + b"".join(frame_record(r) for r in records)


def note_record(fill: int = 0) -> tuple[Field, ...]:
    """A hidden sheet parameter (record 41 without an owner, the keys of the parameters a saved sheet
    holds): the note text followed by ``fill`` filler characters."""
    if fill < 0:
        raise ValueError(f"a fill cannot be negative ({fill})")
    return (
        ("RECORD", "41"),
        ("OWNERPARTID", "-1"),
        ("COLOR", "8388608"),
        ("FONTID", "1"),
        ("ISHIDDEN", "T"),
        ("TEXT", NOTE_TEXT + NOTE_FILL * fill),
        ("NAME", NOTE_NAME),
    )


def padded_records(records: Sequence[Sequence[Field]]) -> list[Sequence[Field]]:
    """``records``, followed by one ``note_record`` when their ``FileHeader`` stream would be smaller than
    ``MINI_CUTOFF``: the note's filler is as long as needed for a stream of exactly ``MINI_CUTOFF`` bytes,
    or empty when the note alone takes the stream past it. Records of a stream of ``MINI_CUTOFF`` bytes or
    more are returned unchanged."""
    found = list(records)
    if len(file_header_stream(found)) >= MINI_CUTOFF:
        return found
    short = MINI_CUTOFF - len(file_header_stream([*found, note_record()]))
    padded = [*found, note_record(max(short, 0))]
    while len(file_header_stream(padded)) < MINI_CUTOFF:  # the count's digits may have grown by one
        short += 1
        padded = [*found, note_record(short)]
    return padded


def storage_stream() -> bytes:
    """The ``Storage`` stream without images: ``|HEADER=Icon storage`` alone, with no weight key."""
    return frame_record((("HEADER", STORAGE_HEADER_TEXT),))


def additional_stream(records: Sequence[Sequence[Field]]) -> bytes:
    """The ``Additional`` stream (change c0037): its own binary header record with the number of records
    after it, then every record, framed as those of ``FileHeader``."""
    return file_header_stream(records)


def write_schdoc_binary(plan: SheetPlan) -> bytes:
    """The bytes of the binary schematic of ``plan``; ``cfb.CompoundTooLarge`` past the size limit. The
    stream ``Additional`` is written only when the plan holds harness records, so a sheet without a harness
    keeps the two streams and the bytes of change c0033. A sheet whose ``FileHeader`` stream would lie in
    the compound file's mini stream gets one hidden sheet parameter as its last record
    (``padded_records``), so the stream is stored in regular sectors."""
    streams = [
        (FILE_HEADER_STREAM, file_header_stream(padded_records(schdoc_records(plan)))),
        (STORAGE_STREAM, storage_stream()),
    ]
    additional = additional_records(plan)
    if additional:
        streams.append((ADDITIONAL_STREAM, additional_stream(additional)))
    return write_compound(streams)


__all__ = [
    "ADDITIONAL_STREAM",
    "EVIDENCE",
    "HEADER_TEXT",
    "MAX_PAYLOAD",
    "MINI_CUTOFF",
    "NOTE_NAME",
    "NOTE_TEXT",
    "STORAGE_HEADER_TEXT",
    "additional_stream",
    "file_header_stream",
    "frame_record",
    "header_record",
    "note_record",
    "padded_records",
    "storage_stream",
    "write_schdoc_binary",
]
