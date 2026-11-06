# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The union members of an Altium PCB document through a conversion to KiCad and back (change c0460).

A union names its members by their records. ``UnionNames`` holds each union's index and name. A member's
record holds the union index:
- a via, as a 32-bit value at offset 70 of its subrecord;
- a region of ``Regions6``, and a component of ``Components6``, as ``UNIONINDEX``.

The census of the public rows (S-2190) found these. The import keeps a member's index in its Altium bag,
under ``UNION_KEY``. KiCad holds no union. The conversion to KiCad therefore gives each member a KiCad uuid
that marks it, a version-8 uuid (RFC 9562, S-0110) whose first 48 bits spell ``altuni``, as
``backends.altium.fills`` marks a fill. It also carries the uuid of every member, with its index, in one
board property. KiCad keeps an item's uuid on a save and on an edit; a copy gets a new one and is no member.
The conversion back gives each item of a uuid in the map its index again, and the writer writes it.
"""

from __future__ import annotations

import dataclasses
import hashlib
import re
import uuid
from collections.abc import Mapping
from typing import TypeVar

from fenolite.backends.altium.adapter.ids import UNION_KEY, VIA_UNION_OFFSET
from fenolite.core.evidence import Evidence, Level
from fenolite.model.base import Entity, ExtBag
from fenolite.model.board import Board, FootprintInstance, Graphic, Via

EVIDENCE = Evidence(Level.INFERRED, hypotheses=("H-A-CONV-UNION",))
"""A conversion's claim: the members written with their index open in Altium as members of their union
(``docs/hypotheses.md``; settled by the kit request of c0460 task 4.1)."""
CARRIER = "UnionMembers"
"""The board property ``Fenolite.Altium.UnionMembers``: one line ``<uuid> <index>`` per member."""
UNION_MARKER = 0x616C74756E69
"""The 48-bit ``custom_a`` field of a member's uuid: the ASCII bytes of ``altuni``."""
_BACKEND = "altium"
_VERSION = 8
_VARIANT = 0b10
_HASH_BITS = 74
_LINE = re.compile(r"([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}) ([1-9][0-9]{0,9})")
_E = TypeVar("_E", bound=Entity)


def union_of(entity: Entity) -> int:
    """The union index of ``entity`` from its Altium bag, 0 for an item of no union."""
    held = entity.ext.get(_BACKEND)
    if held is None:
        return 0
    value = next((v for k, v in held.payload if k == UNION_KEY), "")
    return int(value) if value.isdigit() and int(value) < 1 << 32 else 0


def with_union(entity: _E, index: int) -> _E:
    """``entity`` whose Altium bag holds ``index`` under ``UNION_KEY`` (replacing one it held)."""
    held = entity.ext.get(_BACKEND)
    pairs = tuple((k, v) for k, v in (held.payload if held is not None else ()) if k != UNION_KEY)
    bag = ExtBag(
        min_version=held.min_version if held is not None else None, payload=(*pairs, (UNION_KEY, str(index)))
    )
    return dataclasses.replace(entity, ext={**entity.ext, _BACKEND: bag})


def union_uuid(entity_id: str) -> str:
    """The KiCad uuid of the union member ``entity_id``: version 8, the union marker in ``custom_a`` and the
    first 74 bits of the SHA-256 of ``altium-union:<entity_id>`` in ``custom_b`` and ``custom_c``."""
    digest = hashlib.sha256(f"altium-union:{entity_id}".encode()).digest()
    bits = int.from_bytes(digest, "big") >> (256 - _HASH_BITS)
    custom_b, custom_c = bits >> 62, bits & ((1 << 62) - 1)
    value = (UNION_MARKER << 80) | (_VERSION << 76) | (custom_b << 64) | (_VARIANT << 62) | custom_c
    return str(uuid.UUID(int=value))


def members(board: Board | None) -> dict[str, int]:
    """The union index of each member of ``board`` that a KiCad board can hold, by entity id: its vias, its
    filled graphics and its footprints."""
    if board is None:
        return {}
    items: tuple[Entity, ...] = (*board.vias, *(g for g in board.graphics if g.filled), *board.footprints)
    return {item.id: index for item in items if (index := union_of(item))}


def marked(board: Board, ids: Mapping[str, int]) -> Board:
    """``board`` whose vias, filled graphics and footprints of ``ids`` carry ``union_uuid`` as their KiCad
    uuid. A graphic that holds a KiCad uuid already (a fill's marker) keeps it."""

    def mark(item: _E) -> _E:
        if item.id not in ids or "kicad" in item.native_ids:
            return item
        return dataclasses.replace(item, native_ids={**item.native_ids, "kicad": union_uuid(item.id)})

    vias: tuple[Via, ...] = tuple(mark(v) for v in board.vias)
    graphics: tuple[Graphic, ...] = tuple(mark(g) for g in board.graphics)
    footprints: tuple[FootprintInstance, ...] = tuple(mark(fp) for fp in board.footprints)
    return dataclasses.replace(board, vias=vias, graphics=graphics, footprints=footprints)


def carried_map(ids: Mapping[str, int]) -> bytes:
    """The value of ``CARRIER`` for the members ``ids`` (``members``): one line per member, its
    ``union_uuid`` and its index, in uuid order. ``marked`` gives each member that uuid, so the map names
    the items KiCad holds; a member that already held a KiCad uuid (a fill's marker) is left out."""
    lines = sorted(f"{union_uuid(ident)} {index}" for ident, index in ids.items())
    return "".join(line + "\n" for line in lines).encode("ascii")


def read_map(data: bytes) -> dict[str, int]:
    """The members of a ``CARRIER`` value, by KiCad uuid; a line that is not ``<uuid> <index>`` is left
    out."""
    found: dict[str, int] = {}
    for line in data.decode("ascii", errors="replace").splitlines():
        match = _LINE.fullmatch(line.strip())
        if match is not None and int(match.group(2)) < 1 << 32:
            found[match.group(1)] = int(match.group(2))
    return found


def restored(board: Board, found: Mapping[str, int]) -> Board:
    """``board`` whose vias, filled graphics and footprints of a KiCad uuid in ``found`` hold their union
    index in their Altium bag again."""

    def give(item: _E) -> _E:
        index = found.get(item.native_ids.get("kicad", ""))
        return with_union(item, index) if index else item

    vias: tuple[Via, ...] = tuple(give(v) for v in board.vias)
    graphics: tuple[Graphic, ...] = tuple(give(g) if g.filled else g for g in board.graphics)
    footprints: tuple[FootprintInstance, ...] = tuple(give(fp) for fp in board.footprints)
    return dataclasses.replace(board, vias=vias, graphics=graphics, footprints=footprints)


__all__ = [
    "CARRIER",
    "EVIDENCE",
    "UNION_KEY",
    "UNION_MARKER",
    "VIA_UNION_OFFSET",
    "carried_map",
    "marked",
    "members",
    "read_map",
    "restored",
    "union_of",
    "union_uuid",
    "with_union",
]
