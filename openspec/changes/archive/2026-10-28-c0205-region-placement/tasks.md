## 1. Region placement

- [x] 1.1 Add `placement/regions.py` (`split`, `band_order`, `boundary`, `place_regions`, `region_of`) and register `H-G-REGION-PLACE` (scenarios of "Region placement" and "Region bands"). Proof: `uv run pytest tests/unit/placement/test_regions.py tests/unit/placement/test_grid.py tests/unit/test_inferred_hypotheses.py tests/unit/test_hypotheses_register.py -q`.
  - 2026-10-28: proof passed (6 region tests, 8 grid tests, 41 hypothesis tests); `H-G-REGION-PLACE` registered.
- [x] 1.2 Add the three codes to the table, to `docs/cli-contract.md` and to `fenolite explain` (scenario "Region codes in the table"). Proof: `uv run pytest tests/unit/placement/test_place_codes.py tests/unit/cli/test_explain_cmd.py -q`.
  - 2026-10-28: proof passed.
- [x] 1.3 Wire `--strategy regions` into `place` with `cli/place_regions.py`, sharing the grid's box building (scenarios of "Region strategy in the place command" and "Region report"). Proof: `uv run pytest tests/unit/cli/test_place_regions.py tests/unit/cli/test_place_cmd.py tests/unit/cli/test_place_constrained.py tests/unit/test_import_graph.py -q`.
  - 2026-10-28: proof passed, with `tests/unit/placement` and `test_build_placement_guard.py`: 162 passed; `test_hermetic_examples.py` 47 passed.
- [x] 1.4 Document the strategy in `docs/placement.md` ("Regions") and `docs/cli-contract.md` ("Region placement"); teach it on `board-floorplan`; regenerate the guide. Proof: `uv run python tools/gen_agent_guide.py` and `uv run pytest tests/unit/agent tests/consistency -q`.
  - 2026-10-28: guide regenerated; `tests/unit/agent`, `test_explain_cmd.py`, the two hypothesis tests, the import graph and `tests/consistency`: 609 passed, 27 skipped.

## 2. Closing

- [x] 2.1 Residue and static checks on the changed files. Proof: `uv run ruff check`, `uv run ruff format --check`, `uv run pyright src` and `uv run python tools/residue/scan.py`.
  - 2026-10-28: ruff check and format clean on the tree, pyright 0 errors, residue 0 hits.
- [x] 2.2 Evidence labels: `INFERRED` (`H-G-REGION-PLACE`) on every region reply. Proof: `uv run pytest tests/unit/cli/test_place_regions.py -k islands -q`.
  - 2026-10-28: proof passed; the level is `INFERRED` with `H-G-REGION-PLACE` and `H-G-TIES`.
- [x] 2.3 CHANGELOG `## [Unreleased]` `### Added`, and the README row of the change. Proof: `~/.npm/_npx/20f2b75ddc8bce88/node_modules/.bin/openspec validate c0205-region-placement --strict --no-interactive`.
  - 2026-10-28: the change is valid.
- [x] 2.4 `make check-fast` and CI on the integrated commit (the coordinator runs them; this run was told not to). Proof: `make check-fast` and the required jobs green on the head that holds this change. Done 2026-10-28: `make check-fast` passed on the integrated head (14366 passed, 41 skipped), and every CI job (unit on Ubuntu 3.11 to 3.13, macOS and Windows, kicad-9, kicad-10, routing on KiCad 9 and 10, viewer, wheel, dco) passed on `dev-c0204-c0209` at 01068dd (run 40703612332).
