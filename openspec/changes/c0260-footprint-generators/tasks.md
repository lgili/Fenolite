## 0. Entry check

- [x] 0.1 Read `openspec list` and the living specs this change touches (`fenolite-component-catalog`, `dsl-footprint-authoring`, `component-body-volumes`, `design-model`, `package-layering`), and record under this task, with the date and the base commit:
  - whether c0246, c0248 and c0259 are archived. Take `LengthRange` from c0259 if it defines one, else add it to `fenolite.core.quantities` (task 1.1); align the family keys of `design.md` decision 2 with c0259's final envelope and catalog records;
  - that c0259's catalog records carry `drawing = 0` and a `[land]` per family-shaped entry, and that its golden SHA-256 list exists (else capture it in task 4.1 before any helper is removed);
  - which open change of the batch registers further `fenolite library` verbs (c0262, c0264, c0265, c0266), so that decision 17's dispatch table is the one they extend;
  - the maintainer's answers to the open questions of `design.md` (densities, calibration from IPC-citing documents, lead bodies).

  Proof: `openspec validate c0260-footprint-generators --strict`; `make check-fast`.

  Entry record (2026-10-30; proof: `openspec validate --strict` valid; `make check-fast` 15275 passed, 2 failed, both pre-existing on the base and unrelated: `test_altium_build.py::test_evidence` and `test_altium_rows.py::test_rows_are_well_formed`, from the proposed row `H-A-SCH-BLOCK-ENTRIES` of c0269; base `331362eb` of `circuits-as-code`, branch `cac/c0260-footprint-generators`):
  - `openspec list`: c0246 (0/16), c0248 (0/20) and c0259 (0/21) are open, none archived. c0248 is in progress on
    `cac/c0248-device-catalog` and adds `src/fenolite/core/quantities.py` (electrical quantities); c0259 is in
    progress on another branch, not on this base. Neither defines a length range here, so task 1.1 adds
    `LengthRange` to a new `fenolite.core.quantities` holding only it: merging c0248 gives an add/add conflict
    on that file, resolved by keeping both contents. Range semantics follow c0246 when it lands.
  - c0259's envelope is not on this base: there are no catalog package records, no `drawing = 0` records and no
    golden SHA-256 list (`tests/data/catalog/` does not exist). Task 1.2 reads a minimal record (`schema`,
    `family`, `name` or `id`, the family keys, `[generate]`, `[land]`, and `evidence`, `summary`, `sources`
    kept as given); c0259's design names the family key `generator`, so the reader takes `family` or
    `generator` (equal when both are given). Envelope fields beyond id/family/dimensions (version, licence,
    reviews, stable uid, `FEN-3004` wording of c0259's parser) wait for c0259. Task 4.1 captures the golden
    list before any helper is removed.
  - Further `fenolite library` verbs: c0262 (`check`), c0264 (`import`), c0265 (`propose`, `review`), c0266
    (`seed`), c0279 (`audit`, `replay`, `release`, `gallery`); all open, none implemented, so decision 17's
    dispatch table is first defined here (task 6.2).
  - Maintainer's answers (2026-10-30): open question 3 is answered yes: generated footprints are also written
    as an Altium `.PcbLib` through the existing Altium writer (requirement "Generated footprints in an Altium
    PCB library", tasks 3.7 and 6.2b). Open questions 1, 2, 4 and 5 keep their recommended defaults (nominal
    density only; manufacturer patterns that cite IPC-7351 may calibrate, cited one by one, never the
    standard's tables; one body per lead; `Local` as the default nickname).
  - Found while reading the 0.6 helpers: `_row_pads` and `_quad_pads` put pin 1 at the most positive y, which
    is the bottom in the Y-down library frame (`docs/formats/kicad/frame.md`, `KICAD-VERIFIED`), so their
    numbering runs clockwise in the top view, the mirror image of the manufacturers' top views. The
    generators number correctly under `drawing >= 1` and keep the 0.6 placement under `drawing/0` (catalog
    bytes); the spec delta "Pad numbering and orientation" says so. Correcting the catalog itself is a
    separate change (new versions or ids under c0259's rules).

## 1. Ranges, records and codes

- [x] 1.1 Add `LengthRange` and its parser to `src/fenolite/core/quantities.py` (scenarios "Range spellings", "Sub-nanometre value"). Proof: `uv run pytest tests/unit/core/test_length_range.py -q`.
  Done 2026-10-30: `tests/unit/core/test_length_range.py` 15 passed. `LengthRange` lives in a new `fenolite.core.quantities` (c0248 adds the same module on its branch: keep both at the merge); range semantics follow c0246 when it lands.
- [x] 1.2 Add `src/fenolite/catalog/footprints/` with `generate`, `Generated`, `LandReport`, the family key schemas and `codes.py`; register the `package.*` codes in `explain.toml` (scenarios "Unknown family", "Missing pitch", "Calculator without a table version", "Reserved density", "Span inside the body"). Proof: `uv run pytest tests/unit/catalog/footprints/test_generate.py tests/unit/catalog/footprints/test_codes.py -q`.
  Done 2026-10-30: `test_generate.py` and `test_codes.py` 37 passed; the eight `package.*` codes are registered in `explain.toml` (`test_explain_cmd.py` 8 passed). The record reader is minimal (`record.py`): `family` or c0259's `generator`, `name` or `id`, the family keys of decision 2 (with `body.offset` for `to`, `header` and `connector`, `span` for an SMD `to`, `[[mechanical]]` with `beyond` and `y`), `[generate]` and `[land]`; envelope fields beyond id/family/dimensions wait for c0259.
- [x] 1.3 Author the test records under `tests/data/packages/` (one per family, each opening with the authored-for-Fenolite line, numbers from registered public outlines). Register their sources in `docs/evidence/sources.md` and `docs/catalog/sources.md`. Proof: `make residue`; `uv run pytest tests/unit -k sources -q`.
  Done 2026-10-30: `make residue` 0 hits (4727 files); `pytest tests/unit -k sources` 67 passed (with `test_records.py`: every record opens with the authored line, cites sources registered in both registers, and is declared in `tests/data/MANIFEST.toml`; `tests/corpus/test_manifest.py` passes). Ten records, one or more per family, from S-0855–S-0859 (new) and S-0315, S-0324, S-0377, S-0408, S-0442 (extended); the fetch tool returned each PDF, read as text with pdftotext.

## 2. Land calculator and constants

- [x] 2.1 Implement the worst-case calculator, the pad-gap clip and `package.land-impossible` in `lands.py` (scenarios "Calculated SOIC land", "Missing bound", "Fine pitch is clipped"). Proof: `uv run pytest tests/unit/catalog/footprints/test_lands.py -q`.
  Done 2026-10-30: `test_lands.py` 11 passed (calculated SOIC land Z 6.80, G 3.06, X 0.61 mm with the test table; missing bound; fine pitch clipped to `pitch - pad_gap`; `package.land-impossible`; `package.no-goals`; back-solving inverts the calculator; through-hole helpers).
- [x] 2.2 Write `tools/calibrate_lands.py` and its `--check` mode; author enough calibration records with cited manufacturer lands for each class; generate `LANDS[1]` (scenarios "Calibration is reproducible", "Uncalibrated class"). Proof: `uv run python tools/calibrate_lands.py --check`; `uv run pytest tests/unit/tools/test_calibrate_lands.py -q`.
  Done 2026-10-30: `tools/calibrate_lands.py --check` exits 0 and lists the records per class; `tests/unit/tools/test_calibrate_lands.py` 5 passed. 27 calibration records under `tests/data/packages/calibration` (chip 7, molded 4, gullwing 8, gullwing-fine 4, nolead 4) from cited manufacturer lands (S-0378, S-0402, S-0442–S-0445, S-0855–S-0858, S-0860–S-0864); `smd-tab` and the grid ball ratios have fewer than three records and no goals in `lands/1` (such packages need `[land]`). `hole_clearance` (0.2 mm) and `annular_ring` (0.35 mm) are Fenolite choices, not calibrated: manufacturer documents give holes without a tolerance stack and rarely a pad diameter.
- [x] 2.3 Write `docs/formats/library/lands.md` (every constant, its derivation, the label `INFERRED`, the statement that no IPC table or calculator was used, the drawing conventions) and register `H-G-LAND-CALC` in `docs/hypotheses.md` (scenario "Published table equals the code"). Proof: `uv run pytest tests/unit/catalog/footprints/test_lands.py -k published -q`; `uv run pytest tests/unit/test_hypotheses_register.py -q`.
  Done 2026-10-30: `test_lands.py -k published` 1 passed (every constant of `LANDS[1]` in `docs/formats/library/lands.md` with value, `INFERRED` and derivation, and the drawing conventions); `test_hypotheses_register.py` 38 passed. `H-G-LAND-CALC` (pre-registered as proposed) now names `test_calibration_set_within_tolerance`: on 2026-10-30 every number of the 27 records within 0.42 mm of the manufacturer land; it stays `INFERRED`. A session row is added to `LEGAL-ANNEX.md`.
- [x] 2.4 Add the manufacturer override, `land.deltas`, `package.land-override` and the evidence rule (scenarios "Override recorded", "Calculated land stays inferred"). Proof: `uv run pytest tests/unit/catalog/footprints/test_override.py -q`.
  Done 2026-10-30: `test_override.py` 4 passed: `[land]` wins unchanged, `land.deltas` per number when the class has goals, one info `package.land-override` naming the largest delta (or saying there is nothing to compare), a calculated land is `INFERRED` whatever the record says, a manufacturer land keeps the record's label. The spec scenario "Override recorded" now names the numbers of the authored record (onsemi 751-07: 1.52 × 0.60 mm at 5.50 mm).

## 3. Families

- [ ] 3.1 `chip` and `molded`, with polarity on pad 1 (scenario "Pad numbering and orientation" for two-terminals). Proof: `uv run pytest tests/unit/catalog/footprints/test_two_terminal.py -q`.
- [ ] 3.2 `gullwing` (dual, quad, sides, tab) (scenarios "A gull-wing record is drawn", "SOT-23 sides"). Proof: `uv run pytest tests/unit/catalog/footprints/test_gullwing.py -q`.
- [ ] 3.3 `nolead` with exposed pad and paste grid (scenario "QFN exposed pad"). Proof: `uv run pytest tests/unit/catalog/footprints/test_nolead.py -q`.
- [ ] 3.4 `grid` with ball names and depopulation (scenario "Depopulated centre"). Proof: `uv run pytest tests/unit/catalog/footprints/test_grid.py -q`.
- [ ] 3.5 `dip`, `to`, `header` and `connector` (series expansion) with through-hole lands (scenarios "DIP drill", "Result of a connector series" at the API level). Proof: `uv run pytest tests/unit/catalog/footprints/test_through_hole.py tests/unit/catalog/footprints/test_connector.py -q`.
- [ ] 3.6 Courtyard, `drawing/0` and `drawing/1` conventions, silkscreen clearance, naming check and stamp (scenarios "Courtyard contains everything", "Drawing 1 pin-1 marks", "No silk on copper", "Name checked against numbers", "Stamp in the description"); write `docs/formats/library/naming.md`. Proof: `uv run pytest tests/unit/catalog/footprints/test_courtyard.py tests/unit/catalog/footprints/test_drawing.py tests/unit/catalog/footprints/test_naming.py -q`.
- [ ] 3.7 Altium PCB library of generated footprints: every family's generated footprint passes `pcblib.check_footprint` without refusal or drop, and one library written by `write_pcblib` reads back through `read_pcblib` with equal pads (requirement "Generated footprints in an Altium PCB library", scenario "PcbLib read back with equal pads"). Proof: `uv run pytest tests/unit/catalog/footprints/test_pcblib.py -q`.

## 4. Catalog migration

- [ ] 4.1 Capture `tests/data/catalog/footprints.sha256` on the base commit if c0259 did not, then draw the family-shaped catalog entries with the generators and delete the private helpers (scenarios "Catalog bytes unchanged", "No private land helper remains"). Proof: `uv run pytest tests/unit/catalog/test_catalog_generated.py tests/unit/catalog/test_catalog.py tests/unit/catalog/test_footprint_previews.py -q`.

## 5. Bodies and STEP

- [ ] 5.1 Add `bodies.py` (body, lead, pin and tab bodies, the 32-gon table) (scenarios "SOIC bodies", "Height read from a generated body", "No height, no body"). Proof: `uv run pytest tests/unit/catalog/footprints/test_bodies.py tests/unit/model/test_outward_height.py -q`.
- [ ] 5.2 Write `docs/formats/step/part21.md` from public sources (CAx-IF recommended practices, the ISO 10303-21 abstract) with labels, then `src/fenolite/backends/step.py` and a test reader (scenario "Deterministic and closed"). Proof: `uv run pytest tests/unit/backends/test_step.py -q`; `uv run pytest tests/unit/test_import_graph.py -q`.
- [ ] 5.3 Plan generated STEP models in `fenolite build` (scenario "Model written beside the library"); check that a design with only catalog footprints keeps its KiCad bytes. Proof: `uv run pytest tests/unit/lens/test_build_generated_models.py -q`.
- [ ] 5.4 KiCad oracle: register `H-K-STEP-MODELS` and add `tests/kicad/export/test_generated_models.py` (scenario "KiCad reads the models"). Proof: `uv run pytest tests/kicad/export/test_generated_models.py -rA` (in CI, KiCad 9 and 10).

## 6. DSL and CLI

- [ ] 6.1 Add `Footprint.from_package` (scenarios "A generated footprint is registered", "Error finding in a script"). Proof: `uv run pytest tests/unit/dsl/test_footprint_from_package.py -q`.
- [ ] 6.2 Add the verb dispatch and `fenolite library generate` with its plan, receipt and result (scenarios "Board form unchanged", "Plan and confirm", "Result of a connector series"). Proof: `uv run pytest tests/unit/cli/test_library_generate.py tests/unit/cli/test_library.py -q`.
- [ ] 6.2b `fenolite library generate` also plans `DIR/<NICK>.PcbLib` with all generated footprints through the Altium writer, in the same plan and receipt; `--no-pcblib` leaves it out (maintainer's answer to open question 3, 2026-10-30). Proof: `uv run pytest tests/unit/cli/test_library_generate.py -k pcblib -q`.
- [ ] 6.3 Author `examples/generated/` (a board using one generated footprint per family, built for KiCad, with STEP export). Proof: `uv run pytest tests/unit/test_examples.py -k generated -q`.

## 7. Closing

- [ ] 7.1 Docs: `docs/footprint-generators.md` (families, keys, calculator, override, conventions, bodies, STEP, naming), the "Generated footprints" section of `docs/dsl.md`, `library generate` in `docs/cli-contract.md`, links from `docs/index.md`. Proof: `uv run pytest tests/unit -k "docs or facts_page" -q`.
- [ ] 7.2 Agent guide: add tested lines to `footprints.md` for `Footprint.from_package`, `fenolite library generate` and the `package.*` codes, then run `uv run python tools/gen_agent_guide.py`. Proof: `uv run pytest tests/unit/agent/test_pages.py -q`.
- [ ] 7.3 Residue and evidence: authored-for-Fenolite lines on every record, no IPC value, no third-party footprint or model, hypotheses registered, evidence matrix regenerated. Proof: `make residue`; `uv run pytest tests/unit/test_hypotheses_register.py -q`; `uv run python tools/gen_evidence_matrix.py --check`.
- [ ] 7.4 Add the entry to `CHANGELOG.md` under `## [Unreleased]`, noting that `.fenolite/board.json` gains bodies for catalog footprints whose records give heights. This waits until `dev` is at `0.7.0.dev0`: the v0.6 guard requires `[Unreleased]` to stay empty while the version is `0.6.0`. Proof: `uv run pytest tests/unit -k changelog -q`.
- [ ] 7.5 Run `make check-fast`, publish the batch to its working branch, and confirm the required CI jobs (unit and KiCad) on the exact commit. Proof: `make check-fast`, and the required jobs green on the pushed head.
