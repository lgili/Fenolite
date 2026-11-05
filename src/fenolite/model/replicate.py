# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Copies of a board's items: every id of a copy renamed, every point moved (changes c0173 and c0386).

The flattened panel (``panel.altium``) and the conversion of an Altium Embedded Board Array
(``convert.arrays``) both copy a board once per copy. The caller gives the move: ``place`` maps a point of
the board frame to its place in the copy, and ``turn`` is the copy's quarter turn, added to every absolute
angle. No rotation is computed here, so that the model stays free of geometry.
"""

from __future__ import annotations

import dataclasses
from collections.abc import Callable, Mapping
from typing import Any, cast

from fenolite.core.coords import Point
from fenolite.core.trig import FULL_TURN
from fenolite.model.base import Entity
from fenolite.model.board import (
    Arc,
    Dimension,
    FootprintInstance,
    Graphic,
    Hole,
    Keepout,
    Text,
    Track,
    Via,
    Zone,
)

BOARD_ITEMS = (
    "footprints",
    "tracks",
    "arcs",
    "vias",
    "zones",
    "keepouts",
    "texts",
    "graphics",
    "dimensions",
    "holes",
)
"""The fields of a ``Board`` whose items a copy holds."""


def entity_ids(value: Any, found: set[str]) -> None:
    """Every id held by an entity of ``value`` (its ``id`` field), collected into ``found``."""
    if isinstance(value, Entity):
        found.add(value.id)
    if dataclasses.is_dataclass(value) and not isinstance(value, type):
        for f in dataclasses.fields(value):
            entity_ids(getattr(value, f.name), found)
    elif isinstance(value, (tuple, list)):
        for item in cast("tuple[Any, ...]", value):
            entity_ids(item, found)


def renamed(value: Any, mapping: Mapping[str, str]) -> Any:
    """``value`` with every string equal to an old id replaced by its new id, recursively."""
    if isinstance(value, str):
        return mapping.get(value, value)
    if dataclasses.is_dataclass(value) and not isinstance(value, type):
        changes = {}
        for f in dataclasses.fields(value):
            old = getattr(value, f.name)
            new = renamed(old, mapping)
            if new is not old:
                changes[f.name] = new
        return dataclasses.replace(value, **changes) if changes else value
    if isinstance(value, tuple):
        items = cast("tuple[Any, ...]", value)
        new_items = tuple(renamed(item, mapping) for item in items)
        return new_items if any(a is not b for a, b in zip(items, new_items, strict=True)) else items
    if isinstance(value, dict):
        table = cast("dict[Any, Any]", value)
        return {key: renamed(item, mapping) for key, item in table.items()}
    return value


def _turned(angle: int, turn: int) -> int:
    return (angle + turn) % FULL_TURN


def moved(item: Any, place: Callable[[Point], Point], turn: int) -> Any:  # noqa: C901, PLR0911
    """A board item with its board-frame points moved by ``place`` and its absolute angle turned by
    ``turn``; an item of another kind is returned unchanged."""

    def ring(points: tuple[Point, ...]) -> tuple[Point, ...]:
        return tuple(place(p) for p in points)

    if isinstance(item, FootprintInstance):
        return dataclasses.replace(item, position=place(item.position), rotation=_turned(item.rotation, turn))
    if isinstance(item, Track):
        return dataclasses.replace(item, start=place(item.start), end=place(item.end))
    if isinstance(item, Arc):
        return dataclasses.replace(item, start=place(item.start), mid=place(item.mid), end=place(item.end))
    if isinstance(item, Via):
        return dataclasses.replace(item, position=place(item.position))
    if isinstance(item, Zone):
        fills = tuple(dataclasses.replace(f, polygon=ring(f.polygon)) for f in item.fills)
        return dataclasses.replace(item, outline=ring(item.outline), fills=fills)
    if isinstance(item, Keepout):
        return dataclasses.replace(item, outline=ring(item.outline))
    if isinstance(item, Text):
        return dataclasses.replace(item, position=place(item.position), rotation=_turned(item.rotation, turn))
    if isinstance(item, Graphic):
        return dataclasses.replace(item, points=ring(item.points))
    if isinstance(item, Dimension):
        return dataclasses.replace(item, start=place(item.start), end=place(item.end))
    if isinstance(item, Hole):
        return dataclasses.replace(
            item, position=place(item.position), rotation=_turned(item.rotation, turn) if item.length else 0
        )
    return item


__all__ = ["BOARD_ITEMS", "entity_ids", "moved", "renamed"]
