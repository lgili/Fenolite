# routing Specification

## Purpose
Route a board through a router plugin: the router protocol and registry, the selection of nets, the merge of routed copper into the board, the built-in direct router, the KiCadRoutingTools and Freerouting plugins that run as separate processes, and the routing issue codes.

## Requirements

### Requirement: Router protocol
`fenolite.routing.protocol` SHALL define, as frozen dataclasses on `core` and `model` types only:
- `JobPad(ref: str, number: str, net: str, position: Point, layers: tuple[str, ...], drill: Nm | None = None)`;
- `JobNet(name: str, net_id: str, pads: tuple[JobPad, ...], width: Nm, clearance: Nm, via_diameter: Nm, via_drill: Nm)`;
- `RoutingJob(design: Design, nets: tuple[JobNet, ...], layers: tuple[str, ...], options: Mapping[str, str] = {})`;
- `RoutingResult(tracks: tuple[Track, ...] = (), arcs: tuple[Arc, ...] = (), vias: tuple[Via, ...] = (), routed: tuple[str, ...] = (), unrouted: tuple[str, ...] = (), issues: tuple[Issue, ...] = (), tool: str = "", tool_version: str = "", log: tuple[str, ...] = (), evidence: Evidence = Evidence())`;
- `RouterStatus(available: bool, path: str = "", version: str = "", reason: str = "")`;

and the `typing.Protocol` `Router` with `name: str`, `description: str`, `sends_data_offsite: bool`, `available() -> RouterStatus` and `route(job: RoutingJob) -> RoutingResult`.

`route` MUST NOT write outside a temporary directory of its own, MUST return every failure as issues in the result instead of raising for a tool failure, and MUST return `evidence` of level `UNVERIFIED`. `fenolite.routing` MUST import only `core`, `model` and `geometry`; `fenolite.routing.plugins.<x>` MAY also import `fenolite.backends.<x>` (`package-layering`).

#### Scenario: Protocol satisfied by the built-in router
- **GIVEN** the statement `_ROUTER: Router = DirectRouter()` in `routing/direct.py`
- **WHEN** `uv run pyright src` runs
- **THEN** it reports no error

#### Scenario: Results are unverified
- **WHEN** `uv run pytest tests/unit/routing -k evidence` routes an authored job with every registered router that is available
- **THEN** each result's evidence level is `UNVERIFIED`

#### Scenario: Layering holds
- **WHEN** `uv run pytest tests/unit/test_import_graph.py` runs
- **THEN** it passes; a module in `src/fenolite/routing/` that imports `fenolite.backends.base` makes it fail

### Requirement: Router registry
`fenolite.routing.registry.routers() -> Mapping[str, Router]` SHALL return the routers of the entry-point group `fenolite.routers`, by name, sorted. `pyproject.toml` MUST declare `direct` and `kicadroutingtools` in that group, and `dependencies` MUST stay empty.
- An entry point whose import or construction fails MUST be left out of `routers()` and reported by `unavailable()` with its error text.
- A second entry point with a name already registered MUST be ignored and reported by `unavailable()`.

#### Scenario: Built-in routers listed
- **WHEN** `uv run pytest tests/unit/routing/test_registry.py -k builtin` calls `routers()`
- **THEN** its keys hold `direct` and `kicadroutingtools`

#### Scenario: Broken plugin
- **GIVEN** an entry point whose module raises `ImportError`
- **WHEN** `routers()` is called
- **THEN** it returns the other routers, and `unavailable()` names the broken one with the error text

### Requirement: Net selection
`fenolite.routing.select.unrouted(design, *, patterns=("*",), include_zone_nets=False) -> tuple[str, ...]` SHALL return, sorted, the names of the nets to route:
- a net MUST have two or more pads on placed footprints and no track, arc or via of its own;
- a net that a zone carries MUST be left out unless `include_zone_nets` is true;
- `patterns` are `fnmatch` globs on the net name; a pattern starting with `!` excludes, and a net is selected when it matches a non-excluding pattern and no excluding one.

`select.rip(design, nets) -> tuple[Design, int]` SHALL remove the tracks, arcs and vias of those nets that are not locked and return their count.

#### Scenario: Unrouted nets
- **GIVEN** an authored design with nets `A` (two pads, no copper), `B` (two pads, one track), `GND` (three pads, one zone) and `NC` (one pad)
- **WHEN** `uv run pytest tests/unit/routing/test_select.py` calls `unrouted`
- **THEN** it returns `("A",)`, and `("A", "GND")` with `include_zone_nets=True`

#### Scenario: Patterns
- **WHEN** `unrouted(design, patterns=("*", "!A"))` is called on the same design
- **THEN** it returns `()`

#### Scenario: Rip
- **WHEN** `rip(design, ("B",))` is called
- **THEN** the design has no track on `B`, the count is 1, and `unrouted` then returns `("A", "B")`

### Requirement: Routed copper is merged
`fenolite.routing.merge.apply(design, result) -> Design` SHALL append the result's tracks, arcs and vias to the board after the existing ones, and SHALL change nothing else.
- An item whose `net_id` is not a net of the design, whose layer is not a copper layer of the board, or whose id equals an existing id MUST make `apply` raise `RoutingError` carrying one `route.bad-item` issue per item, and nothing is merged.
- An item without an id MUST get `core.ids.derived_id` over its net name and geometry.

#### Scenario: Tracks appended
- **GIVEN** a design with one track and a result with two tracks and one via on net `A`
- **WHEN** `uv run pytest tests/unit/routing/test_merge.py -k append` calls `apply`
- **THEN** the board has three tracks and one via, the first track is the original one, and every other entity is unchanged

#### Scenario: Foreign net refused
- **GIVEN** a result with a track whose `net_id` the design lacks
- **WHEN** `apply` is called
- **THEN** `RoutingError` is raised with `route.bad-item`, and the design is unchanged

### Requirement: Built-in direct router
`fenolite.routing.direct.DirectRouter` SHALL route each job net that has exactly two pads sharing a copper layer with one `Track` from pad to pad on the first shared layer in stack order, with the net's width, and SHALL list every other net as `unrouted`. It MUST check no clearance, MUST run no subprocess, MUST be deterministic, and its `description` MUST say that it avoids nothing.

#### Scenario: Two-pad net
- **GIVEN** a job with a two-pad net on `F.Cu` and a three-pad net
- **WHEN** `uv run pytest tests/unit/routing/test_direct.py` routes it
- **THEN** the result has one track between the two pad positions, `routed` names the first net and `unrouted` the second

### Requirement: KiCadRoutingTools plugin
`fenolite.routing.plugins.kicad.routingtools.KicadRoutingToolsRouter` SHALL run KiCadRoutingTools (S-0215) as a subprocess from a checkout the user names, and SHALL lift only new copper from its output.
- **Location.** The checkout is the constructor's `path`, else `FENOLITE_KRT`; the interpreter is `python`, else `FENOLITE_KRT_PYTHON`, else `python3` on `PATH`. `available()` MUST report `available == False` with a reason when the checkout, `py_router/route.py` or the interpreter is missing, and MUST run nothing else.
- **Pin.** `PINNED_TAG` MUST be `"v0.22.1"`. A checkout at another version MUST give `route.tool-unpinned` (warning) and MUST still run.
- **Run.** The plugin MUST write the job's board with `write_board` for its own major into a fresh temporary directory, with the project and rules files of its copy set, and run `<python> <path>/py_router/route.py <board> <routed> --nets <names…>` there, passing each net's width, clearance and via sizes through the tool's flags, `LANG=C`, and a timeout. Fenolite MUST NOT import the tool.
- **Lift.** The result MUST hold exactly the tracks, arcs and vias of the routed file whose uuid the input lacks. Copper of the input that the routed file lacks MUST give `route.copper-removed` (warning) and MUST NOT be removed from the design.
- **Failure.** A non-zero exit, a timeout or a missing or unreadable output MUST give `route.tool-failed` (error) with the first sanitised line of the tool's output, and an empty result.
- `sends_data_offsite` MUST be `False`.

#### Scenario: Fake tool
- **GIVEN** `tests/_fakerouter.py`, a fake `route.py` that copies its input to its output and appends one segment on the first named net, and records its arguments
- **WHEN** `uv run pytest tests/unit/routing/test_routingtools.py -k lift` routes an authored job with it
- **THEN** the result has exactly that one track with the net's id, the recorded arguments hold the board name, the output name and `--nets`, and the working directory was a temporary folder

#### Scenario: Tool fails
- **GIVEN** a fake that exits 2 printing `boom`
- **WHEN** the plugin routes
- **THEN** the result has no copper and one `route.tool-failed` error whose message holds `boom`

#### Scenario: Tool missing
- **GIVEN** no `FENOLITE_KRT` and no `path`
- **WHEN** `available()` is called
- **THEN** it returns `available == False` with a reason naming `FENOLITE_KRT`, and no subprocess ran

#### Scenario: Copper never removed
- **GIVEN** a fake whose output lacks one track of its input
- **WHEN** the plugin routes
- **THEN** the result holds `route.copper-removed`, and `merge.apply` leaves that track on the board

### Requirement: Routing issue codes
`fenolite.routing.codes.ISSUE_CODES` SHALL map every `route.*` code to one severity, and SHALL hold at least: `route.bad-item` (error), `route.tool-failed` (error), `route.unrouted` (warning), `route.copper-removed` (warning), `route.tool-unpinned` (warning), `route.zone-net-skipped` (info), `route.fill-stale` (info). `docs/cli-contract.md` MUST document every key.

#### Scenario: Closed set
- **WHEN** `uv run pytest tests/unit/routing -k codes` collects every `route.*` literal under `src/fenolite/routing/` and `cli/cmd_route.py`
- **THEN** each is a key of `ISSUE_CODES`, and every key appears in `docs/cli-contract.md`

### Requirement: Routing facts are documented
`docs/routing.md` SHALL describe the plugin contract (the entry-point group, the protocol, `sends_data_offsite`), the built-in routers, how to install KiCadRoutingTools at the pinned tag, and the loop order `place` → `route` → `fill` → `check`. `docs/evidence/routing.md` SHALL record the feasibility gate: tool version and commit, platform, each outcome per major, and the gate verdict.

#### Scenario: Gate recorded
- **WHEN** the feasibility gate has run
- **THEN** `docs/evidence/routing.md` holds one row per outcome of `H-K-KRT-CLI`, `H-K-KRT-ROUTE`, `H-K-KRT-KEEP` and `H-K-KRT-REPEAT` for each major, and the verdict "passed" or "failed" with its consequence for c0023

### Requirement: Job extras
`routing.protocol.RoutingJob` SHALL gain the field `extra: Mapping[str, object] = {}`, after `options`, which the command fills with data that `routing` cannot type: `board_pads` (the tuple of `BoardPad`s of `BoardFrame.board_pads`) and `outline` (the tuple of rings of `board_outline`, empty for a board without a closed outline). A router that needs neither MUST ignore it, and the built-in `direct` router and the KiCadRoutingTools plugin MUST behave as before.

#### Scenario: Extras passed by the command
- **GIVEN** a test router that records its job
- **WHEN** `uv run pytest tests/unit/cli/test_route_cmd.py -k extra` runs `fenolite route` with it
- **THEN** the recorded job's `extra` holds `board_pads` and `outline`

### Requirement: Freerouting plugin
`fenolite.routing.plugins.specctra.freerouting.FreeroutingRouter` SHALL route through Freerouting (S-0220), run as a subprocess, and SHALL be registered as `freerouting` in the entry-point group `fenolite.routers`.
- **Location.** The jar is the constructor's `path`, else `FENOLITE_FREEROUTING_JAR`, else the file `fenolite.core.tools.tool_path("freerouting", f"freerouting-{PINNED_VERSION}.jar")` when it exists ("Tools folder"); `java` is the constructor's `java`, else `FENOLITE_JAVA`, else `java` on `PATH`. The environment and the tools folder MUST be read when the router is used, not when it is constructed, because the registry holds one instance per process. A `path` of the form `docker:<image>` MUST run that image instead, with the run folder mounted and `--network none`. `fenolite route --router freerouting --router-path PATH` names the jar or the image. `jar_source` MUST say which of the three gave the jar: `argument`, `env` or `fetched`, or `None` without a jar.
- **Availability.** `available()` MUST be false with a reason when the jar is missing or `java -version` gives a major below `JAVA_MIN = 25`, and MUST start no router. The reason for a missing jar MUST name the command `fenolite fetch freerouting --confirm` and the variable `FENOLITE_FREEROUTING_JAR`. The version MUST be learned without running the jar: `PINNED_VERSION` when the jar's manifest names the build revision of the pinned tag (`PINNED_REVISION`, S-0223), else the version in the file name `freerouting-<version>.jar`, else `unknown`.
- **Run.** The plugin MUST write the design file with `write_dsn`, from the job's `extra` (`board_pads`, `outline`), into a fresh temporary directory and run `java -jar <jar> -de board.dsn -do board.ses -mp <passes> -mt 1 -da --gui.enabled=false` there, with `HOME` set to that directory and a timeout (900 s by default). `-da` MUST always be passed and MUST NOT be removable through router options. The only router option is `max-passes=N` (default 20); any other option, and a value that is not a positive integer, MUST be ignored with `route.option-ignored` (warning), a code of `routing.codes.ISSUE_CODES`. The board defaults passed to `write_dsn` are the values of the design's `Default` class, else 0.2 mm width and clearance and a 0.6 mm via with a 0.3 mm drill, as in `fenolite route`.
- **Outline.** A job whose `extra` lacks the pads or holds no outline ring MUST give `route.tool-failed` (error) and start no router: a design file needs the board outline.
- **Result.** The session MUST be read with `read_session` and `to_copper`. A missing or unreadable session, and a timeout, MUST give `route.tool-failed` (error) and no copper. `routed` holds the job's nets that got copper and `unrouted` the others; the findings of the writer and of the reader are part of the result's issues.
- **Pin.** `PINNED_VERSION` MUST be `"2.4.1"`; another version MUST give `route.tool-unpinned` (warning).
- **Data.** `sends_data_offsite` MUST be `True` until `H-G-DSN-OFFLINE` is recorded as `present`, and `False` after; while it is `True`, `fenolite route` refuses the router without `--allow-offsite` (c0016).
- Fenolite MUST NOT import or vendor Freerouting. It MUST NOT download it either, except through `fenolite fetch freerouting --confirm` (`cli-contract`, "Fetch command"): the plugin, `fenolite route`, `fenolite doctor` and `fenolite capabilities` MUST open no network connection.
- **Messages.** When the jar is missing, `fenolite route --router freerouting` MUST exit 6 with `FEN-6001` and the hint `run 'fenolite fetch freerouting --confirm'`. The `freerouting` entry of `doctor`'s `result.routers` MUST hold `source`, the value of `jar_source`.

#### Scenario: Fake java
- **GIVEN** `tests/_fakefreerouting.py`, a fake `java` that records its arguments and writes the authored session for the two-pad board
- **WHEN** `uv run pytest tests/unit/routing/test_freerouting.py -k route` routes the two-pad job
- **THEN** the result holds the session's tracks, and the recorded arguments hold `-de`, `-do`, `-mt 1`, `-da` and `--gui.enabled=false`

#### Scenario: Through the command
- **GIVEN** the two-pad board written as a KiCad board, a fake jar and the fake `java`
- **WHEN** `uv run pytest tests/unit/cli/test_route_cmd.py -k freerouting_through` runs `fenolite route two_pads.kicad_pcb --router freerouting --router-path <jar> --allow-offsite --dry-run`
- **THEN** the exit code is 0, `result.routed` is `["A"]`, and the plan holds the board

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

### Requirement: Tools folder
`fenolite.core.tools` SHALL name the one folder in which Fenolite keeps external tools that the user asked it to fetch, and SHALL create nothing by itself.
- `tools_dir() -> Path` MUST return, in this order: the value of `FENOLITE_TOOLS_DIR` (`TOOLS_ENV`) when it is set; `$XDG_CACHE_HOME/fenolite/tools` when that variable is set; `~/Library/Caches/fenolite/tools` when `sys.platform` is `darwin`; `%LOCALAPPDATA%\fenolite\tools` when it is `win32` and the variable is set; `~/.cache/fenolite/tools` otherwise.
- A relative `FENOLITE_TOOLS_DIR` MUST raise `ValueError` naming the variable; the command line maps it to exit 2.
- `tool_path(name, file) -> Path` MUST return `tools_dir() / name / file`.
- Neither function MUST create a folder, read a file or run a program. The environment MUST be read at each call.
- The module MUST import the standard library only (`package-layering`: `core`).
- `docs/routing.md` MUST name the folder per platform and the variable.

#### Scenario: Explicit folder
- **GIVEN** `FENOLITE_TOOLS_DIR` set to an absolute folder of the test
- **WHEN** `uv run pytest tests/unit/core/test_tools.py -k explicit` calls `tool_path("freerouting", "freerouting-2.4.1.jar")`
- **THEN** it returns that folder joined with `freerouting/freerouting-2.4.1.jar`, and the folder was not created

#### Scenario: Platform defaults
- **GIVEN** `FENOLITE_TOOLS_DIR` unset, and `sys.platform`, `XDG_CACHE_HOME`, `LOCALAPPDATA` and the home folder patched in turn
- **WHEN** `tools_dir()` is called
- **THEN** it returns the folder of the rule above for each of the four cases

#### Scenario: Relative folder refused
- **GIVEN** `FENOLITE_TOOLS_DIR` set to `tools`
- **WHEN** `fenolite fetch freerouting --dry-run` runs
- **THEN** the exit code is 2 and the message names `FENOLITE_TOOLS_DIR`

### Requirement: Fetched tools decision record
`docs/adr/0007-fetching-external-tools.md` SHALL record the rule under which Fenolite downloads an external tool, with the six sections of `docs/adr/README.md` and the status `Accepted`, dated with the maintainer's decision of 2026-10-05, which he confirmed on 2026-10-07. The record MUST name the row of "Open decisions" in `docs/roadmap.md` that holds the decision, and that row MUST exist.
- The decision MUST state: a download happens only inside `fenolite fetch`, only with `--confirm`, only from the address of a table row whose source is registered in `docs/evidence/sources.md`, and only when size and SHA-256 match the row; Fenolite bundles no tool and imports nothing from one; a tool under a copyleft licence stays a separate program (ADR-0004); no other command opens a network connection for a tool.
- The alternatives MUST name bundling the jar, a download on the first `route`, and leaving the install manual, each with the reason it was not chosen.
- `docs/adr/0006-specctra-and-freerouting.md` MUST gain one dated line under its Decision 3 that says the jar may be downloaded by `fenolite fetch` (ADR-0007), and its other sentences MUST stay.
- `docs/adr/README.md` MUST list ADR-0007, and `LEGAL-ANNEX.md` MUST hold a row for the command, the ADR and the files they touch.

#### Scenario: Record present and well formed
- **WHEN** `uv run pytest tests/unit/test_adrs.py tests/unit/test_legal_docs.py` runs
- **THEN** it passes with ADR-0007 listed, its six sections present and its status `Accepted`, and the row number that the record names is a row of "Open decisions" that holds `fenolite fetch`

#### Scenario: Earlier decision amended, not rewritten
- **WHEN** `git diff` of `docs/adr/0006-specctra-and-freerouting.md` is read for this change
- **THEN** it adds one line that names ADR-0007 and removes none

### Requirement: Router runs reported for progress and resumption
`fenolite.routing.protocol` SHALL let a router report each of its tool processes while it works, so that the command can show progress and keep what finished. "Router protocol" is unchanged: the new fields have defaults, and a router that ignores them stays valid.
- `FinishedRun(nets: tuple[str, ...], tracks: tuple[Track, ...] = (), arcs: tuple[Arc, ...] = (), vias: tuple[Via, ...] = (), tier: int = 0, seconds: float = 0.0)` MUST be a frozen dataclass on `core` and `model` types: the copper that one tool process added and the nets it routed.
- `RoutingJob` MUST gain `on_run: Callable[[FinishedRun], None] | None = None` and `progress: Progress = NULL_PROGRESS` (`fenolite.core.progress`).
- A plugin that starts tool processes MUST report each process as one unit of progress (`step` when it starts, `done` when it ends), and MUST call `on_run` once for each process that ended with copper, with that copper, before it starts the next process. A process that failed, was cut by a time limit or gave no copper MUST NOT be reported through `on_run`.
- The KiCadRoutingTools plugin MUST treat each of its processes as a unit: one per group of nets, and one per net with `--router-option group-nets=1`. The Freerouting plugin MUST treat each tier as a unit: its one process for a job without tiers, and the optimizer run of `optimize=on` belongs to the unit of its tier. `FinishedRun.tier` is the tier of the nets of the run. The built-in direct router starts no process and MUST call neither.
- The copper of all `FinishedRun`s of one `route` call MUST equal the copper of its `RoutingResult`.
- `fenolite.routing` MUST still import only `core`, `model` and `geometry`.

#### Scenario: One call per finished process
- **GIVEN** the fake KiCadRoutingTools of the routing tests, routing three nets with one process per net (`group-nets=1`), of which the second fails
- **WHEN** `uv run pytest tests/unit/routing/test_finished_runs.py` routes a job with a recording `on_run` and a recording `Progress`
- **THEN** `on_run` was called twice, for the first and the third net, each before the next process started; the reporter saw three `step` and three `done` records; and the tracks and vias of the two runs together equal those of the result

#### Scenario: A router that ignores the fields
- **WHEN** the direct router routes the same job
- **THEN** `on_run` is never called, and the result equals the result of a job without the two fields

### Requirement: Plane and routing layers in a routing job
`routing.protocol.RoutingJob` SHALL gain the field `plane_layers: tuple[str, ...] = ()` after `extra`, and `JobNet` SHALL gain `layers: tuple[str, ...] | None = None` after `via_drill`; the fields of change c0109 (`RoutingJob.budget`, `JobNet.tier`) stay last, after them. This extends "Router protocol" as "Job extras" did: a job built without them MUST mean what it meant before.
- `plane_layers` names the copper layers, in stack order, that hold planes and take no track. `JobNet.layers` is `None` when the net may use every routing layer, else the non-empty tuple, in stack order, of the routing layers its tracks may use.
- `routing.layers.routing_layers(layers, plane_layers)` MUST return the members of `layers` that are not in `plane_layers`, in order.
- `routing.layers.allowed_layers(design, net, routing_layers)` MUST return the members of `routing_layers` that no `no_tracks` rule of `design.rules` forbids to the net (`rules-model`, "Track layer rules"): a rule of severity other than `ignore` forbids its `layers` when its `selector_a` matches `RuleSubject("track", net=<the net's name>, netclass=<its class name, or Default>)`. It MUST import only `core` and `model`.
- **Direct router.** `DirectRouter` MUST route a two-pad net on the first shared copper layer, in stack order, that is not in `plane_layers` and, when `layers` is not `None`, is in `layers`; a net without such a layer is unrouted. It still avoids nothing.
- **KiCadRoutingTools.** Its command line takes no layer or plane option, so the plugin MUST add one `route.constraint-not-sent` (warning) per run whose job has plane layers or a net with `layers`, naming them; the board and rules files of its run hold the row types and the track layer rules (`H-K-KRT-PLANES`). A rule set that `route` read from the project's rules file MUST be written into the run folder by `dru.write_rules`, which keeps its names, and not lowered again.
- `routing.codes.ISSUE_CODES` MUST gain `route.plane-net` (info), `route.no-layer` (warning), `route.constraint-not-sent` (warning) and `route.project-unread` (warning), which `cli/cmd_route.py` already emits, `docs/cli-contract.md` MUST document each, and `src/fenolite/cli/data/explain.toml` MUST hold an entry for each.

#### Scenario: Allowed layers from track layer rules
- **GIVEN** a six-layer design whose plane layers are `In1.Cu` and `In4.Cu`, and a `no_tracks` rule on `netclass HV` with `layers=("In2.Cu", "In3.Cu")`
- **WHEN** `uv run pytest tests/unit/routing/test_layers.py` calls `routing_layers` and `allowed_layers` for a net of `HV` and a net of `SIG`
- **THEN** the routing layers are `F.Cu`, `In2.Cu`, `In3.Cu`, `B.Cu`, the `HV` net gets `("F.Cu", "B.Cu")` and the `SIG` net all four

#### Scenario: Ignored rule
- **WHEN** the same rule has severity `ignore`
- **THEN** the `HV` net gets all four routing layers

#### Scenario: Direct router off a plane layer
- **GIVEN** a job with `plane_layers=("In1.Cu",)` and a two-pad net whose through-hole pads share every layer, with `layers=("B.Cu",)`
- **WHEN** `uv run pytest tests/unit/routing/test_direct.py -k layers` routes it
- **THEN** its one track lies on `B.Cu`

#### Scenario: KiCadRoutingTools told nothing
- **GIVEN** the fake tool of `tests/_fakerouter.py` and a job with `plane_layers=("In1.Cu",)`
- **WHEN** `uv run pytest tests/unit/routing/test_routingtools.py -k constraint` routes it
- **THEN** the result holds one `route.constraint-not-sent` naming `In1.Cu`, and the recorded arguments are those of a job without plane layers

### Requirement: Plane fan-out
`fenolite.backends.kicad.fanout.plan_fanout(design, pads, *, nets, plane_layers, outline, edge_clearance, clearance) -> FanoutPlan` SHALL join each SMD pad of the given plane nets to its plane with one track and one through via, by the deterministic search of this requirement (design, Decision 5). It MUST be pure: it reads no file and no environment variable and changes none of its arguments. It MUST import only the standard library, `core`, `model`, `geometry`, `backends.base` and modules of `backends.kicad`.
- `nets` maps each plane net's name to `FanoutSizes(width, via_diameter, via_drill, neck)`; `clearance(a, b)` gives the clearance between two `RuleSubject`s; `edge_clearance` is the board's edge clearance; `pads` are the board-frame pads.
- `plane_nets(design, plane_layers)` MUST return, sorted, the names of the nets that have a zone on a layer of `plane_layers`.
- **Pads.** In board footprint order then pad order, the pads without a drill of the nets of `nets` (one pass over the board, whatever the order of `nets`). A pad is joined, and skipped, when a via of its net overlaps its copper, or when a chain of its net's tracks and arcs on its layer runs from an end inside its copper, through equal end points or ends inside another pad of the net, to a via of the net or to a pad of the net with a drill; the copper made so far counts.
- **Candidates.** The outward direction runs from the footprint's position to the pad's position, or is the pad's +X turned by its board rotation when they coincide. The eight directions `k · 45°` from +X of the model frame are taken in order of their angle to it, equal angles by `k`. Along each, with a step `s` of a quarter of the via diameter rounded up to a whole micrometre, the first distance is the smallest multiple of `s` at which the via's copper keeps `neck` from its pad's copper, followed by eight more steps of `s`; each via centre is rounded to a whole micrometre.
- **Tests.** A candidate MUST pass all of these, decided exactly: the via's disc keeps `clearance` from every copper item of another net or of no net on every copper layer (pad copper, pad holes without copper, tracks, arcs, vias); it overlaps no other pad of its net and no other via; it lies inside the outline of a zone of its net on a plane layer by at least half its diameter; it keeps `edge_clearance` from every edge of `outline` and lies inside `outline[0]` and outside every other ring; it touches no keep-out that forbids vias on a copper layer; its drill keeps the `min` of a board-wide `hole_to_hole` rule from every other drill. The track from the pad's position to the via, of `width`, on the pad's layer, keeps `clearance` from every copper item of another net on that layer and crosses no keep-out that forbids tracks there. Zone fills are not obstacles.
- **Result.** The first candidate that passes, in direction order then distance order, MUST give one `Track` on the pad's layer and one through `Via` of the net, with ids derived from the net name and the geometry as `routing.merge.apply` derives them. When none passes, the pad MUST stay open with one `kicad.fanout.failed` (warning) naming the pad (`REF-NUMBER`), the net and the item that blocked its first candidate.
- `FanoutPlan` MUST hold `tracks`, `vias`, `pads` (the SMD pads considered), `joined` (those skipped as joined), `failed` and `issues`. `FANOUT_ISSUE_CODES` MUST be the closed table `{"kicad.fanout.failed": "warning"}`, named in `cli.explain.TABLES` with an entry for its code in `src/fenolite/cli/data/explain.toml`, and `EVIDENCE` `INFERRED` with `H-K-FANOUT`.

#### Scenario: One dog-bone per SMD pad
- **GIVEN** the bench of `tests/routing/_planebench.py` with `In1.Cu` and `In2.Cu` as plane layers, the nets `GND` and `VCC` with sizes 0.4 mm, 0.6 mm, 0.3 mm and a neck of 0.2 mm, and the clearance of the copper check's resolver
- **WHEN** `uv run pytest tests/unit/backends/kicad/test_fanout.py -k bench` calls `plan_fanout`
- **THEN** each of the six SMD pads of `GND` and `VCC` gets one track and one via, every via lies inside its net's zone, `failed` is empty, and `check_copper` on the design with the plan merged reports no finding

#### Scenario: Pads already joined
- **GIVEN** the same bench where `C1` pad `2` carries a via of `GND` inside its copper, and `C2` pad `2` is tied by a `GND` track to `U1` pad `4`
- **WHEN** `plan_fanout` runs
- **THEN** `joined` names `C1-2`, which gets no via; of `C2-2` and `U1-4`, the first in board order (`C2-2`: the built board lists its footprints by reference) gets one via and the other is in `joined` through the track

#### Scenario: A pad without room
- **GIVEN** the bench with a keep-out that forbids vias on every copper layer over the whole part `U1` and 2 mm around it
- **WHEN** `plan_fanout` runs
- **THEN** `U1-4` and `U1-8` are in `failed`, two `kicad.fanout.failed` warnings name them, their nets and the keep-out, and the other four pads get their vias

#### Scenario: Deterministic
- **WHEN** `plan_fanout` runs twice on the bench with `PYTHONHASHSEED=1` and `PYTHONHASHSEED=2`
- **THEN** the two plans are equal, item ids included

### Requirement: Freerouting plugin sends planes, layers and rules
The Freerouting plugin SHALL pass `job.plane_layers` as `plane_layers` and the `layers` of the job's nets as `net_layers` to `write_dsn`, and the job's design carries the rules that "Routing rules in design files" lowers. This extends "Freerouting plugin"; a job without plane layers, layer sets or rules MUST give the command line and file it gave before. The writer's issues MUST join the result's issues, as they do today.

#### Scenario: Recorded design file
- **GIVEN** `tests/_fakefreerouting.py`, a fake `java` that keeps the design file it is given, and a job of the bench with `plane_layers=("In1.Cu", "In2.Cu")`, `SIG1` with `layers=("F.Cu",)` and the rule `hv-sig`
- **WHEN** `uv run pytest tests/unit/routing/test_freerouting.py -k planes` routes it
- **THEN** the kept file holds `(layer In1.Cu (type power))`, a `plane` of `GND`, `(use_layer F.Cu)` and `class_class` for `HV` and `SIG`, and the arguments are those of a job without them
