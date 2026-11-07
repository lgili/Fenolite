# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Explicit command-result wire descriptions; unknown commands have no generic fallback."""

from __future__ import annotations

from collections.abc import Mapping

from fenolite.cli.results.analyses import (
    AnalyzeResult,
    ImpedanceResult,
    NeighborsResult,
    NetlistResult,
    NetResult,
    PadsResult,
    RegionResult,
    RolesResult,
    TestpointsResult,
)
from fenolite.cli.results.checks import (
    CheckResult,
    ConvertResult,
    DiffResult,
    EquivalentResult,
    ImportResult,
    ParityResult,
    ReadyResult,
    RoundtripResult,
    VerifySourceResult,
)
from fenolite.cli.results.common import MigrationResult
from fenolite.cli.results.discovery import (
    BlocksResult,
    CapabilitiesResult,
    CatalogResult,
    DoctorResult,
    ExplainResult,
    FamilyResult,
    FetchResult,
    GetResult,
    GuideResult,
    InitResult,
    LibraryResult,
    McpResult,
    ModelsResult,
    PickResult,
    SkillResult,
)
from fenolite.cli.results.edits import (
    CopperResult,
    FillResult,
    FmtResult,
    PlaceResult,
    PublishResult,
    RefsResult,
    RestoreResult,
    RouteResult,
    SilkResult,
    SnapshotResult,
    TidyResult,
)
from fenolite.cli.results.inspection import (
    InspectResult,
    ViewResult,
)
from fenolite.cli.results.outputs import (
    BomResult,
    ExportResult,
    ManifestResult,
    PnpResult,
    RenderResult,
)
from fenolite.cli.results.writers import (
    BuildResult,
    EditResult,
    KitResult,
    PanelResult,
    SyncResult,
    TemplateResult,
)

RESULTS: Mapping[str, type] = {
    "migrate": MigrationResult,  # Explicit prepared c0218 descriptor.
    "analyze": AnalyzeResult,
    "blocks": BlocksResult,
    "bom": BomResult,
    "build": BuildResult,
    "capabilities": CapabilitiesResult,
    "catalog": CatalogResult,
    "check": CheckResult,
    "convert": ConvertResult,
    "copper": CopperResult,
    "diff": DiffResult,
    "doctor": DoctorResult,
    "edit": EditResult,
    "equivalent": EquivalentResult,
    "explain": ExplainResult,
    "export": ExportResult,
    "family": FamilyResult,
    "fetch": FetchResult,
    "fill": FillResult,
    "fmt": FmtResult,
    "get": GetResult,
    "guide": GuideResult,
    "impedance": ImpedanceResult,
    "import": ImportResult,
    "init": InitResult,
    "inspect": InspectResult,
    "kit": KitResult,
    "library": LibraryResult,
    "manifest": ManifestResult,
    "mcp": McpResult,
    "models": ModelsResult,
    "neighbors": NeighborsResult,
    "net": NetResult,
    "netlist": NetlistResult,
    "pads": PadsResult,
    "panel": PanelResult,
    "parity": ParityResult,
    "pick": PickResult,
    "place": PlaceResult,
    "pnp": PnpResult,
    "publish": PublishResult,
    "ready": ReadyResult,
    "refs": RefsResult,
    "region": RegionResult,
    "render": RenderResult,
    "restore": RestoreResult,
    "roles": RolesResult,
    "roundtrip": RoundtripResult,
    "route": RouteResult,
    "silk": SilkResult,
    "skill": SkillResult,
    "snapshot": SnapshotResult,
    "sync": SyncResult,
    "template": TemplateResult,
    "testpoints": TestpointsResult,
    "tidy": TidyResult,
    "verify-source": VerifySourceResult,
    "view": ViewResult,
}

LEGACY = frozenset({"convert", "equivalent", "import", "verify-source"})


def schema_id(command: str, version: str) -> str:
    """Retain released v0 IDs; new IDs are distinct from persisted document/model schemas."""
    prefix = "fenolite" if version == "v0" and command in LEGACY else "fenolite.result"
    return f"{prefix}.{command}.{version}"
