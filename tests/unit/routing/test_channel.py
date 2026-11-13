# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The free channel of a net between two points (change c0501, requirement "Free channel width"), on the
authored benches of ``_route_benches``."""

from __future__ import annotations

import random
from dataclasses import replace

from _route_benches import MM, BenchPad, bench, ring, round_pad, slot

from fenolite.core.coords import Point
from fenolite.geometry import Thick, thick_gap_floor
from fenolite.routing.channel import widest
from fenolite.routing.octilinear import MARGIN
from fenolite.routing.search import Limits, search


def test_slot_between_two_classes() -> None:
    """Scenario "A slot between two nets of different classes": 3 mm less the 0.5 mm rule and 0.2 mm. The
    world keeps ``MARGIN`` beyond each clearance, so ``high`` may lie up to ``2 * MARGIN`` below 2.3 mm."""
    b = slot()
    out = widest(b.job, "S", b.subject.a, b.subject.b, limits=Limits(50_000, 200_000, 0), resolution=10_000)
    assert out.low is not None and out.high - out.low <= 10_000 and not out.undecided
    assert out.low <= 2_300_000 <= out.high + 2 * MARGIN
    assert out.pinch is not None and {out.pinch.a.label, out.pinch.b.label} == {"H1-1", "D1-1"}
    assert out.pinch.free == 2_300_000
    assert out.runs and all(b.world.fits("S", layer, points, out.low) for layer, points in out.runs)


def test_no_channel_at_all() -> None:
    """Scenario "No channel at all": the ring whose neighbours' clearances overlap, from inside to out."""
    b = ring(free=-100_000)
    out = widest(b.job, "A", b.subject.a, b.subject.b, limits=Limits(100_000, 50_000, 0))
    assert out.low is None and out.high == 1_000 and not out.grid_limited and out.probes == 1
    assert out.refusal is not None and out.refusal.proven


def _clear(pads: tuple[BenchPad, ...], runs: tuple[tuple[str, tuple[Point, ...]], ...], width: int) -> bool:
    """The exact copper check of the bench: every segment keeps 0.2 mm from every pad of another net."""
    for _, points in runs:
        for p, q in zip(points, points[1:], strict=False):
            segment = Thick((p, q), width)
            for pad in pads:
                if pad.net == "A":
                    continue
                for copper in pad.copper:
                    if thick_gap_floor(segment, Thick(copper.core, copper.width, copper.filled)) < 200_000:
                        return False
    return True


def test_channel_property_on_seeded_benches() -> None:
    """On 30 seeded random benches the path at ``low`` passes the exact copper check, and every proven
    ``high`` has no path in a search on a four times finer grid."""
    grid = 400_000
    for seed in range(30):
        rng = random.Random(seed)
        pads = tuple(
            round_pad(
                f"B{i}",
                "B",
                Point(rng.randrange(-2, 3) * MM, rng.randrange(-3, 4) * MM),
                rng.choice((MM, 2 * MM)),
            )
            for i in range(rng.randrange(1, 5))
        )
        b = bench(pads, Point(-4 * MM, 0), Point(4 * MM, 0), half=5 * MM)
        out = widest(b.job, "A", b.subject.a, b.subject.b, limits=Limits(grid, 20_000, 0), resolution=100_000)
        if out.low is not None:
            assert _clear(pads, out.runs, out.low), seed
        if out.refusal is not None and out.refusal.proven:
            finer = replace(b.subject, width=out.high)
            again = search(b.job, finer, b.world, Limits(grid // 4, 200_000, 0), max_length=100 * MM)
            assert not again.runs, seed
