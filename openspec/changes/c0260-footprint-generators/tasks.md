## 0. Entry check

- [ ] 0.1 Read `openspec list` and the living specs this change touches (`fenolite-component-catalog`, `dsl-footprint-authoring`, `component-body-volumes`, `design-model`, `package-layering`), and record under this task, with the date and the base commit:
  - whether c0246, c0248 and c0259 are archived. Take `LengthRange` from c0259 if it defines one, else add it to `fenolite.core.quantities` (task 1.1); align the family keys of `design.md` decision 2 with c0259's final envelope and catalog records;
  - that c0259's catalog records carry `drawing = 0` and a `[land]` per family-shaped entry, and that its golden SHA-256 list exists (else capture it in task 4.1 before any helper is removed);
  - which open change of the batch registers further `fenolite library` verbs (c0262, c0264, c0265, c0266), so that decision 17's dispatch table is the one they extend;
  - the maintainer's answers to the open questions of `design.md` (densities, calibration from IPC-citing documents, lead bodies).

  Proof: `openspec validate c0260-footprint-generators --strict`; `make check-fast`.

## 1. Ranges, records and codes

- [ ] 1.1 Add `LengthRange` and its parser to `src/fenolite/core/quantities.py` (scenarios "Range spellings", "Sub-nanometre value"). Proof: `uv run pytest tests/unit/core/test_length_range.py -q`.
- [ ] 1.2 Add `src/fenolite/catalog/footprints/` with `generate`, `Generated`, `LandReport`, the family key schemas and `codes.py`; register the `package.*` codes in `explain.toml` (scenarios "Unknown family", "Missing pitch", "Calculator without a table version", "Reserved density", "Span inside the body"). Proof: `uv run pytest tests/unit/catalog/footprints/test_generate.py tests/unit/catalog/footprints/test_codes.py -q`.
- [ ] 1.3 Author the test records under `tests/data/packages/` (one per family, each opening with the authored-for-Fenolite line, numbers from registered public outlines). Register their sources in `docs/evidence/sources.md` and `docs/catalog/sources.md`. Proof: `make residue`; `uv run pytest tests/unit -k sources -q`.

## 2. Land calculator and constants

- [ ] 2.1 Implement the worst-case calculator, the pad-gap clip and `package.land-impossible` in `lands.py` (scenarios "Calculated SOIC land", "Missing bound", "Fine pitch is clipped"). Proof: `uv run pytest tests/unit/catalog/footprints/test_lands.py -q`.
- [ ] 2.2 Write `tools/calibrate_lands.py` and its `--check` mode; author enough calibration records with cited manufacturer lands for each class; generate `LANDS[1]` (scenarios "Calibration is reproducible", "Uncalibrated class"). Proof: `uv run python tools/calibrate_lands.py --check`; `uv run pytest tests/unit/tools/test_calibrate_lands.py -q`.
- [ ] 2.3 Write `docs/formats/library/lands.md` (every constant, its derivation, the label `INFERRED`, the statement that no IPC table or calculator was used, the drawing conventions) and register `H-G-LAND-CALC` in `docs/hypotheses.md` (scenario "Published table equals the code"). Proof: `uv run pytest tests/unit/catalog/footprints/test_lands.py -k published -q`; `uv run pytest tests/unit/test_hypotheses_register.py -q`.
- [ ] 2.4 Add the manufacturer override, `land.deltas`, `package.land-override` and the evidence rule (scenarios "Override recorded", "Calculated land stays inferred"). Proof: `uv run pytest tests/unit/catalog/footprints/test_override.py -q`.

## 3. Families

- [ ] 3.1 `chip` and `molded`, with polarity on pad 1 (scenario "Pad numbering and orientation" for two-terminals). Proof: `uv run pytest tests/unit/catalog/footprints/test_two_terminal.py -q`.
- [ ] 3.2 `gullwing` (dual, quad, sides, tab) (scenarios "A gull-wing record is drawn", "SOT-23 sides"). Proof: `uv run pytest tests/unit/catalog/footprints/test_gullwing.py -q`.
- [ ] 3.3 `nolead` with exposed pad and paste grid (scenario "QFN exposed pad"). Proof: `uv run pytest tests/unit/catalog/footprints/test_nolead.py -q`.
- [ ] 3.4 `grid` with ball names and depopulation (scenario "Depopulated centre"). Proof: `uv run pytest tests/unit/catalog/footprints/test_grid.py -q`.
- [ ] 3.5 `dip`, `to`, `header` and `connector` (series expansion) with through-hole lands (scenarios "DIP drill", "Result of a connector series" at the API level). Proof: `uv run pytest tests/unit/catalog/footprints/test_through_hole.py tests/unit/catalog/footprints/test_connector.py -q`.
- [ ] 3.6 Courtyard, `drawing/0` and `drawing/1` conventions, silkscreen clearance, naming check and stamp (scenarios "Courtyard contains everything", "Drawing 1 pin-1 marks", "No silk on copper", "Name checked against numbers", "Stamp in the description"); write `docs/formats/library/naming.md`. Proof: `uv run pytest tests/unit/catalog/footprints/test_courtyard.py tests/unit/catalog/footprints/test_drawing.py tests/unit/catalog/footprints/test_naming.py -q`.

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
- [ ] 6.3 Author `examples/generated/` (a board using one generated footprint per family, built for KiCad, with STEP export). Proof: `uv run pytest tests/unit/test_examples.py -k generated -q`.

## 7. Closing

- [ ] 7.1 Docs: `docs/footprint-generators.md` (families, keys, calculator, override, conventions, bodies, STEP, naming), the "Generated footprints" section of `docs/dsl.md`, `library generate` in `docs/cli-contract.md`, links from `docs/index.md`. Proof: `uv run pytest tests/unit -k "docs or facts_page" -q`.
- [ ] 7.2 Agent guide: add tested lines to `footprints.md` for `Footprint.from_package`, `fenolite library generate` and the `package.*` codes, then run `uv run python tools/gen_agent_guide.py`. Proof: `uv run pytest tests/unit/agent/test_pages.py -q`.
- [ ] 7.3 Residue and evidence: authored-for-Fenolite lines on every record, no IPC value, no third-party footprint or model, hypotheses registered, evidence matrix regenerated. Proof: `make residue`; `uv run pytest tests/unit/test_hypotheses_register.py -q`; `uv run python tools/gen_evidence_matrix.py --check`.
- [ ] 7.4 Add the entry to `CHANGELOG.md` under `## [Unreleased]`, noting that `.fenolite/board.json` gains bodies for catalog footprints whose records give heights. This waits until `dev` is at `0.7.0.dev0`: the v0.6 guard requires `[Unreleased]` to stay empty while the version is `0.6.0`. Proof: `uv run pytest tests/unit -k changelog -q`.
- [ ] 7.5 Run `make check-fast`, publish the batch to its working branch, and confirm the required CI jobs (unit and KiCad) on the exact commit. Proof: `make check-fast`, and the required jobs green on the pushed head.
