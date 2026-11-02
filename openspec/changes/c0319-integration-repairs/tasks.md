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
- [ ] 2.2 Repeat the complete local fast gate on the stable repaired candidate.
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
