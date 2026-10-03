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
ENTRY_PITCH = 100
"""One ``DISTANCEFROMTOP`` step of a sheet entry or harness entry (change c0037)."""
SYMBOL_MIN_WIDTH = 1500
"""A sheet symbol is at least this wide."""
CONNECTOR_MIN_WIDTH = 500
"""A harness connector is at least this wide."""
HARNESS_GAP = 200
"""The length of the signal harness line between a port or sheet entry and its harness connector."""
PORT_MIN_WIDTH = 300
"""A port is at least this wide."""
PORT_HEIGHT = 100
"""A port's height (``HEIGHT=10``): it reaches half of this above and below its location."""
SHEET_NAME_RISE = 100
"""A sheet symbol's name lies this far above its top-left corner; its file name lies on the corner."""


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
    entry gets no stub); ``unique_id`` is part 1's unique id and ``part_ids`` those of parts 2 … n;
    ``no_connects`` holds the designators of the pins marked as intentionally unconnected, which get a
    No ERC directive and no stub (change c0036)."""

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
    no_connects: frozenset[str] = frozenset()

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
class NoConnectMark:
    """A No ERC directive: pin ``designator`` of the component ``key`` (its path) is unconnected on
    purpose; ``at`` is the pin's electrical hot end in the layout frame."""

    key: str
    designator: str
    at: tuple[int, int]


@dataclass(frozen=True)
class Crossing:
    """A net or a harness that leaves a module's sheet (change c0037, "Sheets of a hierarchical project").

    ``name`` is the net name or the harness type name: the name of the port on the module's sheet and of
    the sheet entry on its sheet symbol. ``port_id`` is the port's unique id. ``entries`` is ``None`` for a
    net; for a harness it holds every entry of the type in code-point order, each with the name of its net
    when that net crosses the module and ``None`` when it does not."""

    name: str
    port_id: str = ""
    entries: tuple[tuple[str, str | None], ...] | None = None

    @property
    def harness(self) -> bool:
        return self.entries is not None


@dataclass(frozen=True)
class SymbolSpec:
    """The sheet symbol of a module on the top sheet: the module name (the sheet's name), the file name of
    the module's sheet, the symbol's unique id and its crossings, one sheet entry each, in order."""

    module: str
    file: str
    unique_id: str
    crossings: tuple[Crossing, ...] = ()


@dataclass(frozen=True)
class HarnessBlock:
    """A harness connector with its top-left corner at (``x``, ``y``), drawn beside a port or a sheet entry
    (change c0037, "Harness records"). ``entries`` are the type's entries in code-point order, each with
    the name of its net when it is wired; entry ``k`` (1-based) sits on the right edge, ``k`` steps of 100
    mil below the corner. ``position`` is how far below the corner the connection point lies on the left
    edge; ``line`` is the signal harness line from the port or sheet entry to that point; ``stubs`` are
    the labelled wires of the wired entries, in entry order."""

    name: str
    entries: tuple[tuple[str, str | None], ...]
    x: int
    y: int
    width: int
    height: int
    position: int
    line: tuple[tuple[int, int], tuple[int, int]]
    stubs: tuple[Stub, ...]

    def entry_point(self, k: int) -> tuple[int, int]:
        """The connection point of entry ``k`` (1-based), on the right edge."""
        return self.x + self.width, self.y + ENTRY_PITCH * k


@dataclass(frozen=True)
class PlacedEntry:
    """A sheet entry on the right side of its symbol: ``slot`` is its ``DISTANCEFROMTOP`` and ``point`` its
    connection point; a net entry has a labelled ``stub``, a harness entry a ``block``."""

    crossing: Crossing
    slot: int
    point: tuple[int, int]
    stub: Stub | None = None
    block: HarnessBlock | None = None


@dataclass(frozen=True)
class PlacedSymbol:
    """A sheet symbol with its top-left corner at (``x``, ``y``), its size, its cell and its entries."""

    spec: SymbolSpec
    x: int
    y: int
    width: int
    height: int
    cell: tuple[int, int, int, int]
    entries: tuple[PlacedEntry, ...]


@dataclass(frozen=True)
class PlacedPort:
    """A port with its left end at (``x``, ``y``), extending ``width`` rightwards, and its cell; a net port
    has a labelled ``stub`` from its right end, a harness port a ``block``."""

    crossing: Crossing
    x: int
    y: int
    width: int
    cell: tuple[int, int, int, int]
    stub: Stub | None = None
    block: HarnessBlock | None = None

    @property
    def end(self) -> tuple[int, int]:
        """The port's right end, where its wire or harness line starts."""
        return self.x + self.width, self.y


@dataclass(frozen=True)
class SheetPlan:
    """The sheet, the placed components in component-path order, the stubs in write order and the
    no-connect marks in write order. A sheet of a hierarchical project (change c0037) also holds the sheet
    symbols of a top sheet, the ports of a module sheet and their harness blocks; all three are empty on a
    single sheet."""

    size: SheetSize
    parts: tuple[PlacedPart, ...]
    stubs: tuple[Stub, ...]
    no_connects: tuple[NoConnectMark, ...] = ()
    symbols: tuple[PlacedSymbol, ...] = ()
    ports: tuple[PlacedPort, ...] = ()
    harnesses: tuple[HarnessBlock, ...] = ()

    @property
    def links(self) -> tuple[Stub, ...]:
        """The labelled wires of the sheet entries and ports, in write order: per sheet symbol and per
        entry, then per port; a harness contributes the wires of its wired entries."""
        found: list[Stub] = []
        for item in (*(entry for symbol in self.symbols for entry in symbol.entries), *self.ports):
            if item.stub is not None:
                found.append(item.stub)
            if item.block is not None:
                found.extend(item.block.stubs)
        return tuple(found)


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


def part_marks(spec: PartSpec, x: int, y: int, part: int = 1) -> tuple[NoConnectMark, ...]:
    """The no-connect marks of part ``part`` of ``spec`` with its symbol origin at (``x``, ``y``): one per
    marked pin drawn on that part (its pins and, on part 1, the Part Zero pins), in the pin order of
    ``part_stubs``, each at the pin's hot end."""
    marks: list[NoConnectMark] = []
    for pin in spec.body.pins_of(part):
        if pin.designator in spec.no_connects:
            hx, hy = pin.hot_end
            marks.append(NoConnectMark(spec.key, pin.designator, (x + hx, y - hy)))
    return tuple(marks)


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


def text_width(text: str) -> int:
    """``100 · ⌈(70 · L + 150) / 100⌉`` mil for a text of ``L`` characters, as for a label."""
    return _up(CHAR_WIDTH * len(text) + LABEL_SLACK)


def port_width(name: str) -> int:
    """``max(300, 100 · ⌈(70 · L + 150) / 100⌉)`` mil for a port name of ``L`` characters."""
    return max(PORT_MIN_WIDTH, text_width(name))


def _link(point: tuple[int, int], net: str, designator: str) -> Stub:
    """A wire rightwards from ``point`` with the label of ``net``, by the rules of a right pin."""
    how = PinNet(net, "label")
    x, y = point
    return Stub("", designator, how, "right", point, (x + stub_length(how), y), (x + LABEL_OFFSET, y))


def harness_block(crossing: Crossing, point: tuple[int, int]) -> HarnessBlock:
    """The block of the harness ``crossing`` whose signal harness line starts at ``point``: a connector of
    ``m`` entries is ``(m + 1) · 100`` mil high, its connection point ``100 · ⌊(m + 1) / 2⌋`` mil below its
    top-left corner, 200 mil right of ``point``."""
    entries = crossing.entries
    if entries is None:
        raise ValueError(f"{crossing.name} is not a harness")
    count = len(entries)
    position = ENTRY_PITCH * ((count + 1) // 2)
    x, y = point[0] + HARNESS_GAP, point[1] - position
    longest = max((crossing.name, *(entry for entry, _ in entries)), key=len)
    width = max(CONNECTOR_MIN_WIDTH, text_width(longest))
    stubs = tuple(
        _link((x + width, y + ENTRY_PITCH * k), net, entry)
        for k, (entry, net) in enumerate(entries, start=1)
        if net is not None
    )
    line = (point, (x, point[1]))
    return HarnessBlock(crossing.name, entries, x, y, width, ENTRY_PITCH * (count + 1), position, line, stubs)


def _attach(crossing: Crossing, point: tuple[int, int]) -> tuple[Stub | None, HarnessBlock | None]:
    if crossing.harness:
        return None, harness_block(crossing, point)
    return _link(point, crossing.name, crossing.name), None


def _reach(stub: Stub | None, block: HarnessBlock | None) -> tuple[int, int, int]:
    """How far the drawing of a link reaches: its right end, its top and its bottom."""
    if block is not None:
        right = max((s.end[0] for s in block.stubs), default=block.x + block.width)
        return right, block.y - TEXT_HEIGHT, block.y + block.height
    assert stub is not None
    return stub.end[0], stub.start[1] - TEXT_HEIGHT, stub.start[1]


def _cell(x0: int, y0: int, x1: int, y1: int) -> tuple[int, int, int, int]:
    return _down(x0 - CELL_MARGIN), _down(y0 - CELL_MARGIN), _up(x1 + CELL_MARGIN), _up(y1 + CELL_MARGIN)


def place_symbol(spec: SymbolSpec, x: int, y: int) -> PlacedSymbol:
    """The sheet symbol of ``spec`` with its top-left corner at (``x``, ``y``). Entries are on the right
    side, in slots of 100 mil that start at 1: a net entry takes one slot; a harness entry of ``m`` members
    takes ``m + 2`` slots and sits ``⌊(m + 1) / 2⌋`` slots below the first of them, beside its connector.
    The symbol is ``(slots + 1) · 100`` mil high, at least 1500 mil wide and wide enough for its texts."""
    names = [c.name for c in spec.crossings]
    if len(set(names)) != len(names):
        raise ValueError(f"two crossings of {spec.module} share a name")
    width = max(SYMBOL_MIN_WIDTH, text_width(max((spec.module, spec.file, *names), key=len)))
    entries: list[PlacedEntry] = []
    slot = 1
    x1, y0, y1 = x + width, y - SHEET_NAME_RISE - TEXT_HEIGHT, y
    for crossing in spec.crossings:
        count = len(crossing.entries) if crossing.entries is not None else 0
        k = slot + (count + 1) // 2 if crossing.harness else slot
        point = (x + width, y + ENTRY_PITCH * k)
        stub, block = _attach(crossing, point)
        entries.append(PlacedEntry(crossing, k, point, stub, block))
        right, top, bottom = _reach(stub, block)
        x1, y0, y1 = max(x1, right), min(y0, top), max(y1, bottom)
        slot += count + 2 if crossing.harness else 1
    height = ENTRY_PITCH * slot
    cell = _cell(x, y0, x1, max(y1, y + height))
    return PlacedSymbol(spec, x, y, width, height, cell, tuple(entries))


def place_port(crossing: Crossing, x: int, y: int) -> PlacedPort:
    """The port of ``crossing`` with its left end at (``x``, ``y``), with its stub and label or its harness
    block to its right."""
    width = port_width(crossing.name)
    stub, block = _attach(crossing, (x + width, y))
    right, top, bottom = _reach(stub, block)
    half = PORT_HEIGHT // 2
    cell = _cell(x, min(top, y - half), right, max(bottom, y + half))
    return PlacedPort(crossing, x, y, width, cell, stub, block)


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


def layout_sheet(
    parts: Sequence[PartSpec],
    *,
    symbols: Sequence[SymbolSpec] = (),
    ports: Sequence[Crossing] = (),
    sizes: Sequence[SheetSize] = SHEET_SIZES,
) -> SheetPlan:
    """Place ``parts`` in component-path order, each part of a symbol in its own consecutive cell, on the
    first of ``sizes`` that holds them, else on a custom sheet as wide as A0 (or as the widest cell plus
    the margins) and as high as needed. The sheet symbols of a top sheet (``symbols``) and the ports of a
    module sheet (``ports``) are cells of the same packing, before the component cells, in the order given
    (change c0037, "Hierarchical sheet layout")."""
    ordered = sorted(parts, key=lambda p: p.key)
    keys = [p.key for p in ordered]
    if len(set(keys)) != len(keys):
        raise ValueError("two parts share a component path")
    port_names = [c.name for c in ports]
    if len(set(port_names)) != len(port_names):
        raise ValueError("two ports share a name")
    units = [(spec, part) for spec in ordered for part in range(1, spec.body.parts + 1)]
    extents = [
        *(place_symbol(spec, 0, 0).cell for spec in symbols),
        *(place_port(crossing, 0, 0).cell for crossing in ports),
        *(_extent(spec, part) for spec, part in units),
    ]
    cells = [(x1 - x0, y1 - y0) for x0, y0, x1, y1 in extents]
    size = next((s for s in sizes if _fits(cells, s)), None)
    if size is None:
        widest = max((width for width, _ in cells), default=0)
        width = max(SHEET_SIZES[-1].width, widest + 2 * MARGIN)
        height = _pack(cells, width - 2 * MARGIN)[1]
        size = SheetSize("custom", width, _up(height + 2 * MARGIN, CUSTOM_STEP), None)
    offsets = _pack(cells, size.width - 2 * MARGIN)[0]
    origins = [
        (MARGIN + ox - x0, MARGIN + oy - y0)
        for (x0, y0, _, _), (ox, oy) in zip(extents, offsets, strict=True)
    ]
    first = len(symbols) + len(ports)
    placed_symbols = [place_symbol(spec, *at) for spec, at in zip(symbols, origins, strict=False)]
    placed_ports = [
        place_port(crossing, *at) for crossing, at in zip(ports, origins[len(symbols) : first], strict=True)
    ]
    placed: list[PlacedPart] = []
    stubs: list[Stub] = []
    marks: list[NoConnectMark] = []
    for (spec, part), (x0, y0, x1, y1), (x, y) in zip(units, extents[first:], origins[first:], strict=True):
        left, top = x + x0, y + y0
        placed.append(PlacedPart(spec, x, y, (left, top, left + x1 - x0, top + y1 - y0), part))
        stubs.extend(part_stubs(spec, x, y, part))
        marks.extend(part_marks(spec, x, y, part))
    blocks = [
        item.block
        for item in (*(entry for symbol in placed_symbols for entry in symbol.entries), *placed_ports)
        if item.block is not None
    ]
    return SheetPlan(
        size,
        tuple(placed),
        tuple(stubs),
        tuple(marks),
        tuple(placed_symbols),
        tuple(placed_ports),
        tuple(blocks),
    )


__all__ = [
    "CELL_MARGIN",
    "COMMENT_DROP",
    "CONNECTOR_MIN_WIDTH",
    "Crossing",
    "ENTRY_PITCH",
    "HARNESS_GAP",
    "HarnessBlock",
    "PORT_HEIGHT",
    "PORT_MIN_WIDTH",
    "PlacedEntry",
    "PlacedPort",
    "PlacedSymbol",
    "SHEET_NAME_RISE",
    "SYMBOL_MIN_WIDTH",
    "SymbolSpec",
    "harness_block",
    "place_port",
    "place_symbol",
    "port_width",
    "text_width",
    "DESIGNATOR_RISE",
    "LABEL_OFFSET",
    "MARGIN",
    "PORT_GAP",
    "PORT_STUB",
    "SHEET_SIZES",
    "NoConnectMark",
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
    "part_marks",
    "part_stubs",
    "stub_length",
]
