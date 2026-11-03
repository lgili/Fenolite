# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""STR spatial index (capability geometry-kernel)."""

from __future__ import annotations

import random

from hypothesis import given, settings
from hypothesis import strategies as st

from fenolite.geometry import BBox, SpatialIndex


def _random_boxes(rng: random.Random, count: int) -> list[BBox]:
    boxes: list[BBox] = []
    for _ in range(count):
        x, y = rng.randint(-(10**6), 10**6), rng.randint(-(10**6), 10**6)
        w, h = rng.choice([0, 1, 10, 1000, 50_000]), rng.choice([0, 1, 10, 1000, 50_000])
        boxes.append(BBox(x, y, x + rng.randint(0, w), y + rng.randint(0, h)))
    return boxes


def test_agreement_with_brute_force() -> None:
    rng = random.Random(20261001)
    boxes = _random_boxes(rng, 2000)
    index = SpatialIndex.build((b, i) for i, b in enumerate(boxes))
    assert len(index) == 2000
    for query in _random_boxes(rng, 200):
        expected = [i for i, b in enumerate(boxes) if b.intersects(query)]
        assert index.query_indices(query) == expected
        assert index.query(query) == expected
    brute = [
        (i, j) for i in range(len(boxes)) for j in range(i + 1, len(boxes)) if boxes[i].intersects(boxes[j])
    ]
    assert index.pairs() == brute
    assert sorted(index._join_pairs(lambda: None, lambda count: None)) == brute


RAW_BOX = st.tuples(st.integers(-50, 50), st.integers(-50, 50), st.integers(0, 20), st.integers(0, 20))


@settings(max_examples=50)
@given(st.lists(RAW_BOX), st.integers(2, 20))
def test_small_sets(raw: list[tuple[int, int, int, int]], capacity: int) -> None:
    boxes = [BBox(x, y, x + w, y + h) for x, y, w, h in raw]
    index = SpatialIndex.build(((b, str(i)) for i, b in enumerate(boxes)), capacity=capacity)
    for query in boxes[:10] + [BBox(-5, -5, 5, 5)]:
        assert index.query(query) == [str(i) for i, b in enumerate(boxes) if b.intersects(query)]
    brute = [
        (i, j) for i in range(len(boxes)) for j in range(i + 1, len(boxes)) if boxes[i].intersects(boxes[j])
    ]
    assert index.pairs() == brute
    assert sorted(index._join_pairs(lambda: None, lambda count: None)) == brute


def test_insertion_order() -> None:
    index = SpatialIndex.build([(BBox(0, 0, 10, 10), "b"), (BBox(5, 5, 6, 6), "a")])
    assert index.query(BBox(5, 5, 5, 5)) == ["b", "a"]


def test_empty_index() -> None:
    index: SpatialIndex[str] = SpatialIndex.build([])
    assert index.query(BBox(0, 0, 1, 1)) == []
    assert index.pairs() == []
    assert len(index) == 0


def test_private_join_preserves_closed_degenerate_pairs_and_charges_callbacks() -> None:
    from itertools import combinations

    boxes = [BBox(0, 0, 0, 0), BBox(0, 0, 2, 0), BBox(2, 0, 2, 3), BBox(2, 3, 2, 3)]
    expected = [(i, j) for i, j in combinations(range(len(boxes)), 2) if boxes[i].intersects(boxes[j])]
    for capacity in (2, 4, 8):
        index = SpatialIndex.build(((b, i) for i, b in enumerate(boxes)), capacity=capacity)
        visits = []
        reservations = []
        found = list(index._join_pairs(lambda visits=visits: visits.append(True), reservations.append))
        assert sorted(found) == expected and len(found) == len(set(found))
        assert visits and reservations and max(reservations) >= 1
    pair = SpatialIndex.build([(BBox(0, 0, 1, 1), 0), (BBox(1, 1, 2, 2), 1)], capacity=4)
    visits = []
    assert list(pair._join_pairs(lambda: visits.append(True), lambda count: None)) == [(0, 1)]
    assert len(visits) == 2  # one diagonal-node visit and one closed leaf-box predicate


def test_private_join_callback_exhaustion_propagates_before_output() -> None:
    import pytest

    index = SpatialIndex.build([(BBox(0, 0, 1, 1), i) for i in range(8)], capacity=4)

    def refuse(*args):
        raise RuntimeError("authored resource stop")

    with pytest.raises(RuntimeError, match="authored resource stop"):
        list(index._join_pairs(refuse, lambda count: None))
    with pytest.raises(RuntimeError, match="authored resource stop"):
        list(index._join_pairs(lambda: None, refuse))
