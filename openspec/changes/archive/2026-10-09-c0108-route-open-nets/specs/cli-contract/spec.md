## MODIFIED Requirements

### Requirement: Route command
`fenolite route PATH --router NAME [--nets GLOB]... [--rip] [--include-zone-nets] [--require-complete] [--router-path DIR] [--router-python PATH] [--router-option KEY=VALUE]... [--allow-offsite] [--timeout SECONDS] [-o OUT]` SHALL be registered by `src/fenolite/cli/cmd_route.py` with `mutates=True` and `paged = "open"`, and SHALL add routed copper to the board that `PATH` names.
- **Board.** `PATH` MUST resolve with `projectset.resolve_board`.
- **Router.** `NAME` MUST be a key of `routing.registry.routers()`; otherwise the command MUST exit 2 with `FEN-2001` and a hint listing the registered names. A router whose `available()` is false MUST exit 6 with `FEN-6001` and its reason. A router with `sends_data_offsite` MUST be refused with exit 2 unless `--allow-offsite` is given.
- **Rip.** With `--rip`, every net that matches the patterns, has two or more pads and is not carried by a zone (unless `--include-zone-nets`) MUST be ripped with `routing.select.rip`, whose `keep` holds the ids of the script copper of those nets (items whose KiCad uuid satisfies `backends.kicad.copper.is_copper_uuid`).
- **Job.** The command MUST compute the open connections of the board (`board-analyses`, "Open connections of a net") from the backend's `BoardFrame.board_pads`, after the rip and after any copper the command adds before the router, and MUST select nets with `routing.select.unrouted` and those open nets. It MUST build `JobPad`s from `board_pads`, and take each net's width, clearance and via sizes from its net class, else from the project's default class.
- **Verdict.** After the merge, the command MUST compute the open connections of the selected nets again. `routed` MUST hold the selected nets that have none, and `unrouted` the others, whatever the router listed.
- **Write.** The command MUST merge the result with `routing.merge.apply`, the copper of nets that stay open included, and return one `PlannedWrite` for the board, written by `write_board` for the board's own major, at `--out` when given and at the board's path otherwise. It MUST return none when the command added no track, arc or via (merged from the router, or added by a step before the router), when an issue of severity `error` was reported, or when the text is unchanged and `--out` is not given. The mutation protocol applies unchanged.
- **Result.** `result` MUST hold `board`, `router`, `tool_version`, `selected`, `routed`, `unrouted`, `open`, `connections`, `tracks`, `vias`, `ripped`, `rip_kept`, `fills_stale` and `log` (at most 20 lines, sanitised: no temporary path, no home directory).
  - `open` MUST hold one object per net of `unrouted`, sorted by name, with `net`, `islands` and `connections`: each connection with `a` and `b` (`kind`, `where`, `position`, `layers`) and `length` in nanometres.
  - `connections` MUST hold `before` and `after`: the number of open connections of the selected nets before the router and after the merge.
  - `rip_kept` MUST hold `locked` and `script`: the numbers of items of the ripped nets that the rip kept because they are locked or script copper, 0 without `--rip`.
  - `fills_stale` MUST be true, with one `route.fill-stale` (info), when the board has fills and the command added copper, whether or not a net was completed.
- **Issues and exit codes.** Each net of `unrouted` MUST give `route.unrouted` (warning) with its number of open connections and its shortest one; when the router listed that net as routed, the message MUST say so. Each net of `unrouted` that got copper from the router MUST give `route.partial` (info) with the number of items kept. With `--require-complete` and a non-empty `unrouted`, the command MUST add one `route.incomplete` (error) naming the number of open nets and the first five, and MUST plan no write. The exit code MUST be 5 for `route.bad-item`, `route.tool-failed` or `route.incomplete`, and 0 otherwise.
- **Evidence.** The envelope evidence MUST be `UNVERIFIED`, with the router's name and version as the oracle text.
- `example_args` MUST be `(EXAMPLE_UNROUTED, "--router", "direct", "--out", "fenolite-routed.kicad_pcb", "--dry-run")`, and `mutation_example_args` the same without `--dry-run`; both MUST run no subprocess.

#### Scenario: Direct route of the example
- **WHEN** `uv run pytest tests/unit/cli/test_route_cmd.py -k example` runs the mutation example with `--confirm` in an empty folder
- **THEN** the exit code is 0, `fenolite-routed.kicad_pcb` holds one more segment than the example board, `result.routed` names its net, `result.connections` is `{"before": 1, "after": 0}`, and `evidence.level` is `UNVERIFIED`

#### Scenario: Unknown router
- **WHEN** `fenolite route <board> --router nope --dry-run` runs
- **THEN** the exit code is 2, stderr carries `FEN-2001`, and the hint names `direct` and `kicadroutingtools`

#### Scenario: Tool not installed
- **GIVEN** no `FENOLITE_KRT`
- **WHEN** `fenolite route <board> --router kicadroutingtools --dry-run` runs
- **THEN** the exit code is 6, stderr carries `FEN-6001`, and the hint names the repository and the pinned tag

#### Scenario: Nothing to route
- **GIVEN** a board whose every net is closed
- **WHEN** `fenolite route <board> --router direct --confirm` runs
- **THEN** the exit code is 0, `result.selected` is empty, and no file changes

#### Scenario: A net with a stub is routed
- **GIVEN** `two_pads.kicad_pcb` with a 3 mm track from `J1-1` on `ROUTE_ME`
- **WHEN** `uv run pytest tests/unit/cli/test_route_cmd.py -k stub` runs `fenolite route <board> --router direct --confirm`
- **THEN** `result.selected` and `result.routed` are `["ROUTE_ME"]`, `result.unrouted` is empty, and the written board holds the 3 mm track and the new one

#### Scenario: The router's claim does not decide
- **GIVEN** a test router that returns one 2 mm track from `J1-1` of `two_pads.kicad_pcb` and lists `ROUTE_ME` as routed
- **WHEN** `fenolite route <board> --router <test router> --confirm` runs
- **THEN** the exit code is 0, the board holds the track, `result.unrouted` is `["ROUTE_ME"]`, `result.open` holds one connection of `length` 8 000 000 from the free end of the track to `J2-1`, and the issues hold one `route.partial` and one `route.unrouted` whose message says that the router listed the net as routed

#### Scenario: Required complete
- **GIVEN** the same test router
- **WHEN** `fenolite route <board> --router <test router> --require-complete --confirm` runs
- **THEN** the exit code is 5, the issues hold one `route.incomplete` naming `ROUTE_ME`, there is no receipt, and the board's bytes are unchanged

#### Scenario: A second pass completes a net
- **GIVEN** a board with a net of three pads and no copper, and a test router that joins one open connection of each net per run
- **WHEN** `uv run pytest tests/unit/cli/test_route_cmd.py -k second_pass` runs `fenolite route --confirm` twice
- **THEN** after the first run `result.unrouted` names the net and `result.connections` is `{"before": 2, "after": 1}`; after the second, `result.selected` and `result.routed` name it and `result.connections` is `{"before": 1, "after": 0}`

#### Scenario: Rip keeps locked and script copper
- **GIVEN** a board whose net `N` holds a track written with `(locked yes)`, a track whose uuid is a copper uuid, and an unlocked track with a version-4 uuid
- **WHEN** `fenolite route <board> --router direct --rip --nets N --dry-run` runs
- **THEN** `result.ripped` is 1 and `result.rip_kept` is `{"locked": 1, "script": 1}`

#### Scenario: Routes survive a rebuild
- **GIVEN** a confirmed blink build routed with the fake tool and `--confirm`
- **WHEN** the build runs again twice
- **THEN** the routed segments are kept with their uuids, and the second rebuild writes the bytes of the first

## ADDED Requirements

### Requirement: Open connections in the net command
`fenolite net PATH [NAME]` (c0066, "Net command") SHALL report the open connections of the board's nets (`board-analyses`, "Open connections of a net"), computed from the board-frame pads it already reads.
- Each row of `result.nets` MUST add `islands` and `open`, the number of open connections.
- `result.net` MUST add `islands`, `fill_islands` and `open`: the list of connections, each with `a` and `b` (`kind`, `where`, `position`, `layers`) and `length` in nanometres.
- The envelope evidence MUST be `Evidence.combine` of the board read's evidence, `frame.EVIDENCE` and `connectivity.EVIDENCE`, and the `analysis.item-unsupported` issues of the query MUST be passed on.
- `docs/cli-contract.md` MUST describe the keys and say that they are computed from the board, with the limits of the query.

#### Scenario: Rows of the authored board
- **WHEN** `uv run fenolite net tests/data/kicad/board/two_layer.kicad_pcb --json` runs
- **THEN** the rows `GND`, `LED_A` and `VCC` have `open` 0, 1 and 0 and `islands` 1, 2 and 1

#### Scenario: Pins on no net
- **GIVEN** the board of a confirmed build of `examples/blink_2layer/design.py`, whose pins on no net each hold a net named `unconnected-(…)`
- **WHEN** `uv run pytest tests/unit/cli/test_views_cmd.py -k unconnected` runs `fenolite net <board> --json`
- **THEN** each of those rows has `islands` 1 and `open` 0

#### Scenario: One open net
- **WHEN** `uv run fenolite net tests/data/kicad/board/two_layer.kicad_pcb LED_A --json` runs
- **THEN** `result.net.islands` is 2 and `result.net.open` holds one connection between `D1-2` (`kind` `pad`) and an end of the arc (`kind` `arc`)
