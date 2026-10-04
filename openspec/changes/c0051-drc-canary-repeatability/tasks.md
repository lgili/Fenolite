## 1. Measure and record

- [x] 1.1 Register `H-K-DRC-LIMIT`, `H-K-DRC-REPEAT` and `H-K-CHECK-CANARY-3` in `docs/hypotheses.md` (the rows of design.md, result `pending`), mark `H-K-CHECK-CANARY-2` refuted and superseded with the stress measurement, and add a paragraph for this change. Write the sections "DRC repeatability on the demo boards (change c0051)" and "Clearance report limit (change c0051)" of `docs/evidence/kicad-check.md` with the 10.0.6 macOS table, the stress table, the bench table, the method, the conditions and the `--all-track-errors` table of design.md. Proof: `uv run pytest tests/unit/test_hypotheses_register.py tests/unit/verify -q`.
- [x] 1.2 Run the 15-pair measurement in the pinned 10.0.6 image (`docker:kicad/kicad@sha256:18693567…`, already present; no pull) and add its table to the evidence section. If a board or a type outside the named sets differs, add it to design.md Decision 3, to the spec delta and to the register row before task 3.1. Proof: the section holds a table headed "kicad-cli 10.0.6, pinned Linux image"; `uv run pytest tests/unit/test_hypotheses_register.py -q`.
- [x] 1.3 Run it in the pinned 9.0.9 image (already present; no pull) on the boards 9.0 loads and add its table, or record it as an open row with the reason if the run cannot finish. The label of `H-K-DRC-REPEAT` stays `(10.0.x)` unless 9.0.9 agrees. Proof: the section holds a table or an open row headed "kicad-cli 9.0.9, pinned Linux image".

## 2. The limit and the verdict

- [x] 2.1 Add `CLEARANCE_REPORT_LIMIT`, `clearance_saturated` and the reason `clearance-limit` to `src/fenolite/backends/kicad/canary.py`; make `KicadOracle.drc` give `inconclusive` / `clearance-limit` for a saturated canary report without the pair (design Decision 5), on the two-run and the one-run path; cite `H-K-CHECK-CANARY-3` in `oracle.EVIDENCE` and the texts. Unit tests in `tests/unit/backends/kicad/test_canary.py` and `test_oracle.py` (fake `kicad-cli`: 499 and 498 `clearance` violations without the pair). Covers "A saturated report gives no verdict". Proof: `uv run pytest tests/unit/backends/kicad/test_canary.py tests/unit/backends/kicad/test_oracle.py tests/unit/checks tests/unit/cli/test_check_cmd.py -q`.
- [x] 2.2 Write `tests/kicad/check/_limitbench.py` and `tests/kicad/check/test_drc_limit.py`. Covers "The count stops near 499" and "A saturated board never reads as rules not loaded". Proof: `uv run pytest tests/kicad/check/test_drc_limit.py -q` on the local 10.0.6, and with `FENOLITE_KICAD_CLI=docker:kicad/kicad@sha256:e638b79b…` (9.0.9, already present); record both in the register row of `H-K-DRC-LIMIT`.

## 3. The comparison and the test

- [x] 3.1 Write `tests/_drcrepeat.py` (`UNREPEATABLE_TYPES`, `UNREPEATABLE_BOARDS`, `canonical`, `repeat_problems`) and `tests/unit/test_drc_repeat.py` with the cases of design Decision 4 and the record guard. Covers "A difference outside the named sets fails" and "The named sets match the record". Proof: `uv run pytest tests/unit/test_drc_repeat.py -q -k "problems or record"`.
- [x] 3.2 Change `tests/kicad/check/test_canary.py::test_two_run_demo_boards` to run `KicadOracle.drc` twice and assert `repeat_problems(item.id, first, second) == []`, keeping `canary_removed` = 0 and no canary uuid for both. Covers "Two runs on large boards", "A stable board repeats exactly", "A named board repeats outside the named types" and "A board whose DRC report the tool does not repeat". Proof: `uv run pytest tests/kicad/check/test_canary.py -q` passes 15 times in a row on the local `kicad-cli` 10.0.6 (a loop that stops at the first failure); record the 15 results in the register row.

## 4. The promise to users

- [x] 4.1 Add the reason `clearance-limit` to "Rules canary" and the paragraph "Repeatability" under `check` in `docs/cli-contract.md`; add the reason, the limit and the fact rows to "Check canary" in `docs/formats/kicad/drc.md`; add the contract guard to `tests/unit/test_drc_repeat.py`. Covers "The contract names what does not repeat". Proof: `uv run pytest tests/unit/test_drc_repeat.py -q -k contract`; `uv run pytest tests/consistency -q`.

## 5. Closing

- [x] 5.1 Run the fast gate and the residue tests. Proof: `make check-fast`; `openspec validate c0051-drc-canary-repeatability --strict`.
- [x] 5.2 Evidence labels: set the level and result of the three new rows from tasks 1.1 to 3.2; confirm that `oracle.EVIDENCE` keeps its level. Proof: `uv run pytest tests/unit/test_hypotheses_register.py tests/unit/backends/kicad/test_oracle.py -q -k "register or evidence"`.
- [x] 5.3 Add to `CHANGELOG.md` under `## [Unreleased]`, section "Fixed": one line on the false `rules-not-loaded`, the limit, the two-run test and the narrowed determinism promise of `check`. Proof: `grep -n "c0051" CHANGELOG.md`.
