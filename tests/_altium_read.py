# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""A reader of the ASCII schematics that Fenolite writes, for tests only (change c0032, capability
altium-schematic-writer, "Written records read back").

It is written from ``docs/formats/altium/schematic-ascii.md``, as the writer is, and rebuilds the nets from
geometry: a pin's electrical end, the wires that touch it, the net labels whose hotspot lies on a wire or a
pin end, the power ports whose connection point does, and labels or ports of one name joined into one net.
The product never imports this module. A misreading that the writer and this reader share is caught only by
the maintainer's check in Altium Designer (``docs/evidence/altium-schematic.md``).

``read_no_connects`` (change c0036) rebuilds the pins marked as intentionally unconnected from the No ERC
directives (record 22): each must sit on exactly one pin's electrical end, away from every wire, label
and port.

``nets_from_project`` (change c0037) reads a multi-sheet project: it also takes the ends of ports, the
connection points of sheet entries, harness connectors and harness entries, each from the record's own keys
(``schematic-ascii.md``, "Sheet symbols, sheet entries and ports"; ``schematic-binary.md``, "Additional
stream and harness records"), and joins the sheets under the hierarchical scope (``project.md``).

``read_schlib`` (change c0034) reads a schematic library as the product writes it, from
``docs/formats/altium/schematic-library.md``, with every binary pin decoded field by field.
"""

from __future__ import annotations

import struct
from collections.abc import Mapping, Sequence

from _cfb_read import parse_compound

HEADER = "Protel for Windows - Schematic Capture Ascii File Version 5.0"
DIRECTIONS = {0: (1, 0), 1: (0, 1), 2: (-1, 0), 3: (0, -1)}
"""Bits 0 and 1 of ``PINCONGLOMERATE``: rightwards, upwards, leftwards, downwards."""

Point = tuple[int, int]
Record = dict[str, str]
Nets = dict[str, set[tuple[str, str]]]


class ReadError(ValueError):
    """The bytes break a rule the reader checks."""


def _fields(line: str, number: int) -> Record:
    if not line.startswith("|"):
        raise ReadError(f"line {number} does not start with '|'")
    record: Record = {}
    for field in line[1:].split("|"):
        key, equals, value = field.partition("=")
        if not equals or not key:
            raise ReadError(f"line {number}: field {field!r} is not KEY=VALUE")
        record[key] = value
    return record


def read_records(data: bytes) -> list[Record]:
    """The records after the header, as ``{key: value}``. Checks the header text, that ``WEIGHT`` equals
    the number of records, that every ``OWNERINDEX`` names an earlier record, that record 0 is the sheet,
    and that no line ends with ``|>``. Lines may end with CR LF or LF."""
    try:
        text = data.decode("ascii")
    except UnicodeDecodeError as error:
        raise ReadError(f"not 7-bit ASCII at byte {error.start}") from None
    lines = text.split("\n")
    if lines[-1] != "":
        raise ReadError("the last line has no line end")
    lines = [line.removesuffix("\r") for line in lines[:-1]]
    if not lines:
        raise ReadError("no header")
    for number, line in enumerate(lines, start=1):
        if line.endswith("|>"):
            raise ReadError(f"line {number} ends with '|>'")
    header = _fields(lines[0], 1)
    if header.get("HEADER") != HEADER:
        raise ReadError(f"header {header.get('HEADER')!r}")
    records = [_fields(line, number) for number, line in enumerate(lines[1:], start=2)]
    if header.get("WEIGHT") != str(len(records)):
        raise ReadError(f"WEIGHT={header.get('WEIGHT')} but {len(records)} records follow the header")
    for index, record in enumerate(records):
        owner = record.get("OWNERINDEX")
        if owner is not None and not 0 <= int(owner) < index:
            raise ReadError(f"record {index} names owner {owner}, which is not an earlier record")
    if records and records[0].get("RECORD") != "31":
        raise ReadError("record 0 is not the sheet record RECORD=31")
    return records


def _point(record: Record, name: str) -> Point:
    return int(record[f"{name}.X"]), int(record[f"{name}.Y"])


def pin_end(pin: Record) -> Point:
    """A pin's electrical end: ``LOCATION`` plus ``PINLENGTH`` in the pin's direction."""
    x, y = _point(pin, "LOCATION")
    dx, dy = DIRECTIONS[int(pin["PINCONGLOMERATE"]) & 3]
    length = int(pin["PINLENGTH"])
    return x + dx * length, y + dy * length


def pin_shown(records: Sequence[Record], pin: Record) -> bool:
    """A pin is drawn when its ``OWNERPARTID`` is 0 (Part Zero) or the ``CURRENTPARTID`` of its owner
    (change c0034: a part record carries the pins of every part)."""
    owner = records[int(pin["OWNERINDEX"])]
    return pin.get("OWNERPARTID", "1") in ("0", owner.get("CURRENTPARTID", "1"))


def _on_segment(point: Point, a: Point, b: Point) -> bool:
    (x, y), (x1, y1), (x2, y2) = point, a, b
    cross = (x2 - x1) * (y - y1) - (y2 - y1) * (x - x1)
    return cross == 0 and min(x1, x2) <= x <= max(x1, x2) and min(y1, y2) <= y <= max(y1, y2)


def _touches(point: Point, wire: Sequence[Point]) -> bool:
    return any(_on_segment(point, a, b) for a, b in zip(wire, wire[1:], strict=False))


def nets_from_sheet(records: Sequence[Record]) -> Nets:
    """Net name → {(designator of the owning component, pin designator)}, rebuilt from geometry. Wires,
    labels and ports may be horizontal or vertical; only the pins drawn on a part record count, and one
    pin drawn on several parts of a component is one pin.

    A group of pins that no label or port names is returned under ``<unnamed ref-pin>`` (its first pin),
    so a broken connection shows up; a group that two names join raises ``ReadError``.
    """
    refs = {
        int(r["OWNERINDEX"]): r["TEXT"]
        for r in records
        if r["RECORD"] == "34" and r.get("NAME") == "Designator"
    }
    pins = [
        ((refs[int(r["OWNERINDEX"])], r["DESIGNATOR"]), pin_end(r))
        for r in records
        if r["RECORD"] == "2" and pin_shown(records, r)
    ]
    wires = [
        [(int(r[f"X{i}"]), int(r[f"Y{i}"])) for i in range(1, int(r["LOCATIONCOUNT"]) + 1)]
        for r in records
        if r["RECORD"] == "27"
    ]
    names = [(r["TEXT"], _point(r, "LOCATION")) for r in records if r["RECORD"] in ("25", "17")]
    parent: dict[tuple[str, object], tuple[str, object]] = {}

    def find(node: tuple[str, object]) -> tuple[str, object]:
        parent.setdefault(node, node)
        while parent[node] != node:
            parent[node] = parent[parent[node]]
            node = parent[node]
        return node

    def union(a: tuple[str, object], b: tuple[str, object]) -> None:
        parent[find(a)] = find(b)

    first_of: dict[tuple[str, str], int] = {}
    for i, (key, _) in enumerate(pins):
        find(("pin", i))
        if key in first_of:  # one pin drawn on several parts (Part Zero) is one electrical pin
            union(("pin", i), ("pin", first_of[key]))
        first_of.setdefault(key, i)
    for j, wire in enumerate(wires):
        find(("wire", j))
        for i, (_, end) in enumerate(pins):
            if _touches(end, wire):
                union(("pin", i), ("wire", j))
        for k, other in enumerate(wires):
            if k != j and (_touches(other[0], wire) or _touches(other[-1], wire)):
                union(("wire", k), ("wire", j))
    for text, point in names:
        find(("name", text))
        for j, wire in enumerate(wires):
            if _touches(point, wire):
                union(("name", text), ("wire", j))
        for i, (_, end) in enumerate(pins):
            if end == point:
                union(("name", text), ("pin", i))
    members: dict[tuple[str, object], set[tuple[str, str]]] = {}
    labels: dict[tuple[str, object], set[str]] = {}
    for i, (key, _) in enumerate(pins):
        members.setdefault(find(("pin", i)), set()).add(key)
    for text, _ in names:
        labels.setdefault(find(("name", text)), set()).add(text)
    nets: Nets = {}
    for root, keys in members.items():
        found = sorted(labels.get(root, set()))
        if len(found) > 1:
            raise ReadError(f"the net names {found} are joined")
        name = found[0] if found else "<unnamed {}-{}>".format(*min(keys))
        nets.setdefault(name, set()).update(keys)
    return nets


def net_classes_from_sheet(records: Sequence[Record]) -> dict[str, str]:
    """Net name → net class name, from the net class directives of one sheet (change c0048,
    ``schematic-ascii.md``, "Net class directive"): each record 43 that owns a record 41 named
    ``ClassName`` puts the net of the wire under its location in the class that the parameter's text names.
    The net's name is that of the net label or power port on the same wire.

    ``ReadError`` for a directive whose location lies on no wire or on a wire's end, whose wire holds no
    name or two names, or that owns two ``ClassName`` parameters, and for a net that two directives put in
    two classes."""
    wires = [
        [(int(r[f"X{i}"]), int(r[f"Y{i}"])) for i in range(1, int(r["LOCATIONCOUNT"]) + 1)]
        for r in records
        if r["RECORD"] == "27"
    ]
    names = [(r["TEXT"], _point(r, "LOCATION")) for r in records if r["RECORD"] in ("25", "17")]
    found: dict[str, str] = {}
    for index, record in enumerate(records):
        if record["RECORD"] != "43":
            continue
        owned = [
            r
            for r in records
            if r["RECORD"] == "41" and r.get("OWNERINDEX") == str(index) and r.get("NAME") == "ClassName"
        ]
        if not owned:
            continue
        if len(owned) > 1:
            raise ReadError(f"the directive of record {index} owns {len(owned)} ClassName parameters")
        point = _point(record, "LOCATION")
        under = [wire for wire in wires if _touches(point, wire)]
        if not under:
            raise ReadError(f"the net class directive at {point} lies on no wire")
        if any(point in (wire[0], wire[-1]) for wire in under):
            raise ReadError(f"the net class directive at {point} lies on a wire's end")
        nets = sorted({text for text, at in names for wire in under if _touches(at, wire)})
        if len(nets) != 1:
            raise ReadError(f"the wire of the net class directive at {point} holds the names {nets}")
        name = owned[0]["TEXT"]
        if found.setdefault(nets[0], name) != name:
            raise ReadError(f"the net {nets[0]} is in the classes {found[nets[0]]} and {name}")
    return found


def read_no_connects(records: Sequence[Record]) -> set[tuple[str, str]]:
    """{(designator of the owning component, pin designator)} of the pins whose electrical end holds a
    No ERC directive (``RECORD=22``). Only the pins drawn on a part record count.

    Raises ``ReadError`` when a directive's location is no pin's end, when it lies on a wire, on a net
    label's hotspot or on a power port, and when two directives share a location.
    """
    refs = {
        int(r["OWNERINDEX"]): r["TEXT"]
        for r in records
        if r["RECORD"] == "34" and r.get("NAME") == "Designator"
    }
    ends: dict[Point, set[tuple[str, str]]] = {}
    for r in records:
        if r["RECORD"] == "2" and pin_shown(records, r):
            ends.setdefault(pin_end(r), set()).add((refs[int(r["OWNERINDEX"])], r["DESIGNATOR"]))
    wires = [
        [(int(r[f"X{i}"]), int(r[f"Y{i}"])) for i in range(1, int(r["LOCATIONCOUNT"]) + 1)]
        for r in records
        if r["RECORD"] == "27"
    ]
    names = {_point(r, "LOCATION"): r["RECORD"] for r in records if r["RECORD"] in ("25", "17")}
    seen: set[Point] = set()
    marks: set[tuple[str, str]] = set()
    for r in records:
        if r["RECORD"] != "22":
            continue
        at = _point(r, "LOCATION")
        if at in seen:
            raise ReadError(f"two No ERC directives at {at}")
        seen.add(at)
        if any(_touches(at, wire) for wire in wires):
            raise ReadError(f"the No ERC directive at {at} lies on a wire")
        if at in names:
            what = "net label" if names[at] == "25" else "power port"
            raise ReadError(f"the No ERC directive at {at} lies on a {what}")
        if at not in ends:
            raise ReadError(f"the No ERC directive at {at} is on no pin's electrical end")
        marks |= ends[at]
    return marks


def net_differences(
    read: Mapping[str, set[tuple[str, str]]], expected: Mapping[str, set[tuple[str, str]]]
) -> list[str]:
    """One message per net whose pins differ, naming the net, the missing and the extra pins."""
    problems: list[str] = []
    for name in sorted(set(read) | set(expected)):
        got, want = read.get(name, set()), expected.get(name, set())
        if got != want:
            problems.append(f"{name}: missing {sorted(want - got)}, extra {sorted(got - want)}")
    return problems


# --- hierarchical projects (change c0037) ------------------------------------------------------------

BINARY_HEADER = "Protel for Windows - Schematic Capture Binary File Version 5.0"
CFB_SIGNATURE = bytes.fromhex("d0cf11e0a1b11ae1")
HARNESS_RECORDS = ("215", "216", "217", "218")

SheetRecords = tuple[list[Record], list[Record]]
"""The records of one sheet: those of ``FileHeader`` (or of the ASCII file) and those of ``Additional``,
each without its header record. Owner indexes count inside their own list."""
Node = tuple[object, ...]


def _framed(stream: bytes, where: str) -> list[Record]:
    """The records of a binary stream after its header record, with the header and ``WEIGHT`` checked."""
    records = [dict(_fields(text, number)) for number, text in enumerate(_payloads(stream, where))]
    if not records:
        raise ReadError(f"{where}: no header record")
    header, rest = records[0], records[1:]
    if header.get("HEADER") != BINARY_HEADER:
        raise ReadError(f"{where}: header {header.get('HEADER')!r}")
    if rest and header.get("WEIGHT") != str(len(rest)):
        raise ReadError(f"{where}: WEIGHT={header.get('WEIGHT')} but {len(rest)} records follow the header")
    return rest


def _payloads(stream: bytes, where: str) -> list[str]:
    texts: list[str] = []
    offset = 0
    while offset < len(stream):
        if offset + 4 > len(stream):
            raise ReadError(f"{where}: the length word at byte {offset} is cut")
        (word,) = struct.unpack_from("<I", stream, offset)
        length, kind = word & 0xFFFFFF, word >> 24
        payload = stream[offset + 4 : offset + 4 + length]
        if kind != 0 or len(payload) != length or not payload.endswith(b"\0") or b"\0" in payload[:-1]:
            raise ReadError(f"{where}: the record at byte {offset} is not a text record with one final NUL")
        texts.append(payload[:-1].decode("ascii"))
        offset += 4 + length
    return texts


def read_sheet(data: bytes) -> SheetRecords:
    """The records of one written sheet, in either form: a compound file gives its ``FileHeader`` records
    and, when the stream is there, its ``Additional`` records; an ASCII file gives its records and no
    harness record. A harness record outside ``Additional``, or any other record inside it, is refused."""
    if data.startswith(CFB_SIGNATURE):
        streams = parse_compound(data).streams
        if "FileHeader" not in streams:
            raise ReadError("FileHeader: the stream is missing")
        if "Additional" in streams and not streams["Additional"]:
            raise ReadError("Additional: the stream is empty")
        main = _framed(streams["FileHeader"], "FileHeader")
        extra = _framed(streams["Additional"], "Additional") if "Additional" in streams else []
        other = sorted(set(streams) - {"FileHeader", "Storage", "Additional"})
        if other:
            raise ReadError(f"unexpected streams {other}")
    else:
        main, extra = read_records(data), []
    if any(r.get("RECORD") in HARNESS_RECORDS for r in main):
        raise ReadError("a harness record lies outside the Additional stream")
    if any(r.get("RECORD") not in HARNESS_RECORDS for r in extra):
        raise ReadError("the Additional stream holds a record that is not a harness record")
    return main, extra


def _side_point(box: Record, side: int, distance: int) -> Point:
    """A point on the edge ``side`` (0 left, 1 right, 2 top, 3 bottom) of a box whose location is its
    top-left corner, ``distance`` units from that corner along the edge."""
    x, y = _point(box, "LOCATION")
    if side == 0:
        return x, y - distance
    if side == 1:
        return x + int(box["XSIZE"]), y - distance
    if side == 2:
        return x + distance, y
    return x + distance, y - int(box["YSIZE"])


class _Sheet:
    """The connection points of one sheet's hierarchy and harness records, each from the record's own
    keys."""

    def __init__(self, name: str, records: SheetRecords) -> None:
        self.name = name
        self.main, self.extra = records
        main, extra = self.main, self.extra
        self.wires = [
            [(int(r[f"X{i}"]), int(r[f"Y{i}"])) for i in range(1, int(r["LOCATIONCOUNT"]) + 1)]
            for r in main
            if r["RECORD"] == "27"
        ]
        self.ports: dict[str, tuple[Record, tuple[Point, Point]]] = {}
        for r in main:
            if r["RECORD"] == "18":
                if r["NAME"] in self.ports:
                    raise ReadError(f"{name}: two ports are named {r['NAME']}")
                x, y = _point(r, "LOCATION")
                self.ports[r["NAME"]] = (r, ((x, y), (x + int(r["WIDTH"]), y)))
        self.symbols: dict[int, tuple[str, str]] = {}
        self.entries: dict[int, dict[str, tuple[Record, Point]]] = {}
        for index, r in enumerate(main):
            if r["RECORD"] == "15":
                owned = [o for o in main if o.get("OWNERINDEX") == str(index)]
                names = [o["TEXT"] for o in owned if o["RECORD"] == "32"]
                files = [o["TEXT"] for o in owned if o["RECORD"] == "33"]
                if len(names) != 1 or len(files) != 1:
                    raise ReadError(f"{name}: the sheet symbol at record {index} needs one name and one file")
                self.symbols[index] = (names[0], files[0])
                self.entries[index] = {}
                for o in owned:
                    if o["RECORD"] != "16":
                        continue
                    if o["NAME"] in self.entries[index]:
                        raise ReadError(f"{name}: the sheet symbol {names[0]} has two entries {o['NAME']}")
                    point = _side_point(r, int(o.get("SIDE", "0")), 10 * int(o.get("DISTANCEFROMTOP", "0")))
                    self.entries[index][o["NAME"]] = (o, point)
        self.connectors: dict[int, tuple[Point, str, dict[str, Point]]] = {}
        for index, r in enumerate(extra):
            if r["RECORD"] != "215":
                continue
            owned = [
                o for o in extra if int(o.get("OWNERINDEX", "0")) == index and o["RECORD"] in ("216", "217")
            ]
            owned = [o for o in owned if o.get("OWNERINDEXADDITIONALLIST") == "T"]
            kinds = [o["TEXT"] for o in owned if o["RECORD"] == "217"]
            if len(kinds) != 1:
                raise ReadError(f"{name}: the harness connector at record {index} needs one type record")
            points: dict[str, Point] = {}
            for o in owned:
                if o["RECORD"] == "216":
                    if o["NAME"] in points:
                        raise ReadError(f"{name}: the harness {kinds[0]} has two entries {o['NAME']}")
                    side, distance = int(o.get("SIDE", "0")), 10 * int(o.get("DISTANCEFROMTOP", "0"))
                    points[o["NAME"]] = _side_point(r, side, distance)
            hot = _side_point(r, int(r.get("HARNESSCONNECTORSIDE", "0")), int(r["PRIMARYCONNECTIONPOSITION"]))
            self.connectors[index] = (hot, kinds[0], points)
        claimed = {i for i in self.connectors}
        for index, r in enumerate(extra):
            if r["RECORD"] in ("216", "217") and int(r.get("OWNERINDEX", "0")) not in claimed:
                raise ReadError(f"{name}: harness record {index} names an owner that is not a connector")
        self.lines = [
            [(int(r[f"X{i}"]), int(r[f"Y{i}"])) for i in range(1, int(r["LOCATIONCOUNT"]) + 1)]
            for r in extra
            if r["RECORD"] == "218"
        ]

    def entry_line(self, point: Point) -> Point | None:
        """The far end of the signal harness line that starts or ends at the sheet entry at ``point`` and
        ends on another sheet entry, or ``None`` when no such line touches ``point``."""
        entry_points = {at for entries in self.entries.values() for _r, at in entries.values()}
        found = [
            ends[1] if ends[0] == point else ends[0]
            for ends in ((line[0], line[-1]) for line in self.lines)
            if point in ends
        ]
        found = [far for far in found if far in entry_points and far != point]
        if len(found) > 1:
            raise ReadError(f"{self.name}: two signal harness lines join the sheet entry at {point}")
        return found[0] if found else None

    def connector_at(self, point: Point, what: str) -> int:
        """The connector that a signal harness line joins to ``point`` (an end of a port, or the connection
        point of a sheet entry)."""
        found: list[int] = []
        for line in self.lines:
            ends = (line[0], line[-1])
            if point not in ends:
                continue
            other = ends[1] if ends[0] == point else ends[0]
            found += [i for i, (hot, _kind, _points) in self.connectors.items() if hot == other]
        if len(found) != 1:
            raise ReadError(f"{self.name}: {what} is joined to {len(found)} harness connectors, not one")
        return found[0]


def nets_from_project(sheets: Mapping[str, SheetRecords], top: str) -> Nets:
    """Net name → {(designator, pin designator)} of a written multi-sheet project, rebuilt from geometry
    under the hierarchical scope (``docs/formats/altium/project.md``): a net label is local to its sheet; a
    power port joins its name on every sheet; a port joins the sheet entry of the same name on the sheet
    symbol whose file name is the port's sheet; a harness joins, entry by entry, the wires on the connector
    beside the port with those on the connector beside the sheet entry, or, when a signal harness line
    joins the sheet entry to another sheet entry of the same type, with those on the connector beside that
    entry's port. Nothing else joins two sheets.

    It fails on a port without a sheet entry of its name, a sheet entry without a port, a sheet symbol whose
    file is not in ``sheets``, a signal harness line whose end touches neither a port, a sheet entry nor a
    connector, two connectors of one type with different entries, a net with two names, and one name on two
    separate nets."""
    if top not in sheets:
        raise ReadError(f"the top sheet {top} is not among the sheets")
    found = {name: _Sheet(name, records) for name, records in sheets.items()}
    parent: dict[Node, Node] = {}

    def find(node: Node) -> Node:
        parent.setdefault(node, node)
        while parent[node] != node:
            parent[node] = parent[parent[node]]
            node = parent[node]
        return node

    def union(a: Node, b: Node) -> None:
        parent[find(a)] = find(b)

    pins: list[tuple[str, tuple[str, str]]] = []
    names: list[tuple[Node, str]] = []
    definitions: dict[str, tuple[str, frozenset[str]]] = {}
    for sheet in found.values():
        s, main = sheet.name, sheet.main
        refs = {
            int(r["OWNERINDEX"]): r["TEXT"]
            for r in main
            if r["RECORD"] == "34" and r.get("NAME") == "Designator"
        }
        local = [
            ((refs[int(r["OWNERINDEX"])], r["DESIGNATOR"]), pin_end(r))
            for r in main
            if r["RECORD"] == "2" and pin_shown(main, r)
        ]
        for key, end in local:
            find(("pin", key))
            pins.append((s, key))
            for j, wire in enumerate(sheet.wires):
                if _touches(end, wire):
                    union(("pin", key), ("wire", s, j))
        for j, wire in enumerate(sheet.wires):
            for k, other in enumerate(sheet.wires):
                if k != j and (_touches(other[0], wire) or _touches(other[-1], wire)):
                    union(("wire", s, k), ("wire", s, j))
        for r in main:
            if r["RECORD"] not in ("25", "17"):
                continue
            node: Node = ("label", s, r["TEXT"]) if r["RECORD"] == "25" else ("power", r["TEXT"])
            names.append((node, r["TEXT"]))
            point = _point(r, "LOCATION")
            find(node)
            for j, wire in enumerate(sheet.wires):
                if _touches(point, wire):
                    union(node, ("wire", s, j))
            for key, end in local:
                if end == point:
                    union(node, ("pin", key))

        def wired(points: Sequence[Point], node: Node, sheet: _Sheet = sheet) -> None:
            find(node)
            for j, wire in enumerate(sheet.wires):
                if any(_touches(point, wire) for point in points):
                    union(node, ("wire", sheet.name, j))

        for name, (_record, ends) in sheet.ports.items():
            wired(ends, ("port", s, name))
        for owner, entries in sheet.entries.items():
            for name, (_record, point) in entries.items():
                wired((point,), ("entry", s, owner, name))
        for index, (_hot, kind, points) in sheet.connectors.items():
            entry_names = frozenset(points)
            where, known = definitions.setdefault(kind, (s, entry_names))
            if known != entry_names:
                raise ReadError(
                    f"the harness type {kind} has the entries {sorted(known)} on {where} and "
                    f"{sorted(entry_names)} on {s}"
                )
            for entry, point in points.items():
                wired((point,), ("harness", s, index, entry))
        anchors = {end for _r, ends in sheet.ports.values() for end in ends}
        anchors |= {point for entries in sheet.entries.values() for _r, point in entries.values()}
        anchors |= {hot for hot, _kind, _points in sheet.connectors.values()}
        for line in sheet.lines:
            for end in (line[0], line[-1]):
                if end not in anchors:
                    raise ReadError(
                        f"{s}: a signal harness line ends at {end}, which is neither a port, a sheet entry "
                        "nor a harness connector"
                    )
    named: set[str] = set()
    for sheet in found.values():
        for owner, (symbol, file) in sheet.symbols.items():
            child = found.get(file)
            if child is None:
                raise ReadError(f"the sheet symbol {symbol} names the file {file}, which is not a sheet")
            if file == top or file in named:
                raise ReadError(
                    f"the sheet {file} is named by the sheet symbol {symbol} and is the top or repeated"
                )
            named.add(file)
            entries = sheet.entries[owner]
            for name in sorted(set(child.ports) - set(entries)):
                raise ReadError(f"the port {name} of {file} has no sheet entry on the sheet symbol {symbol}")
            for name in sorted(set(entries) - set(child.ports)):
                raise ReadError(f"the sheet entry {name} of the sheet symbol {symbol} has no port on {file}")
            for name, (entry, point) in entries.items():
                port, ends = child.ports[name]
                kind, other = entry.get("HARNESSTYPE"), port.get("HARNESSTYPE")
                if kind != other:
                    raise ReadError(
                        f"the port {name} of {file} and its sheet entry on {symbol} differ in type"
                    )
                if kind is None:
                    union(("port", file, name), ("entry", sheet.name, owner, name))
                    continue
                below = [child.connector_at(end, f"the port {name}") for end in ends if _line_at(child, end)]
                if len(below) != 1:
                    raise ReadError(f"{file}: the harness port {name} needs one signal harness line")
                if child.connectors[below[0]][1] != kind:
                    raise ReadError(f"{file}: the connector beside {name} is not of the type {kind}")
                far = sheet.entry_line(point)
                if far is not None:
                    # A signal harness line joins this sheet entry to another one: every entry of the
                    # harness travels along it, so both child connectors join the same line, item by item.
                    other = [
                        e
                        for entries_ in sheet.entries.values()
                        for e, at in entries_.values()
                        if at == far and e is not entry
                    ]
                    if len(other) != 1 or other[0].get("HARNESSTYPE") != kind:
                        raise ReadError(
                            f"{sheet.name}: the signal harness line from the sheet entry {name} of {symbol} "
                            f"does not end on one sheet entry of the type {kind}"
                        )
                    line = tuple(sorted((point, far)))
                    for item in child.connectors[below[0]][2]:
                        union(("harness", file, below[0], item), ("line", sheet.name, line, item))
                    continue
                above = sheet.connector_at(point, f"the sheet entry {name} of {symbol}")
                if sheet.connectors[above][1] != kind:
                    raise ReadError(f"{sheet.name}: the connector beside {name} is not of the type {kind}")
                for item in child.connectors[below[0]][2]:
                    union(("harness", file, below[0], item), ("harness", sheet.name, above, item))
    for sheet in found.values():
        if sheet.name != top and sheet.name not in named and sheet.ports:
            port = sorted(sheet.ports)[0]
            raise ReadError(
                f"the port {port} of {sheet.name} has no sheet entry: no sheet symbol names the sheet"
            )
    if found[top].ports:
        raise ReadError(f"the top sheet {top} holds the port {sorted(found[top].ports)[0]}")
    members: dict[Node, set[tuple[str, str]]] = {}
    for _sheet, key in pins:
        members.setdefault(find(("pin", key)), set()).add(key)
    labels: dict[Node, set[str]] = {}
    for node, text in names:
        labels.setdefault(find(node), set()).add(text)
    nets: Nets = {}
    for root, keys in members.items():
        texts = sorted(labels.get(root, set()))
        if len(texts) > 1:
            raise ReadError(f"the net names {texts} are joined")
        name = texts[0] if texts else "<unnamed {}-{}>".format(*min(keys))
        if name in nets:
            raise ReadError(
                f"the name {name} is on two separate nets: {sorted(nets[name])} and {sorted(keys)}"
            )
        nets[name] = set(keys)
    return nets


def _line_at(sheet: _Sheet, point: Point) -> bool:
    return any(point in (line[0], line[-1]) for line in sheet.lines)


# --- the documents of a project and the links of its components (change c0037, step H7) -------------------

SHEET_EXTENSION = ".SchDoc"


def project_documents(project: bytes) -> list[str]:
    """The ``DocumentPath`` of every ``[Document<n>]`` section of a written project file, in file order
    (``docs/formats/altium/project.md``). The sections must be numbered 1, 2, 3, … without a gap, each with
    one path, and no path may repeat."""
    found: list[str] = []
    section: str | None = None
    for line in project.decode("ascii").split("\r\n"):
        if line.startswith("[") and line.endswith("]"):
            section = line[1:-1]
            if section.startswith("Document"):
                if section != f"Document{len(found) + 1}":
                    raise ReadError(f"the project section {section} is out of sequence")
                found.append("")
        elif section is not None and section.startswith("Document") and line.startswith("DocumentPath="):
            if found[-1]:
                raise ReadError(f"the project section {section} holds two paths")
            found[-1] = line.partition("=")[2]
    if any(not path for path in found):
        raise ReadError("a project document section holds no path")
    if len(set(found)) != len(found):
        raise ReadError("the project lists a document twice")
    return found


def component_links(project: bytes, files: Mapping[str, bytes], top: str) -> dict[str, tuple[str, str]]:
    """Link path → (designator, hierarchical path) of every component of a written project, as a PCB
    document names them (``docs/formats/altium/pcb-document.md``): ``\\<component id>`` and an empty path on
    the top sheet, ``\\<sheet symbol id>\\<component id>`` and ``<top sheet stem>\\<sheet name>`` on the
    sheet that a sheet symbol of the top sheet names.

    It reads the hierarchy as a second program must find it: the sheets are the ``.SchDoc`` documents that
    the project file lists; a sheet symbol's file-name record (33) names its child by the exact file name
    of a listed document. It fails when the project does not list ``top``, when a listed sheet has no
    bytes, when a sheet symbol names a file that the project does not list (in any letter case) or names
    the top sheet, when two sheet symbols name one sheet or share a name or a unique id, when a sheet other
    than the top holds a sheet symbol, when a listed sheet is not reachable from the top sheet, and when
    two components share a link path."""
    listed = [name for name in project_documents(project) if name.endswith(SHEET_EXTENSION)]
    if top not in listed:
        raise ReadError(f"the project does not list the top sheet {top}")
    for name in listed:
        if name not in files:
            raise ReadError(f"the project lists the sheet {name}, which was not written")
    sheets = {name: _Sheet(name, read_sheet(files[name])) for name in listed}
    stem = top.removesuffix(SHEET_EXTENSION)
    links: dict[str, tuple[str, str]] = {}

    def add(sheet: _Sheet, prefix: str, path: str) -> None:
        main = sheet.main
        for record in main:
            if record["RECORD"] != "34" or record.get("NAME") != "Designator":
                continue
            owner = main[int(record["OWNERINDEX"])]
            if owner.get("CURRENTPARTID", "1") != "1":
                continue
            link = f"{prefix}\\{owner['UNIQUEID']}"
            if link in links:
                raise ReadError(f"two components share the link {link}")
            links[link] = (record["TEXT"], path)

    add(sheets[top], "", "")
    named: dict[str, str] = {}
    ids: set[str] = set()
    for index, (symbol, file) in sheets[top].symbols.items():
        if file not in sheets:
            near = [name for name in listed if name.lower() == file.lower()]
            hint = f" (the project lists {near[0]})" if near else ""
            raise ReadError(f"the sheet symbol {symbol} names {file}, which the project does not list{hint}")
        if file == top:
            raise ReadError(f"the sheet symbol {symbol} names the top sheet")
        if file in named:
            raise ReadError(f"the sheet symbols {named[file]} and {symbol} name the sheet {file}")
        if symbol in named.values():
            raise ReadError(f"two sheet symbols are named {symbol}")
        unique = sheets[top].main[index].get("UNIQUEID", "")
        if not unique or unique in ids:
            raise ReadError(f"the sheet symbol {symbol} needs a unique id of its own")
        ids.add(unique)
        named[file] = symbol
        add(sheets[file], f"\\{unique}", f"{stem}\\{symbol}")
    for name, sheet in sheets.items():
        if name != top and sheet.symbols:
            raise ReadError(f"the module sheet {name} holds a sheet symbol")
        if name != top and name not in named:
            raise ReadError(f"the sheet {name} is not reachable from the top sheet: no sheet symbol names it")
    return links


def board_link_problems(links: Mapping[str, tuple[str, str]], components: Sequence[Record]) -> list[str]:
    """Why the components of a PCB document (their ``Components6`` records) do not match the schematic
    ``links`` of ``component_links``; empty when every board component's ``SOURCEUNIQUEID`` is the link of a
    schematic component with the same designator and hierarchical path, every schematic component is on
    the board once, and ``CHANNELOFFSET`` counts 0, 1, 2, … on every sheet."""
    problems: list[str] = []
    seen: dict[str, str] = {}
    offsets: dict[str, list[int]] = {}
    for record in components:
        ref, link = record["SOURCEDESIGNATOR"], record["SOURCEUNIQUEID"]
        if link not in links:
            problems.append(f"{ref}: its link {link} is not a schematic component")
            continue
        designator, path = links[link]
        if designator != ref:
            problems.append(f"{ref}: its link {link} is the schematic component {designator}")
        if record["SOURCEHIERARCHICALPATH"] != path:
            problems.append(f"{ref}: its hierarchical path is not {path!r}")
        if link in seen:
            problems.append(f"{ref}: {seen[link]} has the same link")
        seen[link] = ref
        offsets.setdefault(path, []).append(int(record["CHANNELOFFSET"]))
    for link, (designator, _path) in links.items():
        if link not in seen:
            problems.append(f"{designator}: the schematic component {link} is not on the board")
    for path, found in offsets.items():
        if found != list(range(len(found))):
            problems.append(f"the channel offsets on {path or 'the top sheet'} are {found}")
    return problems


# --- schematic libraries (change c0034) --------------------------------------------------------------

LIBRARY_HEADER = "Protel for Windows - Schematic Library Editor Binary File Version 5.0"
PIN_FIELDS = (
    "OWNERPARTID",
    "OWNERPARTDISPLAYMODE",
    "SYMBOL_INNEREDGE",
    "SYMBOL_OUTEREDGE",
    "SYMBOL_INSIDE",
    "SYMBOL_OUTSIDE",
    "DESCRIPTION",
    "FORMALTYPE",
    "ELECTRICAL",
    "PINCONGLOMERATE",
    "PINLENGTH",
    "LOCATION.X",
    "LOCATION.Y",
    "COLOR",
    "NAME",
    "DESIGNATOR",
    "SWAPIDGROUP",
    "PARTANDSEQUENCE",
    "DEFAULTVALUE",
)
"""The fields of a binary pin, in payload order after the record id and the unknown byte
(``docs/formats/altium/schematic-library.md``, "Pin fields")."""

LibRecord = dict[str, object]
"""A de-framed library record: text keys as strings, or a decoded pin with ``BINARY`` set to ``True``."""


def _short(payload: bytes, offset: int, where: str) -> tuple[str, int]:
    if offset >= len(payload):
        raise ReadError(f"{where}: a short string is cut at byte {offset}")
    length = payload[offset]
    end = offset + 1 + length
    if end > len(payload):
        raise ReadError(f"{where}: a short string of {length} bytes is cut")
    return payload[offset + 1 : end].decode("ascii"), end


def decode_pin(payload: bytes, where: str) -> LibRecord:
    """The fields of a binary pin payload, checked: record id 2 and all five short strings, no byte left."""
    if len(payload) < 12:
        raise ReadError(f"{where}: a pin payload of {len(payload)} bytes is cut")
    record_id, unknown, part, mode = struct.unpack_from("<iBhB", payload, 0)
    if record_id != 2:
        raise ReadError(f"{where}: binary record id {record_id}, not 2")
    pin: LibRecord = {"BINARY": True, "RECORD": "2", "UNKNOWN": unknown, "OWNERPARTID": part}
    pin["OWNERPARTDISPLAYMODE"] = mode
    for index, key in enumerate(("SYMBOL_INNEREDGE", "SYMBOL_OUTEREDGE", "SYMBOL_INSIDE", "SYMBOL_OUTSIDE")):
        pin[key] = payload[8 + index]
    pin["DESCRIPTION"], offset = _short(payload, 12, where)
    if offset + 13 > len(payload):
        raise ReadError(f"{where}: the pin is cut after its description")
    pin["FORMALTYPE"], pin["ELECTRICAL"], pin["PINCONGLOMERATE"] = payload[offset : offset + 3]
    length, x, y, colour = struct.unpack_from("<hhhI", payload, offset + 3)
    pin["PINLENGTH"], pin["LOCATION.X"], pin["LOCATION.Y"], pin["COLOR"] = length, x, y, colour
    offset += 13
    for key in ("NAME", "DESIGNATOR", "SWAPIDGROUP", "PARTANDSEQUENCE", "DEFAULTVALUE"):
        pin[key], offset = _short(payload, offset, f"{where} {key}")
    if offset != len(payload):
        raise ReadError(f"{where}: {len(payload) - offset} byte(s) after the pin's last string")
    return pin


def _text_record(payload: bytes, where: str) -> LibRecord:
    if not payload.endswith(b"\0") or b"\0" in payload[:-1]:
        raise ReadError(f"{where}: the text payload does not end with its one NUL")
    text = payload[:-1].decode("ascii")
    return dict(_fields(text, 0))


def deframe_library(stream: bytes, where: str) -> list[LibRecord]:
    """The records of a ``FileHeader``, ``SectionKeys`` or ``Data`` stream; binary records decoded as pins.
    The stream must be consumed exactly."""
    records: list[LibRecord] = []
    offset = 0
    while offset < len(stream):
        if offset + 4 > len(stream):
            raise ReadError(f"{where}: the length word at byte {offset} is cut")
        (word,) = struct.unpack_from("<I", stream, offset)
        length, kind = word & 0xFFFFFF, word >> 24
        payload = stream[offset + 4 : offset + 4 + length]
        if len(payload) != length:
            raise ReadError(f"{where}: the record at byte {offset} is cut")
        at = f"{where} record {len(records)}"
        records.append(_text_record(payload, at) if kind == 0 else decode_pin(payload, at))
        offset += 4 + length
    return records


def read_schlib(data: bytes) -> dict[str, list[LibRecord]]:
    """Storage name → the de-framed records of its ``Data`` stream, in storage order of the file.

    Checks the header text, that ``FileHeader`` holds exactly one record, ``COMPCOUNT`` and the
    ``LIBREF<i>`` keys against the storages (through ``SectionKeys`` when present), ``WEIGHT`` (records of
    all ``Data`` streams plus 1), that each storage holds ``Data`` and nothing else, that ``Data`` starts
    with ``RECORD=1`` and is consumed exactly, and every binary pin field by field.
    """
    compound = parse_compound(data)
    streams = compound.streams
    if "FileHeader" not in streams:
        raise ReadError("FileHeader: the stream is missing")
    header_records = deframe_library(streams["FileHeader"], "FileHeader")
    if len(header_records) != 1:
        raise ReadError(f"FileHeader: {len(header_records)} records, not exactly the header record")
    header = header_records[0]
    if str(header.get("HEADER", "")).lower() != LIBRARY_HEADER.lower():
        raise ReadError(f"FileHeader: header {header.get('HEADER')!r}")
    keys: dict[str, str] = {}
    if "SectionKeys" in streams:
        (section,) = deframe_library(streams["SectionKeys"], "SectionKeys")
        for index in range(int(str(section["KEYCOUNT"]))):
            keys[str(section[f"LIBREF{index}"])] = str(section[f"SECTIONKEY{index}"])
    library: dict[str, list[LibRecord]] = {}
    for storage in compound.storages:
        inside = sorted(path for path in streams if path.startswith(storage + "/"))
        if inside != [f"{storage}/Data"]:
            raise ReadError(f"{storage}: holds {inside}, not exactly Data")
        records = deframe_library(streams[f"{storage}/Data"], f"{storage}/Data")
        if not records or records[0].get("RECORD") != "1" or records[0].get("BINARY"):
            raise ReadError(f"{storage}/Data: the first record is not the component RECORD=1")
        library[storage] = records
    count = int(str(header.get("COMPCOUNT", "-1")))
    if count != len(library):
        raise ReadError(f"FileHeader: COMPCOUNT={count} but {len(library)} storages")
    refs = [str(header[f"LIBREF{i}"]) for i in range(count)]
    if sorted(keys.get(ref, ref) for ref in refs) != sorted(library):
        raise ReadError(f"FileHeader: the LIBREF keys {refs} do not name the storages {sorted(library)}")
    weight = sum(len(records) for records in library.values()) + 1
    if header.get("WEIGHT") != str(weight):
        raise ReadError(f"FileHeader: WEIGHT={header.get('WEIGHT')}, not {weight}")
    other = [p for p in streams if "/" not in p and p not in ("FileHeader", "Storage", "SectionKeys")]
    if other:
        raise ReadError(f"root: unexpected streams {other}")
    return library
