# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Predict what KiCad draws for a drawing sheet on a page (capability ``sheet-templates``, "Sheet layout
prediction"). The rules follow the probes of ``tests/kicad/sheets/``: ``H-K-WKS-CORNER`` (corners),
``H-K-WKS-REPEAT`` (copies stop at the count or when a copy's start leaves the margin box; labels step)
and ``H-K-WKS-PAGE1`` (page scopes). The caller passes the page size, so no size table of a backend is
copied. All values are exact integers in nm.
"""

from __future__ import annotations

from dataclasses import dataclass

from fenolite.core.units import Nm
from fenolite.model.presentation import (
    DrawingSheet,
    SheetItem,
    SheetPoint,
    SheetSetup,
    SheetShape,
    SheetText,
    SheetToken,
    TitleBlock,
    split_tokens,
)


@dataclass(frozen=True, slots=True)
class PlacedText:
    """A drawn text: its neutral text after the label step, its anchor and its size (width, height)."""

    text: str
    x: Nm
    y: Nm
    size: tuple[Nm, Nm]


@dataclass(frozen=True, slots=True)
class PlacedLine:
    x1: Nm
    y1: Nm
    x2: Nm
    y2: Nm


@dataclass(frozen=True, slots=True)
class SheetLayout:
    texts: tuple[PlacedText, ...]
    lines: tuple[PlacedLine, ...]
    bitmaps: int


class _Page:
    def __init__(self, setup: SheetSetup, width: Nm, height: Nm) -> None:
        self.left, self.right = setup.left_margin, width - setup.right_margin
        self.top, self.bottom = setup.top_margin, height - setup.bottom_margin

    def place(self, point: SheetPoint, dx: Nm = 0, dy: Nm = 0) -> tuple[Nm, Nm]:
        """The page point of ``point`` moved by ``(dx, dy)`` in its corner frame (``H-K-WKS-CORNER``)."""
        x, y = point.x + dx, point.y + dy
        px = self.left + x if point.corner in ("lt", "lb") else self.right - x
        py = self.top + y if point.corner in ("lt", "rt") else self.bottom - y
        return px, py

    def inside(self, x: Nm, y: Nm) -> bool:
        return self.left <= x <= self.right and self.top <= y <= self.bottom


def _label(text: str, k: int, step: int) -> str:
    """A one-letter text steps through the alphabet, a number by its value (``H-K-WKS-REPEAT``)."""
    if not step or not k:
        return text
    if len(text) == 1 and text.isalpha():
        return chr(ord(text) + k * step)
    if text.isdigit():
        return str(int(text) + k * step)
    return text


def _drawn(item: SheetItem, page: int) -> bool:
    if item.scope == "first_only":
        return page == 1
    if item.scope == "not_first":
        return page != 1
    return True


def _start(item: SheetItem) -> SheetPoint:
    return item.start if isinstance(item, SheetShape) else item.pos


def layout(sheet: DrawingSheet, *, width: Nm, height: Nm, page: int = 1) -> SheetLayout:
    """The texts, lines and bitmap count of ``sheet`` drawn on a ``width`` × ``height`` page."""
    frame = _Page(sheet.setup, width, height)
    texts: list[PlacedText] = []
    lines: list[PlacedLine] = []
    bitmaps = 0
    for item in sheet.items:
        if not _drawn(item, page):
            continue
        repeat = item.repeat
        for k in range(max(repeat.count, 1)):
            dx, dy = k * repeat.step_x, k * repeat.step_y
            if not frame.inside(*frame.place(_start(item), dx, dy)):
                break
            if isinstance(item, SheetShape):
                x1, y1 = frame.place(item.start, dx, dy)
                x2, y2 = frame.place(item.end, dx, dy)
                if item.kind == "line":
                    lines.append(PlacedLine(x1, y1, x2, y2))
                else:
                    lines += [PlacedLine(x1, y1, x2, y1), PlacedLine(x2, y1, x2, y2),
                              PlacedLine(x2, y2, x1, y2), PlacedLine(x1, y2, x1, y1)]  # fmt: skip
            elif isinstance(item, SheetText):
                x, y = frame.place(item.pos, dx, dy)
                size = item.size if item.size is not None else sheet.setup.text_size
                texts.append(PlacedText(_label(item.text, k, repeat.label_step), x, y, size))
            else:
                bitmaps += 1
    return SheetLayout(tuple(texts), tuple(lines), bitmaps)


def resolve_text(
    text: str, block: TitleBlock, *, paper: str, filename: str, sheet: int = 1, sheets: int = 1
) -> str:
    """The string a neutral text shows on a board: title-block fields, the paper name as written, the
    board file name, sheet numbers and parameters (an absent parameter stays ``{param:NAME}``, as KiCad
    draws an undefined variable literally)."""
    fields = {
        "title": block.title,
        "date": block.date,
        "revision": block.revision,
        "organization": block.organization,
        "doc_id": block.doc_id,
        "responsible": block.responsible,
        "approver": block.approver,
        "paper": paper,
        "filename": filename,
        "sheet": str(sheet),
        "sheets": str(sheets),
    }
    out: list[str] = []
    for part in split_tokens(text):
        if isinstance(part, SheetToken):
            if part.param:
                out.append(block.params.get(part.name, f"{{param:{part.name}}}"))
            else:
                out.append(fields[part.name])
        else:
            out.append(part)
    return "".join(out)


__all__ = ["PlacedLine", "PlacedText", "SheetLayout", "layout", "resolve_text"]
