# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Build a neutral ``DrawingSheet`` from a ``SheetSpec`` (capability ``sheet-templates``, "Frame, reference
zones and title-block grid", "Optional logo bitmap" and "Sheets built from templates are deterministic").

Every point is anchored at a corner of the margin box, so one sheet serves every listed size. No random
generator, clock or environment value is used, and no date is produced.
"""

from __future__ import annotations

import base64
import math
import os
from pathlib import Path

from fenolite.core.errors import Issue
from fenolite.core.ids import derived_id
from fenolite.core.units import Nm
from fenolite.model.presentation import (
    Corner,
    DrawingSheet,
    SheetBitmap,
    SheetItem,
    SheetPoint,
    SheetRepeat,
    SheetSetup,
    SheetShape,
    SheetText,
)
from fenolite.templates.spec import ISSUE_CODES, SheetSpec, TemplateError, TitleBlockSpec, page_size

PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"
CELL_PAD = 1_000_000
"""Distance of a cell text from the cell's left or right border (a Fenolite choice)."""
LABEL_GAP = 500_000
"""Distance of a cell label from the cell's top border (a Fenolite choice)."""


def _issue(code: str, where: str, message: str) -> Issue:
    return Issue(code, ISSUE_CODES[code], message, where=where)


def _margin_box(spec: SheetSpec, size: str) -> tuple[Nm, Nm]:
    width, height = page_size(spec, size)  # type: ignore[arg-type]
    left, right, top, bottom = spec.margins
    return width - left - right, height - top - bottom


def _zones(spec: SheetSpec) -> list[SheetItem]:
    frame = spec.frame
    pitch, band, line, text = frame.zone_pitch, frame.zone_band, frame.zone_line_width, frame.zone_text_size
    boxes = [_margin_box(spec, size) for size in spec.sizes]
    columns = max(math.ceil(w / pitch) for w, _ in boxes)
    rows = max(math.ceil(h / pitch) for _, h in boxes)
    size = (text, text)
    items: list[SheetItem] = [
        SheetShape("rect", SheetPoint("lt", band, band), SheetPoint("rb", band, band), width=line)
    ]
    tick_x = SheetRepeat(columns - 1, step_x=pitch)
    tick_y = SheetRepeat(rows - 1, step_y=pitch)
    for corner in ("lt", "lb"):  # numbers along x on the top and bottom bands
        start, end = SheetPoint(corner, pitch, 0), SheetPoint(corner, pitch, band)
        items.append(SheetShape("line", start, end, width=line, repeat=tick_x))
        label = SheetPoint(corner, pitch // 2, band // 2)
        items.append(
            SheetText("1", label, size=size, justify="center", repeat=SheetRepeat(columns, step_x=pitch))
        )
    for corner in ("lt", "rt"):  # letters along y on the left and right bands
        start, end = SheetPoint(corner, 0, pitch), SheetPoint(corner, band, pitch)
        items.append(SheetShape("line", start, end, width=line, repeat=tick_y))
        label = SheetPoint(corner, band // 2, pitch // 2)
        items.append(
            SheetText("A", label, size=size, justify="center", repeat=SheetRepeat(rows, step_y=pitch))
        )
    return [i for i in items if not (isinstance(i, SheetShape) and i.repeat.count < 1)]


class _Grid:
    """Grid coordinates (x from the grid's left edge, y from its top edge) mapped to corner offsets."""

    def __init__(self, block: TitleBlockSpec, inset: Nm) -> None:
        self.corner: Corner = block.corner
        self.inset = inset
        self.width = sum(block.columns)
        self.height = sum(block.rows)
        self.xs = [sum(block.columns[:j]) for j in range(len(block.columns) + 1)]
        self.ys = [sum(block.rows[:i]) for i in range(len(block.rows) + 1)]

    def point(self, x: Nm, y: Nm) -> SheetPoint:
        cx = self.inset + (x if self.corner in ("lt", "lb") else self.width - x)
        cy = self.inset + (y if self.corner in ("lt", "rt") else self.height - y)
        return SheetPoint(self.corner, cx, cy)

    def line(self, x1: Nm, y1: Nm, x2: Nm, y2: Nm, width: Nm) -> SheetShape:
        return SheetShape("line", self.point(x1, y1), self.point(x2, y2), width=width)


def _title_block(spec: SheetSpec, block: TitleBlockSpec) -> list[SheetItem]:
    inset = spec.frame.zone_band if spec.frame.zones else 0
    grid = _Grid(block, inset)
    lw = block.line_width
    items: list[SheetItem] = [
        SheetShape("rect", grid.point(0, 0), grid.point(grid.width, grid.height), width=lw)
    ]
    for i in range(1, len(block.rows)):  # horizontal borders between rows (spans are horizontal only)
        items.append(grid.line(0, grid.ys[i], grid.width, grid.ys[i], lw))
    for row in range(len(block.rows)):  # vertical borders, row by row, none inside a spanned cell
        inside = {
            j for cell in block.cells if cell.row == row for j in range(cell.col + 1, cell.col + cell.span)
        }
        for j in range(1, len(block.columns)):
            if j not in inside:
                items.append(grid.line(grid.xs[j], grid.ys[row], grid.xs[j], grid.ys[row + 1], lw))
    for cell in block.cells:
        x0, x1 = grid.xs[cell.col], grid.xs[cell.col + cell.span]
        y0, y1 = grid.ys[cell.row], grid.ys[cell.row + 1]
        size = cell.font_size if cell.font_size is not None else spec.text_size
        label_band = 0
        if cell.label:
            label_band = LABEL_GAP + block.label_size
            label_y = y0 + LABEL_GAP + block.label_size // 2
            items.append(SheetText(cell.label, grid.point(x0 + CELL_PAD, label_y),
                                   size=(block.label_size, block.label_size)))  # fmt: skip
        if cell.token:
            x = {"left": x0 + CELL_PAD, "center": (x0 + x1) // 2, "right": x1 - CELL_PAD}[cell.justify]
            y = (y0 + label_band + y1) // 2
            items.append(
                SheetText(f"{{{cell.token}}}", grid.point(x, y), size=(size, size), justify=cell.justify)
            )
    return items


def _bitmap(spec: SheetSpec, base_dir: Path | None) -> SheetBitmap:
    bitmap = spec.bitmap
    assert bitmap is not None
    path = (base_dir or Path(os.curdir)) / bitmap.path
    try:
        data = path.read_bytes()
    except OSError as exc:
        raise TemplateError(
            (_issue("template.bad-value", "bitmap.path", f"cannot read {bitmap.path!r}: {exc}"),)
        ) from None
    if not data.startswith(PNG_SIGNATURE):
        raise TemplateError(
            (_issue("template.bitmap-not-png", "bitmap.path", f"{bitmap.path!r} is not a PNG file"),)
        )
    return SheetBitmap(bitmap.pos, base64.b64encode(data).decode("ascii"), scale_ppm=bitmap.scale_ppm)


def _too_wide(spec: SheetSpec, block: TitleBlockSpec, issues: list[Issue]) -> None:
    inset = spec.frame.zone_band if spec.frame.zones else 0
    width, height = sum(block.columns) + 2 * inset, sum(block.rows) + 2 * inset
    for size in spec.sizes:
        box_w, box_h = _margin_box(spec, size)
        if width > box_w or height > box_h:
            issues.append(_issue("template.too-wide", "title_block",
                                 f"the title block does not fit the margin box of {size}"))  # fmt: skip


def build_sheet(
    spec: SheetSpec, *, base_dir: Path | None = None, issues: list[Issue] | None = None
) -> DrawingSheet:
    """The drawing sheet of ``spec``: setup, frame, optional reference zones, optional title block and
    optional logo (``base_dir`` is the folder of the specification file)."""
    found = issues if issues is not None else []
    left, right, top, bottom = spec.margins
    setup = SheetSetup(
        (spec.text_size, spec.text_size), spec.line_width, spec.text_line_width, left, right, top, bottom
    )
    items: list[SheetItem] = [
        SheetShape("rect", SheetPoint("lt", 0, 0), SheetPoint("rb", 0, 0), width=spec.frame.line_width)
    ]
    if spec.frame.zones:
        items += _zones(spec)
    if spec.title_block is not None:
        _too_wide(spec, spec.title_block, found)
        items += _title_block(spec, spec.title_block)
    if spec.bitmap is not None:
        items.append(_bitmap(spec, base_dir))
    return DrawingSheet(
        id=derived_id("wks", "template", spec.name), name=spec.name, setup=setup, items=tuple(items)
    )


__all__ = ["CELL_PAD", "LABEL_GAP", "PNG_SIGNATURE", "build_sheet"]
