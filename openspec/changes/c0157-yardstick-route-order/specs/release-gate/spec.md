## MODIFIED Requirements

### Requirement: Yardstick stages
The yardstick SHALL grow in five cumulative stages, and `tools/yardstick.py` SHALL hold the table of the stages: for each, the changes it needs and the steps the runner takes.

| stage | needs on `dev`, archived | steps added to the stage before |
|---|---|---|
| 1 | nothing beyond release 0.3.0 | `capabilities`, `build-dry`, `build`, `fill`, `check`, `export`, `render`, `bom`, `pnp`, `manifest`, `rebuild-dry`, `rebuild`, `inspect`, `build-install`, `heavy-read`, `heavy-rt1` |
| 2 | c0100, c0101 | none |
| 3 | c0102, c0103, c0104, c0105, c0111, c0112, c0113, c0114 | `impedance` |
| 4 | c0106, c0107, c0108, c0109, c0110, c0115 | `route`, `route-pairs`, `fill-routed`, `check-routed`, `net`, `analyze` |
| 5 | c0116, c0117, c0118 | `export-package`, `testpoints` |

- `read_stage(path)` MUST read `STAGE` from the script's syntax tree, without running the script. A script without `STAGE`, or with a value outside 1 to 5, MUST make `run` exit 2 with a message that names `STAGE`.
- A stage MUST be set in the example only when every change it needs is archived under `openspec/changes/archive/`, or is named as cut, or as complete for a release (`complete for 0.4: c0100, …`: implemented on the release branch and archived at the release; the coordinator's decision of 2026-10-08), in the `Stages` section of `docs/evidence/yardstick.md`; the part of a cut change MUST then be left out of the example.
- A stage MUST count as reached only after one scheduled run of it has the verdict `passed`; the page MUST then name the date and the run.
- Each stage's additions MUST use the script calls, options and codes of the changes that own them; the yardstick MUST add none of its own. Where two changes offered one thing, the example uses the call that the maintainer's decisions of 2026-10-07 kept: c0102's `design.hole`, c0103's `rule_area`, c0113's `near` rules.
- No stage needs c0096, c0097, c0099, c0120 or c0141. The runner MUST read what they add when it is there (the report-limit mark of c0141, the measures of c0113) and MUST pass without it.
- **Route order** (the maintainer's decision of 2026-10-09, change c0157). The runner MUST run `route` (Freerouting) before `route-pairs` (KiCadRoutingTools), so that Freerouting routes the board without the pair's copper: in run 37836196244, where `route-pairs` ran first, KiCadRoutingTools routed `USB_DP` and `USB_DN` as two separate nets, and their 127 meandered segments left Freerouting 2 of 171 nets closed. This order MUST hold until the yardstick's pair is routed as a coupled pair with the controller's escape; a run with `route-pairs` first is then measured again, and a change of its own sets the order and the budget of `route` on it. The budgets and the ratchets MUST NOT depend on the order: a budget is found by its step's name, and `rebase` MUST give the same budgets and ratchets (its tables may follow the order of the steps) from records that differ only in the order of the two route steps.

#### Scenario: Stage read without running the script
- **GIVEN** a script whose first statement raises an exception and which holds `STAGE = 2`
- **WHEN** `read_stage` reads it
- **THEN** it returns 2, and the exception is never raised

#### Scenario: Stage without its changes
- **GIVEN** the example with `STAGE = 2` while `c0100-board-layer-count` is not archived and the page names no cut
- **WHEN** `uv run pytest tests/unit/test_yardstick.py -k stage_needs` runs
- **THEN** it fails and names `c0100`

#### Scenario: Steps of stage 1
- **WHEN** `steps_for(1)` is called
- **THEN** it returns the steps of stage 1 in the order of the table, `bom`, `pnp` and `manifest` after `render`, `heavy-read` and `heavy-rt1` once for each heavy board, and no `route` step

#### Scenario: Route before the pair
- **WHEN** `steps_for(5)` is called
- **THEN** `route` comes right after `impedance` and right before `route-pairs`, and `fill-routed` comes after both

#### Scenario: Budgets independent of the route order
- **GIVEN** two sets of three stage-5 records that differ only in the order of `route` and `route-pairs`
- **WHEN** `uv run pytest tests/unit/test_yardstick.py -k rebase_ignores_the_order` runs `rebase` on each
- **THEN** both print the same budgets of `route` and `route-pairs` and the same ratchets
