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
