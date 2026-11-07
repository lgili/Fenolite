# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Wire records for checks results; producers retain their existing payloads."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

from fenolite.checks import readiness as readiness_rows
from fenolite.cli.results import common as wire
from fenolite.cli.results.common import (
    ProtocolResult,
)
from fenolite.core.evidence import Evidence
from fenolite.importer import schema as import_rows


@dataclass(frozen=True, kw_only=True)
class CheckMatrixReceipt:
    devices_sha256: str
    fenolite: str
    model_sha256: str
    stages: list[str]


@dataclass(frozen=True, kw_only=True)
class CheckMatrixRowsItem:
    check: str
    decidable: str
    digest: str
    evidence: str
    id: str
    limit: str
    origin: None | str
    source: str
    status: str
    value: str
    waiver: None | str


@dataclass(frozen=True, kw_only=True)
class CheckMatrix:
    receipt: CheckMatrixReceipt
    rows: list[CheckMatrixRowsItem]


@dataclass(frozen=True, kw_only=True)
class CheckProjectDocumentsItem:
    kind: str
    name: str
    role: str


@dataclass(frozen=True, kw_only=True)
class CheckProjectSkippedItem:
    name: str
    reason: str


@dataclass(frozen=True, kw_only=True)
class CheckProject:
    backend: str = field(metadata={"optional": True})
    board: None | str
    built: bool
    documents: list[CheckProjectDocumentsItem] = field(metadata={"optional": True})
    files: list[str]
    project: None | str = field(metadata={"optional": True})
    skipped: list[CheckProjectSkippedItem]


@dataclass(frozen=True, kw_only=True)
class CheckRulesItemGoverning:
    id: str
    name: str
    priority: int
    rank: int


@dataclass(frozen=True, kw_only=True)
class CheckRulesItemOverridesItem:
    id: str
    name: str
    priority: int
    rank: int


@dataclass(frozen=True, kw_only=True)
class CheckRulesItem:
    governing: CheckRulesItemGoverning
    kind: str
    overrides: list[CheckRulesItemOverridesItem]
    rank: int
    subject: str


@dataclass(frozen=True, kw_only=True)
class CheckStagesItemSummaryAfter:
    unconnected: int
    violations: int


@dataclass(frozen=True, kw_only=True)
class CheckStagesItemSummaryBefore:
    unconnected: int
    violations: int


@dataclass(frozen=True, kw_only=True)
class CheckStagesItemSummaryClearanceCells:
    judged: int
    unjudged: int


@dataclass(frozen=True, kw_only=True)
class CheckStagesItemSummaryCompared:
    pcb: list[str]
    schematic: list[str] = field(metadata={"optional": True})


@dataclass(frozen=True, kw_only=True)
class CheckStagesItemSummaryDeferred:
    route: int = field(metadata={"optional": True})


@dataclass(frozen=True, kw_only=True)
class CheckStagesItemSummaryEdges:
    judged: int
    max: int
    rings: list[str]
    unset_items: int


@dataclass(frozen=True, kw_only=True)
class CheckStagesItemSummaryExclusions:
    live: int
    stale: int
    stored: int
    unjudged: int


@dataclass(frozen=True, kw_only=True)
class CheckStagesItemSummaryHalves:
    contracts: str
    rails: str


@dataclass(frozen=True, kw_only=True)
class CheckStagesItemSummaryItems:
    arc: int = field(metadata={"optional": True})
    fill: int = field(metadata={"optional": True})
    pad: int
    track: int = field(metadata={"optional": True})
    via: int = field(metadata={"optional": True})


@dataclass(frozen=True, kw_only=True)
class CheckStagesItemSummaryMeasuresCongestionBusiestItem:
    tracks: int
    x: int
    y: int


@dataclass(frozen=True, kw_only=True)
class CheckStagesItemSummaryMeasuresCongestion:
    busiest: list[CheckStagesItemSummaryMeasuresCongestionBusiestItem]
    cell: int
    layers_needed: None | dict[str, int] = field(
        metadata={"description": "Keys are supplied by named items, rather than fixed record fields."}
    )
    pitch: int | None
    tracks_per_layer: int | None


@dataclass(frozen=True, kw_only=True)
class CheckStagesItemSummaryMeasuresLeftOut:
    off_board: int
    one_pad_nets: int
    zone_nets: int


@dataclass(frozen=True, kw_only=True)
class CheckStagesItemSummaryMeasuresLongestItem:
    hpwl: int
    net: str
    pads: int
    ratsnest: int


@dataclass(frozen=True, kw_only=True)
class CheckStagesItemSummaryMeasures:
    congestion: CheckStagesItemSummaryMeasuresCongestion
    hpwl: int
    left_out: CheckStagesItemSummaryMeasuresLeftOut
    longest: list[CheckStagesItemSummaryMeasuresLongestItem]
    nets: int
    ratsnest: int


@dataclass(frozen=True, kw_only=True)
class CheckStagesItemSummaryModel:
    components: int
    nets: int


@dataclass(frozen=True, kw_only=True)
class CheckStagesItemSummaryPairsItem:
    a: str
    b: str
    common: int
    differences: int
    only_a: int
    only_b: int


@dataclass(frozen=True, kw_only=True)
class CheckStagesItemSummaryPcb:
    components: int
    nets: int


@dataclass(frozen=True, kw_only=True)
class CheckStagesItemSummaryRequirementsItemCornersItem:
    corner: str
    status: str
    text: str


@dataclass(frozen=True, kw_only=True)
class CheckStagesItemSummaryRequirementsItemLimitRangeHigh:
    e: int
    m: int


@dataclass(frozen=True, kw_only=True)
class CheckStagesItemSummaryRequirementsItemLimitRangeLow:
    e: int
    m: int


@dataclass(frozen=True, kw_only=True)
class CheckStagesItemSummaryRequirementsItemLimitRange:
    high: CheckStagesItemSummaryRequirementsItemLimitRangeHigh = field(metadata={"optional": True})
    low: CheckStagesItemSummaryRequirementsItemLimitRangeLow = field(metadata={"optional": True})
    unit: str


@dataclass(frozen=True, kw_only=True)
class CheckStagesItemSummaryRequirementsItemLimit:
    basis: str
    evidence: str
    kind: str
    range: None | CheckStagesItemSummaryRequirementsItemLimitRange
    source: str
    text: str


@dataclass(frozen=True, kw_only=True)
class CheckStagesItemSummaryRequirementsItemValueOrigin:
    kind: str


@dataclass(frozen=True, kw_only=True)
class CheckStagesItemSummaryRequirementsItemValueRangeHigh:
    e: int
    m: int


@dataclass(frozen=True, kw_only=True)
class CheckStagesItemSummaryRequirementsItemValueRangeLow:
    e: int
    m: int


@dataclass(frozen=True, kw_only=True)
class CheckStagesItemSummaryRequirementsItemValueRange:
    high: CheckStagesItemSummaryRequirementsItemValueRangeHigh
    low: CheckStagesItemSummaryRequirementsItemValueRangeLow = field(metadata={"optional": True})
    unit: str


@dataclass(frozen=True, kw_only=True)
class CheckStagesItemSummaryRequirementsItemValue:
    basis: str
    origin: CheckStagesItemSummaryRequirementsItemValueOrigin = field(metadata={"optional": True})
    range: CheckStagesItemSummaryRequirementsItemValueRange
    source: str
    text: str


@dataclass(frozen=True, kw_only=True)
class CheckStagesItemSummaryRequirementsItem:
    check: str
    corners: list[CheckStagesItemSummaryRequirementsItemCornersItem]
    decidable: str
    digest: str
    entities: list[str]
    id: str
    limit: CheckStagesItemSummaryRequirementsItemLimit
    missing: str
    quantity: str
    severity: None | str
    status: str
    subject: str
    unit: str
    value: None | CheckStagesItemSummaryRequirementsItemValue
    waiver: None | str


@dataclass(frozen=True, kw_only=True)
class CheckStagesItemSummaryRoles:
    declared: int
    inferred: int


@dataclass(frozen=True, kw_only=True)
class CheckStagesItemSummaryRulesHeight:
    failed: int
    judged: int
    unknown: int


@dataclass(frozen=True, kw_only=True)
class CheckStagesItemSummaryRulesNear:
    failed: int
    judged: int
    skipped: int


@dataclass(frozen=True, kw_only=True)
class CheckStagesItemSummaryRules:
    height: CheckStagesItemSummaryRulesHeight = field(metadata={"optional": True})
    length: int = field(metadata={"optional": True})
    min_clearance: int | None = field(metadata={"optional": True})
    near: CheckStagesItemSummaryRulesNear = field(metadata={"optional": True})
    opaque_clearance_rules: int = field(metadata={"optional": True})
    skew: int = field(metadata={"optional": True})
    unread: list[str] = field(metadata={"optional": True})


@dataclass(frozen=True, kw_only=True)
class CheckStagesItemSummaryRuns:
    original: int
    redump: int


@dataclass(frozen=True, kw_only=True)
class CheckStagesItemSummarySchematic:
    components: int
    nets: int


@dataclass(frozen=True, kw_only=True)
class CheckStagesItemSummaryViewsItem:
    bytes: int
    name: str
    sha256: str


@dataclass(frozen=True, kw_only=True)
class CheckStagesItemSummary:
    accepted: list[wire.AcceptedDrc] = field(metadata={"optional": True})
    after: CheckStagesItemSummaryAfter = field(metadata={"optional": True})
    analyses: list[str] = field(metadata={"optional": True})
    approximated: int = field(metadata={"optional": True})
    arc_tol: int = field(metadata={"optional": True})
    before: CheckStagesItemSummaryBefore = field(metadata={"optional": True})
    by_severity: dict[str, int] = field(
        metadata={
            "optional": True,
            "description": "Keys are supplied by named items, rather than fixed record fields.",
        }
    )
    by_type: dict[str, int] = field(
        metadata={
            "optional": True,
            "description": "Keys are supplied by named items, rather than fixed record fields.",
        }
    )
    bytes_equal: int = field(metadata={"optional": True})
    canary: str = field(metadata={"optional": True})
    canary_reason: str = field(metadata={"optional": True})
    canary_removed: int = field(metadata={"optional": True})
    clearance: int = field(metadata={"optional": True})
    clearance_cells: CheckStagesItemSummaryClearanceCells = field(metadata={"optional": True})
    codes: dict[str, int] = field(
        metadata={
            "optional": True,
            "description": "Keys are supplied by named items, rather than fixed record fields.",
        }
    )
    compared: bool | CheckStagesItemSummaryCompared = field(metadata={"optional": True})
    components: int = field(metadata={"optional": True})
    connections_missing: int = field(metadata={"optional": True})
    corners: int = field(metadata={"optional": True})
    current: int = field(metadata={"optional": True})
    deferred: CheckStagesItemSummaryDeferred = field(metadata={"optional": True})
    differences: int = field(metadata={"optional": True})
    documents: int = field(metadata={"optional": True})
    edge_clearance: int = field(metadata={"optional": True})
    edges: CheckStagesItemSummaryEdges = field(metadata={"optional": True})
    excluded: int = field(metadata={"optional": True})
    exclusions: CheckStagesItemSummaryExclusions = field(metadata={"optional": True})
    failed: int = field(metadata={"optional": True})
    floating_pin: int = field(metadata={"optional": True, "name": "floating-pin"})
    halves: CheckStagesItemSummaryHalves = field(metadata={"optional": True})
    holds: bool = field(metadata={"optional": True})
    hole_clearance: int = field(metadata={"optional": True})
    hole_clearance_judged: int = field(metadata={"optional": True})
    hole_in_cutout: int = field(metadata={"optional": True})
    hole_overlap: int = field(metadata={"optional": True})
    holes: int = field(metadata={"optional": True})
    ignored_checks: list[str] = field(metadata={"optional": True})
    items: CheckStagesItemSummaryItems = field(metadata={"optional": True})
    judged: bool | int = field(metadata={"optional": True})
    keepouts: int = field(metadata={"optional": True})
    layers: list[str] = field(metadata={"optional": True})
    level: str = field(metadata={"optional": True})
    limits: list[wire.DrcLimit] | None = field(metadata={"optional": True})
    major: int | None = field(metadata={"optional": True})
    max_clearance: int = field(metadata={"optional": True})
    measures: int | CheckStagesItemSummaryMeasures = field(metadata={"optional": True})
    min_pins: int = field(metadata={"optional": True})
    model: CheckStagesItemSummaryModel = field(metadata={"optional": True})
    model_equal: bool = field(metadata={"optional": True})
    net_tie_pairs: int = field(metadata={"optional": True})
    netlist: str = field(metadata={"optional": True})
    nets: int = field(metadata={"optional": True})
    nets_split: int = field(metadata={"optional": True})
    normalised: bool = field(metadata={"optional": True})
    opaque_count: int = field(metadata={"optional": True})
    opaque_equal: bool = field(metadata={"optional": True})
    open: int = field(metadata={"optional": True})
    output_conflict: int = field(metadata={"optional": True, "name": "output-conflict"})
    pairs: list[CheckStagesItemSummaryPairsItem] | int = field(metadata={"optional": True})
    parity: int = field(metadata={"optional": True})
    parity_duplicate_footprints: int = field(
        metadata={"optional": True, "name": "parity.duplicate-footprints"}
    )
    parity_extra_footprint: int = field(metadata={"optional": True, "name": "parity.extra-footprint"})
    parity_footprint_mismatch: int = field(metadata={"optional": True, "name": "parity.footprint-mismatch"})
    parity_missing_footprint: int = field(metadata={"optional": True, "name": "parity.missing-footprint"})
    parity_net_conflict: int = field(metadata={"optional": True, "name": "parity.net-conflict"})
    parity_pad_without_pin: int = field(metadata={"optional": True, "name": "parity.pad-without-pin"})
    parity_pin_without_pad: int = field(metadata={"optional": True, "name": "parity.pin-without-pad"})
    parity_judged: bool = field(metadata={"optional": True})
    pcb: CheckStagesItemSummaryPcb = field(metadata={"optional": True})
    pins: int = field(metadata={"optional": True})
    power_undriven: int = field(metadata={"optional": True, "name": "power-undriven"})
    rails: int = field(metadata={"optional": True})
    records: int = field(metadata={"optional": True})
    refs_one_side: int = field(metadata={"optional": True})
    requirements: list[CheckStagesItemSummaryRequirementsItem] = field(metadata={"optional": True})
    roles: CheckStagesItemSummaryRoles = field(metadata={"optional": True})
    rule_areas: int = field(metadata={"optional": True})
    rules: CheckStagesItemSummaryRules = field(metadata={"optional": True})
    runs: CheckStagesItemSummaryRuns = field(metadata={"optional": True})
    schematic: CheckStagesItemSummarySchematic = field(metadata={"optional": True})
    sheets: int = field(metadata={"optional": True})
    shorts: int = field(metadata={"optional": True})
    stackup: str | None = field(metadata={"optional": True})
    stale: int = field(metadata={"optional": True})
    streams: int = field(metadata={"optional": True})
    tolerance: int = field(metadata={"optional": True})
    tool_version: str = field(metadata={"optional": True})
    tool_writes: list[str] = field(metadata={"optional": True})
    tree_equal: bool = field(metadata={"optional": True})
    types: dict[str, str] = field(
        metadata={
            "optional": True,
            "description": "Keys are supplied by named items, rather than fixed record fields.",
        }
    )
    unconnected: int = field(metadata={"optional": True})
    unfilled: int = field(metadata={"optional": True})
    unjudged: dict[str, int] = field(
        metadata={
            "optional": True,
            "description": "Keys are supplied by named items, rather than fixed record fields.",
        }
    )
    unnumbered: int = field(metadata={"optional": True})
    unpoured: int = field(metadata={"optional": True})
    unset_pairs: int = field(metadata={"optional": True})
    unstable: int = field(metadata={"optional": True})
    unsupported: dict[str, int] = field(metadata={"optional": True})
    views: list[CheckStagesItemSummaryViewsItem] = field(metadata={"optional": True})
    violations: int = field(metadata={"optional": True})
    violations_judged: bool = field(metadata={"optional": True})
    waivers: wire.WaiverSummary = field(metadata={"optional": True})
    zone_overlaps: int = field(metadata={"optional": True})
    zones: int = field(metadata={"optional": True})
    zones_unjudged: int = field(metadata={"optional": True})


@dataclass(frozen=True, kw_only=True)
class CheckStagesItem:
    evidence: Evidence
    name: str
    reason: str
    status: str
    summary: CheckStagesItemSummary


@dataclass(frozen=True, kw_only=True)
class CheckSubjectsItemItemsItem:
    id: str
    kind: str
    name: str


@dataclass(frozen=True, kw_only=True)
class CheckSubjectsItem:
    issue: int
    items: list[CheckSubjectsItemItemsItem]


@dataclass(frozen=True, kw_only=True)
class CheckResult(ProtocolResult):
    matrix: CheckMatrix = field(metadata={"optional": True})
    project: CheckProject = field(metadata={"optional": True})
    rules: list[CheckRulesItem] = field(metadata={"optional": True})
    stages: list[CheckStagesItem] = field(metadata={"optional": True})
    subjects: list[CheckSubjectsItem] = field(metadata={"optional": True})
    waivers: wire.WaiverSummary = field(metadata={"optional": True})


@dataclass(frozen=True, kw_only=True)
class ReadyChecksItemSummaryExclusions:
    live: int
    stale: int
    stored: int
    unjudged: int


@dataclass(frozen=True, kw_only=True)
class ReadyChecksItemSummary:
    accepted: list[wire.AcceptedDrc] = field(metadata={"optional": True})
    by_severity: dict[str, int] = field(
        metadata={
            "optional": True,
            "description": "Keys are supplied by named items, rather than fixed record fields.",
        }
    )
    by_type: dict[str, int] = field(
        metadata={
            "optional": True,
            "description": "Keys are supplied by named items, rather than fixed record fields.",
        }
    )
    canary: str = field(metadata={"optional": True})
    canary_reason: str = field(metadata={"optional": True})
    canary_removed: int = field(metadata={"optional": True})
    connections: int = field(metadata={"optional": True})
    excluded: int = field(metadata={"optional": True})
    exclusions: ReadyChecksItemSummaryExclusions = field(metadata={"optional": True})
    footprint: int = field(metadata={"optional": True})
    ignored_checks: list[str] = field(metadata={"optional": True})
    limits: list[wire.DrcLimit] | None = field(metadata={"optional": True})
    nets: int | list[readiness_rows.PowerNet] = field(metadata={"optional": True})
    parity: int = field(metadata={"optional": True})
    parity_judged: bool = field(metadata={"optional": True})
    pins: int = field(metadata={"optional": True})
    sheets: int = field(metadata={"optional": True})
    tool_version: str = field(metadata={"optional": True})
    tool_writes: list[str] = field(metadata={"optional": True})
    types: dict[str, str] = field(
        metadata={
            "optional": True,
            "description": "Keys are supplied by named items, rather than fixed record fields.",
        }
    )
    unconnected: int = field(metadata={"optional": True})
    value: int = field(metadata={"optional": True})
    violations: int = field(metadata={"optional": True})
    violations_judged: bool = field(metadata={"optional": True})


@dataclass(frozen=True, kw_only=True)
class ReadyChecksItem:
    evidence: Evidence
    name: str
    reason: str
    status: str
    summary: ReadyChecksItemSummary


@dataclass(frozen=True, kw_only=True)
class ReadyCounts:
    error: int
    info: int
    warning: int


@dataclass(frozen=True, kw_only=True)
class ReadyProject:
    board: str
    built: bool


@dataclass(frozen=True, kw_only=True)
class ReadyResult(ProtocolResult):
    checks: list[ReadyChecksItem] = field(metadata={"optional": True})
    complete: bool = field(metadata={"optional": True})
    counts: ReadyCounts = field(metadata={"optional": True})
    project: ReadyProject = field(metadata={"optional": True})
    ready: bool = field(metadata={"optional": True})


@dataclass(frozen=True, kw_only=True)
class ParityFindingsItem:
    board: str
    code: str
    field: str
    key: str
    schematic: str
    severity: str


@dataclass(frozen=True, kw_only=True)
class ParityResult(ProtocolResult):
    board: str = field(metadata={"optional": True})
    findings: list[ParityFindingsItem] = field(metadata={"optional": True})
    netlist: str = field(metadata={"optional": True})
    schematic: str = field(metadata={"optional": True})
    summary: dict[str, int] = field(
        metadata={
            "optional": True,
            "description": "Keys are supplied by named items, rather than fixed record fields.",
        }
    )


@dataclass(frozen=True, kw_only=True)
class RoundtripRt0:
    difference: str
    passed: bool


@dataclass(frozen=True, kw_only=True)
class RoundtripRt1:
    difference: str
    opaque_count: int
    passed: bool


@dataclass(frozen=True, kw_only=True)
class RoundtripRt2After:
    unconnected: int
    violations: int


@dataclass(frozen=True, kw_only=True)
class RoundtripRt2Before:
    unconnected: int
    violations: int


@dataclass(frozen=True, kw_only=True)
class RoundtripRt2Runs:
    original: int
    redump: int


@dataclass(frozen=True, kw_only=True)
class RoundtripRt2Schematic:
    difference: str
    exact: bool
    judged: bool
    kept: int
    passed: bool
    redumped: int
    violations: int
    violations_redump: int


@dataclass(frozen=True, kw_only=True)
class RoundtripRt2:
    after: RoundtripRt2After
    before: RoundtripRt2Before
    difference: str
    differences: int
    judged: bool
    normalised: bool
    passed: bool
    runs: RoundtripRt2Runs
    schematic: RoundtripRt2Schematic = field(metadata={"optional": True})
    unstable: int


@dataclass(frozen=True, kw_only=True)
class RoundtripRta0:
    documents: int
    failed: int
    level: str
    reason: str
    status: str
    streams: int
    unjudged: dict[str, int] = field(
        metadata={"description": "Keys are supplied by named items, rather than fixed record fields."}
    )


@dataclass(frozen=True, kw_only=True)
class RoundtripRta1:
    bytes_equal: int
    documents: int
    failed: int
    level: str
    opaque_count: int
    reason: str
    records: int
    status: str
    streams: int
    unjudged: dict[str, int] = field(
        metadata={"description": "Keys are supplied by named items, rather than fixed record fields."}
    )


@dataclass(frozen=True, kw_only=True)
class RoundtripRta2:
    reason: str
    status: str


@dataclass(frozen=True, kw_only=True)
class RoundtripRta3:
    differences: int
    files: list[str]
    holds: bool
    level: str
    presentation: str
    reason: str
    status: str
    unwritten: dict[str, int] = field(
        metadata={"description": "Keys are supplied by named items, rather than fixed record fields."}
    )
    written: dict[str, int] = field(
        metadata={"description": "Keys are supplied by named items, rather than fixed record fields."}
    )


@dataclass(frozen=True, kw_only=True)
class RoundtripResult(ProtocolResult):
    kind: str = field(metadata={"optional": True})
    level: str = field(metadata={"optional": True})
    rt0: RoundtripRt0 = field(metadata={"optional": True})
    rt1: RoundtripRt1 | str = field(metadata={"optional": True})
    rt2: RoundtripRt2 = field(metadata={"optional": True})
    rta0: RoundtripRta0 = field(metadata={"optional": True})
    rta1: RoundtripRta1 = field(metadata={"optional": True})
    rta2: RoundtripRta2 = field(metadata={"optional": True})
    rta3: RoundtripRta3 = field(metadata={"optional": True})
    unwritten: dict[str, int] = field(
        metadata={
            "optional": True,
            "description": "Keys are supplied by named items, rather than fixed record fields.",
        }
    )


@dataclass(frozen=True, kw_only=True)
class DiffA:
    kind: str
    path: str


@dataclass(frozen=True, kw_only=True)
class DiffB:
    kind: str
    path: str


@dataclass(frozen=True, kw_only=True)
class DiffDifferencesItem:
    a: str
    b: str
    change: str
    path: str


@dataclass(frozen=True, kw_only=True)
class DiffHeadsValue:
    a: int
    b: int


@dataclass(frozen=True, kw_only=True)
class DiffMergeItemsItem:
    change: str
    key: str
    status: str


@dataclass(frozen=True, kw_only=True)
class DiffMerge:
    already: int
    applied: int
    conflicts: int
    items: list[DiffMergeItemsItem]
    out: str
    refused: None | str
    theirs: str


@dataclass(frozen=True, kw_only=True)
class DiffResave:
    streams: dict[str, int] = field(
        metadata={"description": "Keys are supplied by named items, rather than fixed record fields."}
    )
    total: int


@dataclass(frozen=True, kw_only=True)
class DiffSummaryValue:
    added: int
    changed: int
    removed: int


@dataclass(frozen=True, kw_only=True)
class DiffResult(ProtocolResult):
    a: DiffA = field(metadata={"optional": True})
    allow: list[str] = field(metadata={"optional": True})
    b: DiffB = field(metadata={"optional": True})
    differences: list[DiffDifferencesItem] = field(metadata={"optional": True})
    equal: bool = field(metadata={"optional": True})
    first_difference: None | str = field(metadata={"optional": True})
    heads: dict[str, DiffHeadsValue] = field(
        metadata={
            "optional": True,
            "description": "Keys are supplied by named items, rather than fixed record fields.",
        }
    )
    merge: DiffMerge = field(metadata={"optional": True})
    resave: DiffResave = field(metadata={"optional": True})
    summary: dict[str, DiffSummaryValue] = field(
        metadata={
            "optional": True,
            "description": "Keys are supplied by named items, rather than fixed record fields.",
        }
    )
    total: int = field(metadata={"optional": True})
    truncated: bool = field(metadata={"optional": True})
    view: str = field(metadata={"optional": True})


@dataclass(frozen=True, kw_only=True)
class EquivalentDifferencesItem:
    a: str
    b: str
    field: str
    kind: str
    level: int | Literal["S"]
    where: str


@dataclass(frozen=True, kw_only=True)
class EquivalentExcludedItem:
    a: str
    b: str
    field: str
    kind: str
    level: int | Literal["S"]
    rule: str
    where: str


@dataclass(frozen=True, kw_only=True)
class EquivalentLevelsItemSummaryChanges:
    board: list[str] = field(metadata={"optional": True})


@dataclass(frozen=True, kw_only=True)
class EquivalentLevelsItemSummaryComponents:
    a: int
    b: int


@dataclass(frozen=True, kw_only=True)
class EquivalentLevelsItemSummaryCopperNoNet:
    a: int
    b: int


@dataclass(frozen=True, kw_only=True)
class EquivalentLevelsItemSummaryLength:
    a: int
    b: int


@dataclass(frozen=True, kw_only=True)
class EquivalentLevelsItemSummaryNetsUnpaired:
    a: int
    b: int


@dataclass(frozen=True, kw_only=True)
class EquivalentLevelsItemSummaryPieces:
    a: int
    b: int


@dataclass(frozen=True, kw_only=True)
class EquivalentLevelsItemSummaryPitchNm:
    board: int
    sheet: int


@dataclass(frozen=True, kw_only=True)
class EquivalentLevelsItemSummarySources:
    a: str
    b: str


@dataclass(frozen=True, kw_only=True)
class EquivalentLevelsItemSummaryStrictArcs:
    a: int
    b: int
    matched: int


@dataclass(frozen=True, kw_only=True)
class EquivalentLevelsItemSummaryStrictTracks:
    a: int
    b: int
    matched: int


@dataclass(frozen=True, kw_only=True)
class EquivalentLevelsItemSummaryStrictVias:
    a: int
    b: int
    matched: int


@dataclass(frozen=True, kw_only=True)
class EquivalentLevelsItemSummaryStrict:
    arcs: EquivalentLevelsItemSummaryStrictArcs
    tracks: EquivalentLevelsItemSummaryStrictTracks
    vias: EquivalentLevelsItemSummaryStrictVias


@dataclass(frozen=True, kw_only=True)
class EquivalentLevelsItemSummaryUnnumbered:
    a: int
    b: int


@dataclass(frozen=True, kw_only=True)
class EquivalentLevelsItemSummaryUnshaped:
    a: int
    b: int


@dataclass(frozen=True, kw_only=True)
class EquivalentLevelsItemSummaryVias:
    a: int
    b: int


@dataclass(frozen=True, kw_only=True)
class EquivalentLevelsItemSummaryZonesUnfilled:
    a: int
    b: int


@dataclass(frozen=True, kw_only=True)
class DerivedCacheCrossings:
    rings_with_proper_crossings: int = field(metadata={"minimum": 0})
    proper_edge_pair_crossings: int = field(metadata={"minimum": 0})


@dataclass(frozen=True, kw_only=True)
class DerivedCacheRuleDelta:
    """Uninterpreted native JSON canonicalization; not judged rule/geometry semantics."""

    key: str
    a: wire.CanonicalNativeJson
    b: wire.CanonicalNativeJson


@dataclass(frozen=True, kw_only=True)
class DerivedCacheSettingDelta:
    key: str
    a_canonical_sha256: str
    b_canonical_sha256: str


@dataclass(frozen=True, kw_only=True)
class DerivedCacheSide:
    raw_caches: int = field(metadata={"minimum": 0})
    raw_non_simple_rings: DerivedCacheCrossings
    native_input_sha256: str
    qualified_caches_removed_from_private_input: bool = field(metadata={"enum": [True]})
    input_files: dict[str, str]
    command: list[str]
    exit: int | None
    outcome: str
    stdout_sha256: str
    stderr_sha256: str
    output_sha256: str | None
    regenerated_caches: int = field(metadata={"optional": True, "minimum": 0})
    native_non_simple_rings: DerivedCacheCrossings = field(metadata={"optional": True})
    exact_geometry_sha256: str = field(metadata={"optional": True})


@dataclass(frozen=True, kw_only=True)
class DerivedCacheSides:
    a: DerivedCacheSide = field(metadata={"optional": True})
    b: DerivedCacheSide = field(metadata={"optional": True})


@dataclass(frozen=True, kw_only=True)
class DerivedCacheSourceAliases:
    note: str = field(metadata={"enum": ["source alias, not rewritten"]})
    count: int
    identities: list[str] = field(
        metadata={
            "description": "Side-b identities kept because their side-a identity names several objects."
        }
    )


@dataclass(frozen=True, kw_only=True)
class DerivedCacheCanonicalNets:
    """Every net paired under a canonical name, by rule: rows [side, declared name, pairing key]."""

    slash: list[list[str]] = field(
        metadata={"description": "Nets whose stored {slash} was read as the / of their label text."}
    )
    unconnected_single_pad: list[list[str]] = field(
        metadata={
            "description": "unconnected-( nets of exactly one pad whose name KiCad derives from that pad, "
            "keyed by its reference and number."
        }
    )


@dataclass(frozen=True, kw_only=True)
class DerivedCacheIdentityPreparation:
    """Private identity and order preparation of side b's native input copy only (c0384 2.1). By c0275's
    design a build gives copper its own identities and order; a prepared proof measures geometry once they
    are aligned, is labelled accordingly, and never claims that Fenolite keeps the source's ids or order."""

    scope: str = field(metadata={"enum": ["private-native-input-copy"]})
    side: str = field(metadata={"enum": ["b"]})
    status: str = field(metadata={"enum": ["applied", "unneeded", "refused"]})
    reason: None | str
    label: str = field(
        metadata={
            "enum": [
                "L7",
                "L7 after identity preparation",
                "L7 after order preparation",
                "L7 after identity and order preparation",
            ]
        }
    )
    rewritten: list[list[str]] = field(
        metadata={"description": "Every rewritten object: [kind, side-b identity, side-a identity]."}
    )
    moved: list[list[str | int]] = field(
        metadata={
            "description": "Every moved root segment, arc or via: [kind, side-b identity, old position, new "
            "position], positions 0-based among the root segments, arcs and vias."
        }
    )
    identical_pairs: list[list[str]] = field(
        metadata={"description": "Side-b identities of each admitted pair of fully identical pads."}
    )
    source_aliases: DerivedCacheSourceAliases
    canonical_nets: DerivedCacheCanonicalNets


@dataclass(frozen=True, kw_only=True)
class DerivedCacheSummary:
    """Existing common-tool receipt, not raw-cache equality or a DRC safety certificate."""

    judged_project_keys: list[str]
    unjudged_project_rule_deltas: list[DerivedCacheRuleDelta]
    unjudged_project_setting_deltas: list[DerivedCacheSettingDelta]
    whole_project_json_equality_claimed: bool = field(metadata={"enum": [False]})
    whole_native_rule_file_equality_claimed: bool = field(metadata={"enum": [False]})
    tool: str = field(metadata={"enum": ["kicad-cli"]})
    version: str
    raw_cache_equality_claimed: bool = field(metadata={"enum": [False]})
    drc_safety_gate_claimed: bool = field(metadata={"enum": [False]})
    sides: DerivedCacheSides
    status: str = field(
        metadata={
            "enum": ["equal", "differs", "native-failed", "native-config-changed", "native-cache-unqualified"]
        }
    )
    complete_regenerated_geometry_equal: bool = field(metadata={"optional": True})
    normal_zone_priorities_normalized: bool = field(metadata={"optional": True, "enum": [False]})
    identity_preparation: DerivedCacheIdentityPreparation = field(metadata={"optional": True})


@dataclass(frozen=True, kw_only=True)
class NativeProjectRulesSummary:
    """Scoped exact native context; unknown rule properties are explicitly outside coverage."""

    scope: str
    judged_keys: list[str]
    unjudged_absent_fields: list[str]
    judged_count: int
    source_major: int
    generated_major: int
    a_read_files: dict[str, str]
    b_read_files: dict[str, str]
    unjudged: str


@dataclass(frozen=True, kw_only=True)
class EquivalentLevelsItemSummary:
    derived_cache: DerivedCacheSummary = field(metadata={"optional": True})
    project_geometry: int = field(metadata={"optional": True})
    native_project_rules: NativeProjectRulesSummary = field(metadata={"optional": True})
    items: int = field(metadata={"optional": True})
    extraction_issues: int = field(metadata={"optional": True})
    instances: int = field(metadata={"optional": True})
    pins: int = field(metadata={"optional": True})
    symbols: int = field(metadata={"optional": True})
    changes: EquivalentLevelsItemSummaryChanges = field(metadata={"optional": True})
    components: EquivalentLevelsItemSummaryComponents = field(metadata={"optional": True})
    copper_no_net: EquivalentLevelsItemSummaryCopperNoNet = field(metadata={"optional": True})
    copper_unknown: int = field(metadata={"optional": True})
    dimensions: int = field(metadata={"optional": True})
    footprint_items: int = field(metadata={"optional": True})
    footprints: int = field(metadata={"optional": True})
    frame: str = field(metadata={"optional": True})
    graphics: int = field(metadata={"optional": True})
    holes: int = field(metadata={"optional": True})
    ignored: int = field(metadata={"optional": True})
    keepouts: int = field(metadata={"optional": True})
    layers: int = field(metadata={"optional": True})
    length: EquivalentLevelsItemSummaryLength = field(metadata={"optional": True})
    netclasses: int = field(metadata={"optional": True})
    nets: int = field(metadata={"optional": True})
    nets_unpaired: EquivalentLevelsItemSummaryNetsUnpaired = field(metadata={"optional": True})
    outline: int = field(metadata={"optional": True})
    pieces: EquivalentLevelsItemSummaryPieces = field(metadata={"optional": True})
    pitch_nm: EquivalentLevelsItemSummaryPitchNm = field(metadata={"optional": True})
    pixel_ppm: int = field(metadata={"optional": True})
    renamed: int = field(metadata={"optional": True})
    rules: int = field(metadata={"optional": True})
    sheets: int = field(metadata={"optional": True})
    sources: EquivalentLevelsItemSummarySources = field(metadata={"optional": True})
    stackup: int = field(metadata={"optional": True})
    strict: EquivalentLevelsItemSummaryStrict = field(metadata={"optional": True})
    texts: int = field(metadata={"optional": True})
    translation: list[int] = field(metadata={"optional": True})
    unjudged: int = field(metadata={"optional": True})
    unnumbered: EquivalentLevelsItemSummaryUnnumbered = field(metadata={"optional": True})
    unshaped: EquivalentLevelsItemSummaryUnshaped = field(metadata={"optional": True})
    vias: EquivalentLevelsItemSummaryVias = field(metadata={"optional": True})
    zones: int = field(metadata={"optional": True})
    zones_unfilled: EquivalentLevelsItemSummaryZonesUnfilled = field(metadata={"optional": True})


@dataclass(frozen=True, kw_only=True)
class EquivalentLevelsItem:
    compared: int
    differences: int
    excluded: int
    level: int | Literal["S"]
    name: str
    notices: int
    summary: EquivalentLevelsItemSummary


@dataclass(frozen=True, kw_only=True)
class EquivalentNoticesItem:
    a: str
    b: str
    field: str
    kind: str
    level: int | Literal["S"]
    where: str


@dataclass(frozen=True, kw_only=True)
class EquivalentProfile:
    name: str
    rules: int
    tool_version: str


@dataclass(frozen=True, kw_only=True)
class EquivalentSidesA:
    backend: str
    components: int
    footprints: int
    netlist_source: str
    path: str
    power_symbols: int = field(metadata={"optional": True})
    sha256: None | str

    files: dict[str, str] = field(
        metadata={
            "optional": True,
            "description": "exact context input basenames mapped to SHA-256",
        }
    )


@dataclass(frozen=True, kw_only=True)
class EquivalentSidesB:
    backend: str
    components: int
    footprints: int
    netlist_source: str
    path: str
    sha256: None | str
    tool_version: str = field(metadata={"optional": True})
    power_symbols: int = field(metadata={"optional": True})

    files: dict[str, str] = field(
        metadata={
            "optional": True,
            "description": "exact context input basenames mapped to SHA-256",
        }
    )


@dataclass(frozen=True, kw_only=True)
class EquivalentSides:
    a: EquivalentSidesA
    b: None | EquivalentSidesB


@dataclass(frozen=True, kw_only=True)
class EquivalentTolerances:
    angle_udeg: int
    length_nm: int
    length_ppm: int


@dataclass(frozen=True, kw_only=True)
class EquivalentResult(ProtocolResult):
    differences: list[EquivalentDifferencesItem] = field(metadata={"optional": True})
    equivalent: bool = field(metadata={"optional": True})
    excluded: list[EquivalentExcludedItem] = field(metadata={"optional": True})
    frame: str = field(metadata={"optional": True})
    level: int | Literal["S"] = field(metadata={"optional": True})
    levels: list[EquivalentLevelsItem] = field(metadata={"optional": True})
    notices: list[EquivalentNoticesItem] = field(metadata={"optional": True})
    profile: None | EquivalentProfile = field(metadata={"optional": True})
    sides: EquivalentSides = field(metadata={"optional": True})
    tolerances: EquivalentTolerances = field(metadata={"optional": True})
    tool_version: str = field(metadata={"optional": True})
    translation: list[int] = field(metadata={"optional": True})


@dataclass(frozen=True, kw_only=True)
class ConvertEquivalenceDifferencesItem:
    a: str
    b: str
    field: str
    kind: str
    level: int | Literal["S"]
    where: str


@dataclass(frozen=True, kw_only=True)
class ConvertEquivalenceExplainedItem:
    a: str
    b: str
    by: str
    field: str
    kind: str
    level: int
    where: str


@dataclass(frozen=True, kw_only=True)
class ConvertEquivalenceLevelsItemSummaryComponents:
    a: int
    b: int


@dataclass(frozen=True, kw_only=True)
class ConvertEquivalenceLevelsItemSummaryCopperNoNet:
    a: int
    b: int


@dataclass(frozen=True, kw_only=True)
class ConvertEquivalenceLevelsItemSummaryLength:
    a: int
    b: int


@dataclass(frozen=True, kw_only=True)
class ConvertEquivalenceLevelsItemSummaryNetsUnpaired:
    a: int
    b: int


@dataclass(frozen=True, kw_only=True)
class ConvertEquivalenceLevelsItemSummaryPieces:
    a: int
    b: int


@dataclass(frozen=True, kw_only=True)
class ConvertEquivalenceLevelsItemSummarySources:
    a: str
    b: str


@dataclass(frozen=True, kw_only=True)
class ConvertEquivalenceLevelsItemSummaryUnnumbered:
    a: int
    b: int


@dataclass(frozen=True, kw_only=True)
class ConvertEquivalenceLevelsItemSummaryUnshaped:
    a: int
    b: int


@dataclass(frozen=True, kw_only=True)
class ConvertEquivalenceLevelsItemSummaryVias:
    a: int
    b: int


@dataclass(frozen=True, kw_only=True)
class ConvertEquivalenceLevelsItemSummaryZonesUnfilled:
    a: int
    b: int


@dataclass(frozen=True, kw_only=True)
class ConvertEquivalenceLevelsItemSummary:
    extraction_issues: int = field(metadata={"optional": True})
    instances: int = field(metadata={"optional": True})
    pins: int = field(metadata={"optional": True})
    sheets: int = field(metadata={"optional": True})
    symbols: int = field(metadata={"optional": True})
    texts: int = field(metadata={"optional": True})
    components: ConvertEquivalenceLevelsItemSummaryComponents = field(metadata={"optional": True})
    copper_no_net: ConvertEquivalenceLevelsItemSummaryCopperNoNet = field(metadata={"optional": True})
    copper_unknown: int = field(metadata={"optional": True})
    footprints: int = field(metadata={"optional": True})
    frame: str = field(metadata={"optional": True})
    ignored: int = field(metadata={"optional": True})
    length: ConvertEquivalenceLevelsItemSummaryLength = field(metadata={"optional": True})
    nets: int = field(metadata={"optional": True})
    nets_unpaired: ConvertEquivalenceLevelsItemSummaryNetsUnpaired = field(metadata={"optional": True})
    pieces: ConvertEquivalenceLevelsItemSummaryPieces = field(metadata={"optional": True})
    renamed: int = field(metadata={"optional": True})
    sources: ConvertEquivalenceLevelsItemSummarySources = field(metadata={"optional": True})
    translation: list[int] = field(metadata={"optional": True})
    unjudged: int = field(metadata={"optional": True})
    unnumbered: ConvertEquivalenceLevelsItemSummaryUnnumbered = field(metadata={"optional": True})
    unshaped: ConvertEquivalenceLevelsItemSummaryUnshaped = field(metadata={"optional": True})
    vias: ConvertEquivalenceLevelsItemSummaryVias = field(metadata={"optional": True})
    zones_unfilled: ConvertEquivalenceLevelsItemSummaryZonesUnfilled = field(metadata={"optional": True})


@dataclass(frozen=True, kw_only=True)
class ConvertEquivalenceLevelsItem:
    compared: int
    differences: int
    excluded: int
    level: int | Literal["S"]
    name: str
    notices: int
    summary: ConvertEquivalenceLevelsItemSummary


@dataclass(frozen=True, kw_only=True)
class ConvertEquivalenceProfile:
    name: str
    rules: int
    tool_version: str


@dataclass(frozen=True, kw_only=True)
class ConvertEquivalenceSidesA:
    backend: str
    components: int
    footprints: int
    netlist_source: str
    path: str
    sha256: str | None

    files: dict[str, str] = field(
        metadata={
            "optional": True,
            "description": "exact context input basenames mapped to SHA-256",
        }
    )


@dataclass(frozen=True, kw_only=True)
class ConvertEquivalenceSidesB:
    backend: str
    components: int
    footprints: int
    netlist_source: str
    path: str
    sha256: str | None

    files: dict[str, str] = field(
        metadata={
            "optional": True,
            "description": "exact context input basenames mapped to SHA-256",
        }
    )


@dataclass(frozen=True, kw_only=True)
class ConvertEquivalenceSides:
    a: ConvertEquivalenceSidesA
    b: ConvertEquivalenceSidesB


@dataclass(frozen=True, kw_only=True)
class ConvertEquivalenceTolerances:
    angle_udeg: int
    length_nm: int
    length_ppm: int


@dataclass(frozen=True, kw_only=True)
class ConvertEquivalence:
    differences: list[ConvertEquivalenceDifferencesItem]
    equivalent: bool
    excluded: list[EquivalentExcludedItem]
    explained: list[ConvertEquivalenceExplainedItem]
    frame: str
    level: int | Literal["S"]
    levels: list[ConvertEquivalenceLevelsItem]
    notices: list[EquivalentNoticesItem]
    profile: ConvertEquivalenceProfile
    sides: ConvertEquivalenceSides
    tolerances: ConvertEquivalenceTolerances
    translation: list[int]
    unexplained: int


@dataclass(frozen=True, kw_only=True)
class ConvertFilesItem:
    bytes: int
    name: str


@dataclass(frozen=True, kw_only=True)
class ConvertReportRowsItemReasonsItem:
    count: int
    ids: list[str] = field(metadata={"optional": True})
    outcome: str
    reason: str


@dataclass(frozen=True, kw_only=True)
class ConvertReportRowsItem:
    changed: int
    group: str
    kept: int = field(metadata={"optional": True})
    kind: str
    loss: str
    lost: int
    reasons: list[ConvertReportRowsItemReasonsItem]
    source: int
    written: int


@dataclass(frozen=True, kw_only=True)
class ConvertReport:
    lossy: bool
    refused: list[str]
    rows: list[ConvertReportRowsItem]


@dataclass(frozen=True, kw_only=True)
class ConvertSource:
    backend: str
    format_version: int | None
    kind: str
    path: str


@dataclass(frozen=True, kw_only=True)
class ConvertTarget:
    backend: str
    major: int | None


@dataclass(frozen=True, kw_only=True)
class ConvertResult(ProtocolResult):
    equivalence: None | ConvertEquivalence = field(metadata={"optional": True})
    experimental: bool = field(metadata={"optional": True})
    files: list[ConvertFilesItem] = field(metadata={"optional": True})
    report: ConvertReport = field(metadata={"optional": True})
    source: ConvertSource = field(metadata={"optional": True})
    target: ConvertTarget = field(metadata={"optional": True})


@dataclass(frozen=True, kw_only=True)
class ImportCounts:
    arcs: int
    drawings: int
    nets: int
    parts: int
    rule_areas: int
    tables: int
    tracks: int
    vias: int
    zones: int


@dataclass(frozen=True, kw_only=True)
class ImportEquivalence:
    equivalent: bool
    levels: list[int]


@dataclass(frozen=True, kw_only=True)
class ImportFilesItem:
    bytes: int
    path: str


@dataclass(frozen=True, kw_only=True)
class ImportProvenance:
    licence: str
    revision: str | None
    source: str | None


@dataclass(frozen=True, kw_only=True)
class ImportSource:
    backend: str
    file: str
    versions: dict[str, int]


@dataclass(frozen=True, kw_only=True)
class ImportResult(ProtocolResult):
    adopted: wire.AdoptedSummary | None = field(metadata={"optional": True})
    counts: ImportCounts = field(metadata={"optional": True})
    design: str = field(metadata={"optional": True})
    equivalence: ImportEquivalence = field(metadata={"optional": True})
    files: list[ImportFilesItem] = field(metadata={"optional": True})
    modules: list[str] = field(metadata={"optional": True})
    out: str = field(metadata={"optional": True})
    provenance: ImportProvenance = field(metadata={"optional": True})
    report: ConvertReport | None = field(metadata={"optional": True})
    source: ImportSource = field(metadata={"optional": True})
    unexpressed: list[import_rows.ImportUnexpressed] = field(metadata={"optional": True})
    upgrade: list[import_rows.ImportUpgrade] = field(metadata={"optional": True})


@dataclass(frozen=True, kw_only=True)
class VerifySourceAcceptedItem:
    a: str
    b: str
    field: str
    kind: str
    level: int | str
    rule: str
    where: str


@dataclass(frozen=True, kw_only=True)
class VerifySourceAgainst:
    backend: str
    files: dict[str, str] = field(
        metadata={"description": "Keys are supplied by named items, rather than fixed record fields."}
    )
    name: str


@dataclass(frozen=True, kw_only=True)
class VerifySourceBuild:
    copper_check: str
    copy: bool
    files: int
    target: str

    read_files: dict[str, str] = field(
        metadata={
            "optional": True,
            "description": "generated temporary build outputs read by the proof",
        }
    )


@dataclass(frozen=True, kw_only=True)
class VerifySourceDifferencesItem:
    a: str
    b: str
    field: str
    kind: str
    level: int | str
    where: str


@dataclass(frozen=True, kw_only=True)
class VerifySourceLevelsItemSummaryChanges:
    board: list[str] = field(metadata={"optional": True})


@dataclass(frozen=True, kw_only=True)
class VerifySourceLevelsItemSummaryComponents:
    a: int
    b: int


@dataclass(frozen=True, kw_only=True)
class VerifySourceLevelsItemSummaryCopperNoNet:
    a: int
    b: int


@dataclass(frozen=True, kw_only=True)
class VerifySourceLevelsItemSummaryLength:
    a: int
    b: int


@dataclass(frozen=True, kw_only=True)
class VerifySourceLevelsItemSummaryNetsUnpaired:
    a: int
    b: int


@dataclass(frozen=True, kw_only=True)
class VerifySourceLevelsItemSummaryPieces:
    a: int
    b: int


@dataclass(frozen=True, kw_only=True)
class VerifySourceLevelsItemSummaryPitchNm:
    board: int
    sheet: int


@dataclass(frozen=True, kw_only=True)
class VerifySourceLevelsItemSummarySources:
    a: str
    b: str


@dataclass(frozen=True, kw_only=True)
class VerifySourceLevelsItemSummaryStrictArcs:
    a: int
    b: int
    matched: int


@dataclass(frozen=True, kw_only=True)
class VerifySourceLevelsItemSummaryStrictTracks:
    a: int
    b: int
    matched: int


@dataclass(frozen=True, kw_only=True)
class VerifySourceLevelsItemSummaryStrictVias:
    a: int
    b: int
    matched: int


@dataclass(frozen=True, kw_only=True)
class VerifySourceLevelsItemSummaryStrict:
    arcs: VerifySourceLevelsItemSummaryStrictArcs
    tracks: VerifySourceLevelsItemSummaryStrictTracks
    vias: VerifySourceLevelsItemSummaryStrictVias


@dataclass(frozen=True, kw_only=True)
class VerifySourceLevelsItemSummaryUnnumbered:
    a: int
    b: int


@dataclass(frozen=True, kw_only=True)
class VerifySourceLevelsItemSummaryUnshaped:
    a: int
    b: int


@dataclass(frozen=True, kw_only=True)
class VerifySourceLevelsItemSummaryVias:
    a: int
    b: int


@dataclass(frozen=True, kw_only=True)
class VerifySourceLevelsItemSummaryZonesUnfilled:
    a: int
    b: int


@dataclass(frozen=True, kw_only=True)
class VerifySourceLevelsItemSummary:
    derived_cache: DerivedCacheSummary = field(metadata={"optional": True})
    project_geometry: int = field(metadata={"optional": True})
    native_project_rules: NativeProjectRulesSummary = field(metadata={"optional": True})
    changes: VerifySourceLevelsItemSummaryChanges = field(metadata={"optional": True})
    components: VerifySourceLevelsItemSummaryComponents = field(metadata={"optional": True})
    copper_no_net: VerifySourceLevelsItemSummaryCopperNoNet = field(metadata={"optional": True})
    copper_unknown: int = field(metadata={"optional": True})
    dimensions: int = field(metadata={"optional": True})
    extraction_issues: int = field(metadata={"optional": True})
    footprint_items: int = field(metadata={"optional": True})
    footprints: int = field(metadata={"optional": True})
    frame: str = field(metadata={"optional": True})
    graphics: int = field(metadata={"optional": True})
    holes: int = field(metadata={"optional": True})
    ignored: int = field(metadata={"optional": True})
    instances: int = field(metadata={"optional": True})
    items: int = field(metadata={"optional": True})
    keepouts: int = field(metadata={"optional": True})
    layers: int = field(metadata={"optional": True})
    length: VerifySourceLevelsItemSummaryLength = field(metadata={"optional": True})
    netclasses: int = field(metadata={"optional": True})
    nets: int = field(metadata={"optional": True})
    nets_unpaired: VerifySourceLevelsItemSummaryNetsUnpaired = field(metadata={"optional": True})
    opaque: int = field(metadata={"optional": True})
    outline: int = field(metadata={"optional": True})
    pieces: VerifySourceLevelsItemSummaryPieces = field(metadata={"optional": True})
    pins: int = field(metadata={"optional": True})
    pitch_nm: VerifySourceLevelsItemSummaryPitchNm = field(metadata={"optional": True})
    pixel_ppm: int = field(metadata={"optional": True})
    renamed: int = field(metadata={"optional": True})
    rules: int = field(metadata={"optional": True})
    sheets: int = field(metadata={"optional": True})
    sources: VerifySourceLevelsItemSummarySources = field(metadata={"optional": True})
    stackup: int = field(metadata={"optional": True})
    strict: VerifySourceLevelsItemSummaryStrict = field(metadata={"optional": True})
    symbols: int = field(metadata={"optional": True})
    texts: int = field(metadata={"optional": True})
    translation: list[int] = field(metadata={"optional": True})
    unjudged: int = field(metadata={"optional": True})
    unnumbered: VerifySourceLevelsItemSummaryUnnumbered = field(metadata={"optional": True})
    unshaped: VerifySourceLevelsItemSummaryUnshaped = field(metadata={"optional": True})
    vias: VerifySourceLevelsItemSummaryVias = field(metadata={"optional": True})
    zones: int = field(metadata={"optional": True})
    zones_unfilled: VerifySourceLevelsItemSummaryZonesUnfilled = field(metadata={"optional": True})


@dataclass(frozen=True, kw_only=True)
class VerifySourceLevelsItem:
    compared: int
    differences: int
    excluded: int
    level: int | str
    name: str
    notices: int
    reason: str
    status: str
    summary: VerifySourceLevelsItemSummary


@dataclass(frozen=True, kw_only=True)
class VerifySourceNewAcceptedItem:
    attribution: str
    decided: str
    field: str
    id: str
    kind: str
    level: int | str
    reason: str
    where: str


@dataclass(frozen=True, kw_only=True)
class VerifySourceNoticesItem:
    a: str
    b: str
    field: str
    kind: str
    level: int
    where: str


@dataclass(frozen=True, kw_only=True)
class VerifySourceProvenance:
    accepted: int
    path: None | str
    record: bool


@dataclass(frozen=True, kw_only=True)
class VerifySourceScript:
    name: str
    sha256: str


@dataclass(frozen=True, kw_only=True)
class VerifySourceTolerances:
    angle_udeg: int
    frame: str
    length_nm: int
    length_ppm: int
    pixel_ppm: int
    render_pitch_um: int


@dataclass(frozen=True, kw_only=True)
class VerifySourceResult(ProtocolResult):
    accepted: list[VerifySourceAcceptedItem] = field(metadata={"optional": True})
    against: VerifySourceAgainst = field(metadata={"optional": True})
    build: VerifySourceBuild = field(metadata={"optional": True})
    differences: list[VerifySourceDifferencesItem] = field(metadata={"optional": True})
    equivalent: bool = field(metadata={"optional": True})
    levels: list[VerifySourceLevelsItem] = field(metadata={"optional": True})
    new_accepted: list[VerifySourceNewAcceptedItem] = field(metadata={"optional": True})
    notices: list[VerifySourceNoticesItem] = field(metadata={"optional": True})
    provenance: VerifySourceProvenance = field(metadata={"optional": True})
    script: VerifySourceScript = field(metadata={"optional": True})
    tolerances: VerifySourceTolerances = field(metadata={"optional": True})
