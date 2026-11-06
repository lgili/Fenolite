# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The rooms of a PCB document: its Room Definition rule records (change c0462, task 2.3).

A room is a Room Definition rule (``pcb-copper.md``, S-0310). Its record holds, after the common rule
keys, the outline as the vertex keys of a polygon (``KIND<k>``, ``VX<k>``, ``VY<k>``, ``CX<k>``,
``CY<k>``, ``SA<k>``, ``EA<k>``, ``R<k>``, k from 0, the last vertex repeating the first), ``LAYER`` (the
side) and ``CONFINEMENTSTYLE``: the nine records of the public rule file (S-0297) hold these keys. That a
PCB document's ``Rules6`` record holds the same keys is ``INFERRED`` (``H-A-RD-ROOM``): no public document
holds a room.
"""

# evidence: see import_evidence, read.project

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from fenolite.backends.altium.read.pcbprops import PropertyRecord
from fenolite.backends.altium.read.pcbstack import KeyReader, OutlineVertex, read_outline
from fenolite.core.errors import Issue
from fenolite.model.board import Keepout

ROOM_KIND = "RoomDefinition"
SIDES = {"TOP": "F.Cu", "BOTTOM": "B.Cu"}
"""``LAYER`` of a room record → the copper layer of its side."""
LOCATOR = "Rules6/Data#"
"""The provenance locator of a room's rule area, followed by the record's index (``adapter.board``)."""


@dataclass(frozen=True, slots=True)
class Room:
    """One Room Definition record: its position among the rule records, ``NAME``, ``LAYER`` as written,
    whether it is enabled, ``CONFINEMENTSTYLE`` and the outline's vertices."""

    index: int
    name: str
    layer: str | None
    enabled: bool
    confinement: str | None
    vertices: tuple[OutlineVertex, ...]

    @property
    def side(self) -> str | None:
        """The copper layer of the room's side, ``None`` for a ``LAYER`` outside ``SIDES``."""
        return SIDES.get((self.layer or "").upper())

    @property
    def lines(self) -> bool:
        """Whether the outline is a ring of at least three straight edges: every vertex ``KIND`` 0. An arc
        vertex makes an outline that this reader does not shape."""
        return len(self.vertices) >= 3 and all(vertex.kind == 0 for vertex in self.vertices)


def read_rooms(
    records: Sequence[Sequence[tuple[str, str]]], *, where: str = "Rules6/Data"
) -> tuple[tuple[Room, ...], list[Issue]]:
    """The rooms among the rule records ``records`` (each a record's pairs: ``RuleRecord.fields`` of a PCB
    document, or a record of a rule file) in record order, and the issues of keys whose text does not parse
    (a room with one has no vertices)."""
    rooms: list[Room] = []
    issues: list[Issue] = []
    for index, fields in enumerate(records):
        record = PropertyRecord(raw=b"", fields=tuple(fields))
        if record.get("RULEKIND") != ROOM_KIND:
            continue
        values = KeyReader(record, f"{where}#{index}")
        vertices = read_outline(values)
        enabled = values.bool("ENABLED")
        issues += values.issues
        rooms.append(
            Room(
                index=index,
                name=record.get("NAME") or "",
                layer=record.get("LAYER"),
                enabled=enabled is not False,
                confinement=record.get("CONFINEMENTSTYLE"),
                vertices=() if values.issues else vertices,
            )
        )
    return tuple(rooms), issues


def is_room_area(area: Keepout) -> bool:
    """Whether ``area`` is the rule area of a room read from an Altium document: its provenance is the
    room's record (``LOCATOR``). The Altium writer writes such an area as that record, which the board
    keeps (``kept_rule``, change c0424), and not as a keep-out region."""
    where = area.provenance
    return where is not None and where.backend == "altium" and where.locator.startswith(LOCATOR)


__all__ = ["LOCATOR", "ROOM_KIND", "SIDES", "Room", "is_room_area", "read_rooms"]
