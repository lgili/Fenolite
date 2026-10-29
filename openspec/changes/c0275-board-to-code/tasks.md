## 0. Entry check

- [ ] 0.1 Read `openspec list` and the changes and living specs this change builds on, and record under this task, with the date and the base commit:
  - whether c0249 is archived (part keys `name=`, explicit refs in the lock, `--frozen`). This change depends on it; if it is not archived, stop here;
  - whether c0276 and c0277 are archived: c0276 adds `schematic.toml` to the output (then drop `import.schematic-generated`), c0277 gives `design.verbatim` (then decision 10 writes verbatim items) and instance overrides (decision 8);
  - the names of the copper uuid derivation for intents (`dsl/intents.py`, `lens/copper`), so table rows reuse it;
  - whether `library/derive.py` works only on KiCad text (then task 2.3 adds the model form);
  - the maintainer's answers to the open questions of `design.md`.

  Proof: `openspec validate c0275-board-to-code --strict`; `make check-fast`.

## 1. DSL additions

- [ ] 1.1 Add `Design.track_table`, `arc_table` and `via_table` to `dsl/design.py` and `dsl/intents.py`, with the row checks (scenarios "Table of two segments", "Refused rows"). Proof: `uv run pytest tests/unit/dsl/test_copper_tables.py -q`.
- [ ] 1.2 Resolve tables in the build with the copper uuids of their rows, the copper guard and the merge (scenarios "Rebuild keeps table copper", "Designs without tables are unchanged"); the Altium branch follows `track` and `via`. Proof: `uv run pytest tests/unit/lens/test_copper_tables_build.py tests/unit/test_examples.py -q`.
- [ ] 1.3 Add `key=` to `zone()` and `rule_area()` with ids from the key (scenarios "Unnamed zone with a key", "Unnamed area with a key"); no example changes bytes. Proof: `uv run pytest tests/unit/dsl/test_zones.py tests/unit/dsl/test_rule_areas.py tests/unit/test_examples.py -q`.

## 2. Emitter

- [ ] 2.1 Author the inputs under `tests/data/import_python/` (a two-sheet project with a repeated sheet, a board without schematic, a board with a `group`, a board with an edited instance, a board with `(version 20221018)`), each marked `Authored for Fenolite`; register `H-G-IMPORT-CODE`, `H-K-IMPORT-UPGRADE`, `H-K-IMPORT-ADOPT` and `H-A-IMPORT-CODE` in `docs/hypotheses.md`. Proof: `uv run pytest tests/unit/test_hypotheses_register.py -q`; `make residue`.
- [ ] 2.2 Add `src/fenolite/importer/emit/` (records, ordering, printer) for board, outline, stack-up, nets, classes, pairs, rules, parts, placements, zones, rule areas and drawings (scenarios "Positions survive exactly", "Net classes and pairs kept"). Proof: `uv run pytest tests/unit/importer/test_emit_design.py -q`.
- [ ] 2.3 Add the model form of the library derive and the vendored `lib/` with project tables (scenarios "Build uses only the vendored library", "Edited instance"); `fenolite library` keeps its replies. Proof: `uv run pytest tests/unit/importer/test_vendor.py tests/unit/cli/test_library.py -q`.
- [ ] 2.4 Add modules per sheet and the net placement rule (scenarios "Repeated sheet", "Sheet name sanitized"). Proof: `uv run pytest tests/unit/importer/test_sheets.py -q`.
- [ ] 2.5 Add `importer/tables.py` and `copper.py` emission (scenario "Every segment once"). Proof: `uv run pytest tests/unit/importer/test_tables.py -q`.
- [ ] 2.6 Add `importer/keys.py` and the lock writing (scenario "Frozen build of the import"). Proof: `uv run pytest tests/unit/importer/test_keys.py -q`.
- [ ] 2.7 Add `importer/provenance.py`: headers, `PROVENANCE.json`, copied notices (scenarios "Header and record", "Missing licence"). Proof: `uv run pytest tests/unit/importer/test_provenance.py -q`.
- [ ] 2.8 Add `importer/coverage.py` and the lossy rule (scenarios "Group refused without consent", "Group reported with consent"). Proof: `uv run pytest tests/unit/importer/test_coverage.py -q`.

## 3. Checks, upgrade, adoption, Altium

- [ ] 3.1 Add the self-check with the profile `import` (scenarios "Equal at five levels", "Emitter bug caught"). Proof: `uv run pytest tests/unit/importer/test_selfcheck.py -q`.
- [ ] 3.2 Add `importer/upgrade.py` on private copies (scenarios "KiCad 7 board", "No kicad-cli"). Proof: `uv run pytest tests/unit/importer/test_upgrade.py -q`; `uv run pytest tests/kicad/importer/test_upgrade_kicad.py -rA` (in CI, 10.0.x).
- [ ] 3.3 Add `importer/adopt.py` (scenarios "Build over an adopted board changes nothing", "Only identities change", "KiCad loads the adopted board"). Proof: `uv run pytest tests/unit/importer/test_adopt.py -q`; `uv run pytest tests/kicad/importer/test_adopt_kicad.py -rA` (in CI, both majors).
- [ ] 3.4 Altium inputs (scenario "Fenolite-written Altium document"). Proof: `uv run pytest tests/unit/importer/test_altium_input.py -q`.
- [ ] 3.5 Determinism (scenario "Same bytes twice"). Proof: `uv run pytest tests/unit/importer/test_determinism.py -q`.

## 4. Command

- [ ] 4.1 Add `cli/cmd_import.py`, the result schema `schemas/fenolite.import.v0.json`, the codes in `explain.toml` (scenarios "Plan of an authored board", "Confirmed import", "Eagle board refused", "Output over the source refused", "Board without a schematic", "Schema and explain", "Consistency suite covers the import", "Plan id binds the inputs"). Proof: `uv run pytest tests/unit/cli/test_import.py tests/consistency -q`.
- [ ] 4.2 Add the residue detector for converted code (scenarios "Converted corpus board planted", "Authored import example passes"). Proof: `uv run pytest tests/residue/test_converted_code.py -q`.
- [ ] 4.3 Corpus measurement (not committed): import every readable KiCad demo row with an allow-listed licence into `tmp_path`, build and compare at levels 1 to 5, and record counts of unexpressed kinds in `docs/evidence/import-corpus.md`. Proof: `uv run pytest tests/corpus/test_import_corpus.py -rA` (in CI, `needs_corpus`).
- [ ] 4.4 Author `examples/import_python/` (the imported code of an authored board, marked `Authored for Fenolite`) and its build test. Proof: `uv run pytest tests/unit/test_examples.py -k import_python -q`.

## 5. Closing

- [ ] 5.1 Docs: `docs/import.md` (inputs, output tree, tables, keys, provenance, lossy rule, self-check, adoption, upgrade, that converted third-party boards belong in `fenolite-library` only), `import` in `docs/cli-contract.md`, the tables and `key=` in `docs/dsl.md`, links from `docs/index.md`. Proof: `uv run pytest tests/unit -k docs -q`.
- [ ] 5.2 Agent guide: tested lines for `fenolite import` and `track_table` on the guide pages, then `uv run python tools/gen_agent_guide.py`. Proof: `uv run pytest tests/unit/agent/test_pages.py -q`.
- [ ] 5.3 Residue and evidence: no third-party file or converted code in the repository, the evidence matrix regenerated. Proof: `make residue`; `uv run python tools/gen_evidence_matrix.py --check`.
- [ ] 5.4 Add the entry to `CHANGELOG.md` under `## [Unreleased]`. This waits until `dev` is at `0.7.0.dev0`: the v0.6 guard requires `[Unreleased]` to stay empty while the version is `0.6.0`. Proof: `uv run pytest tests/unit -k changelog -q`.
- [ ] 5.5 Run `make check-fast`, publish the batch to its working branch, and confirm the required CI jobs (unit and KiCad) on the exact commit. Proof: `make check-fast`, and the required jobs green on the pushed head.
