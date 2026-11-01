# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Authored exact-boundary copper and edge benches (c0282)."""

from __future__ import annotations

import pytest
from _coppercheck import Copper

from fenolite.backends.base import EdgeRing, PadCopper
from fenolite.checks.copper import check_copper
from fenolite.core.coords import Point
from fenolite.model.board import Keepout

RADIUS = 1_000_000
WIDTH = 100_000
CLEARANCE = 200_000


def bench(kind: str, gap: int, source: str) -> Copper:
    made = Copper()
    if source == "rule":
        made.rule("authored", CLEARANCE)
    elif source == "class":
        made.netclass("Default", CLEARANCE)
    made.arc("A", Point(-RADIUS, 0), Point(0, RADIUS), Point(RADIUS, 0), width=WIDTH)
    y = RADIUS + WIDTH + gap
    if kind == "track":
        made.track("B", Point(-2 * RADIUS, y), Point(2 * RADIUS, y), width=WIDTH)
    elif kind == "via":
        made.via("B", Point(0, y), diameter=WIDTH)
    elif kind == "pad":
        made.pad("U1", "1", "B", PadCopper("F.Cu", (Point(0, y),), WIDTH))
    elif kind == "arc":
        made.arc("B", Point(-RADIUS, y + RADIUS), Point(0, y), Point(RADIUS, y + RADIUS), width=WIDTH)
    else:
        y -= WIDTH // 2
        ring = (Point(-RADIUS, y), Point(RADIUS, y), Point(RADIUS, y + RADIUS), Point(-RADIUS, y + RADIUS))
        made.zone("B", ring, fills=(ring,), clearance=CLEARANCE if source == "zone" else 0)
    return made


@pytest.mark.parametrize("kind", ["track", "via", "pad", "arc", "fill"])
@pytest.mark.parametrize("source", ["rule", "class", "floor"])
@pytest.mark.parametrize(("delta", "expected"), [(0, False), (-500, False), (-501, True)])
def test_exact_copper_tolerance_boundary(kind: str, source: str, delta: int, expected: bool) -> None:
    made = bench(kind, CLEARANCE + delta, source)
    for tolerance in (1, 1000, 50_000):
        report = check_copper(
            made.build(),
            pads=made.pads,
            tolerance=500,
            arc_tol=tolerance,
            min_clearance=CLEARANCE if source == "floor" else None,
        )
        assert bool(report.findings) is expected
        if expected:
            (found,) = report.findings
            assert found.code == "copper.clearance" and found.gap == CLEARANCE + delta
            assert (
                found.source == {"rule": "rule:authored", "class": "class:Default", "floor": "floor"}[source]
            )


@pytest.mark.parametrize(("delta", "expected"), [(0, False), (-500, False), (-501, True)])
def test_zone_arc_has_the_same_boundary(delta: int, expected: bool) -> None:
    made = bench("fill", CLEARANCE + delta, "zone")
    report = check_copper(made.build(), pads=made.pads, tolerance=500)
    assert bool(report.findings) is expected
    if expected:
        assert report.findings[0].source == "zone"


@pytest.mark.parametrize(("gap", "expected"), [(CLEARANCE, False), (CLEARANCE - 1, True)])
def test_direct_arc_calls_remain_strict(gap: int, expected: bool) -> None:
    made = bench("track", gap, "class")
    assert bool(check_copper(made.build(), pads=made.pads).findings) is expected


@pytest.mark.parametrize("kind", ["track", "fill"])
@pytest.mark.parametrize(("delta", "expected"), [(0, False), (-1, True), (1, False)])
def test_true_curved_edge_is_strict(kind: str, delta: int, expected: bool) -> None:
    ring = EdgeRing("authored", (Point(-RADIUS, 0), Point(RADIUS, 0)), (Point(0, RADIUS), Point(0, -RADIUS)))
    made = Copper()
    y = RADIUS + CLEARANCE + delta
    if kind == "track":
        made.track("A", Point(-RADIUS, y + WIDTH // 2), Point(RADIUS, y + WIDTH // 2), width=WIDTH)
    else:
        fill = (Point(-RADIUS, y), Point(RADIUS, y), Point(RADIUS, y + RADIUS), Point(-RADIUS, y + RADIUS))
        made.zone("A", fill, fills=(fill,))
    report = check_copper(
        made.build(), pads=made.pads, edges=(ring,), min_edge_clearance=CLEARANCE, tolerance=500
    )
    assert bool(report.findings) is expected
    if expected:
        assert report.findings[0].gap == CLEARANCE + delta


def test_arc_touching_rule_area_is_not_lost_to_narrow_band() -> None:
    made = Copper()
    made.arc("A", Point(-RADIUS, 0), Point(0, RADIUS), Point(RADIUS, 0), width=WIDTH)
    y = RADIUS + WIDTH // 2
    area = Keepout(
        id="kpt_00000000-0000-4000-8000-000000000282",
        name="authored",
        layers=("F.Cu",),
        no_tracks=True,
        outline=(Point(-RADIUS, y), Point(RADIUS, y), Point(0, y + RADIUS)),
    )
    made.keepouts.append(area)
    (found,) = check_copper(made.build(), pads=made.pads).findings
    assert found.code == "copper.keepout"
