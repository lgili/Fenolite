# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""``geometry.touch_groups`` (change c0108; capability geometry-kernel, "Groups of touching thick
shapes")."""

from __future__ import annotations

import random

from fenolite.core.coords import Point
from fenolite.geometry import Thick, thick_touch, touch_groups

MM = 1_000_000
Item = list[tuple[str, Thick]]


def stadium(x0: int, y0: int, x1: int, y1: int, width: int = 250_000) -> Thick:
    return Thick((Point(x0, y0), Point(x1, y1)), width)


def brute(items: list[Item]) -> list[int]:
    """The groups by a union over every pair of shapes, as the smallest index of each group."""
    parent = list(range(len(items)))

    def find(index: int) -> int:
        while parent[index] != index:
            index = parent[index]
        return index

    for i, one in enumerate(items):
        for j in range(i + 1, len(items)):
            if any(ka == kb and thick_touch(a, b) for ka, a in one for kb, b in items[j]):
                root_a, root_b = find(i), find(j)
                parent[max(root_a, root_b)] = min(root_a, root_b)
    return [find(index) for index in range(len(items))]


def partition(groups: list[int]) -> set[frozenset[int]]:
    found: dict[int, set[int]] = {}
    for index, group in enumerate(groups):
        found.setdefault(group, set()).add(index)
    return {frozenset(members) for members in found.values()}


def test_a_chain_joins_its_ends() -> None:
    """Scenario "A chain joins its ends"."""
    first = stadium(0, 0, MM, 0)
    second = stadium(6 * MM, 0, 7 * MM, 0)
    bridge = stadium(MM, 0, 6 * MM, 0)
    other_layer = stadium(0, 0, MM, 0)
    items: list[Item] = [[("F.Cu", first)], [("F.Cu", second)], [("F.Cu", bridge)], [("B.Cu", other_layer)]]
    assert touch_groups(items) == [0, 0, 0, 3]
    turned = touch_groups(items[::-1])
    assert turned == [0, 1, 1, 1]
    assert partition(turned) == {
        frozenset(len(items) - 1 - index for index in group) for group in partition(touch_groups(items))
    }


def test_shapes_with_different_keys_are_never_compared() -> None:
    same_place = stadium(0, 0, MM, 0)
    assert touch_groups([[("F.Cu", same_place)], [("B.Cu", same_place)]]) == [0, 1]
    assert touch_groups([[(("N1", "F.Cu"), same_place)], [(("N2", "F.Cu"), same_place)]]) == [0, 1]
    # an item with a shape on each key joins what touches it on either
    via = [("F.Cu", Thick((Point(0, 0),), 600_000)), ("B.Cu", Thick((Point(0, 0),), 600_000))]
    assert touch_groups([[("F.Cu", same_place)], via, [("B.Cu", same_place)]]) == [0, 0, 0]


def test_no_item_and_items_without_a_shape() -> None:
    assert touch_groups([]) == []
    assert touch_groups([[], [("F.Cu", stadium(0, 0, MM, 0))], []]) == [0, 1, 2]


def test_brute_force_on_generated_shapes() -> None:
    """Scenario "Equal to every pair"."""
    rng = random.Random(1080)
    for _ in range(40):
        items: list[Item] = []
        for _ in range(rng.randrange(2, 30)):
            shapes: Item = []
            for _ in range(rng.randrange(1, 3)):
                x, y = rng.randrange(0, 12) * MM, rng.randrange(0, 12) * MM
                dx, dy = rng.randrange(-3, 4) * MM, rng.randrange(-3, 4) * MM
                core = (Point(x, y),) if (dx, dy) == (0, 0) else (Point(x, y), Point(x + dx, y + dy))
                shapes.append((rng.choice(("F.Cu", "B.Cu")), Thick(core, rng.choice((200_000, 600_000)))))
            items.append(shapes)
        expected = brute(items)
        assert touch_groups(items) == expected
        order = list(range(len(items)))
        rng.shuffle(order)
        shuffled = touch_groups([items[index][::-1] for index in order])
        assert {frozenset(order[index] for index in group) for group in partition(shuffled)} == partition(
            expected
        )
