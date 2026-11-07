# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The float pruning of exact arc distances (change c0437) changes no answer: ``closest`` returns the same
first closest pair as the search over every segment, and ``within`` agrees with that distance at the
thresholds just below, at and above twice it. The shapes are authored at random from a fixed seed, some
with enough pieces for a spatial index, some at board-scale coordinates."""

from __future__ import annotations

import math
import random
from fractions import Fraction

import pytest

from fenolite.core.coords import Point
from fenolite.geometry import Arc, Thick, _curved, thick_closer_than, thick_gap_floor, thick_touch
from fenolite.geometry._curved import Closest
from fenolite.geometry.predicates import Location, point_in_ring
from fenolite.geometry.thick import _index  # pyright: ignore[reportPrivateUsage]


def _arc(rng: random.Random, span: int, at: tuple[int, int]) -> Thick:
    while True:
        x, y = at
        a, m, b = (Point(x + rng.randint(-span, span), y + rng.randint(-span, span)) for _ in (1, 2, 3))
        arc = Arc(a, m, b) if len({a, m, b}) == 3 else None
        if arc is not None and not arc.is_straight:
            return Thick((a, m, b), rng.randint(0, span // 10), arc=arc)


def _other(rng: random.Random, span: int, at: tuple[int, int], pieces: int) -> Thick:
    if pieces == 1:
        return Thick((Point(at[0] + rng.randint(-span, span), at[1] + rng.randint(-span, span)),), 10)
    # A star-shaped ring around ``at`` is a simple polygon; the same points as a polyline are open.
    step = 360 / pieces
    points = tuple(
        Point(
            at[0] + round(rng.randint(span // 4, span) * math.cos(math.radians(k * step))),
            at[1] + round(rng.randint(span // 4, span) * math.sin(math.radians(k * step))),
        )
        for k in range(pieces)
    )
    return Thick(points, rng.randint(0, span // 10), filled=rng.random() < 0.5)


def _every_segment(a: Thick, b: Thick) -> Closest:
    """``closest`` without the index or the pruning."""
    if a.arc is None:
        return _every_segment(b, a).reversed()
    assert a.arc is not None
    if b.filled and point_in_ring(a.arc.start, b.core) != Location.OUTSIDE:
        point = _curved._xy(a.arc.start)  # pyright: ignore[reportPrivateUsage]
        return Closest(_curved.Real(), point, point)
    if b.arc is not None:
        return _curved._best(_curved._arc_arc(a.arc, b.arc))  # pyright: ignore[reportPrivateUsage]
    return _curved._best(  # pyright: ignore[reportPrivateUsage]
        c
        for s, e in _curved._pieces(b)  # pyright: ignore[reportPrivateUsage]
        for c in _curved._arc_segment(a.arc, s, e)  # pyright: ignore[reportPrivateUsage]
    )


CASES = [(seed, pieces, scale) for seed in range(12) for pieces in (1, 5, 40) for scale in (1, 10**6)]


@pytest.mark.parametrize(("seed", "pieces", "scale"), CASES)
def test_pruning_changes_no_answer(seed: int, pieces: int, scale: int) -> None:
    rng = random.Random(437_000 + seed)
    span = 5_000_000
    centre = (rng.randint(-span, span) * scale // 10**3, rng.randint(-span, span) * scale // 10**3)
    a = _arc(rng, span, centre)
    b = _arc(rng, span, centre) if pieces == 5 and seed % 3 == 0 else _other(rng, span, centre, pieces)
    index = _index(b) if b.arc is None else None
    found = _curved.closest(a, b, index)
    expected = _every_segment(a, b)
    assert found == expected
    twice = expected.distance.scaled(2)
    low = twice.floor()
    for reach in {max(low - 1, 0), low, low + 1, low + 2}:
        for strict in (True, False):
            sign = (twice - reach).sign()
            want = sign < 0 if strict else sign <= 0
            assert _curved.within(a, b, reach, strict, index) is want
            assert _curved.within(b, a, reach, strict, index) is want


def test_the_public_predicates_agree_on_a_near_miss() -> None:
    """An arc whose apex is exactly 1 µm from a ring edge: closer than 1001 nm, not closer than 1000 nm."""
    stored = (Point(0, 0), Point(5_000_000, 5_000_000), Point(10_000_000, 0))
    arc = Thick(stored, 0, arc=Arc(*stored))
    edges = [Point(-20_000_000 + 2_000_000 * k, 5_001_000) for k in range(21)]
    ring = Thick((*edges, Point(20_000_000, 9_000_000), Point(-20_000_000, 9_000_000)), 0, filled=True)
    assert _index(ring) is not None  # the indexed path
    assert thick_closer_than(arc, ring, 1001) and not thick_closer_than(arc, ring, 1000)
    assert not thick_touch(arc, ring)
    assert thick_gap_floor(arc, ring) == 1000


@pytest.mark.parametrize("seed", range(40))
def test_every_sample_lies_on_its_arc(seed: int) -> None:
    """The float points that give the upper bounds lie within the slack of the exact arc, for short arcs,
    arcs of nearly a full turn and arcs either way round."""
    rng = random.Random(437_100 + seed)
    span = rng.choice((50, 5_000, 50_000_000))
    a = _arc(rng, span, (rng.randint(-(10**9), 10**9), rng.randint(-(10**9), 10**9)))
    assert a.arc is not None
    gauge = _curved._Gauge.of(a.arc)  # pyright: ignore[reportPrivateUsage]
    slack = 1.0 + gauge.scale * 1e-9
    for x, y in gauge.points:
        candidates = _curved._point_arc((Fraction(x), Fraction(y)), a.arc)  # pyright: ignore[reportPrivateUsage]
        assert any((c.distance - Fraction(slack)).sign() <= 0 for c in candidates)
