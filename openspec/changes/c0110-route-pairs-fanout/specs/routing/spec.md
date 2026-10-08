## ADDED Requirements

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
`KicadRoutingToolsRouter.features` SHALL hold `pairs` once the pair outcomes of the gate hold ("Pair and escape routes pass the oracle", `kicad-oracle`), and the plugin SHALL route every job pair in its run folder, after the escape steps and before the single nets of the pair's tier, with
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

### Requirement: KiCadRoutingTools escapes parts
`KicadRoutingToolsRouter.features` SHALL hold `escape` once the escape outcomes of the gate hold for this router, and the plugin SHALL run, in job order and before every pair and net step, one step per escape request:
- kind `grid`: `bga_fanout.py <board> --component <ref> --output <out> --escape-method dogbone --nets <nets…> --layers <layers…> --track-width <w> --clearance <c> --via-size <d> --via-drill <drill> --plane-drop off --same-net-pad-clearance <c> --escalation off --no-fix-drc-settings`, adding `--diff-pairs <nets of the job pairs on the part…> --diff-pair-gap <gap>` when the part holds a pair;
- kind `perimeter`: `qfn_fanout.py <board> --output <out> --component <ref> --nets <nets…> --width <w> --clearance <c> --via-size <d> --via-drill <drill> --same-net-pad-clearance <c> --escalation off --no-fix-drc-settings`.
- `w`, `d` and `drill` MUST be the smallest values, and `c` the largest, among the `JobNet`s of the request; `layers` as for a pair step.
- When the router option `grid-step` is given, it MUST be passed to every escape step and to `route.py` alike; otherwise none of them gets it.
- Every escape step runs before the first tier and is a run of "Routing time budget" (c0109), inside the job's budget and listed in `RoutingResult.runs`. A step that exits non-zero or writes no board MUST give `route.tool-failed` (error) naming the part, and the next step MUST read the board of the step before it; a step stopped by the budget follows "Routing time budget" instead.
- Escape copper is lifted with the copper of the nets it belongs to; on a net that is not routed afterwards it MUST still be lifted, and the net MUST stay in `unrouted`.

#### Scenario: Arguments of an escape step
- **GIVEN** fake `bga_fanout.py` and `qfn_fanout.py` that record their arguments
- **WHEN** the plugin routes a job with the requests `U1` (perimeter, nets `Q01`, `Q02`) and `U2` (grid, net `B_A1`) and the option `grid-step=0.05`
- **THEN** `qfn_fanout.py` ran for `U1` and `bga_fanout.py` for `U2` before `route.py`, both with `--escalation off` and `--grid-step 0.05`, `bga_fanout.py` with `--escape-method dogbone` and `--plane-drop off`, and `route.py` with `--grid-step 0.05`

#### Scenario: A failed escape step
- **GIVEN** a fake `qfn_fanout.py` that exits 2
- **WHEN** the plugin routes the same job
- **THEN** the result holds `route.tool-failed` naming `U1`, and the next step read the input board

### Requirement: Freerouting declares no router feature
`FreeroutingRouter.features` SHALL be an empty `frozenset`, so a job never gives it a pair or an escape request: Freerouting 2.4.1 routes a pair as two single nets (`H-G-DSN-PAIR`), and its own fanout stage is a router option of "Freerouting plugin", not an escape step per part.

#### Scenario: No features
- **WHEN** `router_features(FreeroutingRouter())` is called
- **THEN** it gives an empty set

## MODIFIED Requirements

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
