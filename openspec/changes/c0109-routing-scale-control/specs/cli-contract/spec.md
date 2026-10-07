## ADDED Requirements

### Requirement: Route command budget and tiers
`fenolite route` SHALL bound the routing step by one budget and SHALL let the caller route some nets first.
- **Budget.** `--timeout SECONDS` MUST set `RoutingJob.budget` for every router (`routing`, "Routing time budget"); without it the job's budget is `None`, which gives the plugin's `DEFAULT_BUDGET`. The command MUST build a router with the given value whatever it is: `--timeout 600` gives 600 s to Freerouting too. A value that is not a positive number MUST exit 2 with `FEN-2001`.
- **Tiers.** `--order GLOB` (repeatable, `fnmatch` on the net name) MUST set `JobNet.tier` (`routing`, "Routing tiers"): a selected net takes the index of the first `--order` glob it matches, and a net that matches none takes the count of globs. `--order` changes no selection: it orders the nets that `--nets` and the selection give.
- **Result.** `result` MUST hold `budget` (`seconds`, the budget used; `spent`, seconds rounded to 0.1; `exhausted`, a boolean), `runs` (one object per `RouterRun`: `tier`, `nets` as a count, `seconds` rounded to 0.1, `outcome`) and `not_attempted` (net names), beside the keys of "Route command".
- **Write.** When the budget ended, the copper of the finished runs MUST be merged and planned as any routed copper; the exit code MUST stay 0 when no issue of severity error is present.
- `docs/cli-contract.md` MUST describe `--timeout` as the budget of the step, `--order`, the three result keys, `route.budget-exhausted` and `route.optimizer-cut`.

#### Scenario: Finished run written, cut run reported
- **GIVEN** the fake KiCadRoutingTools in a mode that sleeps 5 s when its `--nets` names a net of the second group, and an authored board with two size groups
- **WHEN** `uv run pytest tests/unit/cli/test_route_cmd.py -k budget` runs `fenolite route <board> --router kicadroutingtools --router-path <fake> --timeout 2 --confirm`
- **THEN** the exit code is 0, the written board holds the track of the first run, `result.budget.exhausted` is `true`, `result.runs` has the outcomes `done` then `cut`, and the issues hold one `route.budget-exhausted`

#### Scenario: No sentinel
- **WHEN** `uv run pytest tests/unit/cli/test_route_cmd.py -k timeout` runs `fenolite route <board> --router freerouting --timeout 600 --dry-run` with a router that records its job
- **THEN** the recorded job's `budget` is 600

#### Scenario: Order in tiers
- **WHEN** `fenolite route <board> --router <recording router> --order 'CLK*' --order 'D*' --dry-run` runs on a board with unrouted nets `A`, `CLK1`, `D0`
- **THEN** the recorded job holds `CLK1` with tier 0, `D0` with tier 1 and `A` with tier 2, in that order

#### Scenario: Bad budget
- **WHEN** `fenolite route <board> --router direct --timeout 0 --dry-run` runs
- **THEN** the exit code is 2 and stderr carries `FEN-2001`
