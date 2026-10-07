# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Groups of touching thick shapes: the one union of touching copper of the package."""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Hashable, Iterable, Sequence

from fenolite.geometry.index import SpatialIndex
from fenolite.geometry.thick import Thick, thick_bbox, thick_touch


def touch_groups(items: Sequence[Iterable[tuple[Hashable, Thick]]]) -> list[int]:
    """The group of every item, as the smallest index of the items of its group.

    Each item is a collection of ``(key, shape)`` pairs. Two items are in one group when a shape of one
    and a shape of the other have equal keys and ``thick_touch`` is true for them, directly or through
    other items. Shapes with different keys are never compared: a caller passes the layer, or the net
    and the layer. Candidate pairs come from a ``SpatialIndex`` over ``thick_bbox``; the result is that
    of testing every pair and does not depend on the order of the items or of their shapes.
    """
    parent = list(range(len(items)))

    def find(index: int) -> int:
        while parent[index] != index:
            parent[index] = parent[parent[index]]
            index = parent[index]
        return index

    keyed: dict[Hashable, list[tuple[int, Thick]]] = defaultdict(list)
    for index, item in enumerate(items):
        for key, shape in item:
            keyed[key].append((index, shape))
    for shapes in keyed.values():
        tree = SpatialIndex[int].build((thick_bbox(shape), index) for index, shape in shapes)
        for p, q in tree.pairs():
            (first, one), (second, other) = shapes[p], shapes[q]
            root_a, root_b = find(first), find(second)
            if root_a != root_b and thick_touch(one, other):
                parent[max(root_a, root_b)] = min(root_a, root_b)
    return [find(index) for index in range(len(items))]


__all__ = ["touch_groups"]
