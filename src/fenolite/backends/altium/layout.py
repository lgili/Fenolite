# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Deterministic sheet layout: components in rows of cells, wire stubs, labels and ports (capability
altium-schematic-writer, "Deterministic sheet layout" and "Connectivity on the sheet").

Lengths are in mils, in the layout frame: X rightwards and Y downwards from the top-left corner of the
sheet's drawing area. ``schdoc`` turns Y upwards from the sheet height when it writes the records. Each
component is drawn from its library symbol (``altsym.AltiumSymbol``, Y upwards from the symbol's origin),
placed with that origin at the component's location (change c0034). Cell corners and component origins
lie on the 100-mil grid; pins may lie on the 10-mil grid. A symbol of n parts takes n consecutive cells,
one per part. The sheet sizes and the connection rules are facts of
``docs/formats/altium/schematic-ascii.md``; the cell sizes and text estimates are Fenolite choices.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Literal

from fenolite.backends.altium.altsym import DOWN, LEFT, RIGHT, UP, AltiumPin, AltiumSymbol
from fenolite.backends.altium.symbols import CHAR_WIDTH, GRID, PIN_PITCH

MARGIN = 500
"""Free border inside the drawing area, on each side."""
CELL_MARGIN = 200
"""Free border around everything a component draws, on each side of its cell."""
PORT_STUB = 200
"""A port's stub, except for the second, fourth, … port in a run of ports on adjacent pins of one edge."""
PORT_GAP = 100
"""A staggered port's connection point lies at least this far past the port above and its text."""
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


Side = Literal["left", "right", "up", "down"]
"""The way a pin points away from its body, on the sheet."""
SIDES: Mapping[int, Side] = {LEFT: "left", RIGHT: "right", UP: "up", DOWN: "down"}
STEPS: Mapping[Side, tuple[int, int]] = {"left": (-1, 0), "right": (1, 0), "up": (0, -1), "down": (0, 1)}
"""A unit step outwards in the layout frame (Y downwards)."""


@dataclass(frozen=True)
class PartSpec:
    """Everything the writer needs of one component. ``key`` is its component path; ``body`` is its
    library symbol; ``nets`` maps a pin designator to the way that pin joins its net (a pin without an
    entry gets no stub); ``unique_id`` is part 1's unique id and ``part_ids`` those of parts 2 … n."""

    key: str
    ref: str
    comment: str
    library: str
    symbol: str
    footprint: tuple[str, str] | None
    unique_id: str
    body: AltiumSymbol
    nets: Mapping[str, PinNet]
    part_ids: tuple[str, ...] = ()

    def part_id(self, part: int) -> str:
        """The unique id of part ``part`` (1-based)."""
        return self.unique_id if part == 1 else self.part_ids[part - 2]


@dataclass(frozen=True)
class PlacedPart:
    """Part ``part`` of a component, with its symbol origin at (``x``, ``y``) and its cell
    ``(x0, y0, x1, y1)``."""

    spec: PartSpec
    x: int
    y: int
    cell: tuple[int, int, int, int]
    part: int = 1

    def at(self, sx: int, sy: int) -> tuple[int, int]:
        """A symbol point (Y upwards) in the layout frame."""
        return self.x + sx, self.y - sy


@dataclass(frozen=True)
class Stub:
    """A wire from a pin's electrical end (``start``) outwards to ``end``, and the point ``mark`` where
    its net label (hotspot) or power port (connection point) sits; ``side`` is the way it points."""

    key: str
    designator: str
    net: PinNet
    side: Side
    start: tuple[int, int]
    end: tuple[int, int]
    mark: tuple[int, int]

    @property
    def length(self) -> int:
        return abs(self.end[0] - self.start[0]) + abs(self.end[1] - self.start[1])

    @property
    def vertical(self) -> bool:
        return self.side in ("up", "down")


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


def stub_length(net: PinNet, beside: Sequence[PinNet] = ()) -> int:
    """``max(300, 100 · ⌈(70 · L + 150) / 100⌉)`` for a label of ``L`` characters; 200 mil for a port, or
    ``200 + 100 · ⌈(100 + 70 · M + 100) / 100⌉`` for a port that must clear the ports ``beside`` it,
    ``M`` being their longest net name."""
    if net.kind == "label":
        return max(LABEL_STUB_MIN, _up(CHAR_WIDTH * len(net.net) + LABEL_SLACK))
    if beside:
        return PORT_STUB + _up(max(_beyond(other) for other in beside) + PORT_GAP)
    return PORT_STUB


def _beyond(net: PinNet) -> int:
    """How far a port reaches past its stub (labels stay on their stub)."""
    return PORT_ROOM + CHAR_WIDTH * len(net.net) if net.kind == "port" else 0


def _edge(pin: AltiumPin) -> tuple[int, int]:
    """A pin's edge (its direction) and its place along the edge, in mils: a lower place comes first
    (higher pins on left and right edges, pins further left on top and bottom edges)."""
    return pin.direction, (-pin.y if pin.direction in (LEFT, RIGHT) else pin.x)


def _staggered(spec: PartSpec, pins: Sequence[AltiumPin]) -> dict[str, tuple[PinNet, ...]]:
    """The ports with a long stub, each with the ports it must clear: in a run of ports on adjacent pins
    (100 mil apart) of one edge, the second, fourth, … port clears the ports before and after it."""
    ports = {
        _edge(pin): net
        for pin in pins
        if (net := spec.nets.get(pin.designator)) is not None and net.kind == "port"
    }
    long: dict[str, tuple[PinNet, ...]] = {}
    for pin in pins:
        edge, place = _edge(pin)
        if (edge, place) not in ports:
            continue
        run = 0
        while (edge, place - PIN_PITCH * (run + 1)) in ports:
            run += 1
        if run % 2 == 1:
            near = (place - PIN_PITCH, place + PIN_PITCH)
            long[pin.designator] = tuple(ports[(edge, n)] for n in near if (edge, n) in ports)
    return long


def part_stubs(spec: PartSpec, x: int, y: int, part: int = 1) -> tuple[Stub, ...]:
    """The stubs of part ``part`` of ``spec`` with its symbol origin at (``x``, ``y``): its pins and, on
    part 1, the Part Zero pins, in symbol order."""
    stubs: list[Stub] = []
    pins = spec.body.pins_of(part)
    staggered = _staggered(spec, pins)
    for pin in pins:
        net = spec.nets.get(pin.designator)
        if net is None:
            continue
        hx, hy = pin.hot_end
        start = (x + hx, y - hy)
        side = SIDES[pin.direction]
        dx, dy = STEPS[side]
        length = stub_length(net, staggered.get(pin.designator, ()))
        end = (start[0] + dx * length, start[1] + dy * length)
        if net.kind == "port" or side in ("left", "down"):
            mark = end
        else:
            mark = (start[0] + dx * LABEL_OFFSET, start[1] + dy * LABEL_OFFSET)
        stubs.append(Stub(spec.key, pin.designator, net, side, start, end, mark))
    return tuple(stubs)


def _extent(spec: PartSpec, part: int = 1) -> tuple[int, int, int, int]:
    """The cell of part ``part`` relative to its symbol origin, margins included, on the grid."""
    body = spec.body
    rect = body.rectangle(part)
    x0, x1, y0, y1 = rect.x0, rect.x1, -rect.y1, -rect.y0
    for pin in body.pins_of(part):
        hx, hy = pin.hot_end
        x0, x1, y0, y1 = min(x0, hx), max(x1, hx), min(y0, -hy), max(y1, -hy)
    for stub in part_stubs(spec, 0, 0, part):
        dx, dy = STEPS[stub.side]
        far = _beyond(stub.net)
        ex, ey = stub.end[0] + dx * far, stub.end[1] + dy * far
        x0, x1, y0, y1 = min(x0, ex), max(x1, ex), min(y0, ey), max(y1, ey)
    first = body.rectangle(1)
    x1 = max(x1, first.x0 + CHAR_WIDTH * len(spec.ref), first.x0 + CHAR_WIDTH * len(spec.comment))
    y0 = min(y0, -first.y1 - (DESIGNATOR_RISE + TEXT_HEIGHT))
    y1 = max(y1, -first.y0 + COMMENT_DROP)
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
    """Place ``parts`` in component-path order, each part of a symbol in its own consecutive cell, on the
    first of ``sizes`` that holds them, else on a custom sheet as wide as A0 (or as the widest cell plus
    the margins) and as high as needed."""
    ordered = sorted(parts, key=lambda p: p.key)
    keys = [p.key for p in ordered]
    if len(set(keys)) != len(keys):
        raise ValueError("two parts share a component path")
    units = [(spec, part) for spec in ordered for part in range(1, spec.body.parts + 1)]
    extents = [_extent(spec, part) for spec, part in units]
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
    for (spec, part), (x0, y0, x1, y1), (ox, oy) in zip(units, extents, offsets, strict=True):
        left, top = MARGIN + ox, MARGIN + oy
        x, y = left - x0, top - y0
        placed.append(PlacedPart(spec, x, y, (left, top, left + x1 - x0, top + y1 - y0), part))
        stubs.extend(part_stubs(spec, x, y, part))
    return SheetPlan(size, tuple(placed), tuple(stubs))


__all__ = [
    "CELL_MARGIN",
    "COMMENT_DROP",
    "DESIGNATOR_RISE",
    "LABEL_OFFSET",
    "MARGIN",
    "PORT_GAP",
    "PORT_STUB",
    "SHEET_SIZES",
    "PartSpec",
    "PinNet",
    "PlacedPart",
    "SIDES",
    "STEPS",
    "SheetPlan",
    "SheetSize",
    "Side",
    "Stub",
    "layout_sheet",
    "part_stubs",
    "stub_length",
]
