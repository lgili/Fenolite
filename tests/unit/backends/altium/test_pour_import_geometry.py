# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Independent positive and located negative controls for c0215's actual import proof."""

from __future__ import annotations

from dataclasses import replace

import pytest
from _pour_import_geometry import matched_zones, within_written_boundary_band

from fenolite.backends.altium.pour import PolygonPour
from fenolite.core.coords import Point
from fenolite.geometry import Polygon
from fenolite.geometry.boolean._exact_noding import Budget, Limits, ResourceLimit
from fenolite.model.board import Zone, ZoneFill


def rect(x0: int, y0: int, x1: int, y1: int) -> Polygon:
    return Polygon((Point(x0, y0), Point(x1, y0), Point(x1, y1), Point(x0, y1)))


SQUARE = rect(0, 0, 1000, 1000)


@pytest.mark.parametrize(
    "candidate",
    [
        (SQUARE,),
        (rect(10, 0, 1010, 1000),),
        (rect(0, 0, 500, 1000), rect(500, 0, 1000, 1000), rect(1000, 500, 1001, 501)),
        (Polygon(SQUARE.outer, (rect(2, 500, 3, 501).outer[::-1],)),),
    ],
)
def test_complete_boundary_fragments_and_holes_pass(candidate: tuple[Polygon, ...]) -> None:
    before = tuple(candidate)
    assert within_written_boundary_band((SQUARE,), candidate)
    assert candidate == before  # No discarded tiny fragment, merged polygon or deleted hole.


@pytest.mark.parametrize(
    ("written", "candidate"),
    [
        ((SQUARE,), (SQUARE, rect(2000, 2000, 2001, 2001))),
        ((SQUARE,), (Polygon(SQUARE.outer, (rect(500, 500, 501, 501).outer[::-1],)),)),
        (
            (rect(0, 0, 100, 100), rect(140, 0, 240, 100)),
            (rect(0, 0, 100, 100), rect(140, 0, 240, 100), rect(100, 50, 140, 51)),
        ),
        ((SQUARE,), (rect(11, 0, 1011, 1000),)),
        ((SQUARE,), ()),
    ],
)
def test_even_tiny_located_copper_differences_fail(
    written: tuple[Polygon, ...], candidate: tuple[Polygon, ...]
) -> None:
    assert not within_written_boundary_band(written, candidate)


def test_resource_exhaustion_never_passes() -> None:
    with pytest.raises(ResourceLimit):
        within_written_boundary_band((SQUARE,), (SQUARE,), budget=Budget(Limits(winding_visits=1)))


ZONE = Zone(
    id="native-zone",
    outline=SQUARE.outer,
    layers=("B.Cu",),
    net_id="net",
    fills=(ZoneFill("B.Cu", SQUARE.outer),),
)
POUR = PolygonPour(0, "B.Cu", "VIN", (SQUARE,), 10)


def test_exact_zone_identity_retains_all_fills() -> None:
    assert matched_zones((ZONE,), {"net": "VIN"}, (POUR,)) == ((ZONE, POUR),)


@pytest.mark.parametrize(
    "zone",
    [
        replace(ZONE, net_id="wrong"),
        replace(ZONE, layers=("F.Cu",)),
        replace(ZONE, fills=(ZoneFill("F.Cu", SQUARE.outer),)),
    ],
)
def test_wrong_net_or_layer_fails_even_with_identical_copper(zone: Zone) -> None:
    with pytest.raises(AssertionError):
        matched_zones((zone,), {"net": "VIN", "wrong": "GND"}, (POUR,))


def test_duplicate_zone_and_missing_zone_fail() -> None:
    with pytest.raises(AssertionError):
        matched_zones((ZONE, replace(ZONE, id="duplicate")), {"net": "VIN"}, (POUR, POUR))
    with pytest.raises(AssertionError):
        matched_zones((), {"net": "VIN"}, (POUR,))


def test_refused_zone_must_hold_no_fill() -> None:
    refused = replace(POUR, pieces=(), reason="no-clearance")
    with pytest.raises(AssertionError, match="gained copper"):
        matched_zones((ZONE,), {"net": "VIN"}, (refused,))
    empty = replace(ZONE, fills=())
    assert matched_zones((empty,), {"net": "VIN"}, (refused,)) == ((empty, refused),)
