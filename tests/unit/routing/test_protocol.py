# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The router protocol carries only Fenolite model data and explicit physical constraints."""

from __future__ import annotations

from dataclasses import FrozenInstanceError

import pytest

from fenolite.core.coords import Point
from fenolite.core.evidence import Evidence, Level
from fenolite.model.design import Design
from fenolite.routing.protocol import JobNet, JobPad, Router, RouterStatus, RoutingJob, RoutingResult


def test_job_is_model_data_with_nm_constraints() -> None:
    pad = JobPad("U1", "1", "GND", Point(1, 2), ("F.Cu",), drill=300_000)
    net = JobNet("GND", "ne_00000000-0000-0000-0000-000000000001", (pad,), 250_000, 200_000, 600_000, 300_000)
    job = RoutingJob(Design.new("routing-test", seed=1), (net,), ("F.Cu", "B.Cu"), {"grid-step": "0.1"})

    assert job.nets[0].pads[0].position == Point(1, 2)
    assert job.nets[0].width == 250_000
    assert job.layers == ("F.Cu", "B.Cu")
    with pytest.raises(FrozenInstanceError):
        pad.number = "2"  # type: ignore[misc]


def test_result_defaults_to_unverified_proposal() -> None:
    result = RoutingResult()

    assert result.tracks == result.arcs == result.vias == ()
    assert result.evidence == Evidence(Level.UNVERIFIED)


def test_router_protocol_has_readiness_and_route_contract() -> None:
    class StubRouter:
        name = "stub"
        description = "test router"
        sends_data_offsite = False

        def available(self) -> RouterStatus:
            return RouterStatus(True, path="/router", version="1")

        def route(self, job: RoutingJob) -> RoutingResult:
            return RoutingResult(unrouted=tuple(net.name for net in job.nets))

    router: Router = StubRouter()
    job = RoutingJob(Design.new("routing-test", seed=1), (), ())
    assert router.available().available
    assert router.route(job).unrouted == ()
