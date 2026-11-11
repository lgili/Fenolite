# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""In-memory routing checks for exact pad connections on a placed candidate."""

from collections import defaultdict

from fenolite.backends.base import BoardPad, DesignRules
from fenolite.backends.kicad.layers import plane_layers
from fenolite.checks.clearance import ClearanceResolver
from fenolite.core.coords import Point
from fenolite.model.board import rule_areas
from fenolite.model.design import Design
from fenolite.model.rules import RuleSubject
from fenolite.placement.intent import PlacementIntent, probe_intent_legs
from fenolite.placement.optimization_contract import PadProbe
from fenolite.placement.topology import PadIdentity
from fenolite.routing.layers import allowed_layers, routing_layers
from fenolite.routing.octilinear import World, length
from fenolite.routing.protocol import JobAttach, JobNet, JobSubject, RoutingJob
from fenolite.routing.search import Limits, search
from fenolite.routing.search_grid import Stop


def _physical_attachments(
    pads: tuple[BoardPad, ...],
) -> dict[tuple[str, str, Point], list[BoardPad]]:
    result: dict[tuple[str, str, Point], list[BoardPad]] = defaultdict(list)
    for pad in pads:
        if pad.net is not None and pad.copper:
            result[(pad.net, f"{pad.ref}-{pad.number}", pad.position)].append(pad)
    return result


def probe_pad_connections(
    job: RoutingJob,
    pads: tuple[BoardPad, ...],
    outline: tuple[tuple[Point, ...], ...],
    limits: Limits,
    *,
    max_length: int,
    edge_clearance: int = 0,
    stop: Stop = lambda: None,
) -> tuple[PadProbe, ...]:
    """Test the same pad-to-pad scope under fixed bounds, keeping provisional tracks in memory.

    The initial adapter checks same-layer tracks. Coupled subjects stay unsupported. Each
    later route must fit around the provisional earlier routes. Success is scoped to the
    supplied geometry and connection set. A refusal can depend on their order and budget.
    """
    if limits.max_vias != 0 or max_length <= 0:
        raise ValueError("placement probes need positive length and a zero via bound")
    subjects = tuple(sorted(job.subjects, key=lambda row: row.key))
    if len({row.key for row in subjects}) != len(subjects):
        raise ValueError("placement probe subjects need distinct keys")
    board = job.design.board
    if (
        board is None
        or not outline
        or not job.layers
        or job.extra.get("outline") != outline
        or board.holes
        or board.zones
        or board.verbatim
        or rule_areas(board)
        or any(item.layer in job.layers for item in (*board.graphics, *board.texts))
        or any(item.layer in job.layers for fp in board.footprints for item in (*fp.graphics, *fp.texts))
    ):
        return tuple(PadProbe(subject.key, "unsupported-geometry") for subject in subjects)

    attachments = _physical_attachments(pads)
    world = World(job, pads, outline)
    world.edge = max(world.edge, edge_clearance)

    def matches(end: JobAttach, subject: JobSubject) -> bool:
        found = attachments.get((end.net, end.name, end.at), ())
        return (
            end.kind == "pad"
            and end.net == subject.net
            and len(found) == 1
            and bool(end.layers)
            and set(end.layers) <= {entry.layer for entry in found[0].copper}
        )

    results: list[PadProbe] = []
    for subject in subjects:
        if reason := stop():
            results.append(PadProbe(subject.key, reason))
            continue
        if subject.kind != "connection":
            results.append(PadProbe(subject.key, "search-unsupported"))
            continue
        if not matches(subject.a, subject) or not matches(subject.b, subject):
            results.append(PadProbe(subject.key, "unresolved-pad"))
            continue
        if subject.width <= 0:
            results.append(PadProbe(subject.key, "unknown-width"))
            continue
        outcome = search(job, subject, world, limits, max_length=max_length, stop=stop)
        expanded = outcome.stats.expanded if outcome.stats else 0
        if outcome.reason or not outcome.runs:
            results.append(PadProbe(subject.key, outcome.reason or "no-room", expanded=expanded))
            continue
        for layer, points in outcome.runs:
            world.place(subject.net, layer, points, subject.width)
        results.append(
            PadProbe(subject.key, "found", sum(length(points) for _, points in outcome.runs), expanded)
        )
    return tuple(results)


def probe_placement_intents(
    design: Design,
    rules: DesignRules,
    pads: tuple[BoardPad, ...],
    outline: tuple[tuple[Point, ...], ...],
    intents: tuple[PlacementIntent, ...],
    *,
    max_states: int,
    pitch: int,
) -> tuple[PadProbe, ...]:
    """Resolve reviewed physical IDs into the router's exact pad-to-pad subjects."""
    if not intents:
        return ()
    expanded = {row.key: probe_intent_legs(row) for row in intents}
    if not all(expanded.values()):
        raise ValueError("escape probes need exact pads and a positive path length")
    legs = tuple(leg for group in expanded.values() for leg in group)
    board = design.board
    if (
        board is None
        or rules.unread
        or rules.opaque_clearance_rules
        or rules.left_out
        or (
            design.rules is not None
            and any(rule.kind == "track_width" and rule.severity != "ignore" for rule in design.rules.rules)
        )
    ):
        return tuple(PadProbe(row.key, "unsupported-rules") for row in intents)
    assert board is not None
    if max_states < 1:
        return tuple(PadProbe(row.key, "budget") for row in intents)
    layers = tuple(
        layer.name for layer in sorted(board.layers, key=lambda item: item.ordinal) if layer.kind == "copper"
    )
    planes = plane_layers(design)
    routable = routing_layers(layers, planes)
    physical = {PadIdentity(pad.footprint_id, pad.pad_id): pad for pad in pads}
    for group in expanded.values():
        if len(group) > 1:
            drive = physical.get(group[0].endpoints[0])
            ret = physical.get(group[1].endpoints[0])
            if drive is None or ret is None or drive.net_id == ret.net_id:
                return tuple(PadProbe(item.key, "unresolved-loop-nets") for item in intents)
    nets = {net.id: net for net in design.circuit.nets}
    classes = {item.id: item for item in design.circuit.netclasses}
    default = next((item for item in classes.values() if item.name.casefold() == "default"), None)
    job_nets: dict[str, JobNet] = {}
    subjects: list[JobSubject] = []
    for row in legs:
        first, second = (physical.get(identity) for identity in row.endpoints)
        if first is None or second is None or first.net_id is None or first.net_id != second.net_id:
            return tuple(PadProbe(item.key, "unresolved-net") for item in intents)
        net = nets.get(first.net_id)
        if net is None:
            return tuple(PadProbe(item.key, "unresolved-net") for item in intents)
        cls = classes.get(net.netclass_id or "", default)
        width = cls.track_width if cls else None
        clearance = cls.clearance if cls and cls.clearance is not None else rules.min_clearance
        if not width or clearance is None:
            return tuple(PadProbe(item.key, "unknown-net-dimensions") for item in intents)
        permitted = allowed_layers(design, net, routable)
        job_nets[net.id] = JobNet(net.name, net.id, (), width, clearance, 0, 0, permitted)
        a, b = (
            JobAttach("pad", net.name, pad.position, pad.layers, f"{pad.ref}-{pad.number}")
            for pad in (first, second)
        )
        subjects.append(JobSubject(row.key, "connection", net.name, a, b, width, permitted))
    resolver = ClearanceResolver(
        design,
        min_clearance=rules.min_clearance,
        rules_over_classes=rules.rules_over_classes,
        floor_over_rules=rules.floor_over_rules,
        min_edge_clearance=rules.min_edge_clearance,
        edge_floor_over_rules=rules.edge_floor_over_rules,
        min_hole_clearance=rules.min_hole_clearance,
    )
    conservative_clearance = max(resolver.max_value, resolver.max_hole)

    def clearance_between(_a: RuleSubject, _b: RuleSubject) -> int:
        # The router's obstacle subjects do not carry every selector attribute.
        return conservative_clearance

    job = RoutingJob(
        design,
        tuple(job_nets.values()),
        layers,
        extra={"outline": outline, "clearance": clearance_between},
        plane_layers=planes,
        subjects=tuple(subjects),
    )
    grid = min(pitch, max(1, min(subject.width for subject in subjects) // 2))
    max_lengths = {intent.key: intent.max_distance_nm or 0 for intent in legs}
    checks = probe_pad_connections(
        job,
        pads,
        outline,
        Limits(grid, max_states, 0),
        max_length=max(max_lengths.values()),
        edge_clearance=resolver.max_edge,
    )
    results = {
        row.key: (
            PadProbe(row.key, "too-long", expanded=row.expanded)
            if row.length_nm is not None and row.length_nm > max_lengths[row.key]
            else row
        )
        for row in checks
    }
    for group in expanded.values():
        if len(group) > 1 and any(results[leg.key].status != "found" for leg in group):
            for leg in group:
                observed = results[leg.key]
                if observed.status == "found":
                    results[leg.key] = PadProbe(leg.key, "group-failed", expanded=observed.expanded)
    return tuple(results.values())
