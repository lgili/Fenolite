# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Deterministic candidate Draftsman shells (c0172), behind the native acceptance gate.

Only members already recorded in ``docs/formats/altium/draftsman.md`` are written. Format version 22
comes from the public corpus, not an observation of AD 26.5. Missing members deliberately keep their
data-contract defaults; whether Altium accepts those defaults is Part F's FP3, not an own-readback claim.
No board snapshot is written. The relative PCB-name binding is explicitly unconfirmed (FP4).
Native tables remain empty shells.
"""

from __future__ import annotations

import hashlib
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from decimal import Decimal, localcontext
from typing import Final, Literal
from xml.sax.saxutils import escape, quoteattr

from fenolite.backends.altium.read.draftsman import (
    CHUNK_SIZE,
    INSTANCE,
    NAMESPACE,
    DraftsmanFile,
    DraftsmanSummary,
    summary,
)
from fenolite.core.evidence import Evidence, Level

NATIVE_WRITE: Final = False
DRAFTSMAN_KIND = "altium_draftsman"
EVIDENCE = Evidence(
    Level.INFERRED,
    hypotheses=(
        "H-A-DWF-CONTAINER",
        "H-A-DWF-FIELD",
        "H-A-DWF-GEOM",
        "H-A-DWF-IMPORT",
        "H-A-DWF-KIT",
        "H-A-DWF-MINIMAL",
        "H-A-DWF-PARAMS",
        "H-A-DWF-READBACK",
        "H-A-DWF-TEMPLATE",
    ),
)
Kind = Literal[
    "Text",
    "Note",
    "BoardAssemblyViewData",
    "DrillViewView",
    "LayerStackLegendView",
    "DrillTableBoardView",
    "BillOfMaterialsView",
]
KINDS = frozenset(
    (
        "Text",
        "Note",
        "BoardAssemblyViewData",
        "DrillViewView",
        "LayerStackLegendView",
        "DrillTableBoardView",
        "BillOfMaterialsView",
    )
)
_NS = f"{{{NAMESPACE}}}"


@dataclass(frozen=True)
class DraftsmanItem:
    """An authored shell, with geometry in integer nm from the page's lower-left corner.

    ``name`` is a stable path, not a native member. Texts have one string; notes may have many. The two
    native table kinds and the legend have no guessed data-source, column, or binding members.
    """

    name: str
    kind: Kind
    at: tuple[int, int]
    size: tuple[int, int]
    title: str = ""
    texts: tuple[str, ...] = ()
    side: Literal["Top", "Bottom", "All"] = "Top"
    designators: bool = True


@dataclass(frozen=True)
class DraftsmanSheet:
    name: str
    title: str
    paper: str
    size: tuple[int, int]
    items: tuple[DraftsmanItem, ...]


@dataclass(frozen=True)
class DraftsmanSpec:
    name: str
    sheets: tuple[DraftsmanSheet, ...]
    parameters: tuple[tuple[str, str], ...] = ()
    text_size: int = 1_500_000


def units(nm: int) -> str:
    """Integer nm to the measured 1/96-inch unit, rounded far below a nanometre, without floats."""
    if type(nm) is not int:
        raise ValueError("Draftsman geometry must use integer nanometres")
    with localcontext() as ctx:
        ctx.prec = 40
        value = (Decimal(nm) * 96 / 25_400_000).quantize(Decimal("0.000000000001"))
    return format(value, "f").rstrip("0").rstrip(".") if value else "0"


def _element(parent: ET.Element, name: str, value: str | None = None) -> ET.Element:
    found = ET.SubElement(parent, _NS + name)
    found.text = value
    return found


def _point(parent: ET.Element, name: str, at: tuple[int, int]) -> None:
    point = _element(parent, name)
    for axis, nm in zip(("X", "Y"), at, strict=True):
        _element(point, axis, units(nm))


def _size(parent: ET.Element, size: tuple[int, int]) -> None:
    found = _element(parent, "Size")
    _element(found, "Height", units(size[1]))
    _element(found, "Width", units(size[0]))


def _black(parent: ET.Element, name: str) -> None:
    color = _element(parent, name)
    for channel in ("A", "B", "G", "R"):
        _element(color, channel, "255" if channel == "A" else "0")


def _identifier(name: str) -> str:
    # A conservative positive 31-bit candidate; the hash and the collision check are our choices.
    value = int.from_bytes(hashlib.sha256(("fenolite.draftsman:" + name).encode()).digest()[:4], "big")
    return str((value & 0x7FFF_FFFF) or 1)


def _item(parent: ET.Element, item: DraftsmanItem, path: str) -> None:
    found = _element(parent, "Item")
    found.set(f"{{{INSTANCE}}}type", item.kind)
    _element(found, "Id", _identifier(path))
    _element(found, "OriginatedFromTemplate", "false")
    if item.kind == "Text":
        _black(found, "Color")
        _element(found, "FontStyleId", "1")
        rect = _element(found, "Rect")
        for key, value in (
            ("Height", item.size[1]),
            ("Width", item.size[0]),
            ("X", item.at[0]),
            ("Y", item.at[1]),
        ):
            _element(rect, key, units(value))
        _element(found, "Text", item.texts[0])
    elif item.kind == "Note":
        _element(found, "ElementFontStyleId", "1")
        _black(found, "ElementTextColor")
        elements = _element(found, "Elements")
        for index, text in enumerate(item.texts):
            note = _element(elements, "NoteElement")
            _element(note, "Id", _identifier(f"{path}/{index}"))
            _element(note, "Postfix", ".")
            _element(note, "Text", text)
        # StartPoint is the note's top-left, whereas the spec consistently uses lower-left corners.
        _point(found, "StartPoint", (item.at[0], item.at[1] + item.size[1]))
        _element(found, "Title", item.title)
        _element(found, "TitleFontStyleId", "1")
        _black(found, "TitleTextColor")
        _element(found, "TitleVisible", "true" if item.title else "false")
        _element(found, "Width", units(item.size[0]))
    else:
        _point(found, "Location", item.at)
        if item.kind in ("BoardAssemblyViewData", "DrillViewView"):
            scale = _element(found, "Scale")
            _element(scale, "Denominator", "1")
            _element(scale, "Numenator", "1")
        # Legend/table sizes, data sources and filters await F0; only observed members are emitted.
        if item.kind in ("BoardAssemblyViewData", "DrillViewView"):
            _element(found, "Title", item.title)
        if item.kind == "BoardAssemblyViewData":
            display = _element(found, "DefaultComponentDisplaySettings")
            _element(display, "ShowDesignator", str(item.designators).lower())
            display = _element(found, "ViewComponentDisplaySettingsData")
            _element(display, "ComponentCaptionSource", "Designator")
        if item.kind in ("BoardAssemblyViewData", "DrillViewView", "BillOfMaterialsView"):
            _element(found, "ViewSide", item.side)


def _validate(spec: DraftsmanSpec) -> None:
    if not spec.name or not spec.sheets or spec.text_size <= 0:
        raise ValueError("a Draftsman specification needs a name and a sheet")
    paths = [spec.name]
    for sheet in spec.sheets:
        paths.append(f"{spec.name}/{sheet.name}")
        if not sheet.name or any(n <= 0 for n in sheet.size):
            raise ValueError("a sheet needs a stable name and positive dimensions")
        for item in sheet.items:
            paths.append(f"{spec.name}/{sheet.name}/{item.name}")
            if item.kind == "Note":
                paths.extend(f"{spec.name}/{sheet.name}/{item.name}/{n}" for n in range(len(item.texts)))
            if item.kind not in KINDS or not item.name or any(n <= 0 for n in item.size):
                raise ValueError("an item needs a known kind, stable name and positive dimensions")
            if item.kind == "Text" and len(item.texts) != 1:
                raise ValueError("a Text needs exactly one string")
            if item.kind == "Note" and not item.texts:
                raise ValueError("a Note needs at least one entry")
    if len(set(paths)) != len(paths) or len({_identifier(p) for p in paths}) != len(paths):
        raise ValueError("Draftsman object paths and identifiers must be unique")
    if len({name for name, _ in spec.parameters}) != len(spec.parameters):
        raise ValueError("Draftsman parameter names must be unique")
    texts = [spec.name, *(value for pair in spec.parameters for value in pair)]
    texts += [text for sheet in spec.sheets for item in sheet.items for text in (item.title, *item.texts)]
    if any(
        any(
            ord(c) < 32 and c not in "\t\r\n" or 0xD800 <= ord(c) <= 0xDFFF or ord(c) in (0xFFFE, 0xFFFF)
            for c in text
        )
        for text in texts
    ):
        raise ValueError("Draftsman text contains a character XML 1.0 cannot represent")


def _varint(value: int) -> bytes:
    out = bytearray()
    while value > 127:
        out.append((value & 127) | 128)
        value >>= 7
    out.append(value)
    return bytes(out)


def encode(text: bytes) -> bytes:
    """Encode XML as independent stored chunks of at most the measured 1 MiB length.

    Validity by Fenolite's reader is mechanical evidence only. FP1 must establish native acceptance.
    """
    if not text:
        raise ValueError("a Draftsman document cannot be empty")
    return b"".join(
        b"\0" + _varint(len(part)) + part
        for offset in range(0, len(text), CHUNK_SIZE)
        if (part := text[offset : offset + CHUNK_SIZE])
    )


def write_draftsman(spec: DraftsmanSpec) -> bytes:
    """Write a candidate shell, without opening a file or bypassing the build's closed native gate."""
    _validate(spec)
    root = ET.Element(_NS + "Document")
    _element(root, "Id", _identifier(spec.name))
    styles = _element(root, "FontStyles")
    font = _element(styles, "FontStyleData")
    _element(font, "FamilyName", "Arial")
    _element(font, "Id", "1")
    _element(font, "Size", units(spec.text_size))
    _element(root, "FormatVersion", "22")
    pages = _element(root, "Pages")
    for sheet in spec.sheets:
        path = f"{spec.name}/{sheet.name}"
        page = _element(pages, "Page")
        _element(page, "Id", _identifier(path))
        items = _element(page, "Items")
        for item in sheet.items:
            _item(items, item, f"{path}/{item.name}")
        _element(page, "SheetSizingMode", "StandardSize")
        _size(page, sheet.size)
        _element(page, "StandardSizeName", sheet.paper)
    parameters = _element(root, "Parameters")
    for name, value in spec.parameters:
        parameter = _element(parameters, "DrawingDocumentParameterData")
        _element(parameter, "Name", name)
        _element(parameter, "Value", value)
    # Relative binding is a candidate choice; the public files have absolute source paths (FP4 pending).
    _element(root, "SourceDocumentName", f"{spec.name}.PcbDoc")
    return encode(_xml(root, root=True).encode("utf-8"))


def _xml(element: ET.Element, *, root: bool = False) -> str:
    """Serialize our closed vocabulary without ElementTree's mutable global namespace registry."""
    name = element.tag.removeprefix(_NS)
    attributes = f" xmlns={quoteattr(NAMESPACE)} xmlns:i={quoteattr(INSTANCE)}" if root else ""
    for key, value in element.attrib.items():
        if key != f"{{{INSTANCE}}}type":
            raise ValueError("an unknown attribute in the candidate Draftsman tree")
        attributes += f" i:type={quoteattr(value)}"
    content = escape(element.text or "").replace("\r", "&#13;")
    content += "".join(_xml(child) for child in element)
    return f"<{name}{attributes}>{content}</{name}>"


def written_scope(root: ET.Element) -> DraftsmanSummary:
    """The reader's sheet/object/text/parameter-name scope, not a native rendering verdict."""
    return summary(DraftsmanFile((), root))


__all__ = [
    "DRAFTSMAN_KIND",
    "EVIDENCE",
    "KINDS",
    "NATIVE_WRITE",
    "DraftsmanItem",
    "DraftsmanSheet",
    "DraftsmanSpec",
    "encode",
    "units",
    "write_draftsman",
    "written_scope",
]
