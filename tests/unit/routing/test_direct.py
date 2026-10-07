# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The built-in direct router handles simple two-pad nets deterministically."""

from pathlib import Path

from fenolite.backends.kicad.pcb import read_board
from fenolite.core.coords import Point
from fenolite.model.design import Design
from fenolite.routing.direct import DirectRouter
from fenolite.routing.protocol import JobNet, JobPad, RoutingJob
from fenolite.routing.select import unrouted


def test_two_pad_net_routes_on_first_shared_layer() -> None:
    pads = (
        JobPad("J1", "1", "A", Point(100, 200), ("F.Cu", "B.Cu")),
        JobPad("J2", "1", "A", Point(300, 400), ("F.Cu", "B.Cu")),
    )
    job = RoutingJob(
        Design.new("direct", seed=1),
        (JobNet("A", "net_a", pads, 250_000, 200_000, 600_000, 300_000),),
        ("F.Cu", "B.Cu"),
    )
    result = DirectRouter().route(job)
    assert result.routed == ("A",) and result.unrouted == ()
    assert len(result.tracks) == 1
    track = result.tracks[0]
    assert (track.start, track.end, track.layer, track.width, track.net_id) == (
        Point(100, 200),
        Point(300, 400),
        "F.Cu",
        250_000,
        "net_a",
    )


def test_skips_three_pad_or_layer_disjoint_nets_and_is_deterministic() -> None:
    pads = (
        JobPad("J1", "1", "A", Point(0, 0), ("F.Cu",)),
        JobPad("J2", "1", "A", Point(1, 0), ("B.Cu",)),
    )
    three = JobNet("THREE", "net_three", (*pads, pads[0]), 250_000, 200_000, 600_000, 300_000)
    disjoint = JobNet("DISJOINT", "net_disjoint", pads, 250_000, 200_000, 600_000, 300_000)
    job = RoutingJob(Design.new("direct", seed=1), (three, disjoint), ("F.Cu", "B.Cu"))
    router = DirectRouter()
    first = router.route(job)
    second = router.route(job)
    assert first.routed == first.tracks == ()
    assert first.unrouted == ("THREE", "DISJOINT")
    assert first == second


def test_authored_two_pad_board_is_an_unrouted_candidate() -> None:
    path = Path(__file__).resolve().parents[2] / "data/kicad/routing/two_pads.kicad_pcb"
    design = read_board(path)
    assert unrouted(design, ("ROUTE_ME",)) == ("ROUTE_ME",)
    assert unrouted(design, ()) == ()
    assert len(design.by_net["ROUTE_ME"]) == 2
