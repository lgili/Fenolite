# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The KiCad uuid that marks a fill of an Altium document through a conversion to KiCad (change c0450).

KiCad holds no fill: a conversion writes an Altium fill as a filled rectangle or polygon. Its uuid says it
was a fill, so a conversion back writes it as a fill record again (``pcbdoc.fill_geometry``). The marker is
a version-8 uuid (RFC 9562, S-0110), as ``backends.kicad.boarditems`` marks a script's items, whose first 48
bits spell ``altfil``. KiCad keeps an item's uuid on a save and on an edit of the item; a copy gets a new
uuid and is written as a region.
"""

from __future__ import annotations

import dataclasses
import hashlib
import re
import uuid

from fenolite.core.evidence import Evidence, Level
from fenolite.model.board import Graphic

EVIDENCE = Evidence(Level.INFERRED, hypotheses=("H-A-CONV-FILL",))
"""A conversion's claim: the fill record written for a tagged rectangle opens in Altium as the source's fill
(``docs/hypotheses.md``; settled by the kit request of c0450 task 4.2)."""

FILL_MARKER = 0x616C7466696C
"""The 48-bit ``custom_a`` field of a fill's uuid: the ASCII bytes of ``altfil``."""
FILLS_LOCATOR = "Fills6/Data#"
"""The locator prefix of a graphic read from a fill record."""
_VERSION = 8
_VARIANT = 0b10
_HASH_BITS = 74
_CANONICAL = re.compile(r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}")


def fill_uuid(entity_id: str) -> str:
    """The KiCad uuid of the fill graphic ``entity_id``: version 8, the fill marker in ``custom_a`` and the
    first 74 bits of the SHA-256 of ``altium-fill:<entity_id>`` in ``custom_b`` and ``custom_c``."""
    digest = hashlib.sha256(f"altium-fill:{entity_id}".encode()).digest()
    bits = int.from_bytes(digest, "big") >> (256 - _HASH_BITS)
    custom_b, custom_c = bits >> 62, bits & ((1 << 62) - 1)
    value = (FILL_MARKER << 80) | (_VERSION << 76) | (custom_b << 64) | (_VARIANT << 62) | custom_c
    return str(uuid.UUID(int=value))


def is_fill_uuid(text: str) -> bool:
    """Whether ``text`` is a canonical uuid with the fill marker, version 8 and the RFC variant."""
    if not _CANONICAL.fullmatch(text):
        return False
    value = int(text.replace("-", ""), 16)
    return value >> 80 == FILL_MARKER and (value >> 76) & 0xF == _VERSION and (value >> 62) & 0b11 == _VARIANT


def is_fill(graphic: Graphic) -> bool:
    """Whether a filled graphic carries the fill marker in its KiCad uuid."""
    return graphic.filled and is_fill_uuid(graphic.native_ids.get("kicad", ""))


def read_fill(graphic: Graphic) -> bool:
    """Whether a filled graphic of an Altium design was read from a fill record."""
    where = graphic.provenance
    return graphic.filled and where is not None and where.locator.startswith(FILLS_LOCATOR)


def marked(graphic: Graphic) -> Graphic:
    """``graphic`` with the fill marker as its KiCad uuid; a filled graphic only."""
    if not graphic.filled:
        return graphic
    return dataclasses.replace(graphic, native_ids={**graphic.native_ids, "kicad": fill_uuid(graphic.id)})


__all__ = [
    "EVIDENCE",
    "FILLS_LOCATOR",
    "FILL_MARKER",
    "fill_uuid",
    "is_fill",
    "is_fill_uuid",
    "marked",
    "read_fill",
]
