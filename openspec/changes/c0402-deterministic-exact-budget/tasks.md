## 1. Deterministic budget

- [x] 1.1 Charge counted work at every `Budget.check` (`units` for loops that check every 256 or 1024 steps,
  `n` for `visit(n)`) against the new `Limits.work` and `Limits.stage_work`; refuse with `ResourceLimit` when
  either is used up. Proof: `uv run pytest tests/unit/geometry/test_exact_budget.py -q`.
- [x] 1.2 Make wall time a safety net only: `ExactDeadline` (`FEN-1005`, retryable, not a `GeometryError`) past
  1200 s per operation or 600 s per stage; register `FEN-1005` in the CLI, `explain`, the CLI contract, the
  surface and the agent guide. Proof: `uv run pytest tests/unit/geometry/test_exact_budget.py
  tests/unit/cli/test_explain_cmd.py tests/unit/cli/test_cli_surface.py tests/unit/agent/test_pages.py -q`.
- [x] 1.3 Point the tests that advanced a fake clock past 240 s or 120 s at `ExactDeadline` past the net.
  Proof: the exact-geometry unit files (`tests/unit/geometry/test_exact_*.py`,
  `tests/unit/backends/altium/test_exact_refinement_proposal.py`) pass.

## 2. Sizing

- [x] 2.1 Count the work of every captured exact cut of the 27 c0332 cases, `vme-wren`'s included, and size
  `WORK` and `STAGE_WORK` with a margin. Proof: design.md "Sizing" table from
  `measure.py` over the captured operands (outside the repository; public corpus only).
  162 cuts, none refused; largest 139 180 774 units (`vme-wren`, 465 907 edges, 101.5 s CPU), largest stage
  5 652 376; `WORK = 280_000_000`, `STAGE_WORK = 25_000_000`.
- [x] 2.2 Show that the same input gives the same outcome under a slowed clock. Proof:
  `tests/unit/geometry/test_exact_budget.py` (same polygons and work at four times the former deadline; the
  same refusal at a cap one unit short; the net is `FEN-1005` and retryable).

## 3. Validation

- [x] 3.1 Focused checks of the touched files (coordinator rule of 2026-11-05: `make check-fast` runs once on
  the integrated batch). Proof: `ruff check`, `ruff format --check`, `pyright src` clean; one file at a time:
  every `tests/unit/geometry/test_exact_*.py`, `test_boolean_fallback.py`, the `tests/unit/backends/altium`
  pour, neck-cut and refinement files, `test_explain_cmd.py`, `test_cli_surface.py`, `test_errors.py`,
  `test_pages.py`, `test_build_bytes.py` (77 passed) and `tests/kicad/convert/test_triangle_large.py`
  (2 passed, 2 native skipped locally) all pass.
- [ ] 3.2 `make check-fast` on the integrated batch. Left to the coordinator.
- [ ] 3.3 CI on the exact commit, `kicad-10` included (`test_difat` and the other 26 cases). Left to the
  coordinator.
