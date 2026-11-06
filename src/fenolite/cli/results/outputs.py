# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Wire records for outputs results; producers retain their existing payloads."""

from __future__ import annotations

from dataclasses import dataclass, field

from fenolite.cli.results.common import (
    ProtocolResult,
)
from fenolite.cli.results.writers import BuildResult


@dataclass(frozen=True, kw_only=True)
class ExportArtifactsItem:
    bytes: int
    content_sha256: str
    kind: str
    layer: None | str
    path: str
    sha256: str


@dataclass(frozen=True, kw_only=True)
class ExportDrawingsItemBlocksItem:
    at: list[int]
    name: str
    size: list[int]


@dataclass(frozen=True, kw_only=True)
class ExportDrawingsItem:
    blocks: list[ExportDrawingsItemBlocksItem]
    designators_added: int = field(metadata={"optional": True})
    kind: str
    paper: str
    path: str
    portrait: bool
    sheet: str
    side: str = field(metadata={"optional": True})


@dataclass(frozen=True, kw_only=True)
class ExportModelsItem:
    bytes: int | None
    path: str
    refs: list[str]
    sha256: None | str
    source: str


@dataclass(frozen=True, kw_only=True)
class ExportPreset:
    file: str
    sha256: str


@dataclass(frozen=True, kw_only=True)
class ExportRulesChangedItem:
    detail: str
    kind: str
    selector: str


@dataclass(frozen=True, kw_only=True)
class ExportRulesNotLoweredItem:
    kind: str
    reason: str
    selector: str


@dataclass(frozen=True, kw_only=True)
class ExportRulesWrittenItem:
    kind: str
    rule: str
    selector: str


@dataclass(frozen=True, kw_only=True)
class ExportRules:
    changed: list[ExportRulesChangedItem] = field(metadata={"optional": True})
    not_lowered: list[ExportRulesNotLoweredItem]
    written: list[ExportRulesWrittenItem]


@dataclass(frozen=True, kw_only=True)
class ExportResult(ProtocolResult):
    artifacts: list[ExportArtifactsItem] = field(metadata={"optional": True})
    board: str = field(metadata={"optional": True})
    drawings: list[ExportDrawingsItem] = field(metadata={"optional": True})
    kinds: list[str] = field(metadata={"optional": True})
    models: list[ExportModelsItem] = field(metadata={"optional": True})
    out: str = field(metadata={"optional": True})
    preset: None | ExportPreset = field(metadata={"optional": True})
    repeat: dict[str, str] = field(
        metadata={
            "optional": True,
            "description": "Keys are supplied by named items, rather than fixed record fields.",
        }
    )
    rules: None | ExportRules = field(metadata={"optional": True})
    tool_version: None | str = field(metadata={"optional": True})
    tool_writes: list[str] = field(metadata={"optional": True})


@dataclass(frozen=True, kw_only=True)
class RenderRegionCounts:
    cut: int = field(metadata={"optional": True})
    edge: int
    grid: int
    hole: int = field(metadata={"optional": True})
    label: int = field(metadata={"optional": True})
    open: int = field(metadata={"optional": True})
    pad: int = field(metadata={"optional": True})
    slot: int = field(metadata={"optional": True})
    track: int = field(metadata={"optional": True})
    via: int = field(metadata={"optional": True})
    way: int = field(metadata={"optional": True})
    zone: int = field(metadata={"optional": True})


@dataclass(frozen=True, kw_only=True)
class RenderRegionCutsItem:
    cut: str
    open: int
    routed: int
    supply: int


@dataclass(frozen=True, kw_only=True)
class RenderRegionHighlighted:
    arcs: int
    pads: int
    tracks: int
    vias: int
    zones: int


@dataclass(frozen=True, kw_only=True)
class RenderRegionOpenItemA:
    where: str
    x: int
    y: int


@dataclass(frozen=True, kw_only=True)
class RenderRegionOpenItemB:
    where: str
    x: int
    y: int


@dataclass(frozen=True, kw_only=True)
class RenderRegionOpenItem:
    a: RenderRegionOpenItemA
    b: RenderRegionOpenItemB
    length: int
    net: str


@dataclass(frozen=True, kw_only=True)
class RenderRegionZonesItem:
    layer: str
    net: str
    reason: str
    state: str
    zone: str


@dataclass(frozen=True, kw_only=True)
class RenderRegion:
    copper: list[str]
    counts: RenderRegionCounts
    cuts: list[RenderRegionCutsItem]
    grid: int
    highlighted: RenderRegionHighlighted
    nets: list[str]
    open: list[RenderRegionOpenItem]
    pour_grid: int
    x0: int
    x1: int
    y0: int
    y1: int
    zones: list[RenderRegionZonesItem]


@dataclass(frozen=True, kw_only=True)
class RenderViewsItem:
    bytes: int
    kind: str
    path: str
    sha256: str


@dataclass(frozen=True, kw_only=True)
class RenderResult(BuildResult):
    board: str = field(metadata={"optional": True})
    region: RenderRegion = field(metadata={"optional": True})
    svg_page: None | str = field(metadata={"optional": True})
    tool_version: None | str = field(metadata={"optional": True})
    views: list[RenderViewsItem] = field(metadata={"optional": True})


@dataclass(frozen=True, kw_only=True)
class BomChangesItem:
    a_refs: list[str]
    b_refs: list[str]
    change: str
    key: list[str]


@dataclass(frozen=True, kw_only=True)
class BomCounts:
    dnp: int
    left_out: int | None
    lines: int
    parts: int


@dataclass(frozen=True, kw_only=True)
class BomResult(ProtocolResult):
    changes: list[BomChangesItem] = field(metadata={"optional": True})
    columns: list[str] = field(metadata={"optional": True})
    counts: BomCounts = field(metadata={"optional": True})
    lines: list[dict[str, str]] = field(metadata={"optional": True})
    source: str = field(metadata={"optional": True})
    template: str = field(metadata={"optional": True})


@dataclass(frozen=True, kw_only=True)
class PnpCounts:
    bottom: int
    dnp: int
    left_out: int
    rows: int
    top: int


@dataclass(frozen=True, kw_only=True)
class PnpResult(ProtocolResult):
    columns: list[str] = field(metadata={"optional": True})
    counts: PnpCounts = field(metadata={"optional": True})
    origin: str = field(metadata={"optional": True})
    rows: list[dict[str, str]] = field(metadata={"optional": True})
    template: str = field(metadata={"optional": True})
    units: str = field(metadata={"optional": True})
    y_axis: str = field(metadata={"optional": True})


@dataclass(frozen=True, kw_only=True)
class ManifestArtifactsItem:
    held: str
    kind: str
    path: str
    stale: bool
    state: str


@dataclass(frozen=True, kw_only=True)
class ManifestCheckStagesItem:
    level: str
    name: str
    oracle: None | str
    status: str


@dataclass(frozen=True, kw_only=True)
class ManifestCheck:
    stages: list[ManifestCheckStagesItem]
    tool_version: None | str


@dataclass(frozen=True, kw_only=True)
class ManifestDifferencesItem:
    code: str
    path: str


@dataclass(frozen=True, kw_only=True)
class ManifestProjectBoard:
    format_version: int
    path: str
    sha256: str


@dataclass(frozen=True, kw_only=True)
class ManifestProjectSchematic:
    format_version: int
    path: str
    sha256: str


@dataclass(frozen=True, kw_only=True)
class ManifestProject:
    board: ManifestProjectBoard
    schematic: None | ManifestProjectSchematic


@dataclass(frozen=True, kw_only=True)
class ManifestResult(ProtocolResult):
    artifacts: list[ManifestArtifactsItem] = field(metadata={"optional": True})
    check: None | ManifestCheck = field(metadata={"optional": True})
    differences: list[ManifestDifferencesItem] = field(metadata={"optional": True})
    manifest: str = field(metadata={"optional": True})
    project: ManifestProject = field(metadata={"optional": True})
    states: dict[str, int] = field(
        metadata={
            "optional": True,
            "description": "Keys are supplied by named items, rather than fixed record fields.",
        }
    )
    verified: bool = field(metadata={"optional": True})
