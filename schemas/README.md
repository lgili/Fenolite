# Schemas

Generated from wire dataclasses by `tools/gen_schemas.py`; do not edit schema files by hand.
The active CLI contract remains v0 until the 1.0 release. New result IDs have a `result`
namespace because command names also occur in persisted model/document IDs. Per-command
filenames remain `fenolite.<command>.<version>.json`. Existing v0 files retain their bytes.

Published result objects allow additions. Tests close declared object structures while
retaining documented, typed data maps. Four legacy v0 result files retain their original
closed form. Public standalone formats live under `formats/`; canonical model layers
remain under their model-version directory. Internal formats carry no release promise.

## Command results

| Command | v0 ID | Prepared v1 ID | Wire class |
|---|---|---|---|
| `analyze` | `fenolite.result.analyze.v0` | `fenolite.result.analyze.v1` | `fenolite.cli.results.analyses:AnalyzeResult` |
| `blocks` | `fenolite.result.blocks.v0` | `fenolite.result.blocks.v1` | `fenolite.cli.results.discovery:BlocksResult` |
| `bom` | `fenolite.result.bom.v0` | `fenolite.result.bom.v1` | `fenolite.cli.results.outputs:BomResult` |
| `build` | `fenolite.result.build.v0` | `fenolite.result.build.v1` | `fenolite.cli.results.writers:BuildResult` |
| `capabilities` | `fenolite.result.capabilities.v0` | `fenolite.result.capabilities.v1` | `fenolite.cli.results.discovery:CapabilitiesResult` |
| `catalog` | `fenolite.result.catalog.v0` | `fenolite.result.catalog.v1` | `fenolite.cli.results.discovery:CatalogResult` |
| `check` | `fenolite.result.check.v0` | `fenolite.result.check.v1` | `fenolite.cli.results.checks:CheckResult` |
| `convert` | `fenolite.convert.v0` | `fenolite.result.convert.v1` | `fenolite.cli.results.checks:ConvertResult` |
| `copper` | `fenolite.result.copper.v0` | `fenolite.result.copper.v1` | `fenolite.cli.results.edits:CopperResult` |
| `diff` | `fenolite.result.diff.v0` | `fenolite.result.diff.v1` | `fenolite.cli.results.checks:DiffResult` |
| `doctor` | `fenolite.result.doctor.v0` | `fenolite.result.doctor.v1` | `fenolite.cli.results.discovery:DoctorResult` |
| `edit` | `fenolite.result.edit.v0` | `fenolite.result.edit.v1` | `fenolite.cli.results.writers:EditResult` |
| `equivalent` | `fenolite.equivalent.v0` | `fenolite.result.equivalent.v1` | `fenolite.cli.results.checks:EquivalentResult` |
| `explain` | `fenolite.result.explain.v0` | `fenolite.result.explain.v1` | `fenolite.cli.results.discovery:ExplainResult` |
| `export` | `fenolite.result.export.v0` | `fenolite.result.export.v1` | `fenolite.cli.results.outputs:ExportResult` |
| `family` | `fenolite.result.family.v0` | `fenolite.result.family.v1` | `fenolite.cli.results.discovery:FamilyResult` |
| `fetch` | `fenolite.result.fetch.v0` | `fenolite.result.fetch.v1` | `fenolite.cli.results.discovery:FetchResult` |
| `fill` | `fenolite.result.fill.v0` | `fenolite.result.fill.v1` | `fenolite.cli.results.edits:FillResult` |
| `fmt` | `fenolite.result.fmt.v0` | `fenolite.result.fmt.v1` | `fenolite.cli.results.edits:FmtResult` |
| `get` | `fenolite.result.get.v0` | `fenolite.result.get.v1` | `fenolite.cli.results.discovery:GetResult` |
| `guide` | `fenolite.result.guide.v0` | `fenolite.result.guide.v1` | `fenolite.cli.results.discovery:GuideResult` |
| `impedance` | `fenolite.result.impedance.v0` | `fenolite.result.impedance.v1` | `fenolite.cli.results.analyses:ImpedanceResult` |
| `import` | `fenolite.import.v0` | `fenolite.result.import.v1` | `fenolite.cli.results.checks:ImportResult` |
| `init` | `fenolite.result.init.v0` | `fenolite.result.init.v1` | `fenolite.cli.results.discovery:InitResult` |
| `inspect` | `fenolite.result.inspect.v0` | `fenolite.result.inspect.v1` | `fenolite.cli.results.inspection:InspectResult` |
| `kit` | `fenolite.result.kit.v0` | `fenolite.result.kit.v1` | `fenolite.cli.results.writers:KitResult` |
| `library` | `fenolite.result.library.v0` | `fenolite.result.library.v1` | `fenolite.cli.results.discovery:LibraryResult` |
| `manifest` | `fenolite.result.manifest.v0` | `fenolite.result.manifest.v1` | `fenolite.cli.results.outputs:ManifestResult` |
| `mcp` | `fenolite.result.mcp.v0` | `fenolite.result.mcp.v1` | `fenolite.cli.results.discovery:McpResult` |
| `migrate` | `fenolite.result.migrate.v0` | `fenolite.result.migrate.v1` | `fenolite.cli.results.common:MigrationResult` |
| `models` | `fenolite.result.models.v0` | `fenolite.result.models.v1` | `fenolite.cli.results.discovery:ModelsResult` |
| `neighbors` | `fenolite.result.neighbors.v0` | `fenolite.result.neighbors.v1` | `fenolite.cli.results.analyses:NeighborsResult` |
| `net` | `fenolite.result.net.v0` | `fenolite.result.net.v1` | `fenolite.cli.results.analyses:NetResult` |
| `netlist` | `fenolite.result.netlist.v0` | `fenolite.result.netlist.v1` | `fenolite.cli.results.analyses:NetlistResult` |
| `pads` | `fenolite.result.pads.v0` | `fenolite.result.pads.v1` | `fenolite.cli.results.analyses:PadsResult` |
| `panel` | `fenolite.result.panel.v0` | `fenolite.result.panel.v1` | `fenolite.cli.results.writers:PanelResult` |
| `parity` | `fenolite.result.parity.v0` | `fenolite.result.parity.v1` | `fenolite.cli.results.checks:ParityResult` |
| `pick` | `fenolite.result.pick.v0` | `fenolite.result.pick.v1` | `fenolite.cli.results.discovery:PickResult` |
| `place` | `fenolite.result.place.v0` | `fenolite.result.place.v1` | `fenolite.cli.results.edits:PlaceResult` |
| `pnp` | `fenolite.result.pnp.v0` | `fenolite.result.pnp.v1` | `fenolite.cli.results.outputs:PnpResult` |
| `publish` | `fenolite.result.publish.v0` | `fenolite.result.publish.v1` | `fenolite.cli.results.edits:PublishResult` |
| `ready` | `fenolite.result.ready.v0` | `fenolite.result.ready.v1` | `fenolite.cli.results.checks:ReadyResult` |
| `refs` | `fenolite.result.refs.v0` | `fenolite.result.refs.v1` | `fenolite.cli.results.edits:RefsResult` |
| `region` | `fenolite.result.region.v0` | `fenolite.result.region.v1` | `fenolite.cli.results.analyses:RegionResult` |
| `render` | `fenolite.result.render.v0` | `fenolite.result.render.v1` | `fenolite.cli.results.outputs:RenderResult` |
| `restore` | `fenolite.result.restore.v0` | `fenolite.result.restore.v1` | `fenolite.cli.results.edits:RestoreResult` |
| `roles` | `fenolite.result.roles.v0` | `fenolite.result.roles.v1` | `fenolite.cli.results.analyses:RolesResult` |
| `roundtrip` | `fenolite.result.roundtrip.v0` | `fenolite.result.roundtrip.v1` | `fenolite.cli.results.checks:RoundtripResult` |
| `route` | `fenolite.result.route.v0` | `fenolite.result.route.v1` | `fenolite.cli.results.edits:RouteResult` |
| `silk` | `fenolite.result.silk.v0` | `fenolite.result.silk.v1` | `fenolite.cli.results.edits:SilkResult` |
| `skill` | `fenolite.result.skill.v0` | `fenolite.result.skill.v1` | `fenolite.cli.results.discovery:SkillResult` |
| `snapshot` | `fenolite.result.snapshot.v0` | `fenolite.result.snapshot.v1` | `fenolite.cli.results.edits:SnapshotResult` |
| `sync` | `fenolite.result.sync.v0` | `fenolite.result.sync.v1` | `fenolite.cli.results.writers:SyncResult` |
| `template` | `fenolite.result.template.v0` | `fenolite.result.template.v1` | `fenolite.cli.results.writers:TemplateResult` |
| `testpoints` | `fenolite.result.testpoints.v0` | `fenolite.result.testpoints.v1` | `fenolite.cli.results.analyses:TestpointsResult` |
| `tidy` | `fenolite.result.tidy.v0` | `fenolite.result.tidy.v1` | `fenolite.cli.results.edits:TidyResult` |
| `verify-source` | `fenolite.verify-source.v0` | `fenolite.result.verify-source.v1` | `fenolite.cli.results.checks:VerifySourceResult` |
| `view` | `fenolite.result.view.v0` | `fenolite.result.view.v1` | `fenolite.cli.results.inspection:ViewResult` |

## Source format inventory

Decided 2026-11-01: retain the public inputs and agent-readable outputs below. Viewer
transport, kit forms, protected merge bases and disposable caches remain internal.
Legacy device/family dialects retain their existing v0/v1 dispatch. The model activation
and canonical-folder migration belong to c0218. Frozen model-v0 bytes come from the
final model-0 source recorded in `frozen-model-v0.json`; prepared CLI-v0 targets are
tracked separately in `frozen-v0.json` while the active CLI writer remains v0.

| ID | Classification | Wire class or owner | Reason |
|---|---|---|---|
| `fenolite.altium-graduation.v0` | internal | `internal` | Packaged graduation policy. |
| `fenolite.altium-kit-form.v0` | internal | `internal` | Kit-specific manual form. |
| `fenolite.altium-kit-probes.v0` | internal | `internal` | Kit-specific probe input. |
| `fenolite.altium-kit-run.v0` | public | `fenolite.cli.file_formats:KitRunFile` | User-authored input or agent-readable output. |
| `fenolite.altium-kit.v0` | public | `fenolite.cli.file_formats:KitFile` | User-authored input or agent-readable output. |
| `fenolite.altium-model-heights.v0` | internal | `internal` | Stored heights of Altium model bodies in a KiCad board property (c0449). |
| `fenolite.altium-model-ids.v0` | internal | `internal` | Record IDs and checksums of Altium models in a KiCad board property (c0449). |
| `fenolite.altium-observations.v0` | public | `fenolite.cli.file_source_formats:AltiumObservationsFile` | Value-free observation output; native verdict stays unjudged. |
| `fenolite.altium-polygon-arcs.v0` | internal | `internal` | Arc vertices of Altium polygons in a KiCad board property (c0463). |
| `fenolite.altium-rules.v0` | internal | `internal` | Rule records of an Altium source in a KiCad board property (c0434). |
| `fenolite.altium-rules.v1` | internal | `internal` | Rule records of an Altium source in a KiCad board property (c0434, keyed by content in c0457). |
| `fenolite.altium-rules.v2` | internal | `internal` | Rule records of an Altium source in a KiCad board property (c0457, conditions compared parsed). |
| `fenolite.altium-schematic-layout.v0` | internal | `internal` | Protected native-layout observation used only by rebuilds. |
| `fenolite.artifacts.v0` | public | `fenolite.exports.manifest:Manifest` | User-authored input or agent-readable output. |
| `fenolite.assembly-template.v0` | public | `fenolite.cli.file_formats:AssemblyTemplateFile` | User-authored input or agent-readable output. |
| `fenolite.base.v0` | internal | `internal` | Protected three-way merge base. |
| `fenolite.block-golden.v0` | public | `fenolite.cli.file_formats:BlockGoldenFile` | User-authored input or agent-readable output. |
| `fenolite.block-golden.v1` | public | `fenolite.cli.file_formats:BlockGoldenFile` | Prepared mirror; v0 remains readable. |
| `fenolite.block-item.v0` | public | `fenolite.cli.file_formats:BlockItemFile` | User-authored input or agent-readable output. |
| `fenolite.block-layout-base.v0` | internal | `internal` | Protected copied-copper ownership base. |
| `fenolite.block-layout.v0` | public | `fenolite.cli.file_formats:BlockLayoutFile` | User-authored input or agent-readable output. |
| `fenolite.block.v0` | public | `fenolite.cli.file_formats:BlockFile` | User-authored input or agent-readable output. |
| `fenolite.build-record.v0` | public | `fenolite.cli.file_formats:BuildRecordFile` | User-authored input or agent-readable output. |
| `fenolite.conformance.v1` | public | `fenolite.backends.matrix:Conformance` | User-authored input or agent-readable output. |
| `fenolite.device.v0` | public | `fenolite.cli.file_record_formats:LegacyDeviceFile` | Legacy device dialect; existing v1 dispatch is retained. |
| `fenolite.device.v1` | public | `fenolite.cli.file_record_formats:DeviceFile` | Canonical device-record dialect, already v1. |
| `fenolite.drawing-spec.v0` | public | `fenolite.cli.file_formats:DrawingSpecFile` | User-authored input or agent-readable output. |
| `fenolite.drawn-schematic.v0` | public | `fenolite.cli.file_formats:DrawnSchematicFile` | User-authored input or agent-readable output. |
| `fenolite.edits.v0` | public | `fenolite.cli.file_formats:EditsFile` | User-authored input or agent-readable output. |
| `fenolite.envelope.v0` | public | `fenolite.cli.output:Envelope` | CLI protocol. |
| `fenolite.equivalent.v0` | public | `fenolite.api.schema:EquivalentReply` | Frozen legacy result schema. |
| `fenolite.export-preset.v0` | public | `fenolite.cli.file_formats:ExportPresetFile` | User-authored input or agent-readable output. |
| `fenolite.family.v0` | public | `fenolite.cli.file_record_formats:FamilyRowsFile` | Enumerated row dialect; existing grammar dispatch is retained. |
| `fenolite.family.v1` | public | `fenolite.cli.file_record_formats:FamilyGrammarFile` | Grammar dialect, already v1. |
| `fenolite.import-provenance.v0` | public | `fenolite.cli.file_formats:ImportProvenanceFile` | User-authored input or agent-readable output. |
| `fenolite.import.v0` | public | `fenolite.importer.schema:ImportReply` | Frozen legacy result schema. |
| `fenolite.library-cache.v0` | internal | `internal` | Disposable library-download cache. |
| `fenolite.library-import.v0` | public | `fenolite.cli.file_formats:LibraryImportFile` | User-authored input or agent-readable output. |
| `fenolite.library-index.v0` | public | `fenolite.cli.file_formats:LibraryIndexFile` | User-authored input or agent-readable output. |
| `fenolite.library-item.v0` | public | `fenolite.cli.file_formats:LibraryItemFile` | User-authored input or agent-readable output. |
| `fenolite.library-licences.v0` | internal | `internal` | Packaged licence policy. |
| `fenolite.library-metadata.v1` | public | `fenolite.cli.file_formats:LibraryMetadataFile` | Release metadata; the legacy library.v0 ID also names canonical model data. |
| `fenolite.library-propose.v0` | public | `fenolite.cli.file_formats:LibraryProposeFile` | User-authored input or agent-readable output. |
| `fenolite.library-releases.v0` | internal | `internal` | Packaged release-location policy. |
| `fenolite.library-seed.v0` | public | `fenolite.cli.file_formats:LibrarySeedFile` | User-authored input or agent-readable output. |
| `fenolite.library-sources.v0` | public | `fenolite.cli.file_formats:LibrarySourcesFile` | User-authored input or agent-readable output. |
| `fenolite.library_sheets.v0` | public | `fenolite.cli.file_formats:LibrarySheetsFile` | User-authored input or agent-readable output. |
| `fenolite.lock.v0` | public | `fenolite.cli.file_formats:LockFile` | User-authored input or agent-readable output. |
| `fenolite.model.v1` | internal | `internal` | Schema-directory marker, not a document ID. |
| `fenolite.package.v0` | public | `fenolite.cli.file_record_formats:PackageFile` | User-authored input or agent-readable output. |
| `fenolite.package.v1` | public | `fenolite.cli.file_record_formats:PackageFile` | Prepared mirror; v0 remains readable. |
| `fenolite.part.v0` | public | `fenolite.cli.file_record_formats:PartFile` | User-authored input or agent-readable output. |
| `fenolite.part.v1` | public | `fenolite.cli.file_record_formats:PartFile` | Prepared mirror; v0 remains readable. |
| `fenolite.pins.v0` | public | `fenolite.cli.file_record_formats:PinsFile` | User-authored input or agent-readable output. |
| `fenolite.pins.v1` | public | `fenolite.cli.file_record_formats:PinsFile` | Prepared mirror; v0 remains readable. |
| `fenolite.placement-request.v0` | public | `fenolite.cli.file_formats:PlacementRequestFile` | User-authored input or agent-readable output. |
| `fenolite.placement-request.v1` | public | `fenolite.cli.file_formats:PlacementRequestFile` | Prepared mirror; v0 remains readable. |
| `fenolite.placements.v0` | public | `fenolite.cli.file_formats:PlacementsFile` | User-authored input or agent-readable output. |
| `fenolite.proposal.v0` | public | `fenolite.cli.file_record_formats:ProposalFile` | User-authored input or agent-readable output. |
| `fenolite.proposal_controls.v0` | internal | `internal` | Nested route-result regeneration controls read by the viewer (c0369). |
| `fenolite.provenance.v0` | public | `fenolite.cli.file_formats:ProvenanceFile` | User-authored input or agent-readable output. |
| `fenolite.region.v1` | internal | `internal` | SVG rendering marker, not a JSON document. |
| `fenolite.requirements.v0` | public | `fenolite.cli.file_formats:RequirementsFile` | User-authored input or agent-readable output. |
| `fenolite.review-content.v1` | internal | `internal` | Content-hash domain of a library review sheet, not a document (c0415). |
| `fenolite.review.v0` | public | `fenolite.cli.file_formats:ReviewFile` | User-authored input or agent-readable output. |
| `fenolite.role-copper.v0` | public | `fenolite.cli.file_formats:RoleCopperFile` | User-authored input or agent-readable output. |
| `fenolite.roles.v0` | public | `fenolite.cli.file_formats:RolesFile` | User-authored input or agent-readable output. |
| `fenolite.route-bundle.v0` | internal | `internal` | Content-hash domain of a route bundle id, not a document (c0367). |
| `fenolite.route-decisions.v0` | public | `fenolite.cli.file_source_formats:RouteDecisionsFile` | User-authored input or agent-readable output. |
| `fenolite.schematic-composition.v0` | public | `fenolite.cli.file_formats:SchematicCompositionFile` | User-authored input or agent-readable output. |
| `fenolite.snapshot.v0` | public | `fenolite.cli.file_formats:SnapshotFile` | User-authored input or agent-readable output. |
| `fenolite.supplier-lookup.v0` | internal | `internal` | Python supplier negotiation marker, not a serialized document. |
| `fenolite.supplier-proposal.v0` | public | `fenolite.cli.file_source_formats:SupplierProposalFile` | User-authored input or agent-readable output. |
| `fenolite.symbol-contexts.v0` | public | `fenolite.cli.file_source_formats:SymbolContextsFile` | Public required c0327 authoring index; actual schema participates in every binding SHA. |
| `fenolite.view_library.v0` | internal | `internal` | Viewer document transport. |
| `fenolite.view_overlay.v0` | internal | `internal` | Viewer overlay transport. |
| `fenolite.view_proposals.v0` | internal | `internal` | Viewer proposal transport. |
| `fenolite.view_roles.v0` | internal | `internal` | Viewer role transport. |
| `fenolite.view_scene.v0` | internal | `internal` | Viewer scene transport. |
| `fenolite.view_scene.v1` | internal | `internal` | Compact viewer scene transport. |
| `fenolite.view_schematic.v0` | internal | `internal` | Viewer document transport. |
| `fenolite.view_table.v0` | internal | `internal` | Viewer table transport. |
| `fenolite.viewer_build.v1` | internal | `internal` | Viewer asset bundle stamp. |

## Test and evidence format inventory

Decided 2026-11-02: these IDs occur outside the production source scanner. They describe
internal test/evidence artifacts, with no public schema or reader promise. Their v0 suffix
and any observed `model_schema` are independent of canonical migration; recorded bytes
and measured native limitations remain unchanged.

| ID | Classification | Wire class or owner | Reason |
|---|---|---|---|
| `fenolite.conversion-comparison.v0` | internal | `internal` | Recorded source-paired count-only diagnostic; native_tool and comparison limits stay explicit. |
| `fenolite.drawn-census.v0` | internal | `internal` | Per-row scratch test output from tests/_drawn_corpus.py. |
| `fenolite.drawn-corpus-measurement.v0` | internal | `internal` | Historical count-only evidence; model_schema records the measured run, not a model document. |

Bounded internal diagnostic child markers are not schema IDs or canonical model versions:

- `authored-geometry-hashes-v0` from `tests/_buildgeometry.py`: test diagnostics only; no public reader/schema promise.
