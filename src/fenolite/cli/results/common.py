# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Shared wire records; these classes describe JSON and do not build command replies."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, NewType

from fenolite.analysis.report import Measure
from fenolite.checks.copper import CopperRef
from fenolite.core.coords import Point

CanonicalNativeJson = NewType("CanonicalNativeJson", object)
"""Uninterpreted exact canonical-wire delta leaf: null/bool/int/string/recursive arrays.

Only derived-cache unjudged a/b metadata uses this marker. JSON numbers are rational triples;
object mappings become key/value arrays. The generator supplies its closed recursive schema.
"""


@dataclass(frozen=True, kw_only=True)
class ProtocolPlan:
    path: str
    kind: str
    bytes: int
    sha256: str
    overwrite: bool


@dataclass(frozen=True, kw_only=True)
class ProtocolPage:
    path: str
    limit: int
    offset: int
    total: int
    next: str | None


@dataclass(frozen=True, kw_only=True)
class ProtocolIssueSummary:
    code: str
    count: int
    by_severity: dict[str, int] = field(metadata={"description": "counts indexed by severity"})


@dataclass(frozen=True, kw_only=True)
class ProtocolRecovery:
    failed: list[str]
    preserved: list[str]


@dataclass(frozen=True, kw_only=True)
class ProtocolFields:
    """Dispatcher additions, optional because they depend on flags and the write outcome."""

    plan: list[ProtocolPlan] = field(metadata={"optional": True})
    plan_id: str = field(metadata={"optional": True})
    issues_summary: list[ProtocolIssueSummary] = field(metadata={"optional": True})
    recovery: ProtocolRecovery = field(metadata={"optional": True})


@dataclass(frozen=True, kw_only=True)
class ProtocolResult(ProtocolFields):
    page: ProtocolPage = field(metadata={"optional": True})


@dataclass(frozen=True, kw_only=True)
class BlocksProtocolResult(ProtocolFields):
    page: ProtocolPage | str = field(metadata={"optional": True})


@dataclass(frozen=True)
class PinChoice:
    key: str
    kind: str
    option: str
    alternative: int
    pins: dict[str, str] = field(metadata={"description": "role names mapped to chosen device functions"})
    source: str


@dataclass(frozen=True)
class VersionScope:
    version: str
    tool: str
    level: str
    source: str


@dataclass(frozen=True)
class DistanceRow:
    """The CLI omits the measures of analysis kinds that were not requested."""

    net_a: str
    net_b: str
    gaps: list[Measure] = field(metadata={"optional": True})
    clearance: Measure | None = field(metadata={"optional": True})
    creepage: Measure | None = field(metadata={"optional": True})
    insulation: Measure | None = field(metadata={"optional": True})
    sheets: int | None = field(metadata={"optional": True})


@dataclass(frozen=True)
class DrcLimit:
    type: str
    reported: int
    limit: int


@dataclass(frozen=True)
class AcceptedDrc:
    type: str
    items: list[str]
    comment: str
    state: str
    reported: bool


@dataclass(frozen=True)
class WaiverSummary:
    matched: dict[str, int] = field(metadata={"description": "match counts by authored waiver name"})
    unmatched: list[str]
    unjudged: dict[str, str] = field(
        metadata={"optional": True, "description": "unjudged reason by authored waiver name"}
    )
    declared: int = field(metadata={"optional": True})
    expired: list[str] = field(metadata={"optional": True})


@dataclass(frozen=True)
class GateFinding:
    type: str
    severity: str
    description: str
    uuids: list[str]
    items: list[str]


@dataclass(frozen=True)
class GateDropped:
    id: str
    findings: list[GateFinding]


@dataclass(frozen=True)
class GateSummary:
    tool_version: str | None
    runs: int
    refilled: bool
    items: int
    kept: int
    dropped: list[GateDropped]
    findings: list[GateFinding]


@dataclass(frozen=True)
class RoleFinding:
    code: str
    severity: str
    where: str


@dataclass(frozen=True)
class ReturnSpan:
    layer: str
    where: str
    start: tuple[int, int]
    end: tuple[int, int]
    length: int


@dataclass(frozen=True)
class PlacementFinding:
    code: str
    severity: str
    layer: str
    at: Point
    items: tuple[CopperRef, CopperRef]
    gap: int
    clearance: int | None
    source: str
    message: str
    relation: str
    where: str


@dataclass(frozen=True)
class PresetReference:
    file: str
    sha256: str


@dataclass(frozen=True)
class DrawingSheetPage:
    file: str
    paper: str
    width: int
    height: int


@dataclass(frozen=True)
class DrawingSheetSummary:
    source: str
    items: int
    file: str = field(metadata={"optional": True})
    pages: list[DrawingSheetPage] = field(metadata={"optional": True})


@dataclass(frozen=True)
class DrawnSyncSummary:
    file: str
    planned: bool
    wires: int
    junctions: int
    labels: int
    buses: int
    opaque: int


@dataclass(frozen=True)
class AdoptedSummary:
    board: str
    rewritten: dict[str, int] = field(metadata={"description": "rewritten UUID counts by native item kind"})
    paths: int
    unmatched: dict[str, int] = field(metadata={"description": "unmatched source counts by native item kind"})


@dataclass(frozen=True)
class ViaCount:
    netclass: str
    count: int


@dataclass(frozen=True)
class DrcDifference:
    tool_version: str
    before: dict[str, int] = field(metadata={"description": "original DRC counts indexed by violation kind"})
    after: dict[str, int] = field(metadata={"description": "new DRC counts indexed by violation kind"})
    new: list[str]


@dataclass(frozen=True)
class SilkCut:
    owner: str
    footprint: str | None
    side: str
    items: int
    pieces: int
    dropped: int
    by: list[str]


@dataclass(frozen=True)
class SilkClip:
    margin: int
    margin_source: str
    openings: int
    items: int
    pieces: int
    dropped: int
    cuts: list[SilkCut]


@dataclass(frozen=True)
class SilkLibrary:
    changed: list[str]
    command: str


@dataclass(frozen=True)
class SupplierRate:
    per_minute: int
    per_day: int | None


@dataclass(frozen=True)
class SupplierMetadata:
    name: str
    available: bool
    ready: bool
    reason: str
    credential_env_present: bool
    sends_data_offsite: bool
    sends: list[str]
    cache: str
    extra_installed: bool
    title: str = field(metadata={"optional": True})
    terms: list[str] = field(metadata={"optional": True})
    attribution: str = field(metadata={"optional": True})
    max_age_s: int = field(metadata={"optional": True})
    terms_max_age_s: int | None = field(metadata={"optional": True})
    rate: SupplierRate = field(metadata={"optional": True})
    persist: list[str] = field(metadata={"optional": True})
    evidence: str = field(metadata={"optional": True})


@dataclass(frozen=True)
class SupplierProposal:
    mpn: str
    file: str
    attribution: str
    complete: bool
    decoded_by: str | None
    manufacturer: str = field(metadata={"optional": True})
    datasheet: str = field(metadata={"optional": True})
    reported: dict[str, Any] = field(
        metadata={
            "optional": True,
            "description": "Display-only provider data; excluded from persisted identity.",
        }
    )
    offer: dict[str, Any] = field(
        metadata={
            "optional": True,
            "description": "Display-only provider offer data; excluded from stored plans.",
        }
    )


@dataclass(frozen=True)
class MigrationResult(ProtocolResult):
    """Prepared c0218 command result; the model change owns the command and actual migration."""

    from_: str = field(metadata={"name": "from", "optional": True})
    to: str = field(metadata={"optional": True})
    steps: list[str] = field(metadata={"optional": True})


@dataclass(frozen=True)
class ServerSummary:
    url: str
    seconds: float


@dataclass(frozen=True)
class ProbeSummary:
    ref: str
    net: str
    position: tuple[int, int]
    anchor: tuple[int, int]
    track_length: int
    track_width: int


@dataclass(frozen=True)
class UnplacedProbe:
    net: str
    site: tuple[int, int] | None
    blocker: str


@dataclass(frozen=True)
class CoverageCounts:
    eligible: int
    covered: int


@dataclass(frozen=True)
class ProbePlacement:
    side: str
    grid: int
    reach: int
    size: int
    min_pitch: int
    clearance: int
    edge_clearance: int
    nets: list[str]
    before: CoverageCounts
    after: CoverageCounts
    probes: list[ProbeSummary]
    unplaced: list[UnplacedProbe]
    drc: DrcDifference | None


@dataclass(frozen=True)
class OperationFinding:
    code: str
    severity: str
    message: str
    hint: str
    where: str
    stage: str
    evidence: str
    at: None
    box: None


@dataclass(frozen=True)
class FamilyValues:
    min: str
    max: str


@dataclass(frozen=True)
class CatalogEntry:
    lib_id: str
    kind: str
    category: str
    summary: str
    evidence: str
    sources: list[str] | dict[str, list[str]] = field(
        metadata={"description": "source IDs as a list, or indexed by the enumerated family's dimension"}
    )
    id: str = field(metadata={"optional": True})
    version: str = field(metadata={"optional": True})
    licence: str = field(metadata={"optional": True})
    uid: str = field(metadata={"optional": True})
    series: str = field(metadata={"optional": True})
    case: str = field(metadata={"optional": True})
    values: FamilyValues = field(metadata={"optional": True})


@dataclass(frozen=True)
class CatalogPin:
    number: str
    name: str
    etype: str


@dataclass(frozen=True)
class CatalogPad:
    number: str
    size_nm: tuple[int, int]


@dataclass(frozen=True)
class CatalogDefinition:
    graphics: int
    pins: list[CatalogPin] = field(metadata={"optional": True})
    pads: list[CatalogPad] = field(metadata={"optional": True})
    description: str = field(metadata={"optional": True})
