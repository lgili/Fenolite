## 1. Registers and fact rows

- [ ] 1.1 Register the hypotheses and the sources. This is the first commit of the implementation, so the cited-id guard sees the ids registered.
  - Add the rows `H-K-SCH-READ`, `H-K-SCH-RT1`, `H-K-SCH-COMPONENTS` and `H-K-SCH-TOKENS` to `docs/hypotheses.md`, with backend `kicad`, level `INFERRED`, the test and criterion of `design.md`, and the result `pending; observed at proposal time (2026-10-04)` with the observation of design "Context". Add the paragraph "Change c0060 (KiCad schematic reader) adds …".
  - Add S-0320 and S-0321 to `docs/evidence/sources.md`, each with its licence as stated on the page or in the repository and only what it states. Widen the "used for" cells of S-0020, S-0022, S-0024, S-0027, S-0028, S-0031, S-0037 and S-0058 as design "Sources registered by this change" says.
  - Re-check every name consumed from archived changes (design "Files and public API") against the working tree, and list each divergence in the pull request description.

  Proof: `uv run pytest tests/unit/test_provenance.py tests/unit/test_hypotheses_register.py`; `grep -c '^| H-K-SCH-' docs/hypotheses.md` prints `4`.
- [ ] 1.2 Write `docs/formats/kicad/schematic.md` with the fact rows the reader is written from: the root children per format version, the children of `symbol`, the labels, the sheet properties and instance paths, the version constants and the two load checks. Each row has a source, a label and a hypothesis. Add rows to `src/fenolite/backends/kicad/PROVENANCE.md` and a `LEGAL-ANNEX.md` session row. Proof: `uv run pytest tests/unit/test_format_facts.py tests/unit/test_provenance.py tests/unit/test_legal_docs.py`.

## 2. Probes first: load checks and inventory (`kicad-cli` 10.0.6 locally, 9.0.9 in the pinned image)

- [ ] 2.1 Add the schematic and symbol-library load checks to `tools/kicad_token_fuzz.py` with one authored skeleton per kind and major (design Decision 12), and extend `tests/unit/backends/kicad/test_fuzz_harness.py` with a fake `kicad-cli` (scenarios of "Load checks for schematics and symbol libraries"). Proof: `uv run pytest tests/unit/backends/kicad/test_fuzz_harness.py`; `uv run pytest tests/kicad/test_token_fuzz.py -k skeleton -rA` on the local KiCad 10.0.6 and inside the pinned 9.0.9 image.
- [ ] 2.2 Add the rows and notes of kind `kicad_sch` to `src/fenolite/backends/kicad/data/tokens.toml` from the dated versions of S-0031, each name confirmed in S-0321 at both tags, with an example and an expected outcome per row (design Decision 13). Proof: `uv run pytest tests/unit/backends/kicad/test_inventory.py tests/unit/backends/kicad/test_token_examples.py`.
- [ ] 2.3 Add the rows and notes of kind `kicad_sym`, and make a symbol row match under `kicad_sch/lib_symbols/symbol/…` too. Proof: `uv run pytest tests/unit/backends/kicad/test_inventory.py tests/unit/backends/kicad/test_check_emittable.py tests/unit/backends/kicad/test_sym.py`.
- [ ] 2.4 Run the fuzz on both images, commit the results under `docs/evidence/kicad/token-fuzz/`, correct every row the fuzz contradicts, and regenerate `docs/formats/kicad/tokens.md`. Note under this task each row that was corrected. Proof: `uv run pytest tests/kicad/test_token_fuzz.py tests/unit/backends/kicad/test_token_results.py -rA` on the local KiCad 10.0.6 and inside the pinned 9.0.9 image; `uv run python tools/gen_token_docs.py --check` exits 0.

## 3. Model

- [ ] 3.1 Write `src/fenolite/model/schematic.py`, add the five prefixes to `src/fenolite/core/ids.py`, register the schema in `tools/gen_schemas.py` and generate `schemas/fenolite.model.v0/schematic.json`. Write `tests/unit/model/test_schematic.py` (scenarios of "Schematic sheet definitions", "Identifiers of schematic entities" and "Schematic sheet schema") and the section "Schematic sheets" of `docs/design-model.md`. Proof: `uv run pytest tests/unit/model tests/unit/core tests/unit/test_schema_drift.py tests/unit/test_import_graph.py`; `uv run python tools/gen_schemas.py --check` exits 0; `uv run pyright src`.

## 4. Fixtures

- [ ] 4.1 Author `flat.kicad_sch`, `flat_v9.kicad_sch`, `units.kicad_sch` and `units_v9.kicad_sch` under `tests/data/kicad/schematic/`, and `Mini_DualGate` for `tests/data/libs/Mini_v9.kicad_sym` (design Decision 17). Declare each file in `tests/data/MANIFEST.toml`. Proof: `uv run pytest tests/unit/test_repo_layout.py tests/residue tests/unit/backends/kicad/test_sym.py tests/unit/backends/kicad/test_mini_v9_pins.py`; `kicad-cli sch export netlist` loads each file on its major (10.0.6 locally, 9.0.9 in the pinned image), with the exit codes written under this task.
- [ ] 4.2 Author `hier/top.kicad_sch` with `hier/child.kicad_sch`, `multi/top.kicad_sch` with `multi/cell.kicad_sch`, and `bus.kicad_sch`; declare them. Proof: the same commands.

## 5. Reader

- [ ] 5.1 Write `src/fenolite/backends/kicad/sch.py` with `read_schematic` for the root: version policy, `uuid`, paper, title block, pages, opaque root children, `ISSUE_CODES` and `EVIDENCE`. Write `tests/unit/backends/kicad/test_sch_read.py` (scenarios of "Schematic file reading", "Schematic version policy", "Modelled schematic content" and "Schematic read issue codes"). Proof: `uv run pytest tests/unit/backends/kicad/test_sch_read.py tests/unit/test_import_graph.py`; `uv run pyright src`.
- [ ] 5.2 Add `sym.symbol_from` and read embedded symbols and symbol instances with their properties and uses (scenarios of "Symbol instances" and "Embedded symbol definitions"). Proof: `uv run pytest tests/unit/backends/kicad/test_sch_read.py tests/unit/backends/kicad/test_sym.py tests/unit/backends/kicad/test_sym_extends.py`.
- [ ] 5.3 Read labels, no-connect flags and sheet references; apply the exact-number rules and the id rules (scenarios of "Labels, no-connect flags and sheet references", "Exact numbers on schematics" and "Identifiers of schematic items"). Proof: `uv run pytest tests/unit/backends/kicad/test_sch_read.py`.
- [ ] 5.4 Record the slot lists, the reproducibility check and the minimum versions from the inventory (scenarios of "Unmodelled schematic content is kept as slots"). Proof: `uv run pytest tests/unit/backends/kicad/test_sch_read.py tests/unit/backends/kicad/test_slots.py tests/unit/backends/kicad/test_slots_ext.py`.

## 6. Rebuild, verdict and queries

- [ ] 6.1 Write `rebuild_schematic`, `opaque_count` and `opaque_digests`, and `tests/unit/backends/kicad/test_sch_rebuild.py` (scenarios of "Same-version rebuild of schematics"), with property tests that move, rotate and mirror a symbol. Proof: `uv run pytest tests/unit/backends/kicad/test_sch_rebuild.py`.
- [ ] 6.2 Write `roundtrip_schematic` (scenarios of "Schematic round-trip verdict") and run it on every fixture. Proof: `uv run pytest tests/unit/backends/kicad/test_sch_rebuild.py -k roundtrip`.
- [ ] 6.3 Write `sheet_files` and `components`, and `tests/unit/backends/kicad/test_sch_tree.py` (scenarios of "Sheet tree of a project" and "Components of a project"). Proof: `uv run pytest tests/unit/backends/kicad/test_sch_tree.py`; `uv run pyright src`.

## 7. Corpus

- [ ] 7.1 Add the demo rows of both tags and the two third-party rows to `tests/corpus/manifest.toml`, with sizes and SHA-256 from the files API (S-0024) and the licence of each folder; widen the id pattern in `tests/corpus/test_manifest.py`. Fetch the rows and write the fetch time and the total bytes under this task. Proof: `uv run pytest tests/corpus/test_manifest.py`; `uv run python tools/corpus_fetch.py --uses sch` exits 0.
- [ ] 7.2 Write `tests/corpus/test_schematic_census.py` and set the content tags of every row from its result (requirement "Schematic corpus rows"). Proof: `FENOLITE_CENSUS_OUT=<file> uv run pytest tests/corpus/test_schematic_census.py -rA` passes, and the census file holds the counts per tag, version and origin.
- [ ] 7.3 Write `tests/corpus/test_schematic_rt.py` and `docs/evidence/kicad-schematic.md` (ids and counts only). A failure is a reader defect: fix the reader, or record the row and the reason under this task and in the hypothesis row. Proof: `FENOLITE_CENSUS_OUT=<file> uv run pytest tests/corpus/test_schematic_rt.py -rA`; `uv run pytest tests/residue`; `git status --porcelain` lists no file under the cache.

## 8. Oracle (`kicad-cli` 10.0.6 locally, 9.0.9 in the pinned image)

- [ ] 8.1 Add `KicadCli.export_netlist` and `KicadCli.upgrade_schematic`, teach `tests/_fakecli.py` the two commands, write `tests/_netlist.py`, and extend `tests/unit/backends/kicad/test_cli_runner.py`. Proof: `uv run pytest tests/unit/backends/kicad/test_cli_runner.py`; `uv run pyright src`.
- [ ] 8.2 Write `tests/kicad/schematic/_schcases.py` and `test_components_oracle.py` for the fixtures; add `tests/kicad/schematic` to the `sys.path` list of `tests/kicad/conftest.py` and to the fake run of `tests/unit/test_kicad_probes.py`; add the four probes to `PROBES` and regenerate both probe files with `FENOLITE_PROBES_WRITE=1`. Note under this task the outcome of `sch-components-on-board` per major and the fallback applied. Proof: `uv run pytest tests/kicad/schematic/test_components_oracle.py -k fixtures tests/kicad/test_probe_results.py -rA` on the local KiCad 10.0.6 and inside the pinned 9.0.9 image.
- [ ] 8.3 Add the corpus comparison to `test_components_oracle.py` and write `test_schematic_upgraded.py`; copy the counts into `docs/evidence/kicad-schematic.md`. Proof: `FENOLITE_REQUIRE=kicad,corpus uv run pytest tests/kicad/schematic -rA` on the local KiCad 10.0.6; the corpus comparison inside the pinned 9.0.9 image with the rows of tag 9.0.9.1.

## 9. Closing

- [ ] 9.1 Run the residue and full test suites. Proof: `uv run pytest tests/residue` and `uv run pytest -q` exit 0; `uv run python tools/residue/scan.py` exits 0; `uv run python tools/gen_schemas.py --check` exits 0; `make check` passes; `openspec validate c0060-kicad-schematic-reader --strict --no-interactive` passes; `gh pr checks` shows `kicad-9` and `kicad-10` passing.
- [ ] 9.2 Update the evidence labels: `H-K-SCH-COMPONENTS` becomes `KICAD-VERIFIED (9.0.x, 10.0.x)` or is refuted with a successor and the fallback applied; `H-K-SCH-RT1` becomes `CORPUS-VERIFIED` with both origins named, or records the cut; `H-K-SCH-READ` and `H-K-SCH-TOKENS` record their results. Raise `sch.EVIDENCE` only if the components hypothesis holds on both majors. The rows of `docs/formats/kicad/schematic.md` follow. Proof: `uv run pytest tests/unit/test_provenance.py tests/unit/test_hypotheses_register.py tests/unit/test_format_facts.py`.
- [ ] 9.3 Add to `CHANGELOG.md` under Unreleased: "KiCad schematics are read into a typed sheet (symbols, labels, no-connect flags, sheet references, embedded symbols) with every other child kept in place; round trips proved over the demo schematics; the token inventory covers schematic and symbol-library tokens". Update `docs/roadmap.md`. Proof: `git diff --stat CHANGELOG.md docs/roadmap.md` lists both files.
