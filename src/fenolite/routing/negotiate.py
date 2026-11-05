# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Authored bounded congestion negotiation over job-owned provisional copper (c0367)."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass, replace
from typing import cast

from fenolite.core.coords import Point
from fenolite.core.evidence import Evidence, Level
from fenolite.core.ids import content_hash
from fenolite.geometry import Thick, thick_closer_than
from fenolite.model.canonical import to_data
from fenolite.routing.bundles import make
from fenolite.routing.octilinear import MARGIN, World, length
from fenolite.routing.protocol import Candidate, RoutingJob, RoutingResult
from fenolite.routing.search import Limits, coupled_nets, search
from fenolite.routing.search_fields import FIELD_EVIDENCE, Fields, Provenance, board_fingerprint, rejection
from fenolite.routing.search_grid import Stop

EVIDENCE = Evidence(Level.INFERRED, hypotheses=("H-G-ROUTE-NEGOTIATE", "H-G-ROUTE-BUNDLE"))

OPTIONS = ("negotiate", "negotiate-max-rounds")


def options(given: Mapping[str, str]) -> int | None:
    mode = given.get("negotiate", "off")
    if mode not in ("off", "on"):
        raise ValueError("negotiate must be off or on")
    raw = given.get("negotiate-max-rounds", "")
    if mode == "off":
        if "negotiate-max-rounds" in given:
            raise ValueError("negotiate-max-rounds requires negotiate=on")
        return None
    if not raw.isascii() or not raw.isdigit() or int(raw) < 1:
        raise ValueError("negotiate=on requires a positive negotiate-max-rounds")
    return int(raw)


@dataclass(frozen=True, slots=True)
class Occupied:
    net: str
    layer: str
    shape: Thick


@dataclass(frozen=True, slots=True)
class Outcome:
    members: tuple[Candidate, ...] = ()
    reason: str = ""
    rounds: int = 0
    discovered: int = 0


def shapes(candidate: Candidate, job: RoutingJob) -> tuple[Occupied, ...]:
    names = {n.id: n.name for n in job.design.circuit.nets}
    held = [
        Occupied(names.get(t.net_id or "", ""), t.layer, Thick((t.start, t.end), t.width))
        for t in candidate.tracks
    ]
    for via in candidate.vias:
        at = via.position
        for layer in job.layers:
            held.append(
                Occupied(
                    names.get(via.net_id or "", ""), layer, Thick((at, Point(at.x + 1, at.y)), via.diameter)
                )
            )
    return tuple(held)


def clashes(a: Occupied, b: Occupied, world: World) -> bool:
    return (
        a.net != b.net
        and a.layer == b.layer
        and thick_closer_than(
            a.shape,
            b.shape,
            world.clearance(world.subject(a.net, a.layer), world.subject(b.net, b.layer)) + MARGIN,
        )
    )


@dataclass(frozen=True, slots=True)
class Cost:
    world: World
    current: tuple[Occupied, ...]
    history: tuple[Occupied, ...]
    weight: int

    def __call__(self, net: str, layer: str, points: tuple[Point, ...], width: int) -> int:
        mine = Occupied(net, layer, Thick(points, width))
        present = sum(clashes(mine, other, self.world) for other in self.current)
        previous = sum(clashes(mine, other, self.world) for other in self.history)
        return max(length(points), 1) * 1000 * (self.weight * present + previous)


def negotiate(
    job: RoutingJob, world: World, limits: Limits, rounds: int, *, max_length: int, stop: Stop = lambda: None
) -> Outcome:
    """Return only complete nonoverlapping provisional sets; final judges are a separate gate."""
    from fenolite.routing.propose import search_candidate

    if type(rounds) is not int or rounds < 1:
        raise ValueError("negotiation rounds must be positive")
    ordered = sorted(job.subjects, key=lambda subject: subject.key)
    if len(ordered) < 2 or len({s.key for s in ordered}) != len(ordered):
        return Outcome(reason="negotiate-subjects")
    pairs = coupled_nets(job)
    if any(s.kind != "connection" or s.net in pairs for s in ordered):
        return Outcome(reason="negotiate-unsupported")
    candidates: dict[str, Candidate] = {}
    occupancy: dict[str, tuple[Occupied, ...]] = {}
    history: list[Occupied] = []
    discovered = 0
    for iteration in range(1, rounds + 1):
        for subject in ordered:
            if why := stop():
                return Outcome(reason=why, rounds=iteration, discovered=discovered)
            left = limits.max_states - discovered
            if left < 1:
                return Outcome(reason="state-limit", rounds=iteration, discovered=discovered)
            occupancy.pop(subject.key, None)
            others = tuple(item for held in occupancy.values() for item in held)

            cost = Cost(world, others, tuple(history), iteration - 1)

            trial = replace(job, extra={**job.extra, "_negotiation_cost": cost})
            found = search(
                trial, subject, world, replace(limits, max_states=left), max_length=max_length, stop=stop
            )
            discovered += found.stats.discovered if found.stats is not None else 0
            if found.reason or not found.runs:
                return Outcome(reason=found.reason or "no-room", rounds=iteration, discovered=discovered)
            made = search_candidate(job, subject, found.runs, found.vias)
            candidates[subject.key] = made
            occupancy[subject.key] = shapes(made, job)
        conflicts: list[Occupied] = []
        for i, subject in enumerate(ordered):
            for other in ordered[i + 1 :]:
                if why := stop():
                    return Outcome(reason=why, rounds=iteration, discovered=discovered)
                for a in occupancy[subject.key]:
                    for b in occupancy[other.key]:
                        if clashes(a, b, world):
                            conflicts.extend((a, b))
        if not conflicts:
            return Outcome(tuple(candidates[s.key] for s in ordered), rounds=iteration, discovered=discovered)
        history.extend(conflicts)
    return Outcome(reason="negotiate-round-limit", rounds=rounds, discovered=discovered)


def joint_geometry(job: RoutingJob, world: World, members: tuple[Candidate, ...]) -> bool:
    expected = {s.key: s for s in job.subjects}
    if len(members) != len(expected) or {c.subject for c in members} != set(expected):
        return False
    if any(c.arcs or not c.tracks for c in members):
        return False
    names = {n.id: n.name for n in job.design.circuit.nets}
    all_shapes: list[Occupied] = []
    for c in members:
        subject = expected[c.subject]
        if any(
            names.get(t.net_id or "") != subject.net
            or t.width < subject.width
            or t.layer not in subject.layers
            or not world.fits(subject.net, t.layer, (t.start, t.end), t.width)
            for t in c.tracks
        ):
            return False
        held = shapes(c, job)
        for item in held:
            if not world.fits(item.net, item.layer, item.shape.core, item.shape.width):
                return False
            if any(clashes(item, other, world) for other in all_shapes):
                return False
        all_shapes.extend(held)
    return True


def propose(
    job: RoutingJob, world: World, limits: Limits, rounds: int, *, max_length: int, stop: Stop = lambda: None
) -> RoutingResult:
    """Withhold the complete set until geometry, both judges and adapter connectivity agree."""
    given = job.extra.get("bundle_check")
    checker = cast(Callable[[tuple[Candidate, ...]], str], given) if callable(given) else None
    found = (
        negotiate(job, world, limits, rounds, max_length=max_length, stop=stop)
        if checker is not None
        else Outcome(reason="negotiate-judge-missing")
    )
    reason = found.reason
    if found.members and not joint_geometry(job, world, found.members):
        found = replace(found, members=(), reason="negotiate-refused")
        reason = found.reason
    if found.members:
        fields = job.extra.get("search_fields")
        if not isinstance(fields, Fields):
            digest = content_hash(None)
            fields = Fields(Provenance(board_fingerprint(job.design), digest, digest, digest), job.layers)
        joint = replace(
            found.members[0],
            tracks=tuple(t for c in found.members for t in c.tracks),
            vias=tuple(v for c in found.members for v in c.vias),
        )
        reason = rejection(job, joint, fields)
        if not reason and checker is not None:
            judged = checker(found.members)
            reason = "" if type(judged) is str and not judged else "negotiate-refused"
        if not reason and (cut := stop()):
            reason = cut
        if not reason:
            fingerprint = content_hash(
                board_fingerprint(job.design),
                fields.fingerprint,
                to_data(tuple(sorted(job.subjects, key=lambda subject: subject.key))),
                {k: v for k, v in job.options.items() if k != "candidates"},
                job.extra.get("_bundle_input"),
            )
            bundle = make(found.members, fingerprint)
            return RoutingResult(
                candidates=bundle.members,
                bundles=(bundle,),
                tool="octilinear",
                tool_version="builtin",
                evidence=Evidence.combine(EVIDENCE, FIELD_EVIDENCE),
                log=(f"negotiation rounds={found.rounds}; discovered={found.discovered}",),
            )
    return RoutingResult(
        tool="octilinear",
        tool_version="builtin",
        evidence=Evidence.combine(EVIDENCE, FIELD_EVIDENCE),
        refusals=tuple((s.key, reason or "negotiate-refused", ()) for s in job.subjects),
        log=(f"negotiation rounds={found.rounds}; discovered={found.discovered}",),
    )
