# routing Specification

## Purpose
TBD - created by archiving change c0016-routing-plugins. Update Purpose after archive.
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

