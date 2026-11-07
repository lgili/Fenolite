# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The frame and origin of an Altium document carried through KiCad (change c0467; capability
design-conversion, "The Altium frame travels through KiCad").

A conversion to KiCad keeps the document's absolute coordinates, Y negated, but KiCad has no slot for the
document's origin (``ORIGINX``, ``ORIGINY``). The conversion writes it in the board property ``PROPERTY``
(``backends.kicad.boardcarrier``), in the frame of the design, with the low corner of the board's edge. The
conversion back (``restored``) gives the writer the origin, moved by the translation of the edge's corner,
in the document's frame; the writer then writes the board where KiCad holds it (``lower.write_design``,
``frame_origin``).
"""

from __future__ import annotations

import dataclasses
import json
from typing import cast

from fenolite.core.coords import Point
from fenolite.model.board import Board

PROPERTY = "Fenolite.Altium.Frame"
"""The board property that carries the frame (``boardcarrier``)."""
SCHEMA = "fenolite.altium-frame.v0"


@dataclasses.dataclass(frozen=True, slots=True)
class Carried:
    """The source's origin in the frame of the design (nanometres, Y down) and the low corner of the
    board's edge when it has one."""

    origin: Point
    corner: Point | None = None


def source_origin(board: Board | None) -> Point | None:
    """The origin of an imported board in the frame of the design: its ``altium`` bag's ``origin`` pair
    (``ORIGINX,ORIGINY`` as written), ``(x, -y)``; ``None`` when the board holds none or it does not read."""
    from fenolite.backends.altium.adapter.units import text_length

    bag = board.ext.get("altium") if board is not None else None
    texts = (dict(bag.payload).get("origin") or "").split(",") if bag is not None else []
    if len(texts) != 2:
        return None
    x, y = (text_length(text) for text in texts)
    if x is None or y is None:
        return None
    return Point(x[0], -y[0])


def found(source: Board | None, written: Board | None) -> Carried | None:
    """The frame to carry from the imported board ``source`` into its KiCad conversion ``written``: the
    source's origin and the low corner of the written board's edge; ``None`` without an origin."""
    from fenolite.convert.altium_planes import edge_corner

    origin = source_origin(source)
    if origin is None:
        return None
    return Carried(origin, edge_corner(written) if written is not None else None)


def _point(value: object) -> Point | None:
    items = cast("list[object]", value) if isinstance(value, list) else []
    if len(items) != 2 or not all(isinstance(v, int) and not isinstance(v, bool) for v in items):
        return None
    return Point(cast(int, items[0]), cast(int, items[1]))


def carrier_text(carried: Carried) -> str:
    """The property's canonical JSON text."""
    corner = carried.corner
    root = {
        "schema": SCHEMA,
        "origin": [carried.origin.x, carried.origin.y],
        "corner": None if corner is None else [corner.x, corner.y],
    }
    return json.dumps(root, sort_keys=True, separators=(",", ":"))


def read_carrier(data: bytes | None) -> Carried | None:
    """The carried frame; ``None`` for no property, another schema or text that is no carrier."""
    if not data:
        return None
    try:
        loaded: object = json.loads(data.decode("utf-8"))
    except (UnicodeDecodeError, ValueError):
        return None
    root = cast("dict[str, object]", loaded) if isinstance(loaded, dict) else {}
    origin = _point(root.get("origin"))
    if root.get("schema") != SCHEMA or origin is None:
        return None
    return Carried(origin, _point(root.get("corner")))


def restored(board: Board, carried: Carried) -> Point:
    """The origin to write ``board``, read from KiCad, with: the carried origin moved by the translation of
    the edge's corner (none without a corner on either side), in the document's frame (``(x, -y)``)."""
    from fenolite.convert.altium_planes import edge_corner

    corner = edge_corner(board)
    dx, dy = (
        (corner.x - carried.corner.x, corner.y - carried.corner.y)
        if corner is not None and carried.corner is not None
        else (0, 0)
    )
    return Point(carried.origin.x + dx, -(carried.origin.y + dy))


__all__ = [
    "PROPERTY",
    "SCHEMA",
    "Carried",
    "carrier_text",
    "found",
    "read_carrier",
    "restored",
    "source_origin",
]
