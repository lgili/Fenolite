# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Compile confirmed electrical intent into routing-only immutable data (c0366).

Reuse the existing role profile and user requirement schema; introduce no electrical limit.
Reference geometry is accepted only from a current validated saved fill. Zone envelopes are
conservative aggressor obstacles, not a claim about filled copper or a ground reference.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, replace

from fenolite.analysis.boundary import board_boundary
from fenolite.analysis.pour import DEFAULT_GRID_NM, MAX_CELLS, PourCopper, pour_copper
from fenolite.analysis.requirements import Requirements
from fenolite.backends.base import BoardPad
from fenolite.core.ids import content_hash
from fenolite.geometry import Thick
from fenolite.model.canonical import to_data
from fenolite.model.design import Design
from fenolite.model.rules import RoleSet
from fenolite.roles import profile
from fenolite.roles.measure import RoleBoard, high_voltage_nets
from fenolite.routing.octilinear import World
from fenolite.routing.protocol import RoutingJob
from fenolite.routing.search_fields import (
    Copper,
    Fields,
    Ground,
    Influence,
    Provenance,
    Spacing,
    board_fingerprint,
)


@dataclass(frozen=True, slots=True)
class Compiled:
    fields: Fields
    pour: PourCopper


def compile_fields(
    design: Design,
    pads: Sequence[BoardPad],
    roles: RoleSet,
    *,
    requirements: Requirements | None = None,
    grid: int = DEFAULT_GRID_NM,
) -> Compiled:
    """Compile from the current design, never an unbound previously computed pour.

    Return that current pour alongside the fields so the CLI does not compute it twice.
    Saved-fill geometry coverage is not a return-path or impedance certification.
    """
    board = design.board
    if board is None:
        raise ValueError("role search fields require a board")
    layers = tuple(
        layer.name
        for layer in sorted(board.layers, key=lambda layer: layer.ordinal)
        if layer.kind == "copper"
    )
    boundary = board_boundary(board)
    pour = pour_copper(design, pads=pads, boundary=boundary, grid=grid)
    confirmed = replace(roles, nets=tuple(role for role in roles.nets if role.source != "inferred"))
    by_role = {role.net: role for role in confirmed.nets}
    high = set(high_voltage_nets(RoleBoard(design, tuple(pads), confirmed, {})))
    switches = {role.net for role in confirmed.nets if role.kind == "switch_node"}
    grounds = {role.net for role in confirmed.nets if role.kind == "ground"}
    nets = sorted(design.circuit.nets, key=lambda net: net.name)
    spacings: list[Spacing] = []
    influences: list[Influence] = []
    missing: list[tuple[str, str]] = []
    unknowns = [f"unconfirmed-role:{role.net}" for role in roles.nets if role.source == "inferred"]
    for victim in nets:
        role = by_role.get(victim.name)
        limit = profile.resolve(
            "switching_distance_nm",
            confirmed.limits,
            net=victim.name,
            kind=role.kind if role is not None else "signal",
        )
        for aggressor in nets:
            if victim.id == aggressor.id:
                continue
            matching = (
                tuple(row for row in requirements.distances if row.matches(victim, aggressor, design.circuit))
                if requirements
                else ()
            )
            if victim.name in high or aggressor.name in high or matching:
                values = requirements.distance_for(victim, aggressor, design.circuit) if requirements else ()
                distances = [value for value in values if value is not None]
                insulation = (
                    requirements.insulation_for(victim, aggressor, design.circuit) if requirements else None
                )
                if insulation is not None:
                    distances.append(insulation)
                unresolved = bool(requirements and any(requirements.values(row) is None for row in matching))
                if distances:
                    kind = (
                        "high-voltage"
                        if victim.name in high or aggressor.name in high
                        else "declared-distance"
                    )
                    spacings.append(
                        Spacing(victim.name, aggressor.name, max(distances), kind, "requirements")
                    )
                if not distances or unresolved:
                    missing.append((victim.name, f"roles.limit-missing:{victim.name}~{aggressor.name}"))
            if aggressor.name in switches:
                distance = limit.value if limit.value is not None else 0
                influences.append(Influence(victim.name, aggressor.name, distance))
                if role is not None and role.sensitive:
                    spacings.append(
                        Spacing(
                            victim.name,
                            aggressor.name,
                            distance,
                            "switching",
                            limit.origin + (f":{limit.source}" if limit.source else ""),
                        )
                    )
    # World already represents pads, full through barrels and tessellated arcs conservatively.
    world = World(RoutingJob(design, (), layers), tuple(pads), ())
    copper: list[Copper] = []
    for layer in layers:
        for item in world.by_layer.get(layer, ()):
            if item.net is not None:
                copper.append(Copper(item.net, layer, item.shape, item.subject.item_kind))
    aggressors = high | switches | {row.aggressor for row in spacings}
    names = {net.id: net.name for net in nets}
    reference: list[Ground] = []
    seen_ground: set[str] = set()
    for zone in sorted(board.zones, key=lambda z: z.id):
        name = names.get(zone.net_id or "", "")
        if len(zone.outline) >= 3 and name in aggressors:
            for layer in layers:
                if layer in zone.layers or "*.Cu" in zone.layers:
                    copper.append(Copper(name, layer, Thick(zone.outline, 0, True), "zone-envelope"))
                    unknowns.append(f"aggressor-zone-envelope:{name}:{layer}")
        if name not in grounds:
            continue
        seen_ground.add(name)
        for layer in layers:
            if layer not in zone.layers and "*.Cu" not in zone.layers:
                continue
            state = pour.state_of(zone.id, layer)
            fills = tuple(fill for fill in zone.fills if fill.layer == layer)
            if state != "saved_fill" or not boundary.outer:
                reason = "outline-unavailable" if not boundary.outer else state or "missing-fill"
                unknowns.append(f"ground:{name}:{layer}:{reason}")
                continue
            for fill in fills:
                if fill.island or len(fill.polygon) < 3:
                    unknowns.append(f"ground:{name}:{layer}:island-or-empty")
                    continue
                xs, ys = [p.x for p in fill.polygon], [p.y for p in fill.polygon]
                cells = ((max(xs) - min(xs)) // grid + 3) * ((max(ys) - min(ys)) // grid + 3)
                if cells > MAX_CELLS:
                    unknowns.append(f"ground:{name}:{layer}:validation-limit")
                    continue
                reference.append(Ground(name, layer, fill.polygon))
    unknowns += [f"ground:{name}:missing-zone" for name in sorted(grounds - seen_ground)]
    if not grounds:
        unknowns.append("reference:no-confirmed-ground")
    groups = tuple(
        sorted(
            group.name for group in (*roles.loops, *roles.gates, *roles.kelvins) if group.origin != "inferred"
        )
    )
    provenance = Provenance(
        board_fingerprint(design),
        content_hash(to_data(roles)),
        content_hash(
            [to_data(profile.DEFAULTS[key]) for key in sorted(profile.DEFAULTS)],
            to_data(roles.limits),
            to_data(requirements),
        ),
        content_hash(to_data(pour.zones), [to_data(zone.fills) for zone in board.zones]),
    )
    fields = Fields(
        provenance,
        layers,
        tuple(spacings),
        tuple(influences),
        tuple(copper),
        tuple(reference),
        tuple(sorted(set(missing))),
        tuple(sorted(set(unknowns))),
        groups,
        bool(grounds),
    )
    return Compiled(fields, pour)
