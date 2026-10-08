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
from typing import Literal

from fenolite.core.evidence import Evidence, Level

EVIDENCE = Evidence(Level.INFERRED, hypotheses=("H-A-SCH-LINEEND",))
"""The record text every Altium writer shares: ``INFERRED``, the level of the one row it names."""
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
FIRST_WIDE = 0xA0
"""The first character past the control codes U+007F to U+009F; from here on the code page decides."""
CODE_PAGE = "cp1252"
"""The code page of the plain values of a binary schematic that Fenolite writes (change c0086)."""
CODE_PAGE_NAME = "Windows-1252"
UTF8_PREFIX = "%UTF8%"
"""The prefix of the key that repeats a value in UTF-8 (``schematic-records.md``, "Text")."""
TextForm = Literal["ascii", "binary"]
"""The schematic form that carries a text: the ASCII form holds printable 7-bit ASCII only."""


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


def in_code_page(ch: str) -> bool:
    """Whether ``ch`` is a printable character of the code page the binary form is written in
    (``CODE_PAGE``): printable 7-bit ASCII, or a character from U+00A0 on that the code page encodes."""
    if FIRST_PRINTABLE <= ord(ch) <= LAST_PRINTABLE:
        return True
    if ord(ch) < FIRST_WIDE:
        return False
    try:
        ch.encode(CODE_PAGE)
    except UnicodeEncodeError:
        return False
    return True


def record_bytes(fields: Sequence[Field]) -> bytes:
    """One record of the binary form as bytes, without its NUL (change c0086, "Text outside ASCII"): a
    field whose value is printable 7-bit ASCII is the text of ``format_record``; a field whose value holds
    another character of ``CODE_PAGE`` is written twice, first as ``|%UTF8%<KEY>=`` and the value in
    UTF-8, then as ``|<KEY>=`` and the value in the code page (``schematic-records.md``, "Text": the twin
    holds the text, and saved files put it first). ``ValueError`` for any other value."""
    if not fields:
        raise ValueError("a record needs at least one field")
    parts: list[bytes] = []
    for key, value in fields:
        if _printable(value):
            parts.append(format_record(((key, value),)).encode("ascii"))
            continue
        if not key or not _printable(key) or any(ch in key for ch in "|= "):
            raise ValueError(f"invalid record key {key!r}")
        if not all(in_code_page(ch) for ch in value):
            raise ValueError(f"the value {value!r} of {key} holds a character outside {CODE_PAGE_NAME}")
        head = key.encode("ascii")
        parts.append(b"|" + UTF8_PREFIX.encode("ascii") + head + b"=" + value.encode("utf-8"))
        parts.append(b"|" + head + b"=" + value.encode(CODE_PAGE))
    line = b"".join(parts)
    if line.endswith(b"|>"):
        raise ValueError(f"a line must not end with '|>': {line!r}")
    return line


def text_problem(text: str, *, form: TextForm = "ascii", parameter: bool = False) -> str | None:
    """Why ``text`` cannot be written as a value, or ``None`` when it can.

    ``form`` is the schematic form that carries the value (change c0086): ``"ascii"`` accepts printable
    7-bit ASCII; ``"binary"`` also accepts every printable character of ``CODE_PAGE``, which
    ``record_bytes`` writes with its ``%UTF8%`` twin. The reason names the first character refused and
    says whether the binary form would carry it. ``parameter`` marks a parameter text (the comment, a
    parameter value), which must not start with ``=``.
    """
    if form not in ("ascii", "binary"):
        raise ValueError(f"unknown schematic form {form!r}")
    if not text:
        return "is empty"
    for ch in text:
        if ch == "|":
            return "holds the character '|', which no form can escape"
        if FIRST_PRINTABLE <= ord(ch) <= LAST_PRINTABLE:
            continue
        wide = in_code_page(ch)
        if form == "binary" and wide:
            continue
        where = f"holds the character {ch!r} (U+{ord(ch):04X})"
        if form == "binary":
            return f"{where}, outside {CODE_PAGE_NAME}, which no form carries"
        if wide:
            return (
                f"{where}, outside printable 7-bit ASCII; the binary form carries it in a comment or a "
                "parameter value"
            )
        return f"{where}, outside printable 7-bit ASCII, which no form carries"
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
    "CODE_PAGE",
    "CODE_PAGE_NAME",
    "GRID",
    "HEADER_TEXT",
    "LINE_END",
    "MILS_PER_UNIT",
    "UTF8_PREFIX",
    "Field",
    "TextForm",
    "coord_fields",
    "encode_records",
    "format_record",
    "header_record",
    "in_code_page",
    "record_bytes",
    "text_problem",
    "to_units",
]
