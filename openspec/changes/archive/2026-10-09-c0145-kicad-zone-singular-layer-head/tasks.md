## 1. Measure

- [x] 1.1 On the released 0.2.1 (a scratch worktree of the tag) and on the base: which rewriting commands refuse a board whose zone or rule area holds `(layer "*.Cu")`, `(layer "F&B.Cu")`, `(layer "F.Cu")`, and the plural controls. Proof: the table of `design.md`, "Measurement 1".
  - 2026-10-08: measured on the tag `v0.2.1` (`fde27c9f`, its code through `PYTHONPATH`) and on `v04` at `19ab2ad1`. Both have the defect with the same messages; `(layer "F.Cu")` and the plural forms write. `place` on the base before the fix was not run with a valid move (the table says "not run").
- [x] 1.2 Count the layer child of every zone and rule area of the cached corpus boards, per head, per number of names and per file header. Proof: the table of `design.md`, "Measurement 2".
  - 2026-10-08: 25 boards, 2 291 children counted (2 261 `layer` with one name, 25 `layers` with several names, 5 `layers "F&B.Cu"`); none with a wildcard, a mask or several names under `layer`.
- [x] 1.3 Write `tests/kicad/board/_zonelayers.py`, register the eleven probes `pcb-zone-layers-*` for major 10 in `tests/kicad/_probes.py`, record them on the local `kicad-cli` 10.0.6. Proof: `FENOLITE_REQUIRE=kicad uv run pytest tests/kicad/test_probe_results.py -q`; `git diff --stat docs/evidence/kicad/probes/10.0.6.json` shows eleven added lines and nothing else.
  - 2026-10-08: the eleven outcomes were added to `10.0.6.json` by a script that runs these probes through `_probes.run` and writes the file sorted (11 insertions, nothing else; `FENOLITE_PROBES_WRITE=1` on `test_probe_results.py` rewrites every probe of the file, as c0141 noted). `tests/kicad/test_probe_results.py` passed inside the run of task 3.2. Nothing was run on 9.0.9.
- [x] 1.4 Write the four fact rows to `docs/formats/kicad/board.md`, the row `H-K-ZONE-LAYER-HEAD` to `docs/hypotheses.md` and the session row to `LEGAL-ANNEX.md`. Proof: `uv run pytest tests/unit/test_format_facts.py tests/unit/test_hypotheses_register.py tests/unit/test_provenance.py -q`.
  - 2026-10-08: the rows are at the end of the page's first fact table, after the rows of c0103; the proof ran with the manifest, residue and matrix-page tests: 159 passed.

## 2. The writer

- [x] 2.1 In `src/fenolite/backends/kicad/pcb.py`: `ZONE_LAYER_HEADS`, `_zone_layers_key`, the family lookup and comparison in `_Writer.reconcile`, the wildcard under `layer` in `_spelling_only`. Write `tests/unit/backends/kicad/test_pcb_zone_layer_heads.py` (the scenarios of "Singular and plural layer heads of a zone" that need no tool). Proof: `uv run pytest tests/unit/backends/kicad/test_pcb_zone_layer_heads.py -q`; `uv run pytest tests/unit/backends/kicad -q -n 3`; `uv run pyright src`.
  - 2026-10-08: 52 passed; the folder 2 798 passed, 1 skipped; pyright 0 errors. `_key` is unchanged.
- [x] 2.2 The reproduction through the command: `tests/unit/cli/test_route_zone_layer_head.py` (scenario "Route rewrites the board"), and the rule area a script declares: `tests/unit/lens/test_build_rule_area_layer_head.py` (scenario "A rule area declared in the script"). Proof: `uv run pytest tests/unit/cli/test_route_zone_layer_head.py tests/unit/cli/test_route_cmd.py tests/unit/lens/test_build_rule_area_layer_head.py tests/unit/lens/test_build_board_items.py -q -n 3`.
  - 2026-10-08: run with the unit files of c0103's rule areas and of the board writer (`test_pcb_items`, `test_pcb_write`, `test_boarditems`, `test_pcb_write_projections`, `test_zone_settings_write`, `checks/test_copper`, `lens/test_preserve_board`): 296 passed.
- [x] 2.3 RT1 stays green. Proof: `uv run pytest tests/corpus/test_board_rt1.py -q -n 2` (non-heavy); the round-trip files under `tests/unit/backends/kicad` are part of 2.1.
  - 2026-10-08: 23 passed, 2 skipped (the heavy items).

## 3. The oracle

- [x] 3.1 `tests/kicad/board/test_zone_layer_heads.py`: the scenarios "A changed layer set is written by the number of layers" and "What KiCad 10 loads and saves". Proof: `FENOLITE_REQUIRE=kicad uv run pytest tests/kicad/board/test_zone_layer_heads.py -q -n 2`.
  - 2026-10-08, `kicad-cli` 10.0.6: 12 passed.
- [x] 3.2 The oracle folders that read boards Fenolite writes. Proof: `FENOLITE_REQUIRE=kicad uv run pytest tests/kicad/board tests/kicad/build tests/kicad/routing tests/kicad/test_probe_results.py -q -n 2`.
  - 2026-10-08, `kicad-cli` 10.0.6, on `v04` at `775a85d1`: 325 passed, 5 skipped (cases of major 9), 844 s.

## 4. The release line 0.2

- [x] 4.1 Apply the product-code and unit-test part to a scratch worktree of the tag `v0.2.1` (`git diff <base>..<commit> -- src tests/unit/backends/kicad | git apply --3way`) and run the unit file with the tag's code. Nothing is committed on the tag. Proof: the apply is clean; `uv run pytest tests/unit/backends/kicad/test_pcb_zone_layer_heads.py -q` passes there.
  - 2026-10-08: applied cleanly; 52 passed with the tag's code, and the tag's `tests/unit/backends/kicad` 2 292 passed, 1 skipped. The worktree was removed (design, "Applying to 0.2.1").

## 5. Documentation and checks

- [x] 5.1 `CHANGELOG.md`: one line at the end of `[Unreleased]`, in bold as a fix. `explain.toml`: no message changed, nothing to add. Proof: `uv run pytest tests/unit/test_hypotheses_register.py -q`.
  - 2026-10-08: inside the 159 of task 1.4.
- [x] 5.2 The checks of the night: `uv run ruff check .`; `uv run ruff format --check .`; `uv run pyright src`; `openspec validate --all --strict`; `uv run python tools/gen_schemas.py --check`; `uv run python tools/gen_evidence_matrix.py --check`; `uv run python tools/gen_agent_guide.py --check`; after `git add -A`, `uv run pytest tests/corpus/test_manifest.py tests/residue tests/unit/test_hypotheses_register.py -q -n 3`; `uv run pytest tests/unit/agent -q -n 3`; `make check-fast PYTEST_WORKERS=3`; `python3 tools/dco_check.py v04..HEAD`.
  - 2026-10-08, on `v04` at `775a85d1`: every command exit 0; `openspec validate` 104 passed; `tests/unit/agent` 82 passed; `make check-fast` and the sign-off check as the hand-over report states.
