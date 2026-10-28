## 0. Entry check

- [x] 0.1 Move package 7 from c0175 (its decision 7, its ADDED requirement "Coupling screen", the six kinds of its ADDED requirement "Practice checks" and its tasks 5.1 to 5.4, 5.8 and the kind `relief` of 5.5) into this change, and note the move in c0175's `tasks.md`; `necks`, `loops`, `balance` and `power --split` stay in c0175 under "Pour shape checks". Proof: `openspec validate c0204-practice-checks --strict --no-interactive` and `openspec validate c0175-board-engineering-tools --no-interactive`.
  - 2026-10-28: both pass. c0175 is validated without `--strict`: its other capabilities (`altium-edit`, `copper-tidy`, `layout-reuse` and others) already carry requirements over 500 characters; its `board-analyses` delta has none.

## 1. Practice checks

- [x] 1.1 Add `analysis/pour.py`: the copper states, the stale-fill test and the simulated pour (scenarios "A stale fill is simulated", "Saved, unfilled and too large", "The cells of an unfilled zone"). Proof: `uv run pytest tests/unit/analysis/test_practice.py -k "cutout or states" -q`.
  - 2026-10-28: proof passed (3 tests). The benches are authored in `tests/_practicebench.py`; `H-G-PRACTICE-POUR` registered.
- [x] 1.2 Add the kinds `connectivity` and `dead` (scenarios "A pin left open by a cut-out", "An island and far copper"). Proof: `uv run pytest tests/unit/analysis/test_practice.py -k "connectivity or dead or cutout" -q`.
  - 2026-10-28: proof passed (3 tests); `H-G-PRACTICE-GROUPS` and `H-G-PRACTICE-DEAD` registered.
- [x] 1.3 Add the kind `bodies` and the table `[[body_copper]]` (scenario "Copper of a class under a can"). Proof: `uv run pytest tests/unit/analysis/test_practice.py -k "bodies or tables" -q`.
  - 2026-10-28: proof passed (4 tests); `H-G-PRACTICE-BODIES` registered.
- [x] 1.4 Add the kind `decoupling` and the table `[[decoupling]]` (scenario "Decoupling distance reported without a finding"). Proof: `uv run pytest tests/unit/analysis/test_practice.py -k decoupling -q`.
  - 2026-10-28: proof passed (4 tests); `H-G-PRACTICE-DECOUPLING` registered.
- [x] 1.5 Add the kind `relief` (scenario "Four spokes of 0.5 mm"). Proof: `uv run pytest tests/unit/analysis/test_practice.py -k relief -q`.
  - 2026-10-28: proof passed (2 tests); `H-G-PRACTICE-RELIEF` registered.
- [x] 1.6 Add the kind `coupling` (scenario "A sense net beside a phase track"). Proof: `uv run pytest tests/unit/analysis/test_coupling.py -q`.
  - 2026-10-28: proof passed (5 tests); `H-G-PRACTICE-COUPLING` registered.
- [x] 1.7 Add the six codes to the table and to `fenolite explain` (scenario "Practice codes in the table"). Proof: `uv run pytest tests/unit/analysis/test_findings.py tests/unit/cli/test_explain_cmd.py -q`.
  - 2026-10-28: proof passed.
- [x] 1.8 Wire the six kinds and their options into `analyze`; document them in `docs/analyses.md` and `docs/cli-contract.md`; teach them on `board-practice`; regenerate the agent guide (scenario "Practice kinds through the command"). Proof: `uv run pytest tests/unit/cli/test_analyze_practice.py tests/unit/cli/test_analyze_power.py tests/unit/agent tests/unit/cli/test_explain_cmd.py tests/unit/test_inferred_hypotheses.py tests/unit/test_hypotheses_register.py tests/consistency -q`.
  - 2026-10-28: proof passed.
- [x] 1.9 `make check-fast`, CHANGELOG, and CI on the pushed commit. Proof: `make check-fast` and the required jobs green on the head of `c0204-practice-checks`. Done 2026-10-28: `make check-fast` passed on the integrated head (14366 passed, 41 skipped), and every CI job (unit on Ubuntu 3.11 to 3.13, macOS and Windows, kicad-9, kicad-10, routing on KiCad 9 and 10, viewer, wheel, dco) passed on `dev-c0204-c0209` at 01068dd (run 40703612332).
  - 2026-10-28: CHANGELOG written. `make check-fast` was not run in this session (the coordinator runs it with the parallel changes); CI waits for the push of the integrated branch.
