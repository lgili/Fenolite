## Why

The nightly yardstick run 37836196244 closed 2 of 171 nets with Freerouting, where a local run of the `route` step alone on 2026-10-08 closed 130 of 167. The gap was measured on 2026-10-09 (`docs/evidence/yardstick.md`, "The routing gap of run 37836196244"): in the runner, `route-pairs` runs before `route`, and KiCadRoutingTools routes `USB_DP` and `USB_DN` as two separate nets (c0110 declares `pairs`, but the yardstick's pair is not routed coupled; `escape` is undeclared). Its 127 meandered segments beside the controller `U3` block Freerouting: the same tier-1 design file with that copper leaves tier 1 cut by the budget, and without it about 120 nets close. The page proposed that a change of the runner give `route` the board before the pair is routed. c0119, which owns the runner, is archived.

The maintainer decided on 2026-10-09: `route-pairs` runs after `route` until the yardstick's pair is routed as a coupled pair.

## Outcome in one paragraph

**`route` runs before `route-pairs` in the yardstick.** The step table of stage 4 in `tools/yardstick.py` lists `route`, `route-pairs`, `fill-routed`, `check-routed`, `net`, `analyze`. Freerouting then routes the board the local reference routed (it leaves the pair open with `route.pair-skipped`), and KiCadRoutingTools routes the pair and the controller's escape on what is left. Nothing else in the runner, its record, its budgets or its ratchets changes. The order is measured again once the pair routes as a coupled pair.

## What Changes

- **`tools/yardstick.py`**: the order of the stage-4 steps in `STAGES`; `routed_measures` reports the two route steps in the run's order; the module notes say why.
- **Tests**: `tests/unit/test_yardstick.py` asserts the order, that the routed measures read the same whatever the order of the steps in a record, and that `rebase` gives the same budgets and ratchets from records of either order.
- **Pages**: `tools/README.md`, `docs/evidence/yardstick.md` (Stages, the proposal of the routing gap marked as made), `tools/yardstick_budgets.toml` (tables in step order), the comment of the nightly job, `docs/roadmap.md` (Open decisions, row 39), `openspec/README.md`.

Size: 0.25 design-day (a size, not time).

## Capabilities

### New Capabilities
None.

### Modified Capabilities
- `release-gate`: MODIFIED "Yardstick stages" (the order of the stage-4 steps and the condition under which it is measured again).

## Non-goals

- No change to `fenolite route`, to either router plugin, or to the Specctra writer (keeping the pair's copper apart by its gap rather than the default rule is a separate question).
- No new budget or ratchet value: the stage-5 budgets stay provisional, and the first three scheduled runs after this change give `rebase` its records.
- No run of the nightly job here; the next scheduled run measures the new order.

## Evidence level required

- The cause of the gap: as measured on 2026-10-09 (the page's section; the band of copper as the obstacle is `INFERRED` there). This change moves no evidence label: seconds and counts of one runner move none.
