## 1. Runner

- [ ] 1.1 `STAGES[4]` of `tools/yardstick.py` lists `route` before `route-pairs`; `routed_measures` reports the two route steps in that order; the comment of `_COMMANDS` says why (the maintainer's decision of 2026-10-09). Tests in `tests/unit/test_yardstick.py`: the order of the steps of stages 4 and 5 (`test_steps_of_stages_3_to_5`, `test_route_runs_before_the_pair`) and the passing run at stage 5 in that order. Proof: `uv run pytest tests/unit/test_yardstick.py -q -k "stages_3_to_5 or route_runs_before or passing_run_at_stage_5"`.
- [ ] 1.2 Check that the budgets and the ratchets do not depend on the order: `judge` and `rebase` key a budget by the step's name, and the ratchets come from `board.routed.drc`. Test `test_rebase_ignores_the_order_of_the_route_steps`: three stage-5 records in each order give the same budgets and ratchets, read back from `rebase`'s TOML. Proof: `uv run pytest tests/unit/test_yardstick.py -q -k rebase`.

## 2. Pages

- [ ] 2.1 `tools/README.md` (steps of the later stages), `tools/yardstick_budgets.toml` (the tables of stages 4 and 5 in step order), the comment of the `yardstick` job in `.github/workflows/nightly.yml`, and `docs/evidence/yardstick.md`: the stage-4 row of `Stages`, a note that run 37836196244 ran `route-pairs` first, and the proposal of "The routing gap of run 37836196244" marked as made by c0157, with the condition under which the order is measured again. Proof: `uv run pytest tests/unit/test_yardstick.py -q -k "page or budgets_file"`.

## 3. Closing

- [ ] 3.1 Run tests/residue. Proof: `uv run pytest tests/residue -q`.
- [ ] 3.2 Update evidence labels: none moves (seconds and counts of one runner move no label; `H-K-YARD-*` move on scheduled runs). Proof: `uv run python tools/gen_evidence_matrix.py --check`.
- [ ] 3.3 `CHANGELOG.md` under `[Unreleased]`, `### Changed` (a `Development:` entry); the decision as row 39 of "Open decisions" in `docs/roadmap.md`; the row of `openspec/README.md`. Proof: `make check-fast PYTEST_WORKERS=2`.
