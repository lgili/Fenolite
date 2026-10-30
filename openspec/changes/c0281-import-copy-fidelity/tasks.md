## 0. Entry check

- [ ] 0.1 Read `openspec list`, the living specs `copper-check`, `design-equivalence`, `design-conversion`,
  `design-dsl`, and the changes c0275, c0276, c0278 and c0279. Write under this task the date, the base
  commit, which of c0275, c0278 and c0279 are archived (this change ADDs to their capabilities and archives
  after them), and the answers to the open questions of `design.md`. Proof:
  `openspec validate c0281-import-copy-fidelity --strict`; `make check-fast`.
  Entry check, 2026-10-30, base `8dab89d6` (`circuits-as-code`): c0275, c0276 (most of it), c0278 and c0279 are not archived; c0275, c0276 and c0278 are merged in the base, c0279 is not implemented (no `fenolite library` audit, replay or gate). This change ADDs requirements to `board-to-code`, `fidelity-proof` and `fenolite-library` and archives after c0275, c0278 and c0279. The open questions of `design.md` are decided there (delegated). `make check-fast PYTEST_WORKERS=2` passed; `openspec validate` cannot run here (no `openspec` CLI), so the task stays open for that proof (maintainer).

## 1. Copy mode (issue 1)

- [x] 1.1 `PROVENANCE.json` gains `"copy": true`; add `fenolite.importer.provenance.copy_mode` (scenario
  "Written and read"). Proof: `uv run pytest tests/unit/importer/test_copy_mode.py -q`.
  Done 2026-10-30: `copy: true` in the record, `copy_mode`, `copy_file` and `import_record` in `importer/provenance.py`; proof passed.
- [x] 1.2 `fenolite build`: without `--copper-check`, `warn` for a copy; `result.copper_check.mode_source`;
  schema regenerated (scenario "Imported folder builds"). Proof:
  `uv run pytest tests/unit/cli/test_build_copy_mode.py -q`; `uv run python tools/gen_schemas.py --check`.
  Done 2026-10-30: `cmd_build.copper_mode`, `mode_source` on both targets, the provenance file listed among the inputs; `build` has no result schema, so nothing to regenerate; proof passed.
- [x] 1.3 `verify-source --copper-check refuse|warn`, the copy default, `result.build.copper_check` and
  `result.build.copy` (scenarios of "Copy mode in verify-source"). Proof:
  `uv run pytest tests/unit/cli/test_verify_source_copy.py -k copy tests/unit/cli/test_verify_source.py -q`.
  Done 2026-10-30: `--copper-check`, `Provenance.copy`, `result.build.copper_check` and `copy`, schema regenerated; proof passed.

## 2. Pads on no net (issue 2)

- [x] 2.1 Level 2 reads an `unconnected-(…)` net held by one element as no net (scenario "Two pads of one
  number"). Proof: `uv run pytest tests/unit/checks/equivalence/test_c0281_levels.py -k open tests/unit/checks/equivalence -q`.
  Done 2026-10-30: elements, not pads, counted in `levels._elements`; proof passed.
- [x] 2.2 The vendored symbol has no pin for a pad number on no net in every instance (scenario "Shield
  pads stay on no net"). Proof: `uv run pytest tests/unit/importer/test_no_net_pads.py tests/unit/importer -q`.
  Done 2026-10-30: `vendor.vendor` leaves out numbers no instance nets; the test fails without the change; proof passed. On the demo `video` (in a temporary folder) level 2 is now `equal`.

## 3. KiCad's clearance tolerance (issue 3)

- [x] 3.1 Measure KiCad's verdict at `c − δ` on the authored parity benches (`kicad-cli` 10.0.6), record the
  table in `design.md` and `docs/formats/kicad/copper.md`, register `H-K-COPPER-EPSILON`, and add
  `tests/kicad/copper/test_drc_tolerance.py` (scenario "Measured against KiCad"). Proof:
  `FENOLITE_KICAD_CLI=docker:kicad/kicad:10.0.6 uv run pytest tests/kicad/copper/test_drc_tolerance.py -rA`;
  `uv run pytest tests/unit/test_hypotheses_register.py -q`.
  Done 2026-10-30: measured in the local image `kicad/kicad:10.0.6` (table in `design.md`, decision 3); `H-K-COPPER-EPSILON` registered pending; `docs/formats/kicad/copper.md` row updated; `tests/kicad/copper/test_drc_tolerance.py` passed there (4 passed, 38 rows agree).
- [x] 3.2 `DesignRules.clearance_tolerance`, `check_copper(..., tolerance=)`, the KiCad rules source, the
  build's guard and the stage (scenario "KiCad's tolerance"; "Strict comparison" keeps passing). Proof:
  `uv run pytest tests/unit/checks/test_copper_tolerance.py tests/unit/checks/test_copper.py tests/kicad/copper/test_parity_bench.py -q`.
  Done 2026-10-30: `DesignRules.clearance_tolerance`, `KICAD_DRC_EPSILON_NM`, `check_copper(tolerance=)`, the guard and the stage; proof passed.
- [ ] 3.3 The `kicad-9` and `kicad-10` jobs run `tests/kicad/copper/test_drc_tolerance.py`; raise
  `H-K-COPPER-EPSILON` to `KICAD-VERIFIED (9.0.x, 10.0.x)` after both pass. Proof: the KiCad jobs of the
  commit on GitHub CI are green.
  Open 2026-10-30: CI runs with the batch (not pushed here).

## 4. Losses the import reports (issues 4 and 5)

- [x] 4.1 The unexpressed kinds `outline-width` and `layer-table` (scenario "Wide outline and short layer
  table"). Proof: `uv run pytest tests/unit/importer/test_unexpressed_c0281.py -q`.
  Done 2026-10-30: `emit.design._losses` (KiCad sources only: an Altium document's outline and layers are those of its conversion); proof passed.

## 5. Proof fixes (issues 4, 5, 7, 8, 9)

- [x] 5.1 The kinds `layer-field`, `graphic-field` and `opaque-count`, their codes and `explain.toml`
  entries (scenario "Kinds and codes"). Proof: `uv run pytest tests/unit/checks/equivalence/test_codes.py -q`.
  Done 2026-10-30: the three kinds, codes, `explain.toml`, `docs/equivalence.md` and `docs/cli-contract.md`; schemas regenerated; proof passed.
- [x] 5.2 Level 7 graphic widths and the lens property (scenarios "Outline drawn wider", "Built board
  against an original"). Proof: `uv run pytest tests/unit/checks/equivalence/test_c0281_levels.py -k "width or lens" -q`.
  Done 2026-10-30: `shapes._graphics` keys without width and compares it, `LENS_FIELDS`; proof passed.
- [x] 5.3 Level 6 pairs layers by name (scenario "Two user layers missing"). Proof:
  `uv run pytest tests/unit/checks/equivalence/test_c0281_levels.py -k layers tests/unit/checks/equivalence/test_level6.py -q`.
  Done 2026-10-30: `rules._layers` by name, kind and relative order; proof passed.
- [x] 5.4 `opaque-count` in `verify-source` (scenario "Teardrops left out"). Proof:
  `uv run pytest tests/unit/cli/test_verify_source_copy.py -k opaque -q`.
  Done 2026-10-30: `importer.coverage.root_kinds` and `cmd_verify_source._opaque_differences`; proof passed.
- [x] 5.5 One project's files for `--against x.kicad_pro` (scenario "Two projects in one folder"). Proof:
  `uv run pytest tests/unit/cli/test_verify_source_copy.py -k project -q`.
  Done 2026-10-30: `cmd_verify_source._project_files` (sheet tree by `sch.sheet_files`) and `sheet_scenes(root, sheets)`; proof passed.

## 6. Bottom-side angles (issue 6)

- [x] 6.1 The derive turns bottom angles back as `θ − stored` (scenario "Reference at 270° on the
  bottom"). Proof: `uv run pytest tests/unit/library/test_derive.py -q`.
  Done 2026-10-30: `embed.local_footprint` turns bottom angles back as `(θ − stored) mod 360°`; the test fails without the change (pads too, not only fields); proof passed.

## 7. Level S and the gate (issue 10)

- [x] 7.1 `--record` writes `fidelity.proof.skipped` (scenario "Level S recorded with its reason").
  Proof: `uv run pytest tests/unit/cli/test_verify_source_copy.py -k skipped -q`.
  Done 2026-10-30: `fidelity.proof.skipped`; proof passed.
- [ ] 7.2 The library proof gate accepts a skipped level with a recorded reason (scenario "Level S skipped
  with a reason"). Proof: `uv run pytest tests/unit/library/test_proof_gate.py -k skipped -q`.
  Open 2026-10-30: waits for c0279 task 4.2 (the proof gate is not implemented on `circuits-as-code`); the requirement is written for it.

## 8. Replayable steps (issue 12)

- [ ] 8.1 `library audit` refuses a step holding `--plan`; `replay` runs steps as recorded (scenario "Step
  with a plan id"). Proof: `uv run pytest tests/unit/library/test_audit.py -k plan_step -q`.
  Open 2026-10-30: waits for c0279 tasks 1.3 and 4.1 (`library audit` and `replay` are not implemented); the step form is specified for them. The library's current records already use `--confirm` alone.

## 9. Issue 11

- [x] 9.1 Investigate J1 and J2 of `royalblue54L_feather` (KiCad DRC of the demo, the build's outline and
  placements, the derive's refusal) and record the findings in `design.md`, decision 9. Proof: the
  findings are written with the commands that gave them.
  Done 2026-10-30: findings in `design.md`, decision 9 (KiCad 10.0.6 `pcb drc` of the demo reports the same edge clearances of J1 and J2; J1 is refused by the flip because of `chamfer`); the commands are listed there too.

## 10. Documentation and guide

- [x] 10.1 `docs/import.md` (copy mode, the new kinds, pads on no net), `docs/fidelity.md` (copy mode,
  `--copper-check`, one project, `opaque-count`, `fidelity.proof.skipped`), `docs/equivalence.md` (the three
  kinds, level 6 pairing, level 7 widths and lens field), `docs/cli-contract.md` (`verify-source
  --copper-check`, `build` copy mode). Proof: `uv run pytest tests/consistency tests/unit/checks/equivalence/test_codes.py -q`.
  Done 2026-10-30: `docs/import.md`, `docs/fidelity.md`, `docs/equivalence.md`, `docs/cli-contract.md`; proof passed.
- [x] 10.2 Agent guide (AGENTS.md rule 6): a tested line for `verify-source --copper-check` and copy mode
  on the page `checks`; run `uv run python tools/gen_agent_guide.py`. Proof:
  `uv run pytest tests/unit/agent/test_pages.py -q`.
  Done 2026-10-30: two lines on the page `checks` (a `fenolite-cmd` line with `--copper-check warn` and the copy-mode sentence); `commands.md` regenerated; proof passed.

## 11. Closing

- [x] 11.1 Run the residue tests (no third-party demo file committed). Proof: `uv run pytest tests/residue -q`.
  Done 2026-10-30: proof passed.
- [x] 11.2 Update the evidence labels of the new behaviours (`H-K-COPPER-EPSILON`, `docs/formats/kicad/copper.md`).
  Proof: `uv run pytest tests/unit/test_hypotheses_register.py tests/unit/test_inferred_hypotheses.py -q`.
  Done 2026-10-30: `H-K-COPPER-EPSILON` pending with the first record; the copper boundary row of `docs/formats/kicad/copper.md`; proof passed.
- [x] 11.3 `CHANGELOG.md`: one entry under `## [Unreleased]`. Proof: `uv run pytest tests/unit -k changelog -q`.
  Done 2026-10-30: entry "Imported boards proved as copies" under `## [Unreleased]` › `### Added`; proof passed.
- [ ] 11.4 `make check-fast` passes locally; publish the batch to its working branch and confirm the unit
  and KiCad jobs on the exact commit. Proof: `make check-fast`; the required CI jobs are green on the commit.

  Open 2026-10-30: `make check-fast PYTEST_WORKERS=2` passed locally; CI runs with the batch.