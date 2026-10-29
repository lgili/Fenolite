## 0. Entry check

- [ ] 0.1 Read `openspec list` and the living specs this change touches (`layout-lens`, `design-dsl`, `cli-contract`, `check-overlay`, `package-layering`). Write under this task, with the date and the base commit:
  - whether c0249 (design lock) is archived, and the name of its lock reader, its hand-ref rule and its `--frozen` refusal code (phase 1 does not wait for it; tasks 5.1 and 3.6 do);
  - which open change holds a delta of "Placement precedence", "Sync of the source tree", "Layout issue codes", "Placements file in a build" or "Sync command" (if one was archived, regenerate the MODIFIED block from the living text);
  - whether c0245 is archived (task 6.2 waits for it);
  - the maintainer's answers to open questions 1 to 7 of `design.md`.

  Proof: `timeout 180 npx -y @fission-ai/openspec validate c0250-manual-edit-merge --strict`.

## 1. Files

- [ ] 1.1 Add `src/fenolite/lens/edits.py` with `PROPERTIES`, `PropertyKey`, `EDIT_ISSUE_CODES` and `EVIDENCE`, and its row in the import-graph test (requirements "Edit merge module", "Edit merge public names", "Pure and exact merge functions", "Property keys", "Merged property names"). Proof: `uv run pytest tests/unit/test_import_graph.py tests/unit/lens/test_edit_merge.py -k "import or key" -q`.
- [ ] 1.2 Add the base record: `BaseEntry`, `BaseRecord`, `read_base`, `write_base`, canonical JSON, `edit.base-invalid` (requirements "Base record form", "Base record reading"). Proof: `uv run pytest tests/unit/lens/test_base_record.py -q`.
- [ ] 1.3 Add the edits file: `PartEdits`, `EditsFile`, `read_edits`, `write_edits`, the `over` rules, the printing order and a round-trip property test (requirements "Edits file schema" to "Edits file round trip"). Proof: `uv run pytest tests/unit/lens/test_edits_file.py -q`.

## 2. The rule

- [ ] 2.1 Add `merge_property`, `Decision` and `Conflict` with the four reasons, the removed-request rule, the no-base rule and the locked-request rule (requirements "Three-way property merge", "Removed request keeps the CAD value", "Merge without a base", "Locked requests win", "Decision record", "Conflict record", "Stale and redundant edits"). Proof: `uv run pytest tests/unit/lens/test_edit_merge.py -k "table or merge" -q`.
- [ ] 2.2 Add `Take` and `parse_takes`: grammar, specificity, contradictions, `edit.take-unused` (requirements "Take specificity", "Takes are reported", parsing part). Proof: `uv run pytest tests/unit/lens/test_edit_merge.py -k take -q`.
- [ ] 2.3 Add the CAD sides: board and schematic values compared with `out` on their own, `sides-disagree`, multi-unit symbols (requirements "CAD sides compared on their own", "Units of a symbol", pure part, on read models). Proof: `uv run pytest tests/unit/lens/test_edit_merge.py -k sides -q`.

## 3. Build

- [ ] 3.1 `lens.build` and `lens.altium` write `<out>/fenolite-base.json` as a planned write recorded in `.fenolite/build.json`; regenerate `tests/data/lens/sync_minimal/` and every committed build fixture that gains the file (requirements "Base record file", "Base record code side", "Base record is protected", "Altium builds have no CAD side"). Proof: `uv run pytest tests/unit/lens/test_base_record.py tests/unit/lens/test_build_files.py tests/unit/lens/test_build_bytes_pinned.py -q`.
- [ ] 3.2 Change `effective_placements` to the three-way rule for `position` and `rotation`, with `base`, `takes`, `cad-locked`, `edit.code-wins` and `edit.base-missing` (MODIFIED "Placement precedence", all scenarios). Proof: `uv run pytest tests/unit/lens/test_preserve_place.py tests/unit/lens/test_placement_source.py -q`.
- [ ] 3.3 `read_existing` gains the schematic texts; add `merge_properties` and call it from `prepare`, so `build_design` builds the merged design; footprints edited in KiCad are kept (requirements "Property merge in a build", "Code side of a build", "Property merge result", "Footprints swapped in the CAD tool", "Merge without a CAD file", "Unrecorded CAD edits", "Edits in the build result", "CAD sides of a property", "Schematic read as a CAD side", "Base entries follow aliases", "The cache never decides", "Properties outside the merge"). Proof: `uv run pytest tests/unit/lens/test_build_preserve.py tests/unit/lens/test_edit_merge.py -k build -q`; measure the cost of the schematic read on `examples/yardstick` and write it under this task.
- [ ] 3.4 `cmd_build` reads `edits.toml` and otherwise `placements.toml`, `edit.legacy-file`, edits applied for `--discard-layout` and `--target altium` (MODIFIED "Placements file in a build", all scenarios). Proof: `uv run pytest tests/unit/cli/test_build_command.py tests/unit/lens/test_placement_source.py -k "edits or placements" -q`.
- [ ] 3.5 Add `--take` to `fenolite build`, `result.preserved.edits`, and the `sync.conflict` exit 5 (requirements "Conflict finding", "Conflicts stop writes", "Take option of build", "Take effects"). Proof: `uv run pytest tests/unit/cli/test_build_take.py -q`; `uv run python tools/gen_agent_guide.py` and `uv run pytest tests/unit/agent/test_pages.py -q` after the option is added.
- [ ] 3.6 (waits for c0249) `--frozen` refuses `--take` and `edit.unrecorded` with c0249's code (requirement "Frozen builds refuse unrecorded edits"). Proof: `uv run pytest tests/unit/cli/test_build_take.py -k frozen -q`.
- [ ] 3.7 Pass the `EDIT_ISSUE_CODES` through `PRESERVE_ISSUE_CODES` and `BUILD_ISSUE_CODES` (MODIFIED "Layout issue codes"; requirements "Edit merge error and warning codes", "Edit merge info codes"). Proof: `uv run pytest tests/unit/lens/test_preserve_issues.py tests/unit/lens/test_edit_merge.py -k closed_set -q`.

## 4. Sync

- [ ] 4.1 Add `capture_edits` (requirements "Capture of CAD edits" to "Edits of parts the board does not place"). Proof: `uv run pytest tests/unit/lens/test_edit_merge.py -k capture -q`.
- [ ] 4.2 Change `plan_sync` to write `edits.toml`, migrate `placements.toml`, block on conflicts and limit `sync.value-differs` to parts without a base (MODIFIED "Sync of the source tree", all scenarios). Proof: `uv run pytest tests/unit/lens/test_sync.py -q`.
- [ ] 4.3 Change `cmd_sync`: read the base record and `edits.toml`, refuse `--take`, and make `--check` exit 5 on conflicts (MODIFIED "Sync command", all scenarios). Proof: `uv run pytest tests/unit/cli/test_sync_cmd.py tests/unit/cli/test_hermetic_examples.py -q`.

## 5. References and user properties

- [ ] 5.1 (waits for c0249) Merge `reference`: lock refs as the code side, and edits refs as hand refs (requirement "Reference edits"). Proof: `uv run pytest tests/unit/lens/test_edit_merge.py -k reference -q`.
- [ ] 5.2 Merge the user properties the script names, and treat a removed property as `""` (requirements "User property edits", "Second-phase properties"). Proof: `uv run pytest tests/unit/lens/test_edit_merge.py -k property -q`; `uv run pytest tests/unit/lens/test_build_properties.py -q`.

## 6. Viewer

- [ ] 6.1 `view --check` accepts `build` and `sync` replies and marks `sync.conflict` on its footprint (requirement "Edit conflicts on the board"; the command lines of "Conflict resolution from the viewer"). Proof: `uv run pytest tests/unit/view/test_check_overlay.py -q`.
- [ ] 6.2 (waits for c0245) Add the Properties view of a conflict and the "Take code" and "Take CAD" actions through the Pending panel (requirement "Conflict resolution from the viewer"). Proof: `uv run pytest tests/unit/view/test_check_overlay.py -k workbench -q`.

## 7. Fixture, oracle, docs and guide

- [ ] 7.1 Author `tests/data/lens/edit_merge/` and `tests/_layout_edit.py::edit_properties`, and add the acceptance loop (requirement "Edit merge acceptance fixture"). Proof: `uv run pytest tests/unit/lens/test_edit_merge_acceptance.py -q`.
- [ ] 7.2 Add the oracle test on 9.0.9 and 10.0.6 (requirement "Merged files accepted by KiCad"). Proof: CI job `kicad` green on the pushed commit for `tests/kicad/lens/test_edit_merge_oracle.py`.
- [ ] 7.3 Register `H-K-EDIT-SCH-VALUE` in `docs/hypotheses.md` and set `lens.edits.EVIDENCE` (requirements "Edit merge evidence", "Schematic edit hypothesis"). Proof: `uv run pytest tests/unit/test_hypotheses_register.py tests/unit/lens/test_edit_merge.py -k evidence -q`.
- [ ] 7.4 Update `docs/lens.md` (the five sections, the table, the removal of the two-way sentence and of the `placements.toml` section's write rule) and `docs/cli-contract.md` (`build --take`, `sync`) (requirement "Three-way merge is documented"). Proof: `uv run pytest tests/unit/lens/test_edit_merge.py -k docs -q`; `make check-fast`.
- [ ] 7.5 Add the `explain.toml` entries and the guide lines: a `fenolite-recipe` in `recovery.md` for `sync.conflict` with `--take`, and the edit loop in `board-workflow.md`; then run `uv run python tools/gen_agent_guide.py` (requirement "Conflicts are explained and taught"). Proof: `uv run pytest tests/unit/agent/test_pages.py tests/unit/cli/test_explain_cmd.py -q`.
- [ ] 7.6 Add the edit loop to an example: `examples/blink_2layer/README.md` (build, edit in KiCad, build, sync, conflict, take), run by the example tests. Proof: `uv run pytest tests/unit/test_examples.py -q`.

## 8. Closing

- [ ] 8.1 Run `make check-fast` and the residue scan; publish the batch to the working branch for CI. Proof: `make check-fast`; CI `unit` and `kicad` jobs green on the exact commit.
- [ ] 8.2 Update the evidence labels: `docs/evidence/` rows of the merge at `INFERRED`, `H-K-EDIT-SCH-VALUE` as registered, and the oracle results. Proof: `uv run pytest tests/unit/test_provenance.py tests/unit/test_hypotheses_register.py -q`.
- [ ] 8.3 Add the CHANGELOG entry under `## [Unreleased]`: three-way merge, `edits.toml`, `fenolite-base.json`, `build --take`, `sync.conflict`, and the changed meaning of an unlocked `place()` after the first build. This waits for dev to open `0.7.0.dev0`, because the v0.6 guard requires `[Unreleased]` to be empty. Proof: `uv run pytest tests/unit/test_release_record_v06.py tests/unit/test_release_tool.py -q`; `make check-fast`.
- [ ] 8.4 Validate and archive once every task is closed and CI is green. Proof: `npx -y @fission-ai/openspec validate c0250-manual-edit-merge --strict`.
