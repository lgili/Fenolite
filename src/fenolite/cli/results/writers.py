# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Wire records for writers results; producers retain their existing payloads."""

from __future__ import annotations

from dataclasses import dataclass, field

from fenolite.cli.results import common as wire
from fenolite.cli.results.common import (
    PinChoice,
    ProtocolResult,
)
from fenolite.core.errors import Issue
from fenolite.core.evidence import Evidence


@dataclass(frozen=True, kw_only=True)
class BuildBoardItems:
    dimensions: int
    graphics: int
    rule_areas: int
    texts: int
    images: int = field(metadata={"optional": True})


@dataclass(frozen=True, kw_only=True)
class BuildDraftsmanSpec:
    path: str
    sha256: str


@dataclass(frozen=True, kw_only=True)
class BuildDraftsmanSheet:
    title: str
    paper: str
    objects: list[str]


@dataclass(frozen=True, kw_only=True)
class BuildDraftsman:
    file: str
    route: str
    sheets: list[BuildDraftsmanSheet]
    not_lowered: list[str]
    spec: BuildDraftsmanSpec | None


@dataclass(frozen=True, kw_only=True)
class BuildCopperLocked:
    arcs: int
    tracks: int
    vias: int


@dataclass(frozen=True, kw_only=True)
class BuildCopper:
    arcs: int
    duplicates: int = field(metadata={"optional": True})
    from_: None | str = field(metadata={"optional": True, "name": "from"})
    intents: int = field(metadata={"optional": True})
    layers: int = field(metadata={"optional": True})
    locked: BuildCopperLocked = field(metadata={"optional": True})
    net_classes: int = field(metadata={"optional": True})
    placements_from_board: int = field(metadata={"optional": True})
    planes: dict[str, str] = field(
        metadata={
            "optional": True,
            "description": "Keys are supplied by named items, rather than fixed record fields.",
        }
    )
    regenerated: int = field(metadata={"optional": True})
    source: str = field(metadata={"optional": True})
    stale: int = field(metadata={"optional": True})
    tracks: int
    vias: int
    zones: int = field(metadata={"optional": True})


@dataclass(frozen=True, kw_only=True)
class BuildCopperCheckRules:
    min_clearance: int | None
    opaque_clearance_rules: int
    unread: list[str]


@dataclass(frozen=True, kw_only=True)
class BuildCopperCheck:
    clearance: int = field(metadata={"optional": True})
    edge_clearance: int = field(metadata={"optional": True})
    evidence: Evidence = field(metadata={"optional": True})
    hole_clearance: int = field(metadata={"optional": True})
    mode: str
    mode_source: str
    ran: bool
    rules: BuildCopperCheckRules = field(metadata={"optional": True})
    shorts: int = field(metadata={"optional": True})
    unpoured: int = field(metadata={"optional": True})
    waivers: wire.WaiverSummary = field(metadata={"optional": True})


@dataclass(frozen=True, kw_only=True)
class BuildCopperInput:
    format_version: str
    kind: str
    path: str
    sha256: str


@dataclass(frozen=True, kw_only=True)
class BuildDeviceFilesItem:
    path: str
    sha256: str


@dataclass(frozen=True, kw_only=True)
class BuildDevicesItemItem:
    id: str
    kind: str
    version: str


@dataclass(frozen=True, kw_only=True)
class BuildDevicesItem:
    edited: bool
    evidence: str
    id: str
    item: BuildDevicesItemItem = field(metadata={"optional": True})
    origin: str
    parts: list[str]
    sha256: str


@dataclass(frozen=True, kw_only=True)
class BuildGeneratorsItemParts:
    bot: str = field(metadata={"optional": True})
    c: str = field(metadata={"optional": True})
    r: str = field(metadata={"optional": True})
    scl: str = field(metadata={"optional": True})
    sda: str = field(metadata={"optional": True})
    top: str = field(metadata={"optional": True})


@dataclass(frozen=True, kw_only=True)
class BuildGeneratorsItem:
    achieved: str = field(metadata={"optional": True})
    generator: str
    group: str
    message: str
    ok: bool
    parts: BuildGeneratorsItemParts


@dataclass(frozen=True, kw_only=True)
class BuildLibraryItemsValue:
    id: str
    kind: str
    version: str


@dataclass(frozen=True, kw_only=True)
class BuildLockChangesItem:
    after: None | str
    before: None | str
    key: str
    reason: str
    section: str


@dataclass(frozen=True, kw_only=True)
class BuildLock:
    changes: list[BuildLockChangesItem]
    exists: bool
    file: str
    frozen: bool
    written: bool


@dataclass(frozen=True, kw_only=True)
class BuildNativeTemplate:
    evidence: str
    file: str
    pages: list[str]
    sha256: str
    source: str


@dataclass(frozen=True, kw_only=True)
class BuildOutjobGerberLayersItem:
    id: int
    name: str


@dataclass(frozen=True, kw_only=True)
class BuildOutjobGerberOutline:
    plotted: bool
    reason: str


@dataclass(frozen=True, kw_only=True)
class BuildOutjobGerber:
    decimals: int
    layers: list[BuildOutjobGerberLayersItem]
    outline: BuildOutjobGerberOutline
    unit: str


@dataclass(frozen=True, kw_only=True)
class BuildOutjobMediaItem:
    name: str
    type: str


@dataclass(frozen=True, kw_only=True)
class BuildOutjobOutputsItem:
    category: str
    document: str
    enabled: bool
    kind: str
    medium: str
    name: str
    type: str


@dataclass(frozen=True, kw_only=True)
class BuildOutjob:
    defaults: list[str]
    file: str
    gerber: BuildOutjobGerber
    media: list[BuildOutjobMediaItem]
    outputs: list[BuildOutjobOutputsItem]
    preset: wire.PresetReference | None


@dataclass(frozen=True, kw_only=True)
class BuildPcbPour:
    evidence: None | str
    hypotheses: list[str]
    mode: str
    poured: int
    unpoured: dict[str, int]


@dataclass(frozen=True, kw_only=True)
class BuildPcb:
    bodies: str
    not_lowered: dict[str, int] = field(
        metadata={"description": "Keys are supplied by named items, rather than fixed record fields."}
    )
    pour: BuildPcbPour
    written: dict[str, int] = field(
        metadata={"description": "Keys are supplied by named items, rather than fixed record fields."}
    )


@dataclass(frozen=True, kw_only=True)
class BuildPicksItem:
    before: str | None
    catalog: None | str
    device: None | str
    evidence: None | str
    path: str
    query: str
    row: None | str
    state: str


@dataclass(frozen=True, kw_only=True)
class BuildPlacementBlocksItemLayout:
    path: str
    sha256: str
    status: str


@dataclass(frozen=True, kw_only=True)
class BuildPlacementBlocksItem:
    at: list[int]
    layout: BuildPlacementBlocksItemLayout | str
    path: str
    rotation: int
    side: str = field(metadata={"optional": True})
    source: str
    staged: bool


@dataclass(frozen=True, kw_only=True)
class BuildPlacementRelativeItemRefsItem:
    box: list[int]
    center: list[int]
    ref: str


@dataclass(frozen=True, kw_only=True)
class BuildPlacementRelativeItem:
    at: list[int]
    frame: str
    path: str
    refs: list[BuildPlacementRelativeItemRefsItem]
    request: str
    rotation: int
    side: str


@dataclass(frozen=True, kw_only=True)
class BuildPlacementRulesHeight:
    failed: int
    judged: int
    unknown: int


@dataclass(frozen=True, kw_only=True)
class BuildPlacementRulesNear:
    failed: int
    judged: int
    skipped: int


@dataclass(frozen=True, kw_only=True)
class BuildPlacementRules:
    height: BuildPlacementRulesHeight = field(metadata={"optional": True})
    near: BuildPlacementRulesNear


@dataclass(frozen=True, kw_only=True)
class BuildPlacement:
    blocks: list[BuildPlacementBlocksItem] = field(metadata={"optional": True})
    counts: dict[str, int] = field(
        metadata={"description": "Keys are supplied by named items, rather than fixed record fields."}
    )
    digest: str = field(metadata={"optional": True})
    ran: bool
    relative: list[BuildPlacementRelativeItem] = field(metadata={"optional": True})
    rules: BuildPlacementRules
    top: str | None = field(metadata={"optional": True})


@dataclass(frozen=True, kw_only=True)
class BuildPreservedBoardItems:
    regenerated: int
    stale: int


@dataclass(frozen=True, kw_only=True)
class BuildPreservedDropped:
    arcs: int
    tracks: int
    vias: int
    zones: int


@dataclass(frozen=True, kw_only=True)
class BuildPreservedEditsConflictsItemCad:
    board: list[int] | str = field(metadata={"optional": True})
    edits: str = field(metadata={"optional": True})


@dataclass(frozen=True, kw_only=True)
class BuildPreservedEditsConflictsItem:
    base: list[int] | str
    cad: BuildPreservedEditsConflictsItemCad
    code: list[int] | str
    key: str
    reason: str


@dataclass(frozen=True, kw_only=True)
class BuildPreservedEdits:
    code: list[str]
    conflicts: list[BuildPreservedEditsConflictsItem]
    kept: list[str]
    taken: list[str]
    unrecorded: list[str]


@dataclass(frozen=True, kw_only=True)
class BuildPreservedFields:
    carried: list[str]
    forced: list[str]
    kept: list[str]


@dataclass(frozen=True, kw_only=True)
class BuildPreservedFills:
    dropped: int
    kept: int


@dataclass(frozen=True, kw_only=True)
class BuildPreservedNativeFillCache:
    """Native ordinary fill caches carried over from a verified KiCad import (c0384): the source's bytes,
    never Fenolite-computed copper, never a Fenolite fill in any proof or level."""

    origin: str = field(metadata={"enum": ["native-carry-over"]})
    fenolite_computed: bool = field(metadata={"enum": [False]})
    status: str = field(metadata={"enum": ["carried", "dropped"]})
    reason: None | str = field(
        metadata={
            "description": "Why a carrier was dropped: carrier-unreadable, target-changed, board-changed, "
            "project-changed or rules-changed; null when carried."
        }
    )
    zones: int
    fills: int


@dataclass(frozen=True, kw_only=True)
class BuildPreservedPadZones:
    forced: list[str]
    kept: list[str]


@dataclass(frozen=True, kw_only=True)
class BuildPreservedSource:
    file: None | str
    stale: list[str]
    unknown: list[str]
    used: list[str]


@dataclass(frozen=True, kw_only=True)
class BuildPreserved:
    added: list[str]
    aliases: dict[str, str] = field(
        metadata={"description": "Keys are supplied by named items, rather than fixed record fields."}
    )
    board: bool
    board_items: BuildPreservedBoardItems
    board_only: list[str]
    dropped: BuildPreservedDropped
    edits: BuildPreservedEdits
    fields: BuildPreservedFields
    fills: BuildPreservedFills
    kept: list[str]
    native_fill_cache: BuildPreservedNativeFillCache = field(metadata={"optional": True})
    module_aliases: dict[str, str] = field(
        metadata={"description": "Keys are supplied by named items, rather than fixed record fields."}
    )
    net_aliases: dict[str, str] = field(
        metadata={"description": "Keys are supplied by named items, rather than fixed record fields."}
    )
    orphans: list[str]
    pad_zones: BuildPreservedPadZones
    reader_infos: int
    replaced: list[str]
    source: BuildPreservedSource


@dataclass(frozen=True, kw_only=True)
class BuildRoleCopperBeforeItem:
    code: str
    severity: str
    where: str


@dataclass(frozen=True, kw_only=True)
class BuildRoleCopperClearedItem:
    code: str
    severity: str
    where: str


@dataclass(frozen=True, kw_only=True)
class BuildRoleCopperCorridorsItem:
    group: str
    key: str
    kind: str
    layer: str
    net: str
    origin: str
    polygons: list[list[list[int]]]
    width: int


@dataclass(frozen=True, kw_only=True)
class BuildRoleCopperNetsItem:
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
class BuildRoleCopper:
    after: list[wire.RoleFinding]
    before: list[BuildRoleCopperBeforeItem]
    cleared: list[BuildRoleCopperClearedItem]
    corridors: list[BuildRoleCopperCorridorsItem]
    nets: list[BuildRoleCopperNetsItem]
    records: int
    rules: list[str]
    vias: int


@dataclass(frozen=True, kw_only=True)
class BuildRulesNotLoweredItem:
    kind: str
    reason: str
    selector: str


@dataclass(frozen=True, kw_only=True)
class BuildRulesWrittenItem:
    kind: str
    rule: str
    selector: str


@dataclass(frozen=True, kw_only=True)
class BuildRules:
    not_lowered: list[BuildRulesNotLoweredItem]
    written: list[BuildRulesWrittenItem]


@dataclass(frozen=True, kw_only=True)
class BuildSchematicDrawn:
    buses: int
    file: str
    junctions: int
    labels: int
    opaque: int
    wires: int


@dataclass(frozen=True, kw_only=True)
class BuildSchematic:
    buses: int = field(metadata={"optional": True})
    directed: int = field(metadata={"optional": True})
    directions: str = field(metadata={"optional": True})
    drawn: None | BuildSchematicDrawn = field(metadata={"optional": True})
    file: str = field(metadata={"optional": True})
    files: list[str] = field(metadata={"optional": True})
    junctions: int = field(metadata={"optional": True})
    labels: int = field(metadata={"optional": True})
    layout: str = field(metadata={"optional": True})
    libraries: list[str] = field(metadata={"optional": True})
    no_connects: int = field(metadata={"optional": True})
    paper: str = field(metadata={"optional": True})
    parameters: int = field(metadata={"optional": True})
    power_flags: int = field(metadata={"optional": True})
    power_symbols: int = field(metadata={"optional": True})
    satellites: int = field(metadata={"optional": True})
    sheets: int
    source: str = field(metadata={"optional": True})
    symbols: int | str
    symbols_drawn: int = field(metadata={"optional": True})
    symbols_simplified: int = field(metadata={"optional": True})
    unconnected_pads: int = field(metadata={"optional": True})
    wires: int = field(metadata={"optional": True})


@dataclass(frozen=True, kw_only=True)
class BuildSchematicCompositionEvidence:
    level: str
    native_review: str


@dataclass(frozen=True, kw_only=True)
class BuildSchematicCompositionLimits:
    fanout: int
    grid: int
    pin_grid: int
    placement_budget: int
    text_bounds: str
    wire_budget: int


@dataclass(frozen=True, kw_only=True)
class BuildSchematicCompositionSheetsItemAttachmentsItem:
    anchor: str
    net: str
    reason: str
    unit: str


@dataclass(frozen=True, kw_only=True)
class BuildSchematicCompositionSheetsItemBlocksItem:
    bounds: list[int]
    key: str
    title: str


@dataclass(frozen=True, kw_only=True)
class BuildSchematicCompositionSheetsItemLabelledConnectionsItem:
    net: str
    pin: str
    power: bool
    unit: str


@dataclass(frozen=True, kw_only=True)
class BuildSchematicCompositionSheetsItemPlacementsItemVisibleItemBox:
    x0: int
    x1: int
    y0: int
    y1: int


@dataclass(frozen=True, kw_only=True)
class BuildSchematicCompositionSheetsItemPlacementsItemVisibleItem:
    box: BuildSchematicCompositionSheetsItemPlacementsItemVisibleItemBox
    key: str
    kind: str


@dataclass(frozen=True, kw_only=True)
class BuildSchematicCompositionSheetsItemPlacementsItem:
    block: str
    bounds: list[int]
    component: str
    origin: list[int]
    part: int
    rotation: int
    unit: str
    visible: list[BuildSchematicCompositionSheetsItemPlacementsItemVisibleItem]


@dataclass(frozen=True, kw_only=True)
class BuildSchematicCompositionSheetsItemWiresItem:
    bends: int
    crossings: int
    end: list[str]
    length: int
    net: str
    points: list[list[int]]
    start: list[str]


@dataclass(frozen=True, kw_only=True)
class BuildSchematicCompositionSheetsItem:
    attachments: list[BuildSchematicCompositionSheetsItemAttachmentsItem]
    blocks: list[BuildSchematicCompositionSheetsItemBlocksItem]
    connection_candidates: int
    flow: str
    issues: list[Issue]
    labelled_connections: list[BuildSchematicCompositionSheetsItemLabelledConnectionsItem]
    placement_candidates: int
    placements: list[BuildSchematicCompositionSheetsItemPlacementsItem]
    preview: str
    region: list[int]
    reserved: list[tuple[int, int, int, int]]
    sheet: str
    wires: list[BuildSchematicCompositionSheetsItemWiresItem]
    wrapped: bool


@dataclass(frozen=True, kw_only=True)
class BuildSchematicComposition:
    algorithm: str
    evidence: BuildSchematicCompositionEvidence
    limits: BuildSchematicCompositionLimits
    origin: str
    replayed_sheets: list[str]
    schema: str
    sheets: list[BuildSchematicCompositionSheetsItem]
    units: str


@dataclass(frozen=True, kw_only=True)
class BuildSchematicLayout:
    file: str
    formats: dict[str, str] = field(
        metadata={"description": "Keys are supplied by named items, rather than fixed record fields."}
    )


@dataclass(frozen=True, kw_only=True)
class BuildStackup:
    copper: int
    source: str
    thickness: int


@dataclass(frozen=True, kw_only=True)
class BuildResult(ProtocolResult):
    board_items: BuildBoardItems = field(metadata={"optional": True})
    components: int = field(metadata={"optional": True})
    copper: None | BuildCopper = field(metadata={"optional": True})
    copper_check: BuildCopperCheck = field(metadata={"optional": True})
    copper_input: BuildCopperInput = field(metadata={"optional": True})
    design: str = field(metadata={"optional": True})
    device_files: list[BuildDeviceFilesItem] = field(metadata={"optional": True})
    devices: list[BuildDevicesItem] = field(metadata={"optional": True})
    drawing_sheet: wire.DrawingSheetSummary | None = field(metadata={"optional": True})
    draftsman: BuildDraftsman | None = field(metadata={"optional": True})
    experimental: bool = field(metadata={"optional": True})
    files: list[str] = field(metadata={"optional": True})
    footprints: int = field(metadata={"optional": True})
    generators: list[BuildGeneratorsItem] = field(metadata={"optional": True})
    harnesses: int = field(metadata={"optional": True})
    kept: list[str] = field(metadata={"optional": True})
    labels: int = field(metadata={"optional": True})
    libraries: list[str] | dict[str, str] = field(
        metadata={
            "optional": True,
            "description": "Keys are supplied by named items, rather than fixed record fields.",
        }
    )
    library_items: dict[str, BuildLibraryItemsValue] = field(
        metadata={
            "optional": True,
            "description": "Keys are supplied by named items, rather than fixed record fields.",
        }
    )
    lock: None | BuildLock = field(metadata={"optional": True})
    native_template: BuildNativeTemplate = field(metadata={"optional": True})
    nets: int = field(metadata={"optional": True})
    no_connects: int = field(metadata={"optional": True})
    out: str = field(metadata={"optional": True})
    outjob: None | BuildOutjob = field(metadata={"optional": True})
    pcb: None | BuildPcb = field(metadata={"optional": True})
    pcb_document: None | str = field(metadata={"optional": True})
    picks: list[BuildPicksItem] = field(metadata={"optional": True})
    pins: list[PinChoice] = field(metadata={"optional": True})
    placed: list[str] = field(metadata={"optional": True})
    placement: BuildPlacement = field(metadata={"optional": True})
    ports: int = field(metadata={"optional": True})
    power_ports: int = field(metadata={"optional": True})
    preserved: BuildPreserved = field(metadata={"optional": True})
    role_copper: BuildRoleCopper = field(metadata={"optional": True})
    rules: None | BuildRules = field(metadata={"optional": True})
    schematic: None | BuildSchematic = field(metadata={"optional": True})
    schematic_composition: BuildSchematicComposition = field(metadata={"optional": True})
    schematic_format: str = field(metadata={"optional": True})
    schematic_layout: BuildSchematicLayout = field(metadata={"optional": True})
    script_output: str = field(metadata={"optional": True})
    sheet: None | str = field(metadata={"optional": True})
    sheet_entries: int = field(metadata={"optional": True})
    sheet_mode: str = field(metadata={"optional": True})
    sheets: list[str] = field(metadata={"optional": True})
    stackup: None | BuildStackup = field(metadata={"optional": True})
    staged: list[str] = field(metadata={"optional": True})
    symbols: int = field(metadata={"optional": True})
    target: int | str = field(metadata={"optional": True})
    vendored: list[str] = field(metadata={"optional": True})


@dataclass(frozen=True, kw_only=True)
class SyncConflictsItemCad:
    board: str


@dataclass(frozen=True, kw_only=True)
class SyncConflictsItem:
    base: str
    cad: SyncConflictsItemCad
    code: str
    key: str
    reason: str


@dataclass(frozen=True, kw_only=True)
class SyncResult(ProtocolResult):
    board: str = field(metadata={"optional": True})
    board_only: list[str] = field(metadata={"optional": True})
    conflicts: list[SyncConflictsItem] = field(metadata={"optional": True})
    design: str = field(metadata={"optional": True})
    drawn: wire.DrawnSyncSummary | None = field(metadata={"optional": True})
    edits: list[str] = field(metadata={"optional": True})
    files: list[str] = field(metadata={"optional": True})
    orphans: list[str] = field(metadata={"optional": True})
    out: str = field(metadata={"optional": True})
    pending: list[str] = field(metadata={"optional": True})
    placements: int = field(metadata={"optional": True})
    script_output: str = field(metadata={"optional": True})
    sheets: list[str] = field(metadata={"optional": True})
    symbols: int | None = field(metadata={"optional": True})
    target: str = field(metadata={"optional": True})
    unplaced: list[str] = field(metadata={"optional": True})


@dataclass(frozen=True, kw_only=True)
class TemplateAltium:
    format: str
    height: int
    lines: int
    parameters: list[str]
    size: str
    strings: list[str]
    texts: int
    width: int


@dataclass(frozen=True, kw_only=True)
class TemplateDrawnValue:
    lines: int
    resolved: list[str]
    texts: int


@dataclass(frozen=True, kw_only=True)
class TemplateSheet:
    items: int
    name: str
    sizes: list[str] = field(metadata={"optional": True})
    tokens: list[str]


@dataclass(frozen=True, kw_only=True)
class TemplateSource:
    form: str
    height: int
    paper: str
    portrait: bool
    style: int | None
    width: int


@dataclass(frozen=True, kw_only=True)
class TemplateResult(ProtocolResult):
    altium: TemplateAltium = field(metadata={"optional": True})
    drawn: dict[str, TemplateDrawnValue] = field(
        metadata={
            "optional": True,
            "description": "Keys are supplied by named items, rather than fixed record fields.",
        }
    )
    imported: dict[str, int] = field(
        metadata={
            "optional": True,
            "description": "Keys are supplied by named items, rather than fixed record fields.",
        }
    )
    kicad_version: int = field(metadata={"optional": True})
    output: str = field(metadata={"optional": True})
    parameters: list[str] = field(metadata={"optional": True})
    reported: list[str] = field(metadata={"optional": True})
    sheet: TemplateSheet = field(metadata={"optional": True})
    source: TemplateSource = field(metadata={"optional": True})
    strings: dict[str, str] = field(
        metadata={
            "optional": True,
            "description": "Keys are supplied by named items, rather than fixed record fields.",
        }
    )
    target: str = field(metadata={"optional": True})


@dataclass(frozen=True, kw_only=True)
class PanelFilesItem:
    bytes: int
    name: str


@dataclass(frozen=True, kw_only=True)
class PanelPanelItems:
    fiducials: int
    mouse_bite_holes: int
    mouse_bite_rows: int
    score_lines: int
    tabs: int
    tooling_holes: int


@dataclass(frozen=True, kw_only=True)
class PanelPanelPour:
    evidence: str | None
    hypotheses: list[str]
    mode: str
    poured: int
    unpoured: dict[str, int]


@dataclass(frozen=True, kw_only=True)
class PanelPanelSeparations:
    columns: str
    rails: str
    rows: str


@dataclass(frozen=True, kw_only=True)
class PanelPanelSize:
    h: int
    w: int


@dataclass(frozen=True, kw_only=True)
class PanelPanelUnused:
    h: int
    w: int


@dataclass(frozen=True, kw_only=True)
class PanelPanel:
    cols: int
    copies: int
    form: str
    items: PanelPanelItems
    pour: PanelPanelPour = field(metadata={"optional": True})
    rotation: int
    rows: int
    score_layer: None | str
    separations: PanelPanelSeparations
    size: PanelPanelSize
    target: str
    unused: PanelPanelUnused


@dataclass(frozen=True, kw_only=True)
class PanelResult(ProtocolResult):
    board: str = field(metadata={"optional": True})
    files: list[PanelFilesItem] = field(metadata={"optional": True})
    name: str = field(metadata={"optional": True})
    out: str = field(metadata={"optional": True})
    panel: PanelPanel = field(metadata={"optional": True})
    script_output: str = field(metadata={"optional": True})


@dataclass(frozen=True, kw_only=True)
class KitArchive:
    name: str
    sha256: str
    size: int


@dataclass(frozen=True, kw_only=True)
class KitCounts:
    fail: int
    pass_: int = field(metadata={"name": "pass"})
    skipped: int


@dataclass(frozen=True, kw_only=True)
class KitHypothesesItem:
    form: bool
    id: str
    outcome: str
    steps: list[str]


@dataclass(frozen=True, kw_only=True)
class KitPrivacyItem:
    file: str
    kind: str
    offset: int
    text: str


@dataclass(frozen=True, kw_only=True)
class KitRowsItem:
    form: bool
    id: str
    label: str
    result: str


@dataclass(frozen=True, kw_only=True)
class KitRunsItem:
    altium_version: str
    archive_sha256: str
    date: str
    failed: list[str]
    kit_sha256: str
    passed: list[str]
    run_id: str


@dataclass(frozen=True, kw_only=True)
class KitSamplesItem:
    digest: str
    name: str


@dataclass(frozen=True, kw_only=True)
class KitStepsItem:
    id: str
    kind: str
    outcome: str
    pending: list[str]
    reasons: list[str]
    sample: str
    scripted: bool


@dataclass(frozen=True, kw_only=True)
class KitResult(ProtocolResult):
    altium_version: str = field(metadata={"optional": True})
    archive: KitArchive = field(metadata={"optional": True})
    counts: KitCounts = field(metadata={"optional": True})
    files: int = field(metadata={"optional": True})
    form_problems: list[str] = field(metadata={"optional": True})
    hypotheses: list[KitHypothesesItem] = field(metadata={"optional": True})
    kit_problems: list[str] = field(metadata={"optional": True})
    kit_resaved: list[str] = field(metadata={"optional": True})
    kit_sha256: str = field(metadata={"optional": True})
    kit_version: int = field(metadata={"optional": True})
    out: str = field(metadata={"optional": True})
    passed: bool = field(metadata={"optional": True})
    privacy: list[KitPrivacyItem] = field(metadata={"optional": True})
    problems: list[str] = field(metadata={"optional": True})
    record: str = field(metadata={"optional": True})
    result_files: int = field(metadata={"optional": True})
    rows: list[KitRowsItem] = field(metadata={"optional": True})
    run_id: str = field(metadata={"optional": True})
    runs: list[KitRunsItem] = field(metadata={"optional": True})
    samples: list[KitSamplesItem] = field(metadata={"optional": True})
    scripted: list[str] = field(metadata={"optional": True})
    seed: int = field(metadata={"optional": True})
    stale: list[str] = field(metadata={"optional": True})
    steps: list[KitStepsItem] | int = field(metadata={"optional": True})
    synthetic: bool = field(metadata={"optional": True})
    timestamp: str = field(metadata={"optional": True})


@dataclass(frozen=True, kw_only=True)
class EditRecordsItem:
    added: int
    removed: int
    storage: str


@dataclass(frozen=True, kw_only=True)
class EditResult(ProtocolResult):
    changed: bool = field(metadata={"optional": True})
    created: bool = field(metadata={"optional": True})
    diff: str = field(metadata={"optional": True})
    diff_truncated: bool = field(metadata={"optional": True})
    kind: str = field(metadata={"optional": True})
    lines_added: int = field(metadata={"optional": True})
    lines_removed: int = field(metadata={"optional": True})
    operations: list[str] = field(metadata={"optional": True})
    path: str = field(metadata={"optional": True})
    records: list[EditRecordsItem] = field(metadata={"optional": True})
    redrawn: dict[str, int] = field(metadata={"optional": True})
    stale_pours: list[str] = field(metadata={"optional": True})
