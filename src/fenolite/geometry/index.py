# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Immutable spatial index packed with Sort-Tile-Recursive (Leutenegger, Edgington, Lopez 1997).

The index is built once from ``(BBox, payload)`` items and never updated; rebuild it when the items
change. Boxes are closed, so boxes that only touch intersect. Results are in insertion order.
"""

from __future__ import annotations

import math
from collections.abc import Callable, Iterable, Iterator, Sequence
from itertools import combinations, product
from typing import Generic, TypeVar

from fenolite.geometry.shapes import BBox

T = TypeVar("T")
_Box = tuple[int, int, int, int]


class _Node:
    __slots__ = ("box", "children", "items")

    def __init__(self, box: _Box, children: tuple[_Node, ...], items: tuple[int, ...]) -> None:
        self.box = box
        self.children = children  # empty for a leaf
        self.items = items  # item indices, only in leaves


def _union(boxes: Iterable[_Box]) -> _Box:
    it = iter(boxes)
    x0, y0, x1, y1 = next(it)
    for b in it:
        x0, y0 = min(x0, b[0]), min(y0, b[1])
        x1, y1 = max(x1, b[2]), max(y1, b[3])
    return x0, y0, x1, y1


def _tiles(entries: Sequence[tuple[_Box, int]], capacity: int) -> list[list[tuple[_Box, int]]]:
    """Group entries into runs of at most ``capacity`` with STR: vertical slices, then by y."""
    count = len(entries)
    pages = math.ceil(count / capacity)
    slices = math.ceil(math.sqrt(pages))
    per_slice = slices * capacity
    by_x = sorted(entries, key=lambda e: (e[0][0] + e[0][2], e[1]))
    groups: list[list[tuple[_Box, int]]] = []
    for start in range(0, count, per_slice):
        column = sorted(by_x[start : start + per_slice], key=lambda e: (e[0][1] + e[0][3], e[1]))
        groups.extend(column[i : i + capacity] for i in range(0, len(column), capacity))
    return groups


class SpatialIndex(Generic[T]):
    """Answers "which items' boxes intersect this box" without scanning every item."""

    __slots__ = ("_boxes", "_payloads", "_root")

    def __init__(self, boxes: tuple[_Box, ...], payloads: tuple[T, ...], root: _Node | None) -> None:
        self._boxes = boxes
        self._payloads = payloads
        self._root = root

    @classmethod
    def build(cls, items: Iterable[tuple[BBox, T]], *, capacity: int = 16) -> SpatialIndex[T]:
        if capacity < 2:
            raise ValueError("capacity must be at least 2")
        pairs = list(items)
        boxes = tuple(b.as_tuple() for b, _ in pairs)
        payloads = tuple(p for _, p in pairs)
        if not pairs:
            return cls(boxes, payloads, None)
        level = [
            _Node(_union(e[0] for e in group), (), tuple(sorted(e[1] for e in group)))
            for group in _tiles([(b, i) for i, b in enumerate(boxes)], capacity)
        ]
        while len(level) > 1:
            groups = _tiles([(node.box, i) for i, node in enumerate(level)], capacity)
            level = [
                _Node(_union(level[i].box for _, i in g), tuple(level[i] for _, i in g), ()) for g in groups
            ]
        return cls(boxes, payloads, level[0])

    def __len__(self) -> int:
        return len(self._payloads)

    def _search(self, box: _Box) -> list[int]:
        found: list[int] = []
        if self._root is None:
            return found
        qx0, qy0, qx1, qy1 = box
        stack = [self._root]
        while stack:
            node = stack.pop()
            nx0, ny0, nx1, ny1 = node.box
            if nx0 > qx1 or qx0 > nx1 or ny0 > qy1 or qy0 > ny1:
                continue
            if node.children:
                stack.extend(node.children)
                continue
            for i in node.items:
                bx0, by0, bx1, by1 = self._boxes[i]
                if bx0 <= qx1 and qx0 <= bx1 and by0 <= qy1 and qy0 <= by1:
                    found.append(i)
        found.sort()
        return found

    def query_indices(self, bbox: BBox) -> list[int]:
        """Indices (insertion order) of the items whose boxes intersect ``bbox``."""
        return self._search(bbox.as_tuple())

    def query(self, bbox: BBox) -> list[T]:
        """Payloads (insertion order) of the items whose boxes intersect ``bbox``."""
        return [self._payloads[i] for i in self._search(bbox.as_tuple())]

    def _join_pairs(
        self, visit: Callable[[], None], reserve: Callable[[int], None]
    ) -> Iterator[tuple[int, int]]:
        """Private exact self join. Hooks bound every node/leaf predicate and pending pair storage."""
        if self._root is None:
            return

        def closed(a: _Box, b: _Box) -> bool:
            return a[0] <= b[2] and b[0] <= a[2] and a[1] <= b[3] and b[1] <= a[3]

        def size(node: _Node) -> tuple[int, int]:
            x0, y0, x1, y1 = node.box
            width, height = x1 - x0, y1 - y0
            return width * height, width + height

        reserve(1)
        stack = [(self._root, self._root)]
        while stack:
            a, b = stack.pop()
            visit()  # Count diagonal visits too; identity is not a free per-query budget reset.
            if a is b:
                if a.children:
                    count = len(a.children)
                    reserve(len(stack) + count * (count + 1) // 2)
                    stack.extend((child, child) for child in a.children)
                    stack.extend(combinations(a.children, 2))
                else:
                    for i, j in combinations(a.items, 2):
                        visit()
                        if closed(self._boxes[i], self._boxes[j]):
                            yield i, j
            elif closed(a.box, b.box):
                if a.children and (not b.children or size(a) >= size(b)):
                    reserve(len(stack) + len(a.children))
                    stack.extend((child, b) for child in a.children)
                elif b.children:
                    reserve(len(stack) + len(b.children))
                    stack.extend((a, child) for child in b.children)
                else:
                    for i, j in product(a.items, b.items):
                        visit()
                        if closed(self._boxes[i], self._boxes[j]):
                            yield min(i, j), max(i, j)

    def pairs(self) -> list[tuple[int, int]]:
        """Every pair ``(i, j)``, ``i < j``, of items whose boxes intersect, sorted ascending."""
        out: list[tuple[int, int]] = []
        for i, box in enumerate(self._boxes):
            out.extend((i, j) for j in self._search(box) if j > i)
        return out


__all__ = ["SpatialIndex"]
