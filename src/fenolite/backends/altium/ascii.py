# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The ASCII form of an Altium schematic: records as lines of ``|KEY=VALUE`` fields
(``docs/formats/altium/schematic-ascii.md``, "File form" and "Units, axes and colours").

A record is a sequence of ``(key, value)`` fields in the order they are written. ``encode_records`` puts
the header record first, with the number of records after it, ends every line with CR LF and checks
that every byte is printable 7-bit ASCII. Texts that the form cannot carry are refused, never escaped
or replaced (``text_problem``). Lengths are passed in mils on the 10-mil grid (library pins may sit on
a 50-mil grid, change c0034) and written in the file's unit of 10 mil, so no ``_FRAC`` key is needed.
"""

from __future__ import annotations

from collections.abc import Sequence

Field = tuple[str, str]
"""One ``|KEY=VALUE`` field of a record."""

HEADER_TEXT = "Protel for Windows - Schematic Capture Ascii File Version 5.0"
"""The value of the header record's ``HEADER`` key."""
LINE_END = b"\r\n"
"""Every line, the last one included, ends with CR LF (a Fenolite choice, ``H-A-SCH-LINEEND``)."""
MILS_PER_UNIT = 10
"""A file length unit is 10 mil."""
GRID = 10
"""Every length the writer passes is a multiple of 10 mil, so no ``_FRAC`` key is ever needed."""
FIRST_PRINTABLE = 0x20
LAST_PRINTABLE = 0x7E


def header_record(count: int) -> tuple[Field, ...]:
    """The header record of a file holding ``count`` records after it."""
    if count < 0:
        raise ValueError(f"a record count cannot be negative ({count})")
    return (("HEADER", HEADER_TEXT), ("WEIGHT", str(count)))


def _printable(text: str) -> bool:
    return all(FIRST_PRINTABLE <= ord(ch) <= LAST_PRINTABLE for ch in text)


def format_record(fields: Sequence[Field]) -> str:
    """One record as its line, without the line end: ``|KEY=VALUE`` per field, no trailing ``|``."""
    if not fields:
        raise ValueError("a record needs at least one field")
    parts: list[str] = []
    for key, value in fields:
        if not key or not _printable(key) or any(ch in key for ch in "|= "):
            raise ValueError(f"invalid record key {key!r}")
        if not _printable(value) or "|" in value:
            raise ValueError(f"the value {value!r} of {key} is not printable 7-bit ASCII without '|'")
        parts.append(f"|{key}={value}")
    line = "".join(parts)
    if line.endswith("|>"):
        raise ValueError(f"a line must not end with '|>': {line!r}")
    return line


def encode_records(records: Sequence[Sequence[Field]]) -> bytes:
    """The file bytes: the header record with the record count, then one line per record, CR LF ends."""
    lines = [format_record(header_record(len(records))), *(format_record(r) for r in records)]
    return b"".join(line.encode("ascii") + LINE_END for line in lines)


def text_problem(text: str, *, parameter: bool = False) -> str | None:
    """Why ``text`` cannot be written as a value, or ``None`` when it can.

    ``parameter`` marks a parameter text (the comment), which must not start with ``=``.
    """
    if not text:
        return "is empty"
    for ch in text:
        if ch == "|":
            return "holds the character '|', which the ASCII form cannot escape"
        if not FIRST_PRINTABLE <= ord(ch) <= LAST_PRINTABLE:
            return f"holds the character {ch!r} (U+{ord(ch):04X}), outside printable 7-bit ASCII"
    if text != text.strip(" "):
        return "starts or ends with a space, which readers trim"
    if parameter and text.startswith("="):
        return "starts with '=', which Altium reads as a reference to another parameter"
    return None


def to_units(mils: int) -> int:
    """A length in mils as file units of 10 mil; ``ValueError`` when negative or off the 10-mil grid."""
    if mils < 0 or mils % GRID:
        raise ValueError(f"{mils} mil is not a non-negative multiple of {GRID} mil")
    return mils // MILS_PER_UNIT


def coord_fields(name: str, x: int, y: int) -> tuple[Field, Field]:
    """The fields ``<name>.X`` and ``<name>.Y`` of a point given in mils in the file frame (Y upwards)."""
    return ((f"{name}.X", str(to_units(x))), (f"{name}.Y", str(to_units(y))))


__all__ = [
    "GRID",
    "HEADER_TEXT",
    "LINE_END",
    "MILS_PER_UNIT",
    "Field",
    "coord_fields",
    "encode_records",
    "format_record",
    "header_record",
    "text_problem",
    "to_units",
]
