# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Conservative topology budgets lowered into already supported KiCad length constraints.

Only a proven whole-net track chain with one propagation and no via/die offset can mean the same
thing as KiCad's net-total length. Endpoint skew within a single net has no equivalent net-skew rule.
"""

from __future__ import annotations

from collections import Counter

from fenolite.backends.kicad.frame import board_pads
from fenolite.core.errors import Issue
from fenolite.core.evidence import Evidence, Level
from fenolite.core.ids import derived_id
from fenolite.geometry import (
    SegmentRelation,
    Thick,
    Transform,
    classify_segments,
    intersection_point,
    segment_length,
    thick_touch,
)
from fenolite.model.design import Design
from fenolite.model.pairs import pair_base
from fenolite.model.rules import Rule, RuleSet, Selector, Topology

EVIDENCE = Evidence(Level.INFERRED, hypotheses=("H-G-TOPO-DELAY",))
"""Conservative conversions of user-stated topology inputs; no native time-domain claim."""


def _propagation(topology: Topology, rules: RuleSet, design: Design | None) -> tuple[int | None, str]:
    if design is None or design.board is None:
        return None, "no routed board was supplied to prove whole-net coverage"
    if topology.missing_bridges or any(edge.kind == "bridge" for edge in topology.edges):
        return None, "the path crosses a series bridge"
    nets = {edge.net for edge in topology.edges}
    if len(nets) != 1 or len(topology.nodes) != 2:
        return None, "the path is not one complete two-terminal net"
    name = next(iter(nets))
    net = next((net for net in design.circuit.nets if net.name == name), None)
    if net is None:
        return None, "the net is absent from the board"
    board = design.board
    if any(item.net_id == net.id for item in (*board.vias, *board.arcs, *board.zones)):
        return None, "vias, arcs or zones prevent the whole-net length equivalence proof"
    tracks = tuple(track for track in board.tracks if track.net_id == net.id)
    if not tracks:
        return None, "the net has no proven whole-net track route"
    values = {row.layer: row.per_mm_fs for row in rules.propagation if row.layer}
    layers = {track.layer for track in tracks}
    if len(layers) != 1:
        return None, "a layer transition has no proven equivalent net-total delay"
    if any(layer not in values for layer in layers) or len({values[layer] for layer in layers}) != 1:
        return None, "the used layers do not share one stated propagation"
    propagation = values[next(iter(layers))]
    if propagation is None or propagation <= 0:
        return None, "the propagation is not positive"
    if any(segment_length(track.start, track.end) * propagation % 1_000_000 for track in tracks):
        return None, "per-segment rounding has no equivalent net-total length rule"
    components = {part.id: part for part in design.circuit.components}
    pads: dict[str, object] = {}
    for footprint in board.footprints:
        component = components.get(footprint.component_id)
        if component is None:
            continue
        for pad in footprint.pads:
            if pad.net_id != net.id:
                continue
            if pad.die_delay_fs or any(
                "(die_delay" in text or "(die_length" in text
                for bag in pad.ext.values()
                for _, text in bag.payload
            ):
                return None, "a pad has a die offset"
            point = Transform.placement(footprint.position, footprint.rotation).apply(pad.position)
            for pin in component.pins:
                if pad.number in component.pads_of(pin.number):
                    pads[f"{component.ref}-{pin.number}"] = point
            pads[f"{component.ref}-{pad.number}"] = point
    if any(name not in pads for name in topology.nodes) or len(set(pads.values())) != 2:
        return None, "the net does not hold exactly the two constrained pad locations"
    degree = Counter(point for track in tracks for point in (track.start, track.end))
    if any(value > 2 for value in degree.values()) or {
        point for point, value in degree.items() if value == 1
    } != set(pads.values()):
        return None, "the routing is not one unbranched pad-to-pad track chain"
    internal = tuple(point for point, count in degree.items() if count == 2)
    for record in board_pads(design):
        if record.net_id != net.id:
            continue
        if not record.copper or any(not shape.exact for shape in record.copper):
            return None, "exact endpoint pad copper is unavailable"
        for shape in record.copper:
            copper = Thick(shape.core, shape.width, shape.filled)
            if any(thick_touch(copper, Thick((point,), 1)) for point in internal):
                return None, "pad copper shortcuts an internal track junction"
    for index, a in enumerate(tracks):
        for b in tracks[index + 1 :]:
            if a.layer != b.layer:
                continue
            if classify_segments(a.start, a.end, b.start, b.end) == SegmentRelation.COLLINEAR_OVERLAP:
                return None, "tracks overlap inside the purported chain"
            crossing = intersection_point(a.start, a.end, b.start, b.end)
            if crossing is not None and crossing not in {
                (point.x, point.y) for point in (a.start, a.end) if point in (b.start, b.end)
            }:
                return None, "tracks intersect inside the purported chain"
    reached = {tracks[0].start}
    while True:
        previous = set(reached)
        for track in tracks:
            if track.start in reached or track.end in reached:
                reached.update((track.start, track.end))
        if reached == previous:
            break
    if reached != set(degree):
        return None, "the net holds disconnected copper"
    return propagation, ""


def lower_topologies(
    rules: RuleSet, *, design: Design | None = None
) -> tuple[tuple[Rule, ...], tuple[Issue, ...]]:
    """Return supported length/skew forms and one informational row for every retained constraint."""
    lowered: list[Rule] = []
    issues: list[Issue] = []

    def retained(name: str, kind: str, reason: str) -> None:
        issues.append(
            Issue(
                "rules.topology-not-lowered",
                "info",
                f"topology {name}: {kind} remains checked by Fenolite; {reason}",
                where=name,
                hint="run fenolite check --stages topology.rules with the user's propagation and loss inputs",
            )
        )

    by_name = {topology.name: topology for topology in rules.topologies}
    for topology in rules.topologies:
        occurrences: Counter[str] = Counter()
        for index, constraint in enumerate(topology.constraints):
            occurrences[constraint.kind] += 1
            propagation, reason = _propagation(topology, rules, design)
            if constraint.kind != "delay":
                retained(
                    topology.name,
                    constraint.kind,
                    "KiCad net-total length/skew cannot express this endpoint constraint",
                )
                continue
            if propagation is None:
                retained(topology.name, constraint.kind, reason)
                continue
            suffix = "" if occurrences[constraint.kind] == 1 else f":{occurrences[constraint.kind]}"
            lowered.append(
                Rule(
                    id=derived_id("rul", "dsl", f"topology:{topology.name}:{index}"),
                    name=f"topology:{topology.name}:delay{suffix}",
                    kind="length",
                    selector_a=Selector("net", topology.edges[0].net),
                    min=None
                    if constraint.min_fs is None
                    else (constraint.min_fs * 1_000_000 + propagation - 1) // propagation,
                    max=None if constraint.max_fs is None else constraint.max_fs * 1_000_000 // propagation,
                    severity=constraint.severity,
                )
            )
    for constraint in rules.protocol_skews:
        members = [by_name[name] for name in constraint.topologies]
        values = [_propagation(member, rules, design)[0] for member in members]
        base = pair_base(members[0].edges[0].net, members[1].edges[0].net)
        if None in values or len(set(values)) != 1 or base is None:
            retained(
                constraint.interface,
                "pair skew",
                "both complete member paths need one propagation, no offsets and KiCad pair net names",
            )
            continue
        propagation = values[0]
        assert propagation is not None
        lowered.append(
            Rule(
                id=derived_id("rul", "dsl", f"protocol:{constraint.interface}:skew"),
                name=f"pair:{constraint.interface}:skew",
                kind="diff_pair_skew",
                selector_a=Selector("diff_pair", base),
                max=constraint.max_fs * 1_000_000 // propagation,
                severity=constraint.severity,
            )
        )
    return tuple(lowered), tuple(issues)


__all__ = ["lower_topologies"]
