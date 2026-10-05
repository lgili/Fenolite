## 0. Entry check

- [ ] 0.1 Read the living `layout-lens`, `design-dsl`, `cli-contract` and `kicad-oracle` specs and `openspec list`. Write under this task, with the date: whether c0060 and c0061 are archived (else tasks 5.3 and the stand-in step of 7.1 wait, and say so); whether another change modified one of the seven `layout-lens` requirements this change modifies (then re-base the MODIFIED text on the living one); and the names this change consumes from c0061 (`lens.schplacements`, `schlayout.PROVED_FRAMES`, `update_from_schematic`, `Component.path` of the schematic lowering), checked against the tree. Proof: `openspec validate c0069-layout-lens-complete --strict --no-interactive` passes after any re-base.

## 1. Registers

- [ ] 1.1 Add the row `H-K-LENS-RENAME` to `docs/hypotheses.md` (backend `kicad`, level `INFERRED`, the test and criterion of "Renamed footprints pass the oracle", result `pending`), and stubs for the new sections of `docs/lens.md` and the command section of `docs/cli-contract.md`. Proof: `uv run pytest tests/unit/test_hypotheses_register.py tests/unit/test_provenance.py tests/consistency`; `grep -c '^| H-K-LENS-RENAME ' docs/hypotheses.md` prints `1`.

## 2. Aliases

- [ ] 2.1 Extend `Design.moved` to module paths, add `module_moves` and the expansion in `moves`, add `Design.moved_net` and `net_moves`, re-export both from `fenolite.dsl`, and write `tests/unit/dsl/test_moved.py` (scenarios of "Path aliases in the DSL" and "Net aliases in the DSL"). Proof: `uv run pytest tests/unit/dsl/test_moved.py tests/unit/dsl`; `uv run pyright src`.
- [ ] 2.2 Write `src/fenolite/lens/moved.py` (`Aliases`, `resolve_aliases`, `identity_map`) and `tests/unit/lens/test_moved.py` (scenarios of "Alias resolution"). Proof: `uv run pytest tests/unit/lens/test_moved.py tests/unit/test_import_graph.py`.

## 3. Merge

- [ ] 3.1 Pass `module_moves`, `net_moves` and the resolved aliases through `prepare`, `Prepared` and `cmd_build`; add `result.preserved.module_aliases` and `net_aliases`. Proof: `uv run pytest tests/unit/lens tests/unit/cli/test_build_cmd.py`.
- [ ] 3.2 Keep alias matches under the new identity in `merge_layout`, rewrite group members, and write `tests/unit/lens/test_alias_keep.py` (scenarios of "Kept and re-placed footprints" and "Board content outside the design is kept"). Proof: `uv run pytest tests/unit/lens/test_alias_keep.py tests/unit/lens/test_preserve_determinism.py tests/unit/lens`.
- [ ] 3.3 Keep copper and board-only pads through net aliases, map net names before digesting the existing board, add the new codes to `PRESERVE_ISSUE_CODES`, and write `tests/unit/lens/test_net_alias.py` (scenarios of "Copper items follow their nets" and "Zone fills and the staleness digest"). Proof: `uv run pytest tests/unit/lens/test_net_alias.py tests/unit/lens/test_preserve_issues.py`.

## 4. Placements file

- [ ] 4.1 Write `src/fenolite/lens/placements.py` and `tests/unit/lens/test_placements_file.py` (scenarios of "Placements file", with the round-trip property test). Proof: `uv run pytest tests/unit/lens/test_placements_file.py tests/unit/test_import_graph.py`; the no-float scan of the lens tests passes.
- [ ] 4.2 Add `source` to `effective_placements` and `prepare` (scenarios of "Placement precedence"), and read the file in `cmd_build` for both targets (scenarios of "Placements file in a build"), with its hash in `.fenolite/build.json`. Proof: `uv run pytest tests/unit/lens tests/unit/cli/test_build_cmd.py tests/unit/lens/test_preserve_determinism.py`.
- [ ] 4.3 Write `src/fenolite/lens/extract.py` and `tests/unit/lens/test_extract.py` (scenarios of "Placement extraction"). Proof: `uv run pytest tests/unit/lens/test_extract.py`.

## 5. Sync

- [ ] 5.1 Write `src/fenolite/lens/sync.py` (`plan_sync`, `SYNC_ISSUE_CODES`, `EVIDENCE`) and `tests/unit/lens/test_sync.py` (scenarios of "Sync of the source tree"), and `src/fenolite/cli/cmd_sync.py` with the committed example folder `tests/data/lens/sync_minimal/` and the test that keeps it equal to a fresh build. Proof: `uv run pytest tests/unit/lens/test_sync.py tests/unit/cli/test_sync_cmd.py tests/consistency tests/unit/cli/test_hermetic_examples.py`.
- [ ] 5.2 Add `--check` (scenarios "Stale file found by check" and "Current file passes check"). Proof: `uv run pytest tests/unit/cli/test_sync_cmd.py -k check`.
- [ ] 5.3 When c0060 and c0061 are archived: add `extract_symbol_placements` and `write_placements` to `lens/schplacements.py` and the schematic half of `sync` (scenarios of "Symbol placement extraction"). Proof: `uv run pytest tests/unit/lens/test_schplacements.py tests/unit/cli/test_sync_cmd.py`.

## 6. Documentation

- [ ] 6.1 Complete `docs/lens.md`, `docs/dsl.md` and `docs/cli-contract.md` as "Complete lens is documented" lists, with the precedence and issue tables of the living requirements. Proof: `uv run pytest tests/consistency tests/unit/test_repo_layout.py tests/residue`.

## 7. Acceptance

- [ ] 7.1 Author `tests/data/lens/acceptance/design.py` and write `tests/unit/lens/test_lens_acceptance.py` (scenarios of "Lens acceptance fixture"), with the stand-in step when c0061 is archived. Proof: `uv run pytest tests/unit/lens/test_lens_acceptance.py -rA`.
- [ ] 7.2 Write `tests/kicad/lens/test_rename_oracle.py` with the probes `lens-rename-t9` and `lens-rename-t10`, and record their outcomes. Proof: `uv run pytest tests/kicad/lens/test_rename_oracle.py -rA` on the local KiCad 10.0.6 and inside the pinned 9.0.9 image; `FENOLITE_PROBES_WRITE=1` updates both probe files; `uv run pytest tests/kicad/test_probe_results.py`.
- [ ] 7.3 Write `tests/kicad/lens/test_lens_acceptance_oracle.py`: the acceptance fixture's rebuilt and discarded-layout boards load on both majors and keep the DRC report of the edited board. Proof: `uv run pytest tests/kicad/lens -rA` on both majors.

## 8. Closing

- [ ] 8.1 Run the residue and full test suites. Proof: `uv run pytest tests/residue` and `uv run python tools/residue/scan.py` exit 0; `make check` passes; `openspec validate c0069-layout-lens-complete --strict --no-interactive` passes; `gh pr checks` shows `unit`, `kicad-9` and `kicad-10` passing.
- [ ] 8.2 Update the evidence: `H-K-LENS-RENAME` becomes `KICAD-VERIFIED (9.0.x, 10.0.x)` with the run, or records the outcome that failed and the stop rule taken. Proof: `uv run pytest tests/unit/test_provenance.py tests/unit/test_hypotheses_register.py`.
- [ ] 8.3 Add to `CHANGELOG.md` under Unreleased: "`moved()` takes module paths and `moved_net()` renames nets without losing their routing; a footprint renamed through an alias keeps its KiCad edits; `fenolite sync --to-source` writes `placements.toml`, which `build` reads beside the script". Update `docs/roadmap.md`. Proof: `git diff --stat CHANGELOG.md docs/roadmap.md` lists both files.
