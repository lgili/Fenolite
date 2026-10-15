## 0. Entry check

- [x] 0.1 Read `openspec list` and the living `copper-check`, `backend-protocol`, `copper-rule-explanation`, `verification-loop`, `board-analyses` and `kicad-oracle` specs. Write under this task, with the date: that c0167 is archived or its outline lowering and fixture are on the branch (else stop); whether c0168 is archived (the Altium frame then gives cut-out regions); whether another open change holds a delta of "Copper stage issue codes" (regenerate the MODIFIED block from the living text if one was archived); the maintainer's answers to the open questions. Proof: `openspec validate c0169-edge-clearance-check --strict --no-interactive` passes.
  - 2026-10-15, on `origin/dev` at `e6c42a8`: c0167 is not archived (16 of 18 tasks; 1.2 and 4.4 wait for the CI jobs), and its outline lowering (`model.outline.outline_items`, `geometry.rings.merge_rings`, `backends/kicad/_lowering.py`) and the shared fixture `tests/data/slots/design.py` are on the branch, so this change goes on. c0168 is not archived (0 of 19 tasks): the Altium frame gives the board outline of the import only. The open change c0114 (complete, not archived) holds a MODIFIED delta of "Copper stage issue codes" (the `info` severity of a waived finding and the Altium copper guard), whose code is on `dev`; no change was archived over the living text, but this change's MODIFIED block now copies c0114's text and adds its three rows, so the requirement keeps both whichever change is archived first. The maintainer's answers of 2026-10-15 are those of "Open questions" in `design.md` (every recommended answer). `openspec validate c0169-edge-clearance-check --strict --no-interactive`: valid.

## 1. Register and probes

- [x] 1.1 Add `H-K-EDGE-CENTRE`, `H-K-EDGE-RESOLVE` and `H-K-EDGE-AGREE` to `docs/hypotheses.md` (level `INFERRED`, the measurement of 2026-10-15 as the first record of the first) and the fact of the edge line to `docs/formats/kicad/drc.md` with S-0020 and S-0029. Proof: `uv run pytest tests/unit/test_hypotheses_register.py tests/unit/test_provenance.py tests/unit/test_format_facts.py -q`.
  - 2026-10-15: three rows added after `H-G-RING-UNION`, each `INFERRED`; `H-K-EDGE-CENTRE` carries the measurement of 2026-10-15 as its first record. `docs/formats/kicad/drc.md` gains the section "Copper to edge clearance (c0169)" with the edge line and the 0.5 mm default (S-0020, S-0029, `INFERRED` until the probes hold). The proof passes (66 tests).
- [ ] 1.2 Write the probes `edge-centre-*` and `edge-resolve-*` (an `edge_clearance` rule of 0.3 mm and of 0.8 mm, each with the project minimum of 0.5 mm, on a pad at 0.4 mm and at 0.7 mm) in `tests/kicad/checks/_edgebench.py`; record them on both majors. An outcome that differs from `design.md` stops this task. Proof: `uv run pytest tests/kicad/checks/test_edge_clearance.py -k "centre or resolve" -rA` in the pinned 9.0.9 and 10.0.6 images; `uv run pytest tests/kicad/test_probe_results.py -q`.
  - 2026-10-15: `tests/kicad/checks/_edgebench.py` builds the centre board (slot `S1`, five plated hole parts 0.47 to 0.6 mm from its edge) and the two resolve boards (rules files of 0.3 and 0.8 mm beside the template's 0.5 mm, parts at 0.4 and 0.7 mm); the nine probes `edge-centre-*` and `edge-resolve-*` are recorded in `docs/evidence/kicad/probes/10.0.6.json` and `9.0.9.json` with equal outcomes on both majors, as `design.md` says (a board-wide rule governs below and above the minimum: `edge_floor_over_rules` false). `uv run pytest tests/kicad/checks/test_edge_clearance.py -k "centre or resolve" -rA` passes (4 tests) with `FENOLITE_KICAD_CLI=docker:kicad/kicad:10.0.6` and `docker:kicad/kicad:9.0.9`. The full `tests/kicad/test_probe_results.py` drifts locally on environment probes: that gate is owed to the kicad CI jobs, so the task stays open.

## 2. Frame and resolver

- [ ] 2.1 Add `EdgeRing`, `BoardFrame.board_edges`, `DesignRules.min_edge_clearance` and `edge_floor_over_rules`, and implement them for KiCad (from `outline_items` and `merge_rings`, else `edge_outline`) and Altium (scenario "Edges of a read KiCad board"). Proof: `uv run pytest tests/unit/backends/kicad/test_frame_edges.py tests/unit/backends/altium -q`.
- [ ] 2.2 Write `ClearanceResolver.edge` with the switch of task 1.2 and route `edge_clearance_in_force` through it; stitching keeps its results. Proof: `uv run pytest tests/unit/checks/test_clearance.py tests/unit/backends/kicad/test_copper_stitch.py -q`.

## 3. Findings

- [ ] 3.1 Judge the edge pair and give `copper.edge-clearance` with its explanation (scenarios "A pad near a slot", "A rule for one net", "Rule over the board minimum"); add the codes, `explain.toml` entries and `recovery` rows. Proof: `uv run pytest tests/unit/checks/test_copper_edges.py tests/unit/checks -k "edge or codes" tests/unit/agent/test_pages.py -q`.
- [ ] 3.2 Build the bench of "Edge clearance agrees with KiCad" and record `H-K-EDGE-AGREE` on both majors. Proof: `uv run pytest tests/kicad/checks/test_edge_clearance.py -rA` in both pinned images.
- [ ] 3.3 Run the copper guard on every example and committed board; move copper of an example that is too close to its edge (never waive it) and write what moved here. Proof: `uv run pytest tests/unit/cli/test_hermetic_examples.py tests/unit/agent -q`.
- [ ] 3.4 Give `copper.hole-in-cutout` and `copper.hole-overlap` (scenarios "A via drilled into a slot", "Two drilled slots in an L"). First item of the cut order for the overlap. Proof: `uv run pytest tests/unit/checks/test_copper_holes.py -q`.

## 4. Creepage

- [ ] 4.1 Write the creepage equality tests (scenario "Slot and ring are equal") and the L against its hand-drawn merged ring; document slots in `docs/analyses.md` ("Creepage", "Grooves"). Proof: `uv run pytest tests/unit/analysis/test_creepage_slots.py -q`.

## 5. Closing

- [ ] 5.1 Document the edge pair, its limit and explanation and the two hole findings in `docs/copper-rule-explanations.md` and `docs/cli-contract.md`. Proof: `uv run pytest tests/consistency -q`.
- [ ] 5.2 Run the residue scan and the fast checks. Proof: `uv run python tools/residue/scan.py` exits 0; `make check-fast` passes.
- [ ] 5.3 Update the evidence labels: the three rows hold their measured levels; `checks.copper.EVIDENCE` names `H-K-EDGE-AGREE`; `uv run python tools/gen_evidence_matrix.py`. Proof: `uv run pytest tests/unit/test_hypotheses_register.py tests/unit/test_evidence_matrix_page.py -q`.
- [ ] 5.4 Add to `CHANGELOG.md` under `## [Unreleased]`: copper-to-edge clearance in `check` and the build guard, the two hole findings, the creepage of slots, and that existing boards may gain findings. Proof: `grep -n "copper.edge-clearance" CHANGELOG.md`; `openspec validate c0169-edge-clearance-check --strict --no-interactive` passes.
