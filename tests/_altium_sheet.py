# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Authored Altium sheet templates for the tests of the sheet import (change c0046, capability
sheet-templates, "Authored sheet fixtures and corpus rows").

Every template is built in memory from the records written below, with Fenolite's own encoders
(``fenolite.backends.altium.ascii``, ``binary`` and ``cfb``). No template file is read from the repository.
Every text is a special string (``=Name``), a generic word of ``WORDS`` or a one-character label; the
geometry and the values are authored for Fenolite and describe no organisation's sheet.
``tests/residue/test_template_residue.py`` checks the texts.
"""

from __future__ import annotations

import struct
import zlib
from collections.abc import Mapping, Sequence
from typing import Literal

from fenolite.backends.altium import ascii as altium_ascii
from fenolite.backends.altium import binary, cfb

Field = tuple[str, str]
Record = tuple[Field, ...]
Form = Literal["binary", "ascii"]

WORDS: frozenset[str] = frozenset(
    {"Title", "Rev", "Sheet", "of", "Date", "Drawn", "Notes", "Rev {A}", "Checked", "Number", "File"}
)
"""The generic words a label of this module may show (beside special strings and one-character labels)."""
PARAMETER_NAMES: frozenset[str] = frozenset({"Title", "Revision", "CheckedBy", "DocumentNumber"})
"""The names of the sheet-level parameters of this module: predefined special-string names only."""
IMAGE_NAME = "mark.png"
"""The name of the authored embedded image."""
LINKED_IMAGE = "C:\\art\\files\\logo.bmp"
"""An authored Windows path of a linked image; it names no real folder and is never opened."""


def _chunk(kind: bytes, body: bytes) -> bytes:
    return struct.pack(">I", len(body)) + kind + body + struct.pack(">I", zlib.crc32(kind + body))


PNG = (
    b"\x89PNG\r\n\x1a\n"
    + _chunk(b"IHDR", struct.pack(">IIBBBBB", 1, 1, 8, 0, 0, 0, 0))
    + _chunk(b"IDAT", zlib.compress(b"\x00\x80"))
    + _chunk(b"IEND", b"")
)
"""An authored PNG of one grey pixel."""
NOT_PNG = b"BM" + bytes(24)
"""Bytes that are not a PNG (they start as a bitmap file does)."""


# --- records ------------------------------------------------------------------------------------------------


def rec(kind: int, keys: Mapping[str, object] | None = None, **more: object) -> Record:
    """A record of ``kind``: ``keys`` (for names with a dot), then ``more``; ``True`` is written ``T``."""
    fields: list[Field] = [("RECORD", str(kind))]
    for key, value in {**(keys or {}), **more}.items():
        if value is None or value is False:
            continue
        fields.append((key, "T" if value is True else str(value)))
    return tuple(fields)


def sheet(**keys: object) -> Record:
    """A sheet record with one font of size 10 (no font name) unless ``keys`` say otherwise."""
    base: dict[str, object] = {"FONTIDCOUNT": 1, "SIZE1": 10, "SYSTEMFONT": 1}
    base.update(keys)
    return rec(31, base)


def _box(x1: int, y1: int, x2: int, y2: int) -> dict[str, object]:
    return {"LOCATION.X": x1, "LOCATION.Y": y1, "CORNER.X": x2, "CORNER.Y": y2}


def line(
    x1: int, y1: int, x2: int, y2: int, keys: Mapping[str, object] | None = None, **more: object
) -> Record:
    return rec(13, {**_box(x1, y1, x2, y2), **(keys or {})}, **more)


def rect(x1: int, y1: int, x2: int, y2: int, **more: object) -> Record:
    return rec(14, _box(x1, y1, x2, y2), **more)


def label(x: int, y: int, text: str, **more: object) -> Record:
    return rec(4, {"LOCATION.X": x, "LOCATION.Y": y}, FONTID=more.pop("FONTID", 1), TEXT=text, **more)


def poly(kind: int, points: Sequence[tuple[int, int]], **more: object) -> Record:
    keys: dict[str, object] = {"LOCATIONCOUNT": len(points)}
    for number, (x, y) in enumerate(points, start=1):
        keys[f"X{number}"] = x
        keys[f"Y{number}"] = y
    return rec(kind, keys, **more)


def image(x1: int, y1: int, x2: int, y2: int, **more: object) -> Record:
    return rec(30, _box(x1, y1, x2, y2), **more)


def parameter(name: str, text: str = "*") -> Record:
    return rec(41, NAME=name, TEXT=text, ISHIDDEN=True)


# --- files --------------------------------------------------------------------------------------------------


def embedded(name: str, data: bytes) -> bytes:
    """One embedded file of ``Storage`` (``schematic-records.md``, "Storage"): a binary frame holding 0xD0,
    the name behind its length byte, the 4-byte size and the zlib data."""
    packed = zlib.compress(data)
    raw = name.encode("ascii")
    payload = bytes([0xD0, len(raw)]) + raw + struct.pack("<I", len(packed)) + packed
    return struct.pack("<I", (1 << 24) | len(payload)) + payload


def build(
    records: Sequence[Record], *, form: Form = "binary", files: Mapping[str, bytes] | None = None
) -> bytes:
    """The bytes of a schematic holding ``records`` (the sheet record first). ``files`` are embedded in the
    ``Storage`` stream of the binary form; the ASCII form has no storage."""
    if form == "ascii":
        return altium_ascii.encode_records(records)
    storage = binary.storage_stream() + b"".join(embedded(n, d) for n, d in (files or {}).items())
    return cfb.write_compound(
        [
            (binary.FILE_HEADER_STREAM, binary.file_header_stream(records)),
            (binary.STORAGE_STREAM, storage),
        ]
    )


TITLE_BLOCK: tuple[Record, ...] = (
    sheet(SHEETSTYLE=0, FONTIDCOUNT=2, SIZE2=14, BOLD2=True),
    rect(750, 10, 1140, 170, LINEWIDTH=2),
    line(750, 130, 1140, 130, LINEWIDTH=1),
    line(750, 90, 1140, 90, LINEWIDTH=1),
    line(750, 50, 1140, 50, LINEWIDTH=1),
    line(950, 10, 950, 90, LINEWIDTH=1),
    line(1040, 10, 1040, 50),
    label(760, 155, "Title"),
    label(760, 136, "=Title", FONTID=2),
    label(760, 115, "Number"),
    label(760, 96, "=DocumentNumber"),
    label(760, 75, "Drawn"),
    label(760, 56, "=DrawnBy"),
    label(960, 75, "Checked"),
    label(960, 56, "=ApprovedBy"),
    label(760, 35, "Date"),
    label(760, 16, "=Date"),
    label(960, 35, "Rev"),
    label(960, 16, "=Revision"),
    label(1050, 35, "Sheet"),
    label(1050, 16, "=SheetNumber"),
    label(1085, 16, "of", JUSTIFICATION=1),
    label(1130, 16, "=SheetTotal", JUSTIFICATION=2),
    label(1130, 136, "=Organization", JUSTIFICATION=2),
    label(1130, 96, "=DocumentName", JUSTIFICATION=2),
    rect(10, 10, 1140, 750),
    label(20, 740, "A", JUSTIFICATION=6),
)
"""An A4 template with a frame and a title block at the bottom right: rectangles, lines and labels of solid
style on whole units, without colours or font names, so that its import gives no issue."""

MIXED: tuple[Record, ...] = (
    sheet(SHEETSTYLE=0),
    line(900, 10, 1140, 10, LINEWIDTH=1),
    line(900, 40, 1140, 40, LINEWIDTH=1),
    label(910, 20, "=Title"),
    rec(12, {"LOCATION.X": 500, "LOCATION.Y": 400}, RADIUS=20),
    poly(27, [(100, 100), (200, 100)]),
    parameter("Title"),
)
"""Two lines, one label, one arc, one wire and one sheet-level parameter after the sheet record."""

APPLIED: tuple[Record, ...] = (
    sheet(SHEETSTYLE=0, SHOWTEMPLATEGRAPHICS=True),
    rec(39, ISNOTACCESIBLE=True, OWNERPARTID=-1),
    line(900, 10, 1140, 10, OWNERINDEX=1),
    line(900, 40, 1140, 40, OWNERINDEX=1),
    label(910, 20, "=Title", OWNERINDEX=1),
)
"""A document with an applied template: record 1 (kind 39) owns two lines and one label."""

CASES: dict[str, tuple[tuple[Record, ...], dict[str, bytes]]] = {
    "title_block": (TITLE_BLOCK, {}),
    "mixed": (MIXED, {}),
    "applied": (APPLIED, {}),
    "no_sheet": ((line(0, 0, 10, 10),), {}),
    "a4": ((sheet(SHEETSTYLE=0),), {}),
    "no_style": ((sheet(),), {}),
    "style_18": ((sheet(SHEETSTYLE=18),), {}),
    "custom_portrait": (
        (sheet(USECUSTOMSHEET=True, CUSTOMX=1000, CUSTOMY=700, WORKSPACEORIENTATION=1),),
        {},
    ),
    "custom_ignored": ((sheet(SHEETSTYLE=1, CUSTOMX=1000, CUSTOMY=700),), {}),
    "fraction": ((sheet(SHEETSTYLE=0), line(10, 10, 100, 10, {"LOCATION.X_FRAC": 12345})), {}),
    "border_zones": (
        (
            sheet(
                USECUSTOMSHEET=True,
                CUSTOMX=1000,
                CUSTOMY=700,
                BORDERON=True,
                CUSTOMMARGINWIDTH=20,
                REFERENCEZONESON=True,
                CUSTOMXZONES=4,
                CUSTOMYZONES=2,
            ),
        ),
        {},
    ),
    "border_standard": ((sheet(SHEETSTYLE=0, BORDERON=True, TITLEBLOCKON=True),), {}),
    "line_rb": ((sheet(SHEETSTYLE=0), line(900, 10, 1140, 10, LINEWIDTH=1)), {}),
    "label_rotated": (
        (
            sheet(SHEETSTYLE=0, BOLD1=True),
            label(20, 700, "Notes", JUSTIFICATION=8, ORIENTATION=1),
        ),
        {},
    ),
    "polygon_solid": (
        (sheet(SHEETSTYLE=0), poly(7, [(100, 100), (200, 100), (150, 180)], ISSOLID=True)),
        {},
    ),
    "polyline": ((sheet(SHEETSTYLE=0), poly(6, [(900, 600), (1000, 600), (1000, 700)], LINEWIDTH=3)), {}),
    "arc": (
        (
            sheet(SHEETSTYLE=0),
            line(10, 10, 100, 10),
            line(10, 20, 100, 20),
            rec(12, {"LOCATION.X": 500, "LOCATION.Y": 400}, RADIUS=20),
        ),
        {},
    ),
    "outside": ((sheet(SHEETSTYLE=0), line(1100, 10, 1200, 10)), {}),
    "styles_dropped": (
        (
            sheet(SHEETSTYLE=0, UNDERLINE1=True),
            line(10, 10, 100, 10, LINEWIDTH=7),
            line(10, 20, 100, 20, LINESTYLE=1),
            rect(10, 30, 100, 60, ISSOLID=True),
            label(10, 70, "Notes", ISMIRRORED=True),
        ),
        {},
    ),
    "appearance": (
        (
            sheet(SHEETSTYLE=0, FONTNAME1="Times New Roman"),
            line(10, 10, 100, 10, COLOR=128),
            label(10, 70, "Notes", COLOR=128),
        ),
        {},
    ),
    "strings": (
        (
            sheet(SHEETSTYLE=0),
            label(10, 10, "=Title"),
            label(10, 30, "=documentnumber"),
            label(10, 50, "=SheetNumber"),
            label(10, 70, "=CheckedBy"),
            label(10, 90, "Rev {A}"),
        ),
        {},
    ),
    "dynamic": ((sheet(SHEETSTYLE=0), label(10, 10, "=CurrentDate")), {}),
    "spaced": ((sheet(SHEETSTYLE=0), label(10, 10, "=Drawn By")), {}),
    "image_png": (
        (sheet(SHEETSTYLE=0), image(100, 100, 300, 200, EMBEDIMAGE=True, FILENAME=IMAGE_NAME)),
        {IMAGE_NAME: PNG},
    ),
    "image_not_png": (
        (sheet(SHEETSTYLE=0), image(100, 100, 300, 200, EMBEDIMAGE=True, FILENAME=IMAGE_NAME)),
        {IMAGE_NAME: NOT_PNG},
    ),
    "image_missing": (
        (sheet(SHEETSTYLE=0), image(100, 100, 300, 200, EMBEDIMAGE=True, FILENAME=IMAGE_NAME)),
        {},
    ),
    "image_linked": ((sheet(SHEETSTYLE=0), image(100, 100, 300, 200, FILENAME=LINKED_IMAGE)), {}),
}
"""Every authored template by name: its records and the files embedded in its binary form."""


def template(name: str, *, form: Form = "binary") -> bytes:
    """The bytes of the authored template ``name`` in ``form``."""
    records, files = CASES[name]
    return build(records, form=form, files=files)


__all__ = [
    "CASES",
    "IMAGE_NAME",
    "LINKED_IMAGE",
    "NOT_PNG",
    "PARAMETER_NAMES",
    "PNG",
    "WORDS",
    "Record",
    "build",
    "embedded",
    "image",
    "label",
    "line",
    "parameter",
    "poly",
    "rec",
    "rect",
    "sheet",
    "template",
]
