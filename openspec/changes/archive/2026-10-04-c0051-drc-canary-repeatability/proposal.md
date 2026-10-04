## Why

`tests/kicad/check/test_canary.py::test_two_run_demo_boards` fails now and then in the `kicad-10`
job, a merge and release gate. Measured on 2026-10-04, `kicad-cli` 10.0.6 (design.md):

- **The failure has one cause.** `kicad-cli` stops reporting `clearance` violations near 499 per
  run. On a board with more, the check canary's own violation competes for a place and is
  sometimes left out: 4 of 110 canary runs on `kicad-demo-10-0-6-pcb-01` and `-13`, the two demo
  boards with 499 `clearance` violations; never on a board below the limit. An authored bench
  reproduces it on 10.0.6 and 9.0.9.
- **It is a product fault.** A missing canary reads as `absent`, so `fenolite check` reports
  `kicad.drc.rules-not-loaded` (an error on a built project) for rules that were loaded.
- **Otherwise two DRC runs differ in a bounded way.** The report order differs on 10 of the 21
  boards. On 6 boards the content differs, only in entries of the types `clearance`,
  `hole_clearance` and `unconnected_items`. No other type differed in 30 runs per board.
- **The spec promises more than KiCad gives.** "Check output is deterministic" says two
  `fenolite check --json` runs are byte-identical apart from `elapsed_ms`.

## What Changes

- **A saturated report gives no verdict.** When the canary run's report holds no canary pair and
  at least `CLEARANCE_REPORT_LIMIT = 499` `clearance` violations, the canary state is
  `inconclusive` with the new reason `clearance-limit` (`kicad.drc.rules-unchecked`, a warning),
  not `absent`. Below the limit nothing changes. The oracle does not repeat the run.
- **Hypotheses.** `H-K-DRC-LIMIT` (the limit) and `H-K-DRC-REPEAT` (what two runs share) are
  registered. `H-K-CHECK-CANARY-2` is refuted by its own criterion; `H-K-CHECK-CANARY-3` adds the
  limit.
- **A bench proves the limit on both majors** (`tests/kicad/check/test_drc_limit.py`, authored
  board): the count stops near 499, and a saturated board never reads as `absent`.
- **The two-run test compares two runs** of `KicadOracle.drc` per board:
  - the canary state must be `fired`; `clearance-limit` is accepted only on a saturated report;
  - on the 15 stable boards the whole sorted report must be equal;
  - on the 6 named boards every entry outside the three named types must be equal;
  - the return code and the tool's written files must be equal.
  Any other difference fails and names the board and the type. No retry, skip or flaky marker.
  The comparing helper has unit tests of its own.
- **The determinism promise says what holds** (`verification-loop`, `docs/cli-contract.md`).

## Capabilities

- `kicad-oracle`: MODIFIED "Check canary injection"; ADDED "Clearance report limit" and "DRC
  repeatability on the demo boards".
- `verification-loop`: MODIFIED "Check output is deterministic".

## Non-goals

- No repeat of the canary run to get another answer.
- No `--all-track-errors` in the DRC call: it changes every count users see (design.md).
- No new issue code, and no change to RT2.
- No verdict on a saturated board: the user is told it is unknown.

## Evidence level required

- `H-K-DRC-LIMIT` and `H-K-CHECK-CANARY-3`: `KICAD-VERIFIED (9.0.x, 10.0.x)`, by the bench on
  10.0.6 (local) and in the pinned 9.0.9 image, before the oracle relies on them.
- `H-K-DRC-REPEAT`: `KICAD-VERIFIED (10.0.x)`.
- `oracle.EVIDENCE` stays `KICAD-VERIFIED` and cites `H-K-CHECK-CANARY-3`.
- Sources: S-0020, S-0022 and S-0037 of `docs/evidence/sources.md`.

## Impact

- Files: about 15 lines in `canary.py` and `oracle.py`, tests, documents (design.md).
- Users: on a board with 499 or more `clearance` violations, `check` may answer
  `kicad.drc.rules-unchecked` where it answered `fired`, or wrongly `rules-not-loaded`, before.
- CI: about 100 s more in `kicad-10`, a few seconds in `kicad-9`.
- Order: independent of c0016, c0023 and c0025. No active change on `main` modifies the two
  requirements; the sibling fixes c0050 and c0052 to c0056 were not visible.
- Size: 1.5 design-days.
