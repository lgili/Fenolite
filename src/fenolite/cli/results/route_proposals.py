# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Wire records of route candidates, measured facts and persisted-decision replies."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

NativeCheck = Literal["not-run", "candidate-facts", "acceptance-findings"]
NotEvaluatedFact = Literal["closes", "open", "copper_check", "roles", "loop", "drc"]
NotEvaluatedReason = Literal[
    "no-gate", "no-role-loop", "outside-role-reach", "no-kicad-cli", "budget", "external-trial-failed"
]


@dataclass(frozen=True, kw_only=True)
class ProposalEnd:
    kind: str
    name: str
    layers: list[str]
    at: tuple[int, int] = field(metadata={"optional": True})


@dataclass(frozen=True, kw_only=True)
class ProposalTrack:
    kind: Literal["track"]
    layer: str
    width: int
    points: list[tuple[int, int]]


@dataclass(frozen=True, kw_only=True)
class ProposalVia:
    kind: Literal["via"]
    at: tuple[int, int]
    diameter: int
    drill: int
    layers: list[str]


@dataclass(frozen=True, kw_only=True)
class ProposalItems:
    tracks: int
    vias: int


@dataclass(frozen=True, kw_only=True)
class ProposalOpen:
    before: int
    after: int = field(metadata={"optional": True})


@dataclass(frozen=True, kw_only=True)
class ProposalCopperFinding:
    code: str
    layer: str
    items: list[str]
    gap: int


@dataclass(frozen=True, kw_only=True)
class ProposalCopper:
    before: int
    after: int
    new: list[ProposalCopperFinding]


@dataclass(frozen=True, kw_only=True)
class ProposalRoleFinding:
    code: str
    where: str
    severity: str
    measure: int | None


@dataclass(frozen=True, kw_only=True)
class ProposalRoles:
    before: int
    after: int
    new: list[ProposalRoleFinding]
    cleared: list[ProposalRoleFinding]


@dataclass(frozen=True, kw_only=True)
class ProposalLoop:
    group: str
    area: int | None
    ratio_permille: int | None
    bound: int | None


@dataclass(frozen=True, kw_only=True)
class ProposalDrcFinding:
    type: str
    items: list[str]


@dataclass(frozen=True, kw_only=True)
class ProposalDrc:
    new: list[ProposalDrcFinding]
    evidence: str


@dataclass(frozen=True, kw_only=True)
class ProposalNotEvaluated:
    fact: NotEvaluatedFact
    why: NotEvaluatedReason


@dataclass(frozen=True, kw_only=True)
class ProposalFacts:
    vias: int = field(metadata={"optional": True})
    length: int = field(metadata={"optional": True})
    layers: list[str] = field(metadata={"optional": True})
    bends: int = field(metadata={"optional": True})
    conflicts: list[str] = field(metadata={"optional": True})
    fill: str = field(metadata={"optional": True})
    current: str = field(metadata={"optional": True})
    relaxed: list[str] = field(metadata={"optional": True})
    closes: list[str] = field(metadata={"optional": True})
    open: ProposalOpen = field(metadata={"optional": True})
    copper_check: ProposalCopper = field(metadata={"optional": True})
    roles: ProposalRoles = field(metadata={"optional": True})
    loop: ProposalLoop = field(metadata={"optional": True})
    drc: ProposalDrc = field(metadata={"optional": True})
    not_evaluated: list[ProposalNotEvaluated] = field(metadata={"optional": True})


@dataclass(frozen=True, kw_only=True)
class ProposalCandidate:
    id: str
    source: str
    relaxed: list[str]
    items: ProposalItems
    geometry: list[ProposalTrack | ProposalVia]
    facts: ProposalFacts
    rejected: bool


@dataclass(frozen=True, kw_only=True)
class ProposalAlternative:
    kind: str
    text: str
    command: str
    region: str
    then: str = field(metadata={"optional": True})


@dataclass(frozen=True, kw_only=True)
class Proposal:
    id: str
    subject: str
    kind: str
    net: str
    ends: list[ProposalEnd]
    region: str
    candidates: list[ProposalCandidate]
    reason: str | None
    alternatives: list[ProposalAlternative]


@dataclass(frozen=True, kw_only=True)
class ProposalRejected:
    id: str
    subject: str
    reason: str


@dataclass(frozen=True, kw_only=True)
class ProposalLocked:
    candidate: str
    subject: str
    present: bool


@dataclass(frozen=True, kw_only=True)
class ProposalAccepted:
    candidate: str
    subject: str
    facts: ProposalFacts


@dataclass(frozen=True, kw_only=True)
class ProposalStale:
    candidate: str
    subject: str
    why: str
