# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The Altium Draftsman document (``.PCBDwf``) read into its chunks and its XML tree (capability
altium-draftsman, "Draftsman document read"; change c0172).

A document is a run of chunks. Each chunk is a flag byte, the decoded length and, after the flag 1, the
stored length, both in the 7-bit form of .NET, then one LZ4 block (flag 1) or the bytes as they are
(flag 0). The joined text is one XML document of the Draftsman namespace. ``read_draftsman`` decodes it
and parses it; ``summary`` lists the sheets with their paper, and the items with their kind, side, scale,
place, title and texts, and the document parameters by name.

Facts: ``docs/formats/altium/draftsman.md``, "Container" and "Document tree". The LZ4 block decoder is
Fenolite's own, written from the public block format description (S-0803); no third-party parser or
program code was read. Reading a document into the design model is not part of this change.
"""

from __future__ import annotations

import xml.etree.ElementTree as ET
from dataclasses import dataclass

from fenolite.core.errors import FormatError
from fenolite.core.evidence import Evidence, Level

EVIDENCE = Evidence(Level.INFERRED, hypotheses=("H-A-DWF-CONTAINER", "H-A-DWF-FIELD"))

NAMESPACE = "http://schemas.datacontract.org/2004/07/Altium.Designer.PcbDrawing.DataSerialization.V1"
INSTANCE = "http://www.w3.org/2001/XMLSchema-instance"
CHUNK_SIZE = 1 << 20
"""The decoded length of every chunk but the last in the public documents (``draftsman.md``, "Container")."""
STORED, LZ4 = 0, 1
"""The two chunk flags."""
VIEW_KINDS: dict[str, str] = {
    "BoardAssemblyViewData": "board-assembly",
    "BoardFabricationViewData": "board-fabrication",
    "DrillViewView": "drill-drawing",
    "LayerStackLegendView": "layer-stack-legend",
}
"""The views by ``i:type`` (``draftsman.md``, "Document tree"; the names are confirmed by round F0)."""
TABLE_KINDS: dict[str, str] = {
    "BillOfMaterialsView": "bill-of-materials",
    "DrillTableBoardView": "drill-table",
    "TransmissionLineTableData": "transmission-line",
}
"""The tables by ``i:type``."""
NOTE_KIND, TEXT_KIND = "Note", "Text"

_NS = f"{{{NAMESPACE}}}"
_TYPE = f"{{{INSTANCE}}}type"


class DraftsmanError(FormatError):
    """Bytes that are not a Draftsman document; ``offset`` is where reading stopped (in the file, or in the
    decoded text when ``locator`` is ``text``)."""


@dataclass(frozen=True)
class Chunk:
    """One chunk: its flag, its offset in the file, the offset of its payload, its decoded and its stored
    length."""

    flag: int
    offset: int
    start: int
    size: int
    stored: int


@dataclass(frozen=True)
class DraftsmanFile:
    """A decoded document: its chunks and the root ``Document`` element."""

    chunks: tuple[Chunk, ...]
    root: ET.Element


@dataclass(frozen=True)
class ItemSummary:
    """One object of a sheet. ``role`` is ``view``, ``table``, ``note``, ``text`` or ``other``; ``name`` is
    the view or table name of ``VIEW_KINDS`` or ``TABLE_KINDS`` (else the ``i:type``). Values are the
    file's text: ``scale`` is (denominator, numerator), ``place`` is (X, Y) in 1/96 inch."""

    kind: str
    role: str
    name: str
    id: str
    from_template: bool
    side: str | None = None
    title: str | None = None
    scale: tuple[str, str] | None = None
    place: tuple[str, str] | None = None
    texts: tuple[str, ...] = ()


@dataclass(frozen=True)
class SheetSummary:
    """One sheet: its id, the standard size name, the sizing mode, the size (width, height) in 1/96 inch
    as written, and its objects in file order."""

    id: str
    paper: str
    sizing: str
    size: tuple[str, str]
    items: tuple[ItemSummary, ...]


@dataclass(frozen=True)
class DraftsmanSummary:
    """The sheets of a document, its format version and the names of its document parameters."""

    format_version: str
    sheets: tuple[SheetSummary, ...]
    parameters: tuple[str, ...]

    def items(self, role: str) -> tuple[ItemSummary, ...]:
        """Every object of ``role`` on every sheet, in order."""
        return tuple(item for sheet in self.sheets for item in sheet.items if item.role == role)


def _varint(data: bytes, at: int) -> tuple[int, int]:
    value = shift = 0
    start = at
    while True:
        if at >= len(data):
            raise DraftsmanError("a length runs past the end of the file", offset=start)
        byte = data[at]
        at += 1
        value |= (byte & 0x7F) << shift
        if not byte & 0x80:
            return value, at
        shift += 7
        if shift > 28:
            raise DraftsmanError("a length of more than five bytes", offset=start)


def chunks(data: bytes) -> tuple[Chunk, ...]:
    """The chunks of ``data`` (``draftsman.md``, "Container"); ``DraftsmanError`` when a chunk has another
    flag, runs past the end, or there is none."""
    found: list[Chunk] = []
    at = 0
    while at < len(data):
        flag = data[at]
        if flag not in (STORED, LZ4):
            raise DraftsmanError(f"chunk flag {flag} is neither 0 nor 1", offset=at)
        size, after = _varint(data, at + 1)
        stored = size
        if flag == LZ4:
            stored, after = _varint(data, after)
        if after + stored > len(data):
            raise DraftsmanError(f"a chunk of {stored} bytes runs past the end of the file", offset=at)
        found.append(Chunk(flag, at, after, size, stored))
        at = after + stored
    if not found:
        raise DraftsmanError("no chunk", offset=0)
    return tuple(found)


def _run_length(block: bytes, at: int, base: int, where: int) -> tuple[int, int]:
    length = base
    if base == 15:
        while True:
            if at >= len(block):
                raise DraftsmanError("an LZ4 length runs past the end of its block", offset=where + at)
            byte = block[at]
            at += 1
            length += byte
            if byte != 255:
                break
    return length, at


def lz4_block(block: bytes, size: int, where: int = 0) -> bytes:
    """Decode one LZ4 block (S-0803) that refers to no earlier data into ``size`` bytes; ``where`` is the
    block's offset in the file, for the error."""
    out = bytearray()
    at = 0
    while True:
        if at >= len(block):
            raise DraftsmanError("an LZ4 block ends without its last literals", offset=where + at)
        token = block[at]
        literals, at = _run_length(block, at + 1, token >> 4, where)
        if at + literals > len(block):
            raise DraftsmanError("LZ4 literals run past the end of their block", offset=where + at)
        out += block[at : at + literals]
        at += literals
        if at == len(block):
            break
        if at + 2 > len(block):
            raise DraftsmanError("an LZ4 offset runs past the end of its block", offset=where + at)
        distance = block[at] | block[at + 1] << 8
        if distance == 0 or distance > len(out):
            raise DraftsmanError(f"LZ4 offset {distance} reaches outside its block", offset=where + at)
        match, at = _run_length(block, at + 2, token & 15, where)
        match += 4
        start = len(out) - distance
        if distance >= match:
            out += out[start : start + match]
        else:
            pattern = bytes(out[start:])
            out += (pattern * (match // distance + 1))[:match]
        if len(out) > size:
            raise DraftsmanError(f"an LZ4 block decodes to more than its {size} bytes", offset=where + at)
    if len(out) != size:
        raise DraftsmanError(f"an LZ4 block decodes to {len(out)} bytes, not {size}", offset=where)
    return bytes(out)


def decode(data: bytes) -> tuple[tuple[Chunk, ...], bytes]:
    """The chunks of ``data`` and their decoded text, joined in order."""
    found = chunks(data)
    parts: list[bytes] = []
    for chunk in found:
        payload = data[chunk.start : chunk.start + chunk.stored]
        parts.append(payload if chunk.flag == STORED else lz4_block(payload, chunk.size, chunk.start))
    return found, b"".join(parts)


def _text_offset(text: bytes, line: int, column: int) -> int:
    at = 0
    for _ in range(line - 1):
        found = text.find(b"\n", at)
        if found < 0:
            return len(text)
        at = found + 1
    return at + column


def read_draftsman(data: bytes) -> DraftsmanFile:
    """Decode and parse a document; ``DraftsmanError`` when ``data`` is not one."""
    found, text = decode(data)
    try:
        root = ET.fromstring(text)
    except ET.ParseError as error:
        line, column = error.position
        offset = _text_offset(text, line, column)
        message = "the decoded text is not well-formed XML"
        raise DraftsmanError(message, locator="text", offset=offset) from None
    if root.tag != f"{_NS}Document":
        raise DraftsmanError("the root is not a Draftsman Document", locator="text", offset=0)
    return DraftsmanFile(found, root)


def _text(element: ET.Element | None, name: str) -> str | None:
    if element is None:
        return None
    child = element.find(_NS + name)
    return None if child is None else (child.text or "")


def _pair(element: ET.Element, name: str, first: str, second: str) -> tuple[str, str] | None:
    child = element.find(_NS + name)
    if child is None:
        return None
    return (_text(child, first) or "", _text(child, second) or "")


def _item(element: ET.Element) -> ItemSummary:
    kind = element.get(_TYPE, "")
    if kind in VIEW_KINDS:
        role, name = "view", VIEW_KINDS[kind]
    elif kind in TABLE_KINDS:
        role, name = "table", TABLE_KINDS[kind]
    elif kind == NOTE_KIND:
        role, name = "note", kind
    elif kind == TEXT_KIND:
        role, name = "text", kind
    else:
        role, name = "other", kind
    texts: tuple[str, ...] = ()
    if role == "note":
        elements = element.find(_NS + "Elements")
        texts = tuple(_text(entry, "Text") or "" for entry in ([] if elements is None else list(elements)))
    elif role == "text":
        texts = (_text(element, "Text") or "",)
    return ItemSummary(
        kind=kind,
        role=role,
        name=name,
        id=_text(element, "Id") or "",
        from_template=_text(element, "OriginatedFromTemplate") == "true",
        side=_text(element, "ViewSide"),
        title=_text(element, "Title"),
        scale=_pair(element, "Scale", "Denominator", "Numenator"),
        place=_pair(element, "Location", "X", "Y"),
        texts=texts,
    )


def summary(file: DraftsmanFile) -> DraftsmanSummary:
    """The sheets, objects and document parameters of ``file`` (design Decision 2)."""
    root = file.root
    sheets: list[SheetSummary] = []
    pages = root.find(_NS + "Pages")
    for page in [] if pages is None else list(pages):
        items = page.find(_NS + "Items")
        size = _pair(page, "Size", "Width", "Height") or ("", "")
        sheets.append(
            SheetSummary(
                id=_text(page, "Id") or "",
                paper=_text(page, "StandardSizeName") or "",
                sizing=_text(page, "SheetSizingMode") or "",
                size=size,
                items=tuple(_item(item) for item in ([] if items is None else list(items))),
            )
        )
    parameters = root.find(_NS + "Parameters")
    names = tuple(_text(entry, "Name") or "" for entry in ([] if parameters is None else list(parameters)))
    return DraftsmanSummary(_text(root, "FormatVersion") or "", tuple(sheets), names)


__all__ = [
    "CHUNK_SIZE",
    "EVIDENCE",
    "INSTANCE",
    "NAMESPACE",
    "TABLE_KINDS",
    "VIEW_KINDS",
    "Chunk",
    "DraftsmanError",
    "DraftsmanFile",
    "DraftsmanSummary",
    "ItemSummary",
    "SheetSummary",
    "chunks",
    "decode",
    "lz4_block",
    "read_draftsman",
    "summary",
]
