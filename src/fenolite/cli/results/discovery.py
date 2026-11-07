# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Wire records for discovery results; producers retain their existing payloads."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from fenolite.catalog.records import Review
from fenolite.cli.results import common as wire
from fenolite.cli.results.blocks import BlockData, BlockDeprecation, BlockShown
from fenolite.cli.results.common import (
    BlocksProtocolResult,
    PinChoice,
    ProtocolResult,
    VersionScope,
)
from fenolite.core.evidence import Evidence
from fenolite.model.library import DeviceDef


@dataclass(frozen=True, kw_only=True)
class CapabilitiesBackendsItem:
    default_target: int | None
    downgrade: str
    evidence: Evidence
    name: str
    operations: list[str]
    read_kinds: list[str]
    targets: list[int]
    write_kinds: list[str]


@dataclass(frozen=True, kw_only=True)
class CapabilitiesCommandArgumentsItem:
    choices: list[str | int | float | bool | None] | None
    default: Any = field(
        metadata={"description": "Parser-declared JSON default; its shape follows the described argument."}
    )
    flags: list[str]
    help: str
    kind: str
    name: str
    repeatable: bool
    required: bool
    type: str


@dataclass(frozen=True, kw_only=True)
class CapabilitiesCommand:
    actions: list[str] = field(metadata={"optional": True})
    arguments: list[CapabilitiesCommandArgumentsItem]
    claims: bool = field(metadata={"optional": True})
    default_limit: int | None = field(metadata={"optional": True})
    example_tools: list[str] = field(metadata={"optional": True})
    hidden: bool
    levels: list[int | str] = field(metadata={"optional": True})
    mutates: bool
    name: str
    paged: str = field(metadata={"optional": True})
    protocol_versions: list[str] = field(metadata={"optional": True})
    schema: str
    sides: list[str] = field(metadata={"optional": True})
    summary: str
    usage: str
    verbs: list[str] = field(metadata={"optional": True})


@dataclass(frozen=True, kw_only=True)
class CapabilitiesCommandsItem:
    actions: list[str] = field(metadata={"optional": True})
    claims: bool = field(metadata={"optional": True})
    default_limit: int | None = field(metadata={"optional": True})
    example_tools: list[str] = field(metadata={"optional": True})
    hidden: bool = field(metadata={"optional": True})
    levels: list[int | str] = field(metadata={"optional": True})
    mutates: bool
    name: str
    paged: str = field(metadata={"optional": True})
    protocol_versions: list[str] = field(metadata={"optional": True})
    schema: str = field(metadata={"optional": True})
    sides: list[str] = field(metadata={"optional": True})
    summary: str = field(metadata={"optional": True})
    usage: str = field(metadata={"optional": True})
    verbs: list[str] = field(metadata={"optional": True})


@dataclass(frozen=True, kw_only=True)
class CapabilitiesConversionsItem:
    downgrade: bool
    evidence: Evidence
    experimental: bool
    from_: str = field(metadata={"name": "from"})
    targets: list[int]
    to: str


@dataclass(frozen=True, kw_only=True)
class CapabilitiesDeprecatedItem:
    command: str
    option: str | None
    since: str
    use: str


@dataclass(frozen=True, kw_only=True)
class CapabilitiesExperimentalItem:
    command: str
    evidence: Evidence
    missing: dict[str, list[str]] = field(
        metadata={"description": "Keys are supplied by named items, rather than fixed record fields."}
    )
    name: str
    option: str
    write_kinds: list[str]


@dataclass(frozen=True, kw_only=True)
class CapabilitiesExtrasValue:
    installed: bool
    missing: list[str]


@dataclass(frozen=True, kw_only=True)
class CapabilitiesGlobalArgumentsItem:
    choices: list[int | str] | None
    default: bool | int | None | str
    flags: list[str]
    help: str
    kind: str
    name: str
    repeatable: bool
    required: bool
    type: str


@dataclass(frozen=True, kw_only=True)
class CapabilitiesGuideItem:
    summary: str
    title: str
    topic: str


@dataclass(frozen=True, kw_only=True)
class CapabilitiesMatrixItem:
    versions: dict[str, list[VersionScope]] = field(
        metadata={"optional": True, "description": "Verified tool scopes indexed by backend operation."}
    )
    backend: str
    detect: None | str
    experimental: list[str]
    kind: str
    read: None | str
    roundtrip_exact: None | str
    roundtrip_modified: None | str
    verified_by: list[str]
    write: None | str


@dataclass(frozen=True, kw_only=True)
class CapabilitiesExternalCandidates:
    """c0368: whether a router can propose local external candidates, and their scope."""

    supported: bool
    available: bool | None
    projection: str
    scope: str
    arcs: bool
    pairs: bool
    groups: bool
    local_only: bool
    automatic_acceptance: bool


@dataclass(frozen=True, kw_only=True)
class CapabilitiesRoutersItem:
    available: bool | None = field(metadata={"optional": True})
    builtin: bool = field(metadata={"optional": True})
    description: str = field(metadata={"optional": True})
    features: list[str] = field(metadata={"optional": True})
    name: str
    reason: None | str = field(metadata={"optional": True})
    sends_data_offsite: bool = field(metadata={"optional": True})
    external_candidates: CapabilitiesExternalCandidates | None = field(metadata={"optional": True})


@dataclass(frozen=True, kw_only=True)
class CapabilitiesStartersItem:
    name: str
    summary: str


@dataclass(frozen=True, kw_only=True)
class CapabilitiesTargets:
    build: list[str]
    default: int = field(metadata={"optional": True})
    kicad: list[int] = field(metadata={"optional": True})


@dataclass(frozen=True, kw_only=True)
class CapabilitiesToolsValue:
    path: str
    version: str


@dataclass(frozen=True, kw_only=True)
class CapabilitiesResult(ProtocolResult):
    suppliers: list[wire.SupplierMetadata] = field(metadata={"optional": True})
    backends: list[CapabilitiesBackendsItem] = field(metadata={"optional": True})
    command: CapabilitiesCommand = field(metadata={"optional": True})
    commands: list[CapabilitiesCommandsItem] = field(metadata={"optional": True})
    contract: str = field(metadata={"optional": True})
    conversions: list[CapabilitiesConversionsItem] = field(metadata={"optional": True})
    deprecated: list[CapabilitiesDeprecatedItem] = field(metadata={"optional": True})
    experimental: list[CapabilitiesExperimentalItem] = field(metadata={"optional": True})
    extras: dict[str, CapabilitiesExtrasValue] = field(
        metadata={
            "optional": True,
            "description": "Keys are supplied by named items, rather than fixed record fields.",
        }
    )
    fenolite_version: str = field(metadata={"optional": True})
    global_arguments: list[CapabilitiesGlobalArgumentsItem] = field(metadata={"optional": True})
    global_flags: list[str] = field(metadata={"optional": True})
    guide: list[CapabilitiesGuideItem] = field(metadata={"optional": True})
    matrix: list[CapabilitiesMatrixItem] = field(metadata={"optional": True})
    mutation_flags: list[str] = field(metadata={"optional": True})
    routers: list[CapabilitiesRoutersItem] = field(metadata={"optional": True})
    sends_data_offsite: bool = field(metadata={"optional": True})
    starters: list[CapabilitiesStartersItem] = field(metadata={"optional": True})
    targets: CapabilitiesTargets = field(metadata={"optional": True})
    tools: dict[str, None | CapabilitiesToolsValue] = field(
        metadata={
            "optional": True,
            "description": "Keys are supplied by named items, rather than fixed record fields.",
        }
    )


@dataclass(frozen=True, kw_only=True)
class DoctorDocker:
    path: str


@dataclass(frozen=True, kw_only=True)
class DoctorJava:
    path: str


@dataclass(frozen=True, kw_only=True)
class DoctorKicadCliItem:
    evidence: Evidence | None
    major: int | None
    matrix: None | dict[str, bool | str] = field(
        metadata={"description": "Keys are supplied by named items, rather than fixed record fields."}
    )
    path: str
    selected: bool
    source: str
    supported: bool | None
    version: None | str


@dataclass(frozen=True, kw_only=True)
class DoctorRoutersItem:
    available: bool = field(metadata={"optional": True})
    java: None | str = field(metadata={"optional": True})
    java_major: int | None = field(metadata={"optional": True})
    java_ok: bool = field(metadata={"optional": True})
    name: str
    path: None | str = field(metadata={"optional": True})
    reason: None | str = field(metadata={"optional": True})
    source: None | str = field(metadata={"optional": True})
    version: None | str = field(metadata={"optional": True})


@dataclass(frozen=True, kw_only=True)
class DoctorResult(ProtocolResult):
    by_major: dict[str, list[str]] = field(
        metadata={
            "optional": True,
            "description": "Keys are supplied by named items, rather than fixed record fields.",
        }
    )
    docker: None | DoctorDocker = field(metadata={"optional": True})
    java: None | DoctorJava = field(metadata={"optional": True})
    kicad_cli: list[DoctorKicadCliItem] = field(metadata={"optional": True})
    routers: list[DoctorRoutersItem] = field(metadata={"optional": True})


@dataclass(frozen=True, kw_only=True)
class ExplainResult(ProtocolResult):
    code: str = field(metadata={"optional": True})
    exit_code: int | None = field(metadata={"optional": True})
    family: None | str = field(metadata={"optional": True})
    fix: str = field(metadata={"optional": True})
    kind: str = field(metadata={"optional": True})
    meaning: str = field(metadata={"optional": True})
    see: str = field(metadata={"optional": True})
    severities: list[str] = field(metadata={"optional": True})


@dataclass(frozen=True, kw_only=True)
class GuideTopicsItem:
    lines: int
    summary: str
    title: str
    topic: str


@dataclass(frozen=True, kw_only=True)
class GuideResult(ProtocolResult):
    summary: str = field(metadata={"optional": True})
    text: str = field(metadata={"optional": True})
    title: str = field(metadata={"optional": True})
    topic: str = field(metadata={"optional": True})
    topics: list[GuideTopicsItem] = field(metadata={"optional": True})
    version: str = field(metadata={"optional": True})


@dataclass(frozen=True, kw_only=True)
class SkillAgentsItem:
    agent: str
    dir: str


@dataclass(frozen=True, kw_only=True)
class SkillFilesItem:
    bytes: int
    path: str
    sha256: str


@dataclass(frozen=True, kw_only=True)
class SkillResult(ProtocolResult):
    action: str = field(metadata={"optional": True})
    agents: list[SkillAgentsItem] = field(metadata={"optional": True})
    description: str = field(metadata={"optional": True})
    files: list[SkillFilesItem | str] = field(metadata={"optional": True})
    name: str = field(metadata={"optional": True})
    target: None | str = field(metadata={"optional": True})
    version: str = field(metadata={"optional": True})


@dataclass(frozen=True, kw_only=True)
class InitResult(ProtocolResult):
    design: str = field(metadata={"optional": True})
    name: str = field(metadata={"optional": True})
    next: list[str] = field(metadata={"optional": True})
    starter: str = field(metadata={"optional": True})


@dataclass(frozen=True, kw_only=True)
class FetchResult(ProtocolResult):
    bytes: int = field(metadata={"optional": True})
    env: dict[str, str] = field(
        metadata={
            "optional": True,
            "description": "Keys are supplied by named items, rather than fixed record fields.",
        }
    )
    file: str = field(metadata={"optional": True})
    installed: bool = field(metadata={"optional": True})
    licence: str = field(metadata={"optional": True})
    name: str = field(metadata={"optional": True})
    needs: list[str] = field(metadata={"optional": True})
    origin: str = field(metadata={"optional": True})
    path: str = field(metadata={"optional": True})
    sha256: str = field(metadata={"optional": True})
    url: str = field(metadata={"optional": True})
    version: str = field(metadata={"optional": True})


@dataclass(frozen=True, kw_only=True)
class CatalogCounts:
    footprints: int
    symbols: int


@dataclass(frozen=True, kw_only=True)
class CatalogExport:
    bytes: int
    sha256: str


@dataclass(frozen=True, kw_only=True)
class CatalogFilters:
    kind: str
    query: str


@dataclass(frozen=True, kw_only=True)
class CatalogResult(ProtocolResult):
    catalog: str = field(metadata={"optional": True})
    series: str = field(metadata={"optional": True})
    case: str = field(metadata={"optional": True})
    values: wire.FamilyValues = field(metadata={"optional": True})
    category: str = field(metadata={"optional": True})
    count: int = field(metadata={"optional": True})
    counts: CatalogCounts = field(metadata={"optional": True})
    definition: wire.CatalogDefinition = field(metadata={"optional": True})
    device: str = field(metadata={"optional": True})
    digest: str = field(metadata={"optional": True})
    edited: bool = field(metadata={"optional": True})
    entries: list[wire.CatalogEntry] = field(metadata={"optional": True})
    evidence: str = field(metadata={"optional": True})
    export: CatalogExport = field(metadata={"optional": True})
    filters: CatalogFilters = field(metadata={"optional": True})
    functions: list[str] = field(metadata={"optional": True})
    id: str = field(metadata={"optional": True})
    kind: str = field(metadata={"optional": True})
    lib_id: str = field(metadata={"optional": True})
    licence: str = field(metadata={"optional": True})
    out: str = field(metadata={"optional": True})
    record: DeviceDef | str = field(metadata={"optional": True})
    replaces: bool = field(metadata={"optional": True})
    shadowed: list[str] = field(metadata={"optional": True})
    sources: list[str] | dict[str, list[str]] = field(metadata={"optional": True})
    summary: str = field(metadata={"optional": True})
    uid: str = field(metadata={"optional": True})
    version: str = field(metadata={"optional": True})


@dataclass(frozen=True, kw_only=True)
class ModelsCounts:
    located: int
    missing: int
    paths: int


@dataclass(frozen=True, kw_only=True)
class ModelsModelsItem:
    bytes: int | None
    path: str
    refs: list[str]
    sha256: None | str
    source: str


@dataclass(frozen=True, kw_only=True)
class ModelsResult(ProtocolResult):
    board: str = field(metadata={"optional": True})
    counts: ModelsCounts = field(metadata={"optional": True})
    models: list[ModelsModelsItem] = field(metadata={"optional": True})


@dataclass(frozen=True, kw_only=True)
class McpResult(ProtocolResult):
    resources: list[str] = field(metadata={"optional": True})
    root: str = field(metadata={"optional": True})
    tools: list[str] = field(metadata={"optional": True})
    versions: list[str] = field(metadata={"optional": True})


@dataclass(frozen=True, kw_only=True)
class BlocksBlocksItemTestsItem:
    message: str
    name: str
    status: str


@dataclass(frozen=True, kw_only=True)
class BlocksBlocksItem:
    category: str = field(metadata={"optional": True})
    deprecated: bool = field(metadata={"optional": True})
    digest: str = field(metadata={"optional": True})
    evidence: str = field(metadata={"optional": True})
    golden: str = field(metadata={"optional": True})
    golden_paths: list[str] = field(metadata={"optional": True})
    id: str
    licence: str = field(metadata={"optional": True})
    source: str = field(metadata={"optional": True})
    summary: str = field(metadata={"optional": True})
    tests: list[BlocksBlocksItemTestsItem] = field(metadata={"optional": True})
    usage: str = field(metadata={"optional": True})
    version: str
    where: str = field(metadata={"optional": True})


@dataclass(frozen=True, kw_only=True)
class BlocksCapture:
    arcs: int = field(metadata={"optional": True})
    block: str = field(metadata={"optional": True})
    file: str = field(metadata={"optional": True})
    hint: str = field(metadata={"optional": True})
    instance: str
    left: list[str] = field(metadata={"optional": True})
    parts: int = field(metadata={"optional": True})
    tracks: int = field(metadata={"optional": True})
    version: str = field(metadata={"optional": True})
    vias: int = field(metadata={"optional": True})
    zones: int = field(metadata={"optional": True})


@dataclass(frozen=True, kw_only=True)
class BlocksGoldenPlanItem:
    new_sha256: str
    old_sha256: str
    path: str


@dataclass(frozen=True, kw_only=True)
class BlocksRecord:
    fenolite: str
    id: str
    namespace: str
    record: BlockData
    schema: str
    version: str


@dataclass(frozen=True, kw_only=True)
class BlocksUpgradesItemCircuitItemAfter:
    device: str
    footprint: str
    symbol: str
    value: str


@dataclass(frozen=True, kw_only=True)
class BlocksUpgradesItemCircuitItemBefore:
    device: str
    footprint: str
    symbol: str
    value: str


@dataclass(frozen=True, kw_only=True)
class BlocksUpgradesItemCircuitItem:
    after: BlocksUpgradesItemCircuitItemAfter
    before: BlocksUpgradesItemCircuitItemBefore
    change: str
    path: str


@dataclass(frozen=True, kw_only=True)
class BlocksUpgradesItemIssuesItem:
    code: str
    hint: str
    message: str
    retryable: bool
    severity: str
    where: str


@dataclass(frozen=True, kw_only=True)
class BlocksUpgradesItem:
    after: str
    before: str
    circuit: list[BlocksUpgradesItemCircuitItem] = field(metadata={"optional": True})
    deprecated: BlockDeprecation | None
    id: str
    issues: list[BlocksUpgradesItemIssuesItem]
    path: str
    record: BlockData
    step: str


@dataclass(frozen=True, kw_only=True)
class BlocksUsesItem:
    design: str
    instance: str
    lock: str
    version: str


@dataclass(frozen=True, kw_only=True)
class BlocksResult(BlocksProtocolResult):
    block: BlockShown = field(metadata={"optional": True})
    blocks: list[BlocksBlocksItem] = field(metadata={"optional": True})
    capture: BlocksCapture = field(metadata={"optional": True})
    current: bool = field(metadata={"optional": True})
    file: str = field(metadata={"optional": True})
    golden_plan: list[BlocksGoldenPlanItem] = field(metadata={"optional": True})
    id: str = field(metadata={"optional": True})
    lock: str = field(metadata={"optional": True})
    output: str = field(metadata={"optional": True})
    record: BlocksRecord = field(metadata={"optional": True})
    source: str = field(metadata={"optional": True})
    text: str = field(metadata={"optional": True})
    upgrades: list[BlocksUpgradesItem] = field(metadata={"optional": True})
    uses: list[BlocksUsesItem] = field(metadata={"optional": True})
    version: str = field(metadata={"optional": True})


@dataclass(frozen=True, kw_only=True)
class FamilyCandidatesItem:
    case: str
    device: str
    dielectric: str
    evidence: str = field(metadata={"optional": True})
    family: str
    footprint: str
    manufacturer: str = field(metadata={"optional": True})
    mpn: str
    packing: str = field(metadata={"optional": True})
    rating: str = field(metadata={"optional": True})
    tolerance: str
    value: str


@dataclass(frozen=True, kw_only=True)
class FamilyDecodedItem:
    case: str
    codes: dict[str, str] = field(
        metadata={"description": "Keys are supplied by named items, rather than fixed record fields."}
    )
    device: str
    dielectric: str = field(metadata={"optional": True})
    evidence: str
    family: str
    footprint: str
    in_matrix: bool
    manufacturer: str
    mpn: str
    packing: str
    power: str = field(metadata={"optional": True})
    rating: str = field(metadata={"optional": True})
    suffix: None | str
    tolerance: str
    value: str
    voltage: str = field(metadata={"optional": True})


@dataclass(frozen=True, kw_only=True)
class FamilyFailuresItem:
    family: str
    field: str
    mpn: str
    position: int


@dataclass(frozen=True, kw_only=True)
class FamilyFamiliesItem:
    errors: int
    evidence: str
    file: str
    id: str
    kind: str
    manufacturer: str
    summary: str
    uid: str
    version: str
    warnings: int


@dataclass(frozen=True, kw_only=True)
class FamilyFamilyExcludeItemValue:
    max: str
    min: str


@dataclass(frozen=True, kw_only=True)
class FamilyFamilyExcludeItem:
    size: list[str]
    value: FamilyFamilyExcludeItemValue
    voltage: list[str]


@dataclass(frozen=True, kw_only=True)
class FamilyFamilyFieldsValueCodesValue:
    case: str = field(metadata={"optional": True})
    dielectric: str = field(metadata={"optional": True})
    footprint: str = field(metadata={"optional": True})
    packing: str = field(metadata={"optional": True})
    rating: str = field(metadata={"optional": True})
    tolerance: str = field(metadata={"optional": True})


@dataclass(frozen=True, kw_only=True)
class FamilyFamilyFieldsValue:
    codes: dict[str, FamilyFamilyFieldsValueCodesValue] = field(
        metadata={
            "optional": True,
            "description": "Keys are supplied by named items, rather than fixed record fields.",
        }
    )
    prefer: None | str = field(metadata={"optional": True})
    role: str = field(metadata={"optional": True})
    scheme: str = field(metadata={"optional": True})
    series: str = field(metadata={"optional": True})
    unit: str = field(metadata={"optional": True})


@dataclass(frozen=True, kw_only=True)
class FamilyFamilyValidItemValue:
    max: str
    min: str


@dataclass(frozen=True, kw_only=True)
class FamilyFamilyValidItem:
    dielectric: list[str]
    size: list[str]
    tolerance: list[str]
    value: FamilyFamilyValidItemValue
    voltage: list[str]


@dataclass(frozen=True, kw_only=True)
class FamilyFamily:
    combinations: int
    datasheet: str
    errors: int
    evidence: str
    exclude: list[FamilyFamilyExcludeItem]
    fields: dict[str, FamilyFamilyFieldsValue] = field(
        metadata={"description": "Keys are supplied by named items, rather than fixed record fields."}
    )
    file: str
    footprint: str | None
    id: str
    kind: str
    licence: str
    manufacturer: str
    pattern: str
    sources: list[str]
    summary: str
    symbol: str
    tail: str
    uid: str
    valid: list[FamilyFamilyValidItem]
    version: str
    warnings: int


@dataclass(frozen=True, kw_only=True)
class FamilyFilesItem:
    errors: int
    evidence: str
    file: str
    id: str
    kind: str
    manufacturer: str
    summary: str
    uid: str
    version: str
    warnings: int


@dataclass(frozen=True, kw_only=True)
class FamilyResult(ProtocolResult):
    candidates: list[FamilyCandidatesItem] = field(metadata={"optional": True})
    combinations: int = field(metadata={"optional": True})
    decoded: list[FamilyDecodedItem] = field(metadata={"optional": True})
    failures: list[FamilyFailuresItem] = field(metadata={"optional": True})
    families: list[FamilyFamiliesItem] = field(metadata={"optional": True})
    family: FamilyFamily | str = field(metadata={"optional": True})
    files: list[FamilyFilesItem] = field(metadata={"optional": True})
    matches: int = field(metadata={"optional": True})
    query: str = field(metadata={"optional": True})
    truncated: bool = field(metadata={"optional": True})


@dataclass(frozen=True, kw_only=True)
class GetDownloadsItem:
    asset: str
    bytes: int
    origin: str
    path: str
    release: str
    sha256: str
    url: str = field(metadata={"optional": True})


@dataclass(frozen=True, kw_only=True)
class GetItemsItemUpstream:
    commit: str
    url: str


@dataclass(frozen=True, kw_only=True)
class GetItemsItem:
    action: str
    after: None | str
    authors: list[str] = field(metadata={"optional": True})
    before: None | str
    bytes: int = field(metadata={"optional": True})
    evidence: str = field(metadata={"optional": True})
    executes: bool = field(metadata={"optional": True})
    family: str = field(metadata={"optional": True})
    id: str
    kind: str
    obligations: list[str] = field(metadata={"optional": True})
    path: str
    proof: None | str = field(metadata={"optional": True})
    reciprocal: bool = field(metadata={"optional": True})
    release: str = field(metadata={"optional": True})
    required_by: list[str] = field(metadata={"optional": True})
    spdx: str = field(metadata={"optional": True})
    tree: str = field(metadata={"optional": True})
    upstream: None | GetItemsItemUpstream = field(metadata={"optional": True})
    version: str


@dataclass(frozen=True, kw_only=True)
class GetLicencesItem:
    accept_required: bool
    accepted: bool
    spdx: str


@dataclass(frozen=True, kw_only=True)
class GetRowsItem:
    authors: list[str] = field(metadata={"optional": True})
    family: str = field(metadata={"optional": True})
    gallery: str = field(metadata={"optional": True})
    id: str
    kind: str
    modified: bool = field(metadata={"optional": True})
    newer: str | None = field(metadata={"optional": True})
    path: str = field(metadata={"optional": True})
    present: bool = field(metadata={"optional": True})
    release: str = field(metadata={"optional": True})
    spdx: str
    title: str = field(metadata={"optional": True})
    version: str


@dataclass(frozen=True, kw_only=True)
class GetResult(ProtocolResult):
    accepted: list[str] = field(metadata={"optional": True})
    attribution: str = field(metadata={"optional": True})
    cached: bool = field(metadata={"optional": True})
    downloads: list[GetDownloadsItem] = field(metadata={"optional": True})
    index_sha256: None | str = field(metadata={"optional": True})
    item: str = field(metadata={"optional": True})
    items: list[GetItemsItem] = field(metadata={"optional": True})
    licences: list[GetLicencesItem] = field(metadata={"optional": True})
    lock: str = field(metadata={"optional": True})
    notes: list[str] = field(metadata={"optional": True})
    origin: None | str = field(metadata={"optional": True})
    release: None | str = field(metadata={"optional": True})
    removes: list[str] = field(metadata={"optional": True})
    rows: list[GetRowsItem] = field(metadata={"optional": True})
    stage: str = field(metadata={"optional": True})
    total: int = field(metadata={"optional": True})


@dataclass(frozen=True, kw_only=True)
class LibraryCompareItem:
    change: str
    fields: list[str]
    footprint_changed: bool
    id: str
    kind: str
    symbol_changed: bool


@dataclass(frozen=True, kw_only=True)
class LibraryCrosscheckRowsItemMeasured:
    centre_nm: list[int]
    size_nm: list[int]


@dataclass(frozen=True, kw_only=True)
class LibraryCrosscheckRowsItemReference:
    centre_nm: list[int]
    size_nm: list[int]


@dataclass(frozen=True, kw_only=True)
class LibraryCrosscheckRowsItem:
    measured: LibraryCrosscheckRowsItemMeasured
    pad: str
    reference: LibraryCrosscheckRowsItemReference


@dataclass(frozen=True, kw_only=True)
class LibraryCrosscheckTolerances:
    centre_nm: int
    pitch_nm: int
    size_min_nm: int
    size_percent: int


@dataclass(frozen=True, kw_only=True)
class LibraryCrosscheck:
    reference: None | str
    rows: list[LibraryCrosscheckRowsItem]
    tolerances: LibraryCrosscheckTolerances


@dataclass(frozen=True, kw_only=True)
class LibraryDatasheet:
    file: str
    sha256: str


@dataclass(frozen=True, kw_only=True)
class LibraryDoubtsItem:
    field: str
    reason: str


@dataclass(frozen=True, kw_only=True)
class LibraryDriftItem:
    kinds: list[str]
    name: str


@dataclass(frozen=True, kw_only=True)
class LibraryFootprintsItem:
    name: str
    refs: list[str]
    source: str


@dataclass(frozen=True, kw_only=True)
class LibraryItemsItemFindingsItem:
    code: str
    hint: str
    message: str
    retryable: bool
    severity: str
    waived: bool
    where: str


@dataclass(frozen=True, kw_only=True)
class LibraryItemsItemReview:
    digest: str
    latest: Review | None
    state: str


@dataclass(frozen=True, kw_only=True)
class LibraryItemsItemSheet:
    artifact_sha256: str = field(metadata={"optional": True})
    content_sha256: str = field(metadata={"optional": True})
    path: str
    sha256: str


@dataclass(frozen=True, kw_only=True)
class LibraryItemsItem:
    effective_evidence: str = field(metadata={"optional": True})
    element: str = field(metadata={"optional": True})
    evidence: str = field(metadata={"optional": True})
    file: str = field(metadata={"optional": True})
    findings: list[LibraryItemsItemFindingsItem] = field(metadata={"optional": True})
    id: str
    kind: str
    review: LibraryItemsItemReview = field(metadata={"optional": True})
    rules_run: list[str] = field(metadata={"optional": True})
    sheet: LibraryItemsItemSheet = field(metadata={"optional": True})
    version: str = field(metadata={"optional": True})


@dataclass(frozen=True, kw_only=True)
class LibraryPackage:
    family: str
    pins: int


@dataclass(frozen=True, kw_only=True)
class LibraryPackagesItemBodies:
    count: int
    top: int | None


@dataclass(frozen=True, kw_only=True)
class LibraryPackagesItemLandDeltas:
    drill: int = field(metadata={"optional": True})
    pad_diameter: int = field(metadata={"optional": True})
    pad_length: int = field(metadata={"optional": True})
    pad_length_x: int = field(metadata={"optional": True})
    pad_length_y: int = field(metadata={"optional": True})
    pad_width: int = field(metadata={"optional": True})
    pad_width_x: int = field(metadata={"optional": True})
    pad_width_y: int = field(metadata={"optional": True})
    row_spacing: int = field(metadata={"optional": True})
    row_spacing_x: int = field(metadata={"optional": True})
    row_spacing_y: int = field(metadata={"optional": True})


@dataclass(frozen=True, kw_only=True)
class LibraryPackagesItemLand:
    deltas: LibraryPackagesItemLandDeltas
    drill: int | None
    evidence: str
    g: int | None
    pad: list[int] | None
    pad_diameter: int | None
    source: str
    table: int | None
    x: int | None
    z: int | None


@dataclass(frozen=True, kw_only=True)
class LibraryPackagesItem:
    bodies: LibraryPackagesItemBodies
    courtyard: list[int] | None
    family: str
    files: list[str]
    id: str
    issues: list[str]
    land: LibraryPackagesItemLand
    name: str
    stamp: str


@dataclass(frozen=True, kw_only=True)
class LibraryProposalsItemProposer:
    date: str
    kind: str
    name: str


@dataclass(frozen=True, kw_only=True)
class LibraryProposalsItem:
    file: str
    proposer: LibraryProposalsItemProposer
    sha256: str


@dataclass(frozen=True, kw_only=True)
class LibrarySkippedItem:
    file: str
    member: str
    reason: str


@dataclass(frozen=True, kw_only=True)
class LibrarySourcesItem:
    file: str
    kind: str
    member: str
    sha256: str


@dataclass(frozen=True, kw_only=True)
class LibrarySummaryFindings:
    error: int = field(metadata={"optional": True})
    info: int = field(metadata={"optional": True})
    warning: int = field(metadata={"optional": True})


@dataclass(frozen=True, kw_only=True)
class LibrarySummary:
    evidence: dict[str, int] = field(
        metadata={"description": "Keys are supplied by named items, rather than fixed record fields."}
    )
    findings: LibrarySummaryFindings


@dataclass(frozen=True, kw_only=True)
class LibrarySymbolsItemUnitsItemPins:
    bottom: list[str]
    left: list[str]
    right: list[str]
    top: list[str]


@dataclass(frozen=True, kw_only=True)
class LibrarySymbolsItemUnitsItem:
    name: str
    pins: LibrarySymbolsItemUnitsItemPins
    unit: int


@dataclass(frozen=True, kw_only=True)
class LibrarySymbolsItem:
    extends: str = field(metadata={"optional": True})
    issues: list[str]
    name: str
    units: list[LibrarySymbolsItemUnitsItem]


@dataclass(frozen=True, kw_only=True)
class LibraryResult(ProtocolResult):
    action: str = field(metadata={"optional": True})
    board: str = field(metadata={"optional": True})
    compare: list[LibraryCompareItem] = field(metadata={"optional": True})
    crosscheck: LibraryCrosscheck = field(metadata={"optional": True})
    datasheet: LibraryDatasheet = field(metadata={"optional": True})
    device: str = field(metadata={"optional": True})
    doubts: list[LibraryDoubtsItem] = field(metadata={"optional": True})
    drift: list[LibraryDriftItem] = field(metadata={"optional": True})
    evidence: str = field(metadata={"optional": True})
    family: None | str = field(metadata={"optional": True})
    folder: str = field(metadata={"optional": True})
    footprint: str = field(metadata={"optional": True})
    footprints: list[LibraryFootprintsItem] = field(metadata={"optional": True})
    format: str = field(metadata={"optional": True})
    guide: str = field(metadata={"optional": True})
    items: list[LibraryItemsItem] = field(metadata={"optional": True})
    library: str = field(metadata={"optional": True})
    out: str = field(metadata={"optional": True})
    package: LibraryPackage = field(metadata={"optional": True})
    packages: list[LibraryPackagesItem] = field(metadata={"optional": True})
    pcblib: None | str = field(metadata={"optional": True})
    proposals: list[LibraryProposalsItem] = field(metadata={"optional": True})
    record_digests: dict[str, str] = field(
        metadata={
            "optional": True,
            "description": "Keys are supplied by named items, rather than fixed record fields.",
        }
    )
    schema: str = field(metadata={"optional": True})
    skeleton: str = field(metadata={"optional": True})
    skipped: list[LibrarySkippedItem] = field(metadata={"optional": True})
    source: str = field(metadata={"optional": True})
    sources: list[LibrarySourcesItem] = field(metadata={"optional": True})
    step: None | str = field(metadata={"optional": True})
    summary: LibrarySummary = field(metadata={"optional": True})
    symbol: str = field(metadata={"optional": True})
    symbols: list[LibrarySymbolsItem] = field(metadata={"optional": True})
    unchanged: bool = field(metadata={"optional": True})
    uncited: list[str] = field(metadata={"optional": True})


@dataclass(frozen=True, kw_only=True)
class PickCandidatesItem:
    case: str
    catalog: str
    device: str
    distance: str
    evidence: str
    row: str
    tolerance: str
    value: str


@dataclass(frozen=True, kw_only=True)
class PickExcludedItem:
    failed: str
    first: str
    reason: str
    row: str


@dataclass(frozen=True, kw_only=True)
class PickGeneratorsItemParts:
    bot: str = field(metadata={"optional": True})
    c: str = field(metadata={"optional": True})
    r: str = field(metadata={"optional": True})
    scl: str = field(metadata={"optional": True})
    sda: str = field(metadata={"optional": True})
    top: str = field(metadata={"optional": True})


@dataclass(frozen=True, kw_only=True)
class PickGeneratorsItem:
    achieved: str
    generator: str
    group: str
    message: str
    ok: bool
    parts: PickGeneratorsItemParts


@dataclass(frozen=True, kw_only=True)
class PickLockChangesItem:
    after: str
    before: str
    key: str
    reason: str
    section: str


@dataclass(frozen=True, kw_only=True)
class PickLock:
    changes: list[PickLockChangesItem]
    exists: bool
    file: str
    frozen: bool
    written: bool


@dataclass(frozen=True, kw_only=True)
class PickPicksItem:
    before: str | None
    catalog: str
    device: str
    evidence: str
    path: str
    query: str
    row: str
    state: str


@dataclass(frozen=True, kw_only=True)
class PickProposedItem:
    file: str
    id: str


@dataclass(frozen=True, kw_only=True)
class PickUpdatesItem:
    after: str
    before: str
    path: str


@dataclass(frozen=True, kw_only=True)
class PickResult(ProtocolResult):
    sends: list[str] = field(metadata={"optional": True})
    proposals: list[wire.SupplierProposal] = field(metadata={"optional": True})
    candidates: list[PickCandidatesItem] = field(metadata={"optional": True})
    excluded: list[PickExcludedItem] = field(metadata={"optional": True})
    generators: list[PickGeneratorsItem] = field(metadata={"optional": True})
    lock: PickLock = field(metadata={"optional": True})
    matches: int = field(metadata={"optional": True})
    path: str = field(metadata={"optional": True})
    picks: list[PickPicksItem] = field(metadata={"optional": True})
    pins: list[PinChoice] = field(metadata={"optional": True})
    proposed: list[PickProposedItem] = field(metadata={"optional": True})
    query: str = field(metadata={"optional": True})
    skipped: list[str] = field(metadata={"optional": True})
    updates: list[PickUpdatesItem] = field(metadata={"optional": True})
