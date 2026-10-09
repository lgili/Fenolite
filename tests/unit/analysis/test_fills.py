# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Fill regions from stored fills (capability board-analyses, "Copper fill regions")."""

from __future__ import annotations

from fractions import Fraction

from _analysis import MM, at, box
from _coppercheck import Copper
from _power import SPLIT4, SPLIT4_HOLE, SQUARE20, pour_board, region, split4, stored

from fenolite.analysis.fills import area_outside, fill_regions, unfracture
from fenolite.geometry import area2, keyhole_ring


def test_a_pour_with_a_hole() -> None:
    """Scenario "A pour with a hole"."""
    ring = stored(SPLIT4, (SPLIT4_HOLE,))
    assert len(ring) == len(SPLIT4) + 4 + 3  # one anchor point and one slit pair
    regions, left_out = fill_regions(pour_board(SPLIT4, (SPLIT4_HOLE,)))
    assert left_out == 0 and len(regions) == 1
    (found,) = regions
    assert len(found.holes) == 1 and len(found.holes[0]) == 4
    assert found.area2 == 418_880_000_000_000
    assert found.net == "P" and found.layer == "F.Cu" and found.where.endswith("#0")
    assert set(found.holes[0]) == set(SPLIT4_HOLE)


def test_a_keyhole_ring_is_undone() -> None:
    """Scenario "A keyhole ring is undone"."""
    holes = (
        box(5, 9, 7, 11),
        box(13, 9, 15, 11),
    )  # 2 mm squares, 6 mm apart
    ring = keyhole_ring(SQUARE20, holes).ring
    found = unfracture(ring)
    assert found is not None
    outer, inner = found
    assert set(SQUARE20) <= set(outer)
    assert {frozenset(hole) for hole in inner} == {frozenset(hole) for hole in holes}
    twice = abs(area2(outer)) - sum(abs(area2(hole)) for hole in inner)
    assert twice == 784_000_000_000_000 == abs(area2(ring))


def test_keyhole_anchor_put_into_an_edge_and_on_a_hole() -> None:
    low, high = box(5, 3, 7, 5), box(12, 12.5, 14, 14.5)  # no vertex of the square on their rays
    for holes in ((low,), (low, high), (box(5, 9, 7, 11), box(9, 9.5, 11, 10.5))):
        made = keyhole_ring(SQUARE20, holes)
        assert made.merged == len(holes)
        found = unfracture(made.ring)
        assert found is not None
        outer, inner = found
        assert len(inner) == len(holes)
        assert abs(area2(outer)) == 400 * MM * MM * 2
        assert abs(area2(outer)) - sum(abs(area2(hole)) for hole in inner) == abs(area2(made.ring))
        for given in holes:
            assert any(set(given) <= set(hole) for hole in inner)


def test_a_plain_ring_and_what_does_not_chain() -> None:
    assert unfracture(SQUARE20) == (SQUARE20, ())
    assert unfracture((at(0, 0), at(1, 0))) is None
    # a spur walked once: its two edges are a slit pair, the rest is the square
    spur = (*SQUARE20[:1], at(-3, 0), *SQUARE20)
    found = unfracture(spur)
    assert found is not None and set(found[0]) == set(SQUARE20)


def test_fills_without_a_net_or_without_area_are_not_regions() -> None:
    made = Copper()
    made.zone(None, SQUARE20, fills=(SQUARE20,))
    made.zone("P", SQUARE20, fills=((at(0, 0), at(5, 0), at(10, 0)), SQUARE20), locator="/zone[1]")
    regions, left_out = fill_regions(made.build())
    assert left_out == 1 and [r.where for r in regions] == ["/zone[1]#1"]


def test_area_outside_hulls() -> None:
    found = split4()
    assert area_outside(found, ()) == Fraction(found.area2, 2)
    # a hull over the left square's lower left quarter, half outside the region
    hull = box(-5, -5, 5, 5)
    assert area_outside(found, (hull,)) == Fraction(found.area2, 2) - 25 * MM * MM
    # a hull over the neck: 3 mm × 4 mm less the hole, clipped exactly
    neck = box(10, 0, 13, 10)
    assert area_outside(found, (neck, hull)) == 175 * MM * MM
    # a hull that cuts the hole in two halves, turned the other way round
    half = tuple(reversed(box(11.5, 3, 13, 7)))
    assert area_outside(found, (half,)) == Fraction(found.area2, 2) - (6 * MM * MM - 128 * MM * MM // 100)
    # a degenerate hull has no area
    assert area_outside(region(SQUARE20), ((at(1, 1), at(2, 2)),)) == 400 * MM * MM
