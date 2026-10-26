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
`fenolite.routing.select.unrouted(design, open_nets, *, patterns=("*",), include_zone_nets=False) -> tuple[str, ...]` SHALL return, sorted, the names of the nets to route. `open_nets` is a collection of the names of the nets that have at least one open connection on `design` (`board-analyses`, "Open connections of a net"); the caller computes it, because `routing` may not import `analysis`:
- a net MUST have two or more pads on placed footprints and MUST be in `open_nets`; copper of its own MUST NOT exclude it;
- a net that a zone carries MUST be left out unless `include_zone_nets` is true;
- `patterns` are `fnmatch` globs on the net name; a pattern starting with `!` excludes, and a net is selected when it matches a non-excluding pattern and no excluding one.

`select.rip(design, nets, *, keep=frozenset()) -> tuple[Design, int]` SHALL remove the tracks, arcs and vias of those nets whose `locked` is false and whose id is not in `keep`, and return their count. Every other item MUST stay, in its order.

#### Scenario: Unrouted nets
- **GIVEN** an authored design with nets `A` (two pads, no copper), `B` (two pads joined by one track), `S` (two pads and a 3 mm track from one of them), `GND` (three pads, one zone) and `NC` (one pad), and `open_nets` computed by `analysis.connectivity.connectivity`
- **WHEN** `uv run pytest tests/unit/routing/test_select.py` calls `unrouted(design, open_nets)`
- **THEN** it returns `("A", "S")`, and `("A", "GND", "S")` with `include_zone_nets=True`

#### Scenario: Patterns
- **WHEN** `unrouted(design, open_nets, patterns=("*", "!A"))` is called on the same design
- **THEN** it returns `("S",)`

#### Scenario: Rip
- **GIVEN** the same design, where `B` also holds a second track with `locked=True` that joins nothing
- **WHEN** `rip(design, ("B", "S"), keep=frozenset({<id of the track of S>}))` is called
- **THEN** the unlocked track of `B` is gone, the locked track of `B` and the track of `S` stay, and the count is 1

#### Scenario: The old call fails loudly
- **WHEN** `unrouted(design)` is called without `open_nets`
- **THEN** it raises `TypeError`

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
- **Run.** The plugin MUST write the design file with `write_dsn` and `others="netless"` (`specctra-dsn`, "Nets outside the routing job in design files"), from the job's `extra` (`board_pads`, `outline`), into a fresh temporary directory and run `java -jar <jar> -de board.dsn -do board.ses -mp <passes> -mt 1 -da --gui.enabled=false --router.automatic_neckdown=false --router.optimizer.enabled=false` there, with `HOME` set to that directory and the time left of the job's budget ("Routing time budget"). `-da` and `--router.automatic_neckdown=false` MUST always be passed and MUST NOT be removable through router options (`H-G-DSN-NARROW`). The router options are `max-passes=N` (default 20), `optimize=on|off` (default `off`) and `fanout=on|off` (default `on`): `fanout=off` MUST add `--router.fanout.enabled=false`, and `fanout=on` MUST add nothing, the stage being on by default (S-0222; `H-G-DSN-FANOUT`); any other option, and a value that is not valid, MUST be ignored with `route.option-ignored` (warning), a code of `routing.codes.ISSUE_CODES`. When the design file keeps nets outside the job declared for their class clearance, the result MUST hold one `route.net-declared` (info), also a code of `routing.codes.ISSUE_CODES` with its entry in `explain.toml`, whose message gives their count and names the first five. The board defaults passed to `write_dsn` are the values of the design's `Default` class, else 0.2 mm width and clearance and a 0.6 mm via with a 0.3 mm drill, as in `fenolite route`.
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
- **THEN** the result holds the session's tracks, and the recorded arguments hold `-de`, `-do`, `-mt 1`, `-da`, `--gui.enabled=false`, `--router.automatic_neckdown=false` and `--router.optimizer.enabled=false`, and no fanout setting

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

#### Scenario: Fanout stage off, neck-down never on
- **WHEN** `uv run pytest tests/unit/routing/test_freerouting.py -k fanout` routes the two-pad job with the options `fanout=off` and `automatic_neckdown=true`, and again with `fanout=maybe`
- **THEN** the first recorded arguments hold `--router.automatic_neckdown=false` and `--router.fanout.enabled=false`, with one `route.option-ignored` naming `automatic_neckdown`; the second hold no fanout setting, with one `route.option-ignored` naming `fanout`

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

### Requirement: Router copper on open nets
A router MAY return copper for a net that it lists in `unrouted`, and the `routed` and `unrouted` of a `RoutingResult` SHALL be read as the router's own claim. `fenolite route` takes its verdict from the open connections after the merge (`cli-contract`, "Route command"); it MUST merge every valid item of a result, the copper of nets that stay open included, and MUST NOT remove copper that a router returned because its net stays open. A router MUST NOT be given a net that has no open connection. `docs/routing.md` MUST tell plugin authors both rules.

#### Scenario: Partial copper is merged
- **GIVEN** `two_pads.kicad_pcb` and a test router that returns one 2 mm track from `J1-1` on `ROUTE_ME` and lists that net in `unrouted`
- **WHEN** `uv run pytest tests/unit/cli/test_route_cmd.py -k partial` runs `fenolite route <board> --router <test router> --confirm`
- **THEN** the written board holds the track, `result.unrouted` is `["ROUTE_ME"]`, and the issues hold one `route.partial` naming `ROUTE_ME`

#### Scenario: A closed net is not given to the router
- **GIVEN** a board with a net whose pads are joined and a net that is open, and a test router that records its job
- **WHEN** `fenolite route <board> --router <test router> --dry-run` runs
- **THEN** the recorded job holds only the open net

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

### Requirement: Pairs and escape in a routing job
`fenolite.routing.protocol` SHALL define, as frozen dataclasses on `core` types only:
- `JobPair(name: str, positive: str, negative: str, width: Nm, gap: Nm, via_gap: Nm | None = None, skew_max: Nm | None = None)`: two nets of the job routed as one differential pair;
- `JobEscape(ref: str, kind: str, pitch: Nm, nets: tuple[str, ...])`: a part whose pads the router escapes before it routes, `kind` being `grid` or `perimeter`;

and SHALL add to `RoutingJob`, after every field that exists when this change is archived, `pairs: tuple[JobPair, ...] = ()` and `escape: tuple[JobEscape, ...] = ()`.
- `positive` and `negative` MUST name nets of `job.nets`, and a net MUST belong to at most one pair. `nets` of an escape request MUST name nets of `job.nets`.
- The four codes of "Pairs and escape in the route command" (`cli-contract`) MUST each have an entry in `src/fenolite/cli/data/explain.toml`.
- `routing.protocol.ROUTER_FEATURES` MUST be `frozenset({"pairs", "escape"})`. `router_features(router) -> frozenset[str]` MUST return the router's attribute `features` when it is a `frozenset` of members of `ROUTER_FEATURES`, and an empty set when the attribute is missing or holds anything else. The `Router` protocol MUST NOT gain the attribute, so a router written before this change keeps satisfying it.
- A job given to a router whose features lack `pairs` MUST hold no pair, and one given to a router whose features lack `escape` MUST hold no escape request; the command removes them ("Pairs and escape in the route command", `cli-contract`).
- The built-in `direct` router MUST declare no feature.

#### Scenario: A job built as before
- **WHEN** `uv run pytest tests/unit/routing/test_protocol.py -k pairs` builds `RoutingJob(design, nets, layers)`
- **THEN** its `pairs` and `escape` are empty, and it equals a job built with `pairs=()` and `escape=()`

#### Scenario: A router without features
- **GIVEN** a test router class that defines `name`, `description`, `sends_data_offsite`, `available` and `route` only, and one whose `features` is the list `["pairs"]`
- **WHEN** `router_features` is called on each and on `DirectRouter()`
- **THEN** all three give an empty set, and `uv run pyright src` reports no error for `_ROUTER: Router = DirectRouter()`

### Requirement: Pair selection for routing
`fenolite.routing.pairs.job_pairs(design, candidates) -> tuple[tuple[JobPair, ...], tuple[str, ...], tuple[Issue, ...]]` SHALL return the differential pairs among the candidate nets, the candidates that stay single nets, and one issue per pair left out, using the name rule of `fenolite.model.pairs` (c0104), which is how KiCad's DRC and router find pairs.
- **Pairs.** Two nets of the design form a pair when `pair_base(positive, negative)` is not `None`; the positive net is the one whose polarity is `P` or `+`.
- **Both selected.** When only one net of a pair is a candidate, that net MUST be removed from the candidates with one `route.pair-skipped` (warning) that names the pair and the net that is not selected.
- **One class.** When the two nets have different net classes, both MUST be removed with `route.pair-skipped` naming both classes.
- **Values.** `width`, `gap` and `via_gap` MUST be the class's `diff_pair_width`, `diff_pair_gap` and `diff_pair_via_gap` (c0104), each falling back to the value of the class named `Default`, without letter case; a pair left without a width or a gap MUST be removed with `route.pair-skipped` naming the missing value. No value is invented.
- **Skew.** `skew_max` MUST be the `max` of the `diff_pair_skew` rule (c0104) that governs the positive net in the order in which the rules are lowered (`rules-model`, "Lowered rules follow priority"), ignoring rules of severity `ignore`, and `None` without one.
- `name` MUST be `<positive>/<negative>`. Pairs MUST be sorted by the positive net's name; the result MUST be equal for equal inputs.

#### Scenario: Names that pair
- **GIVEN** a design whose candidates are `USB_P`, `USB_N`, `D_P0`, `D_N0` and `SDA`, all in class `HS` with `diff_pair_width` 0.2 mm and `diff_pair_gap` 0.15 mm
- **WHEN** `uv run pytest tests/unit/routing/test_pairs.py -k names` calls `job_pairs`
- **THEN** it gives the pairs `D_P0/D_N0` and `USB_P/USB_N` with width 200 000 nm and gap 150 000 nm, the single candidate `SDA`, and no issue

#### Scenario: One net selected
- **GIVEN** the same design with `USB_N` not among the candidates
- **WHEN** `job_pairs` is called
- **THEN** `USB_P` is neither a pair member nor a single candidate, and one `route.pair-skipped` names `USB_P/USB_N` and `USB_N`

#### Scenario: Values from the Default class
- **GIVEN** a pair whose class has no pair values, and a `Default` class with `diff_pair_width` 0.2 mm and `diff_pair_gap` 0.25 mm
- **WHEN** `job_pairs` is called
- **THEN** the pair gets width 200 000 nm and gap 250 000 nm; without the `Default` values it is left out with `route.pair-skipped` naming the gap and the width

#### Scenario: Skew limit from a rule
- **GIVEN** a priority-1 `diff_pair_skew` rule on `diff_pair USB_` with max 0.1 mm, and a priority-0 `diff_pair_skew` rule on `diff_pair *` with max 0.5 mm
- **WHEN** `job_pairs` is called
- **THEN** the pair `USB_P/USB_N` has `skew_max` 100 000 nm, and `D_P0/D_N0` has 500 000 nm

### Requirement: Escape requests for routing
`fenolite.routing.escape` SHALL provide:
- `escape_kind(points) -> str`: for the centres of a part's pads without a drill, `grid` when one centre has, at the smallest distance `p` between two centres (within 1 µm), four neighbours that lie in two orthogonal directions, both ways; `perimeter` otherwise. It MUST use integer arithmetic only and MUST give the same kind for a part turned by any angle.
- `requests(parts, patterns, nets) -> tuple[tuple[JobEscape, ...], tuple[Issue, ...]]`: `parts` maps each reference to its pads (position, net, drill), `patterns` are the `--escape` values, `REF` as an `fnmatch` glob on references, optionally followed by `=grid` or `=perimeter`, which overrides the kind. A request MUST name the job nets that have a pad on the part, sorted, and the part's pitch `p`. A pattern that matches no part, or a part without a job net, MUST give `route.escape-skipped` (warning) naming the pattern or the part; any other suffix MUST raise `ValueError`.
- Requests MUST follow reference order and be equal for equal inputs.

#### Scenario: A BGA and a QFN
- **GIVEN** pad centres written in the test: an 11 × 11 grid of 0.8 mm pitch, and the 48 pads of a QFN of 0.5 mm pitch with a centre pad, each placed at 0° and turned by 45°
- **WHEN** `uv run pytest tests/unit/routing/test_escape.py -k kind` calls `escape_kind`
- **THEN** the BGA gives `grid` with pitch 800 000 nm and the QFN `perimeter` with pitch 500 000 nm, at both angles

#### Scenario: Patterns
- **GIVEN** parts `U1` (QFN, two job nets) and `U2` (BGA, no job net)
- **WHEN** `requests` is called with `("U1", "U2", "J9=grid")`
- **THEN** it gives one request for `U1` with kind `perimeter` and its two nets, and two `route.escape-skipped` warnings naming `U2` and `J9`

### Requirement: KiCadRoutingTools routes pairs
`KicadRoutingToolsRouter.features` SHALL hold `pairs` once the pair outcomes of the gate hold ("Pair and escape routes pass the oracle", `kicad-oracle`), and the plugin SHALL route every job pair in its run folder, before the single nets of the pair's tier, with
`<python> <path>/py_router/route_diff.py <board> <routed> --nets <positive> <negative> --track-width <width> --diff-pair-gap <gap> --clearance <c> --via-size <d> --via-drill <drill> --layers <layers…> --no-gnd-vias --keep-input-copper --same-net-pad-clearance <c> --escalation off --no-fix-drc-settings`,
adding `--diff-pair-intra-match --length-match-tolerance <skew_max>` when the pair has a `skew_max`.
- `c`, `d` and `drill` MUST be the values of the positive net's `JobNet`; `layers` MUST be that net's `layers` (c0107) when set, else the job's layers without its plane layers.
- Each step MUST read the board that the previous step wrote, and MUST be one process. A step is a run of "Routing time budget" (c0109): it gets the time left of the job's budget, is listed in `RoutingResult.runs`, keeps its copper when it ends in time, and is `cut` or never started as that requirement states. The pair steps of a tier ("Routing tiers") run before the groups of that tier ("KiCadRoutingTools plugin"); a pair whose two nets have different tiers takes the lower one.
- Only a pair whose names take one of the forms of `routingtools.PAIR_NAME_FORMS`, the forms that the probe `krt-pair-names` recorded as routed coupled, MUST be sent; any other pair MUST be routed by no step and MUST give `route.pair-skipped` naming the form the tool does not pair.
- The lift MUST be the plugin's: copper whose uuid the step's input lacks, on the pair's two nets only. A pair whose two nets got no copper MUST be in `unrouted`, with `route.unrouted` per net.
- The options `polarity-swap-nets`, `impedance`, `rip-existing-nets` and `force-reroute`, given through `--router-option`, MUST NOT reach any step and MUST give `route.option-ignored` (warning).

#### Scenario: Arguments of a pair step
- **GIVEN** `tests/_fakerouter.py` extended with a fake `route_diff.py` that records its arguments and adds one segment on each named net
- **WHEN** `uv run pytest tests/unit/routing/test_routingtools.py -k pair` routes a job with the pair `USB_P/USB_N` (width 0.2 mm, gap 0.15 mm, `skew_max` 0.1 mm) and the single net `SDA`
- **THEN** `route_diff.py` ran once before `route.py`, its arguments hold `--nets USB_P USB_N`, `--track-width 0.2`, `--diff-pair-gap 0.15`, `--no-gnd-vias`, `--escalation off`, `--diff-pair-intra-match` and `--length-match-tolerance 0.1`, and the result holds the two segments with the pair's net ids

#### Scenario: A name form the tool does not pair
- **WHEN** the plugin routes a job with the pair `DP1/DN1`
- **THEN** no step names `DP1`, the result holds `route.pair-skipped` naming the pair, and `DP1` and `DN1` are in `unrouted`

#### Scenario: A swap option refused
- **WHEN** the plugin routes with `--router-option polarity-swap-nets=*`
- **THEN** no recorded argument holds `polarity-swap-nets`, and the result holds `route.option-ignored` naming it

### Requirement: Freerouting declares no router feature
`FreeroutingRouter.features` SHALL be an empty `frozenset`, so a job never gives it a pair or an escape request: Freerouting 2.4.1 routes a pair as two single nets (`H-G-DSN-PAIR`), and its own fanout stage is a router option of "Freerouting plugin", not an escape step per part.

#### Scenario: No features
- **WHEN** `router_features(FreeroutingRouter())` is called
- **THEN** it gives an empty set
