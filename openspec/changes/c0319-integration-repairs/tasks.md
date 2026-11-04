## 0. Entry

- [x] 0.1 Record the exact complete-run failure and independent repair decisions.
  Proof: `npx -y @fission-ai/openspec validate c0319-integration-repairs --strict`.
  Passed 2026-11-01: exact96d full-run receipt recorded; scoped decisions
  documented; strict validation valid without warnings.

## 1. Independent repairs

- [x] 1.1 Reproduce and repair the seven Altium scope, project, unsupported-item
  and example-rule cases without changing native acceptance gates or defaults.
  Proof: `uv run pytest tests/unit/backends/altium/test_roundtrip.py tests/unit/lens/test_altium_issues.py tests/unit/exports/test_altium_rul.py tests/unit/backends/altium/test_project.py -q`.
  Passed 2026-11-01: all seven original failures reproduced on `2c707d00`.
  Documented eight excluded footprint/pad fields without widening RT-A2; kept
  exact image/verbatim loss sets plus the existing closed-gate Draftsman notice;
  bounded candidate XML imports to their two exact stdlib modules and retained
  the registered `INFERRED` parameter hypothesis. Classified only the imported
  `blocks/divider.py` helper as a module; `blocks/design.py` and the unrelated
  `picks/divider.py` remain in the rule readback census. The exact proof passed
  287 tests; independent candidate/gate/layering regressions passed 100 and all
  33 Altium default byte guards passed unchanged. Runtime files and native
  acceptance gates are unchanged. The combined complete gate and exact CI
  remain tasks 2.2 and 2.3.
- [x] 1.2 Reproduce and repair the five remaining block-version, field ordering,
  field readback, generated-symbol and declared-layer cases. Coordinate shared
  source files with the separate footprint-identity change.
  Proof: `uv run pytest tests/unit/dsl/test_lock_blocks.py tests/unit/lens/test_build_fields.py tests/unit/backends/kicad/test_replace.py tests/unit/dsl/test_symbol_units.py tests/unit/backends/kicad/test_layer_undeclared.py -q`.
  Passed 2026-11-01 on the isolated model/lens repair: exact five reproduced (5 failed in 2.50s);
  the literal five-file proof now passes (47 in 5.84s). Four stale fixtures follow the specified
  upgrade hint, font-request protocol, named/stacked symbol pins and declared user layers. Native
  replacement retains font properties from model values or existing opaque effects; write/read and
  another rotation, explicit False overrides, and existing flip policy are covered. The authored
  generated-symbol fixture has exactly seven pads and asserts stacked 2/7 share a nonempty net.
  All 76 pinned build-byte tests pass; no pin, comparison/refusal assertion, resource skip or reader
  default changed. Local lint/format/types/residue checks pass; combined tasks 2.1–2.3 remain open.
- [x] 1.3 Reproduce and repair issue/explanation/severity and authored-library
  measurement contracts using actual registered behavior and measured scope.
  Proof: `uv run pytest tests/unit/catalog/test_pin_text_legibility.py tests/unit/cli/test_explain_cmd.py tests/unit/lens/test_pins.py tests/unit/checks/test_codes.py -q`.
  Passed 2026-11-01 on the isolated registry repair: all six original failures reproduced;
  the literal proof passes 133 tests. Draftsman explanations link to the existing Build target
  section that describes them. Pin-code discovery distinguishes proposal filename bundles and
  registered readiness calls from findings; unknown-code and filename-as-issue negatives remain
  strict. The parallel-pullup warning is represented in severity/waiver contracts with its
  warning default and exact row/digest requirements. Existing rating-missing and block-port-merged
  info behavior is preserved.

  Related waiver proof passes 33 tests: one exact I2C line can be accepted by its current digest,
  the other line stays a warning, and an expired digest retains warnings. All 73 library/catalog
  cases were already collected; relative-path names repair duplicate labels without changing
  geometry/calibration, adding cases or adding exceptions. The same four documented exceptions
  and glyph allowlist remain. Local kicad-cli is 9.0.2 (version receipt only); no new native
  measurement or evidence promotion is claimed. Complete/CI gates remain tasks 2.2/2.3.
- [x] 1.4 Reproduce and repair guide-start, paged-capability and hermetic-set
  contracts. Preserve every taught surface and resource requirement.
  Proof: `uv run pytest tests/unit/test_agent_skill.py tests/unit/cli/test_paging.py tests/unit/test_parallel_runs.py -q`.
  Passed 2026-11-01: all three exact failures reproduced, then the literal proof
  passed 44 cases without skips. Library retains items/sources/proposals and pick
  retains proposals; the exact fast recipe keeps tests/fidelity and all three resource
  exclusions. An additional parallel/fidelity proof passed 27 cases, including
  the authored round trip that refuses external subprocesses. Six guide budget,
  index and generated-page checks passed. The start page is 11,991 bytes / 160
  lines; its topic index and loop commands are byte-identical. Makefile and
  resource policy files are unchanged. Full/combined/exact-head CI remains open.
- [x] 1.5 Reproduce the ten authored-data header cases, preserve their declared
  licences, and enforce the first-two-line policy with bounded role checks.
  Proof: `uv run pytest tests/unit/test_spdx_headers.py tests/corpus/test_manifest.py tests/residue -q`.
  Passed 2026-11-01: 132 cases with seven missing-corpus skips. Ten already
  correctly headed CC0 data files retain identical bytes; five fixture manifest
  rows now state their existing CC0 dedication explicitly. Core implementation
  remains Apache-2.0. Negative cases reject core CC0, unregistered/foreign data,
  missing copyright and absent authored-data statements.
- [x] 1.6 Confirm the reserved-part-attribute union coordinated with c0318.
  Proof: `uv run pytest tests/unit/catalog/test_device_ports.py -q` on the combined source.
  Passed 2026-11-01: the complete device-port proof passes within the final 224-case
  byte/identity/guide/schema group on the combined model0 source; the original exact attribute
  case also passes in the mapped integration replay.
- [x] 1.7 Document the combined c0318 KiCad-only component definition reference in the existing
  Altium RT-A2 exclusion table. Retain the field-completeness assertion and runtime refusal.
  Proof: `uv run pytest tests/unit/backends/altium/test_roundtrip.py::test_scope_documented -q`;
  replay the original integration failures with the explicit import-only helper-role mapping.
  Passed 2026-11-01: the unchanged scope-completeness assertion passes. The replay preserves
  all 23 original failure identities: 22 node IDs remain direct, while the obsolete import-only
  helper parameter has an explicit role/rejection proof and two actual-design readbacks.
  Those 24 pytest cases pass; no assertion, RT-A2 scope, byte pin or refusal was relaxed.

- [x] 1.8 Reproduce the three native KiCad expectation failures from exact `96d687d1`
  CI run `41359100272`. Retain the literal stage order with `topology.rules` after
  `length.rules`; require the exact device-only informational metadata counts
  without excluding any new error or warning. Keep all native gates and runtime
  defaults unchanged. Report the actual local KiCad version separately from CI.
  Proof: `uv run pytest tests/kicad/check/test_check_oracle.py::test_canary tests/kicad/check/test_check_built.py::test_built_blink_before_routing 'tests/kicad/build/test_device_build.py::test_device_build_passes_the_kicad_oracle[t9]' -q -s`;
  `uv run pytest tests/unit/checks/test_stages.py tests/unit/checks/test_codes.py tests/unit/checks/test_topology_stage.py tests/unit/checks/test_circuit_stage.py tests/unit/cli/test_check_cmd.py -q`.
  Passed 2026-11-01: actual local KiCad 9.0.2 reproduced all three failures
  (22.27 s); the corrected native proof passes all three (25.17 s), with no
  skips. Both device and plain builds retain 18 unconnected-item errors and
  one zone-fill info; the device-only difference is exactly one policy-missing
  info and one value-unknown info. Code/severity counters accept no additional
  warning or error. All 80 stage/issue contracts pass (19.82 s). Runtime,
  dependency, model/schema, native gates and the original 96d CI receipts are
  unchanged; no repeat of CI's 9.0.9 or a KiCad 10 measurement is claimed.

- [x] 1.9 Reproduce the stale component-tail assertion after c0318; retain the exact append-only
  field sequence and the existing absent-value-range default. Change only the test name, explanation
  and expected tail, then repeat model and identity/default-byte proofs.
  Proof: `uv run pytest tests/unit/model/test_value_range.py -q`;
  `uv run pytest tests/unit/lens/test_footprint_identity_bytes.py tests/unit/importer/test_footprint_identity.py tests/unit/test_build_bytes.py -q`.
  Passed 2026-11-01: the unchanged stale assertion reproduces (1 failed in 0.34 s); the
  corrected whole file passes 19 cases (0.26 s), and the identity/import/default-byte group
  passes 96 cases (24.55 s). The absent value-range default remains checked. No runtime,
  model/schema, constructor order, native gate or byte pin changes.

- [x] 1.10 Reproduce the published `697cdf02` strict residue filename failure. Rename the four
  authored DigiKey/Nexar authentication response and source-sidecar files to `auth-reply` role names;
  update all fixture references and declarations while preserving payload/sidecar bytes, source
  citations, access policies and the unchanged detector. No waiver or readiness promotion.
  Proof: `uv run pytest tests/unit/suppliers tests/unit/pick/test_propose.py tests/unit/cli/test_pick_cmd.py tests/unit/test_spdx_headers.py tests/corpus/test_manifest.py tests/residue -q`;
  `uv run ruff check .`; `uv run ruff format --check .`; `uv run pyright src`;
  `uv run python tools/residue/scan.py`;
  `npx -y @fission-ai/openspec validate c0319-integration-repairs --strict`.
  Passed 2026-11-02: the exact original test fails only on the four authored fixture/sidecar paths
  (one failure, 2.23 s). All four renames retain 100% identical bytes and the same S-1100/S-1105
  citations. The complete supplier/proposal/pick/manifest/header/residue selection passes 270 cases
  with seven existing missing-corpus skips (88.82 s). Lint/format, source types (zero diagnostics),
  public residue scan (zero hits) and strict OpenSpec pass. Endpoint/protocol fields, provider rights
  policies, dependencies, source register and strict detector are byte-identical to the published base;
  no waiver, credential, exception or readiness promotion. Combined/full/exact-CI remains 2.2/2.3.

- [x] 1.11 Compare actual temporary-directory identity across aliases while
  retaining Windows-style cleanup rejection and original authored exceptions.
  Reproduce the stale assertion with an actual parent-component alias first.
  Proof: `uv run pytest tests/unit/blocks/test_runner.py tests/unit/cli/test_blocks_test.py tests/unit/blocks/test_starter.py tests/unit/testing/test_load.py -q`;
  `uv run fenolite blocks test --json`.
  Passed 2026-11-02: the real parent-component alias first reproduced all four
  stale identity assertions (4 failed / 4 passed). Resolved identity then passes
  all 49 runner/CLI/starter/load cases with ordinary bytecode enabled. Both
  temporary spellings retain cleanup rejection, state restoration and authored
  exception checks. The actual shipped command exits 0: five usages, five equal
  goldens, 16 tests and no findings. Styles, public residue and strict validation
  pass; source/model/schema/example/fixture trees are unchanged. Native Windows
  and macOS CI on the new batch remain open.

- [x] 1.12 Repair the three exact L8 Windows circuit-difference, authored ZIP
  reproducibility and Part F cross-drive kit failures without changing checked
  archive/payload bytes, plan bindings or native acceptance gates.
  Proof: `uv run pytest tests/unit/cli/test_blocks_upgrade.py tests/unit/library/importer/test_sources.py tests/unit/backends/altium/test_part_f.py -q`.
  Add portable backslash-cache, simulated Windows ZIP metadata and synthetic
  cross-drive reference controls; keep actual Windows CI validation pending.
  The rooted-source negative also requires ordinary Altium resolved symbol item
  and library-table inputs in the reviewed plan. Prove edits to either refuse
  confirmation with FEN-4002; preserve Alpha's separate drawn alias bindings.
  Passed 2026-11-02: the literal proof passes 34 cases with the one existing
  real-native F8 skip. Backslash cache paths retain the exact 1k-to-2k change;
  simulated Windows ZIP creator defaults reproduce the complete checked archive
  bytes. Synthetic same/cross-drive references retain their exact library source.
  Rooted symbol/table edits refuse staged confirmation with FEN-4002 and no
  output; an unchanged control replays successfully. The affected Altium CLI
  file passes all 50 cases. Checked fixture archives and byte pins are unchanged.
  Actual Windows rerun and complete/exact-head CI remain tasks 2.2 and 2.3;
  native Altium acceptance is neither performed nor claimed.

- [x] 1.13 Repair the exact Windows UTF-8 document readbacks and library-check cross-drive input
  display errors from `697cdf02` CI. Preserve licence/source/HTML content, findings, dependencies,
  sheet paths and strict validation. Prove original nodes under a real cp1252 default-open shim and
  actual CLI behavior under the Windows relpath failure; no global encoding workaround.
  Proof: `uv run pytest tests/unit/cli/test_library_check_portability.py tests/unit/test_legal_docs.py tests/unit/blocks/test_starter.py tests/unit/suppliers/test_policy.py tests/unit/cli/test_library_check.py tests/unit/library/test_fixtures.py -q`;
  `uv run ruff check .`; `uv run ruff format --check .`; `uv run pyright src`;
  `npx -y @fission-ai/openspec validate c0319-integration-repairs --strict`.
  Local reproduction 2026-11-02: the cp1252 child reproduces the same five decoding failures
  (5 failed, 4 passed); the separate cross-drive CLI control reproduces FEN-1001. After repair,
  the literal six-file group passes 48 cases in 60.64 s, including the original nine cases under
  cp1252. The unchanged same-drive path, warning threshold, invalid-record finding, sheet scope,
  stale-input refusal and fresh-plan confirmation are proved. Source/licence/HTML/fixture payloads
  are byte-unchanged; only explicit test codecs and the display-path fallback change behavior.
  This is local Windows-condition simulation, not native Windows or exact-head CI evidence.
  Ruff, format (3181 files), the generated guide, public residue (0 hits; 16 existing waivers),
  source types (locked Pyright 1.1.414, 0 errors/warnings) and strict validation pass.
  The complete fast gate and exact-head CI remain tasks 2.2/2.3, unchecked.

- [x] 1.14 Document the actual drawn-coordinate warning in the CLI issue table,
  retaining its severity and explicit lossy-write prerequisite.
  Proof: `uv run pytest tests/consistency/test_cli_consistency.py::test_check_codes_documented tests/unit/cli/test_explain_cmd.py tests/unit/agent/test_pages.py -q`;
  `npx -y @fission-ai/openspec validate c0319-integration-repairs --strict`.
  Passed 2026-11-02: the original exact L9 assertion first fails on the missing
  warning. The unchanged consistency, explanation and guide proof then passes
  all 107 cases. Strict validation is valid; source, schema, example and fixture
  trees remain byte-identical. Native/full/exact-head CI remain open.

- [x] 1.15 Repair the eight exact L8 KiCad 10 failures from run `41362730027`, job
  `125016358377`. Preserve raw duplicate-reference counts and historical conversion tables;
  record source-bound current comparisons after c0277 pairing. Preserve safe interior spaces in
  derived footprint names without changing project/symbol naming, path guards or name comparison.
  Proof: `uv run pytest tests/unit/convert/test_native_footprint_names.py tests/unit/checks/equivalence/test_levels.py tests/unit/convert/test_docs.py -q`;
  `uv run pytest 'tests/corpus/test_convert_census.py::test_differences_per_kind[08]' 'tests/corpus/test_convert_census.py::test_differences_per_kind[16]' 'tests/corpus/test_convert_census.py::test_conversion_is_explained[08]' 'tests/corpus/test_convert_census.py::test_conversion_is_explained[16]' -q`;
  `uv run pytest tests/kicad/convert/test_native_footprint_names.py -q`;
  `uv run pytest tests/kicad/equivalence/test_triangle_corpus.py::test_keys tests/kicad/convert/test_a2k_import.py::test_public_import -q` on actual KiCad 10.
  Keep this task open until the literal native proof passes; local KiCad 9 can prove authored
  loading and pure comparison behavior but cannot replace the independent KiCad 10 importer.
  Local progress 2026-11-02: all four original demo-census assertions reproduce on `46d788ee`
  (4 failed in 16.83 s). The current source-bound supplement and authored name/pairing/document
  group pass 43 cases (17.07 s); conversion/exclusion compatibility passes 25 (4.72 s).
  Actual local KiCad 9.0.2 passes three authored load/export controls (8.26 s), including distinct
  `M Mount.svg` and `M_Mount.svg` from the derived library. All three historical conversion
  table sections, the strict comparator and the native-import exclusion file retain identical
  bytes. No actual local KiCad 10 import is available; task 1.15 and combined/full/CI tasks
  2.2/2.3 remain unchecked pending their literal required proofs.

  Superseding measured continuation, 2026-11-02, clean signed
  `1918e63214a7d0123e1f5fa8ef095c73fd2e1472`: the complete specified
  unit/document/four-census selection passes 43 tests (12.92 s). All native
  selectors above pass on the actual installed KiCad CLI 10.0.6 with heavy
  inputs enabled: 16 passed (56.79 s), no skipped cases. This includes the
  authored space/underscore load, triangle keys and public independent
  importer proofs. No exclusion/table, tolerance or raw duplicate count is
  changed. This closes only 1.15; complete and exact-head CI stay open.

- [x] 1.16 Declare the drawn Altium writer's existing inferred evidence and use
  a pure, permitted own-module import without broadening backend import rules.
  Proof: `uv run pytest tests/unit/backends/altium/test_project.py tests/unit/backends/test_evidence_declared.py tests/unit/backends/altium/test_drawn_altium.py tests/unit/test_build_bytes.py -q`;
  `uv run python tools/gen_evidence_matrix.py --check`;
  `npx -y @fission-ai/openspec validate c0319-integration-repairs --strict`.
  Passed 2026-11-02: all three exact L9 backend failures reproduce first.
  Existing project/declaration/drawn-writer/default-byte proofs then pass all
  163 cases; all 75 example maps retain their bytes. Source typing reports zero
  diagnostics; focused styles, evidence freshness, public residue and strict
  validation pass. The existing inferred hypothesis/grade and native write
  gates are unchanged. Complete/exact-head CI remains open.

- [x] 1.17 Include the already-registered drawn-coordinate warning in the exact
  severity contract, preserving its warning default and waiver/refusal rules.
  Proof: `uv run pytest tests/unit/checks/test_codes.py -q`.
  Passed 2026-11-02: the exact missing-warning assertion reproduces first;
  the unchanged complete code/severity/waiver proof passes all eight cases.
  The production registry and warning/refusal behavior are unchanged.
- [x] 1.18 Record the actual current-week backend session and reused public
  format facts in the existing clean-room annex without asserting native acceptance.
  Proof: `uv run pytest tests/unit/test_provenance.py -q`;
  `npx -y @fission-ai/openspec validate c0319-integration-repairs --strict`.
  Passed 2026-11-02: the exact missing-W45 assertion reproduces first; the
  complete provenance proof then passes all eight cases. The dated row records
  only the actual evidence/import review, authored tests and reused public
  record facts; native application acceptance remains pending. Strict valid;
  production/source fixtures and all original provenance assertions unchanged.

- [x] 1.19 Make the three viewer shell assertions use the existing platform-specific
  palette chord and displayed shortcut. Preserve the explicit Mac Ctrl-rejection/Cmd-acceptance
  control, production bundle and screenshot references.
  Proof: `uv run pytest tests/visual/test_shell.py -k 'palette or plain_keys or shortcut_sheet' -q`
  with the required pinned browser on the maintainer's Mac; focused Ruff checks.
  Passed 2026-11-02: all four selected cases pass on macOS with Playwright 1.63.0
  (12.52 s), including the unchanged explicit Mac Ctrl-rejection/Cmd-acceptance
  case. Focused Ruff lint/format and diff whitespace checks pass. The initial
  complete visual run was 90 passed/14 failed: these three chord assertions and
  eleven screenshot comparisons. Screenshot references, production TypeScript
  and the committed bundle retain their exact bytes. The image comparisons and
  combined/full/exact-head gates remain separate unresolved results.

- [x] 1.20 Measure the guide's newly added authored design blocks with actual KiCad 10,
  extend the exact error-code table and its per-block native cases, and retain complete
  coverage plus the existing routed/fill proof. Do not infer expected findings from prose.
  Proof: `uv run pytest tests/unit/agent/test_pages_kicad.py -q` on native KiCad 10;
  focused Ruff checks. Record any build refusal as a blocker rather than omitting its block.
  Passed 2026-11-02: all fourteen previously missing blocks were actually built and checked on
  native KiCad 10.0.6. `board-workflow:0`, `files:1` and `rules:3` return exit 0 with no errors;
  the other eleven return exit 5 with their measured exact error-code sets. The complete
  unchanged coverage comparison, all 31 per-block native cases and existing routed/fill case
  pass together: 33 passed in 222.41 s. Focused Ruff lint/format and diff checks pass. No guide
  script, native issue code, severity or production implementation changes.

  L12 integration repeats pass on native KiCad 10.0.6 and the pinned browser:
  all 33 guide cases (137.93 s) and four shortcut cases (7.89 s). The previous
  receipts above retain their earlier L10 source scope.

### Maintainer-host L12 repairs

- [x] 1.21 Keep the native contextual-property preservation proof at its source
  format version while running the actual installed KiCad 9/10 process. Explicitly
  bind import/build/verify to that version: the authored hierarchy is KiCad 9,
  even when the oracle is KiCad 10. Preserve exact complete property assertions,
  native components/BOM, all-nine equality and unchanged source bytes. Retain the
  separate legacy-tilde conversion contract. Proof: `uv run pytest
  tests/kicad/schematic/test_contextual_symbols.py tests/unit/backends/kicad/test_symembed.py -q`.
  Proof on native KiCad 10.0.6: 15 passed (7.59 s). The first attempt still
  combined a target-10 board with target-9 versioned drawings; selecting the
  matching target-9 authored board closes that setup defect, preserving the
  original complete-property assertion and all nine strict comparisons.
- [x] 1.22 Isolate direct font-oracle CLI exports in a copied input project, retain
  exact hashes of every original and copied input, and record only the bounded
  new native project-local settings file as an output. A failed sample must not
  poison subsequent parameter setup. No source-file exclusion, native AST
  normalization, glyph comparison or tolerance relaxation is permitted.
  Proof: `uv run pytest tests/kicad/schematic/test_drawn_fonts_oracle.py -q`.

  Native KiCad 10.0.6: the entire font file passes 28 cases (45.71 s),
  including a planted failed export followed by a real successful retry.
  The retry control first reproduced the stale-directory failure. Every
  attempt now has its own retained scratch directory; failed attempts do not
  populate the sample cache. All original and copied input bytes remain exact;
  only a new `drawn_full.kicad_prl` may appear in the export copy and its digest
  is retained in the receipt. Source hashes, glyph groups, styles, multiplicity,
  and native default/asymmetric-axis comparisons are unchanged.

- [x] 1.23 Keep the block-document consistency probe's ordinary import in its
  own temporary folder. It currently creates an undeclared divider bytecode
  file beside the committed data and makes the subsequent manifest proof fail.
  Preserve ordinary bytecode and the strict data-manifest policy. Proof:
  `uv run pytest tests/consistency/test_block_docs.py tests/corpus/test_manifest.py
  tests/unit/backends/kicad/test_tuning_profiles.py tests/unit/test_format_facts.py -q`
  after staging the authored tuning fixture and its declaration.

  Passed after staging: 100 cases (2.32 s). The preceding overlay run
  reproduced the undeclared bytecode failure (96 passed, 1 failed). The probe
  now imports a byte-identical temporary copy with ordinary bytecode enabled;
  only its previously generated untracked cache file was removed. The strict
  manifest rules and native fixture save digest are unchanged.

- [x] 1.24 Record the maintainer-host takeover ledger, exact open task IDs,
  external-resource boundaries and completed CI cleanup with archived evidence.
  Preserve historical failed outcomes and all exact-head CI gates.
  Proof: ledger task IDs/counts agree with current source task files;
  `npx -y @fission-ai/openspec validate c0319-integration-repairs --strict`;
  `git diff --check`.
  Passed 2026-11-02: 58 current task files and 101 unchecked numbered tasks
  verified against the ledger (excluding this self-referential task). Strict
  OpenSpec validates without warnings and the diff is whitespace-clean.

## 2. Combined validation

- [x] 2.1 Update the one Unreleased entry, retain exact proof scope and run static,
  guide/schema, residue and strict checks after merging the repairs.
  Proof: `uv run ruff check .`; `uv run ruff format --check .`;
  `uv run pyright src`; `uv run python tools/gen_agent_guide.py --check`;
  `uv run python tools/residue/scan.py`;
  `npx -y @fission-ai/openspec validate c0319-integration-repairs --strict`.
  Passed 2026-11-01: per-packet focused/static/type checks and final combined checks pass;
  all schema/guide/evidence-matrix/Altium-graduation generators are current, public residue
  finds no hits, and all five affected changes validate strictly. See validation.md for the
  exact mapped proof, model0 boundary, byte guards and remaining source/native/CI limits.
- [x] 2.2 Repeat the complete local fast gate on the stable repaired candidate.
  Proof: `make check-fast`.

  Passed 2026-11-02 on the stable repaired source
  `ea762411cbb24bc5f9ba5a16d8b372ae7c720568`: `make check-fast`, exit 0,
  19564 passed and 55 skipped, JUnit zero failures/errors. The source-bound
  timestamps and receipt/log/XML digests are in validation.md. This is the
  complete local fast gate, not successful GitHub CI. Task 2.3 and the specific
  independent native/private/release proofs remain open.

  L12 continuation: the historical passing L10 receipt above is retained.
  The L12 maintainer-host complete run finishes with 1 failed, 20005 passed,
  51 skipped (1157.18 s): only `board_40parts@altium` fails. Static, types,
  generated checks and private residue pass. No byte table, tolerance or
  producer change is used to hide that existing Mac mismatch. Keep this task
  open; the earlier L10 receipt remains historical.

  Fast15 continuation —2026-11-03: the independent runtime candidate
  9ff58f57ba2daf05309391b8ebcd23bb9cf67186 passed the complete
  `make check-fast PYTEST_MAX_WORKERS=4`:22421passed/52skipped, exit0,
  1034.28s pytest/1127.695304666995s complete driver, clean unchanged HEAD.
  See fast15-receipt.json for the recomputed external receipt/log/driver
  bindings. Failed fast14 remains unchanged and historical. This proves the
  local gate on9ff58f57 only, not task2.3, Royal L7 or any actual archive.

- [ ] 2.3 Publish one reviewed batch and confirm all required CI jobs on that
  exact commit; keep native/private/release proofs separate.
  Proof: required GitHub CI jobs completed successfully on the recorded commit.

- [x] 2.4 Publish the ready inspection checkpoints and record their exact
  remote heads, implemented scope, open gates and source-bound CI outcomes in
  `published-checkpoints.md`. Preserve active work and the separate model-1 hold.
  Proof: remote branch reads match all three recorded heads;
  `npx -y @fission-ai/openspec validate c0319-integration-repairs --strict`.
  Passed 2026-11-02: GitHub API branch reads confirm the recorded L11,
  prepared-model and separate-library SHA values after non-forced pushes.
  Strict validation is valid without warnings. This publication proof closes
  no remaining implementation, activation, native acceptance or CI gate.


Inspection source update — 2026-11-02 (L12): the new assembly preserves font
`b548fa46`/proof-only `2376efe5` and contextual `4595266e` from immutable 2fa.
The published-checkpoints index now distinguishes functional contextual plan
binding from the historical interim refusal and retains the source-bound VME
1700-versus-1800 failure. No new remote-head, all-corpus, model1, native GUI or
successful exact-head CI claim closes task 2.3 or a feature gate.

- [x] 2.5 Declare the authored native project sidecar used by examples/import_python in the committed-data manifest. Preserve every policy check, data byte and corpus licence boundary. Proof: the complete focused corpus manifest component passes; exact-head CI remains task2.3.

CI41611925152 on40d27f47: macOS unit job125835695455 completed with one missing data-manifest row,21967 passed and4225 skipped. The missing path is the authored native project sidecar, not third-party CAD. Other jobs remain independent; no successful complete CI is claimed.

Task2.5 proof: examples/import_python/native/project.kicad_pro is byte-identical to the already declared authored tests/data/import_python/two_sheet/two_sheet.kicad_pro. Complete focused tests/corpus/test_manifest.py:60 passed. No fixture bytes, licence policy, test assertion or comparison changed. Final exact-head CI remains open.

- [x] 2.6 Reconcile accumulated Unreleased example/identity status paragraphs after integrating native checkpoints, keeping only the current example outcome and retaining all historical failures in their evidence records. Proof: no stale duplicate example paragraph; git diff --check.

Task2.6 proof passed: exactly one current drawn-example paragraph remains and git diff --check reports no whitespace errors. Historical incomplete attempts stay in the native evidence records; no gate is changed by this documentation reconciliation.

- [x] 2.7 Diagnose CI native9 CM5_MINIMA_3 downgrade failure using the declared public corpus, distinguish conversion unexplained differences from project DRC/ERC type changes, then fix the demonstrated cause. Preserve strict existing demo/probe expectations and all losses, no new waiver or baseline update; prove focused native9/10 and source/input/output hashes.

Task2.7 proof: source M705 is explicitly pinless in_bom=yes/on_board=no and absent from PCB. The old conversion preparation omitted it while public read-back preserved it, causing the sole false L1 component-missing finding before native project checks. Authored writer-input controls fail2before; after the private API preparation repair104focused tests pass (10BOM/context/unsafe-unit/Altium-refusal controls plus conversion/import-graph neighbors), source pyright0, and native9.0.9/10.0.6 each pass test_demo_project[CM5_MINIMA_3]+test_probe (2passed28.91s/41.68s). All72converted CAD files remain BYTE-IDENTICAL to before, all source hashes remain exact, and no loss/probe/type baseline changes. Receipt cm5-bom-source-proof.json. Full test_probe_results/full validation remain root-owned exact-head CI, not a local full-census claim.


- [x] 2.8 Reproduce fast-batch9 release-record failures, retain historical release/native/freeze claims while naming newly opened current acceptance tasks in dated tracking, and replace the v0.4 negative's now-completed task with an independent authored open-task fixture. Do not weaken parser/checker or task coverage. Proof: complete focused v0.4/v0.5/v0.6 release-record tests and private residue gate; exact-head CI remains2.3.


Task2.8 proof: exact18351e40 reproduction gives3fail/106pass: v0.4's hardcoded completed4.2 negative, and c0092 new5.3 unnamed in v0.5/v0.6. Three additional authored parser reds demonstrate letter-suffixed open/checked IDs were omitted. The guard now retains distinct lowercase continuation IDs and still refuses an unnamed open continuation; v0.4's negative reads an independent temporary authored tasks.md while retaining both existing failure assertions. Dated2026-11-03 tracking names c0092.5.3, c0178.3.4a and c0180.2.4a; no historical acceptance text/result, freeze, runtime or source CAD changes. Complete focused release-record files:112passed3.35s, Ruff/format/diff clean; private staged gate0hits. Exact-head full validation remains2.3/root-owned. Receipt release-ledger-proof.json.

- [x] 2.9 Repair the two stale drawn-example guards exposed by the complete b5f6c84a fast gate: assert the intentionally added IN label and make the missing-symbol mutation actually append R9 after the source's GND connection changed. Preserve refusal/no-output and repeated-build byte checks; prove the missing-symbol finding identifies R9 without changing a producer or comparator. Proof: original two failures reproduced (1.54s); complete drawn module7passed (1.98s), then drawn plus all three release-ledger modules119passed (4.17s). The negative now reuses the existing GND object, produces exactly one R9 missing-symbol finding and writes no output; the positive explicitly checks IN plus the exact eight-label count and unchanged rebuild bytes. Ruff/format/strict OpenSpec pass; final whole fast/exact CI remain pending.

- [x] 2.10 Reconcile the bounded v0.7 closure queue with literal integration, native, human and library-publication gates. Preserve historical CI failures and source-bound successes separately; do not archive or infer current CI success. Proof: review all eight ready-current-CI entries, original c0246–c0279 open tasks, and source-bound receipts; strict OpenSpec validation and git diff --check.

  - Root review: original open task IDs and the eight candidates reconciled; corrected c0279 release/workflow IDs against its literal tasks. Historical13/13 job results and producer hashes independently rechecked, focused196/55/152 receipts and cleanup hashes verified. Strict c0319 validation and diff check pass. The interrupted97a52 replay remains19failed/6passed/2heavy-skipped, not a combined pass. This completes only the queue audit;2.2/2.3 and every actual archive remain pending.


- [x] 2.11 Reconcile the new c0215.6.4a continuation with the historical v0.6 release ledger after fast12's literal unnamed-open-task failure. Name it in the current open-task cell and a dated continuation paragraph, preserving the original release/K6 outcome, native24 authorization scope and pending exact-current CI. Keep every release-record checker unchanged. Proof: complete v0.4/v0.5/v0.6 release-record modules and strict c0319 validation; preserve the failed fast12 receipt.


Task2.11 proof: complete source5bbe19c7 fast12 finished with1failed/22350passed/
52skipped in2090.46s (whole2197.368s, exit2), clean unchanged HEAD. Sole failure:
c0215.6.4a was open and absent from the historical record's current tracking.
Added its exact ID and an explicitly dated continuation; all historical verdicts,
K6 and current CI requirements stay unchanged. Complete unchanged v0.4/v0.5/v0.6
record checkers now112passed12.81s. Strict c0319/diff checks pass. Receipt
fast12-receipt.json preserves log SHA48459d3aa490fb7c8d2411a0646e8672245ff8049145275e54ad0c5a0dded9a7.
This fixes the named consistency failure; neither the full fast nor exact-current
CI is relabelled successful, and2.2/2.3 remain open for the final source.


Task2.2 fast13 reproof —2026-11-03: complete make check-fast
PYTEST_MAX_WORKERS=2 exits0 on clean unchanged source
2c0540572c936303eb5c46a25002872648dfabad:22366passed/52skipped,
1624.58s pytest/1720.2919891250203s total. Public/private residue, all generated
checks, Ruff/format and pyright pass. Receipt fast13-receipt.json binds the
command, source, driver and complete log SHA. All later commits through
c5e34749 contain only evidence/docs/OpenSpec/CHANGELOG changes, with separate
82/24 focused evidence proofs; no later whole-fast or native/CI success is
inferred. Revalidate any subsequent runtime candidate. The source-bound local
fast requirement2.2 is complete; exact-head required GitHub CI2.3 and every
independent native/library/private/release gate remain open.


- [x] 2.12 Record the complete fast15 result with a portable source/log/driver/receipt binding; reconcile current local-fast tracking without rewriting fast14 or closing CI/native/Royal/archive gates. Proof: recompute external SHA-256 bindings and literal counts; strict c0319 validation; git diff --check; staged residue scan with the private gate enabled.

  Passed 2026-11-03: all original external receipt fields and three SHA-256
  bindings match; literal 22421 passed / 52 skipped / 1034.28 s matches the
  complete log. The failed fast14 receipt is byte-identical. Strict c0319
  validation and whitespace checks pass; staged private-enabled residue scans
  all seven changed documentation files with zero hits. No suite/native/CI
  rerun, runtime change, publication or actual archival was performed.


- [x] 2.13 Restore the maintainer’s already agreed geometry exclusion for the CAC closure batch.
  On pushes to codex/cac-next only, explicitly deselect the 27 source-bound known c0332 native
  failures, report them as deferred rather than passed, and leave main/dev/PR selection unchanged.
  Preserve all runtime, assertions and geometry budgets; do not rerun the complete CI to rediscover
  known failures. Required jobs/proofs of other specs are judged in their own scope. Proof:
  `uv run pytest tests/unit/test_ci_workflow.py -q`; strict c0319 validation; scope manifest/hash
  verification; diff and private residue checks. No new CI or push is implied by this local repair.

  Proof2026-11-03:51workflow unit cases pass in0.25s; the exact inline scope script verified all27
  bound test-file digests and produced exactly their deselect arguments plus explicit summary,
  without executing pytest/native/CI. Strict c0319 and diff checks pass; private staged scan0hits
  in9files. No runtime changed, no push/new CI, and the previous failed run remains failed.


- [x] 2.14 Record the fifteen actual scoped archives, their complete file/commit/DCO bindings,
  the actual static library audit and retained failed-run cleanup without closing later integration,
  fresh Royal fidelity or external release gates. Proof: verify every archived file against its
  reviewed source commit and the living-spec chain; strict living/c0319/c0266/c0273 validation;
  diff check; private staged residue. Reuse completed proofs without another full suite or CI.

  Proof2026-11-03: every file in all15archives equals its reviewed source commit; every CAC
  archival commit has the maintainer DCO; living specs exactly match the reviewed archive chain.
  All86living specs and c0319/c0266/c0273 strict checks pass; diff passes; private staged scan
  reports0hits in9files. Library audit and CI cleanup receipts retain their exact sources and limits.

- [x] 2.15 Reconcile the current32 actual scoped archives and their complete source/CAC commit,
  file and DCO bindings after integrating the twelve additional catalog/DSL archives and five viewer
  archives. Preserve the historical fifteen-archive proof, failed CI verdict, authorized geometry
  deferral, later runtime CI gate, and the five original-plan changes still active. Update only the
  current closure ledger; do not infer missing native, human or library release outcomes.
  Proof: all archive files equal their reviewed source commits; living specifications equal the
  reviewed archive chain; strict living/c0319 validation; diff and private staged residue checks.

Task2.15 proof2026-11-03: all242 files in32archives equal their reviewed source commits, both source and CAC archive messages contain the exact maintainer DCO, and all95living files equal reviewed archive chain2d780d9e. Nominal PATH OpenSpec1.3.0 (the archive executor tool) passes95/95living specs and c0319 strict. A separate later1.16.0 strict diagnostic reports17passed/78failed for new style warnings (zero ERROR items); its log is retained, not represented as passing or used to mass-rewrite unrelated contracts. No requirement/scenario loss is excused by tool choice; the independent complete file/byte comparisons passed. Diff check passes; private staged residue must pass before commit. No new native/CI/push; current runtime integration remains independently open.

- [x] 2.16 Reconcile the three additional completed failed/cancelled runs on the separate
  ci-layers-and-coverage branch (41719443567,41717667385,41715402200) with the maintainer's
  cleanup instruction. Retain run/job metadata, complete available logs and artifact bytes,
  SHA256/server sizes/digests and ZIP CRCs before any deletion. Recheck terminal state, delete
  only those reviewed runs and verify404. Do not cancel live work, remove source branches,
  trigger CI, or equate deletion with a passing source verdict. Record any unavailable
  logs explicitly instead of claiming they were captured.

Task2.16 proof: all3 reviewed terminal runs were removed with HTTP204 and each subsequently returned404. Independent retention verified30artifacts/69335748bytes/1280members against server digests/sizes/CRCs, plus3run-logZIPs/1231175bytes/108members and54 top-level job logs. Unavailable macOS logs are explicitly retained as404 evidence:417154 had an assigned runner/eight successful steps/Tests begun, so its full log is NOT claimed captured;417194 had runner0/zero steps, also no available log. Metadata/steps/available ZIPs and HTTP responses remain preserved. Portable receipt docs/evidence/cac-ci-cleanup-extra3-20261103.json binds the complete external receipts/manifest. No rerun, push, live cancellation or source-branch deletion. Post-cleanup remote failed/cancelled counts: {"lgili/Fenolite": 0, "lgili/fenolite-library": 0}. Removal is not a passing CI verdict.

- [x] 2.17 Bind the42 actual source-scoped archives and101living files, clean fast16/source863 plus the54-case later documentary-guard proof and the five actual native viewer passes. Preserve failed-CI/geometry deferral, separate post985 integration, immutable old native reports and active c0246/c0276/Altium/release gates. Proof: complete archive/source/DCO and living-byte comparisons; strict living/c0319; diff/private residue. No additional fast/CI or push is implied.

Task2.17 proof:42actual archive directories/316files match their reviewed source commits and individual maintainer DCO; all101living files equal reviewed chain1789432f and101/101 nominal strict passes. Fast16: clean unchanged8635415a, exit0,22471passed/52skips,1049.99s pytest/1146.12s driver; log/driver/receipt digests recomputed. Every later runtime/config/schema/tool file equals that source; the sole later test file is the independently54passed documentary guard. Actual c0303 local native proof is2pass+1version skip on9.0.9 and3pass on10.0.6, with unchanged inputs/test/workflow; no CI result is inferred. Strict c0319/c0303 and diff pass; private staged scan is required before commit. The c0168 runtime gate and c0246 variant-native WIP remain outside this candidate; no push or CI performed.

- [x] 2.18 Make the three affected documentary file operations explicitly UTF-8 after the retained
  Windows failure of CI41744987316/source723183a1. Preserve every assertion, approval literal and
  historical receipt. Cover both decoding and the temporary archived tasks write without relying
  on the platform locale. Proof: the two complete affected unit modules; a CP1252-default I/O
  control on the two original failing tests; strict c0319, diff and private staged residue.
  This repairs test portability only; the failed CI and independent native gates remain recorded.

Task2.18 proof: retained Windows source723 had2failed/22599passed/4369skipped. The same two tests reproduce2failures under targeted CP1252-default I/O before the fix, then2pass with explicit UTF-8. Both affected modules pass56tests; all171assertion ASTs and every other AST node remain identical after normalizing only the added encoding keywords. Original tasks/evidence/approval bytes are unchanged. Ruff/format, nominal strict c0319 and diff pass; private staged scan reports0hits/7files with the gate on. This is a local portability correction, not a claim that the failed Windows run passed; exact-source CI closure remains pending.

- [x] 2.19 Make the drawn native visual-proof reader survive a later normal archive of c0276.
  Resolve exactly one active or archived change directory; reject missing, non-directory and
  ambiguous matches before reading the proof. Keep explicit UTF-8 and every existing approval,
  evidence, limitation and experimental-writer assertion unchanged. Prove active and archived
  reading under a controlled CP1252 default, plus absence and ambiguity refusals in temporary
  trees only. Proof: the focused reader cases and both complete documentary unit modules,
  existing-assertion AST comparison, focused Ruff/format, strict c0319, diff and private residue.
  Do not move the real change, alter native evidence or claim CI/archival completion.

Task2.19 proof: the extracted old active-only reader reproduces five failures and
one pass for the six lifecycle controls. Strict directory selection then passes
both complete documentary modules: 62 cases in 1.04s, including active/archive
reads under an enforced CP1252 default and four missing/file/ambiguity refusals.
Both positive layouts also run the original full approval/limitation checks;
copied proof bytes remain exact. All 171 preexisting assertion ASTs are unchanged;
the only changed original assignment delegates proof loading to the strict UTF-8
reader. Native proof bytes and production code are unchanged. Focused Ruff,
format, OpenSpec 1.3 strict and diff pass; staged private residue is zero hits in
five files, gate on. No real archive, hypothesis promotion, fast/full/native/CI
or push.

- [x] 2.20 Clarify the three drawn-census comparison subjects from the retained producer:
  source resolver versus original native export, lowered/readback resolver versus original native
  export, and original native export versus rewritten native export. Do not describe the third
  field as lowered-resolver naming equivalence. Preserve all measured counts, hashes and sealed
  receipts, the original H-K-DRAWN-NAMES statement/INFERRED label, and open c0276 gates.
  Proof: read-only producer AST and retained-summary reconciliation; protected-byte comparisons;
  strict c0319, diff and private residue. No native measurement, suite, CI or archive.

Task2.20 proof: producer AST confirms that `partition` consumes `own/native`,
`lowered_partition` consumes `lowered_own/native`, and `lowered_native_partition`
consumes `original_netlist/lowered_native`. The third left subject is constructed
from original native groups, not the lowered resolver. The retained source985
summaries reconcile unchanged: resolver naming differences in 57/87 and 82/113
contexts; original-native/rewritten-native names equal in 87/87 and 113/113.
Twenty-three protected receipt, producer and contract files retain exact bytes.
Removing only the declared documentation inserts and reversing one clarified
label restores both original pages exactly. Runtime, tests, tools and normative
specs are unchanged. OpenSpec 1.3 strict, diff and staged private residue pass
with zero hits in six files, gate on. No new measurement, suite, CI, hypothesis
promotion or c0276 closure occurred.

- [x] 2.21 Reconcile the current documentary closure inventory after the completed fast18
  and later isolated local integrations. Bind only existing source-specific proofs for
  c0329/c0330/c0350 local tasks, preserving their independent CI/native boundaries,
  all42 actual archives, earlier failed verdicts and source/future-release limits.
  Record c0305 visual inspection, c0168/c0246 local integration, Windows UTF-8
  repair and configurable viewer UI against their actual sources; keep the
  locked-Mac limitation and current CI uncertainty explicit. No new suite, CAD,
  Royal run, CI or archive is requested. Proof: existing receipt/log/driver and
  source-file SHA comparisons; generated checks where applicable; nominal strict
  OpenSpec, git diff --check and staged private-enabled residue.


Task2.21 proof — 2026-11-03: fast18 log/driver/receipt hashes and six retained
c0350 native logs match; relevant source/test/tool paths are unchanged between
ad8 and010. Three generator --check commands pass without a test/native rerun.
Three local tasks are completed with individual DCO commits and portable proof
records; all independent CI/native/archive gates remain. The current ledger has
a dated addendum, preserving every earlier snapshot and42 actual archives.
Four cleanup candidates were reviewed,31 cherry-picked files match and the
negative-control source is ancestral; nothing was deleted. Nominal strict,
diff and staged private-enabled residue pass on this documentation.
No current CI green, human review or release is inferred.
