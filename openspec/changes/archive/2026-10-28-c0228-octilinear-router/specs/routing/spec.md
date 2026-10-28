## ADDED Requirements

### Requirement: Octilinear router plugin
A routing plugin `fenolite.routing.octilinear.OctilinearRouter` SHALL route short connections between pads of the selected nets in copper whose every segment runs at 0°, 45° or 90°, and SHALL be registered as `octilinear` in the entry-point group `fenolite.routers`. Its features MUST be `pairs` and `short`; it MUST run no process, MUST place no via and MUST send nothing offsite.

#### Scenario: Listed with its features
- **WHEN** `uv run pytest tests/unit/routing/test_octilinear.py -k registry` reads `routers()` and `router_features`
- **THEN** `octilinear` is listed, available, with the features `pairs` and `short`

### Requirement: Octilinear connections
The connections of a net SHALL be the edges of a minimum spanning tree over its board-frame pads, pads joined by copper of the net counting as one group, by squared distance with ties by `REF-NUMBER`, routed shortest first, each between the two pad centres on a copper layer where both pads have copper, not a plane layer and allowed for the net. Without board-frame pads in `extra` the plugin MUST route nothing and give `route.tool-failed`.

#### Scenario: Three pads, two connections
- **GIVEN** a net of three pads in a row, the first two joined by a track
- **WHEN** the plugin routes it
- **THEN** it adds the one connection from the joined group to the third pad

### Requirement: Octilinear shapes
For each connection the plugin SHALL try, in this order and each on every allowed layer in stack order before the next: a straight segment when the two centres lie on one 0°, 45° or 90° line; 45° then straight; straight then 45°; the L through `(b.x, a.y)`; the L through `(a.x, b.y)`. It MUST accept the first shape that passes "Octilinear acceptance", with the net's width.

#### Scenario: A gate loop routed octilinear
- **GIVEN** the authored bench of `tests/_octibench.py`: a driver and a switch, the nets `GATE` and `KSRC` unrouted, and a 0.3 mm clearance
- **WHEN** `uv run pytest tests/unit/routing/test_octilinear.py -k gate` routes them with `fenolite route <board> --router octilinear --nets GATE --nets KSRC --confirm`
- **THEN** both nets are complete, every segment angle is a multiple of 45°, no joint is acute, and the copper check finds nothing new

### Requirement: Octilinear acceptance
A shape SHALL be accepted only when each segment keeps, from every other net's pad copper, track, arc, via and job copper on its layer and from every other net's hole, the clearance in force (`extra["clearance"]`, else the larger class clearance) plus 2 µm, keeps the board-wide `edge_clearance` from every outline ring, and makes no acute angle with a track of its net that ends at the same pad centre. Zone fills MUST NOT be obstacles.

#### Scenario: A pad in the way
- **GIVEN** a pad of another net on the straight line between the two pads of a connection
- **WHEN** the plugin routes it
- **THEN** the straight shape is refused and a bent shape that keeps the clearance is placed

### Requirement: Octilinear length limit
A shape longer than `--router-option max-length=LENGTH` (default 20 mm; the sum of its segments) MUST NOT be tried. A connection whose every shape is longer MUST stay open with one `route.unrouted` naming its pads and the limit, and MUST NOT be searched further. An option that does not parse MUST give `route.option-ignored` and keep the default.

#### Scenario: Too long stays open
- **GIVEN** a connection of 60 mm between two pads
- **WHEN** the plugin routes it with the default options
- **THEN** the connection stays open and the result holds one `route.unrouted` naming it

### Requirement: Octilinear rounds
The plugin SHALL route the connections in rounds, at most `--router-option rounds=N` (default 3): each round starts from the board without the job's copper, with the connections that failed for lack of room first. It MUST keep the round that routed the most connections, the earliest of equals, and MUST NOT remove copper that it did not place.

#### Scenario: A blocked connection goes first
- **GIVEN** two connections where the first routed blocks every shape of the second, and the second routed first leaves room for the first
- **WHEN** the plugin routes them with `rounds=1`, then with the default
- **THEN** one connection stays open with `rounds=1`, and both are routed with the default

### Requirement: Octilinear pairs
A pair of the job SHALL be routed as two tracks of the pair width, parallel at the pair's gap or wider by at most 5 nm (rounding up), along an offset of one shape between the middles of its two ends, joined to the pads by entries that start at the coupled part, with the positive net on one side at both ends. A pair of other than two pads per net, or that no shape routes, MUST stay open with `route.pair-not-routed`.

#### Scenario: A sense pair
- **GIVEN** the bench's pair `SNS_P`/`SNS_N` of a class with pair width 0.2 mm and gap 0.2 mm
- **WHEN** `uv run pytest tests/unit/routing/test_octilinear.py -k pair` routes it
- **THEN** both nets are complete, and the coupled tracks keep a gap of 0.2 mm to 0.2 mm + 2 nm

### Requirement: Octilinear copper check
With `extra["copper_check"]`, the plugin SHALL judge the board before and after its copper and remove the copper of every connection (both nets for a pair) of which an item is named by a new finding, with one `route.check-refused` per connection. Its result MUST be planned only after this check.

#### Scenario: A finding refused
- **GIVEN** a copper check that reports a new finding on the job's track of net `GATE`
- **WHEN** the plugin routes
- **THEN** the result holds no copper of that connection and one `route.check-refused` naming `GATE`

### Requirement: Octilinear codes
`route.pair-not-routed` and `route.check-refused` SHALL be warnings of `ISSUE_CODES`, each with an entry of `src/fenolite/cli/data/explain.toml`, and documented in `docs/cli-contract.md`, "route". Equal inputs MUST give equal results, whatever `--seed`.

#### Scenario: Codes explained
- **WHEN** `uv run pytest tests/unit/cli/test_explain_cmd.py tests/unit/routing -k codes` runs
- **THEN** both codes have an entry and are documented

### Requirement: Clearance and copper check in job extras
`fenolite route` SHALL add to `RoutingJob.extra` `clearance`, the clearance in force between two `RuleSubject`s under the project's rules, and `copper_check`, a callable that judges a design with `check_copper`, the project's rules, the board edge and the board-frame pads, zone fills left out, and gives each finding as `(code, layer, sorted item ids, gap)`.

#### Scenario: Extras of the route command
- **GIVEN** a test router that records its job
- **WHEN** `uv run pytest tests/unit/routing/test_octilinear.py -k extras` runs `fenolite route` with it
- **THEN** the recorded `extra` holds `clearance` and `copper_check`, and `copper_check` of the board as read gives its findings

## MODIFIED Requirements

### Requirement: Pairs and escape in a routing job
`fenolite.routing.protocol` SHALL define, as frozen dataclasses on `core` types only:
- `JobPair(name: str, positive: str, negative: str, width: Nm, gap: Nm, via_gap: Nm | None = None, skew_max: Nm | None = None)`: two nets of the job routed as one differential pair;
- `JobEscape(ref: str, kind: str, pitch: Nm, nets: tuple[str, ...])`: a part whose pads the router escapes before it routes, `kind` being `grid` or `perimeter`;

and SHALL add to `RoutingJob`, after every field that exists when this change is archived, `pairs: tuple[JobPair, ...] = ()` and `escape: tuple[JobEscape, ...] = ()`.
- `positive` and `negative` MUST name nets of `job.nets`, and a net MUST belong to at most one pair. `nets` of an escape request MUST name nets of `job.nets`.
- The four codes of "Pairs and escape in the route command" (`cli-contract`) MUST each have an entry in `src/fenolite/cli/data/explain.toml`.
- `routing.protocol.ROUTER_FEATURES` MUST be `frozenset({"pairs", "escape", "short"})`; `short` marks a router of short connections, not of whole boards (c0228). `router_features(router) -> frozenset[str]` MUST return the router's attribute `features` when it is a `frozenset` of members of `ROUTER_FEATURES`, and an empty set when the attribute is missing or holds anything else. The `Router` protocol MUST NOT gain the attribute, so a router written before this change keeps satisfying it.
- A job given to a router whose features lack `pairs` MUST hold no pair, and one given to a router whose features lack `escape` MUST hold no escape request; the command removes them ("Pairs and escape in the route command", `cli-contract`).
- The built-in `direct` router MUST declare no feature.

#### Scenario: A job built as before
- **WHEN** `uv run pytest tests/unit/routing/test_protocol.py -k pairs` builds `RoutingJob(design, nets, layers)`
- **THEN** its `pairs` and `escape` are empty, and it equals a job built with `pairs=()` and `escape=()`

#### Scenario: A router without features
- **GIVEN** a test router class that defines `name`, `description`, `sends_data_offsite`, `available` and `route` only, and one whose `features` is the list `["pairs"]`
- **WHEN** `router_features` is called on each and on `DirectRouter()`
- **THEN** all three give an empty set, and `uv run pyright src` reports no error for `_ROUTER: Router = DirectRouter()`
