# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Reviewed pad-level placement relationships and their precedence."""

from collections import defaultdict
from dataclasses import dataclass, replace
from typing import Literal

from fenolite.placement.topology import PadIdentity

Origin = Literal["suggested", "confirmed", "declared"]
_PRECEDENCE: dict[Origin, int] = {"suggested": 0, "confirmed": 1, "declared": 2}


@dataclass(frozen=True, slots=True)
class PlacementIntent:
    key: str
    kind: str
    endpoints: tuple[PadIdentity, ...]
    origin: Origin
    source: str
    rule_version: str
    rationale: str
    required: bool = False
    max_distance_nm: int | None = None

    def __post_init__(self) -> None:
        if not all((self.key, self.kind, self.source, self.rule_version, self.rationale)):
            raise ValueError("placement intent needs identity, source, rule version and rationale")
        if len(self.endpoints) < 2 or len(set(self.endpoints)) != len(self.endpoints):
            raise ValueError("placement intent needs distinct physical endpoints")
        if self.origin == "suggested" and (self.required or self.max_distance_nm is not None):
            raise ValueError("suggested intent cannot set requirements or distance limits")
        if self.max_distance_nm is not None and (
            type(self.max_distance_nm) is not int or self.max_distance_nm < 0
        ):
            raise ValueError("maximum distance must be nonnegative integer nm")


def probe_intent_legs(intent: PlacementIntent) -> tuple[PlacementIntent, ...]:
    """Expand a required trace probe into its exact drive and return connections."""
    if not intent.required or not intent.max_distance_nm:
        return ()
    if intent.kind == "escape" and len(intent.endpoints) == 2:
        return (intent,)
    if intent.kind == "gate-loop" and len(intent.endpoints) == 4:
        return (
            replace(intent, kind="escape", key=intent.key + ":drive", endpoints=intent.endpoints[:2]),
            replace(intent, kind="escape", key=intent.key + ":return", endpoints=intent.endpoints[2:]),
        )
    return ()


@dataclass(frozen=True, slots=True)
class ResolvedIntent:
    key: str
    effective: PlacementIntent | None
    alternatives: tuple[PlacementIntent, ...]
    problem: Literal["conflict", "missing_endpoint"] | None = None


def resolve_intents(
    rows: tuple[PlacementIntent, ...], *, available_pads: frozenset[PadIdentity]
) -> tuple[ResolvedIntent, ...]:
    """Retain competing evidence and use only valid reviewed relationships."""
    groups: dict[str, list[PlacementIntent]] = defaultdict(list)
    for row in rows:
        groups[row.key].append(row)
    result: list[ResolvedIntent] = []
    for key, group in sorted(groups.items()):
        ordered = tuple(
            sorted(
                set(group),
                key=lambda r: (
                    -_PRECEDENCE[r.origin],
                    r.kind,
                    r.endpoints,
                    r.required,
                    -1 if r.max_distance_nm is None else r.max_distance_nm,
                    r.source,
                    r.rule_version,
                    r.rationale,
                ),
            )
        )
        first = ordered[0]
        if first.origin == "suggested":
            result.append(ResolvedIntent(key, None, ordered))
            continue
        peers = {
            (row.kind, row.endpoints, row.required, row.max_distance_nm)
            for row in ordered
            if row.origin == first.origin
        }
        if len(peers) != 1:
            result.append(ResolvedIntent(key, None, ordered, "conflict"))
        elif not available_pads.issuperset(first.endpoints):
            result.append(ResolvedIntent(key, None, ordered, "missing_endpoint"))
        else:
            result.append(ResolvedIntent(key, first, ordered))
    return tuple(result)
