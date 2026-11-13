# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Wire records for edits results; producers retain their existing payloads."""

from __future__ import annotations

from dataclasses import dataclass, field

from fenolite.cli.results import common as wire
from fenolite.cli.results import route_proposals as proposal_wire
from fenolite.cli.results.common import (
    ProtocolResult,
)
from fenolite.placement import constrained as constrained_rows
from fenolite.placement.optimization_contract import PlacementOptimization
from fenolite.safety.refs import Ref


@dataclass(frozen=True, kw_only=True)
class PlaceGroupCopper:
    items: int
    zones: int


@dataclass(frozen=True, kw_only=True)
class PlaceGroupCopperCheck:
    after: int
    before: int
    new: int


@dataclass(frozen=True, kw_only=True)
class PlaceGroupSearchAbout:
    x: int
    y: int


@dataclass(frozen=True, kw_only=True)
class PlaceGroupSearchPosesItem:
    demand: int
    dx: int
    dy: int
    rotation: int


@dataclass(frozen=True, kw_only=True)
class PlaceGroupSearch:
    about: PlaceGroupSearchAbout
    current: int
    nets: list[str]
    pitch: int
    poses: list[PlaceGroupSearchPosesItem]
    tried: int
    within: int


@dataclass(frozen=True, kw_only=True)
class PlaceGroupTransform:
    rotation: int
    x: int
    y: int


@dataclass(frozen=True, kw_only=True)
class PlaceGroup:
    copper: PlaceGroupCopper
    copper_check: None | PlaceGroupCopperCheck
    kind: str
    refs: list[str]
    residual: int | None
    search: None | PlaceGroupSearch
    transform: None | PlaceGroupTransform


@dataclass(frozen=True, kw_only=True)
class PlaceMeasuresChange:
    hpwl: int
    ratsnest: int


@dataclass(frozen=True, kw_only=True)
class PlaceMeasuresCongestionBusiestItem:
    tracks: int
    x: int
    y: int


@dataclass(frozen=True, kw_only=True)
class PlaceMeasuresCongestion:
    busiest: list[PlaceMeasuresCongestionBusiestItem]
    cell: int
    layers_needed: None | dict[str, int] = field(
        metadata={"description": "Keys are supplied by named items, rather than fixed record fields."}
    )
    pitch: int | None
    tracks_per_layer: int | None


@dataclass(frozen=True, kw_only=True)
class PlaceMeasuresLeftOut:
    off_board: int
    one_pad_nets: int
    zone_nets: int


@dataclass(frozen=True, kw_only=True)
class PlaceMeasuresLongestItem:
    hpwl: int
    net: str
    pads: int
    ratsnest: int


@dataclass(frozen=True, kw_only=True)
class PlaceMeasures:
    change: PlaceMeasuresChange
    congestion: PlaceMeasuresCongestion
    hpwl: int
    left_out: PlaceMeasuresLeftOut
    longest: list[PlaceMeasuresLongestItem]
    nets: int
    ratsnest: int


@dataclass(frozen=True, kw_only=True)
class PlaceMovedItemFrom:
    rotation: int
    side: str
    x: int
    y: int


@dataclass(frozen=True, kw_only=True)
class PlaceMovedItemTo:
    rotation: int
    side: str
    x: int
    y: int


@dataclass(frozen=True, kw_only=True)
class PlaceMovedItem:
    from_: PlaceMovedItemFrom = field(metadata={"name": "from"})
    path: str
    ref: str
    to: PlaceMovedItemTo


@dataclass(frozen=True, kw_only=True)
class PlacePlacementAssessment:
    findings: list[str]
    missing_inputs: list[str]
    state: str


@dataclass(frozen=True, kw_only=True)
class PlacePlacementConstraints:
    edge_clearance: int = field(metadata={"optional": True})
    gap: int = field(metadata={"optional": True})
    max_candidates: int = field(metadata={"optional": True})
    pitch: int = field(metadata={"optional": True})
    source_hashes: list[list[str]] = field(metadata={"optional": True})


@dataclass(frozen=True, kw_only=True)
class PlacePlacementPositionsItemItem:
    x: int
    y: int


@dataclass(frozen=True, kw_only=True)
class PlacePlacement:
    assessment: PlacePlacementAssessment
    candidate_counts: dict[str, int] = field(
        metadata={"description": "Keys are supplied by named items, rather than fixed record fields."}
    )
    constraints: PlacePlacementConstraints
    hard_findings: list[str]
    intrinsic: list[wire.PlacementFinding]
    missing_inputs: list[str]
    objective_metric: str
    objectives: list[constrained_rows.ObjectiveMeasure]
    positions: list[list[PlacePlacementPositionsItemItem | str]]
    request_sha256: str
    selected: list[str]
    source_sha256: str
    unplaced: list[constrained_rows.Unplaced]


@dataclass(frozen=True, kw_only=True)
class PlacePreview:
    faces: list[str]
    source: str
    source_sha256: str


@dataclass(frozen=True, kw_only=True)
class PlaceRegionsBarriersItem:
    ref: str
    sides: list[str]
    status: str


@dataclass(frozen=True, kw_only=True)
class PlaceRegionsCrossingsItem:
    between: list[str]
    nets: list[str]
    open: int


@dataclass(frozen=True, kw_only=True)
class PlaceRegionsRowsItemBox:
    x0: int
    x1: int
    y0: int
    y1: int


@dataclass(frozen=True, kw_only=True)
class PlaceRegionsRowsItem:
    area: int
    box: PlaceRegionsRowsItemBox
    fill_permille: int
    name: str
    nets: list[str]
    parts: list[str]
    placed: list[str]
    unplaced: list[str]
    used: int


@dataclass(frozen=True, kw_only=True)
class PlaceRegions:
    axis: None | str
    barriers: list[PlaceRegionsBarriersItem]
    crossings: list[PlaceRegionsCrossingsItem]
    rows: list[PlaceRegionsRowsItem]
    source: str
    unassigned: list[str]


@dataclass(frozen=True, kw_only=True)
class PlaceReuseCopperDroppedItem:
    detail: str
    item: str
    kind: str
    net: str
    reason: str


@dataclass(frozen=True, kw_only=True)
class PlaceReuseCopperItemsItem:
    detail: str
    kind: str
    net: str
    source: str
    uuid: str


@dataclass(frozen=True, kw_only=True)
class PlaceReuseCopper:
    copied: int
    counts: dict[str, int] = field(
        metadata={"description": "Keys are supplied by named items, rather than fixed record fields."}
    )
    dropped: list[PlaceReuseCopperDroppedItem]
    items: list[PlaceReuseCopperItemsItem]
    passes: int


@dataclass(frozen=True, kw_only=True)
class PlaceReuseCopperCheck:
    before: int
    new: int
    placed: int


@dataclass(frozen=True, kw_only=True)
class PlaceReuseDrc:
    after: int
    before: int
    new: list[str]
    tool_version: str


@dataclass(frozen=True, kw_only=True)
class PlaceReusePartsItemFrom:
    rotation: int
    side: str
    x: int
    y: int


@dataclass(frozen=True, kw_only=True)
class PlaceReusePartsItemTo:
    rotation: int
    side: str
    x: int
    y: int


@dataclass(frozen=True, kw_only=True)
class PlaceReusePartsItem:
    by_net: int
    from_: PlaceReusePartsItemFrom = field(metadata={"name": "from"})
    matched: int
    mirror_suspected: bool
    moved: bool
    placed: bool
    ref: str
    reference: str
    residual: int
    side_changed: bool
    to: None | PlaceReusePartsItemTo
    within: int


@dataclass(frozen=True, kw_only=True)
class PlaceReuseTransform:
    mirror: bool
    rotation: int
    x: int
    y: int


@dataclass(frozen=True, kw_only=True)
class PlaceReuse:
    anchor: str
    copper: None | PlaceReuseCopper
    copper_check: PlaceReuseCopperCheck
    drc: None | PlaceReuseDrc
    flipped: bool
    parts: list[PlaceReusePartsItem]
    reference: str
    tolerance: int
    transform: PlaceReuseTransform


@dataclass(frozen=True, kw_only=True)
class PlaceRulesValue:
    failed: int
    judged: int
    skipped: int = field(metadata={"optional": True})
    unknown: int = field(metadata={"optional": True})


@dataclass(frozen=True, kw_only=True)
class PlaceResult(ProtocolResult):
    board: str = field(metadata={"optional": True})
    group: PlaceGroup = field(metadata={"optional": True})
    legality: dict[str, int] = field(
        metadata={
            "optional": True,
            "description": "Keys are supplied by named items, rather than fixed record fields.",
        }
    )
    measures: PlaceMeasures = field(metadata={"optional": True})
    moved: list[PlaceMovedItem] = field(metadata={"optional": True})
    optimization: PlacementOptimization = field(metadata={"optional": True})
    placement: PlacePlacement = field(metadata={"optional": True})
    preview: None | PlacePreview = field(metadata={"optional": True})
    regions: PlaceRegions = field(metadata={"optional": True})
    reuse: PlaceReuse = field(metadata={"optional": True})
    rules: dict[str, PlaceRulesValue] = field(
        metadata={
            "optional": True,
            "description": "Keys are supplied by named items, rather than fixed record fields.",
        }
    )
    strategy: str = field(metadata={"optional": True})
    unplaced: list[str] = field(metadata={"optional": True})


@dataclass(frozen=True, kw_only=True)
class RouteBudget:
    exhausted: bool
    seconds: int | None | float
    spent: float


@dataclass(frozen=True, kw_only=True)
class RouteConnections:
    after: int
    before: int


@dataclass(frozen=True, kw_only=True)
class RouteEscapeItem:
    kind: str
    nets: list[str]
    pitch: int
    ref: str


@dataclass(frozen=True, kw_only=True)
class RouteOpenItemConnectionsItemAPosition:
    x: int
    y: int


@dataclass(frozen=True, kw_only=True)
class RouteOpenItemConnectionsItemA:
    kind: str
    layers: list[str]
    position: RouteOpenItemConnectionsItemAPosition
    where: str


@dataclass(frozen=True, kw_only=True)
class RouteOpenItemConnectionsItemBPosition:
    x: int
    y: int


@dataclass(frozen=True, kw_only=True)
class RouteOpenItemConnectionsItemB:
    kind: str
    layers: list[str]
    position: RouteOpenItemConnectionsItemBPosition
    where: str


@dataclass(frozen=True, kw_only=True)
class RouteOpenItemConnectionsItem:
    a: RouteOpenItemConnectionsItemA
    b: RouteOpenItemConnectionsItemB
    length: int


@dataclass(frozen=True, kw_only=True)
class RouteOpenItem:
    connections: list[RouteOpenItemConnectionsItem]
    islands: int
    net: str


@dataclass(frozen=True, kw_only=True)
class RoutePairsItem:
    gap: int
    name: str
    negative: str
    positive: str
    routed: bool
    width: int


@dataclass(frozen=True, kw_only=True)
class RoutePlaneFanout:
    failed: list[str]
    joined: int
    nets: list[str]
    pads: int
    tracks: int
    vias: int


@dataclass(frozen=True, kw_only=True)
class RouteResumed:
    nets: int
    runs: int


@dataclass(frozen=True, kw_only=True)
class RouteRipKept:
    locked: int
    script: int


@dataclass(frozen=True, kw_only=True)
class RouteRolesItemConnectionsItem:
    a: str
    b: str
    form: None | str
    key: str
    layer: None | str
    length: int
    net: str
    vias: int


@dataclass(frozen=True, kw_only=True)
class RouteRolesItemFindingsAfterItem:
    code: str
    measure: int | None
    severity: str


@dataclass(frozen=True, kw_only=True)
class RouteRolesItemFindingsBeforeItem:
    code: str
    measure: int | None
    severity: str


@dataclass(frozen=True, kw_only=True)
class RouteRolesItemProposal:
    command: str
    kind: str
    region: str
    text: str


@dataclass(frozen=True, kw_only=True)
class RouteRolesItem:
    connections: list[RouteRolesItemConnectionsItem]
    copper: list[str]
    corridors: list[str]
    findings_after: list[RouteRolesItemFindingsAfterItem]
    findings_before: list[RouteRolesItemFindingsBeforeItem]
    group: str
    kind: str
    proposal: None | RouteRolesItemProposal
    reason: None | str
    status: str
    propose: str | None = field(metadata={"optional": True})


@dataclass(frozen=True, kw_only=True)
class RouteRunsItem:
    nets: int
    outcome: str
    seconds: float
    tier: int


@dataclass(frozen=True, kw_only=True)
class RouteResult(ProtocolResult):
    native_check: proposal_wire.NativeCheck = field(metadata={"optional": True})
    board: str = field(metadata={"optional": True})
    budget: RouteBudget = field(metadata={"optional": True})
    connections: RouteConnections = field(metadata={"optional": True})
    escape: list[RouteEscapeItem] = field(metadata={"optional": True})
    fills_stale: bool = field(metadata={"optional": True})
    gate: wire.GateSummary | None = field(metadata={"optional": True})
    log: list[str] = field(metadata={"optional": True})
    not_attempted: list[str] = field(metadata={"optional": True})
    open: list[RouteOpenItem] | proposal_wire.ProposalOpen = field(metadata={"optional": True})
    pairs: list[RoutePairsItem] = field(metadata={"optional": True})
    plane_fanout: None | RoutePlaneFanout = field(metadata={"optional": True})
    plane_layers: list[str] = field(metadata={"optional": True})
    resumed: None | RouteResumed = field(metadata={"optional": True})
    rip_kept: RouteRipKept = field(metadata={"optional": True})
    ripped: int = field(metadata={"optional": True})
    roles: list[RouteRolesItem] = field(metadata={"optional": True})
    routed: list[str] = field(metadata={"optional": True})
    router: str = field(metadata={"optional": True})
    runs: list[RouteRunsItem] = field(metadata={"optional": True})
    selected: list[str] = field(metadata={"optional": True})
    tool_version: None | str = field(metadata={"optional": True})
    tracks: int = field(metadata={"optional": True})
    unrouted: list[str] = field(metadata={"optional": True})
    vias: int = field(metadata={"optional": True})
    mode: str = field(metadata={"optional": True})
    order: str = field(metadata={"optional": True})
    proposals: list[proposal_wire.Proposal] = field(metadata={"optional": True})
    rejected: list[proposal_wire.ProposalRejected] = field(metadata={"optional": True})
    locked: list[proposal_wire.ProposalLocked] = field(metadata={"optional": True})
    next: list[str] = field(metadata={"optional": True})
    accepted: list[proposal_wire.ProposalAccepted] = field(metadata={"optional": True})
    decision: str | None = field(metadata={"optional": True})
    record: str = field(metadata={"optional": True})
    replayed: list[str] = field(metadata={"optional": True})
    stale: list[proposal_wire.ProposalStale] = field(metadata={"optional": True})
    forgotten: list[str] = field(metadata={"optional": True})
    removed: int = field(metadata={"optional": True})
    drc_unattributed: list[wire.GateFinding] = field(metadata={"optional": True})
    bundles: list[proposal_wire.ProposalBundle] | list[str] = field(metadata={"optional": True})
    controls: proposal_wire.ProposalControls = field(metadata={"optional": True})
    role_fields: proposal_wire.ProposalRoleFields = field(metadata={"optional": True})
    external: proposal_wire.ProposalExternal = field(metadata={"optional": True})
    completion: proposal_wire.ProposalCompletion = field(metadata={"optional": True})


@dataclass(frozen=True, kw_only=True)
class FillZonesItem:
    filled: bool
    fills: int
    id: str
    islands: int
    layers: list[str]
    name: str


@dataclass(frozen=True, kw_only=True)
class FillResult(ProtocolResult):
    board: str = field(metadata={"optional": True})
    changed: bool = field(metadata={"optional": True})
    target: str = field(metadata={"optional": True})
    tool_version: None | str = field(metadata={"optional": True})
    tool_writes: list[str] = field(metadata={"optional": True})
    zones: list[FillZonesItem] = field(metadata={"optional": True})


@dataclass(frozen=True, kw_only=True)
class RestoreResult(ProtocolResult):
    changed: list[str] = field(metadata={"optional": True})
    id: str = field(metadata={"optional": True})
    kept: list[str] = field(metadata={"optional": True})
    restored: list[str] = field(metadata={"optional": True})


@dataclass(frozen=True, kw_only=True)
class FmtResult(ProtocolResult):
    first_difference: int | None = field(metadata={"optional": True})
    formatted: bool = field(metadata={"optional": True})
    kind: str = field(metadata={"optional": True})
    lines: int = field(metadata={"optional": True})
    schema: str = field(metadata={"optional": True})


@dataclass(frozen=True, kw_only=True)
class SnapshotFilesItem:
    path: str
    sha256: str
    size: int


@dataclass(frozen=True, kw_only=True)
class SnapshotResult(ProtocolResult):
    count: int = field(metadata={"optional": True})
    files: list[SnapshotFilesItem] = field(metadata={"optional": True})
    out: str = field(metadata={"optional": True})
    retries: int = field(metadata={"optional": True})
    source: str = field(metadata={"optional": True})


@dataclass(frozen=True, kw_only=True)
class PublishResult(ProtocolResult):
    added: list[str] = field(metadata={"optional": True})
    changed: list[str] = field(metadata={"optional": True})
    replaced: list[str] = field(metadata={"optional": True})
    source: str = field(metadata={"optional": True})
    to: str = field(metadata={"optional": True})
    unchanged: int = field(metadata={"optional": True})


@dataclass(frozen=True, kw_only=True)
class RefsRepoint:
    new: str
    old: str


@dataclass(frozen=True, kw_only=True)
class RefsResult(ProtocolResult):
    count: int = field(metadata={"optional": True})
    refs: list[Ref] = field(metadata={"optional": True})
    repoint: RefsRepoint = field(metadata={"optional": True})
    rewritten: list[str] = field(metadata={"optional": True})
    root: str = field(metadata={"optional": True})


@dataclass(frozen=True, kw_only=True)
class TidyCompareCounts:
    acute: int
    jogs: int
    joints_45: int
    joints_90: int
    other: int
    vias: int


@dataclass(frozen=True, kw_only=True)
class TidyCompareRowsItemWidthsItem:
    length: int
    width: int


@dataclass(frozen=True, kw_only=True)
class TidyCompareRowsItem:
    acute: int
    jogs: int
    joints_45: int
    joints_90: int
    layer: str
    netclass: str
    other: int
    widths: list[TidyCompareRowsItemWidthsItem]


@dataclass(frozen=True, kw_only=True)
class TidyCompare:
    board: str
    counts: TidyCompareCounts
    rows: list[TidyCompareRowsItem]
    vias: list[wire.ViaCount]


@dataclass(frozen=True, kw_only=True)
class TidyCopperCheck:
    after: int
    before: int
    new: int


@dataclass(frozen=True, kw_only=True)
class TidyDrc:
    after: int
    before: int
    new: list[str]
    tool_version: str


@dataclass(frozen=True, kw_only=True)
class TidyEditsItemAt:
    x: int
    y: int


@dataclass(frozen=True, kw_only=True)
class TidyEditsItem:
    added: list[str]
    at: TidyEditsItemAt
    layer: None | str
    net: str
    reason: str
    removed: list[str]
    replaced: list[str]
    step: str


@dataclass(frozen=True, kw_only=True)
class TidyReportCounts:
    acute: int
    jogs: int
    joints_45: int
    joints_90: int
    other: int
    vias: int


@dataclass(frozen=True, kw_only=True)
class TidyReportRowsItemWidthsItem:
    length: int
    width: int


@dataclass(frozen=True, kw_only=True)
class TidyReportRowsItem:
    acute: int
    jogs: int
    joints_45: int
    joints_90: int
    layer: str
    netclass: str
    other: int
    widths: list[TidyReportRowsItemWidthsItem]


@dataclass(frozen=True, kw_only=True)
class TidyReportViasItem:
    count: int
    netclass: str


@dataclass(frozen=True, kw_only=True)
class TidyReport:
    counts: TidyReportCounts
    rows: list[TidyReportRowsItem]
    vias: list[TidyReportViasItem]


@dataclass(frozen=True, kw_only=True)
class TidyStyleAfter:
    acute: int
    jogs: int
    joints_45: int
    joints_90: int
    other: int
    vias: int


@dataclass(frozen=True, kw_only=True)
class TidyStyleBefore:
    acute: int
    jogs: int
    joints_45: int
    joints_90: int
    other: int
    vias: int


@dataclass(frozen=True, kw_only=True)
class TidyStyle:
    after: TidyStyleAfter
    before: TidyStyleBefore


@dataclass(frozen=True, kw_only=True)
class TidyResult(ProtocolResult):
    added: int = field(metadata={"optional": True})
    board: str = field(metadata={"optional": True})
    changed: bool = field(metadata={"optional": True})
    compare: None | TidyCompare = field(metadata={"optional": True})
    copper_check: TidyCopperCheck = field(metadata={"optional": True})
    counts: dict[str, int] = field(
        metadata={
            "optional": True,
            "description": "Keys are supplied by named items, rather than fixed record fields.",
        }
    )
    drc: None | TidyDrc = field(metadata={"optional": True})
    edits: list[TidyEditsItem] = field(metadata={"optional": True})
    fills_stale: bool = field(metadata={"optional": True})
    gate: wire.GateSummary | None = field(metadata={"optional": True})
    nets: int = field(metadata={"optional": True})
    removed: int = field(metadata={"optional": True})
    report: TidyReport = field(metadata={"optional": True})
    steps: list[str] = field(metadata={"optional": True})
    style: TidyStyle = field(metadata={"optional": True})
    target: str = field(metadata={"optional": True})


@dataclass(frozen=True, kw_only=True)
class SilkMeasure:
    cached: int
    source: str
    texts: int


@dataclass(frozen=True, kw_only=True)
class SilkPlacementsItem:
    angle: int
    height: int
    ref: str
    side: str
    status: str
    stroke: int
    where: str
    x: int
    y: int


@dataclass(frozen=True, kw_only=True)
class SilkSettings:
    angles: list[int]
    clearance: int
    gap: int
    keep: bool
    min_height: int
    min_stroke: int
    sizes: list[int] | None
    model: str
    reach: int
    over_body: bool
    min_size: int | None
    size_step: int
    mask_clearance: int


@dataclass(frozen=True, kw_only=True)
class SilkResult(ProtocolResult):
    aligned: list[list[str]] = field(metadata={"optional": True})
    board: str = field(metadata={"optional": True})
    changed: bool = field(metadata={"optional": True})
    clip: wire.SilkClip | None = field(metadata={"optional": True})
    drc: wire.DrcDifference | None = field(metadata={"optional": True})
    kept: int = field(metadata={"optional": True})
    library: wire.SilkLibrary | None = field(metadata={"optional": True})
    measure: SilkMeasure = field(metadata={"optional": True})
    placed: int = field(metadata={"optional": True})
    placements: list[SilkPlacementsItem] = field(metadata={"optional": True})
    settings: SilkSettings = field(metadata={"optional": True})
    target: str = field(metadata={"optional": True})
    unplaced: dict[str, int] = field(
        metadata={
            "optional": True,
            "description": "Unplaced designators counted by the kind of what blocked them (change c0493).",
        }
    )


@dataclass(frozen=True, kw_only=True)
class CopperBeforeItem:
    code: str
    severity: str
    where: str


@dataclass(frozen=True, kw_only=True)
class CopperClearedItem:
    code: str
    severity: str
    where: str


@dataclass(frozen=True, kw_only=True)
class CopperCorridorsItem:
    group: str
    key: str
    kind: str
    layer: str
    net: str
    origin: str
    polygons: list[list[list[int]]]
    width: int


@dataclass(frozen=True, kw_only=True)
class CopperNetsItem:
    kind: str
    layers: list[str]
    max_width: int | None
    method: None | str
    net: str
    skipped: None | str
    vias: int
    width: int | None
    zones: list[str]


@dataclass(frozen=True, kw_only=True)
class CopperResult(ProtocolResult):
    after: list[wire.RoleFinding] = field(metadata={"optional": True})
    before: list[CopperBeforeItem] = field(metadata={"optional": True})
    board: str = field(metadata={"optional": True})
    changed: bool = field(metadata={"optional": True})
    cleared: list[CopperClearedItem] = field(metadata={"optional": True})
    corridors: list[CopperCorridorsItem] = field(metadata={"optional": True})
    gate: wire.GateSummary | None = field(metadata={"optional": True})
    kept: list[str] = field(metadata={"optional": True})
    nets: list[CopperNetsItem] = field(metadata={"optional": True})
    next: list[str] = field(metadata={"optional": True})
    records: int = field(metadata={"optional": True})
    replaced: int = field(metadata={"optional": True})
    rules: list[str] = field(metadata={"optional": True})
    vias: int = field(metadata={"optional": True})
