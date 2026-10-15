## Context

- `tools/yardstick.py` (c0119, archived) holds `STAGES`: per stage, the changes it needs and the steps it adds. Stage 4 added `route-pairs` (KiCadRoutingTools on `USB_D*` with the escape of `U3`, `--timeout 600`) and then `route` (Freerouting, `--timeout 3600`, tiers `OSC_*` and `CH*`). `steps_for` keeps the table's order, and the runner runs the steps in that order.
- Run 37836196244 (2026-10-08, stage 5, verdict `passed`): `route-pairs` selected the 2 pair nets and routed 1; `route` selected 171 nets and closed 2. Measured again on 2026-10-09 (`docs/evidence/yardstick.md`, "The routing gap of run 37836196244"): KiCadRoutingTools routes `USB_DP` and `USB_DN` as two nets, 127 segments meandered over a band 14 mm wide beside `U3`; `route` writes them as protected wiring without a net; with that copper Freerouting's tier 1 is cut by the budget, and without it the first two passes leave 20 connections open.
- Freerouting does not route the pair: `fenolite route --router freerouting` leaves a pair it cannot route coupled open with `route.pair-skipped` (the local run of 2026-10-08 skipped `USB_DP`/`USB_DN`). So `route-pairs` after `route` still finds the pair open.

## Decisions

1. **`route` first, then `route-pairs`** (the maintainer's decision of 2026-10-09, Open decisions row 39 of `docs/roadmap.md`). The stage-4 entry of `STAGES` becomes `route`, `route-pairs`, `fill-routed`, `check-routed`, `net`, `analyze`. `route` then measures what the local reference measured, the step its 3 900 s budget was sized on.
2. **Kept, not left out.** The page offered leaving `route-pairs` out of the step list. The step stays: it is the only nightly use of KiCadRoutingTools on a board of this size, and its reply (selected, routed, `pairs`, `escape`) stays in the record.
3. **When the order is measured again.** Once the yardstick's pair is routed as a coupled pair, with the controller's escape (c0110's gate for `escape`, and the yardstick's pair taking the coupled path of `pairs`), a run with `route-pairs` before `route` is measured again, and the order and the budget of `route` are set on it by a change of their own. Until then the order of this change holds.
4. **Budgets and ratchets do not depend on the order.** `judge` finds a step's budget by its name; `rebase` keys each budget by the step name, in the order it first meets the names, and takes the ratchets as the largest counts of the routed board (`board.routed.drc`), which `check-routed` measures after both route steps. The record's format (`fenolite.yardstick-record.v0`) does not change: `steps` is in run order, and `board.routed` holds one entry per route step, keyed by its name. `routed_measures` now fills it in the run's order. The tests show that records that differ only in the order of the two steps give the same budgets and ratchets from `rebase` (read back as TOML; the tables follow the step order).
5. **No record of the old order feeds `rebase`.** The counts of the routed board change with the order. The ratchets and budgets of stage 5 are still provisional (bounds and copies of stage 1); the first three scheduled runs after this change are the records `rebase` takes. Run 37836196244 stays a row of `Runs`, with a note on its order in the page.
6. **The tables of the budgets file** list `route` before `route-pairs`, to read in step order (TOML order carries no meaning).

## Files and API

- `tools/yardstick.py`: `STAGES[4]`, the comment of `_COMMANDS`, `routed_measures`. No public name changes.
- `tests/unit/test_yardstick.py`: `test_steps_of_stages_3_to_5`, a new `test_route_runs_before_the_pair`, a new `test_rebase_ignores_the_order_of_the_route_steps`.
- `tools/yardstick_budgets.toml`, `tools/README.md`, `docs/evidence/yardstick.md`, `.github/workflows/nightly.yml` (comment only).

## Evidence

No label moves. The order follows the measurement of 2026-10-09; whether the next scheduled run closes as many nets as the local reference is that run's measure, recorded on the page when it comes.

## Tests

- `uv run pytest tests/unit/test_yardstick.py -q`: the step order of stages 4 and 5, the passing run at stage 5 through the fake `fenolite` with the new order, and `rebase` on records of both orders.

## Size (design-days)

| group | dd |
|---|---|
| runner, tests, pages | 0.25 |

Total: 0.25. This is a size, not a calendar estimate.

## Spec deltas and archive order

- `release-gate`: MODIFIED "Yardstick stages", added by c0119 (archived); no open change holds a delta of it, so this change can be archived at any time.
