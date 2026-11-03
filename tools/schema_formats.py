# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Explicit review decisions for concrete serialized IDs, including source-owned internal markers."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Literal


@dataclass(frozen=True)
class Format:
    classification: Literal["public", "internal"]
    reference: str | None
    note: str
    owner: Literal["formats", "model", "protocol", "result", "internal"] = "formats"


def public(reference: str, note: str = "User-authored input or agent-readable output.") -> Format:
    return Format("public", reference if ":" in reference else "fenolite.cli.file_formats:" + reference, note)


TEST_EVIDENCE_FORMATS: dict[str, tuple[str, ...]] = {
    "fenolite.conversion-comparison.v0": ("docs/evidence/conversion-comparison-c0319.json",),
    "fenolite.drawn-census.v0": ("tests/_drawn_corpus.py",),
    "fenolite.drawn-corpus-measurement.v0": ("docs/evidence/drawn-schematic.json",),
}
TEST_DIAGNOSTIC_MARKERS: dict[str, str] = {
    "authored-geometry-hashes-v0": "tests/_buildgeometry.py",
}


FORMATS: dict[str, Format] = {
    "fenolite.symbol-contexts.v0": public(
        "fenolite.cli.file_source_formats:SymbolContextsFile",
        "Public required c0327 authoring index; actual schema participates in every binding SHA.",
    ),
    "fenolite.conversion-comparison.v0": Format(
        "internal",
        None,
        "Recorded source-paired count-only diagnostic; native_tool and comparison limits stay explicit.",
        "internal",
    ),
    "fenolite.altium-observations.v0": public(
        "fenolite.cli.file_source_formats:AltiumObservationsFile",
        "Value-free observation output; native verdict stays unjudged.",
    ),
    "fenolite.altium-graduation.v0": Format("internal", None, "Packaged graduation policy.", "internal"),
    "fenolite.altium-kit-form.v0": Format("internal", None, "Kit-specific manual form.", "internal"),
    "fenolite.altium-kit-probes.v0": Format("internal", None, "Kit-specific probe input.", "internal"),
    "fenolite.altium-kit-run.v0": public("KitRunFile"),
    "fenolite.altium-kit.v0": public("KitFile"),
    "fenolite.altium-schematic-layout.v0": Format(
        "internal", None, "Protected native-layout observation used only by rebuilds.", "internal"
    ),
    "fenolite.artifacts.v0": public("fenolite.exports.manifest:Manifest"),
    "fenolite.assembly-template.v0": public("AssemblyTemplateFile"),
    "fenolite.base.v0": Format("internal", None, "Protected three-way merge base.", "internal"),
    "fenolite.block-golden.v0": public("BlockGoldenFile"),
    "fenolite.block-item.v0": public("BlockItemFile"),
    "fenolite.block-layout-base.v0": Format(
        "internal", None, "Protected copied-copper ownership base.", "internal"
    ),
    "fenolite.block-layout.v0": public("BlockLayoutFile"),
    "fenolite.block.v0": public("BlockFile"),
    "fenolite.build-record.v0": public("BuildRecordFile"),
    "fenolite.device.v0": public(
        "LegacyDeviceFile", "Legacy device dialect; existing v1 dispatch is retained."
    ),
    "fenolite.device.v1": public("DeviceFile", "Canonical device-record dialect, already v1."),
    "fenolite.drawing-spec.v0": public("DrawingSpecFile"),
    "fenolite.drawn-schematic.v0": public("DrawnSchematicFile"),
    "fenolite.drawn-census.v0": Format(
        "internal", None, "Per-row scratch test output from tests/_drawn_corpus.py.", "internal"
    ),
    "fenolite.drawn-corpus-measurement.v0": Format(
        "internal",
        None,
        "Historical count-only evidence; model_schema records the measured run, not a model document.",
        "internal",
    ),
    "fenolite.edits.v0": public("EditsFile"),
    "fenolite.export-preset.v0": public("ExportPresetFile"),
    "fenolite.family.v0": public(
        "FamilyRowsFile", "Enumerated row dialect; existing grammar dispatch is retained."
    ),
    "fenolite.family.v1": public("FamilyGrammarFile", "Grammar dialect, already v1."),
    "fenolite.import-provenance.v0": public("ImportProvenanceFile"),
    "fenolite.library-cache.v0": Format("internal", None, "Disposable library-download cache.", "internal"),
    "fenolite.library-import.v0": public("LibraryImportFile"),
    "fenolite.library-index.v0": public("LibraryIndexFile"),
    "fenolite.library-item.v0": public("LibraryItemFile"),
    "fenolite.library-metadata.v1": public(
        "LibraryMetadataFile", "Release metadata; the legacy library.v0 ID also names canonical model data."
    ),
    "fenolite.library-licences.v0": Format("internal", None, "Packaged licence policy.", "internal"),
    "fenolite.library-propose.v0": public("LibraryProposeFile"),
    "fenolite.library-releases.v0": Format("internal", None, "Packaged release-location policy.", "internal"),
    "fenolite.library-seed.v0": public("LibrarySeedFile"),
    "fenolite.library-sources.v0": public("LibrarySourcesFile"),
    "fenolite.library_sheets.v0": public("LibrarySheetsFile"),
    "fenolite.lock.v0": public("LockFile"),
    "fenolite.model.v0": Format("internal", None, "Schema-directory marker, not a document ID.", "internal"),
    "fenolite.model.v1": Format("internal", None, "Schema-directory marker, not a document ID.", "internal"),
    "fenolite.package.v0": public("PackageFile"),
    "fenolite.part.v0": public("PartFile"),
    "fenolite.pins.v0": public("PinsFile"),
    "fenolite.placement-request.v0": public("PlacementRequestFile"),
    "fenolite.placements.v0": public("PlacementsFile"),
    "fenolite.proposal.v0": public("ProposalFile"),
    "fenolite.provenance.v0": public("ProvenanceFile"),
    "fenolite.region.v1": Format("internal", None, "SVG rendering marker, not a JSON document.", "internal"),
    "fenolite.requirements.v0": public("RequirementsFile"),
    "fenolite.review.v0": public("ReviewFile"),
    "fenolite.role-copper.v0": public("RoleCopperFile"),
    "fenolite.roles.v0": public("RolesFile"),
    "fenolite.route-decisions.v0": public("fenolite.cli.file_source_formats:RouteDecisionsFile"),
    "fenolite.schematic-composition.v0": public("SchematicCompositionFile"),
    "fenolite.snapshot.v0": public("SnapshotFile"),
    "fenolite.supplier-lookup.v0": Format(
        "internal", None, "Python supplier negotiation marker, not a serialized document.", "internal"
    ),
    "fenolite.supplier-proposal.v0": public("fenolite.cli.file_source_formats:SupplierProposalFile"),
    "fenolite.view_library.v0": Format("internal", None, "Viewer document transport.", "internal"),
    "fenolite.view_overlay.v0": Format("internal", None, "Viewer overlay transport.", "internal"),
    "fenolite.view_proposals.v0": Format("internal", None, "Viewer proposal transport.", "internal"),
    "fenolite.view_roles.v0": Format("internal", None, "Viewer role transport.", "internal"),
    "fenolite.view_scene.v0": Format("internal", None, "Viewer scene transport.", "internal"),
    "fenolite.view_scene.v1": Format("internal", None, "Compact viewer scene transport.", "internal"),
    "fenolite.view_schematic.v0": Format("internal", None, "Viewer document transport.", "internal"),
    "fenolite.view_table.v0": Format("internal", None, "Viewer table transport.", "internal"),
    "fenolite.viewer_build.v1": Format("internal", None, "Viewer asset bundle stamp.", "internal"),
    # Prepared descriptors activate when the producing change is present in the source inventory.
    "fenolite.conformance.v1": public("fenolite.backends.matrix:Conformance"),
}

for name, reference in {
    "board": "fenolite.model.board:Board",
    "circuit": "fenolite.model.circuit:Circuit",
    "drawing_sheet": "fenolite.model.presentation:DrawingSheet",
    "findings": "fenolite.model.findings:Findings",
    "library": "fenolite.model.library:Library",
    "manufacturing": "fenolite.model.manufacturing:Manifest",
    "meta": "fenolite.model.design:DesignHeader",
    "panel_model": "fenolite.model.panel:Panel",
    "rules": "fenolite.model.rules:RuleSet",
    "schematic": "fenolite.model.schematic:SchematicSheet",
}.items():
    for version in ("v0", "v1"):
        FORMATS[f"fenolite.{name}.{version}"] = Format(
            "public", reference, "Canonical model target; c0218 owns activation and migration.", "model"
        )

for name, reference in {
    "envelope": "fenolite.cli.output:Envelope",
    "error": "fenolite.cli.errors:ErrorInfo",
}.items():
    for version in ("v0", "v1"):
        FORMATS[f"fenolite.{name}.{version}"] = Format("public", reference, "CLI protocol.", "protocol")

for name, ref in {
    "equivalent": "fenolite.api.schema:EquivalentReply",
    "convert": "fenolite.api.schema:ConvertReply",
    "verify-source": "fenolite.api.schema:VerifySourceReply",
    "import": "fenolite.importer.schema:ImportReply",
}.items():
    FORMATS[f"fenolite.{name}.v0"] = Format("public", ref, "Frozen legacy result schema.", "result")

for name in (
    "device.v0",
    "device.v1",
    "family.v0",
    "family.v1",
    "package.v0",
    "pins.v0",
    "part.v0",
    "proposal.v0",
):
    key = "fenolite." + name
    old = FORMATS[key]
    assert old.reference is not None
    FORMATS[key] = Format(
        old.classification, old.reference.replace(".file_formats:", ".file_record_formats:"), old.note
    )

# Equivalent v1 grammars are explicit mirror targets. Device/family already use v1 for a distinct
# dialect and retain both existing dispatches. Canonical model versions are owned by c0218.
for schema_id, decision in list(FORMATS.items()):
    if decision.owner == "formats" and schema_id.endswith(".v0") and schema_id[:-1] + "1" not in FORMATS:
        FORMATS[schema_id[:-1] + "1"] = Format(
            "public", decision.reference, "Prepared mirror; v0 remains readable."
        )

ID = re.compile(r"\bfenolite\.[a-z0-9_.-]+\.v[0-9]+\b")


def inventory(root: Path) -> dict[str, tuple[str, ...]]:
    found: dict[str, set[str]] = {}
    for path in sorted((root / "src/fenolite").rglob("*")):
        if path.suffix not in {".py", ".toml", ".json", ".ts", ".tsx", ".js", ".pas"} or not path.is_file():
            continue
        module = path.relative_to(root / "src").as_posix()
        for schema_id in ID.findall(path.read_text(encoding="utf-8")):
            found.setdefault(schema_id, set()).add(module)
    return {key: tuple(sorted(paths)) for key, paths in sorted(found.items())}


def markdown(rows: dict[str, tuple[str, ...]]) -> str:
    lines = [
        "| ID | Classification | Wire class or owner | Reason |",
        "|---|---|---|---|",
    ]
    for schema_id in rows:
        decision = FORMATS.get(schema_id)
        if decision is None:
            lines.append(f"| `{schema_id}` | **unclassified** | — | Requires an explicit decision. |")
        else:
            lines.append(
                f"| `{schema_id}` | {decision.classification} | `{decision.reference or decision.owner}` "
                f"| {decision.note} |"
            )
    return "\n".join(lines) + "\n"
