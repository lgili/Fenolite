# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Board items of a script on a KiCad board: rule areas, texts, graphics and dimensions (capability
kicad-file-backend, "Board items of a script are written"; facts: ``docs/formats/kicad/board.md``).

Script items are derived output, as script copper is: every build regenerates them from the script.
Their marker is a version-8 uuid (RFC 9562, S-0110) whose first 48 bits spell ``fenitm``, so a rebuild
can tell them from items drawn in KiCad without any registry.
"""

from __future__ import annotations

import dataclasses
import fnmatch
import hashlib
import re
import uuid
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from types import MappingProxyType

from fenolite.core.errors import Issue, Severity
from fenolite.core.evidence import Evidence, Level
from fenolite.model.base import Entity
from fenolite.model.board import Dimension, Graphic, Keepout, Text
from fenolite.model.design import Design
from fenolite.model.rules import Selector

ITEM_MARKER = 0x66656E69746D
"""The 48-bit ``custom_a`` field of every item uuid: the ASCII bytes of ``fenitm``."""
_VERSION = 8
_VARIANT = 0b10
_HASH_BITS = 74
_CANONICAL = re.compile(r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}")

EVIDENCE = Evidence(
    Level.INFERRED, hypotheses=("H-K-AREA-NAME", "H-K-AREA-COND", "H-K-BOARD-TEXT", "H-K-DIM")
)
"""``INFERRED``: the rows cover the benches of their probes, not every board."""
MERGE_ISSUE_CODES: Mapping[str, Severity] = MappingProxyType(
    {
        "kicad.board-item.stale": "warning",
        "kicad.board-item.regenerated": "info",
    }
)
"""Every code ``merge_items`` reports (layout-lens, "Board items declared in the script")."""

BoardItem = Keepout | Text | Graphic | Dimension
_COLLECTIONS = ("keepouts", "texts", "graphics", "dimensions")
_KIND_NAMES: Mapping[type, str] = MappingProxyType(
    {Keepout: "rule area", Text: "text", Graphic: "graphic", Dimension: "dimension"}
)
_SETTINGS = ("no_tracks", "no_vias", "no_pads", "no_copper_pour", "no_footprints")


def _fields(item: BoardItem) -> dict[str, object]:
    """Per kind of item, the modelled fields whose difference is an edit made in KiCad."""
    if isinstance(item, Keepout):
        return {
            "name": item.name,
            "outline": item.outline,
            "layers": item.layers,
            "settings": tuple(getattr(item, setting) for setting in _SETTINGS),
        }
    if isinstance(item, Text):
        return {
            "text": item.text,
            "position": item.position,
            "layer": item.layer,
            "size": item.size,
            "thickness": item.thickness,
            "rotation": item.rotation,
            "justification": (item.h_justify, item.v_justify),
        }
    if isinstance(item, Graphic):
        return {
            "kind": item.kind,
            "layer": item.layer,
            "points": item.points,
            "width": item.width,
            "fill": item.filled,
        }
    return {
        "kind": item.kind,
        "layer": item.layer,
        "points": (item.start, item.end),
        "offset": item.offset,
        "direction": item.direction,
        "units": item.units,
        "precision": item.precision,
    }


def item_uuid(entity_id: str) -> str:
    """The KiCad uuid of the script board item ``entity_id``: version 8, the Fenolite item marker in
    ``custom_a``, and the first 74 bits of the SHA-256 of ``kicad-item:<entity_id>`` in ``custom_b`` and
    ``custom_c``. ``uuid.UUID`` refuses ``version=8`` before Python 3.14 (S-0111), so the bits are set on
    the integer."""
    digest = hashlib.sha256(f"kicad-item:{entity_id}".encode()).digest()
    bits = int.from_bytes(digest, "big") >> (256 - _HASH_BITS)
    custom_b, custom_c = bits >> 62, bits & ((1 << 62) - 1)
    value = (ITEM_MARKER << 80) | (_VERSION << 76) | (custom_b << 64) | (_VARIANT << 62) | custom_c
    return str(uuid.UUID(int=value))


def is_item_uuid(text: str) -> bool:
    """Whether ``text`` is a canonical uuid with the item marker, version 8 and the RFC variant."""
    if not _CANONICAL.fullmatch(text):
        return False
    value = int(text.replace("-", ""), 16)
    return value >> 80 == ITEM_MARKER and (value >> 76) & 0xF == _VERSION and (value >> 62) & 0b11 == _VARIANT


def _native(entity: Entity) -> str:
    return entity.native_ids.get("kicad", "")


def mark_items(design: Design) -> Design:
    """``design`` with ``native_ids["kicad"]`` of every rule area, text, graphic and dimension of its
    board set to ``item_uuid(<its id>)``; nothing else changes."""
    board = design.board
    if board is None:
        return design
    changes: dict[str, tuple[Entity, ...]] = {}
    for name in _COLLECTIONS:
        items: Sequence[Entity] = getattr(board, name)
        if items:
            changes[name] = tuple(
                dataclasses.replace(item, native_ids={**item.native_ids, "kicad": item_uuid(item.id)})
                for item in items
            )
    if not changes:
        return design
    return dataclasses.replace(design, board=dataclasses.replace(board, **changes))  # type: ignore[arg-type]


@dataclass(frozen=True)
class ItemMerge:
    """What stays of the existing board's items beside the script items of a build: the kept items per
    collection, in their order, the counts, and the issues (codes of ``MERGE_ISSUE_CODES``)."""

    keepouts: tuple[Keepout, ...] = ()
    texts: tuple[Text, ...] = ()
    graphics: tuple[Graphic, ...] = ()
    dimensions: tuple[Dimension, ...] = ()
    regenerated: int = 0
    stale: int = 0
    issues: tuple[Issue, ...] = ()


def script_items(design: Design) -> dict[str, tuple[BoardItem, ...]]:
    """The items of ``design``'s board whose KiCad uuid is an item uuid, per collection, in order."""
    board = design.board
    return {
        name: tuple(
            item
            for item in (getattr(board, name) if board is not None else ())
            if is_item_uuid(_native(item))
        )
        for name in _COLLECTIONS
    }


def _where(item: BoardItem) -> str:
    """The name of a rule area, else the layer (a rule area without a name: its first layer)."""
    if isinstance(item, Keepout):
        return item.name or (item.layers[0] if item.layers else "")
    return item.layer


def _differences(old: BoardItem, new: BoardItem) -> list[str]:
    if type(old) is not type(new):
        return ["kind"]
    before, after = _fields(old), _fields(new)
    return [name for name, value in after.items() if before[name] != value]


def merge_items(existing: Design, built: Design) -> ItemMerge:
    """Which rule areas, texts, graphics and dimensions of ``existing`` stay beside the script items of
    ``built``.

    An existing item with an item uuid is dropped: regenerated when ``built`` holds its uuid (with an info
    when a modelled field differs, an edit made in KiCad), stale otherwise. Every other item is kept.
    Points and fields are compared as integers and texts.
    """
    old = existing.board
    if old is None:
        return ItemMerge()
    script: dict[str, BoardItem] = {
        _native(item): item for items in script_items(built).values() for item in items
    }
    kept: dict[str, list[BoardItem]] = {name: [] for name in _COLLECTIONS}
    issues: list[Issue] = []
    regenerated = stale = 0
    for name in _COLLECTIONS:
        for item in getattr(old, name):
            native = _native(item)
            if not is_item_uuid(native):
                kept[name].append(item)
                continue
            kind = _KIND_NAMES[type(item)]
            twin = script.get(native)
            if twin is None:
                stale += 1
                issues.append(
                    Issue(
                        "kicad.board-item.stale",
                        MERGE_ISSUE_CODES["kicad.board-item.stale"],
                        f"script {kind} {native} ({_where(item)}) is no longer declared and is removed",
                        where=native,
                    )
                )
                continue
            fields = _differences(item, twin)
            if fields:
                regenerated += 1
                issues.append(
                    Issue(
                        "kicad.board-item.regenerated",
                        MERGE_ISSUE_CODES["kicad.board-item.regenerated"],
                        f"script {kind} {native} ({_where(twin)}) was edited in KiCad and is written again "
                        f"from the script: {', '.join(fields)}",
                        where=native,
                    )
                )
    return ItemMerge(
        keepouts=tuple(kept["keepouts"]),  # type: ignore[arg-type]
        texts=tuple(kept["texts"]),  # type: ignore[arg-type]
        graphics=tuple(kept["graphics"]),  # type: ignore[arg-type]
        dimensions=tuple(kept["dimensions"]),  # type: ignore[arg-type]
        regenerated=regenerated,
        stale=stale,
        issues=tuple(issues),
    )


def _area_leaves(selector: Selector | None) -> list[str]:
    if selector is None:
        return []
    if selector.op == "area":
        return [selector.value]
    return [value for item in selector.items for value in _area_leaves(item)]


def unknown_areas(design: Design) -> tuple[tuple[str, str], ...]:
    """``(rule name, value)`` for every ``area`` leaf of a rule of ``design`` that no rule area of its
    board matches: no ``Keepout.name`` matches the value with ``fnmatch.fnmatchcase``. KiCad loads such a
    condition and selects nothing (``H-K-AREA-COND``), so the caller refuses it."""
    names = [k.name for k in (design.board.keepouts if design.board is not None else ()) if k.name]
    out: list[tuple[str, str]] = []
    for rule in design.rules.rules if design.rules is not None else ():
        for value in dict.fromkeys((*_area_leaves(rule.selector_a), *_area_leaves(rule.selector_b))):
            if not any(fnmatch.fnmatchcase(name, value) for name in names):
                out.append((rule.name, value))
    return tuple(out)


__all__ = [
    "EVIDENCE",
    "ITEM_MARKER",
    "MERGE_ISSUE_CODES",
    "ItemMerge",
    "is_item_uuid",
    "item_uuid",
    "mark_items",
    "merge_items",
    "script_items",
    "unknown_areas",
]
