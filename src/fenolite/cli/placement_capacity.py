# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Estimate occupied routing channels from a projected candidate and its net classes."""

from collections import defaultdict
from dataclasses import dataclass
from typing import Literal

from fenolite.backends.base import BoardPad, DesignRules
from fenolite.backends.kicad.layers import plane_layers
from fenolite.checks.clearance import ClearanceResolver
from fenolite.core.coords import Point
from fenolite.geometry import BBox
from fenolite.model.board import rule_areas
from fenolite.model.design import Design
from fenolite.model.pairs import pair_nets
from fenolite.placement.routability import ChannelCut, ChannelDemand, estimate_channels
from fenolite.routing.layers import allowed_layers, routing_layers
from fenolite.routing.pairs import job_pairs


@dataclass(frozen=True, slots=True)
class Capacity:
    overflow_nm: int = 0
    unknown: tuple[str, ...] = ()
    by_layer: tuple[tuple[str, int], ...] = ()


def placement_capacity(
    design: Design,
    rules: DesignRules,
    pads: tuple[BoardPad, ...],
    outline: tuple[tuple[Point, ...], ...],
    movable: frozenset[str],
) -> Capacity:
    """Estimate lane packing across fixed cuts of a rectangular board.

    Each affected net claims one lane per crossed cut on its uniquely shared layer.
    Paired nets claim an indivisible lane. Layer ambiguity and absent dimensions stay
    unknown. This bounded estimate cannot prove a continuous routing path.
    """
    board = design.board
    by_net: dict[str, list[BoardPad]] = defaultdict(list)
    affected = {pad.net for pad in pads if pad.footprint_id in movable and pad.net is not None}
    for pad in pads:
        if pad.net is not None and pad.copper:
            by_net[pad.net].append(pad)
    affected = {name for name in affected if len(by_net[name]) > 1}
    if not affected:
        return Capacity()
    if board is None or not outline or not outline[0]:
        return Capacity(unknown=("capacity:outline",))
    bounds = BBox.of_points(outline[0])
    corners = {Point(x, y) for x in (bounds.x0, bounds.x1) for y in (bounds.y0, bounds.y1)}
    if len(corners) != 4 or set(outline[0]) != corners:
        return Capacity(unknown=("capacity:outline",))
    layers = tuple(
        layer.name for layer in sorted(board.layers, key=lambda item: item.ordinal) if layer.kind == "copper"
    )
    routable = routing_layers(layers, plane_layers(design))
    if not routable:
        return Capacity(unknown=("capacity:layers",))
    if (
        board.arcs
        or board.zones
        or board.holes
        or board.verbatim
        or rule_areas(board)
        or rules.unread
        or rules.left_out
        or rules.opaque_clearance_rules
        or any(item.layer in routable for item in (*board.graphics, *board.texts))
        or any(item.layer in routable for fp in board.footprints for item in (*fp.graphics, *fp.texts))
        or (
            design.rules is not None
            and any(rule.kind == "track_width" and rule.severity != "ignore" for rule in design.rules.rules)
        )
    ):
        return Capacity(unknown=("capacity:unmodeled-geometry-or-rules",))
    resolver = ClearanceResolver(
        design,
        min_clearance=rules.min_clearance,
        min_edge_clearance=rules.min_edge_clearance,
        min_hole_clearance=rules.min_hole_clearance,
    )
    edge = resolver.max_edge
    margin = max(resolver.max_value, resolver.max_hole)
    if min(bounds.width, bounds.height) <= 2 * edge:
        return Capacity(unknown=("capacity:edge-clearance",))
    inner = bounds.inflate(-edge)
    axes: tuple[tuple[Literal["x", "y"], int, int, tuple[int, int]], ...] = (
        ("x", inner.x0, inner.x1, (inner.y0, inner.y1)),
        ("y", inner.y0, inner.y1, (inner.x0, inner.x1)),
    )
    cuts = tuple(
        ChannelCut(f"{layer}:{direction}:{at}", layer, direction, at, span)
        for layer in routable
        for direction, lo, hi, span in axes
        for at in sorted({lo + (hi - lo) * i // 4 for i in (1, 2, 3)})
        if lo < at < hi
    )
    if not cuts:
        return Capacity(unknown=("capacity:cuts",))
    blocked: dict[str, list[BBox]] = {
        layer: [BBox.of_points(ring).inflate(margin) for ring in outline[1:] if ring] for layer in routable
    }
    for pad in pads:
        for shape in pad.copper:
            if shape.layer in blocked:
                blocked[shape.layer].append(
                    BBox.of_points(shape.core).inflate((shape.width + 1) // 2 + margin)
                )
        if pad.hole and pad.drill:
            hole = BBox.of_points(pad.hole).inflate((pad.drill + 1) // 2 + margin)
            for layer in routable:
                blocked[layer].append(hole)
    for track in board.tracks:
        if track.layer in blocked:
            blocked[track.layer].append(
                BBox.of_points((track.start, track.end)).inflate((track.width + 1) // 2 + margin)
            )
    for via in board.vias:
        # Reserve its full diameter through all modeled layers.
        box = BBox.of_points((via.position,)).inflate((via.diameter + 1) // 2 + margin)
        for layer in routable:
            blocked[layer].append(box)

    nets = {net.name: net for net in design.circuit.nets}
    classes = {cls.id: cls for cls in design.circuit.netclasses}
    default = next((cls for cls in classes.values() if cls.name.casefold() == "default"), None)
    pairs, singles, _ = job_pairs(design, tuple(sorted(nets)))
    by_id = {net.id: net.name for net in nets.values()}
    declared_pairs = {
        by_id[net]
        for interface in design.circuit.interfaces
        for net in pair_nets(interface) or ()
        if net in by_id
    }
    represented: set[str] = set()
    missing: set[str] = set()
    demands: list[ChannelDemand] = []

    def charge(names: tuple[str, ...], width: int | None) -> None:
        label = ("pair:" if len(names) > 1 else "net:") + "/".join(names)
        represented.update(names)
        common = set(routable)
        gaps: list[int] = []
        for name in names:
            net = nets[name]
            common.intersection_update(allowed_layers(design, net, routable))
            for pad in by_net[name]:
                common.intersection_update(shape.layer for shape in pad.copper)
            cls = classes.get(net.netclass_id or "", default)
            clearance = (
                cls.clearance if cls is not None and cls.clearance is not None else rules.min_clearance
            )
            if clearance is not None:
                gaps.append(max(clearance, rules.min_clearance or 0))
        if len(common) != 1 or len(gaps) != len(names) or not width:
            missing.add("capacity:" + label)
            return
        layer = next(iter(common))
        boxes = [BBox.of_points(pad.position for pad in by_net[name]) for name in names if by_net[name]]
        crossed = tuple(
            cut.key
            for cut in cuts
            if cut.layer == layer
            and any(
                (box.x0 < cut.at < box.x1 if cut.direction == "x" else box.y0 < cut.at < box.y1)
                for box in boxes
            )
        )
        if crossed:
            demands.append(ChannelDemand(label, crossed, width, max(margin, *gaps)))

    for pair in pairs:
        names = (pair.positive, pair.negative)
        if affected.intersection(names):
            if all(len(by_net[name]) > 1 for name in names):
                charge(names, 2 * pair.width + pair.gap)
    for name in singles:
        if name in affected and name not in declared_pairs:
            net = nets[name]
            cls = classes.get(net.netclass_id or "", default)
            charge((name,), cls.track_width if cls is not None else None)
    missing.update("capacity:net:" + name for name in affected - represented)
    measures = estimate_channels(
        cuts,
        {layer: tuple(boxes) for layer, boxes in blocked.items()},
        tuple(demands),
        known_layers=frozenset(routable),
    )
    by_key = {cut.key: cut.layer for cut in cuts}
    totals = {layer: 0 for layer in routable}
    for row in measures:
        totals[by_key[row.key]] += row.overflow_nm or 0
    return Capacity(sum(totals.values()), tuple(sorted(missing)), tuple(sorted(totals.items())))
