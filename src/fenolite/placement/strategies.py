# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The four layout strategies of a frame: ``row``, ``column``, ``grid`` and ``pack`` (change c0255;
capability placement-in-code, "Row and column strategies" and "Grid and pack strategies";
``docs/placement.md``, "Placement in code").

A strategy arranges boxes, nothing else: each item is a box in its own frame (a part's box at its rotation,
or a block's box), and the result is the translation that puts each box where the strategy says, in the
frame of the request. Pure integer arithmetic, no search: equal inputs give equal translations.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Protocol

from fenolite.geometry.shapes import BBox


class StrategyLike(Protocol):
    """A strategy as ``fenolite.dsl.relative.Strategy`` records it."""

    @property
    def kind(self) -> str: ...

    @property
    def gap(self) -> int: ...

    @property
    def align(self) -> str: ...

    @property
    def columns(self) -> int: ...

    @property
    def width(self) -> int: ...

    @property
    def at(self) -> tuple[int, int]: ...


@dataclass(frozen=True, slots=True)
class Item:
    """One box to arrange: its key (a component or block path) and its box in its own frame."""

    key: str
    box: BBox


@dataclass(frozen=True, slots=True)
class Arranged:
    """The translation of each item, by key in item order, and the keys of the boxes wider than a
    ``pack`` width (each on its own shelf)."""

    moves: tuple[tuple[str, tuple[int, int]], ...]
    overflow: tuple[str, ...] = ()


def _middle(a: int, b: int) -> int:
    return (a + b) // 2


def _row(items: Sequence[Item], gap: int, align: str, at: tuple[int, int]) -> Arranged:
    tallest = max((item.box.height for item in items), default=0)
    cursor = at[0]
    moves: list[tuple[str, tuple[int, int]]] = []
    for item in items:
        box = item.box
        if align == "center":
            dy = at[1] + tallest // 2 - _middle(box.y0, box.y1)
        elif align == "end":
            dy = at[1] + tallest - box.y1
        else:
            dy = at[1] - box.y0
        moves.append((item.key, (cursor - box.x0, dy)))
        cursor += box.width + gap
    return Arranged(tuple(moves))


def _column(items: Sequence[Item], gap: int, align: str, at: tuple[int, int]) -> Arranged:
    widest = max((item.box.width for item in items), default=0)
    cursor = at[1]
    moves: list[tuple[str, tuple[int, int]]] = []
    for item in items:
        box = item.box
        if align == "center":
            dx = at[0] + widest // 2 - _middle(box.x0, box.x1)
        elif align == "end":
            dx = at[0] + widest - box.x1
        else:
            dx = at[0] - box.x0
        moves.append((item.key, (dx, cursor - box.y0)))
        cursor += box.height + gap
    return Arranged(tuple(moves))


def _grid(items: Sequence[Item], columns: int, gap: int, at: tuple[int, int]) -> Arranged:
    """Cells of the largest box's size plus ``gap``; each box centred in the largest box's size at the
    cell's top-left corner, so the gap lies between the cells."""
    widest = max((item.box.width for item in items), default=0)
    tallest = max((item.box.height for item in items), default=0)
    moves: list[tuple[str, tuple[int, int]]] = []
    for index, item in enumerate(items):
        row, col = divmod(index, columns)
        cx = at[0] + col * (widest + gap) + widest // 2
        cy = at[1] + row * (tallest + gap) + tallest // 2
        box = item.box
        moves.append((item.key, (cx - _middle(box.x0, box.x1), cy - _middle(box.y0, box.y1))))
    return Arranged(tuple(moves))


def _pack(items: Sequence[Item], width: int, gap: int, at: tuple[int, int]) -> Arranged:
    """Shelf packing: boxes sorted by height, tallest first, then item order; each right of the previous
    on the current shelf while it fits within ``width``, else on a new shelf under the tallest box of the
    shelf. A box wider than ``width`` takes a shelf of its own."""
    order = sorted(range(len(items)), key=lambda i: (-items[i].box.height, i))
    placed: dict[int, tuple[int, int]] = {}
    overflow: list[str] = []
    shelf_top, shelf_height, cursor = at[1], 0, at[0]
    for index in order:
        box = items[index].box
        wide = box.width > width
        if cursor > at[0] and (wide or cursor - at[0] + box.width > width):
            shelf_top += shelf_height + gap
            shelf_height, cursor = 0, at[0]
        placed[index] = (cursor - box.x0, shelf_top - box.y0)
        cursor += box.width + gap
        shelf_height = max(shelf_height, box.height)
        if wide:
            overflow.append(items[index].key)
            shelf_top += shelf_height + gap
            shelf_height, cursor = 0, at[0]
    return Arranged(tuple((items[i].key, placed[i]) for i in range(len(items))), tuple(overflow))


def arrange(strategy: StrategyLike, items: Sequence[Item], origin: tuple[int, int] = (0, 0)) -> Arranged:
    """The translation of each item by ``strategy``; ``origin`` is added to the strategy's ``at`` (the
    frame's origin in the coordinates of the boxes). ``ValueError`` for an unknown kind."""
    at = (origin[0] + strategy.at[0], origin[1] + strategy.at[1])
    if strategy.kind == "row":
        return _row(items, strategy.gap, strategy.align, at)
    if strategy.kind == "column":
        return _column(items, strategy.gap, strategy.align, at)
    if strategy.kind == "grid":
        return _grid(items, max(strategy.columns, 1), strategy.gap, at)
    if strategy.kind == "pack":
        return _pack(items, strategy.width, strategy.gap, at)
    raise ValueError(f"unknown layout strategy {strategy.kind!r}")


__all__ = ["Arranged", "Item", "StrategyLike", "arrange"]
