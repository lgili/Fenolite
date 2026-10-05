## 0. Entry check

- [ ] 0.1 Read the living `design-dsl`, `kicad-file-backend`, `manufacturing-exports`, `cli-contract`, `manual-copper` and `kicad-oracle` specs and `openspec list`. Write under this task, with the date: whether another change modified one of the four requirements this change modifies (then re-base the MODIFIED text), and whether c0061 is archived (else the schematic key of task 2.3 waits). Proof: `openspec validate c0074-drawing-sheets-followups --strict --no-interactive` passes after any re-base.

## 1. Probes and registers

- [ ] 1.1 Add the rows `H-K-PRO-WKS-SCH`, `H-K-OUTLINE-CHAIN`, `H-K-OUTLINE-FPEDGE`, `H-K-EXPORT-OPTIONS` and `H-K-STITCH-AVOID` to `docs/hypotheses.md` (backend `kicad`, level `INFERRED`, the tests and criteria of `design.md`, result `pending`), and set `H-G-EDGE-EXACT` to refuted with the measured tolerance. Proof: `uv run pytest tests/unit/test_hypotheses_register.py tests/unit/test_provenance.py`.
- [ ] 1.2 Write `tests/kicad/followups/test_followup_probes.py` for the schematic key, the outline gaps, the footprint edges and the export options (scenario "Probes on both majors" without the stitching probe), record the outcomes, and write the facts to `docs/formats/kicad/worksheet.md`, `board.md` and `cli.md` with sources S-0020 and S-0029. Proof: `uv run pytest tests/kicad/followups/test_followup_probes.py -rA` on the local KiCad 10.0.6 and inside the pinned 9.0.9 image; `FENOLITE_PROBES_WRITE=1` updates both probe files; `uv run pytest tests/kicad/test_probe_results.py tests/unit/test_format_facts.py`.

## 2. Drawing sheet and title block

- [ ] 2.1 Add `Design.sheet`, `Design.title_block` and `drawing_sheet_source`, and their model in `to_model` (scenarios of "Drawing sheet and title block in the DSL"). Proof: `uv run pytest tests/unit/dsl/test_sheet_calls.py tests/unit/dsl`.
- [ ] 2.2 Read the source and write `<name>.kicad_wks` in the build, with `result.drawing_sheet` (scenarios of "Drawing sheets in a build"). Proof: `uv run pytest tests/unit/lens/test_build_sheet.py tests/unit/cli/test_build_cmd.py tests/consistency`.
- [ ] 2.3 Add `schematic` to `apply_sheet_keys` and pass it from the build when a schematic is written (scenario "Schematic key with a schematic", and "Schematic gets the frame" when c0061 is archived). Proof: `uv run pytest tests/unit/backends/kicad/test_pro_sheet.py tests/unit/lens/test_build_sheet.py`.

## 3. Export presets

- [ ] 3.1 Write `src/fenolite/exports/preset.py` and `tests/unit/exports/test_preset.py` (scenarios of "Export presets"). Proof: `uv run pytest tests/unit/exports/test_preset.py tests/unit/exports/test_plan.py`.
- [ ] 3.2 Add `--preset` to `cmd_export` (scenarios of "Export command"). Proof: `uv run pytest tests/unit/cli/test_export_cmd.py tests/consistency tests/unit/cli/test_hermetic_examples.py`.

## 4. Outline

- [ ] 4.1 Add `CHAIN_GAP`, the endpoint joining and `BoardOutline.joined` (scenario "Gap below the chaining distance"). Proof: `uv run pytest tests/unit/backends/kicad/test_outline.py`.
- [ ] 4.2 Add `frame.footprint_edges` and chain footprint edge items (scenario "Edge closed by a footprint"); re-run the demo census for `H-G-PLACE-OUTLINE`. Proof: `uv run pytest tests/unit/backends/kicad/test_outline.py tests/unit/backends/kicad/test_frame.py`; `uv run pytest tests/corpus/test_outline_corpus.py -rA` with the corpus cached.

## 5. Stitching

- [ ] 5.1 Drop stitch candidates in keep-outs and near the edge (scenarios of "Stitching vias"). Proof: `uv run pytest tests/unit/backends/kicad/test_copper_stitch.py tests/unit/backends/kicad/test_copper.py`.
- [ ] 5.2 Add the stitching probe `stitch-avoid` to `tests/kicad/followups/test_followup_probes.py`. Proof: `uv run pytest tests/kicad/followups/test_followup_probes.py -k stitch -rA` on both majors.

## 6. Documentation

- [ ] 6.1 Document `sheet()`, `title_block()`, the drawing sheet output, presets with an example of the user's own, the outline joining and footprint edges, and the stitching rule in `docs/dsl.md`, `docs/cli-contract.md` and `docs/lens.md` where the outline is described. Proof: `uv run pytest tests/consistency tests/unit/test_repo_layout.py tests/residue`.

## 7. Closing

- [ ] 7.1 Run the residue and full test suites. Proof: `uv run pytest tests/residue` and `uv run python tools/residue/scan.py` exit 0; `make check` passes; `openspec validate c0074-drawing-sheets-followups --strict --no-interactive` passes; `gh pr checks` shows `unit`, `kicad-9` and `kicad-10` passing.
- [ ] 7.2 Update the evidence: the five rows become `KICAD-VERIFIED (9.0.x, 10.0.x)` with their runs, `H-G-PLACE-OUTLINE` records the new counts, or each records what failed. Proof: `uv run pytest tests/unit/test_provenance.py tests/unit/test_hypotheses_register.py`.
- [ ] 7.3 Add to `CHANGELOG.md` under Unreleased: "`design.sheet()` and `design.title_block()` put the user's drawing sheet and title block on the board and the schematic; `fenolite export --preset` applies the user's fab options; board outlines join endpoints closer than 10 µm and include footprint edge items; stitching avoids keep-outs and the board edge". Update `docs/roadmap.md`. Proof: `git diff --stat CHANGELOG.md docs/roadmap.md` lists both files.
