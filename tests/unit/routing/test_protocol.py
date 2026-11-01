# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The router protocol carries only Fenolite model data and explicit physical constraints."""

from __future__ import annotations

from dataclasses import FrozenInstanceError

import pytest

from fenolite.core.coords import Point
from fenolite.core.evidence import Evidence, Level
from fenolite.model.design import Design
from fenolite.routing.direct import DirectRouter
from fenolite.routing.protocol import (
    ROUTER_FEATURES,
    JobEscape,
    JobNet,
    JobPad,
    JobPair,
    JobRoleEnd,
    JobRoleRoute,
    RoleOutcome,
    Router,
    RouterStatus,
    RoutingJob,
    RoutingResult,
    router_features,
)


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


# --- pairs, escape requests and router features (change c0110) ----------------------------------------


def test_pairs_and_escape_default_to_empty() -> None:
    """Scenario "A job built as before"."""
    design = Design.new("routing-test", seed=1)
    job = RoutingJob(design, (), ("F.Cu",))
    assert job.pairs == () and job.escape == ()
    assert job == RoutingJob(design, (), ("F.Cu",), pairs=(), escape=())
    pair = JobPair("USB_P/USB_N", "USB_P", "USB_N", 200_000, 150_000, skew_max=100_000)
    escape = JobEscape("U1", "perimeter", 500_000, ("Q01", "Q02"))
    held = RoutingJob(design, (), ("F.Cu",), pairs=(pair,), escape=(escape,))
    assert held.pairs[0].via_gap is None and held.escape[0].nets == ("Q01", "Q02")
    with pytest.raises(FrozenInstanceError):
        pair.gap = 1  # type: ignore[misc]


def test_router_features_of_routers_without_a_valid_set() -> None:
    """Scenario "A router without features"."""

    class Bare:
        name = "bare"
        description = "test router"
        sends_data_offsite = False

        def available(self) -> RouterStatus:
            return RouterStatus(True)

        def route(self, job: RoutingJob) -> RoutingResult:
            return RoutingResult()

    class Listed(Bare):
        features = ["pairs"]

    class Unknown(Bare):
        features = frozenset({"pairs", "meanders"})

    class Both(Bare):
        features = frozenset({"pairs", "escape"})

    bare: Router = Bare()
    assert router_features(bare) == frozenset()
    assert router_features(Listed()) == frozenset()
    assert router_features(DirectRouter()) == frozenset()
    assert router_features(Unknown()) == frozenset()
    assert router_features(Both()) == frozenset({"pairs", "escape"})
    assert ROUTER_FEATURES == frozenset({"pairs", "escape", "short", "roles", "propose"})


# --- role routes (change c0244) ---------------------------------------------------------------------------


def test_roles_default_to_empty() -> None:
    """Scenarios "A job built as before" of "Role routes in a routing job" and "A result built as before"."""
    design = Design.new("routing-test", seed=1)
    job = RoutingJob(design, (), ("F.Cu",))
    assert job.roles == ()
    assert job == RoutingJob(design, (), ("F.Cu",), roles=())
    assert RoutingResult().roles == ()
    assert RoutingResult() == RoutingResult(roles=())
    a = JobRoleEnd("R1", "1", "VA", Point(1, 2), ("F.Cu",))
    b = JobRoleEnd("U1", "3", "VA", Point(5, 2), ("F.Cu",))
    key = "kelvin_R1:kelvin:R1-1:U1-3"
    route = JobRoleRoute("kelvin_R1", "kelvin", 1, "VA", a, b, 200_000, ("F.Cu",), key=key)
    held = RoutingJob(design, (), ("F.Cu",), roles=(route,))
    assert held.roles[0].vias == 0 and not held.roles[0].isolated and a.label == "R1-1"
    outcome = RoleOutcome(route.key, route.group, "unrouted", reason="no-room")
    assert outcome.runs == () and outcome.form == ""
    with pytest.raises(FrozenInstanceError):
        route.width = 1  # type: ignore[misc]


# --- proposal subjects and candidates (change c0280) ----------------------------------------------------


def test_propose_subjects_and_candidates_default_to_empty() -> None:
    """Scenarios "A job built as before" of "Proposal subjects in a routing job" and "The octilinear router
    takes roles"."""
    from fenolite.routing.octilinear import OctilinearRouter
    from fenolite.routing.protocol import SUBJECT_KINDS, Candidate, JobAttach, JobSubject

    design = Design.new("routing-test", seed=1)
    job = RoutingJob(design, (), ("F.Cu",))
    assert job.subjects == ()
    assert job == RoutingJob(design, (), ("F.Cu",), subjects=())
    assert RoutingResult().candidates == () and RoutingResult().refusals == ()
    assert RoutingResult() == RoutingResult(candidates=(), refusals=())
    a = JobAttach("pad", "GND", Point(1, 2), ("F.Cu",), "C3-2")
    b = JobAttach("zone", "GND", Point(1, 9), ("B.Cu",), "role.ground.GND.B.Cu")
    subject = JobSubject("fanout:GND:C3-2", "fanout", "GND", a, b, 250_000, ("F.Cu", "B.Cu"))
    held = RoutingJob(design, (), ("F.Cu", "B.Cu"), subjects=(subject,))
    assert held.subjects[0].via_diameter == 0 and held.subjects[0].group == ""
    candidate = Candidate("c-0000000000000000", subject.key, "fanout")
    assert candidate.relaxed == () and candidate.tracks == candidate.vias == ()
    assert SUBJECT_KINDS == ("fanout", "join", "role-net", "group", "connection")
    with pytest.raises(FrozenInstanceError):
        subject.width = 1  # type: ignore[misc]
    assert router_features(OctilinearRouter()) == frozenset({"pairs", "short", "roles", "propose"})
