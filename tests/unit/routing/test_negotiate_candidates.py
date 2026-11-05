# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Joint validation, complete-set emission and interrupted/unsupported refusal (c0367)."""

from dataclasses import replace

import pytest
from _negotiatebench import negotiation_bench

from fenolite.core.ids import content_hash
from fenolite.routing.negotiate import Outcome, propose
from fenolite.routing.octilinear import OctilinearRouter
from fenolite.routing.protocol import JobPair
from fenolite.routing.search_fields import Fields, Provenance, board_fingerprint

OPTIONS = {
    "search": "only",
    "search-grid": "0.5mm",
    "search-max-states": "40000",
    "search-max-vias": "0",
    "negotiate": "on",
    "negotiate-max-rounds": "5",
    "max-length": "40mm",
}


def prepared():
    job, world = negotiation_bench()
    return replace(job, options=OPTIONS, extra={**job.extra, "bundle_check": lambda members: ""}), world


def test_router_emits_only_one_atomic_joint_alternative_without_copper_mutation() -> None:
    job, _ = prepared()
    result = OctilinearRouter().route(job)
    assert len(result.bundles) == 1 and len(result.candidates) == 2
    bundle = result.bundles[0]
    assert bundle.members == result.candidates and all(c.bundle == bundle.id for c in result.candidates)
    assert not (result.tracks or result.arcs or result.vias or result.refusals)
    assert result == OctilinearRouter().route(job)
    assert result == OctilinearRouter().route(replace(job, subjects=tuple(reversed(job.subjects))))
    assert "H-G-ROUTE-NEGOTIATE" in result.evidence.hypotheses


def test_round_exhaustion_has_no_candidates_or_bundles() -> None:
    job, _ = prepared()
    out = OctilinearRouter().route(replace(job, options={**OPTIONS, "negotiate-max-rounds": "1"}))
    assert not (out.bundles or out.candidates)
    assert len(out.refusals) == 2 and all(r[1] == "negotiate-round-limit" for r in out.refusals)


@pytest.mark.parametrize("mode", ["missing", "refused", "invalid"])
def test_whole_set_judge_is_required_and_fail_closed(mode: str) -> None:
    job, _ = prepared()
    extra = dict(job.extra)
    if mode == "missing":
        del extra["bundle_check"]
    else:
        extra["bundle_check"] = lambda members: "connectivity" if mode == "refused" else None
    out = OctilinearRouter().route(replace(job, extra=extra))
    assert not (out.bundles or out.candidates)


def test_fresh_copper_failure_rejects_the_whole_bundle() -> None:
    job, _ = prepared()
    extra = {
        **job.extra,
        "copper_check": lambda design: [] if design == job.design else [("clearance", "F.Cu", ("new",), 1)],
    }
    out = OctilinearRouter().route(replace(job, extra=extra))
    assert not (out.bundles or out.candidates)


def test_confirmed_role_failure_rejects_the_whole_bundle() -> None:
    job, _ = prepared()
    digest = content_hash(None)
    fields = Fields(
        Provenance(board_fingerprint(job.design), digest, digest, digest),
        job.layers,
        confirmed_groups=("confirmed",),
    )
    extra = {
        **job.extra,
        "search_fields": fields,
        "role_check": lambda design: (
            [] if design == job.design else [("roles.gate-length", "confirmed", "warning", 10)]
        ),
    }
    out = OctilinearRouter().route(replace(job, extra=extra))
    assert not (out.bundles or out.candidates)


def test_a_pair_leg_is_not_emitted_independently() -> None:
    job, _ = prepared()
    out = OctilinearRouter().route(replace(job, pairs=(JobPair("p", "SIG", "WALL", 100_000, 100_000),)))
    assert not (out.bundles or out.candidates) and out.refusals[0][1] == "negotiate-unsupported"


def test_cancel_after_one_provisional_route_exports_nothing(monkeypatch) -> None:
    from fenolite.routing import negotiate as module

    job, _ = prepared()
    real = module.search
    visited = []

    def search(*args, **kwargs):
        result = real(*args, **kwargs)
        visited.append(True)
        return result

    monkeypatch.setattr(module, "search", search)
    job = replace(job, extra={**job.extra, "cancelled": lambda: bool(visited)})
    result = OctilinearRouter().route(job)
    assert visited and not (result.candidates or result.bundles) and result.refusals[0][1] == "cancelled"


def test_joint_geometry_cannot_be_bypassed_by_adapter_approval(monkeypatch) -> None:
    from fenolite.routing import negotiate as module
    from fenolite.routing.propose import search_candidate

    job, world = prepared()
    members = tuple(search_candidate(job, s, (("F.Cu", (s.a.at, s.b.at)),), ()) for s in job.subjects)
    monkeypatch.setattr(module, "negotiate", lambda *args, **kwargs: Outcome(members=members))
    result = propose(job, world, module.Limits(500_000, 40_000, 0), 5, max_length=40_000_000)
    assert not (result.candidates or result.bundles) and result.refusals[0][1] == "negotiate-refused"


def test_default_router_result_is_unchanged_when_negotiation_is_off() -> None:
    job, _ = prepared()
    legacy = replace(job, options={k: v for k, v in OPTIONS.items() if not k.startswith("negotiate")})
    off = replace(legacy, options={**legacy.options, "negotiate": "off"})
    assert OctilinearRouter().route(legacy).candidates == OctilinearRouter().route(off).candidates
    assert not OctilinearRouter().route(off).bundles


@pytest.mark.parametrize("given", [{"negotiate": "off"}, {"negotiate": "on", "negotiate-max-rounds": "2"}])
def test_direct_routing_job_cannot_silently_ignore_proposal_only_negotiation(given) -> None:
    job, _ = prepared()
    with pytest.raises(ValueError, match="proposal"):
        OctilinearRouter().route(replace(job, subjects=(), options=given))
