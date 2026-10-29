## 1. Region renders

- [x] 1.1 Let `connectivity()` take `pour=`: the copper of `analysis.pour`, with the items one island of a simulated pour covers joined (design decision 6). Proof: `uv run pytest tests/unit/analysis/test_region_render.py tests/unit/analysis/test_connectivity.py tests/unit/analysis/test_crossings.py tests/unit/analysis/test_practice.py -q`.
  - 2026-10-28: proof passed (71 tests). On the ground bench unfilled, the saved copper leaves `GND` open and the pour closes it, at `POUR_EVIDENCE`.
- [x] 1.2 Add `analysis/region.py`: the SVG of a region with its copper in its state, holes, slots, edge, grid, net labels, open connections and cut overlay (requirements "Region render elements" and "Region render copper"). Proof: `uv run pytest tests/unit/analysis/test_region_render.py -q`.
  - 2026-10-28: proof passed (6 tests).
- [x] 1.3 Add `render --region` with `--nets`, `--open`, `--grid`, `--cut`, `--cut-width`, `--cut-clearance`, `--manifest`, and the codes `render.region-empty` and `render.copper-simulated` (requirements "Region renders", "Region render cut overlay" and "Region render refusals"). Proof: `uv run pytest tests/unit/cli/test_render_region.py tests/unit/cli/test_render_cmd.py tests/unit/exports/test_plan.py -q`.
  - 2026-10-28: proof passed (38 tests: 14 of the region, the whole-side render tests and the code table). A way of the crossing analysis is rounded inward to the nanometre, so the first way of the row ends at 11.839999 mm.

## 2. Documents and teaching

- [x] 2.1 Register `H-G-REGION-RENDER`, add the two codes to `explain.toml`, document "Region renders" in `docs/cli-contract.md` and `docs/exports.md`, teach `--region` on the guide's `fabrication` page and regenerate the guide (`tools/gen_agent_guide.py`) and the evidence matrix (`tools/gen_evidence_matrix.py`), and add the CHANGELOG entry. In c0175, replace task 12.4 with the move note and remove "Region renders" from its `manufacturing-exports` delta. Proof: `uv run pytest tests/unit/agent tests/unit/cli/test_explain_cmd.py tests/unit/test_inferred_hypotheses.py tests/unit/test_hypotheses_register.py tests/unit/test_import_graph.py tests/consistency -q` and `openspec validate c0211-region-renders --strict --no-interactive`.
  - 2026-10-28: proof passed (698 passed, 30 skipped), and `openspec validate c0211-region-renders --strict` reports the change valid. `tests/unit/exports/test_plan.py` learns the two codes; regenerating the evidence matrix also adds the rows `resave` and `merge` that c0207 left out of the page. c0175 keeps the length warnings of its other deltas, which predate this change.

## 3. Validation

- [x] 3.1 `make check-fast` on the integrated head, and the required CI jobs green on it. Proof: `make check-fast` and the required jobs green on the head that holds this change. Done 2026-10-28: `make check-fast` passed on the integrated head b0ca6b9 (14856 passed, 44 skipped); the fixes after it (corpus census pins, KiCad 9 probe scopes) passed their focused tests, and every CI job (unit on Ubuntu 3.11 to 3.13, macOS and Windows, kicad-9, kicad-10, routing on KiCad 9 and 10, mcp, viewer, wheel, dco) passed on `dev-c0225-c0227` at 171bb10 (run 40756504456).
