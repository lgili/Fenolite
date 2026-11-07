# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The long form of Altium texts on Mechanical 17 to 32 through KiCad (change c0450, task 4.5).

A text record names Mechanical 17 to 32 by the byte of Mechanical 16 and the layer's long id at 226 of a
first subrecord of 232 or 252 bytes (``pcb-records.md``, "Text"). The import gives such a text that layer and
keeps the bytes from 137 on of its first subrecord in its Altium bag (``text_tail``); the writer's own text
form ends at 137, and no other source gives those bytes. KiCad holds none of them, so a conversion to KiCad
carries them in the board property ``PROPERTY``: one line ``<uuid> <hex>`` per text or field, by the KiCad
uuid the writer gives it, as ``strokefonts`` carries fonts. The conversion back gives each text and field of
a uuid in the map its ``text_tail`` again.
"""

from __future__ import annotations

import dataclasses
import re
from collections.abc import Mapping
from typing import TypeVar

from fenolite.backends.altium.adapter.ids import TEXT_TAIL_KEY
from fenolite.model.base import Entity, ExtBag
from fenolite.model.board import Board

PROPERTY = "Fenolite.Altium.TextTails"
"""The board property that carries the bytes (``boardcarrier``)."""
_LINE = re.compile(r"([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}) ((?:[0-9a-f]{2})+)")
_E = TypeVar("_E", bound=Entity)


def tail_of(entity: Entity) -> str | None:
    """The ``text_tail`` value of ``entity``'s Altium bag, or ``None``."""
    bag = entity.ext.get("altium")
    return dict(bag.payload).get(TEXT_TAIL_KEY) if bag is not None else None


def with_tail(entity: _E, value: str) -> _E:
    """``entity`` whose Altium bag holds ``value`` under ``text_tail`` (replacing one it held)."""
    bag = entity.ext.get("altium")
    pairs = tuple((k, v) for k, v in (bag.payload if bag is not None else ()) if k != TEXT_TAIL_KEY)
    held = ExtBag(bag.min_version if bag is not None else None, (*pairs, (TEXT_TAIL_KEY, value)))
    return dataclasses.replace(entity, ext={**entity.ext, "altium": held})


def found(board: Board | None) -> dict[str, str]:
    """The bytes of the board's texts by the KiCad uuid the writer gives each (``pcb.kicad_uuid``, after
    ``unions.marked``): footprint fields, footprint texts and free texts whose Altium bag holds
    ``text_tail``."""
    from fenolite.backends.altium import unions
    from fenolite.backends.kicad.pcb import kicad_uuid

    if board is None:
        return {}
    board = unions.marked(board, unions.members(board))  # a union member's text has its marked uuid
    items: list[Entity] = [*board.texts]
    for fp in board.footprints:
        items += [*fp.fields, *fp.texts]
    return {kicad_uuid(item): value for item in items if (value := tail_of(item))}


def carrier_text(tails: Mapping[str, str]) -> bytes:
    """The property's text: one line per text, sorted by uuid."""
    return "".join(f"{uuid} {tails[uuid]}\n" for uuid in sorted(tails)).encode("utf-8")


def read_carrier(data: bytes | None) -> dict[str, str]:
    """The carried bytes by uuid; a line that is not well formed is left out, and so is text that does not
    decode."""
    try:
        text = (data or b"").decode("utf-8")
    except UnicodeDecodeError:
        return {}
    tails: dict[str, str] = {}
    for line in text.splitlines():
        match = _LINE.fullmatch(line)
        if match is not None:
            tails[match.group(1)] = match.group(2)
    return tails


def restored(board: Board, tails: Mapping[str, str]) -> Board:
    """``board``, read from KiCad, whose texts and fields of a uuid in ``tails`` hold their bytes again."""
    if not tails:
        return board

    def own(item: _E) -> _E:
        uuid = item.native_ids.get("kicad")
        return with_tail(item, tails[uuid]) if uuid is not None and uuid in tails else item

    footprints = tuple(
        dataclasses.replace(
            fp, fields=tuple(own(f) for f in fp.fields), texts=tuple(own(t) for t in fp.texts)
        )
        for fp in board.footprints
    )
    return dataclasses.replace(board, footprints=footprints, texts=tuple(own(t) for t in board.texts))


__all__ = ["PROPERTY", "carrier_text", "found", "read_carrier", "restored", "tail_of", "with_tail"]
