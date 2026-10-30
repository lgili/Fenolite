## 0. Entry check

- [x] 0.1 Read `openspec list` and the living specs this change touches (`layout-lens`, `design-dsl`, `cli-contract`, `check-overlay`, `package-layering`). Write under this task, with the date and the base commit:
  - whether c0249 (design lock) is archived, and the name of its lock reader, its hand-ref rule and its `--frozen` refusal code (phase 1 does not wait for it; tasks 5.1 and 3.6 do);
  - which open change holds a delta of "Placement precedence", "Sync of the source tree", "Layout issue codes", "Placements file in a build" or "Sync command" (if one was archived, regenerate the MODIFIED block from the living text);
  - whether c0245 is archived (task 6.2 waits for it);
  - the maintainer's answers to open questions 1 to 7 of `design.md`.

  Proof: `timeout 180 npx -y @fission-ai/openspec validate c0250-manual-edit-merge --strict`.

  2026-10-29, base `3cabfe5a` (branch `cac/c0250-manual-edit-merge` on `circuits-as-code`):
  - c0249 (design lock) is not archived and not merged in `circuits-as-code`; it is implemented in parallel
    on its own branch. Its proposal names `fenolite.dsl.lock.read_lock`, hand refs win over lock entries,
    and `build --frozen` refuses with `FEN-7004` (exit 7). Phase 1 here does not use it; 3.6 and 5.1 stay
    open.
  - Open deltas of the same requirements: only c0255-relative-placement (MODIFIED "Placement precedence").
    None is archived, so the MODIFIED blocks of this change stand.
  - c0245 is not archived (other branch): 6.2 waits.
  - Open questions 1 to 7: no maintainer answer recorded; the implementation follows the recommendations
    of `design.md` (output-folder base record, bare numbers, no Altium CAD side).

## 1. Files

- [x] 1.1 Add `src/fenolite/lens/edits.py` with `PROPERTIES`, `PropertyKey`, `EDIT_ISSUE_CODES` and `EVIDENCE`, and its row in the import-graph test (requirements "Edit merge module", "Edit merge public names", "Pure and exact merge functions", "Property keys", "Merged property names"). Proof: `uv run pytest tests/unit/test_import_graph.py tests/unit/lens/test_edit_merge.py -k "import or key" -q`.
  2026-10-29: `src/fenolite/lens/edits.py`; the import edges are asserted by `test_edit_merge.py::test_import_edges` (the package table of `test_import_graph.py` already allows `lens` → `backends`, `model`); proof passed.
- [x] 1.2 Add the base record: `BaseEntry`, `BaseRecord`, `read_base`, `write_base`, canonical JSON, `edit.base-invalid` (requirements "Base record form", "Base record reading"). Proof: `uv run pytest tests/unit/lens/test_base_record.py -q`.
  2026-10-29: proof passed (14 tests).
- [x] 1.3 Add the edits file: `PartEdits`, `EditsFile`, `read_edits`, `write_edits`, the `over` rules, the printing order and a round-trip property test (requirements "Edits file schema" to "Edits file round trip"). Proof: `uv run pytest tests/unit/lens/test_edits_file.py -q`.
  2026-10-29: proof passed, round trip by hypothesis (150 examples).

## 2. The rule

- [x] 2.1 Add `merge_property`, `Decision` and `Conflict` with the four reasons, the removed-request rule, the no-base rule and the locked-request rule (requirements "Three-way property merge", "Removed request keeps the CAD value", "Merge without a base", "Locked requests win", "Decision record", "Conflict record", "Stale and redundant edits"). Proof: `uv run pytest tests/unit/lens/test_edit_merge.py -k "table or merge" -q`.
  2026-10-29: proof passed.
- [x] 2.2 Add `Take` and `parse_takes`: grammar, specificity, contradictions, `edit.take-unused` (requirements "Take specificity", "Takes are reported", parsing part). Proof: `uv run pytest tests/unit/lens/test_edit_merge.py -k take -q`.
  2026-10-29: proof passed.
- [x] 2.3 Add the CAD sides: board and schematic values compared with `out` on their own, `sides-disagree`, multi-unit symbols (requirements "CAD sides compared on their own", "Units of a symbol", pure part, on read models). Proof: `uv run pytest tests/unit/lens/test_edit_merge.py -k sides -q`.
  2026-10-29: proof passed; multi-unit symbols in `test_units_of_a_symbol_disagree`.

## 3. Build

- [x] 3.1 `lens.build` and `lens.altium` write `<out>/fenolite-base.json` as a planned write recorded in `.fenolite/build.json`; regenerate `tests/data/lens/sync_minimal/` and every committed build fixture that gains the file (requirements "Base record file", "Base record code side", "Base record is protected", "Altium builds have no CAD side"). Proof: `uv run pytest tests/unit/lens/test_base_record.py tests/unit/lens/test_build_files.py tests/unit/lens/test_build_bytes_pinned.py -q`.
  2026-10-29: `build_design(write_base=True)` (the command always passes it; direct callers keep their bytes) and the Altium branch of `cmd_build` write the record. `tests/data/lens/sync_minimal/` gains it; the pinned digest tables of `test_unused_keys*.py` were recorded again: only `fenolite-base.json` and `.fenolite/build.json` change, every other file keeps its bytes. Without `.fenolite/build.json` the base record is not guarded, so a clone without the cache builds as the original. Proof passed.
- [x] 3.2 Change `effective_placements` to the three-way rule for `position` and `rotation`, with `base`, `takes`, `cad-locked`, `edit.code-wins` and `edit.base-missing` (MODIFIED "Placement precedence", all scenarios). Proof: `uv run pytest tests/unit/lens/test_preserve_place.py tests/unit/lens/test_placement_source.py -q`.
  2026-10-29: `lens.preserve.decide_placements` (the three-way rule; `effective_placements` keeps its two-value return and old behaviour without `base`); proof passed.
- [x] 3.3 `read_existing` gains the schematic texts; add `merge_properties` and call it from `prepare`, so `build_design` builds the merged design; footprints edited in KiCad are kept (requirements "Property merge in a build", "Code side of a build", "Property merge result", "Footprints swapped in the CAD tool", "Merge without a CAD file", "Unrecorded CAD edits", "Edits in the build result", "CAD sides of a property", "Schematic read as a CAD side", "Base entries follow aliases", "The cache never decides", "Properties outside the merge"). Proof: `uv run pytest tests/unit/lens/test_build_preserve.py tests/unit/lens/test_edit_merge.py -k build -q`; measure the cost of the schematic read on `examples/yardstick` and write it under this task.
  2026-10-29: the schematic sheets are read by `cmd_build.schematic_sheets` and passed to `prepare(sheets=...)` rather than through `read_existing`. Proof passed. Cost of the schematic read: `examples/yardstick` needs the KiCad libraries, which this machine lacks; on `examples/board_40parts` (3 sheets, 42 symbols) it is 86 ms of a 2.1 s rebuild (`--dry-run`), on `acceptance_v03` 18 ms.
- [x] 3.4 `cmd_build` reads `edits.toml` and otherwise `placements.toml`, `edit.legacy-file`, edits applied for `--discard-layout` and `--target altium` (MODIFIED "Placements file in a build", all scenarios). Proof: `uv run pytest tests/unit/cli/test_build_command.py tests/unit/lens/test_placement_source.py -k "edits or placements" -q`.
  2026-10-29: `cmd_build.read_edit_source`; proof passed (`test_build_command.py -k edits`).
- [x] 3.5 Add `--take` to `fenolite build`, `result.preserved.edits`, and the `sync.conflict` exit 5 (requirements "Conflict finding", "Conflicts stop writes", "Take option of build", "Take effects"). Proof: `uv run pytest tests/unit/cli/test_build_take.py -q`; `uv run python tools/gen_agent_guide.py` and `uv run pytest tests/unit/agent/test_pages.py -q` after the option is added.
  2026-10-29: `--take` on `build`, `result.preserved.edits`, conflicts refuse every write (exit 5); proof passed, guide regenerated, `test_pages.py` passed.
- [x] 3.6 (waits for c0249) `--frozen` refuses `--take` and `edit.unrecorded` with c0249's code (requirement "Frozen builds refuse unrecorded edits"). Proof: `uv run pytest tests/unit/cli/test_build_take.py -k frozen -q`.
  2026-10-29: was open: c0249 (`--frozen`, `FEN-7004`) was not merged in `circuits-as-code`.
  2026-10-30: c0249 is merged (base `52f32e8c`). `cli._lock.refuse_frozen_edits` raises `EditsFrozenError`
  (a `LockFrozenError`, `FEN-7004`, exit 7) with one `lock.changed` error per take (`where` `--take`) and
  per `edit.unrecorded` key; proof passed (2 tests).
- [x] 3.7 Pass the `EDIT_ISSUE_CODES` through `PRESERVE_ISSUE_CODES` and `BUILD_ISSUE_CODES` (MODIFIED "Layout issue codes"; requirements "Edit merge error and warning codes", "Edit merge info codes"). Proof: `uv run pytest tests/unit/lens/test_preserve_issues.py tests/unit/lens/test_edit_merge.py -k closed_set -q`.
  2026-10-29: `EDIT_ISSUE_CODES` join `BUILD_ISSUE_CODES`; proof passed.

## 4. Sync

- [x] 4.1 Add `capture_edits` (requirements "Capture of CAD edits" to "Edits of parts the board does not place"). Proof: `uv run pytest tests/unit/lens/test_edit_merge.py -k capture -q`.
  2026-10-29: `capture_edits` takes the script's requests (`requests`) and the off-board parts (`off_board`) as arguments, because `lens.edits` may not import `dsl` or `lens.preserve`; proof passed.
- [x] 4.2 Change `plan_sync` to write `edits.toml`, migrate `placements.toml`, block on conflicts and limit `sync.value-differs` to parts without a base (MODIFIED "Sync of the source tree", all scenarios). Proof: `uv run pytest tests/unit/lens/test_sync.py -q`.
  2026-10-29: proof passed. Deviation: the hint of `sync.value-differs` without a base names the base record rather than `--take cad:…`, because a take resolves conflicts only and a part without a base has none.
- [x] 4.3 Change `cmd_sync`: read the base record and `edits.toml`, refuse `--take`, and make `--check` exit 5 on conflicts (MODIFIED "Sync command", all scenarios). Proof: `uv run pytest tests/unit/cli/test_sync_cmd.py tests/unit/cli/test_hermetic_examples.py -q`.
  2026-10-29: `--take` on `sync` is a registered option that exits 2 with `FEN-2001` and the hint; `first_difference` compares tables without their trailing blank line. Proof passed.

## 5. References and user properties

- [x] 5.1 (waits for c0249) Merge `reference`: lock refs as the code side, and edits refs as hand refs (requirement "Reference edits"). Proof: `uv run pytest tests/unit/lens/test_edit_merge.py -k reference -q`.
  2026-10-29: was open: needed c0249's lock refs, not merged in `circuits-as-code` then.
  2026-10-30: `merge_properties` and `capture_edits` merge `reference` (code side: the ref the part is
  lowered with); `dsl.lock.hand_refs` makes an edit's ref a hand ref of the lock when it was recorded over
  the explicit or locked ref; `sync` reads the lock (`cli._lock.locked_refs`) for its code side. Proof passed
  (4 tests). Deviation: two parts of a lock design that meet on one ref are renumbered by c0249's rule
  (`lock.ref-taken`); `model.duplicate-ref` (exit 5) comes when explicit refs and edits meet.
- [x] 5.2 Merge the user properties the script names, and treat a removed property as `""` (requirements "User property edits", "Second-phase properties"). Proof: `uv run pytest tests/unit/lens/test_edit_merge.py -k property -q`; `uv run pytest tests/unit/lens/test_build_properties.py -q`.
  2026-10-29: was open (second phase).
  2026-10-30: `property:<name>` for each user property the script names (`edits.user_names`), a CAD side
  without it counts as `""`, one added in KiCad stays out of the base record. The base record gains
  `reference` and the named user properties, so the pinned digests of `fenolite-base.json` and
  `.fenolite/build.json` in `test_unused_keys*.py` were recorded again. Proof passed (4 tests;
  `test_build_properties.py` 13 passed).

## 6. Viewer

- [x] 6.1 `view --check` accepts `build` and `sync` replies and marks `sync.conflict` on its footprint (requirement "Edit conflicts on the board"; the command lines of "Conflict resolution from the viewer"). Proof: `uv run pytest tests/unit/view/test_check_overlay.py -q`.
  2026-10-29: was open: left for a later batch.
  2026-10-30: `view.check_overlay.read_reply` reads `check`, `build` and `sync` replies; a `sync.conflict` is
  marked on the footprint of its `fenolite.path` and carries `commands`, the two `build --take ... --dry-run`
  lines, shown on selection (the page runs nothing); `docs/viewer.md` updated. Proof passed (6 tests).
- [ ] 6.2 (waits for c0245) Add the Properties view of a conflict and the "Take code" and "Take CAD" actions through the Pending panel (requirement "Conflict resolution from the viewer"). Proof: `uv run pytest tests/unit/view/test_check_overlay.py -k workbench -q`.
  2026-10-29: open: waits for c0245.

## 7. Fixture, oracle, docs and guide

- [x] 7.1 Author `tests/data/lens/edit_merge/` and `tests/_layout_edit.py::edit_properties`, and add the acceptance loop (requirement "Edit merge acceptance fixture"). Proof: `uv run pytest tests/unit/lens/test_edit_merge_acceptance.py -q`.
  2026-10-29: was open: the fixture folder and the acceptance loop were not written yet.
  2026-10-30: `tests/data/lens/edit_merge/design.py` (Fenolite catalog, module `led`, user property on
  `R1`; in `tests/data/MANIFEST.toml`) and `test_edit_merge_acceptance.py`: value, footprint, reference,
  user property and positions edited on the board and both sheets, rebuild, sync, rebuild twice with
  equal bytes. Fix found by it: `cmd_build` selects the catalog definitions from the merged design, so a
  footprint swapped in KiCad for another catalog footprint resolves. Proof passed.
- [ ] 7.2 Add the oracle test on 9.0.9 and 10.0.6 (requirement "Merged files accepted by KiCad"). Proof: CI job `kicad` green on the pushed commit for `tests/kicad/lens/test_edit_merge_oracle.py`.
  2026-10-29: open: depends on 7.1; CI runs with the batch.
  2026-10-30: `tests/kicad/lens/test_edit_merge_oracle.py` written; passed locally on `kicad/kicad:10.0.6`
  (docker, targets 9 and 10). KiCad reports `lib_footprint_mismatch` for `R2`, whose id the token edit swaps
  without new pads (KiCad's "Change Footprint" would replace them); the test leaves that one type out.
  Open until the CI `kicad` job (9.0.9 and 10.0.6) is green: CI runs with the batch.
- [x] 7.3 Register `H-K-EDIT-SCH-VALUE` in `docs/hypotheses.md` and set `lens.edits.EVIDENCE` (requirements "Edit merge evidence", "Schematic edit hypothesis"). Proof: `uv run pytest tests/unit/test_hypotheses_register.py tests/unit/lens/test_edit_merge.py -k evidence -q`.
  2026-10-29: the proposed row of `H-K-EDIT-SCH-VALUE` now names its test and kit request, `INFERRED`; proof passed.
- [x] 7.4 Update `docs/lens.md` (the five sections, the table, the removal of the two-way sentence and of the `placements.toml` section's write rule) and `docs/cli-contract.md` (`build --take`, `sync`) (requirement "Three-way merge is documented"). Proof: `uv run pytest tests/unit/lens/test_edit_merge.py -k docs -q`; `make check-fast`.
  2026-10-29: `docs/lens.md` (five sections, table, the two-way sentence and the `placements.toml` write rule replaced) and `docs/cli-contract.md` (`build --take`, `sync`); proof passed.
- [x] 7.5 Add the `explain.toml` entries and the guide lines: a `fenolite-recipe` in `recovery.md` for `sync.conflict` with `--take`, and the edit loop in `board-workflow.md`; then run `uv run python tools/gen_agent_guide.py` (requirement "Conflicts are explained and taught"). Proof: `uv run pytest tests/unit/agent/test_pages.py tests/unit/cli/test_explain_cmd.py -q`.
  2026-10-29: `explain.toml` entries for the seven codes and `sync.placements-migrated`; recipe `conflict` in `recovery.md` (sandbox `conflict` in `tests/unit/agent/_sandbox.py`; the page stays under 12000 bytes, so the recipe ends with the take and the prose names the sync), the edit loop in `board-workflow.md`; guide regenerated; proof passed.
- [ ] 7.6 Add the edit loop to an example: `examples/blink_2layer/README.md` (build, edit in KiCad, build, sync, conflict, take), run by the example tests. Proof: `uv run pytest tests/unit/test_examples.py -q`.
  2026-10-29: open: not done in this batch.

## 8. Closing

- [ ] 8.1 Run `make check-fast` and the residue scan; publish the batch to the working branch for CI. Proof: `make check-fast`; CI `unit` and `kicad` jobs green on the exact commit.
  2026-10-29: open: `make check-fast` passes locally; CI runs with the batch (the coordinator pushes it).
- [ ] 8.2 Update the evidence labels: `docs/evidence/` rows of the merge at `INFERRED`, `H-K-EDIT-SCH-VALUE` as registered, and the oracle results. Proof: `uv run pytest tests/unit/test_provenance.py tests/unit/test_hypotheses_register.py -q`.
  2026-10-29: open.
- [x] 8.3 Add the CHANGELOG entry under `## [Unreleased]`: three-way merge, `edits.toml`, `fenolite-base.json`, `build --take`, `sync.conflict`, and the changed meaning of an unlocked `place()` after the first build. This waits for dev to open `0.7.0.dev0`, because the v0.6 guard requires `[Unreleased]` to be empty. Proof: `uv run pytest tests/unit/test_release_record_v06.py tests/unit/test_release_tool.py -q`; `make check-fast`.
  2026-10-29: entry under `## [Unreleased]` › `### Added` on `circuits-as-code`, after the c0249 entry, once
  `dev` (0.7.0.dev0) was merged into it; it names the changed meaning of an unlocked `place()` (`edit.code-wins`).
  2026-10-29: was open: waited for dev's 0.7.0.dev0 (the v0.6 guard needs `[Unreleased]` empty).
- [ ] 8.4 Validate and archive once every task is closed and CI is green. Proof: `npx -y @fission-ai/openspec validate c0250-manual-edit-merge --strict`.
