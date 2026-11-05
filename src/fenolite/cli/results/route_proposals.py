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
class ProposalFieldProvenance:
    board: str
    roles: str
    profile: str
    fill: str


@dataclass(frozen=True, kw_only=True)
class ProposalRoleLimit:
    victim: str
    aggressor: str
    distance_nm: int
    kind: str
    origin: str


@dataclass(frozen=True, kw_only=True)
class ProposalRolePreference:
    victim: str
    aggressor: str
    within_nm: int


@dataclass(frozen=True, kw_only=True)
class ProposalRoleFields:
    """c0366: the role search fields in force (``result.role_fields``)."""

    fingerprint: str
    provenance: ProposalFieldProvenance
    limits: list[ProposalRoleLimit]
    preferences: list[ProposalRolePreference]
    unknowns: list[str]
    missing_limits: list[list[str]]


@dataclass(frozen=True, kw_only=True)
class ProposalCandidateRoleFields(ProposalRoleFields):
    """c0366: the fields after a candidate and its conservative reference and exposure bounds."""

    input_fingerprint: str
    input_provenance: ProposalFieldProvenance
    confirmed_reference_length_lower_bound_nm: int
    unconfirmed_reference_length_nm: int
    switching_exposure_upper_bound_nm: int


@dataclass(frozen=True, kw_only=True)
class ProposalTool:
    """c0368: the identity of the external router that made a candidate."""

    router: str
    version: str
    inputs: str
    job: str
    deterministic: bool


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
    role_fields: ProposalCandidateRoleFields = field(metadata={"optional": True})


@dataclass(frozen=True, kw_only=True)
class ProposalCandidate:
    id: str
    source: str
    relaxed: list[str]
    items: ProposalItems
    geometry: list[ProposalTrack | ProposalVia]
    facts: ProposalFacts
    rejected: bool
    bundle: str = field(metadata={"optional": True})
    tool: ProposalTool = field(metadata={"optional": True})


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
    source: str = field(metadata={"optional": True})
    tool: ProposalTool = field(metadata={"optional": True})


@dataclass(frozen=True, kw_only=True)
class ProposalStale:
    candidate: str
    subject: str
    why: str
    bundle: str = field(metadata={"optional": True})


@dataclass(frozen=True, kw_only=True)
class ProposalBundle:
    """c0367: one negotiated atomic unit; member geometry stays in the candidate rows."""

    id: str
    fingerprint: str
    members: list[str]
    subjects: list[str]


@dataclass(frozen=True, kw_only=True)
class ProposalControls:
    """c0369: the regeneration controls a reviewed viewer action repeats."""

    schema: Literal["fenolite.proposal_controls.v0"]
    router_options: list[str]
    external_routers: list[str]
    nets: list[str]
    kinds: list[str]
    groups: list[str]
    candidate_limit: int | None
    requirements: str | None
    timeout: float | None
    gate: str | None
    portable: bool


@dataclass(frozen=True, kw_only=True)
class ProposalExternalRefusal:
    subject: str
    reason: str
    router: str
    details: list[str]


@dataclass(frozen=True, kw_only=True)
class ProposalExternalNotAttempted:
    subject: str
    router: str


@dataclass(frozen=True, kw_only=True)
class ProposalExternal:
    """c0368: the external routers asked for, their refusals and the subjects they did not attempt."""

    requested: list[str]
    refusals: list[ProposalExternalRefusal]
    not_attempted: list[ProposalExternalNotAttempted]


@dataclass(frozen=True, kw_only=True)
class ProposalCompletionSubjects:
    proposed: list[str]
    unknown: list[str]
    no_candidate: list[str] = field(metadata={"name": "no-candidate"})
    rejected: list[str]
    not_attempted: list[str] = field(metadata={"name": "not-attempted"})


@dataclass(frozen=True, kw_only=True)
class ProposalCompletion:
    """c0370: the physical open count and every subject's state; never a completion claim."""

    state: Literal["open", "unchecked"]
    open: int
    fill: Literal["saved", "simulated"]
    subjects: ProposalCompletionSubjects
    checks: Literal["not-run"]
    complete: bool
