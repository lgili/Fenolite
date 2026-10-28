## 0. Entry check

- [x] 0.1 Move the rest of package 7 from c0175 (its tasks 5.5 except `relief`, 5.6 and 5.7, and its ADDED requirement "Pour shape checks") into this change, and note the move in c0175's `tasks.md`. Proof: `openspec validate c0213-pour-shapes --strict --no-interactive` and `openspec validate c0175-board-engineering-tools --no-interactive`.
  - 2026-10-28: both pass; c0175 without `--strict`, as c0204 recorded (its other capabilities carry requirements over 500 characters). Its `board-analyses` delta keeps only the MODIFIED "Analyze command".

## 1. Pour shapes

- [x] 1.1 Add the tables `[[neck]]` and `[[loop]]` to the requirements file (scenario "The two tables load"). Proof: `uv run pytest tests/unit/analysis/test_shapes.py -k tables -q`.
  - 2026-10-28: proof passed (1 test).
- [x] 1.2 Add `analysis/shapes.py` with the widths on the raster and the kind `necks` (scenarios "A neck of a pour", "Neck rows missing or unmatched", "A finger and a strip"). Proof: `uv run pytest tests/unit/analysis/test_shapes.py -k "necks or tips" -q`.
  - 2026-10-28: proof passed (3 tests). The benches are authored in `tests/_shapebench.py`; `pour.window_cells` added; `H-G-SHAPE-NECK` registered.
- [x] 1.3 Add the kinds `loops` and `balance` (scenarios "Two decoupling loops", "A pad on a pour and a pad on a track"). Proof: `uv run pytest tests/unit/analysis/test_shapes.py -k "loops or balance" -q`.
  - 2026-10-28: proof passed (3 tests); `practice.copper_path` gives the legs; `H-G-SHAPE-LOOP` and `H-G-SHAPE-BALANCE` registered.
- [x] 1.4 Add `analysis/split.py`, the resistive solve of `--kinds power --split`, bracketed by the interval of `power` on the same benches (scenarios "Two strips share by thickness", "Vias in parallel"). Proof: `uv run pytest tests/unit/analysis/test_power_split.py -q`.
  - 2026-10-28: proof passed (4 tests, 5 s). The raster of `two_strips()` lies in `power`'s interval to the microohm; on `branch()` the solve lies below it, because `power` counts the track inside the pads (design, decision 7, and the module's docstring). `H-G-POWER-SPLIT` registered.
- [x] 1.5 Add the two codes to the table and to `fenolite explain` (scenario "Pour shape codes in the table"). Proof: `uv run pytest tests/unit/analysis/test_findings.py tests/unit/cli/test_explain_cmd.py -q`.
  - 2026-10-28: proof passed (26 tests).
- [x] 1.6 Wire the three kinds, `--split` and `--loop-baseline` into `analyze`; document them in `docs/analyses.md` and `docs/cli-contract.md`; register the hypotheses and regenerate the evidence matrix; teach them on `board-power`; regenerate the agent guide (scenario "Pour shape kinds through the command"). Proof: `uv run pytest tests/unit/cli/test_analyze_shapes.py tests/unit/cli/test_analyze_practice.py tests/unit/test_inferred_hypotheses.py tests/unit/test_hypotheses_register.py -q` and `uv run pytest tests/unit/agent tests/consistency -q -n 2`.
  - 2026-10-28: proof passed (both commands; the agent and consistency suites with 607 passed, 30 skipped). `docs/evidence/matrix.md` regenerated unchanged (it lists no `H-G-` row); `commands.md` is 592 lines (two flags added). `tests/unit/cli/test_analyze_power.py` lists the three new kinds; the console example of `--split` in `docs/analyses.md` gives no resistivity, as `test_facts_page.py` asks.
- [x] 1.7 `make check-fast`, CHANGELOG, and CI on the pushed commit. Proof: `make check-fast` and the required jobs green on the head of the integrated branch. Done 2026-10-28: `make check-fast` passed on the integrated head b0ca6b9 (14856 passed, 44 skipped); the fixes after it (corpus census pins, KiCad 9 probe scopes) passed their focused tests, and every CI job (unit on Ubuntu 3.11 to 3.13, macOS and Windows, kicad-9, kicad-10, routing on KiCad 9 and 10, mcp, viewer, wheel, dco) passed on `dev-c0225-c0227` at 171bb10 (run 40756504456).
  - 2026-10-28: CHANGELOG written. `make check-fast` was not run in this session (the coordinator runs it with the parallel changes); CI waits for the push of the integrated branch.
