# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Deterministic sheet layout: components in rows of cells, wire stubs, labels and ports (capability
altium-schematic-writer, "Deterministic sheet layout" and "Connectivity on the sheet").

Every length is in mils on a 100-mil grid, in the layout frame: X rightwards and Y downwards from the
top-left corner of the sheet's drawing area. ``schdoc`` turns Y upwards from the sheet height when it
writes the records. The sheet sizes and the connection rules are facts of
``docs/formats/altium/schematic-ascii.md``; the cell sizes and text estimates are Fenolite choices.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Literal

from fenolite.backends.altium.symbols import CHAR_WIDTH, GRID, GenericSymbol, Side

MARGIN = 500
"""Free border inside the drawing area, on each side."""
CELL_MARGIN = 200
"""Free border around everything a component draws, on each side of its cell."""
PORT_STUB = 200
LABEL_STUB_MIN = 300
LABEL_SLACK = 150
"""A label stub is at least the label text plus this much, so the text stays on its own stub."""
LABEL_OFFSET = 100
"""A right pin's label hotspot lies this far from the pin's electrical end."""
PORT_ROOM = 100
"""A power port's symbol beyond its stub, besides its text."""
TEXT_HEIGHT = 100
DESIGNATOR_RISE = 100
"""The designator's location lies this far above the body's top-left corner."""
COMMENT_DROP = 200
"""The comment's location lies this far below the body's bottom-left corner."""
CUSTOM_STEP = 1000
"""A custom sheet height is rounded up to this step."""


@dataclass(frozen=True)
class SheetSize:
    """A sheet's drawing area in mils, and its ``SHEETSTYLE`` (``None`` for a custom size)."""

    name: str
    width: int
    height: int
    style: int | None


SHEET_SIZES: tuple[SheetSize, ...] = (
    SheetSize("A4", 11_500, 7_600, 0),
    SheetSize("A3", 15_500, 11_100, 1),
    SheetSize("A2", 22_300, 15_700, 2),
    SheetSize("A1", 31_500, 22_300, 3),
    SheetSize("A0", 44_600, 31_500, 4),
)
"""The ISO sheet styles 0 to 4, landscape, with their drawing areas (1150 × 760 … 4460 × 3150 units)."""


@dataclass(frozen=True)
class PinNet:
    """How a pin joins its net: a net label, or a power port of style ``ground`` or ``bar``."""

    net: str
    kind: Literal["label", "port"]
    style: Literal["ground", "bar"] | None = None


@dataclass(frozen=True)
class PartSpec:
    """Everything the writer needs of one component. ``key`` is its component path; ``nets`` maps a pin
    designator to the way that pin joins its net (a pin without an entry gets no stub)."""

    key: str
    ref: str
    comment: str
    library: str
    symbol: str
    footprint: tuple[str, str] | None
    unique_id: str
    body: GenericSymbol
    nets: Mapping[str, PinNet]


@dataclass(frozen=True)
class PlacedPart:
    """A component with its body's top-left corner at (``x``, ``y``) and its cell ``(x0, y0, x1, y1)``."""

    spec: PartSpec
    x: int
    y: int
    cell: tuple[int, int, int, int]


@dataclass(frozen=True)
class Stub:
    """A horizontal wire from a pin's electrical end (``start``) outwards to ``end``, and the point
    ``mark`` where its net label (hotspot) or power port (connection point) sits."""

    key: str
    designator: str
    net: PinNet
    side: Side
    start: tuple[int, int]
    end: tuple[int, int]
    mark: tuple[int, int]


@dataclass(frozen=True)
class SheetPlan:
    """The sheet, the placed components in component-path order, and the stubs in write order."""

    size: SheetSize
    parts: tuple[PlacedPart, ...]
    stubs: tuple[Stub, ...]


def _up(value: int, step: int = GRID) -> int:
    return -(-value // step) * step


def _down(value: int, step: int = GRID) -> int:
    return (value // step) * step


def stub_length(net: PinNet) -> int:
    """200 mil for a port; ``max(300, 100 · ⌈(70 · L + 150) / 100⌉)`` for a label of ``L`` characters."""
    if net.kind == "port":
        return PORT_STUB
    return max(LABEL_STUB_MIN, _up(CHAR_WIDTH * len(net.net) + LABEL_SLACK))


def _beyond(net: PinNet) -> int:
    """How far a port reaches past its stub (labels stay on their stub)."""
    return PORT_ROOM + CHAR_WIDTH * len(net.net) if net.kind == "port" else 0


def part_stubs(spec: PartSpec, x: int, y: int) -> tuple[Stub, ...]:
    """The stubs of ``spec`` with its body's top-left corner at (``x``, ``y``), pins in natural order."""
    stubs: list[Stub] = []
    width = spec.body.width
    for pin in spec.body.pins:
        net = spec.nets.get(pin.designator)
        if net is None:
            continue
        hx, hy = pin.hot_end(width)
        start = (x + hx, y + hy)
        length = stub_length(net)
        if pin.side == "left":
            end = (start[0] - length, start[1])
            mark = end
        else:
            end = (start[0] + length, start[1])
            mark = end if net.kind == "port" else (start[0] + LABEL_OFFSET, start[1])
        stubs.append(Stub(spec.key, pin.designator, net, pin.side, start, end, mark))
    return tuple(stubs)


def _extent(spec: PartSpec) -> tuple[int, int, int, int]:
    """The cell of ``spec`` relative to its body's top-left corner, margins included, on the grid."""
    body = spec.body
    x0, x1 = 0, body.width
    for pin in body.pins:
        hx = pin.hot_end(body.width)[0]
        x0, x1 = min(x0, hx), max(x1, hx)
    for stub in part_stubs(spec, 0, 0):
        if stub.side == "left":
            x0 = min(x0, stub.end[0] - _beyond(stub.net))
        else:
            x1 = max(x1, stub.end[0] + _beyond(stub.net))
    x1 = max(x1, CHAR_WIDTH * len(spec.ref), CHAR_WIDTH * len(spec.comment))
    y0 = -(DESIGNATOR_RISE + TEXT_HEIGHT)
    y1 = body.height + COMMENT_DROP
    return (
        _down(x0 - CELL_MARGIN),
        _down(y0 - CELL_MARGIN),
        _up(x1 + CELL_MARGIN),
        _up(y1 + CELL_MARGIN),
    )


def _pack(cells: Sequence[tuple[int, int]], usable_width: int) -> tuple[list[tuple[int, int]], int]:
    """Shelf packing: each cell's (left, top) offset, left to right and top to bottom, and the height."""
    offsets: list[tuple[int, int]] = []
    x = top = row_height = 0
    for width, height in cells:
        if x > 0 and x + width > usable_width:
            top += row_height
            x = row_height = 0
        offsets.append((x, top))
        x += width
        row_height = max(row_height, height)
    return offsets, top + row_height


def _fits(cells: Sequence[tuple[int, int]], size: SheetSize) -> bool:
    usable_width = size.width - 2 * MARGIN
    if any(width > usable_width for width, _ in cells):
        return False
    return _pack(cells, usable_width)[1] <= size.height - 2 * MARGIN


def layout_sheet(parts: Sequence[PartSpec], *, sizes: Sequence[SheetSize] = SHEET_SIZES) -> SheetPlan:
    """Place ``parts`` in component-path order on the first of ``sizes`` that holds them, else on a
    custom sheet as wide as A0 (or as the widest cell plus the margins) and as high as needed."""
    ordered = sorted(parts, key=lambda p: p.key)
    keys = [p.key for p in ordered]
    if len(set(keys)) != len(keys):
        raise ValueError("two parts share a component path")
    extents = [_extent(p) for p in ordered]
    cells = [(x1 - x0, y1 - y0) for x0, y0, x1, y1 in extents]
    size = next((s for s in sizes if _fits(cells, s)), None)
    if size is None:
        widest = max((width for width, _ in cells), default=0)
        width = max(SHEET_SIZES[-1].width, widest + 2 * MARGIN)
        height = _pack(cells, width - 2 * MARGIN)[1]
        size = SheetSize("custom", width, _up(height + 2 * MARGIN, CUSTOM_STEP), None)
    offsets = _pack(cells, size.width - 2 * MARGIN)[0]
    placed: list[PlacedPart] = []
    stubs: list[Stub] = []
    for spec, (x0, y0, x1, y1), (ox, oy) in zip(ordered, extents, offsets, strict=True):
        left, top = MARGIN + ox, MARGIN + oy
        x, y = left - x0, top - y0
        placed.append(PlacedPart(spec, x, y, (left, top, left + x1 - x0, top + y1 - y0)))
        stubs.extend(part_stubs(spec, x, y))
    return SheetPlan(size, tuple(placed), tuple(stubs))


__all__ = [
    "CELL_MARGIN",
    "COMMENT_DROP",
    "DESIGNATOR_RISE",
    "LABEL_OFFSET",
    "MARGIN",
    "SHEET_SIZES",
    "PartSpec",
    "PinNet",
    "PlacedPart",
    "SheetPlan",
    "SheetSize",
    "Stub",
    "layout_sheet",
    "part_stubs",
    "stub_length",
]
