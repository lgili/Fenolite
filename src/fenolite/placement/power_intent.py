# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Pad-level placement objectives from reviewed power circuit intent."""

from collections import defaultdict
from collections.abc import Mapping
from dataclasses import dataclass
from itertools import combinations
from typing import Literal

from fenolite.backends.base import BoardPad
from fenolite.core.coords import Point
from fenolite.geometry.polygon import area2
from fenolite.geometry.predicates import SegmentRelation, classify_segments
from fenolite.model.rules import GateLoop, HotLoop, KelvinPair, RoleSet
from fenolite.placement.topology import PadIdentity

Pair = tuple[PadIdentity, PadIdentity]
PowerKind = Literal["hot_loop", "gate", "kelvin", "bootstrap", "isolation"]


@dataclass(frozen=True, slots=True)
class BootstrapBinding:
    key: str
    supply: Pair
    return_path: Pair
    source: str


@dataclass(frozen=True, slots=True)
class IsolationBinding:
    key: str
    endpoints: Pair
    rule_id: str
    source: str


@dataclass(frozen=True, slots=True)
class PowerObjective:
    key: str
    kind: PowerKind
    source: str
    legs: tuple[Pair, ...] = ()
    loop: tuple[PadIdentity, ...] = ()
    force_pads: tuple[PadIdentity, ...] = ()
    isolation_rule: str | None = None
    unresolved: tuple[str, ...] = ()


def power_objectives(
    roles: RoleSet,
    pads: tuple[BoardPad, ...],
    *,
    bootstrap: tuple[BootstrapBinding, ...] = (),
    isolation: tuple[IsolationBinding, ...] = (),
    isolation_rules: frozenset[str] = frozenset(),
) -> tuple[PowerObjective, ...]:
    """Project named reviewed groups onto unique physical identities without changing topology."""
    by_name: dict[str, set[PadIdentity]] = defaultdict(set)
    by_id: dict[PadIdentity, BoardPad] = {}
    for pad in pads:
        if pad.kind != "np_thru_hole":
            key = PadIdentity(pad.footprint_id, pad.pad_id)
            by_name[f"{pad.ref}-{pad.number}"].add(key)
            by_id[key] = pad

    out: list[PowerObjective] = []
    for group in (*roles.loops, *roles.gates, *roles.kelvins):
        if group.origin == "inferred":
            continue
        # Ordered loop terminals are kept separate from the shunt's force terminals.
        if isinstance(group, HotLoop):
            kind: PowerKind = "hot_loop"
        elif isinstance(group, GateLoop):
            kind = "gate"
        else:
            kind = "kelvin"
        force_names = group.force if isinstance(group, KelvinPair) else ()
        names = (*group.pads, *force_names)
        unresolved = tuple(name for name in names if len(by_name[name]) != 1)
        if unresolved:
            out.append(PowerObjective(group.name, kind, group.origin, unresolved=unresolved))
            continue
        ordered = tuple(next(iter(by_name[name])) for name in group.pads)
        if len(set(ordered)) != len(ordered):
            out.append(PowerObjective(group.name, kind, group.origin, unresolved=("duplicate_pad",)))
            continue
        legs: tuple[Pair, ...] = ()
        if kind == "gate":
            drive: tuple[Pair, ...] = ((ordered[0], ordered[1]),)
            if len(ordered) == 6:
                drive += ((ordered[2], ordered[3]),)
            legs = (*drive, (ordered[-2], ordered[-1]))
        elif kind == "kelvin":
            legs = ((ordered[0], ordered[1]), (ordered[3], ordered[2]))
        force = tuple(next(iter(by_name[name])) for name in force_names)
        out.append(PowerObjective(group.name, kind, group.origin, legs, ordered, force))

    for binding in bootstrap:
        a, b = binding.supply
        c, d = binding.return_path
        legs = (binding.supply, binding.return_path)
        if not all(pad in by_id for pad in (a, b, c, d)):
            reason = ("missing_endpoint",)
        elif (
            len({a, b, c, d}) != 4
            or by_id[a].net_id is None
            or by_id[c].net_id is None
            or by_id[a].net_id == by_id[c].net_id
            or by_id[a].net_id != by_id[b].net_id
            or by_id[c].net_id != by_id[d].net_id
        ):
            reason = ("invalid_bootstrap_binding",)
        else:
            reason = ()
        out.append(
            PowerObjective(
                binding.key,
                "bootstrap",
                binding.source,
                legs if not reason else (),
                (a, b, d, c) if not reason else (),
                unresolved=reason,
            )
        )
    for boundary in isolation:
        first, second = boundary.endpoints
        missing: list[str] = []
        if first == second or first not in by_id or second not in by_id:
            missing.append("invalid_endpoint")
        if boundary.rule_id not in isolation_rules:
            missing.append("missing_isolation_rule")
        out.append(
            PowerObjective(
                boundary.key,
                "isolation",
                boundary.source,
                (boundary.endpoints,) if not missing else (),
                isolation_rule=boundary.rule_id,
                unresolved=tuple(missing),
            )
        )
    return tuple(sorted(out, key=lambda row: (row.kind, row.key)))


def projected_loop_area2(objective: PowerObjective, positions: Mapping[PadIdentity, Point]) -> int | None:
    """Doubled planar pad-polygon area, or unknown for an invalid or incomplete sketch."""
    if objective.unresolved or len(objective.loop) < 3 or any(pad not in positions for pad in objective.loop):
        return None
    ring = tuple(positions[pad] for pad in objective.loop)
    if len(set(ring)) != len(ring):
        return None
    edges = tuple(zip(ring, (*ring[1:], ring[0]), strict=True))
    for i, j in combinations(range(len(edges)), 2):
        relation = classify_segments(*edges[i], *edges[j])
        adjacent = j == i + 1 or (i == 0 and j == len(edges) - 1)
        if not adjacent and relation != SegmentRelation.DISJOINT:
            return None
        if adjacent and relation == SegmentRelation.COLLINEAR_OVERLAP:
            return None
    return abs(area2(ring)) or None
