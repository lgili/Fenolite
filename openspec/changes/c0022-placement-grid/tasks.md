## 1. Registers and documentation

- [ ] 1.1 Register the hypotheses. This is the first commit of the implementation, so c0014's cited-id guard sees the ids registered.
  - Add the rows `H-K-PLACE-MOVE` and `H-K-PLACE-TOUCH` (backend `kicad`) and `H-G-PLACE-OUTLINE` (backend `general`) to `docs/hypotheses.md`, with level `INFERRED`, the test and criterion of `design.md`, and result `pending`. Add the paragraph "Change c0022 (placement) adds …".
  - Widen the "used for" cells of S-0020 (moved footprints, touching courtyards) and S-0038 (the courtyard overlap check), after opening S-0038; widen only with what the page states.
  - Re-check every name consumed from c0011, c0019, c0026, c0028 and c0030 (design "Context" and "Files and public API") against the working tree, and list each divergence in the pull request description. If c0030 has not archived, apply the design's risk note and say so under this task.

  Proof: `uv run pytest tests/unit/test_provenance.py tests/unit/test_hypotheses_register.py`; `grep -cE '^\| (H-K-PLACE-(MOVE|TOUCH)|H-G-PLACE-OUTLINE) ' docs/hypotheses.md` prints `3`.
- [ ] 1.2 Write the skeleton of `docs/placement.md` (strategies, legality codes, how a placement survives a build) and the fact rows of `docs/formats/kicad/board.md` for the outline from `Edge.Cuts` and for a moved footprint, each with a source, a label and a hypothesis. Add a `PROVENANCE.md` row for `replace.py` and `outline.py` and a `LEGAL-ANNEX.md` session row. Proof: `uv run pytest tests/unit/test_format_facts.py tests/unit/test_provenance.py tests/unit/test_legal_docs.py`.

## 2. Probes first (`kicad-cli` 10.0.6 locally, 9.0.9 in the pinned image)

- [ ] 2.1 Write `src/fenolite/backends/kicad/replace.py::move_footprint` and `PlacementError` (design Decision 4) and `tests/unit/backends/kicad/test_replace.py`, covering every scenario of "Footprints are re-placed on a read board" plus RT1 of each written board. Proof: `uv run pytest tests/unit/backends/kicad/test_replace.py`; `uv run pyright src`.
- [ ] 2.2 Write `tests/kicad/place/_placecases.py` and `test_place_probes.py` (`test_move`, `test_touch`), add `tests/kicad/place` to the `sys.path` list of `tests/kicad/conftest.py` and to the fake run of `tests/unit/test_kicad_probes.py`, and add the probes `place-move-translate`, `place-move-rotate`, `place-move-flip` and `place-touch` to `PROBES` for both majors. The touch bench is built through the model API with c0028's courtyards and carries its 20 µm control pair. Regenerate both probe files with `FENOLITE_PROBES_WRITE=1`. Apply the fallbacks of design Decisions 4 and 6 to any outcome that differs, and note each outcome under this task. Proof: `uv run pytest tests/kicad/place/test_place_probes.py tests/kicad/test_probe_results.py -rA` on the local KiCad 10.0.6 and inside the pinned 9.0.9 image.

## 3. Outline

- [ ] 3.1 Write `src/fenolite/backends/kicad/outline.py` (design Decision 3) and `tests/unit/backends/kicad/test_outline.py`, covering "Model outline", "Edge graphics with a cut-out" and "Open contour named", plus arcs (`exact == False`), a rectangle item and footprint-only edges. Proof: `uv run pytest tests/unit/backends/kicad/test_outline.py`.
- [ ] 3.2 Write `tests/corpus/test_outline_corpus.py::test_outlines` (`needs_corpus`) over the readable non-heavy demo boards, comparing with `pcb export stats` on 10.0.6 where a `kicad-cli` is present, and record the counts in `docs/evidence/kicad-board-read.md`. Proof: `uv run pytest tests/corpus/test_outline_corpus.py -rA` with the cached corpus.

## 4. Placement package

- [ ] 4.1 Write `src/fenolite/placement/{__init__,codes,legality}.py` (design Decisions 2, 5 and 6), with `TOUCHING_OVERLAPS` set from the committed probe files, and `tests/unit/placement/test_legality.py`, covering every scenario of "Placement legality", "Placement issue codes" and "Placement evidence", and a test that keeps `TOUCHING_OVERLAPS` equal to the probe files. Proof: `uv run pytest tests/unit/placement -k "legality or codes or evidence" tests/unit/test_import_graph.py`; `uv run pyright src`.
- [ ] 4.2 Write `src/fenolite/placement/grid.py` (design Decision 7) and `tests/unit/placement/test_grid.py`, covering every scenario of "Grid placement" plus a cut-out, a `--only` subset and a property test that no two placed boxes, grown by the gap, intersect. Proof: `uv run pytest tests/unit/placement -k grid`.

## 5. Command and build

- [ ] 5.1 Write `src/fenolite/cli/cmd_place.py` (design Decisions 8, 10 and 11) and `tests/unit/cli/test_place_cmd.py`, covering every scenario of "Place command" plus `--only`, a rotation through the project's library table, `place.locked`, `place.script-locked`, `place.copper-left` and two runs writing equal bytes; add `place` to `tests/unit/cli/test_check_readonly.py` for `--dry-run`. Add the `place` section and its issue table to `docs/cli-contract.md`, and complete `docs/placement.md`. Proof: `uv run pytest tests/unit/cli/test_place_cmd.py tests/unit/cli/test_hermetic_examples.py tests/consistency`.
- [ ] 5.2 Call the legality check from `lens.build.build_design`, add the `place.*` codes to `BUILD_ISSUE_CODES` and `result.placement` to `cmd_build` (design Decision 9). Extend `tests/unit/lens/` with the scenarios of "Placement legality in a build", and check that the blink's bytes are unchanged for both targets. Proof: `uv run pytest tests/unit/lens tests/unit/cli/test_build_cmd.py`; `uv run pytest tests/kicad/build -rA` on the local KiCad 10.0.6.

## 6. Oracle proofs

- [ ] 6.1 Write `tests/kicad/place/test_place_oracle.py` with `test_legality_matches_drc` and `test_placed_then_rebuilt` (scenarios "Legality matches DRC" and "Placed then rebuilt"). Proof: `uv run pytest tests/kicad/place -rA` on the local KiCad 10.0.6 and inside the pinned 9.0.9 image.

## 7. Closing

- [ ] 7.1 Run the residue and full test suites. Add a `LEGAL-ANNEX.md` row for every further ISO week in which `backends/` or `docs/formats/` changed. Proof: `uv run pytest tests/residue` and `uv run pytest -q` exit 0; `uv run python tools/residue/scan.py` exits 0; `uv run python tools/gen_schemas.py --check` exits 0 (model unchanged); `make check` passes; `openspec validate c0022-placement-grid --strict --no-interactive` passes; `gh pr checks` shows `kicad-9` and `kicad-10` passing.
- [ ] 7.2 Update the evidence labels from the results: `H-K-PLACE-MOVE` and `H-K-PLACE-TOUCH` become `KICAD-VERIFIED (9.0.x, 10.0.x)` with the run links, or are refuted with a `-2` successor and the fallback recorded; `H-G-PLACE-OUTLINE` becomes `CORPUS-VERIFIED` with its counts. `placement.EVIDENCE` is raised only as "Placement evidence" allows; the labels in `board.md` follow. Proof: `uv run pytest tests/unit/test_provenance.py tests/unit/test_hypotheses_register.py tests/unit/test_format_facts.py tests/unit/placement -k evidence`.
- [ ] 7.3 Add to `CHANGELOG.md` under Unreleased: "Placement: `fenolite place` puts staged parts on the board in a deterministic grid or moves named parts, a legality check reports courtyard overlaps and parts outside the outline in `build` and `place`, and a placed part is kept by later builds". Update `docs/roadmap.md` (c0022 state). Proof: `git diff CHANGELOG.md docs/roadmap.md`.
