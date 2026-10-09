## ADDED Requirements

### Requirement: Pairs and escape in the route command
`fenolite route` SHALL also take `--escape REF[=grid|perimeter]` (repeatable) and `--pairs-as-nets`, and SHALL give the router the differential pairs and the escape requests of the job, in addition to what "Route command" states.
- **Pairs.** After the candidates are selected, the command MUST call `routing.pairs.job_pairs` unless `--pairs-as-nets` is given. When `router_features(router)` lacks `pairs`, the nets of every pair MUST be removed from the job, each pair with one `route.pair-skipped` (warning) whose hint names `--pairs-as-nets` and the registered routers that have the feature. With `--pairs-as-nets`, the nets of each pair MUST be routed as single nets, each pair giving one `route.pair-uncoupled` (info).
- **Escape.** Requests MUST come from `routing.escape.requests` over the board-frame pads of the board. When `router_features(router)` lacks `escape`, every request MUST be removed, each with `route.escape-skipped` (warning) naming the router. A value of `--escape` with a suffix other than `=grid` or `=perimeter` MUST exit 2 with `FEN-2001`.
- **Width guard.** A routed track or arc narrower than the width the job gave its net, the pair's width for a pair net, MUST give one `route.width-below-job` (warning) per net, naming the smallest width found and the width asked, with a hint naming `--router-option fanout=off` when the router is `freerouting`; the copper is kept, and KiCad's DRC judges it.
- **Result.** `result` MUST gain `pairs`, a list of `{name, positive, negative, width, gap, routed}` for the pairs given to the router, `routed` being true when both nets are in `result.routed`, and `escape`, a list of `{ref, kind, pitch, nets}` for the requests given to it. `result.selected` MUST name every net given to the router, pair nets included.
- **Codes.** `route.pair-skipped` (warning), `route.pair-uncoupled` (info), `route.escape-skipped` (warning) and `route.width-below-job` (warning) MUST be keys of `routing.codes.ISSUE_CODES` and MUST be described in `docs/cli-contract.md`. None changes the exit code, which stays as "Route command" states.

#### Scenario: A router without pairs
- **GIVEN** the unrouted board `tests/data/kicad/routing/pair_two_headers.kicad_pcb`, authored for Fenolite, with the pair `USB_P`/`USB_N` and the single nets `S1` and `S2` in one class with pair values, and the fake `java` of `tests/_fakefreerouting.py`
- **WHEN** `uv run pytest tests/unit/cli/test_route_cmd.py -k pair_skipped` runs `fenolite route <board> --router freerouting --router-path <jar> --dry-run`
- **THEN** the exit code is 0, `result.selected` is `["S1", "S2"]`, `result.pairs` is empty, and one `route.pair-skipped` names `USB_P/USB_N` with a hint naming `--pairs-as-nets` and `kicadroutingtools`

#### Scenario: Pairs as single nets
- **WHEN** the same command runs with `--pairs-as-nets`
- **THEN** `result.selected` holds `USB_N`, `USB_P`, `S1` and `S2`, and one `route.pair-uncoupled` names the pair

#### Scenario: Escape without the feature
- **WHEN** `fenolite route <board> --router direct --escape 'U*' --dry-run` runs on a board with a QFN `U1` that has a selected net
- **THEN** the exit code is 0, `result.escape` is empty, and one `route.escape-skipped` names `U1` and `direct`

#### Scenario: Unknown escape kind
- **WHEN** `fenolite route <board> --router direct --escape U1=ring --dry-run` runs
- **THEN** the exit code is 2 and stderr carries `FEN-2001` naming `ring`

#### Scenario: Narrower copper reported
- **GIVEN** a test router that returns, for the net `A` of width 0.2 mm, a track of 0.1996 mm
- **WHEN** `fenolite route <board> --router <test router> --dry-run` runs
- **THEN** one `route.width-below-job` names `A`, 0.1996 mm and 0.2 mm, the plan holds the board, and the exit code is 0

### Requirement: Router pair and escape features in capabilities
Each entry of `result.routers` of `fenolite capabilities` SHALL also hold `features`, the sorted list of `routing.protocol.router_features(router)`, read without running anything. The key is added to the router entries only: `result.matrix` and the kinds of the Altium backend in the reply are not changed.

#### Scenario: Features listed
- **WHEN** `uv run pytest tests/unit/cli/test_capabilities.py -k features` runs `fenolite capabilities --json --no-tools`
- **THEN** `direct` and `freerouting` list no feature, and `kicadroutingtools` lists the features that its gate outcomes allowed
