# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The fonts of Altium stroke texts through KiCad (change c0460, S-2253).

A stroke text record of an Altium PCB document names a font and holds bold and italic flags, though a stroke
text draws with neither; a saved document names ``Arial`` on its designators and comments (S-2253). The
import keeps them in the text's or field's Altium bag (``stroke_font``). KiCad holds no such font on a
stroke text, so a conversion to KiCad carries them in the board property ``PROPERTY``: one line
``<uuid> <bold><italic> <name>`` per text or field, by the KiCad uuid the writer gives it. The conversion
back gives each text and field of a uuid in the map its ``stroke_font`` again, and the writer writes the name
and the flags in the stroke text's record.
"""

from __future__ import annotations

import dataclasses
import re
from collections.abc import Mapping
from typing import TypeVar

from fenolite.backends.altium.adapter.ids import STROKE_FONT_KEY
from fenolite.model.base import Entity, ExtBag
from fenolite.model.board import Board

PROPERTY = "Fenolite.Altium.StrokeFonts"
"""The board property that carries the fonts (``boardcarrier``)."""
_LINE = re.compile(r"([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}) ([01]{2} [^\n]+)")
_E = TypeVar("_E", bound=Entity)


def font_of(entity: Entity) -> str | None:
    """The ``stroke_font`` value of ``entity``'s Altium bag, or ``None``."""
    bag = entity.ext.get("altium")
    return dict(bag.payload).get(STROKE_FONT_KEY) if bag is not None else None


def with_font(entity: _E, value: str) -> _E:
    """``entity`` whose Altium bag holds ``value`` under ``stroke_font`` (replacing one it held)."""
    bag = entity.ext.get("altium")
    pairs = tuple((k, v) for k, v in (bag.payload if bag is not None else ()) if k != STROKE_FONT_KEY)
    held = ExtBag(bag.min_version if bag is not None else None, (*pairs, (STROKE_FONT_KEY, value)))
    return dataclasses.replace(entity, ext={**entity.ext, "altium": held})


def found(board: Board | None) -> dict[str, str]:
    """The fonts of the board's stroke texts by the KiCad uuid the writer gives each (``pcb.kicad_uuid``):
    footprint fields, footprint texts and free texts whose Altium bag holds ``stroke_font``."""
    from fenolite.backends.kicad.pcb import kicad_uuid

    if board is None:
        return {}
    items: list[Entity] = [*board.texts]
    for fp in board.footprints:
        items += [*fp.fields, *fp.texts]
    return {kicad_uuid(item): value for item in items if (value := font_of(item))}


def carrier_text(fonts: Mapping[str, str]) -> bytes:
    """The property's text: one line per text, sorted by uuid."""
    return "".join(f"{uuid} {fonts[uuid]}\n" for uuid in sorted(fonts)).encode("utf-8")


def read_carrier(data: bytes | None) -> dict[str, str]:
    """The carried fonts by uuid; a line that is not well formed is left out, and so is text that does not
    decode."""
    try:
        text = (data or b"").decode("utf-8")
    except UnicodeDecodeError:
        return {}
    found_fonts: dict[str, str] = {}
    for line in text.splitlines():
        match = _LINE.fullmatch(line)
        if match is not None:
            found_fonts[match.group(1)] = match.group(2)
    return found_fonts


def restored(board: Board, fonts: Mapping[str, str]) -> Board:
    """``board``, read from KiCad, whose texts and fields of a uuid in ``fonts`` hold their font again."""
    if not fonts:
        return board

    def own(item: _E) -> _E:
        uuid = item.native_ids.get("kicad")
        return with_font(item, fonts[uuid]) if uuid is not None and uuid in fonts else item

    footprints = tuple(
        dataclasses.replace(
            fp, fields=tuple(own(f) for f in fp.fields), texts=tuple(own(t) for t in fp.texts)
        )
        for fp in board.footprints
    )
    return dataclasses.replace(board, footprints=footprints, texts=tuple(own(t) for t in board.texts))


__all__ = ["PROPERTY", "carrier_text", "font_of", "found", "read_carrier", "restored", "with_font"]
