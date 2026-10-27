## 0. Entry check

- [x] 0.1 Move package 3 from c0175 (its decision 3, its ADDED requirement "Barrier crossings" and its tasks 3.1 and 3.2) into this change, and note the move in c0175's `tasks.md`. Proof: `openspec validate c0199-barrier-crossings --strict --no-interactive`.

## 1. Barrier crossings

- [x] 1.1 Add `analysis/crossings.py` with the ways per layer and the demand (scenarios of "Barrier crossings" and "Crossing ways and demand"). Proof: `uv run pytest tests/unit/analysis/test_crossings.py -q`.
  - 2026-10-26: proof passed (8 tests: the hand count of the row, 20 against 14 with `B.Cu` forbidden, a routed track that is demand and obstacle, a cut beyond the board edge, the clearance option, the level without pads).
- [x] 1.2 Add `analysis.crossings-short` to the table and to `fenolite explain` (scenario "Crossings code in the table"). Proof: `uv run pytest tests/unit/analysis/test_findings.py tests/unit/cli/test_explain_cmd.py -q`.
  - 2026-10-26: proof passed (23 tests).
- [x] 1.3 Wire the kind `crossings` and its options into `analyze`; document it in `docs/analyses.md` and `docs/cli-contract.md`; teach it on the agent guide's floor-plan page and regenerate the guide. Proof: `uv run pytest tests/unit/cli/test_analyze_crossings.py tests/unit/cli/test_analyze_power.py tests/consistency tests/unit/agent -q`.
  - 2026-10-26: proof passed (536 passed, 24 skipped). The command test writes the bench as a KiCad board and passes `--clearance`, as a board read without its project file holds no class clearance.
- [x] 1.4 `make check-fast`, CHANGELOG, and CI on the pushed commit. Proof: `make check-fast` and the required jobs green on the head of `c0199-barrier-crossings`.
  - 2026-10-26: `make check-fast` passed (14,025 passed, 34 skipped). CI on the pushed head is recorded below.
  - 2026-10-27: CI run 40417517668 on `462bb36`: every job green.
