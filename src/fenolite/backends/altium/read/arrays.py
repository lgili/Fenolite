# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The Embedded Board Array records of a PCB document (``docs/formats/altium/pcb-document.md``,
"Embedded board arrays"; ``H-A-PANEL-RECORD``; change c0374).

Each array is one property record of ``EmbeddedBoards6/Data`` and ``EmbeddedBoards6/Header`` holds their
count as a 32-bit little-endian word (S-1422). This module reads what each record says: the referenced
document, the location, rotation, mirror, counts, pitches and origin mode. Placing the referenced boards'
items from these values is not measured and is not done here.
"""

# evidence: see read.pcb

from __future__ import annotations

from dataclasses import dataclass
from fractions import Fraction
from typing import TypeVar

from fenolite.backends.altium.read.cfb import is_compound, open_compound
from fenolite.backends.altium.read.pcbprops import (
    PropertyRecord,
    parse_angle,
    parse_blocks,
    parse_bool,
    parse_int,
    parse_mil,
)

HEADER = "EmbeddedBoards6/Header"
DATA = "EmbeddedBoards6/Data"
_T = TypeVar("_T")


@dataclass(frozen=True)
class BoardArray:
    """One Embedded Board Array as its record states it. Lengths are exact units of 1/10 000 mil in the
    document's own frame (Y up); ``rotation`` is in degrees, counter-clockwise."""

    document: str
    """``DOCUMENTPATH``: the referenced PCB document, relative to the panel document."""
    x: Fraction
    y: Fraction
    rotation: float
    mirrored: bool
    rows: int
    cols: int
    row_pitch: Fraction
    """``ROWSPACING``: from one copy to the next, board height plus gap (the margin folded in)."""
    col_pitch: Fraction
    linked: bool
    """Link Location to Embedded Board Origin (``ORIGINMODE`` 0)."""


class ArrayError(ValueError):
    """The ``EmbeddedBoards6`` storage holds records that do not read as arrays."""


def _array(record: PropertyRecord, index: int) -> BoardArray:
    def need(key: str, value: _T | None) -> _T:
        if value is None:
            raise ArrayError(f"array {index}: {key}={record.get(key)!r} is absent or not readable")
        return value

    origin = need("ORIGINMODE", parse_int(record.get("ORIGINMODE")))
    if origin not in (0, 1):
        raise ArrayError(f"array {index}: ORIGINMODE={origin} is neither 0 nor 1")
    rows = need("ROWCOUNT", parse_int(record.get("ROWCOUNT")))
    cols = need("COLCOUNT", parse_int(record.get("COLCOUNT")))
    if rows < 1 or cols < 1:
        raise ArrayError(f"array {index}: {rows} rows and {cols} columns")
    document = need("DOCUMENTPATH", record.get("DOCUMENTPATH") or None)
    return BoardArray(
        document=document,
        x=need("X", parse_mil(record.get("X"))),
        y=need("Y", parse_mil(record.get("Y"))),
        rotation=need("ROTATION", parse_angle(record.get("ROTATION"))),
        mirrored=need("MIRROR", parse_bool(record.get("MIRROR"))),
        rows=rows,
        cols=cols,
        row_pitch=need("ROWSPACING", parse_mil(record.get("ROWSPACING"))),
        col_pitch=need("COLSPACING", parse_mil(record.get("COLSPACING"))),
        linked=origin == 0,
    )


def board_arrays(data: bytes) -> tuple[BoardArray, ...]:
    """The arrays of the PCB document ``data``, in record order (Altium stores a later array first);
    empty for a document without arrays or that is no compound file. :class:`ArrayError` when the count
    of ``Header`` and the records differ, a block is cut, or a record lacks a key."""
    if not is_compound(data):
        return ()
    document = open_compound(data)
    header = document.read(HEADER) if HEADER in document else b""
    body = document.read(DATA) if DATA in document else b""
    count = int.from_bytes(header[:4], "little") if len(header) >= 4 else 0
    if count == 0 and not body:
        return ()
    records, trailing, issues = parse_blocks(body, where="EmbeddedBoards6")
    if trailing or issues:
        raise ArrayError(f"EmbeddedBoards6: {len(trailing)} bytes after the last whole record")
    if len(records) != count:
        raise ArrayError(f"EmbeddedBoards6: Header counts {count} arrays, Data holds {len(records)}")
    return tuple(_array(record, index) for index, record in enumerate(records))


__all__ = ["DATA", "HEADER", "ArrayError", "BoardArray", "board_arrays"]
