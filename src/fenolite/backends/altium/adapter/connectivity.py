# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The local nets of one schematic sheet, from its geometry (capability altium-import, "Connectivity
within a sheet"; ``docs/formats/altium/connectivity.md``; change c0043).

All arithmetic is on ``SchLength.value``, an integer count of 1/100 000 of the 10-mil unit. "Lies on a
segment" is a zero cross product and a position inside the segment's box: no tolerance is used. Wires
connect at a wire end on another wire, at a junction and where collinear segments overlap; an electrical
point connects to the wires it lies on and to the points at its position. Buses, bus entries and signal
harness lines are not wires.
"""

from __future__ import annotations

import re
from collections.abc import Hashable, Iterable, Sequence
from dataclasses import dataclass

from fenolite.backends.altium.adapter.parts import PartGroup, locator, order, part_groups
from fenolite.backends.altium.read.sch import (
    HarnessConnector,
    HarnessEntry,
    NetLabel,
    Port,
    SchDocument,
    SchLength,
    SchRecord,
    SheetEntry,
    SheetSymbol,
    SignalHarness,
)
from fenolite.geometry.index import SpatialIndex
from fenolite.geometry.shapes import BBox

Pt = tuple[int, int]
BUS_FORM = re.compile(r"\s*(.*?)\[\s*(\d+)\s*\.\.\s*(\d+)\s*\]\s*")
VERTICAL_PORT_STYLES = frozenset({4, 5, 6, 7})
SIDE_LEFT, SIDE_RIGHT, SIDE_TOP = 0, 1, 2


def on_segment(p: Pt, a: Pt, b: Pt) -> bool:
    """Whether ``p`` lies on the segment from ``a`` to ``b``, its ends included: a zero cross product and a
    position inside the segment's box."""
    (x, y), (x1, y1), (x2, y2) = p, a, b
    if (x2 - x1) * (y - y1) - (y2 - y1) * (x - x1) != 0:
        return False
    return min(x1, x2) <= x <= max(x1, x2) and min(y1, y2) <= y <= max(y1, y2)


def bus_range(text: str) -> tuple[str, tuple[int, ...]] | None:
    """The name and the member indexes, in order, of a bus identifier ``<name>[<a>..<b>]``; ``None`` for a
    text of another form."""
    match = BUS_FORM.fullmatch(text)
    if match is None or not match.group(1).strip():
        return None
    first, last = int(match.group(2)), int(match.group(3))
    step = 1 if last >= first else -1
    return match.group(1).strip(), tuple(range(first, last + step, step))


class Union:
    """A union-find over hashable nodes; a node exists once it was named."""

    def __init__(self) -> None:
        self._parent: dict[Hashable, Hashable] = {}

    def find(self, node: Hashable) -> Hashable:
        parent = self._parent
        parent.setdefault(node, node)
        root = node
        while parent[root] != root:
            root = parent[root]
        while parent[node] != root:
            parent[node], node = root, parent[node]
        return root

    def join(self, a: Hashable, b: Hashable) -> None:
        ra, rb = self.find(a), self.find(b)
        if ra != rb:
            self._parent[rb] = ra

    def nodes(self) -> tuple[Hashable, ...]:
        return tuple(self._parent)


def pt(point: tuple[SchLength, SchLength]) -> Pt:
    """A reader's point as integers."""
    return (point[0].value, point[1].value)


def _box(a: Pt, b: Pt) -> BBox:
    return BBox(min(a[0], b[0]), min(a[1], b[1]), max(a[0], b[0]), max(a[1], b[1]))


class Lines:
    """A set of polylines (wires, bus lines or signal harness lines) with an index of their segments."""

    def __init__(self, lines: Sequence[Sequence[Pt]]) -> None:
        self.lines = [list(line) for line in lines]
        self.segments: list[tuple[int, Pt, Pt]] = []
        for number, line in enumerate(self.lines):
            if len(line) == 1:
                self.segments.append((number, line[0], line[0]))
            self.segments += [(number, a, b) for a, b in zip(line, line[1:], strict=False)]
        boxes = [(_box(a, b), i) for i, (_n, a, b) in enumerate(self.segments)]
        self._index = SpatialIndex[int].build(boxes)

    def at(self, point: Pt) -> list[int]:
        """The lines that have a segment through ``point``, without repeats, in line order."""
        found = {
            self.segments[i][0]
            for i in self._index.query(BBox(point[0], point[1], point[0], point[1]))
            if on_segment(point, self.segments[i][1], self.segments[i][2])
        }
        return sorted(found)

    def groups(self, junctions: Iterable[Pt] = ()) -> list[int]:
        """Per line, the number of its group: lines connect when an end of one lies on a segment of
        another, when a junction lies on both, and when collinear segments overlap."""
        union = Union()
        for number, line in enumerate(self.lines):
            union.find(number)
            for end in (line[0], line[-1]) if line else ():
                for other in self.at(end):
                    union.join(number, other)
        for junction in junctions:
            touching = self.at(junction)
            for other in touching[1:]:
                union.join(touching[0], other)
        for i, (number, a, b) in enumerate(self.segments):
            if a == b:
                continue
            for j in self._index.query(_box(a, b)):
                other, c, d = self.segments[j]
                if j <= i or other == number or c == d:
                    continue
                collinear = (b[0] - a[0]) * (c[1] - a[1]) == (b[1] - a[1]) * (c[0] - a[0]) and (
                    b[0] - a[0]
                ) * (d[1] - a[1]) == (b[1] - a[1]) * (d[0] - a[0])
                if collinear and (on_segment(c, a, b) or on_segment(d, a, b) or on_segment(a, c, d)):
                    union.join(number, other)
        roots: dict[Hashable, int] = {}
        return [roots.setdefault(union.find(number), len(roots)) for number in range(len(self.lines))]


def side_point(corner: Pt, x_size: int, y_size: int, side: int, distance: int) -> Pt:
    """The point on the edge ``side`` (0 left, 1 right, 2 top, 3 bottom) of a box whose ``corner`` is its
    top-left corner, ``distance`` from that corner along the edge (Y points up)."""
    x, y = corner
    if side == SIDE_LEFT:
        return (x, y - distance)
    if side == SIDE_RIGHT:
        return (x + x_size, y - distance)
    if side == SIDE_TOP:
        return (x + distance, y)
    return (x + distance, y - y_size)


def port_ends(port: Port) -> tuple[Pt, Pt]:
    """The two electrical points of a port: its location and the point ``WIDTH`` further along it, along Y
    for the vertical styles (4 to 7) and along X otherwise."""
    x, y = pt(port.location)
    width = port.width.value
    return ((x, y), (x, y + width) if port.style in VERTICAL_PORT_STYLES else (x + width, y))


def entry_point(document: SchDocument, entry: SheetEntry | HarnessEntry) -> Pt | None:
    """The electrical point of a sheet entry or a harness entry on its owner's edge; ``None`` when its
    owner is no box."""
    owner = document.owner_of(entry)
    if not isinstance(owner, SheetSymbol | HarnessConnector):
        return None
    return side_point(
        pt(owner.location), owner.x_size.value, owner.y_size.value, entry.side, entry.distance.value
    )


def connector_point(connector: HarnessConnector) -> Pt:
    """The connection point of a harness connector, on the side it names."""
    return side_point(
        pt(connector.location),
        connector.x_size.value,
        connector.y_size.value,
        connector.side,
        connector.primary_position.value,
    )


@dataclass(frozen=True, slots=True)
class Ident:
    """One net identifier of a local net. ``kind`` is ``label``, ``power``, ``offsheet``, ``port``,
    ``entry`` or ``harness`` (a harness entry); ``index`` and ``stream`` name its record; ``owner`` is the
    record index of the sheet symbol of an entry, or of the connector of a harness entry."""

    kind: str
    text: str
    locator: str
    index: int
    owner: int = -1
    stream: str = "main"


@dataclass(frozen=True, slots=True)
class LocalPin:
    """A pin of a local net: the index of its component in ``part_groups`` and its designator."""

    group: int
    designator: str
    locator: str


@dataclass(frozen=True, slots=True)
class LocalNet:
    """One net of a sheet before the sheets are joined. ``no_connect`` marks a net of one pin that holds a
    No ERC directive and nothing else: the pin is left open on purpose."""

    pins: tuple[LocalPin, ...]
    idents: tuple[Ident, ...]
    locators: tuple[str, ...]
    no_connect: bool = False

    def of(self, kind: str) -> tuple[Ident, ...]:
        return tuple(ident for ident in self.idents if ident.kind == kind)


def wire_lines(document: SchDocument) -> Lines:
    return Lines([[pt(p) for p in wire.points] for wire in document.wires() if wire.points])


def bus_lines(document: SchDocument) -> Lines:
    return Lines([[pt(p) for p in bus.points] for bus in document.buses() if bus.points])


def harness_lines(document: SchDocument) -> Lines:
    lines = document.of_type(SignalHarness)
    return Lines([[pt(p) for p in line.points] for line in lines if line.points])


def is_bus_label(label: NetLabel, buses: Lines) -> bool:
    """Whether a net label is a bus identifier: its text has the bus form and it lies on a bus line."""
    return bus_range(label.text) is not None and bool(buses.at(pt(label.location)))


def local_nets(document: SchDocument, groups: Sequence[PartGroup] | None = None) -> tuple[LocalNet, ...]:
    """The local nets of ``document`` in a stable order: by the first record, in stream order, among their
    pins and identifiers. ``groups`` are the sheet's components (``part_groups(document)`` by default); a
    pin is named by the index of its component there."""
    groups = part_groups(document) if groups is None else groups
    wires = wire_lines(document)
    buses = bus_lines(document)
    junctions = [pt(j.location) for j in document.junctions()]
    union = Union()
    for number, group in enumerate(wires.groups(junctions)):
        union.join(("wire", number), ("wires", group))
    positions: dict[Pt, None] = {}

    def attach(node: Hashable, point: Pt) -> None:
        positions.setdefault(point)
        union.join(node, ("at", point))

    pin_records: dict[tuple[int, str], SchRecord] = {}
    pin_points: dict[tuple[int, str], list[Pt]] = {}
    for number, group in enumerate(groups):
        for pin in group.shown:
            key = (number, pin.designator)
            if key not in pin_records or order(pin) < order(pin_records[key]):
                pin_records[key] = pin
            pin_points.setdefault(key, []).append(pt(pin.hot_end))
            attach(("pin", *key), pt(pin.hot_end))
    idents: dict[Hashable, list[tuple[Ident, tuple[int, int]]]] = {}

    def name(node: Hashable, ident: Ident, record: SchRecord, points: Iterable[Pt]) -> None:
        idents.setdefault(node, []).append((ident, order(record)))
        for point in points:
            attach(node, point)

    for label in document.net_labels():
        if label.owner is not None or is_bus_label(label, buses):
            continue
        node = ("label", label.text.casefold()) if label.text else ("label", "", label.ref.index)
        name(node, Ident("label", label.text, locator(label), label.ref.index), label, [pt(label.location)])
    for power in document.power_ports():
        kind = "offsheet" if power.cross_sheet else "power"
        node = (kind, power.text.casefold()) if power.text else (kind, "", power.ref.index)
        name(node, Ident(kind, power.text, locator(power), power.ref.index), power, [pt(power.location)])
    for port in document.ports():
        if port.harness_type or bus_range(port.name) is not None:
            continue  # it carries a harness or a bus, not a net
        name(
            ("port", port.ref.index),
            Ident("port", port.name, locator(port), port.ref.index),
            port,
            port_ends(port),
        )
    for entry in document.of_type(SheetEntry):
        point = entry_point(document, entry)
        owner = document.owner_of(entry)
        if point is None or owner is None or entry.harness_type or bus_range(entry.name) is not None:
            continue
        ident = Ident("entry", entry.name, locator(entry), entry.ref.index, owner.ref.index)
        name(("entry", entry.ref.index), ident, entry, [point])
    for entry in document.of_type(HarnessEntry):
        point = entry_point(document, entry)
        owner = document.owner_of(entry)
        if point is None or owner is None:
            continue
        ident = Ident(
            "harness", entry.name, locator(entry), entry.ref.index, owner.ref.index, entry.ref.stream
        )
        name(("harness", entry.ref.stream, entry.ref.index), ident, entry, [point])
    for junction in junctions:
        positions.setdefault(junction)
    marks = {pt(mark.location) for mark in document.no_ercs()}
    for point in positions:
        for number in wires.at(point):
            union.join(("at", point), ("wire", number))

    members: dict[Hashable, list[tuple[int, str]]] = {}
    for key in pin_records:
        members.setdefault(union.find(("pin", *key)), []).append(key)
    named: dict[Hashable, list[tuple[Ident, tuple[int, int]]]] = {}
    for node, found in idents.items():
        named.setdefault(union.find(node), []).extend(found)
    nets: list[tuple[tuple[int, int], LocalNet]] = []
    for root in dict.fromkeys([*members, *named]):
        keys = sorted(members.get(root, []), key=lambda key: order(pin_records[key]))
        found = sorted(named.get(root, []), key=lambda pair: pair[1])
        pins = tuple(
            LocalPin(group, designator, locator(pin_records[(group, designator)]))
            for group, designator in keys
        )
        firsts = [order(pin_records[key]) for key in keys] + [position for _ident, position in found]
        open_pin = len(keys) == 1 and not found and any(point in marks for point in pin_points[keys[0]])
        nets.append(
            (
                min(firsts),
                LocalNet(
                    pins=pins,
                    idents=tuple(ident for ident, _position in found),
                    locators=tuple([p.locator for p in pins] + [ident.locator for ident, _ in found]),
                    no_connect=open_pin,
                ),
            )
        )
    return tuple(net for _key, net in sorted(nets, key=lambda pair: pair[0]))


__all__ = [
    "Ident",
    "Lines",
    "LocalNet",
    "LocalPin",
    "Union",
    "bus_lines",
    "bus_range",
    "connector_point",
    "entry_point",
    "harness_lines",
    "is_bus_label",
    "local_nets",
    "on_segment",
    "port_ends",
    "pt",
    "side_point",
    "wire_lines",
]
