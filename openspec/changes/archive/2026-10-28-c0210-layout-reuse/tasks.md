## 1. Layout reuse

- [x] 1.1 Add `reuse/fit.py` and `reuse/codes.py`, the import-graph row `reuse` and the bench `tests/_reusebench.py` (scenarios "A mirrored reference is found", "A mirrored footprint is suspected" and "A part without a fit"). Proof: `uv run pytest tests/unit/reuse/test_fit.py tests/unit/test_import_graph.py -q`.
  - 2026-10-28: proof passed (12 fit tests and the import-graph tests).
- [x] 1.2 Add `reuse/copper.py` and the settling glue `cli/reuse_copper.py` (scenarios "Nets and layers of the copy" and "Copper that ends nowhere is pruned"). Proof: `uv run pytest tests/unit/reuse/test_copper.py -q`.
  - 2026-10-28: proof passed (7 tests).
- [x] 1.3 Add `--strategy reuse` to `fenolite place` with `cli/place_reuse.py`, the codes and their `explain` entries, and the contract section (scenarios "Placement of a copied block", "Dry run of a block" and "Every code is explained"). Proof: `uv run pytest tests/unit/cli/test_place_reuse.py tests/unit/cli/test_place_cmd.py tests/unit/cli/test_explain_cmd.py tests/consistency -q`.
  - 2026-10-28: proof passed.
- [x] 1.4 Prove the written board with `kicad-cli` and register `H-G-REUSE-FIT` and `H-K-REUSE-DRC` (scenario "KiCad finds nothing new"). Proof: `uv run pytest tests/kicad/reuse -rA` with the local `kicad-cli`, and `uv run pytest tests/unit/test_hypotheses_register.py tests/unit/test_inferred_hypotheses.py -q`.
  - 2026-10-28: the case passed with local `kicad-cli` 10.0.7; the 9.0.9 side runs in the `kicad-9` job.
- [x] 1.5 Teach it: `docs/placement.md` "Layout reuse", the guide's `placement` and `board-floorplan` pages, the generated `commands` page; CHANGELOG; move the requirements and tasks out of c0175. Proof: `uv run python tools/gen_agent_guide.py`, `uv run pytest tests/unit/agent -q`, and `openspec validate c0210-layout-reuse --strict --no-interactive`.
  - 2026-10-28: proof passed.
- [x] 1.6 `make check-fast` and CI on the integrated head. Proof: `make check-fast` and the required jobs (`kicad-9` and `kicad-10` among them) green on the head that carries this change. Done 2026-10-28: `make check-fast` passed on the integrated head b0ca6b9 (14856 passed, 44 skipped); the fixes after it (corpus census pins, KiCad 9 probe scopes) passed their focused tests, and every CI job (unit on Ubuntu 3.11 to 3.13, macOS and Windows, kicad-9, kicad-10, routing on KiCad 9 and 10, mcp, viewer, wheel, dco) passed on `dev-c0225-c0227` at 171bb10 (run 40756504456).
