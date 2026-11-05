## 0. Entry check

- [x] 0.1 Read `openspec list`, the living specs `design-equivalence` and `corpus-policy`, and the state of
  c0275, c0276, c0277 and c0279. Write under this task the date, the base commit, and:
  - whether c0275 is archived, with the name of its importer entry and the schema and path of the
    `PROVENANCE.json` it creates (phase 5 waits for it);
  - whether c0276 is archived, with the names of `DrawnSchematic`, `extract` and `resolve` (task 2.4 waits
    for it);
  - which open change holds a delta of "Equivalence package", "Differences are located", "Equivalent
    command", "Level 5 in the equivalent command" or "Equivalence documentation"; if one was archived,
    regenerate the MODIFIED blocks from the living text;
  - whether `verify-source`, `fenolite.view.fidelity` and the use `rtf` are free names;
  - the maintainer's answers to the open questions of `design.md`.
  Entry check, 2026-10-29, base `7ed71d3f` (integration branch with c0246, c0247, c0249): c0275 is not
  archived and not merged (no importer `import --to python`, no `PROVENANCE.json` writer; phase 5 waits);
  c0276 is not archived and not merged (no `DrawnSchematic`, `extract`, `resolve`; task 2.4 waits); no other
  open change holds a delta of the five MODIFIED requirements; `verify-source`, `fenolite.view.fidelity` and
  the use `rtf` were free names; the open questions are decided in `design.md` (the maintainer delegated
  them). `make check-fast` passed on 2026-10-29; `openspec validate` cannot run here (no `openspec` CLI in
  this environment), so the task stays open for that one proof.

  Continuation entry — 2026-11-01, base `eabbeeef38f54c0ff14ac2cbb0bd2234da464ff1`:
  c0275/c0276/c0277/c0279 remain active, but their actual surfaces are present. c0275's CLI entry is
  `cli.cmd_import`, with `importer.source.read_kicad`, `importer.emit.emit`, and the emitted
  `PROVENANCE.json` of schema `fenolite.import-provenance.v0` (the library wraps it in
  `fenolite.provenance.v0`). c0276 supplies `model.drawn.DrawnSchematic`,
  `backends.kicad.drawn.extract`/`extract_with_pins`, and `model.drawn_connect.resolve`.
  Source-sheet/symbol import preservation is unfinished on this base and owned separately; its actual
  signed prerequisite is needed for positive all-level round trips. The five MODIFIED requirements
  remain owned only by c0278; no archived owner requires rebasing their text. The names `verify-source`,
  `view.fidelity` and `rtf` are already claimed by this change's current implementation/preparation,
  not free for an unrelated change. The five dated decisions of 2026-10-29 remain adopted.
  Strict validation now passes. Task 0.1 remains open because its literal proof includes the coordinating
  `make check-fast`; focused proofs do not substitute for that full fast gate.

  Proof: `openspec validate c0278-fidelity-proof --strict`; `make check-fast`.

  Entry refresh 2026-11-02, integration base `697cdf02b39c570b7827bd2b7b5419dfcf6bdea6`:
  c0275/c0276/c0277/c0279 remain active and implemented. Import enters through
  cli.cmd_import, importer.source.read_kicad and importer.emit.emit, writing PROVENANCE.json
  with fenolite.import-provenance.v0; library provenance wraps that in fenolite.provenance.v0.
  c0276 now supplies actual source-drawing/native-symbol preservation as well as
  model.drawn.DrawnSchematic, backends.kicad.drawn.extract/extract_with_pins and
  model.drawn_connect.resolve. The earlier missing-source-drawing entry is superseded by
  these implemented APIs, not by a claim that every external round trip passes. Only c0278
  holds the five listed equivalence MODIFIED requirements; no newly archived owner requires
  regeneration. verify-source, view.fidelity and corpus use rtf are already owned here.
  Explicit equivalent level S is implemented; integer/default result contracts remain separate.
  All five accepted recommendations remain 1000 ppm configurable masks, a later independent
  plot oracle, no merged-segment library-proof relaxation, reviewed acceptance changes, and
  locked as a notice. Pending corpus ratchets, native GUI/application gates, releases and
  exact-head CI stay open; no new accepted count or third-party source fact is asserted.

  Available proof: `openspec validate c0278-fidelity-proof --strict` passes without warnings
  (OpenSpec 1.16.0).
  The literal `make check-fast` is not run by this worker and has no applicable passing
  serialized receipt yet. Task 0.1 remains unchecked for that actual proof; independent
  CI, native/manual and release criteria are unchanged.

  Entry proof completed 2026-11-02 on `ea762411cbb24bc5f9ba5a16d8b372ae7c720568`: root
  ran the serialized `make check-fast` from 09:45:03 to 10:17:02 UTC, exit 0
  (19564 passed, 55 skipped; JUnit records zero failures/errors). Fresh OpenSpec
  1.16.0 strict validation of this change also passes without warnings. The
  `a85f7846` entry review was checked against this source: dependencies remain
  active, no new archival requires rebasing a delta, and the named APIs, accepted
  decisions and current dispatcher/record contracts still apply.
  This dated proof supersedes the earlier missing-fast-gate blocker only.
  Independent CI, native/manual, corpus, external-library and release criteria
  remain unchanged. The source-bound receipt, log and JUnit hashes are recorded
  in [the integration validation record](../c0319-integration-repairs/validation.md).

## 1. Package constants and kinds

- [x] 1.1 Extend `LEVELS`, `LEVEL_NAMES`, `PRESENTATION_LEVEL`, `SCHEMATIC_LEVEL`, `Difference.level`, the
  kinds table of `levels.py`, `EQUIVALENCE_CODES` and `explain.toml` (scenarios "Kinds table is closed",
  "Levels 6 and 7 on request"; the existing scenarios of "Equivalence package" keep passing). Proof:
  `uv run pytest tests/unit/checks/equivalence/test_codes.py tests/unit/checks/equivalence/test_package.py -q`.
  Done 2026-10-29: `LEVELS` 1 to 7, `PRESENTATION_LEVEL`, `SCHEMATIC_LEVEL`, `ALL_LEVEL_NAMES`, the kinds
  table with the placeholders `field` and `item`, the codes and their `explain.toml` entries; proof passed.
- [x] 1.2 Register `H-K-FID-ZONE-OUTLINE` and `H-K-FID-PLOT-AGREE` in `docs/hypotheses.md`. Proof:
  `uv run pytest tests/unit/test_hypotheses_register.py -q`.
  Done 2026-10-29: both rows rewritten with their statement, settling test and criterion; proof passed.

## 2. Levels

- [x] 2.1 Add `strict.py` and `strict=` (scenarios of "Level 5 strict compares copper items" and "Level 5
  strict matching"; "Five planted edits" keeps passing). Proof:
  `uv run pytest tests/unit/checks/equivalence/test_strict.py tests/unit/checks/equivalence/test_level5.py -q`.
  Done 2026-10-29: `strict.py` (`compare_strict`, `STRICT_RULE`), `compare_designs(..., strict=True)`;
  proof passed.
- [x] 2.2 Add `rules.py`, level 6 (scenarios of "Level 6 compares rules"). Proof:
  `uv run pytest tests/unit/checks/equivalence/test_level6.py -q`.
  Done 2026-10-29: `rules.py` (`level_rules`, `fields`); proof passed.
- [x] 2.3 Add `shapes.py` and level 7 (scenarios of "Level 7 compares exact geometry" and "Level 7
  normalisation"). Proof: `uv run pytest tests/unit/checks/equivalence/test_level7.py tests/unit/checks/equivalence/test_shapes.py -q`.
  Done 2026-10-29: `shapes.py` (normalisation and `level_geometry`); proof passed.
- [x] 2.4 Add `drawn.py` with `compare_drawn` (scenarios of "Level S compares drawn schematics"); waits for
  c0276. Proof: `uv run pytest tests/unit/checks/equivalence/test_level_s.py -q`.
  Open 2026-10-29: waits for c0276 (`DrawnSchematic`, `extract`, `resolve`), not merged in the integration
  branch. Until then `equivalent --level S` exits 2 naming side `a`, and `verify-source` skips level S with
  the reason `drawn-unavailable`.
  Done 2026-10-30 (with c0276's open tasks): `checks/equivalence/drawn.py` (`compare_drawn`, exported by the
  package) and `cli/_drawn_level.py`; `verify-source` runs level S on KiCad originals (sides joined by
  reference, each named by the build's `fenolite.path`), and `drawn-unavailable` now means a side's sheets were
  not read. The authored `sensor` fixture is `equal` at S; `tests/unit/cli/test_verify_source_drawn.py` proves
  the drawn fixtures `flat`, `hier` and `repeat` and a removed junction. Proof passed (12 tests). Not done:
  `fenolite equivalent --level S` still exits 2, since `fenolite.equivalent.v0` types `level` as an integer.
- [x] 2.5 Add `view/fidelity.py` with `render_masks` and `compare_masks`, and the level-8 kinds (scenarios
  "Grid shared", "Located change", "Same board, no difference", "Moved logo on silkscreen"). Proof:
  `uv run pytest tests/unit/view/test_fidelity_masks.py -q`.
  Done 2026-10-29: `view/fidelity.py` (`render_masks`, `compare_masks`, `compare_scenes`, `board_scene`);
  `view` imports no `checks`, so it gives plain findings that `cli/_presentation.py` turns into the level's
  differences; proof passed.

## 3. The equivalent command

- [x] 3.1 Add `--level 6|7|8|S`, `--strict`, `--pixel-ppm` and `--render-pitch-um` to
  `cmd_equivalent.py` and the API, and update `schemas/fenolite.equivalent.v0.json` (scenarios "Geometry
  level on request", "Schematic level on a board", "Strict copy", "Usage errors"; every existing scenario of
  "Equivalent command" keeps its output). Proof:
  `uv run pytest tests/unit/cli/test_equivalent_cmd.py tests/unit/api/test_equivalence_api.py tests/consistency -k equivalent -q`.
  Done 2026-10-29: `--level 1..8|S`, `--strict`, `--pixel-ppm`, `--render-pitch-um`;
  `fenolite.api.equivalent(..., strict=, presentation=)` (level 8 needs the renderer of `view`, which `api`
  may not import, so the caller passes it); schema regenerated; proof passed.

- [x] 3.2 Finish the existing S prerequisite through actual schematic extraction: accept explicit `level="S"` in the API/CLI, compare only the schematic level, widen the active v0 result types additively, and preserve every integer/default result byte. Reuse the shared actual-sheet comparator without an API-to-CLI import edge. Prove raw schematic, project, hierarchy, bus, Repeat, missing-side, planted junction and exact historical integer results; coordinate the final shape with the result-contract owner before freeze. Proof: `uv run pytest tests/unit/api/test_equivalence_api.py tests/unit/cli/test_equivalent_cmd.py tests/unit/api/test_equivalent_s_api.py tests/unit/cli/test_equivalent_s_cmd.py tests/unit/checks/equivalence/test_level_s.py tests/consistency -k equivalent -q`; generated schemas and the typed public API examples pass.

  Reopened 2.4 and 3.1 on 2026-11-01: their historical integer/engine proofs remain recorded, but actual
  `equivalent --level S` still refuses every input on this base. They close only after the authored and
  available public S cases actually pass, without accepting source drawing losses. Root authorizes this
  prerequisite before the last-v0 freeze; the result-contract owner prepares the same exact union shape.

## 4. verify-source

- [x] 4.1 Author `tests/data/fidelity/sensor/` (a KiCad 10 project authored for Fenolite, CC0, saved by the
  KiCad GUI per "Project fixtures saved by the KiCad GUI": four layers, net classes, a custom rule, zones,
  arcs, vias, board text, a drawn hierarchical schematic with a bus, a repeated sheet and junctions) and its
  converted script `tests/data/fidelity/sensor_code/`; declare both in `tests/data/MANIFEST.toml`. Until
  the GUI save, an authored text fixture stands in and task 4.1 stays open. Proof:
  `uv run pytest tests/residue tests/corpus/test_manifest.py -q`.
  Open 2026-10-29: `tests/data/fidelity/sensor_code/` (the script) and `tests/data/fidelity/sensor/` are
  authored and declared; `sensor/` is the target-10 build of the script, a text stand-in until a KiCad GUI
  save (maintainer). It holds four layers, net classes, a custom rule, a zone, an arc and vias, board text
  and a flat schematic; the hierarchical drawn schematic with a bus waits for c0276. The proof passes.
- [x] 4.1a Complete the sensor's actual hierarchy/bus/nonempty repeated sheet, preserve original physical cases, declare new authored dependencies and strengthen copy/fixture/import tests. Proof: focused verify-source tests and manifest; target10 strict levels1–8+S.
- [x] 4.1b Prove native10 net partition and import/build, then supply exact prepared project to root for real GUI save. No GUI proof is inferred from generated files. Proof: source-bound native receipts and root GUI follow-up.
- [x] 4.2 Add `cmd_verify_source.py`: inputs, the temporary build, the levels, tolerances, result schema
  `fenolite.verify-source.v0`, exit codes and `ISSUE_CODES` (scenarios of "Verify-source command",
  "Verify-source inputs", "Build in a temporary folder", "Verify-source levels", "Verify-source
  tolerances", "Verify-source result", "Verify-source exit codes", "Fidelity issue codes"). Proof:
  `uv run pytest tests/unit/cli/test_verify_source.py tests/consistency -k verify_source -q`.
  Done 2026-10-29: `cmd_verify_source.py`, `schemas/fenolite.verify-source.v0.json`, `ISSUE_CODES` with
  `explain.toml` entries; proof passed.
- [x] 4.3 Accepted differences, `accepted_rules`, unused entries, `--record` and `--accept` (scenarios of
  "Accepted differences in the provenance file", "Unused accepted differences", "Recording the proof").
  Proof: `uv run pytest tests/unit/cli/test_verify_source.py -k "accepted or record" tests/unit/checks/equivalence/test_exclusions.py -q`.
  Done 2026-10-29: `accepted_rules` in `exclusions.py`, unused entries, `--record` and `--accept`; proof
  passed.

## 5. Round-trip category (waits for c0275)

- [x] 5.1 Add `tests/_fidelity.py::roundtrip` and `tests/fidelity/` over the authored fixtures (scenarios
  "Authored fixtures", "A regression shows"), and add `tests/fidelity` to the hermetic set of
  `make check-fast`. Proof: `uv run pytest tests/fidelity -q`; `make check-fast`.
  Open 2026-10-29: waits for c0275 (`fenolite import --to python`), not merged.

  Completed 2026-11-02: `uv run pytest tests/fidelity -q` passes all 14 cases.
  The actual importer, explicit build and every strict fidelity level run on
  the authored sensor/hierarchy/bus/repeated-sheet stand-ins; the planted redundant
  junction deletion remains visible. `make check-fast` includes this category and
  passed on `ea762411cbb24bc5f9ba5a16d8b372ae7c720568` (19564 passed,
  55 skipped, exit 0). This closes the hermetic category only: the GUI save in
  task 4.1, native application/zone proof in 6.1, pending corpus ratchets in 6.2
  and exact-head CI remain open. No original, acceptance count or tolerance changes.

- [x] 5.2 Tag the demo project rows with `rtf` by the licence rule and add the manifest check (scenarios of
  "Round-trip fidelity use"). Proof: `uv run pytest tests/corpus/test_manifest.py -k rtf -q`.
  Open 2026-10-29: the `rtf` use and its manifest check come with the round trip, which waits for c0275.

## 6. Evidence

- [x] 6.1 KiCad CI job: upgrade and refill the authored fixture with `kicad-cli` and compare at level 7
  (`H-K-FID-ZONE-OUTLINE`); raise the row to `KICAD-VERIFIED (9.0.x, 10.0.x)` only after the job passes.
  Proof: the KiCad job of the commit on GitHub CI is green;
  `uv run pytest tests/kicad/fidelity/test_zone_outline.py -rA` there.
  Open 2026-10-29: needs the KiCad CI job and the GUI-saved fixture of task 4.1.
  2026-11-04, local KiCad 10.0.6 (macOS): `uv run pytest tests/kicad/fidelity/test_zone_outline.py -rA` passes on the
  GUI-saved fixture of task 4.1. Level 7 has no differences after `pcb upgrade --force` and a refill, and the original's
  bytes are unchanged. The kicad-10 CI job runs it with `tests/kicad`. The row stays `INFERRED`. `pcb upgrade` exists in
  10.0 only (H-K-FMT-RESAVE, KICAD-VERIFIED), so the test skips on 9.0.9 and cannot measure the row's "9.0.x" part.
  `docs/hypotheses.md` says so. Open: the green kicad-10 job on the exact commit, and a maintainer decision on the 9.0.x
  part of the target level.
  - 2026-11-05 (coordinator, maintainer's delegation of 2026-11-04): `tests/kicad/fidelity/test_zone_outline.py` passed in kicad-10 shard 1 (10.0.6), CI 41968083051 on 5f46b8d7 (cac/lote-16): every required job green, including unit on five platforms, kicad-9, kicad-10 shards 0-3, routing 9/10, viewer, mcp, wheel, complete test coverage and ci-complete. Decision (c0401): H-K-FID-ZONE-OUTLINE targets 10.0.x only, since 9.0 has no `pcb upgrade` (H-K-FMT-RESAVE); the row is raised to `KICAD-VERIFIED (10.0.x)`.
- [x] 6.2 Add `tests/kicad/fidelity/test_corpus_roundtrip.py` and `accepted.toml`, run it on the `rtf`
  rows, record counts and timings in `docs/evidence/fidelity.md` (scenarios "Demo rows", "Ratchet", "Page
  matches the run"). Proof: `uv run pytest tests/kicad/fidelity -rA` in the KiCad job;
  `uv run pytest tests/unit/test_fidelity_docs.py -q`.
  Open 2026-10-29: needs c0275 and the `rtf` rows (tasks 5.1 and 5.2).
  2026-11-04, on `468d8a61` with local KiCad 10.0.6: a strict census of the 24 `rtf` roots ran in 549.09 s. Ten rows had
  no difference at any level they reached. Each became a measured `[[row]]` with `counts = {}` (attribution `fenolite`,
  `[run]` 0.7.0.dev0 / 2026-11-04), so any new difference fails the ratchet. The other 14 stay `pending` with their
  2026-11-04 outcome. Five differ with undecided attribution, five imports were refused, one `verify-source` was refused
  (FEN-3004), the malformed input was refused, and two heavy rows were skipped. Counts and timings are in
  `docs/evidence/fidelity.md` ("Strict census — 2026-11-04"). `FENOLITE_REQUIRE=kicad,corpus uv run pytest tests/kicad/fidelity -rA`:
  11 passed, 14 skipped, 570.67 s. `uv run pytest tests/unit/test_fidelity_docs.py -q` passes. The kicad-10 job now also fetches
  `--uses rtf`. Open: the same run in the kicad-10 CI job on the exact commit, and the attribution review of the five differing
  rows (not decided here).
  - 2026-11-05 (coordinator, maintainer's delegation of 2026-11-04): `tests/kicad/fidelity/test_corpus_roundtrip.py`: 10 passed and 14 pending skips in kicad-10 shard 2, as in the local census; CI 41968083051 on 5f46b8d7 (cac/lote-16): every required job green, including unit on five platforms, kicad-9, kicad-10 shards 0-3, routing 9/10, viewer, mcp, wheel, complete test coverage and ci-complete. The attribution of the differing rows, the refusals and the heavy rows move to c0401.

## 7. Documentation and guide

- [x] 7.1 Write `docs/fidelity.md`; update `docs/equivalence.md` (eight levels and S), `docs/cli-contract.md`
  (`verify-source`, the new `equivalent` options) and `docs/roadmap.md` (scenarios "Codes are documented",
  "Codes documented"). Proof: `uv run pytest tests/consistency tests/unit/checks/equivalence/test_codes.py -k docs -q`.
  Done 2026-10-29: `docs/fidelity.md`, `docs/equivalence.md` (levels 6 to 8, S, strict),
  `docs/cli-contract.md` (`equivalent`, `verify-source`), `docs/roadmap.md`; proof passed.
- [x] 7.2 Agent guide (AGENTS.md rule 6): a tested line for `verify-source` and its codes, and for the new
  levels of `equivalent`, on the page `checks`; run `uv run python tools/gen_agent_guide.py` after the
  argument change. Proof: `uv run python tools/gen_agent_guide.py`; `uv run pytest tests/unit/agent/test_pages.py -q`.
  Done 2026-10-29: the page `checks` teaches `verify-source`, its codes and the new levels; `commands.md`
  regenerated; proof passed.

## 8. Changelog and CI

- [x] 8.1 `CHANGELOG.md`: one entry under `## [Unreleased]`. This waits until `dev` is at `0.7.0.dev0`,
  because the v0.6 guard requires `[Unreleased]` to be empty. Proof: `uv run pytest tests/unit -k changelog -q`.
  Open 2026-10-29: waits for `0.7.0.dev0` (the v0.6 guard needs `[Unreleased]` empty).
  Done 2026-10-29: entry "Fidelity proof" under `## [Unreleased]` › `### Added` on `circuits-as-code`;
  `uv run pytest tests/unit -k changelog -q` passed.
- [x] 8.2 `make check-fast` passes locally; publish the batch to its working branch and confirm the unit
  and KiCad jobs on the exact commit. Proof: `make check-fast`; the required CI jobs are green on the
  commit.
  Open 2026-10-29: `make check-fast PYTEST_WORKERS=2` passed locally; CI runs with the batch.
  - 2026-11-05 (coordinator, maintainer's delegation of 2026-11-04): CI 41968083051 on 5f46b8d7 (cac/lote-16): every required job green, including unit on five platforms, kicad-9, kicad-10 shards 0-3, routing 9/10, viewer, mcp, wheel, complete test coverage and ci-complete.

## Continuation proof — 2026-11-01

Task 5.2: the 24 board roots and 150 declared inputs carry `rtf` by the shipped board-library licence
allow-list, including both refs and heavy inputs. NC/ND and restricted variants are rejected. The exact
manifest `-k rtf` proof passes: 11 passed, 49 deselected. Real inputs remain fetched-only; the new residue
case emits a cached row into a temporary tool-tree stand-in and reports its row id. No third-party file
or derived code is committed.

Task 5.1's implementation now includes the source-dependent authored tests after prerequisite
`81f3bb1d`. The strict helper imports, explicitly builds, and verifies all 1–8+S levels without
lossy/acceptance/tolerance flags, with original-byte snapshots. The actual sensor, hierarchy, bus and
Repeat comparisons pass all nine levels with copper compared. A passing all-level control precedes the
redundant-junction negative, which then reports exactly one missing junction at S. The sensor's earlier
64S+1presentation failure remains historical evidence of the old source path. The task stays open:
its literal proof also includes the coordinating full fast gate, which has not run on this batch.

Tasks 6.1 and 6.2 remain open. The native upgrade/refill test is prepared, but `kicad-cli` 9.0.2 lacks the
10-only upgrade/refill methods and no exact CI job or GUI-saved task-4.1 fixture is supplied. No evidence
level is raised. Corpus ratchet infrastructure validates counts in both directions and separates
unreviewed baselines from actual observations. A real strict full-project local census, with no broad
acceptance flags, failed 22 cases and skipped two heavy rows. Its observations retain 16 import refusals,
five unequal comparisons and one published-malformed input refusal after the focused variant fix.
These are failed proofs, not accepted differences or zero counts. The counts-only observations and their
scope/timings are in `docs/evidence/fidelity.md`; baselines remain pending review.

The manifest-wide focused group has one inherited failure: `test_committed_data_files_are_declared_and_embeddable`
on missing declarations for `examples/board_coverage` and `examples/library-devices` in this base. The
coordinating branch owns their already-prepared declaration union. No unrelated fixture row is changed here.
Task 8.2 retains full fast/CI/publication requirements with the coordinating branch.

Combined integration — 2026-11-01, base `5cede829`: the focused fidelity/category, manifest,
documentation and converted-code group passes all 75 cases, including the formerly missing fixture
declarations supplied by the batch. All 405 corpus entries, existing fields and prior uses remain;
`rtf` is added to 150 inputs. Viewer build targets remain present. That checkpoint omitted positive
source-dependent cases; reviewed corpus baselines, native/GUI and full/CI gates remained open.

Authored continuation — 2026-11-01, after source prerequisite `81f3bb1d`: `uv run pytest tests/fidelity
-q` passes all 14 cases, including five actual source-fidelity tests; the cross-tag materialization and
licence policy selector passes 11 cases (49 deselected). Explicitly identical declared cross-tag inputs
are reused with their original SHA-256 checks; the selected corpus remains 24 roots and 150 inputs.
Only the authored runtime proofs are now satisfied; reviewed corpus baselines, GUI/native and full/CI
requirements remain open.

## Explicit S completion — 2026-11-01

Tasks 2.4, 3.1 and 3.2 now pass their actual authored/public proofs. Explicit S uses the shared native-sheet
comparator, with the old CLI helper retaining its imports. Raw schematic, project and written-build
inputs identify the actual root sheet; no PCB or netlist-export process is needed for S. Native sheet
instance paths retain repeated symbol identities, including source symbols without PCB footprints.
A critical unsplit native crossing loses both a junction item and its resolved net when its junction is
deleted; excluding that exact item still leaves `drawn-net`. Integer/default behavior is unchanged.

The final focused API/CLI/conversion/schema/import-graph/engine/fidelity/guide group passes 329 tests.
It includes actual cached public rows 04 and 12, authored flat/full/hierarchy/bus/Repeat drawings,
missing-side/invalid-option checks, and nine byte digests compared against the pre-S API at c4533497.
The equivalent consistency selection passes 12 tests. Full source pyright and a typed public client
(`level="S"`, integer and default calls) each report zero errors/warnings. Ruff/format, guide/schema
generation checks and residue pass. The active v0 producer/schema widens only the four existing level
fields to `int | Literal["S"]`; the version-1 contract owner has the exact unchanged-key shape before
root's final last-v0 capture. There is no legacy-schema exemption or generic type fallback.

The source prerequisite is signed at 81f3bb1d and integrated by merge 5cab0e29. The independently proved
0738456b packet adds the formerly omitted positive authored round trips: all nine levels pass with actual
copper, and the redundant endpoint-junction writer fault is located after a passing control (5 passed).
Manifest cross-tag materialization uses only the declared identical-at-tag notes; 11 policy cases pass,
with the same 24 roots and 150 fetched-only input rows. These focused proofs do not close 0.1/5.1/8.2's
coordinated full fast/CI requirements, task 4.1's literal GUI save, or native/evidence tasks 6.1/6.2.

## Strict corpus refresh — 2026-11-01

The actual all-level corpus census was rerun on signed source 613b6f1b after the source prerequisite
and explicit S completion. It failed 22 cases and skipped the two declared heavy inputs in 186.16s:
19 import refusals (13 FEN-3004 validation, six FEN-7001 unexpressed content), one manifest-declared
malformed-input refusal and two unequal comparisons. Both compared inputs are equal at S; the remaining
raw differences are 3:footprint-name=7 and 8:render-pixels=1 on one input, and 7:graphic-missing=5 and
8:render-pixels=1 on the other. Counts, timing and refusal codes replace the older infrastructure-only
observations in the evidence page; attribution remains undecided and all 24 baselines remain pending.
This failed local proof does not close 6.2 or claim native/CI evidence. The corpus ratchet requires all
nine level entries and a nonempty reason for any explicit skipped level.

Sensor completion preparation (2026-11-02, base e2658942): actual shared child
contains one resistor symbol and is instantiated in ch0/ch1, while original
U1/R1/D1 and all physical board cases remain. Native10 netlist contains five
components and distinct SENSE0(U1.17/R2.1) and SENSE1(U1.18/R3.1). S summary
counts four unique symbol templates, three sheet instances and40 resolved pins;
these are asserted alongside five physical footprints,8tracks/1arc/3vias,4copper
layers, inner zone, original placements/text/rules. Missing junction or populated
child makes S fail; no relaxed comparison or accepted difference was added.

Proof:107 focused verify-source/drawn/replay/manifest tests passed54.05s; two
additional planted sensor-feature removals passed2.98s. Native10 sensor partition
and import→build→verify-source strict1–8+S passed, with no differences/acceptances.
Touched-file Ruff and script/native-test Pyright pass. A broader exploratory
direct Pyright run over the existing CLI test modules reports48 legacy unknown-
fixture/unused-variable errors outside these additions; the normal gate types
src, and no runtime source is changed here. Prepared native text source remains pending
root's actual GUI-save receipt under4.1/4.1b, and exact-source CI remains pending.
No generated source file is represented as already GUI-saved.

Actual GUI proof completed after c0344: fresh runtime-fixed v4 opened without auto-repair, root/ch0/ch1/board saved in real KiCad10.0.6 GUI; post-GUI strict1–8+S and native five-component partition are equal, no accepted differences. Only five native files captured; exact SHA table and rejected v1 diagnosis are in ../c0344-kicad-project-sheet-identity/native-proof.md. Task4.1 remains subject to its literal residue/manifest proof below and root exact-source CI; generated text was not mistaken for a GUI save.

Task4.1 literal residue/manifest proof is now complete: the combined focused run executed tests/residue and tests/corpus/test_manifest.py along with sensor/import/native regressions,224 passed146.09s. The actual GUI-saved five-file source is captured and source-bound; broader c0278 native/corpus/CI gates elsewhere remain open.
