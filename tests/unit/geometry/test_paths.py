# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Mixed line/arc contours and ring assembly (capability geometry-kernel)."""

from __future__ import annotations

import random

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from fenolite.geometry import Arc, BBox, GeometryError, Path, Point, Segment, area2, assemble_rings

P = Point
SIDES = [
    Segment(P(0, 0), P(10, 0)),
    Segment(P(10, 0), P(10, 10)),
    Segment(P(10, 10), P(0, 10)),
    Segment(P(0, 10), P(0, 0)),
]


def test_shuffled_outline_assembled() -> None:
    pieces = [SIDES[2], SIDES[0].reversed(), SIDES[3], SIDES[1].reversed()]
    (ring,) = assemble_rings(pieces)
    assert ring.closed
    assert ring.start == P(0, 0)
    assert area2(ring.polygonize()) > 0
    assert ring.pieces == tuple(SIDES)


@settings(max_examples=60)
@given(st.permutations(range(4)), st.lists(st.booleans(), min_size=4, max_size=4))
def test_permutation_invariance(order: list[int], flips: list[bool]) -> None:
    pieces = [SIDES[i].reversed() if flip else SIDES[i] for i, flip in zip(order, flips, strict=True)]
    assert assemble_rings(pieces) == (Path(tuple(SIDES), True),)


def test_line_and_arc_outline() -> None:
    pieces = [Segment(P(-1000, 0), P(1000, 0)), Arc(P(1000, 0), P(0, 1000), P(-1000, 0))]
    (ring,) = assemble_rings(pieces)
    vertices = ring.polygonize(5)
    assert {P(1000, 0), P(0, 1000), P(-1000, 0)} <= set(vertices)
    assert area2(vertices) > 0
    assert ring.bbox() == BBox(-1000, 0, 1000, 1000)
    assert assemble_rings(list(reversed(pieces))) == (ring,)
    assert assemble_rings([pieces[0].reversed(), pieces[1].reversed()]) == (ring,)


def test_two_rings_sorted_and_mixed() -> None:
    far = [
        Segment(P(100, 100), P(110, 100)),
        Segment(P(110, 100), P(100, 110)),
        Segment(P(100, 110), P(100, 100)),
    ]
    pieces = far + SIDES
    rnd = random.Random(7)
    for _ in range(10):
        rnd.shuffle(pieces)
        rings = assemble_rings(pieces)
        assert [r.start for r in rings] == [P(0, 0), P(100, 100)]


def test_zero_area_ring_direction_is_deterministic() -> None:
    there, back = Segment(P(0, 0), P(10, 0)), Segment(P(10, 0), P(0, 0))
    assert assemble_rings([there, back]) == assemble_rings([back, there])


def test_gap_rejected() -> None:
    pieces = [SIDES[0], SIDES[1], Segment(P(10, 10), P(1, 10)), SIDES[3]]
    with pytest.raises(GeometryError) as info:
        assemble_rings(pieces)
    assert info.value.code == "geometry.open-contour"
    assert set(info.value.points) == {P(1, 10), P(0, 10)}
    assert "(1, 10)" in str(info.value) and "(0, 10)" in str(info.value)


def test_zero_length_piece_rejected() -> None:
    with pytest.raises(GeometryError) as info:
        assemble_rings([*SIDES, Segment(P(10, 0), P(10, 0))])
    assert info.value.code == "geometry.degenerate"
    assert info.value.points == (P(10, 0),)
    assert "(10, 0)" in str(info.value)


def test_branch_rejected() -> None:
    pieces = [Segment(P(0, 0), P(10, 0)), Segment(P(0, 0), P(0, 10)), Segment(P(0, 0), P(-10, 0))]
    with pytest.raises(GeometryError) as info:
        assemble_rings(pieces)
    assert info.value.code == "geometry.branching-contour"
    assert info.value.points == (P(0, 0),)


def test_path_validation() -> None:
    with pytest.raises(GeometryError) as info:
        Path((SIDES[0], SIDES[2]), False)
    assert info.value.code == "geometry.open-contour"
    with pytest.raises(GeometryError):
        Path(tuple(SIDES[:3]), True)
    open_path = Path(tuple(SIDES[:3]), False)
    assert open_path.polygonize() == (P(0, 0), P(10, 0), P(10, 10), P(0, 10))
    assert Path(tuple(SIDES), True).polygonize() == (P(0, 0), P(10, 0), P(10, 10), P(0, 10))
    with pytest.raises(TypeError):
        Path(((P(0, 0), P(1, 1)),), False)  # type: ignore[arg-type]
