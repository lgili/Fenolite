## 0. Entry check

- [x] 0.1 Read the living `design-dsl`, `kicad-file-backend`, `manufacturing-exports`, `cli-contract`, `manual-copper` and `kicad-oracle` specs and `openspec list`. Write under this task, with the date: whether another change modified one of the four requirements this change modifies (then re-base the MODIFIED text), and whether c0061 is archived (else the schematic key of task 2.3 waits). Proof: `openspec validate c0074-drawing-sheets-followups --strict --no-interactive` passes after any re-base.
  - 2026-10-06: no other change modifies the four requirements this change modifies: c0068 added "Pad zone connections" requirements and c0069 other `layout-lens` ones. c0061 is not archived, so no build writes a schematic: `apply_sheet_keys(schematic=True)` exists and is tested, and the scenario "Schematic gets the frame" waits.

## 1. Probes and registers

- [x] 1.1 Add the rows `H-K-PRO-WKS-SCH`, `H-K-OUTLINE-CHAIN`, `H-K-OUTLINE-FPEDGE`, `H-K-EXPORT-OPTIONS` and `H-K-STITCH-AVOID` to `docs/hypotheses.md` (backend `kicad`, level `INFERRED`, the tests and criteria of `design.md`, result `pending`), and set `H-G-EDGE-EXACT` to refuted with the measured tolerance. Proof: `uv run pytest tests/unit/test_hypotheses_register.py tests/unit/test_provenance.py`.
  - 2026-10-06: done, with the results of task 1.2: four rows `KICAD-VERIFIED`, `H-K-EXPORT-OPTIONS` `INFERRED` (six keys change nothing on the probe board), `H-G-EDGE-EXACT` refuted and superseded by `H-K-OUTLINE-CHAIN`.
- [x] 1.2 Write `tests/kicad/followups/test_followup_probes.py` for the schematic key, the outline gaps, the footprint edges and the export options (scenario "Probes on both majors" without the stitching probe), record the outcomes, and write the facts to `docs/formats/kicad/worksheet.md`, `board.md` and `cli.md` with sources S-0020 and S-0029. Proof: `uv run pytest tests/kicad/followups/test_followup_probes.py -rA` on the local KiCad 10.0.6 and inside the pinned 9.0.9 image; `FENOLITE_PROBES_WRITE=1` updates both probe files; `uv run pytest tests/kicad/test_probe_results.py tests/unit/test_format_facts.py`.
  - 2026-10-06: done on 10.0.6 (local) and 9.0.9 (pinned image), 39 tests on each. The option runs use the built blink, not a corpus demo, so the test needs no corpus; the requirement says so now. The cases are in `tests/kicad/followups/_followcases.py`.

## 2. Drawing sheet and title block

- [x] 2.1 Add `Design.sheet`, `Design.title_block` and `drawing_sheet_source`, and their model in `to_model` (scenarios of "Drawing sheet and title block in the DSL"). Proof: `uv run pytest tests/unit/dsl/test_sheet_calls.py tests/unit/dsl`.
  - 2026-10-06: done.
- [x] 2.2 Read the source and write `<name>.kicad_wks` in the build, with `result.drawing_sheet` (scenarios of "Drawing sheets in a build"). Proof: `uv run pytest tests/unit/lens/test_build_sheet.py tests/unit/cli/test_build_cmd.py tests/consistency`.
  - 2026-10-06: done. One rule beyond the text: a paper or title block that the script declares is written from the script on a rebuild too, because a changed `title_block()` would otherwise never reach the board; the requirement says so now.
- [x] 2.3 Add `schematic` to `apply_sheet_keys` and pass it from the build when a schematic is written (scenario "Schematic key with a schematic", and "Schematic gets the frame" when c0061 is archived). Proof: `uv run pytest tests/unit/backends/kicad/test_pro_sheet.py tests/unit/lens/test_build_sheet.py`.
  - 2026-10-06: done for `apply_sheet_keys`; the build passes `schematic=True` when c0061 makes it write a schematic.
  - 2026-10-05: c0061 is on `dev` (76ef4916): `write_triad(schematic=…)` passes the flag, and the build sets it unless `--schematic skip`. Scenario "Schematic gets the frame" is covered by `test_user_sheet_in_a_built_project` and `test_schematic_key_follows_the_schematic`.

## 3. Export presets

- [x] 3.1 Write `src/fenolite/exports/preset.py` and `tests/unit/exports/test_preset.py` (scenarios of "Export presets"). Proof: `uv run pytest tests/unit/exports/test_preset.py tests/unit/exports/test_plan.py`.
  - 2026-10-06: done.
- [x] 3.2 Add `--preset` to `cmd_export` (scenarios of "Export command"). Proof: `uv run pytest tests/unit/cli/test_export_cmd.py tests/consistency tests/unit/cli/test_hermetic_examples.py`.
  - 2026-10-06: done.

## 4. Outline

- [x] 4.1 Add `CHAIN_GAP`, the endpoint joining and `BoardOutline.joined` (scenario "Gap below the chaining distance"). Proof: `uv run pytest tests/unit/backends/kicad/test_outline.py`.
  - 2026-10-06: done.
- [x] 4.2 Add `frame.footprint_edges` and chain footprint edge items (scenario "Edge closed by a footprint"); re-run the demo census for `H-G-PLACE-OUTLINE`. Proof: `uv run pytest tests/unit/backends/kicad/test_outline.py tests/unit/backends/kicad/test_frame.py`; `uv run pytest tests/corpus/test_outline_corpus.py -rA` with the corpus cached.
  - 2026-10-06: done; the corpus was cached: all 21 native demos close (`-01` with one joined group, `-14` and `-16` with their footprints' edge items), and the test now asserts it.

## 5. Stitching

- [x] 5.1 Drop stitch candidates in keep-outs and near the edge (scenarios of "Stitching vias"). Proof: `uv run pytest tests/unit/backends/kicad/test_copper_stitch.py tests/unit/backends/kicad/test_copper.py`.
  - 2026-10-06: done. Two additions: a candidate off the board (outside the outline or inside a cut-out) is dropped, and on a rebuild the rule areas and the outline of the existing board count; the requirement says both.
- [x] 5.2 Add the stitching probe `stitch-avoid` to `tests/kicad/followups/test_followup_probes.py`. Proof: `uv run pytest tests/kicad/followups/test_followup_probes.py -k stitch -rA` on both majors.
  - 2026-10-06: done on both majors: `stitch-avoid` `equal`.

## 6. Documentation

- [x] 6.1 Document `sheet()`, `title_block()`, the drawing sheet output, presets with an example of the user's own, the outline joining and footprint edges, and the stitching rule in `docs/dsl.md`, `docs/cli-contract.md` and `docs/lens.md` where the outline is described. Proof: `uv run pytest tests/consistency tests/unit/test_repo_layout.py tests/residue`.
  - 2026-10-06: done, with the preset table and an example in `docs/exports.md` and the stitching rule in `docs/copper.md`.

## 7. Closing

- [x] 7.1 Run the residue and full test suites. Proof: `uv run pytest tests/residue` and `uv run python tools/residue/scan.py` exit 0; `make check` passes; `openspec validate c0074-drawing-sheets-followups --strict --no-interactive` passes; `gh pr checks` shows `unit`, `kicad-9` and `kicad-10` passing.
  - 2026-10-06: residue, `make check-fast` and `openspec validate` pass locally; the follow-up probes and the probe files pass on 10.0.6 and 9.0.9 (local). The full `make check` and `gh pr checks` are left to the coordinator's merge run (one full suite at a time).
- [x] 7.2 Update the evidence: the five rows become `KICAD-VERIFIED (9.0.x, 10.0.x)` with their runs, `H-G-PLACE-OUTLINE` records the new counts, or each records what failed. Proof: `uv run pytest tests/unit/test_provenance.py tests/unit/test_hypotheses_register.py`.
  - 2026-10-06: done from the local runs: four rows `KICAD-VERIFIED (9.0.x, 10.0.x)`; `H-K-EXPORT-OPTIONS` records which six keys changed nothing and stays `INFERRED`; `H-G-PLACE-OUTLINE` records the new counts. The CI runs are to be added when the jobs pass.
  - 2026-10-05: the `kicad-9` and `kicad-10` jobs passed on commit dcd9c04 (run https://github.com/lgili/Fenolite/actions/runs/37311079171); the run is cited in the four verified rows.
- [x] 7.3 Add to `CHANGELOG.md` under Unreleased: "`design.sheet()` and `design.title_block()` put the user's drawing sheet and title block on the board and the schematic; `fenolite export --preset` applies the user's fab options; board outlines join endpoints closer than 10 µm and include footprint edge items; stitching avoids keep-outs and the board edge". Update `docs/roadmap.md`. Proof: `git diff --stat CHANGELOG.md docs/roadmap.md` lists both files.
  - 2026-10-06: done.
