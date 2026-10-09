## ADDED Requirements

### Requirement: Routing time budget
`fenolite.routing.protocol` SHALL bound a routing job by one wall-clock budget and SHALL keep the copper of every router run that ended inside it.
- `RoutingJob` MUST gain `budget: float | None = None`, seconds for the plugin's whole `route()`; `None` means the plugin's `DEFAULT_BUDGET`. `DEFAULT_BUDGET` MUST be 900 for `KicadRoutingToolsRouter` and for `FreeroutingRouter`. The built-in `direct` router starts no process and MUST ignore the budget.
- `RouterRun(nets: tuple[str, ...], tier: int, seconds: float, outcome: Literal["done", "failed", "cut"])` MUST be defined, and `RoutingResult` MUST gain `runs: tuple[RouterRun, ...] = ()` and `not_attempted: tuple[str, ...] = ()`. A plugin MUST list one `RouterRun` per process it started, in the order it started them.
- `fenolite.routing.budget.Budget(seconds)` MUST start every process of a plugin: it gives the process the time left on a `time.monotonic()` clock that starts before the first process, kills it when that time is spent, and reports `spent()` and `left()`.
- A process still running when the budget ends MUST be killed and MUST add no copper; its run has the outcome `cut`, and its nets that no finished run routed MUST be in `unrouted`.
- A plugin MUST NOT start a process once the budget is spent. The nets of the runs never started MUST be in `unrouted` and in `not_attempted`.
- The copper of every run with the outcome `done` MUST be in the result.
- A job whose budget ended before every run was done MUST give exactly one `route.budget-exhausted` (warning) whose message names the budget in seconds, the count of nets of the cut run and the count of nets not attempted; only the cut of the optimizer run of "Freerouting plugin" gives `route.optimizer-cut` instead. Reaching the budget MUST NOT give `route.tool-failed`.
- `routing.codes.ISSUE_CODES` MUST hold `route.budget-exhausted` (warning) and `route.optimizer-cut` (info), and `src/fenolite/cli/data/explain.toml` MUST hold an entry for each, whose fix says to run `route` again or to raise `--timeout`.

#### Scenario: Second group cut
- **GIVEN** the fake KiCadRoutingTools of `tests/_fakerouter.py` in a mode that sleeps 5 s when its `--nets` names `B1`, and a job with nets `A1` (track width 0.2 mm) and `B1` (track width 0.4 mm) and a budget of 2 s
- **WHEN** `uv run pytest tests/unit/routing/test_budget.py -k second_group` routes it
- **THEN** the result holds the fake's track on `A1`, `unrouted` holds `B1`, `runs` has the outcomes `done` then `cut`, one `route.budget-exhausted` warning names 2 s, and no `route.tool-failed` is present

#### Scenario: Runs not attempted
- **GIVEN** the same fake and a job with three groups whose second sleeps 5 s, and a budget of 2 s
- **WHEN** the plugin routes it
- **THEN** `runs` holds two entries (`done`, `cut`), `not_attempted` holds the nets of the third group, and the fake recorded two runs

#### Scenario: Freerouting cut
- **GIVEN** the fake `java` of `tests/_fakefreerouting.py` in mode `sleep` and a budget of 1 s
- **WHEN** `uv run pytest tests/unit/routing/test_freerouting.py -k budget` routes the two-pad job
- **THEN** the result has no copper, `runs` holds one `cut` run, `route.budget-exhausted` is present and `route.tool-failed` is absent

#### Scenario: Budget not reached
- **GIVEN** the fake KiCadRoutingTools in mode `append` and the default budget
- **WHEN** the plugin routes a job of two groups
- **THEN** `runs` holds two `done` runs, `not_attempted` is empty, and no `route.budget-exhausted` is present

### Requirement: Routing tiers
`fenolite.routing.protocol.JobNet` SHALL gain `tier: int = 0`, and a plugin SHALL route the tiers of a job one after the other, lowest first.
- `RoutingJob.nets` MUST be sorted by tier, then by name.
- The copper of the runs of earlier tiers MUST be fixed input of the runs of later tiers: `KicadRoutingToolsRouter` MUST write it into the board of each later run, and `FreeroutingRouter` MUST write it as protected wiring into the design file of each later run.
- A job whose nets all have tier 0 MUST be routed as before this requirement: one Freerouting run, and one KiCadRoutingTools run per group.
- Inside a tier, each tool MUST keep its own order of the nets.

#### Scenario: Two tiers with KiCadRoutingTools
- **GIVEN** the fake KiCadRoutingTools in a mode that records each run's arguments and input board, and a job with `CLK` in tier 0 and `D0` in tier 1, both of one size group
- **WHEN** `uv run pytest tests/unit/routing/test_routingtools.py -k tiers` routes it
- **THEN** two runs are recorded, the first naming only `CLK` and the second only `D0`, and the input board of the second holds the track the first run added

#### Scenario: Two tiers with Freerouting
- **GIVEN** the fake `java` recording the design file of each run, and the same job
- **WHEN** `uv run pytest tests/unit/routing/test_freerouting.py -k tiers` routes it
- **THEN** two runs are recorded; the second design file declares `D0` and not `CLK`, and holds the first session's wire as wiring of type `protect` without a net

## MODIFIED Requirements

### Requirement: KiCadRoutingTools plugin
`fenolite.routing.plugins.kicad.routingtools.KicadRoutingToolsRouter` SHALL run KiCadRoutingTools (S-0215) as a subprocess from a checkout the user names, one process per group of nets, and SHALL lift only new copper from its output.
- **Location.** The checkout is the constructor's `path`, else `FENOLITE_KRT`; the interpreter is `python`, else `FENOLITE_KRT_PYTHON`, else `python3` on `PATH`. `available()` MUST report `available == False` with a reason when the checkout, `py_router/route.py` or the interpreter is missing, and MUST run nothing else.
- **Pin.** `PINNED_TAG` MUST be `"v0.22.1"`. A checkout at another version MUST give `route.tool-unpinned` (warning) and MUST still run.
- **Groups.** A group MUST be the nets of one tier ("Routing tiers") whose `JobNet` width, via diameter and via drill are equal, in the order of the job. With the router option `group-nets=N` (a positive integer), a group MUST be split into runs of at most N nets, in that order. Runs MUST go in the order of their first net in the job.
- **Run.** The plugin MUST write the job's board with `write_board` for its own major into a fresh temporary directory, with the project and rules files of its copy set, and for each run write the board again with the copper of the runs before it. Each run MUST be `<python> <path>/py_router/route.py <board> <routed> --nets <the run's names…> --track-width <width> --via-size <diameter> --via-drill <drill> --escalation off --no-fix-drc-settings` in that directory, with the other router options appended as `--KEY VALUE`, `LANG=C`, and the time left of the job's budget ("Routing time budget"). The plugin MUST NOT pass `--clearance`: the tool reads each class's clearance from the project file of the copy set. The router options `nets`, `output` and `overwrite` MUST be ignored with `route.option-ignored` (warning). Fenolite MUST NOT import the tool.
- **Lift.** The result MUST hold exactly the tracks, arcs and vias of the routed file whose uuid the input lacks. Copper of the input that the routed file lacks MUST give `route.copper-removed` (warning) and MUST NOT be removed from the design.
- **Failure.** A run that exits non-zero or leaves a missing or unreadable output MUST give `route.tool-failed` (error) naming the run's nets, with the first sanitised line of the tool's output; it adds no copper, its nets are unrouted, its `RouterRun` has the outcome `failed`, and the next run starts. A run stopped by the budget MUST follow "Routing time budget" instead.
- `sends_data_offsite` MUST be `False`.

#### Scenario: Fake tool
- **GIVEN** `tests/_fakerouter.py`, a fake `route.py` that copies its input to its output and appends one segment on the first named net, and records its arguments
- **WHEN** `uv run pytest tests/unit/routing/test_routingtools.py -k lift` routes an authored job with it
- **THEN** the result has exactly that one track with the net's id, the recorded arguments hold the board name, the output name, `--nets`, `--escalation off` and `--no-fix-drc-settings` and no `--clearance`, and the working directory was a temporary folder

#### Scenario: One run per group
- **GIVEN** the fake recording every run, and a job with nets `A1` and `A2` of a class with a 0.2 mm track and `B1` of a class with a 0.4 mm track, the same via sizes
- **WHEN** `uv run pytest tests/unit/routing/test_routingtools.py -k groups` routes it
- **THEN** two runs are recorded: the first with `--nets A1 A2` and `--track-width 0.2`, the second with `--nets B1` and `--track-width 0.4`

#### Scenario: Groups split by the option
- **WHEN** the same job is routed with the router option `group-nets=1`
- **THEN** three runs are recorded, one per net, and the option is not passed to the tool

#### Scenario: Tool fails
- **GIVEN** a fake that exits 2 printing `boom` when its `--nets` names `B1`
- **WHEN** the plugin routes the job of "One run per group"
- **THEN** the result keeps the copper of the first run, holds one `route.tool-failed` error whose message holds `boom` and names `B1`, and `runs` has the outcomes `done` then `failed`

#### Scenario: Tool missing
- **GIVEN** no `FENOLITE_KRT` and no `path`
- **WHEN** `available()` is called
- **THEN** it returns `available == False` with a reason naming `FENOLITE_KRT`, and no subprocess ran

#### Scenario: Copper never removed
- **GIVEN** a fake whose output lacks one track of its input
- **WHEN** the plugin routes
- **THEN** the result holds `route.copper-removed`, and `merge.apply` leaves that track on the board

### Requirement: Freerouting plugin
`fenolite.routing.plugins.specctra.freerouting.FreeroutingRouter` SHALL route through Freerouting (S-0220), run as a subprocess, and SHALL be registered as `freerouting` in the entry-point group `fenolite.routers`.
- **Location.** The jar is the constructor's `path`, else `FENOLITE_FREEROUTING_JAR`, else the file `fenolite.core.tools.tool_path("freerouting", f"freerouting-{PINNED_VERSION}.jar")` when it exists ("Tools folder"); `java` is the constructor's `java`, else `FENOLITE_JAVA`, else `java` on `PATH`. The environment and the tools folder MUST be read when the router is used, not when it is constructed, because the registry holds one instance per process. A `path` of the form `docker:<image>` MUST run that image instead, with the run folder mounted and `--network none`. `fenolite route --router freerouting --router-path PATH` names the jar or the image. `jar_source` MUST say which of the three gave the jar: `argument`, `env` or `fetched`, or `None` without a jar.
- **Availability.** `available()` MUST be false with a reason when the jar is missing or `java -version` gives a major below `JAVA_MIN = 25`, and MUST start no router. The reason for a missing jar MUST name the command `fenolite fetch freerouting --confirm` and the variable `FENOLITE_FREEROUTING_JAR`. The version MUST be learned without running the jar: `PINNED_VERSION` when the jar's manifest names the build revision of the pinned tag (`PINNED_REVISION`, S-0223), else the version in the file name `freerouting-<version>.jar`, else `unknown`.
- **Run.** The plugin MUST write the design file with `write_dsn` and `others="netless"` (`specctra-dsn`, "Nets outside the routing job in design files"), from the job's `extra` (`board_pads`, `outline`), into a fresh temporary directory and run `java -jar <jar> -de board.dsn -do board.ses -mp <passes> -mt 1 -da --gui.enabled=false --router.optimizer.enabled=false` there, with `HOME` set to that directory and the time left of the job's budget ("Routing time budget"). `-da` MUST always be passed and MUST NOT be removable through router options. The router options are `max-passes=N` (default 20) and `optimize=on|off` (default `off`); any other option, and a value that is not valid, MUST be ignored with `route.option-ignored` (warning), a code of `routing.codes.ISSUE_CODES`. When the design file keeps nets outside the job declared for their class clearance, the result MUST hold one `route.net-declared` (info), also a code of `routing.codes.ISSUE_CODES` with its entry in `explain.toml`, whose message gives their count and names the first five. The board defaults passed to `write_dsn` are the values of the design's `Default` class, else 0.2 mm width and clearance and a 0.6 mm via with a 0.3 mm drill, as in `fenolite route`.
- **Tiers.** A job of more than one tier MUST give one run per tier ("Routing tiers"); the design file of each run selects the nets of its tier.
- **Optimizer.** With `optimize=on` and one tier, a second run of the same design file without `--router.optimizer.enabled=false` MUST get the time left. When it writes a session in time, that session replaces the first; otherwise the first is kept and `route.optimizer-cut` (info) is reported, not `route.budget-exhausted`. With more than one tier, `optimize=on` MUST be ignored with `route.option-ignored`.
- **Outline.** A job whose `extra` lacks the pads or holds no outline ring MUST give `route.tool-failed` (error) and start no router: a design file needs the board outline.
- **Result.** Each session MUST be read with `read_session` and `to_copper`. A missing or unreadable session MUST give `route.tool-failed` (error) and no copper for that run. A run stopped by the budget MUST follow "Routing time budget". `routed` holds the job's nets that got copper and `unrouted` the others; the findings of the writer and of the reader are part of the result's issues.
- **Pin.** `PINNED_VERSION` MUST be `"2.4.1"`; another version MUST give `route.tool-unpinned` (warning).
- **Data.** `sends_data_offsite` MUST be `True` until `H-G-DSN-OFFLINE` is recorded as `present`, and `False` after; while it is `True`, `fenolite route` refuses the router without `--allow-offsite` (c0016).
- Fenolite MUST NOT import or vendor Freerouting. It MUST NOT download it either, except through `fenolite fetch freerouting --confirm` (`cli-contract`, "Fetch command"): the plugin, `fenolite route`, `fenolite doctor` and `fenolite capabilities` MUST open no network connection.
- **Messages.** When the jar is missing, `fenolite route --router freerouting` MUST exit 6 with `FEN-6001` and the hint `run 'fenolite fetch freerouting --confirm'`. The `freerouting` entry of `doctor`'s `result.routers` MUST hold `source`, the value of `jar_source`.

#### Scenario: Fake java
- **GIVEN** `tests/_fakefreerouting.py`, a fake `java` that records its arguments and writes the authored session for the two-pad board
- **WHEN** `uv run pytest tests/unit/routing/test_freerouting.py -k route` routes the two-pad job
- **THEN** the result holds the session's tracks, and the recorded arguments hold `-de`, `-do`, `-mt 1`, `-da`, `--gui.enabled=false` and `--router.optimizer.enabled=false`

#### Scenario: Through the command
- **GIVEN** the two-pad board written as a KiCad board, a fake jar and the fake `java`
- **WHEN** `uv run pytest tests/unit/cli/test_route_cmd.py -k freerouting_through` runs `fenolite route two_pads.kicad_pcb --router freerouting --router-path <jar> --allow-offsite --dry-run`
- **THEN** the exit code is 0, `result.routed` is `["A"]`, and the plan holds the board

#### Scenario: Other nets left out of the design file
- **GIVEN** a board with nets `A` and `B`, each of two pads, and a job that selects `A`
- **WHEN** the fake `java` records the design file it is given
- **THEN** the network section declares `A` and not `B`, and the pins of `B` are in their images

#### Scenario: A net of a wider class is named
- **GIVEN** the bench `netless_bench` of `tests/_specctra.py`, where the net `B` outside the job is in a class whose clearance is twice the default rule, and a job that selects `A`
- **WHEN** `uv run pytest tests/unit/routing/test_freerouting.py -k wider` routes it with the fake `java`
- **THEN** the recorded design file declares `A` and `B` and not `C`, and the result holds one `route.net-declared` (info) that names `B`

#### Scenario: Optimizer run cut
- **GIVEN** a fake `java` that writes the session at once when it is given `--router.optimizer.enabled=false` and sleeps 5 s otherwise, the option `optimize=on` and a budget of 2 s
- **WHEN** the plugin routes the two-pad job
- **THEN** the result holds the first session's tracks, `runs` has the outcomes `done` then `cut`, and `route.optimizer-cut` is present

#### Scenario: Board without an outline
- **GIVEN** a board without a closed outline
- **WHEN** the plugin routes
- **THEN** the result holds `route.tool-failed` naming the outline, and no router run was recorded

#### Scenario: Java too old
- **GIVEN** a fake `java` whose `-version` prints `17.0.2`
- **WHEN** `available()` is called
- **THEN** it is false with a reason naming Java 25, and no router run was recorded

#### Scenario: Analytics cannot be re-enabled
- **WHEN** the plugin routes with the option `da=false`
- **THEN** the recorded arguments still hold `-da`, and the result holds a warning naming the ignored option

#### Scenario: No session
- **GIVEN** a fake `java` that exits 0 and writes nothing
- **WHEN** the plugin routes
- **THEN** the result has no copper and one `route.tool-failed` error

#### Scenario: Fetched jar is found
- **GIVEN** no `FENOLITE_FREEROUTING_JAR`, `FENOLITE_TOOLS_DIR` naming a folder that holds `freerouting/freerouting-2.4.1.jar` (a fake jar), and the fake `java`
- **WHEN** `uv run pytest tests/unit/routing/test_freerouting.py -k fetched` asks the router for `available()` and `jar_source`
- **THEN** it is available, `jar_source` is `fetched`, and setting `FENOLITE_FREEROUTING_JAR` to another fake jar makes `jar_source` `env`

#### Scenario: Missing jar names the command
- **GIVEN** no jar in any of the three places
- **WHEN** `uv run pytest tests/unit/cli/test_route_cmd.py -k missing_jar` runs `fenolite route two_pads.kicad_pcb --router freerouting --dry-run`, and `fenolite doctor --json`
- **THEN** the first exits 6 with `FEN-6001` and a hint that holds `fenolite fetch freerouting --confirm`, and the `freerouting` entry of the second has `available: false`, `source: null` and a reason that names the same command

#### Scenario: No connection outside fetch
- **GIVEN** `urllib.request.urlopen` and `socket.create_connection` patched to raise
- **WHEN** `uv run pytest tests/unit/cli/test_fetch_cmd.py -k no_connection` runs `route --dry-run` with the fake jar, `doctor --no-run` and `capabilities --no-tools`
- **THEN** each exits as it does without the patches
