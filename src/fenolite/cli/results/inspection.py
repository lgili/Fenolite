# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Wire records for inspection results; producers retain their existing payloads."""

from __future__ import annotations

from dataclasses import dataclass, field

from fenolite.cli.results import common as wire
from fenolite.cli.results.common import (
    ProtocolResult,
)
from fenolite.cli.results.route_proposals import NativeCheck
from fenolite.core.errors import Issue


@dataclass(frozen=True, kw_only=True)
class InspectBlocksItemInstancesItemParamsItem:
    name: str
    text: str
    type: str


@dataclass(frozen=True, kw_only=True)
class InspectBlocksItemInstancesItem:
    params: list[InspectBlocksItemInstancesItemParamsItem] = field(metadata={"optional": True})
    path: str


@dataclass(frozen=True, kw_only=True)
class InspectBlocksItem:
    id: str
    instances: list[InspectBlocksItemInstancesItem]
    version: str


@dataclass(frozen=True, kw_only=True)
class InspectDocumentsItem:
    exists: bool
    kind: None | str
    name: str
    role: None | str


@dataclass(frozen=True, kw_only=True)
class InspectEntriesItem:
    children: int = field(metadata={"optional": True})
    path: str
    sha256: str = field(metadata={"optional": True})
    size: int = field(metadata={"optional": True})
    type: str


@dataclass(frozen=True, kw_only=True)
class InspectModelFindings:
    error: int = field(metadata={"optional": True})
    warning: int = field(metadata={"optional": True})


@dataclass(frozen=True, kw_only=True)
class InspectStackupLayersItem:
    color: str = field(metadata={"optional": True})
    dielectric_kind: str = field(metadata={"optional": True})
    epsilon_r: str = field(metadata={"optional": True})
    kind: str
    loss_tangent: str = field(metadata={"optional": True})
    material: str = field(metadata={"optional": True})
    name: str
    thickness: int


@dataclass(frozen=True, kw_only=True)
class InspectStackup:
    finish: str
    impedance_controlled: bool
    layers: list[InspectStackupLayersItem]
    thickness: int


@dataclass(frozen=True, kw_only=True)
class InspectStreams:
    opaque: int
    typed: int


@dataclass(frozen=True, kw_only=True)
class InspectViaProtection:
    by_default: dict[str, int] = field(
        metadata={"description": "Keys are supplied by named items, rather than fixed record fields."}
    )
    default: dict[str, bool | str] = field(
        metadata={"description": "Keys are supplied by named items, rather than fixed record fields."}
    )
    effective: dict[str, int] = field(
        metadata={"description": "Keys are supplied by named items, rather than fixed record fields."}
    )


@dataclass(frozen=True, kw_only=True)
class InspectResult(ProtocolResult):
    blocks: list[InspectBlocksItem] = field(metadata={"optional": True})
    counts: dict[str, int] = field(
        metadata={
            "optional": True,
            "description": "Keys are supplied by named items, rather than fixed record fields.",
        }
    )
    difat_sectors: int = field(metadata={"optional": True})
    directory_entries: int = field(metadata={"optional": True})
    documents: list[InspectDocumentsItem] = field(metadata={"optional": True})
    entries: list[InspectEntriesItem] = field(metadata={"optional": True})
    fat_sectors: int = field(metadata={"optional": True})
    format_version: int | None | str = field(metadata={"optional": True})
    generator: None | str = field(metadata={"optional": True})
    generator_version: None | str = field(metadata={"optional": True})
    kind: str = field(metadata={"optional": True})
    major: int | None = field(metadata={"optional": True})
    mini_sector_size: int = field(metadata={"optional": True})
    minor: int = field(metadata={"optional": True})
    model_findings: InspectModelFindings = field(metadata={"optional": True})
    opaque_count: int | None = field(metadata={"optional": True})
    root_clsid: str | None = field(metadata={"optional": True})
    sector_size: int = field(metadata={"optional": True})
    sectors: int = field(metadata={"optional": True})
    stackup: None | InspectStackup = field(metadata={"optional": True})
    status: str = field(metadata={"optional": True})
    streams: InspectStreams = field(metadata={"optional": True})
    via_protection: InspectViaProtection = field(metadata={"optional": True})


@dataclass(frozen=True, kw_only=True)
class ViewCache:
    hits: int
    misses: int
    where: str


@dataclass(frozen=True, kw_only=True)
class ViewCheck:
    error: int
    info: int
    placed: int
    total: int
    warning: int


@dataclass(frozen=True, kw_only=True)
class ViewCompareOld:
    name: str
    sha256: str


@dataclass(frozen=True, kw_only=True)
class ViewCompare:
    added: int
    changed: int
    changes: list[str]
    kind: str
    moved: int
    old: ViewCompareOld
    removed: int
    zone: int


@dataclass(frozen=True, kw_only=True)
class ViewExport:
    bytes: int
    documents: list[str]
    sha256: str


@dataclass(frozen=True, kw_only=True)
class ViewMarksItem:
    created: str
    doc: str
    id: str
    note: str
    select: str
    x_mm: float
    x_nm: int
    y_mm: float
    y_nm: int


@dataclass(frozen=True, kw_only=True)
class ViewProjectGroupsItemDocumentsItem:
    group: str
    id: str
    kind: str
    name: str
    path: str
    present: bool
    size: int
    viewable: bool


@dataclass(frozen=True, kw_only=True)
class ViewProjectGroupsItem:
    documents: list[ViewProjectGroupsItemDocumentsItem]
    name: str


@dataclass(frozen=True, kw_only=True)
class ViewProject:
    groups: list[ViewProjectGroupsItem]
    issues: list[Issue]
    name: str
    project_file: str
    source: str


@dataclass(frozen=True, kw_only=True)
class ViewReviewBinding:
    matched: bool
    note: str
    path: str
    sha256: str


@dataclass(frozen=True, kw_only=True)
class ViewReviewCardsItemBinding:
    matched: bool
    note: str
    path: str
    sha256: str


@dataclass(frozen=True, kw_only=True)
class ViewReviewCardsItemStagesItemCounts:
    error: int
    info: int
    warning: int


@dataclass(frozen=True, kw_only=True)
class ViewReviewCardsItemStagesItemSummaryClearanceCells:
    judged: int
    unjudged: int


@dataclass(frozen=True, kw_only=True)
class ViewReviewCardsItemStagesItemSummaryEdges:
    judged: int
    max: int
    rings: list[str]
    unset_items: int


@dataclass(frozen=True, kw_only=True)
class ViewReviewCardsItemStagesItemSummaryItems:
    arc: int = field(metadata={"optional": True})
    fill: int = field(metadata={"optional": True})
    pad: int
    track: int = field(metadata={"optional": True})
    via: int = field(metadata={"optional": True})


@dataclass(frozen=True, kw_only=True)
class ViewReviewCardsItemStagesItemSummaryMeasuresCongestionBusiestItem:
    tracks: int
    x: int
    y: int


@dataclass(frozen=True, kw_only=True)
class ViewReviewCardsItemStagesItemSummaryMeasuresCongestion:
    busiest: list[ViewReviewCardsItemStagesItemSummaryMeasuresCongestionBusiestItem]
    cell: int
    layers_needed: dict[str, int] | None
    pitch: int | None
    tracks_per_layer: int | None


@dataclass(frozen=True, kw_only=True)
class ViewReviewCardsItemStagesItemSummaryMeasuresLeftOut:
    off_board: int
    one_pad_nets: int
    zone_nets: int


@dataclass(frozen=True, kw_only=True)
class ViewReviewCardsItemStagesItemSummaryMeasuresLongestItem:
    hpwl: int
    net: str
    pads: int
    ratsnest: int


@dataclass(frozen=True, kw_only=True)
class ViewReviewCardsItemStagesItemSummaryMeasures:
    congestion: ViewReviewCardsItemStagesItemSummaryMeasuresCongestion
    hpwl: int
    left_out: ViewReviewCardsItemStagesItemSummaryMeasuresLeftOut
    longest: list[ViewReviewCardsItemStagesItemSummaryMeasuresLongestItem]
    nets: int
    ratsnest: int


@dataclass(frozen=True, kw_only=True)
class ViewReviewCardsItemStagesItemSummaryPairsItem:
    a: str
    b: str
    common: int
    differences: int
    only_a: int
    only_b: int


@dataclass(frozen=True, kw_only=True)
class ViewReviewCardsItemStagesItemSummaryPcb:
    components: int
    nets: int


@dataclass(frozen=True, kw_only=True)
class ViewReviewCardsItemStagesItemSummaryRulesNear:
    failed: int
    judged: int
    skipped: int


@dataclass(frozen=True, kw_only=True)
class ViewReviewCardsItemStagesItemSummaryRules:
    min_clearance: int | None = field(metadata={"optional": True})
    near: ViewReviewCardsItemStagesItemSummaryRulesNear = field(metadata={"optional": True})
    opaque_clearance_rules: int = field(metadata={"optional": True})
    unread: list[str] = field(metadata={"optional": True})


@dataclass(frozen=True, kw_only=True)
class ViewReviewCardsItemStagesItemSummarySchematic:
    components: int
    nets: int


@dataclass(frozen=True, kw_only=True)
class ViewReviewCardsItemStagesItemSummary:
    approximated: int = field(metadata={"optional": True})
    arc_tol: int = field(metadata={"optional": True})
    bytes_equal: int = field(metadata={"optional": True})
    clearance: int = field(metadata={"optional": True})
    clearance_cells: ViewReviewCardsItemStagesItemSummaryClearanceCells = field(metadata={"optional": True})
    compared: bool = field(metadata={"optional": True})
    components: int = field(metadata={"optional": True})
    connections_missing: int = field(metadata={"optional": True})
    differences: int = field(metadata={"optional": True})
    documents: int = field(metadata={"optional": True})
    edge_clearance: int = field(metadata={"optional": True})
    edges: ViewReviewCardsItemStagesItemSummaryEdges = field(metadata={"optional": True})
    failed: int = field(metadata={"optional": True})
    floating_pin: int = field(metadata={"optional": True, "name": "floating-pin"})
    hole_clearance: int = field(metadata={"optional": True})
    hole_clearance_judged: int = field(metadata={"optional": True})
    hole_in_cutout: int = field(metadata={"optional": True})
    hole_overlap: int = field(metadata={"optional": True})
    holes: int = field(metadata={"optional": True})
    items: ViewReviewCardsItemStagesItemSummaryItems = field(metadata={"optional": True})
    judged: int = field(metadata={"optional": True})
    keepouts: int = field(metadata={"optional": True})
    layers: list[str] = field(metadata={"optional": True})
    level: str = field(metadata={"optional": True})
    max_clearance: int = field(metadata={"optional": True})
    measures: ViewReviewCardsItemStagesItemSummaryMeasures = field(metadata={"optional": True})
    min_pins: int = field(metadata={"optional": True})
    net_tie_pairs: int = field(metadata={"optional": True})
    netlist: str = field(metadata={"optional": True})
    nets: int = field(metadata={"optional": True})
    nets_split: int = field(metadata={"optional": True})
    opaque_count: int = field(metadata={"optional": True})
    output_conflict: int = field(metadata={"optional": True, "name": "output-conflict"})
    pairs: list[ViewReviewCardsItemStagesItemSummaryPairsItem] | int = field(metadata={"optional": True})
    parity_duplicate_footprints: int = field(
        metadata={"optional": True, "name": "parity.duplicate-footprints"}
    )
    parity_extra_footprint: int = field(metadata={"optional": True, "name": "parity.extra-footprint"})
    parity_footprint_mismatch: int = field(metadata={"optional": True, "name": "parity.footprint-mismatch"})
    parity_missing_footprint: int = field(metadata={"optional": True, "name": "parity.missing-footprint"})
    parity_net_conflict: int = field(metadata={"optional": True, "name": "parity.net-conflict"})
    parity_pad_without_pin: int = field(metadata={"optional": True, "name": "parity.pad-without-pin"})
    parity_pin_without_pad: int = field(metadata={"optional": True, "name": "parity.pin-without-pad"})
    pcb: ViewReviewCardsItemStagesItemSummaryPcb = field(metadata={"optional": True})
    power_undriven: int = field(metadata={"optional": True, "name": "power-undriven"})
    records: int = field(metadata={"optional": True})
    refs_one_side: int = field(metadata={"optional": True})
    rule_areas: int = field(metadata={"optional": True})
    rules: ViewReviewCardsItemStagesItemSummaryRules = field(metadata={"optional": True})
    schematic: ViewReviewCardsItemStagesItemSummarySchematic = field(metadata={"optional": True})
    shorts: int = field(metadata={"optional": True})
    streams: int = field(metadata={"optional": True})
    tolerance: int = field(metadata={"optional": True})
    unjudged: dict[str, int] = field(
        metadata={
            "optional": True,
            "description": "Keys are supplied by named items, rather than fixed record fields.",
        }
    )
    unnumbered: int = field(metadata={"optional": True})
    unpoured: int = field(metadata={"optional": True})
    unset_pairs: int = field(metadata={"optional": True})
    unsupported: dict[str, int] = field(metadata={"optional": True})
    zone_overlaps: int = field(metadata={"optional": True})
    zones_unjudged: int = field(metadata={"optional": True})


@dataclass(frozen=True, kw_only=True)
class ViewReviewCardsItemStagesItem:
    counts: ViewReviewCardsItemStagesItemCounts
    evidence: str
    limits: list[wire.DrcLimit] | None
    name: str
    reasons: list[str]
    state: str
    status: str
    summary: ViewReviewCardsItemStagesItemSummary


@dataclass(frozen=True, kw_only=True)
class ViewReviewCardsItem:
    binding: ViewReviewCardsItemBinding = field(metadata={"optional": True})
    evidence: str = field(metadata={"optional": True})
    id: str
    missing: list[str]
    reasons: list[str] = field(metadata={"optional": True})
    stages: list[ViewReviewCardsItemStagesItem]
    state: str
    title: str


@dataclass(frozen=True, kw_only=True)
class ViewReviewStagesItemCounts:
    error: int
    info: int
    warning: int


@dataclass(frozen=True, kw_only=True)
class ViewReviewStagesItemSummaryClearanceCells:
    judged: int
    unjudged: int


@dataclass(frozen=True, kw_only=True)
class ViewReviewStagesItemSummaryEdges:
    judged: int
    max: int
    rings: list[str]
    unset_items: int


@dataclass(frozen=True, kw_only=True)
class ViewReviewStagesItemSummaryItems:
    arc: int = field(metadata={"optional": True})
    fill: int = field(metadata={"optional": True})
    pad: int
    track: int = field(metadata={"optional": True})
    via: int = field(metadata={"optional": True})


@dataclass(frozen=True, kw_only=True)
class ViewReviewStagesItemSummaryMeasuresCongestionBusiestItem:
    tracks: int
    x: int
    y: int


@dataclass(frozen=True, kw_only=True)
class ViewReviewStagesItemSummaryMeasuresCongestion:
    busiest: list[ViewReviewStagesItemSummaryMeasuresCongestionBusiestItem]
    cell: int
    layers_needed: dict[str, int] | None
    pitch: int | None
    tracks_per_layer: int | None


@dataclass(frozen=True, kw_only=True)
class ViewReviewStagesItemSummaryMeasuresLeftOut:
    off_board: int
    one_pad_nets: int
    zone_nets: int


@dataclass(frozen=True, kw_only=True)
class ViewReviewStagesItemSummaryMeasuresLongestItem:
    hpwl: int
    net: str
    pads: int
    ratsnest: int


@dataclass(frozen=True, kw_only=True)
class ViewReviewStagesItemSummaryMeasures:
    congestion: ViewReviewStagesItemSummaryMeasuresCongestion
    hpwl: int
    left_out: ViewReviewStagesItemSummaryMeasuresLeftOut
    longest: list[ViewReviewStagesItemSummaryMeasuresLongestItem]
    nets: int
    ratsnest: int


@dataclass(frozen=True, kw_only=True)
class ViewReviewStagesItemSummaryPairsItem:
    a: str
    b: str
    common: int
    differences: int
    only_a: int
    only_b: int


@dataclass(frozen=True, kw_only=True)
class ViewReviewStagesItemSummaryPcb:
    components: int
    nets: int


@dataclass(frozen=True, kw_only=True)
class ViewReviewStagesItemSummaryRulesNear:
    failed: int
    judged: int
    skipped: int


@dataclass(frozen=True, kw_only=True)
class ViewReviewStagesItemSummaryRules:
    min_clearance: int | None = field(metadata={"optional": True})
    near: ViewReviewStagesItemSummaryRulesNear = field(metadata={"optional": True})
    opaque_clearance_rules: int = field(metadata={"optional": True})
    unread: list[str] = field(metadata={"optional": True})


@dataclass(frozen=True, kw_only=True)
class ViewReviewStagesItemSummarySchematic:
    components: int
    nets: int


@dataclass(frozen=True, kw_only=True)
class ViewReviewStagesItemSummary:
    approximated: int = field(metadata={"optional": True})
    arc_tol: int = field(metadata={"optional": True})
    bytes_equal: int = field(metadata={"optional": True})
    clearance: int = field(metadata={"optional": True})
    clearance_cells: ViewReviewStagesItemSummaryClearanceCells = field(metadata={"optional": True})
    compared: bool = field(metadata={"optional": True})
    components: int = field(metadata={"optional": True})
    connections_missing: int = field(metadata={"optional": True})
    differences: int = field(metadata={"optional": True})
    documents: int = field(metadata={"optional": True})
    edge_clearance: int = field(metadata={"optional": True})
    edges: ViewReviewStagesItemSummaryEdges = field(metadata={"optional": True})
    failed: int = field(metadata={"optional": True})
    floating_pin: int = field(metadata={"optional": True, "name": "floating-pin"})
    hole_clearance: int = field(metadata={"optional": True})
    hole_clearance_judged: int = field(metadata={"optional": True})
    hole_in_cutout: int = field(metadata={"optional": True})
    hole_overlap: int = field(metadata={"optional": True})
    holes: int = field(metadata={"optional": True})
    items: ViewReviewStagesItemSummaryItems = field(metadata={"optional": True})
    judged: int = field(metadata={"optional": True})
    keepouts: int = field(metadata={"optional": True})
    layers: list[str] = field(metadata={"optional": True})
    level: str = field(metadata={"optional": True})
    max_clearance: int = field(metadata={"optional": True})
    measures: ViewReviewStagesItemSummaryMeasures = field(metadata={"optional": True})
    min_pins: int = field(metadata={"optional": True})
    net_tie_pairs: int = field(metadata={"optional": True})
    netlist: str = field(metadata={"optional": True})
    nets: int = field(metadata={"optional": True})
    nets_split: int = field(metadata={"optional": True})
    opaque_count: int = field(metadata={"optional": True})
    output_conflict: int = field(metadata={"optional": True, "name": "output-conflict"})
    pairs: list[ViewReviewStagesItemSummaryPairsItem] | int = field(metadata={"optional": True})
    parity_duplicate_footprints: int = field(
        metadata={"optional": True, "name": "parity.duplicate-footprints"}
    )
    parity_extra_footprint: int = field(metadata={"optional": True, "name": "parity.extra-footprint"})
    parity_footprint_mismatch: int = field(metadata={"optional": True, "name": "parity.footprint-mismatch"})
    parity_missing_footprint: int = field(metadata={"optional": True, "name": "parity.missing-footprint"})
    parity_net_conflict: int = field(metadata={"optional": True, "name": "parity.net-conflict"})
    parity_pad_without_pin: int = field(metadata={"optional": True, "name": "parity.pad-without-pin"})
    parity_pin_without_pad: int = field(metadata={"optional": True, "name": "parity.pin-without-pad"})
    pcb: ViewReviewStagesItemSummaryPcb = field(metadata={"optional": True})
    power_undriven: int = field(metadata={"optional": True, "name": "power-undriven"})
    records: int = field(metadata={"optional": True})
    refs_one_side: int = field(metadata={"optional": True})
    rule_areas: int = field(metadata={"optional": True})
    rules: ViewReviewStagesItemSummaryRules = field(metadata={"optional": True})
    schematic: ViewReviewStagesItemSummarySchematic = field(metadata={"optional": True})
    shorts: int = field(metadata={"optional": True})
    streams: int = field(metadata={"optional": True})
    tolerance: int = field(metadata={"optional": True})
    unjudged: dict[str, int] = field(
        metadata={
            "optional": True,
            "description": "Keys are supplied by named items, rather than fixed record fields.",
        }
    )
    unnumbered: int = field(metadata={"optional": True})
    unpoured: int = field(metadata={"optional": True})
    unset_pairs: int = field(metadata={"optional": True})
    unsupported: dict[str, int] = field(metadata={"optional": True})
    zone_overlaps: int = field(metadata={"optional": True})
    zones_unjudged: int = field(metadata={"optional": True})


@dataclass(frozen=True, kw_only=True)
class ViewReviewStagesItem:
    counts: ViewReviewStagesItemCounts
    evidence: str
    limits: list[wire.DrcLimit] | None
    name: str
    reasons: list[str]
    state: str
    status: str
    summary: ViewReviewStagesItemSummary


@dataclass(frozen=True, kw_only=True)
class ViewReview:
    binding: None | ViewReviewBinding
    cards: list[ViewReviewCardsItem]
    note: str
    operation_findings: list[wire.OperationFinding]
    stages: list[ViewReviewStagesItem]


@dataclass(frozen=True, kw_only=True)
class ViewSelect:
    found: bool
    name: str


@dataclass(frozen=True, kw_only=True)
class ViewSummaryModels:
    fitted: int
    model: int
    outline: int
    unmeshed: int


@dataclass(frozen=True, kw_only=True)
class ViewSummary:
    bounds_um: list[int] = field(metadata={"optional": True})
    counts: dict[str, int] = field(
        metadata={"description": "Keys are supplied by named items, rather than fixed record fields."}
    )
    findings: dict[str, int] = field(
        metadata={
            "optional": True,
            "description": "Keys are supplied by named items, rather than fixed record fields.",
        }
    )
    items: list[str] = field(metadata={"optional": True})
    kind: str = field(metadata={"optional": True})
    layers: list[str] = field(metadata={"optional": True})
    lib: str = field(metadata={"optional": True})
    models: None | ViewSummaryModels = field(metadata={"optional": True})
    panel: bool = field(metadata={"optional": True})
    sheets: list[str] = field(metadata={"optional": True})
    unfilled: int = field(metadata={"optional": True})


@dataclass(frozen=True, kw_only=True)
class ViewVariant:
    fitted: int
    name: str
    not_fitted: int


@dataclass(frozen=True, kw_only=True)
class ViewProposals:
    document: str | None
    proposals: int
    candidates: int
    evidence: str | None
    native_check: NativeCheck = field(metadata={"optional": True})
    sha256: str = field(metadata={"optional": True})


@dataclass(frozen=True, kw_only=True)
class ViewRoleStates:
    confirmed: int
    declared: int
    inferred: int


@dataclass(frozen=True, kw_only=True)
class ViewFindingCounts:
    error: int
    warning: int
    info: int


@dataclass(frozen=True, kw_only=True)
class ViewRoles:
    document: str | None
    roles: ViewRoleStates
    findings: ViewFindingCounts
    groups: int
    evidence: str | None


@dataclass(frozen=True, kw_only=True)
class ViewRunCounts:
    done: int = field(metadata={"optional": True})
    failed: int = field(metadata={"optional": True})
    cancelled: int = field(metadata={"optional": True})
    timeout: int = field(metadata={"optional": True})


@dataclass(frozen=True, kw_only=True)
class ViewWrite:
    id: str
    action: str
    files: list[str]


@dataclass(frozen=True, kw_only=True)
class ViewServe(wire.ServerSummary):
    marks_written: int = field(metadata={"optional": True})
    runs: ViewRunCounts = field(metadata={"optional": True})
    writes: list[ViewWrite] = field(metadata={"optional": True})


@dataclass(frozen=True, kw_only=True)
class ViewResult(ProtocolResult):
    proposals: ViewProposals = field(metadata={"optional": True})
    roles: ViewRoles = field(metadata={"optional": True})
    serve: ViewServe = field(metadata={"optional": True})
    cache: ViewCache = field(metadata={"optional": True})
    check: ViewCheck = field(metadata={"optional": True})
    compare: ViewCompare = field(metadata={"optional": True})
    document: str = field(metadata={"optional": True})
    export: ViewExport = field(metadata={"optional": True})
    marks: list[ViewMarksItem] = field(metadata={"optional": True})
    notes: list[str] = field(metadata={"optional": True})
    project: ViewProject = field(metadata={"optional": True})
    review: ViewReview = field(metadata={"optional": True})
    select: ViewSelect = field(metadata={"optional": True})
    summary: None | ViewSummary = field(metadata={"optional": True})
    theme: None | str = field(metadata={"optional": True})
    variant: ViewVariant = field(metadata={"optional": True})
