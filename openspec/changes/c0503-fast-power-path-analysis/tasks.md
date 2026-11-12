# Tasks: c0503-fast-power-path-analysis

Rules for every task:

- The field board is private. Nothing from it (names, nets, designators, coordinates, rules, files) goes
  into tests, fixtures, commits or messages. Every bench is authored for Fenolite in `tests/_power.py`.
- Run each touched test file alone with `-n 0`; timing runs and anything heavier go through
  `~/.local/bin/fenolite-heavy`, one at a time.

## 1. Bench and baseline

- [ ] 1.1 Add `plane_board(holes, *, round=False)` to `tests/_power.py` (design D1's bench; round holes are
  polygonised with `ARC_TOL_NM`) and `tests/unit/analysis/test_power_speed.py` (marked `slow`) that times
  `analyze_power` and `analyze_split` and prints the times. Record the times before any change for 48 square
  holes and for 300 round holes with a 600 s cap, in the task note.
  - Proof: `~/.local/bin/fenolite-heavy uv run --extra dev pytest tests/unit/analysis/test_power_speed.py -m slow -q -n 0 -s`

## 2. Power bounds

- [ ] 2.1 `analysis/deadline.py` (`Deadline` with an injectable clock) and `analysis.deadline` in
  `analysis/codes.py` and `explain.toml`.
  - Proof: `uv run --extra dev pytest tests/unit/analysis/test_power_deadline.py -k clock tests/unit/cli/test_explain_cmd.py -q -n 0`
- [ ] 2.2 Staged region bounds in `power._region_element` and `_bounds` (design D2); tests "Bounds contain the
  exact interval" and "No deadline, no change".
  - Proof: `uv run --extra dev pytest tests/unit/analysis/test_power_stages.py tests/unit/analysis/test_power.py tests/unit/analysis/test_power_benches.py -q -n 0`
- [ ] 2.3 Indexed visibility in `surface._Board.allowed` (design D3); the creepage and surface tests give the
  same answers.
  - Proof: `uv run --extra dev pytest tests/unit/analysis/test_surface.py tests/unit/analysis/test_surface_bridges.py tests/unit/analysis/test_creepage_slots.py -q -n 0`
- [ ] 2.4 The deadline in `analyze_power` (design D5); test "A cut run is sound".
  - Proof: `uv run --extra dev pytest tests/unit/analysis/test_power_deadline.py -k sound -q -n 0`

## 3. Split on a mesh

- [ ] 3.1 `analysis/mesh.py`: the balanced quadtree and its conductances (design D4); test "Fewer cells than the
  raster".
  - Proof: `uv run --extra dev pytest tests/unit/analysis/test_mesh.py -q -n 0`
- [ ] 3.2 The coarse-to-fine solve in `analysis/split.py` and the deadline there; scenarios of "Current split" and
  "A cut split keeps a coarse level".
  - Proof: `uv run --extra dev pytest tests/unit/analysis/test_power_split.py tests/unit/analysis/test_power_deadline.py -q -n 0`
- [ ] 3.3 Accuracy against the old raster and the oracle: on `strip`, `dumbbell`, `split4`, `two_strips` and
  `via_array`, the mesh resistance lies within 2 % of `fdm_resistance` and each share within 10 permille of the
  raster solve of this change's parent commit (values recorded in the test).
  - Proof: `uv run --extra dev pytest tests/unit/analysis/test_mesh.py -k accuracy tests/unit/analysis/test_power.py -k fdm -q -n 0`

## 4. Time budget

- [ ] 4.1 Scenario "The plane bench in budget": both rows complete, `analyze_power` under 20 s and `analyze_split`
  under 60 s on the CI unit runner. Record the local and the CI times and the speed-up over task 1.1 in the
  task note.
  - Proof: `~/.local/bin/fenolite-heavy uv run --extra dev pytest tests/unit/analysis/test_power_speed.py -m slow -q -n 0 -s`
  - Proof (CI): the unit job of `ci-complete` on the exact commit passes `test_power_speed.py` and prints both times

## 5. Pending edits

- [ ] 5.1 `fenolite.api.analyze_power` and `analyze_split` on a `Board`, a path or a `Session` (design D6;
  needs c0501 task 1.1); test "A fix checked before it is committed".
  - Proof: `uv run --extra dev pytest tests/unit/api/test_power_api.py -q -n 0`
- [ ] 5.2 `--deadline` and `--after-plan` in `cmd_analyze.py`; tests "Analyze a planned route before writing it"
  and "A stale plan"; the read-only test of `analyze` stays green.
  - Proof: `uv run --extra geo --extra dev pytest tests/unit/cli/test_analyze_cmd.py -q -n 0`
- [ ] 5.3 Regenerate the schemas for `complete`, `cell_nm` and the new inputs.
  - Proof: `uv run python tools/gen_schemas.py --check && uv run python tools/model_review.py --check`

## 6. Docs, guide, changelog

- [ ] 6.1 `docs/analyses.md`, "Power paths" (stages, mesh, deadline, measured times); `docs/cli-contract.md`,
  "analyze" (`--deadline`, `--after-plan`, `analysis.deadline`); `docs/api.md` (`analyze_power`,
  `analyze_split`).
  - Proof: `uv run --extra dev pytest tests/unit/api/test_run_api.py -k page -q -n 0`
- [ ] 6.2 Teach `--deadline`, `--after-plan` and `analysis.deadline` on the agent guide page `board-power.md`, then
  regenerate the guide.
  - Proof: `uv run python tools/gen_agent_guide.py --check && uv run --extra dev pytest tests/unit/agent/test_pages.py -q -n 0`
- [ ] 6.3 Add the change to `CHANGELOG.md` under `## [Unreleased]` and run `make check-fast`.
  - Proof: `make check-fast`
