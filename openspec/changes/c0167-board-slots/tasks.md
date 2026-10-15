## 0. Entry check

- [ ] 0.1 Read `openspec list` and the living `design-model`, `design-dsl`, `geometry-boolean-backends`, `kicad-file-backend`, `board-analyses` and `kicad-oracle` specs. Write under this task, with the date: whether another open change holds a delta of "Backend selection", "Outline shape checks" or "Board boundary" (regenerate this change's MODIFIED blocks from the living text if one was archived since `a87723c`); whether c0159 to c0161 are archived (c0170 needs them, this change does not); the maintainer's answers to the open questions of `design.md`. Proof: `openspec validate c0167-board-slots --strict --no-interactive` passes.

## 1. Register and probes

- [ ] 1.1 Add the rows `H-K-SLOT-RING`, `H-K-SLOT-OVERLAP`, `H-K-SLOT-UNION`, `H-K-HOLE-OVERLAP` and `H-G-RING-UNION` to `docs/hypotheses.md` (level `INFERRED`, the tests and criteria of `design.md`, the measurements of 2026-10-15 as the first record), and the facts of measurements 1 to 5 to `docs/formats/kicad/board.md` with S-0020 and S-0029. Proof: `uv run pytest tests/unit/test_hypotheses_register.py tests/unit/test_provenance.py tests/unit/test_format_facts.py -q`.
- [ ] 1.2 Write `tests/data/slots/design.py` (the shared fixture, authored for Fenolite) and `tests/kicad/board/_slotbench.py` with the probes `slot-overlap`, `slot-union`, `slot-drilled-overlap` and `slot-drilled-near` on boards written through the model API (measurements 1, 2, 4, 5); record them on both majors. An outcome that differs from `design.md` stops this task and the design is corrected first. Proof: `uv run pytest tests/kicad/board/test_slots.py -k "overlap or union or drilled" -rA` with `FENOLITE_KICAD_CLI=docker:kicad/kicad:10.0.6` and then `docker:kicad/kicad:9.0.9`; `FENOLITE_PROBES_WRITE=1`; `uv run pytest tests/kicad/test_probe_results.py -q`.

## 2. Stadium and model

- [ ] 2.1 Move the fixed-point table to `fenolite.core.trig` (re-exported by `geometry.transform`, values unchanged) and write `fenolite.core.stadium` (Decision 3; scenario "The stadium of a turned slot"). Proof: `uv run pytest tests/unit/core/test_stadium.py tests/unit/geometry -q`; `uv run pytest tests/unit/test_import_graph.py -q`.
- [ ] 2.2 Add `OutlineSlot`, `Outline.slots` and `model.outline.outline_items` (Decision 6), the canonical form and the schema (scenario "A slot round-trips"); the 0.2.0 and 0.4.0 fixtures keep their bytes. Proof: `uv run pytest tests/unit/model/test_outline_slots.py tests/unit/model -q`; `uv run python tools/gen_schemas.py --check`.
- [ ] 2.3 Write `Design.slot`, `shape.stadium`, the key row and `to_model` (scenarios "A slot in the model", "Refused slots"); add a `fenolite-design` use to the agent guide and regenerate `dsl-reference`. Proof: `uv run pytest tests/unit/dsl/test_slots.py tests/unit/agent/test_pages.py -q`; `uv run python tools/gen_agent_guide.py --check`.

## 3. Union

- [ ] 3.1 Write `ClipperBackend`, `BACKEND_ORDER = ("fallback", "clipper")` and `select_backend(…, operation=)` (scenarios "Selection by operation", "Two slots in an L"); `body_volumes` results unchanged. Proof: `uv run pytest tests/unit/geometry/test_clipper.py tests/unit/geometry/test_boolean_fallback.py tests/unit/analysis/test_body_volumes.py tests/unit/test_import_graph.py -q`.
- [ ] 3.2 Write `merge_rings` with the arcs put back (scenarios "L of two slots keeps its arcs", "Separate rings untouched"), with a seeded property test: the merged area equals the polygon union's within `MERGE_TOL` times the perimeter. First item of the cut order for the arcs. Proof: `uv run pytest tests/unit/geometry/test_merge_rings.py -q`.

## 4. KiCad lowering

- [ ] 4.1 Write `lowered_outline`, route `_edgesign`, `board_outline`, `outline_box`, `fill_inputs_digest` through it, and extend `check_outline` with the two codes, their `explain.toml` entries and `recovery` rows (scenario "Overlapping slots merged or refused"). Proof: `uv run pytest tests/unit/backends/kicad/test_slots_outline.py tests/unit/backends/kicad/test_outline.py tests/unit/lens -q`.
- [ ] 4.2 Write slots and merged rings in `write_board`, `kicad.board.outline-overlap` and `kicad.board.free-hole` (scenarios "A lone slot as a stadium", "Overlap through the model API", "A model hole"); every committed board sample keeps its bytes. Proof: `uv run pytest tests/unit/backends/kicad -q`.
- [ ] 4.3 Write `edge_outline` and `slots_of` (scenario "Slots read back"). Second item of the cut order for `slots_of`. Proof: `uv run pytest tests/unit/backends/kicad/test_slots_outline.py -k read_back -q`.
- [ ] 4.4 Add the probes `slot-ring-drc`, `slot-ring-drill` and `slot-ring-read` on the built fixture and record them on both majors (requirement "Slots pass the oracle"). Proof: `uv run pytest tests/kicad/board/test_slots.py -rA` in both pinned images; `uv run pytest tests/kicad/test_probe_results.py -q`.

## 5. Readers

- [ ] 5.1 Take slots and merged rings in `board_boundary`, with `problem` (scenario "Slots in the boundary"); `fenolite analyze` gives `geometry.backend-unavailable` with exit 6 for `overlap-needs-geo`. Proof: `uv run pytest tests/unit/analysis/test_boundary.py tests/unit/cli/test_analyze_cmd.py -q`.
- [ ] 5.2 Plan no PCB document for an outline with slots, and add the slots to `lower._outline`'s skip (Decision 9). Proof: `uv run pytest tests/unit/lens/test_altium_pcb.py -k slot -q`.

## 6. Documentation

- [ ] 6.1 Write `docs/geometry.md` ("Boolean backends": the clipper backend and the licence of pyclipper, S-0016; "Union of curved rings"), `docs/dsl.md` ("Board": `slot`, `shape.stadium`, milled versus drilled), `docs/design-model.md` (`Outline.slots`, the 0.4.x sentence, the two meanings of slot), `docs/cli-contract.md` (four codes), `docs/analyses.md` ("Creepage": slots are cut-outs). Proof: `uv run pytest tests/consistency -q`.

## 7. Closing

- [ ] 7.1 Run the residue scan and the fast checks. Proof: `uv run python tools/residue/scan.py` exits 0; `make check-fast` passes.
- [ ] 7.2 Update the evidence labels: the five rows hold their measured levels and results; `uv run python tools/gen_evidence_matrix.py`. Proof: `uv run pytest tests/unit/test_hypotheses_register.py tests/unit/test_evidence_matrix_page.py -q`.
- [ ] 7.3 Add to `CHANGELOG.md` under `## [Unreleased]`: board slots, the union of overlapping cut-outs and slots, the clipper backend, the named refusals, and the sentence that release 0.4.x cannot read a model document that carries `slots`. Proof: `grep -n "slots" CHANGELOG.md`; `openspec validate c0167-board-slots --strict --no-interactive` passes.
