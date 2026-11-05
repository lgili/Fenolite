# c0402 design: deterministic work budget for the exact neck cut

## Context

c0332's exact cut (`geometry.boolean._exact_cut.exact_difference`) runs under one `Budget` per operation.
Its storage caps (`nodes`, `fragments`, `halfedges`, `faces`, `incidences`, `candidates`) and some work caps
(`comparisons`, `winding_visits`) count, but every loop also calls `Budget.check()`, which compared the wall
clock with `total_seconds=240` and `stage_seconds=120` and raised `ResourceLimit`, a `GeometryError`.
Several loops (noding, snap drawing, assembly, ring walks) are bounded by nothing else, and the number of
cells or groups of one cut is bounded only by that clock. On a busy CI runner, `vme-wren`'s DIFAT conversion
refused in `assembly` (dev run 41976474801, attempt 1); the same conversion passed seconds later.

## Decision

1. **Work units.** `Budget.check(units=1)` charges `units` to `_work` (whole operation) and `_stage_work`
   (reset by `stage()`). A loop that checks every 256 or 1024 iterations charges 256 or 1024; `visit(n)`
   charges `n`. The live modules (`_exact_noding`, `_exact_faces`, `_exact_snap`, `_exact_seed_index`,
   `_exact_cut`) charge this way; the unused c0332 modules charge one unit per call. Which checks run, and
   how often, depends only on the input, so the total is the same on every machine. (Python's hash of
   `int`, `Fraction` and tuples of them does not depend on `PYTHONHASHSEED`, so set and dict order is
   reproducible too.)
2. **Caps.** `Limits.work` and `Limits.stage_work` refuse with `ResourceLimit("exact geometry work budget
   exceeded during <stage>")`, the existing `GeometryError`/`FEN-3005`. All other caps are unchanged.
3. **Safety net.** The clock is still read at every check, after the work caps. Past `total_seconds` or
   `stage_seconds` it raises `ExactDeadline`, a `FenoliteError` with `cli_code = "FEN-1005"` (exit 1,
   `retryable` true) that is not a `GeometryError`. The pour's `except GeometryError` handlers (outline,
   offsets, board area) therefore never turn it into a different pour: the command stops before writing.
   The net is raised to 1200 s per operation and 600 s per stage, above the time the caps allow on the
   measuring machine (see "Sizing"), so on a healthy machine the caps always decide first.
4. **Kept from c0332.** One `Budget` per exact operation, shared by all its groups and cells; no floating
   fallback; every refusal before any write.

Rejected: a pure CPU-time deadline (`process_time`) still varies with the machine and the interpreter; a
cap per cell only (an operation with many cells would be unbounded); dropping the clock entirely (a
pathological loop that charges little work would never stop).

## Sizing

Measured on 2026-11-05 on the maintainer's Mac (Python 3.13), with the caps lifted, over the 162 distinct
operands captured from the 27 c0332 cases (public corpus only; captures and
`measure.py` kept outside the repository). Every cut finished; none refused.

| operand | edges | work units | largest stage (units) | winding visits | CPU s |
|---|---:|---:|---:|---:|---:|
| `vme-wren` largest (a88f5f79) | 465 907 | 139 180 774 | 4 011 930 | 8 878 501 | 101.5 |
| `vme-wren` (49d0f37f) | 421 846 | 128 445 204 | 3 601 307 | 8 330 564 | 101.6 |
| `vme-wren` (a8f3d96a) | 338 239 | 100 479 780 | 5 652 376 (winding) | 6 643 247 | 76.1 |
| `vme-wren` (fd90c826) | 338 105 | 100 390 478 | 5 636 812 | 6 633 900 | 77.4 |
| largest outside `vme-wren` (1f218b47) | 256 315 | 57 907 267 | 3 229 271 | 3 985 279 | 57.5 |

`vme-wren`'s 67 cuts hold every maximum (410 s of the 792 s CPU of all 162). The rate is 0.93 to 1.91
million units per CPU second.

- `WORK = 280_000_000`: twice the largest cut, rounded up; at the slowest measured rate about 300 s CPU.
- `STAGE_WORK = 25_000_000`: 4.4 times the largest stage, so that one group at the 100 000-edge input ceiling
  that no seam splits (twice the 50 000-edge cell target) still fits.
- Safety net `total_seconds = 1200`, `stage_seconds = 600`: four times the cap's time at the slowest rate, so
  only a machine more than four times slower than the measuring Mac can reach it.
- `winding_visits` (10 000 000) is unchanged; the largest cut uses 89 % of it.

## Risks

- A future input that needs more work than the cap refuses deterministically on every machine; the
  message names the stage. Raising the cap is a reviewed change with its own measurement.
- A machine more than about four times slower than the measuring Mac can reach the safety net before the
  cap: it gets a retryable `FEN-1005`, never a different result.
