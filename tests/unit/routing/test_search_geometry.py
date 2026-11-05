# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""c0365 exact attachment, swept geometry and through-barrel negative proofs."""

from dataclasses import replace

import pytest
from _searchbench import MM, bench, point, wall

from fenolite.core.coords import Point
from fenolite.geometry import Location, point_in_ring
from fenolite.routing.protocol import JobPair
from fenolite.routing.search import Limits, search

LIMITS = Limits(MM, 20_000, 0)


def test_maze_detour_preserves_world_and_obstacles() -> None:
    tracks = (wall("one", 4, 0, 6), wall("two", 8, 4, 10))
    job, subject, world = bench(tracks=tracks, allowed=("F.Cu",))
    before = (job.design, tuple(world.placed), dict(world.ends))
    out = search(job, subject, world, LIMITS, max_length=40 * MM)
    assert out.runs and not out.reason
    assert out.stats and out.stats.termination == "found"
    for layer, points in out.runs:
        assert world.fits("SIG", layer, points, subject.width)
    points = tuple(p for _, run in out.runs for p in run)
    assert any(p.y > 6 * MM for p in points) and any(p.y < 4 * MM for p in points)
    assert before == (job.design, tuple(world.placed), dict(world.ends))


def test_off_grid_attachments_are_exact_and_octilinear() -> None:
    start, end = Point(2_200_000, 3_300_000), Point(9_600_000, 6_700_000)
    job, subject, world = bench(start=start, end=end)
    out = search(job, subject, world, LIMITS, max_length=30 * MM)
    assert out.runs[0][1][0] == start and out.runs[-1][1][-1] == end
    for _, points in out.runs:
        for a, b in zip(points, points[1:], strict=False):
            dx, dy = abs(a.x - b.x), abs(a.y - b.y)
            assert dx == 0 or dy == 0 or dx == dy


def test_swept_diagonal_cannot_cut_through_obstacle_between_grid_points() -> None:
    obstacle = wall("diagonal_obstacle", 4, 4, 5, width=300_000)
    job, subject, world = bench(start=point(2, 2), end=point(8, 8), tracks=(obstacle,), allowed=("F.Cu",))
    out = search(job, subject, world, Limits(2 * MM, 20_000, 0), max_length=40 * MM)
    assert out.runs
    assert all(world.fits("SIG", layer, points, subject.width) for layer, points in out.runs)
    assert any(
        a.x == b.x or a.y == b.y for _, points in out.runs for a, b in zip(points, points[1:], strict=False)
    )


def test_cutout_is_not_a_path_or_via_region() -> None:
    hole = (point(5, 3), point(7, 3), point(7, 7), point(5, 7))
    job, subject, world = bench(holes=(hole,), allowed=("F.Cu",))
    out = search(job, subject, world, LIMITS, max_length=30 * MM)
    assert out.runs
    assert all(point_in_ring(p, hole) is Location.OUTSIDE for _, points in out.runs for p in points)
    assert all(world.fits("SIG", layer, points, subject.width) for layer, points in out.runs)


def test_via_barrel_checks_inner_layers_even_when_tracks_use_outer_layers_only() -> None:
    layers = ("F.Cu", "In1.Cu", "In2.Cu", "B.Cu")
    obstacle = wall("inner_barrier", 6, 0, 10, "In1.Cu", width=24 * MM)
    args = dict(layers=layers, ends=(("F.Cu",), ("B.Cu",)), allowed=("F.Cu", "B.Cu"))
    job, subject, world = bench(**args, tracks=(obstacle,))
    failed = search(job, subject, world, Limits(MM, 20_000, 1), max_length=30 * MM)
    assert not failed.runs and not failed.vias and failed.reason == "no-room"
    job, subject, world = bench(**args)
    passed = search(job, subject, world, Limits(MM, 20_000, 1), max_length=30 * MM)
    assert len(passed.vias) == 1 and not passed.reason
    assert set(layer for layer, _ in passed.runs) <= {"F.Cu", "B.Cu"}


def test_via_resource_limit_is_enforced() -> None:
    job, subject, world = bench(ends=(("F.Cu",), ("B.Cu",)))
    out = search(job, subject, world, LIMITS, max_length=30 * MM)
    assert not out.runs and not out.vias and out.reason == "no-room"


@pytest.mark.parametrize("kind", ["group", "fanout", "join", "role-net"])
def test_unsupported_subjects_are_explicit(kind: str) -> None:
    job, subject, world = bench()
    assert (
        search(job, replace(subject, kind=kind), world, LIMITS, max_length=30 * MM).reason
        == "search-unsupported"
    )


def test_pair_cannot_be_routed_as_independent_leg() -> None:
    job, subject, world = bench()
    job = replace(job, pairs=(JobPair("pair", "SIG", "OTHER", 100_000, 100_000),))
    assert search(job, subject, world, LIMITS, max_length=30 * MM).reason == "search-unsupported"


def test_missing_outline_and_end_in_hole_refuse_geometry() -> None:
    job, subject, world = bench()
    assert (
        search(replace(job, extra={}), subject, world, LIMITS, max_length=30 * MM).reason == "search-geometry"
    )
    hole = (point(1, 4), point(3, 4), point(3, 6), point(1, 6))
    job, subject, world = bench(holes=(hole,))
    assert search(job, subject, world, LIMITS, max_length=30 * MM).reason == "search-geometry"


def test_no_allowed_layer_and_max_length() -> None:
    job, subject, world = bench(allowed=("In1.Cu",))
    assert search(job, subject, world, LIMITS, max_length=30 * MM).reason == "no-layer"
    job, subject, world = bench()
    assert search(job, subject, world, LIMITS, max_length=MM).reason == "too-long"


def test_model_pairs_are_protected_even_when_job_has_no_pair_records() -> None:
    from fenolite.model.circuit import Interface, Net

    job, subject, world = bench()
    named = replace(
        job.design, circuit=replace(job.design.circuit, nets=(Net(id="p", name="DP"), Net(id="n", name="DN")))
    )
    assert (
        search(
            replace(job, design=named), replace(subject, net="DP"), world, LIMITS, max_length=30 * MM
        ).reason
        == "search-unsupported"
    )
    interface = Interface(
        id="pair", name="authored", kind="diff_pair", members={"p": "net_sig", "n": "other"}
    )
    model = replace(job.design, circuit=replace(job.design.circuit, interfaces=(interface,)))
    assert (
        search(replace(job, design=model), subject, world, LIMITS, max_length=30 * MM).reason
        == "search-unsupported"
    )
