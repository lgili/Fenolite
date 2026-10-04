## ADDED Requirements

### Requirement: Route command
`fenolite route PATH --router NAME [--nets GLOB]... [--rip] [--include-zone-nets] [--router-path DIR] [--router-python PATH] [--router-option KEY=VALUE]... [--allow-offsite] [--timeout SECONDS] [-o OUT]` SHALL be registered by `src/fenolite/cli/cmd_route.py` with `mutates=True`, and SHALL add routed copper to the board that `PATH` names.
- **Board.** `PATH` MUST resolve with `projectset.resolve_board`.
- **Router.** `NAME` MUST be a key of `routing.registry.routers()`; otherwise the command MUST exit 2 with `FEN-2001` and a hint listing the registered names. A router whose `available()` is false MUST exit 6 with `FEN-6001` and its reason. A router with `sends_data_offsite` MUST be refused with exit 2 unless `--allow-offsite` is given.
- **Job.** The command MUST select nets with `routing.select.unrouted` (after `select.rip` when `--rip` is given), build `JobPad`s from the backend's `BoardFrame.board_pads`, and take each net's width, clearance and via sizes from its net class, else from the project's default class.
- **Write.** The command MUST merge the result with `routing.merge.apply` and return one `PlannedWrite` for the board, written by `write_board` for the board's own major, at `--out` when given and at the board's path otherwise. It MUST return none when no net was selected or the result holds no copper. The mutation protocol applies unchanged.
- **Result.** `result` MUST hold `board`, `router`, `tool_version`, `selected`, `routed`, `unrouted`, `tracks`, `vias`, `ripped`, `fills_stale` and `log` (at most 20 lines, sanitised: no temporary path, no home directory).
- **Issues and exit codes.** Each selected net left unrouted MUST give `route.unrouted` (warning). The exit code MUST be 5 for `route.bad-item` or `route.tool-failed`, and 0 otherwise.
- **Evidence.** The envelope evidence MUST be `UNVERIFIED`, with the router's name and version as the oracle text.
- `example_args` MUST be `(EXAMPLE_UNROUTED, "--router", "direct", "--out", "fenolite-routed.kicad_pcb", "--dry-run")`, and `mutation_example_args` the same without `--dry-run`; both MUST run no subprocess.

#### Scenario: Direct route of the example
- **WHEN** `uv run pytest tests/unit/cli/test_route_cmd.py -k example` runs the mutation example with `--confirm` in an empty folder
- **THEN** the exit code is 0, `fenolite-routed.kicad_pcb` holds one more segment than the example board, `result.routed` names its net, and `evidence.level` is `UNVERIFIED`

#### Scenario: Unknown router
- **WHEN** `fenolite route <board> --router nope --dry-run` runs
- **THEN** the exit code is 2, stderr carries `FEN-2001`, and the hint names `direct` and `kicadroutingtools`

#### Scenario: Tool not installed
- **GIVEN** no `FENOLITE_KRT`
- **WHEN** `fenolite route <board> --router kicadroutingtools --dry-run` runs
- **THEN** the exit code is 6, stderr carries `FEN-6001`, and the hint names the repository and the pinned tag

#### Scenario: Nothing to route
- **GIVEN** a board whose every net has copper
- **WHEN** `fenolite route <board> --router direct --confirm` runs
- **THEN** the exit code is 0, `result.selected` is empty, and no file changes

#### Scenario: Routes survive a rebuild
- **GIVEN** a confirmed blink build routed with the fake tool and `--confirm`
- **WHEN** the build runs again twice
- **THEN** the routed segments are kept with their uuids, and the second rebuild writes the bytes of the first

### Requirement: Routers in capabilities and doctor
`fenolite capabilities` SHALL list the registered routers in `result.routers`, sorted by name, each with `name`, `description`, `sends_data_offsite` and `builtin`, without importing a plugin's tool or running a subprocess. `result.sends_data_offsite` MUST stay `false` while no enabled feature sends data without an explicit flag.

`fenolite doctor` SHALL add `result.routers`, each entry with `name`, `available`, `path`, `version` and `reason` from `Router.available()`; a registered router that is not available MUST give `doctor.tool-missing` (warning) naming it, and a plugin listed by `routing.registry.unavailable()` MUST give `doctor.tool-unsupported` (warning) with its error. With `--no-run`, `doctor` MUST list the names only and call no `available()`.

#### Scenario: Routers listed
- **WHEN** `fenolite capabilities --json --no-tools` runs
- **THEN** `result.routers` holds `direct` with `builtin: true` and `kicadroutingtools` with `sends_data_offsite: false`

#### Scenario: Doctor reports a missing tool
- **GIVEN** no `FENOLITE_KRT`
- **WHEN** `fenolite doctor --json` runs
- **THEN** the `kicadroutingtools` entry has `available: false`, one `doctor.tool-missing` warning names it, and the exit code is 0
