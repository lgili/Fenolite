## 0. Entry check

- [x] 0.1 Read `openspec list` and the changes and living specs this change builds on, and record under this task, with the date and the base commit:
  - whether c0248, c0259, c0260 and c0261 are archived. If c0248 is not, move its `catalog import` code into `fenolite.library.importer` as part of its own implementation (design decision 9). Take the device tree, the record keys (`origin`, `licence`, `shippable`) and the stable-id rule from c0259 as archived, and adapt the paths of this change if c0259 kept flat `devices/*.toml` files;
  - the package and function names of c0260's generators and whether `fenolite.library` needs an import edge to them or to `catalog` (update "Allowed import edges" through the change that owns it if so);
  - whether another library change (c0262, c0265, c0266, c0279) already added the subcommand dispatch of `fenolite library`;
  - the maintainer's answers to the open questions of `design.md`.

  Proof: `openspec validate c0264-library-import --strict`; `make check-fast`.

  Entry record (2026-11-01, base `8d74a798`, branch `cac/c0264-library-import`): c0248, c0259,
  c0260 and c0261 remain active changes, with their implementations present. The shared c0248 import
  implementation moves into the importer here. c0259 supplies recursive `devices/`, v1 devices,
  explicit pins/packages and `record_uid(kind, id)`; its CC0-only origin gains a distinct local import
  form. c0260 exposes `catalog.footprints.generate/read_package`; the library-to-catalog edge already
  exists. c0261 exposes `catalog.generate.symbol.generate_symbol`. c0261/c0260/c0279 already provide
  `cmd_library.ACTIONS` dispatch and repository verbs. All four recommendations are decided in the
  design on this date. The proposed H-L identifier is aligned to the existing general-register prefix as H-G-LIBRARY-IMPORT. Task remains open until the root runs the single scheduled full local gate.

  Entry refresh 2026-11-02, integration base `697cdf02b39c570b7827bd2b7b5419dfcf6bdea6`:
  c0248/c0259/c0260/c0261 remain active and implemented, with recursive device records,
  `record_uid(kind,id)` identity and distinct `ImportOrigin` metadata. The compatibility
  `catalog import` wrapper now shares `library.importer.templates` readers/templates;
  source selection, zip safety, normalized records and cross-checks live in that importer
  package. `licence`, `origin` and non-shippable local imports retain their existing meanings.
  c0260 exposes `catalog.footprints.generate/read_package`; c0261 exposes
  `catalog.generate.symbol.generate_symbol`. The implemented import-graph table already
  permits library-to-catalog/dsl edges. The living and active "Allowed import edges" copies
  still omit the library row; their archive-time union remains a formal alignment item,
  not an invented delta owner or a new edge here. Shared `cmd_library.ACTIONS` supplies
  symbol/generate/check/review/import/propose/seed/audit/replay/release/gallery; no second
  dispatcher is needed. The four accepted recommendations remain a separately evidenced
  future IntLib reader, source hashes without a duplicate archive, `Imported:` by default,
  and the compatibility alias for one minor release.

  Available proof: `openspec validate c0264-library-import --strict` passes without warnings
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

## 1. Sources and zip safety

- [x] 1.1 Add `src/fenolite/library/importer/zipsafe.py`: in-memory reading with the limits and name rules of design decision 5, counted while inflating (scenarios "A compression bomb", "Path traversal refused", "Legacy library skipped"). Archives are built inside the tests. Proof: `uv run pytest tests/unit/library/importer/test_zipsafe.py -q`.
- [x] 1.2 Add `importer/sources.py`: one reader per source kind (KiCad symbol and footprint, Altium `.SchLib`/`.PcbLib` through the existing adapters, STEP header), item selection and the `.IntLib` refusal (scenarios "IntLib refused", "Two footprints, none picked", "Not a STEP file"). Author the test sources under `tests/data/library_import/`, each with the authored-for-Fenolite line and an `example.invalid` datasheet. Proof: `uv run pytest tests/unit/library/importer/test_sources.py -q`.

## 2. Records

- [x] 2.1 Add `importer/records.py`: the device, pins and package records with `[origin]`, `licence`, `evidence`, the canonical KiCad files, the copied STEP and the model entry (scenarios "Origin rows", "STEP copied unchanged", "Altium symbol drawn from pins", "Same bytes twice"). Register `H-G-LIBRARY-IMPORT` in `docs/hypotheses.md`. Proof: `uv run pytest tests/unit/library/importer/test_records.py -q`; `uv run pytest tests/unit/test_hypotheses_register.py -q`.
- [x] 2.2 Move c0248's pin template (function names, identity map, `--pin`, `catalog.pin-without-pad`, `catalog.pad-unmapped`) into the importer, and add `shippable()` and `library.not-shippable` (scenario "An imported device in a pack"). Proof: `uv run pytest tests/unit/library/importer -k "pins or shippable" -q`.

## 3. Cross-check

- [x] 3.1 Write `docs/formats/library/import-crosscheck.md`: the classifier's features, the tolerances (pitch 0.01 mm, pad centre 0.10 mm, pad size 20 % or 0.10 mm), each labelled `INFERRED`, authored for Fenolite and citing no IPC table. Proof: `uv run pytest tests/unit -k "facts_page or docs" -q`.
- [x] 3.2 Add `importer/crosscheck.py`: `classify`, `crosscheck(footprint, package=None)` with c0260's generators, and the `library.import-*` findings (scenarios "A matching download", "Clockwise numbering caught", "A pad moved", "KiCad and Altium differ"). Proof: `uv run pytest tests/unit/library/importer/test_crosscheck.py -q`.

## 4. Command

- [x] 4.1 Add the subcommand dispatch of `fenolite library` if no other change did (scenarios "The board form is unchanged", "A board folder named like a word"). Proof: `uv run pytest tests/unit/cli/test_library.py -q`.
- [x] 4.2 Add `library import` with its options, the `--into` rules, re-import, the result schema and the codes in `fenolite.library.codes` and `explain.toml` (scenarios "Import an authored archive", "Shipped catalog refused", "Re-import over a reviewed device", "Result fields", "Consistency suite covers the import"). Proof: `uv run pytest tests/unit/cli/test_library_import.py tests/consistency -q`.
- [x] 4.3 Make `catalog import` the alias with `catalog.import-deprecated` (scenario "Alias keeps its bytes"). Proof: `uv run pytest tests/unit/cli/test_catalog_import.py -q`.
- [x] 4.4 Author `examples/library_import/` (the authored archive imported into the example's `devices/` and a design that places it) and the KiCad build test (scenario "Confirmed import builds"). Proof: `uv run pytest tests/unit/test_examples.py -k library_import -q`; `uv run pytest tests/kicad/build/test_imported_device.py -rA` (in CI).

## 5. Closing

- [x] 5.1 Docs: `docs/library-import.md` (sources, what is written, origin and licence, the zip limits, the cross-check, re-import, what sharing the project means for the source terms), `library import` in `docs/cli-contract.md`, links from `docs/index.md` and `docs/devices.md`. Proof: `uv run pytest tests/unit -k docs -q`.
- [x] 5.2 Agent guide: a tested line of `library import` on the page `parts.md`, saying that the device stays `UNVERIFIED` until reviewed, then `uv run python tools/gen_agent_guide.py`. Proof: `uv run pytest tests/unit/agent/test_pages.py -q`.
- [x] 5.3 Residue and evidence: no third-party file in the repository (every test source authored for Fenolite), the evidence matrix regenerated. Proof: `make residue`; `uv run python tools/gen_evidence_matrix.py --check`.
- [x] 5.4 Add the entry to `CHANGELOG.md` under `## [Unreleased]`. This waits until `dev` is at `0.7.0.dev0`: the v0.6 guard requires `[Unreleased]` to stay empty while the version is `0.6.0`. Proof: `uv run pytest tests/unit -k changelog -q`.
- [x] 5.5 Run `make check-fast`, publish the batch to its working branch, and confirm the required CI jobs (unit and KiCad) on the exact commit. Proof: `make check-fast`, and the required jobs green on the pushed head.

Proof record 2026-11-01: task 1.1, `uv run pytest tests/unit/library/importer/test_zipsafe.py -q`: 12 passed.
Proof record 2026-11-01: task 1.2, `uv run pytest tests/unit/library/importer/test_sources.py -q`: 7 passed.
Proof record 2026-11-01: task 2.1 records 4 passed and hypothesis register 38 passed; task 2.2 pins/shippable 4 passed.
Proof record 2026-11-01: 3.1 docs/facts 75 passed, 1 skipped; 3.2 crosscheck 16 passed; 4.1 existing dispatcher with board compatibility 2 passed.
Proof record 2026-11-01: 4.2 command plus consistency 675 passed, 41 skipped; 4.3 legacy alias 10 passed, then full import-focused run 67 passed including the original-byte SHA-256 control. 5.1 docs 61 passed, 1 skipped; 5.2 guide 82 passed after generation. Task 4.4 local example builds; its checkbox stays open pending the required CI KiCad oracle. The accepted implementation explicitly refuses shrinking output sets rather than adding file deletion to the shared mutation protocol.
Proof record 2026-11-01: 5.3 residue 0 hits (15 scoped waivers; the new file waiver covers only four known writer viewport numbers), evidence matrix check clean; 5.4 changelog 8 passed, 1 skipped on version 0.7.0.dev0. 4.4 local example and plain control 2 passed; CI oracle remains unrun.
Proof record 2026-11-01: final imported-record/build compatibility run 106 passed (including body-volume preservation and three example controls); alias/source/zip/command-focused run 69 passed; authored data-manifest selection 1 passed. Explain registry 14 passed after fixing table ordering and section links. Current native source fixtures include their authored SPDX marker and fictional datasheet.
Final local verification 2026-11-01: `pyright src` 0 errors/warnings; `ruff check .` clean; `ruff format --check .` 2864 files formatted; generated guide/evidence checks clean; strict OpenSpec valid without warnings. Destination-symlink regression proof: `tests/unit/cli/test_library_import.py` 15 passed. Tasks 0.1 and 5.5 retain the scheduled full-gate/CI portion; task 4.4 retains the unrun KiCad oracle. No push or full local suite was run.

## Proposed scoped closure receipt —2026-11-03

Preflight base `9ba56e18562695c9cdf5ba3520cdb3e8d481db82` keeps runtime, tests and fixtures
identical to CI source `985f59a1d01a612b2eac0219243199896c24075a`.
`ci-scoped-985f59a1.json` records the actual selected results and limits from retained
run41708879698: five green unit jobs, native9 explicit selected PASSED rows,
and native10 completed required-CLI quiet-run inference, not an invented PASSED line.
The run itself remains failed; the maintainer expressly excludes the27 deferred
geometry cases from this closure batch, without passing them.
This preparation marks no task and archives nothing; root review and the applicable
scoped closing checks remain required. c0246 stays active; its missing literal double
native-variant proof is not borrowed by this change.

Documentary preflight (not a new native proof): nominal OpenSpec1.3.0 passes
all four prepared changes and101 projected living specs. Its normal pure spec
builder projects88 added requirements and120 added scenarios, two complete
MODIFIED bodies, no removal/rename and no existing requirement/scenario loss.
Both modified bodies preserve every old scenario body exactly. Matrix generator
`--check` passes; the focused hypothesis-register/evidence-matrix modules pass
59 tests in125.57s. No task checkbox or archive was changed by this preparation.

## Authorized scoped closure —2026-11-03

Root reviewed and approved the complete normative reconciliations and retained
source985 proof. Local fast is the actual serialized fast13 receipt from
`c0319-integration-repairs/fast13-receipt.json`: source
`2c0540572c936303eb5c46a25002872648dfabad`, exit0,22366passed/52skipped.
Runtime/tests/examples/tools Git trees and Makefile/pyproject/uv.lock/CI config
are exactly equal through source985 and this docs-only executor. The original
log and driver were independently rehashed. This is source-bound applicability,
not an invented fast execution on985; later fast16/source863 is not used.

The maintainer-authorized CI scope excludes the27 deferred geometry cases;
those cases are NOT passed. Retained CI41708879698 and its native10 job remain
FAILURE. Own native9 PASSED results, native10 completed quiet-run source-bound
inference, five green unit jobs and the named artifact are recorded with their
limits in ci-scoped-985f59a1.json. This closes the listed task proofs in that
explicit scope, not a claim of whole-job green. The59 documentary tests,
nominal strict validations and matrix check complement the retained fast/CI.
No new fast/full/native/GUI/CI was run. c0246 stays open.
