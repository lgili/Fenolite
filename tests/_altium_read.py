# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""A reader of the ASCII schematics that Fenolite writes, for tests only (change c0032, capability
altium-schematic-writer, "Written records read back").

It is written from ``docs/formats/altium/schematic-ascii.md``, as the writer is, and rebuilds the nets from
geometry: a pin's electrical end, the wires that touch it, the net labels whose hotspot lies on a wire or a
pin end, the power ports whose connection point does, and labels or ports of one name joined into one net.
The product never imports this module. A misreading that the writer and this reader share is caught only by
the maintainer's check in Altium Designer (``docs/evidence/altium-schematic.md``).
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence

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


def _on_segment(point: Point, a: Point, b: Point) -> bool:
    (x, y), (x1, y1), (x2, y2) = point, a, b
    cross = (x2 - x1) * (y - y1) - (y2 - y1) * (x - x1)
    return cross == 0 and min(x1, x2) <= x <= max(x1, x2) and min(y1, y2) <= y <= max(y1, y2)


def _touches(point: Point, wire: Sequence[Point]) -> bool:
    return any(_on_segment(point, a, b) for a, b in zip(wire, wire[1:], strict=False))


def nets_from_sheet(records: Sequence[Record]) -> Nets:
    """Net name → {(designator of the owning component, pin designator)}, rebuilt from geometry.

    A group of pins that no label or port names is returned under ``<unnamed ref-pin>`` (its first pin),
    so a broken connection shows up; a group that two names join raises ``ReadError``.
    """
    refs = {
        int(r["OWNERINDEX"]): r["TEXT"]
        for r in records
        if r["RECORD"] == "34" and r.get("NAME") == "Designator"
    }
    pins = [
        ((refs[int(r["OWNERINDEX"])], r["DESIGNATOR"]), pin_end(r)) for r in records if r["RECORD"] == "2"
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

    for i in range(len(pins)):
        find(("pin", i))
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
