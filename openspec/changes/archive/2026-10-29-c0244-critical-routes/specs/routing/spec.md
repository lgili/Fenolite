## ADDED Requirements

### Requirement: Role routes in a routing job
`fenolite.routing.protocol` SHALL define the frozen dataclasses `JobRoleEnd` and `JobRoleRoute` (group, kind, tier, net, ends, width, layers, vias, isolated, aggressors, keep_away, partner, gap, loop, key) on `core` types only, and `RoutingJob.roles: tuple[JobRoleRoute, ...] = ()` after `escape`. A router whose features lack `roles` MUST get no role route.

#### Scenario: A job built as before
- **WHEN** `uv run pytest tests/unit/routing/test_protocol.py -k roles` builds `RoutingJob(design, nets, layers)`
- **THEN** its `roles` is empty and the job equals one built with `roles=()`

### Requirement: Role outcomes in a routing result
`fenolite.routing.protocol` SHALL define the frozen dataclass `RoleOutcome` (key, group, status, reason, form, layer, length, vias, runs, via points, blockers, detail) and `RoutingResult.roles: tuple[RoleOutcome, ...] = ()` after `not_attempted`. A router in role mode MUST give one outcome per role route, in the order of `job.roles`.

#### Scenario: A result built as before
- **WHEN** `uv run pytest tests/unit/routing/test_protocol.py -k roles` builds `RoutingResult()`
- **THEN** its `roles` is empty and it equals a result built with `roles=()`

### Requirement: Octilinear role tiers
With a non-empty `job.roles`, `OctilinearRouter` SHALL route only the role routes, in tiers 0 (gate loops) and 1 (Kelvin pairs), each tier by group name then key, the routes of one group as one unit routed whole or not at all. Rounds MUST reorder failed units within their tier only, and earlier tiers' copper MUST be fixed.

#### Scenario: Kelvin pair after the gate return
- **GIVEN** an authored bench with one gate loop and one Kelvin pair whose straight route would cross the gate return's
- **WHEN** `uv run pytest tests/unit/routing/test_roleroute.py -k tiers` routes the job
- **THEN** the gate return is routed first and straight, and the pair avoids it

### Requirement: Octilinear role ends
A role route SHALL end at `JobRoleEnd.at`, not at the pad centre. For a Kelvin route the element end MUST lie on the inner half of the sense pad, at `c + u·(L/2 − w/2 − 2 µm)` along the axis `u` to the other sense pad, or at the centre when that offset is not positive.

#### Scenario: Entry on the inner half
- **GIVEN** a 2512 two-pad shunt and an amplifier on the authored bench
- **WHEN** `uv run pytest tests/unit/routing/test_roleroute.py -k entry` routes its Kelvin pair
- **THEN** each track end lies inside its pad with an offset `t > 0` toward the other pad

### Requirement: Octilinear isolated branches
For an `isolated` role route, every item of its own net (pad copper, track, arc, via and zone outline on its layer) other than its two end pads SHALL be an obstacle at the clearance in force. A connection whose every shape is refused by this test MUST report reason `isolation`.

#### Scenario: A sense branch beside its own pour
- **GIVEN** a Kelvin pair of the power nets `VA` and `VB` whose shortest shapes cross the outline of a `VB` zone
- **WHEN** `uv run pytest tests/unit/routing/test_roleroute.py -k isolated` routes it
- **THEN** the placed `VB` branch does not touch the zone outline

### Requirement: Octilinear switching keep-away
A role route with aggressors SHALL keep `keep_away` from aggressor copper and zone outlines on its layer, and MUST NOT overlap aggressor copper or zone outlines on an adjacent copper layer. A connection whose every clear shape breaks this MUST report reason `near-switching`.

#### Scenario: A pair over a switch-node pour
- **GIVEN** a bench whose sense pair's straight path runs over a switch-node zone on the adjacent layer
- **WHEN** `uv run pytest tests/unit/routing/test_roleroute.py -k keepaway` routes it with `z-shapes=off`, then with the default
- **THEN** the first run reports `near-switching` and the second places the pair clear of the zone

### Requirement: Octilinear Z shapes
In role mode the router SHALL try, after c0228's five shapes, at most 8 Z shapes per layer (90° corners, no acute joint) whose middle segment runs on a line taken from the partner's segments and from the keep-away and blocking bounding boxes. `--router-option z-shapes=off` MUST turn them off; a job without role routes MUST keep its five shapes and bytes.

#### Scenario: Plain jobs unchanged
- **WHEN** `uv run pytest tests/unit/routing/test_octilinear.py` runs after the role mode lands
- **THEN** every existing octilinear test passes with the same copper

### Requirement: Octilinear role cost
Among the accepted shapes of a gate route the router SHALL keep the one of least gate-loop area (the absolute shoelace area of its centre polyline closed by the route's loop points, the partner's placed polyline in place of its straight line), then the least length, then the first in shape order; among those of a Kelvin pair, the shortest centre line, then the first in shape order.

#### Scenario: The smaller loop wins
- **GIVEN** a bench gate loop whose drawn drive turns a corner, and whose return has several clear shapes
- **WHEN** `uv run pytest tests/unit/routing/test_roleroute.py -k smaller` routes it
- **THEN** the return takes the L inside the drive's L, whose loop encloses least, where c0228 would keep the first shape that passes

### Requirement: Octilinear gate pairs
A gate loop SHALL be routed as its open `gate-out` routes, then its open `gate-return`: side by side on the pad layer, with Z lines at the pair pitch beside the out route, else stacked under the out route on the adjacent layer through one via at each end when no side-by-side shape passes and the route may place two vias. A `ground` return net with a zone under the whole out route on the adjacent layer MUST NOT be routed, and its outcome MUST be `plane-return`.

#### Scenario: Stacked when the side is blocked
- **GIVEN** a bench gate loop with rings of another net's copper around its source pad and its return pad
- **WHEN** `uv run pytest tests/unit/routing/test_roleroute.py -k gate` routes it
- **THEN** the return runs under the out route on the adjacent layer with two vias, and its form is `stacked`

### Requirement: Octilinear role vias
A role route SHALL place at most its `vias`: 0 by default for `gate-out` and `kelvin`, 2 for `gate-return`, changed by the router options `gate-vias` and `kelvin-vias`. A connection whose ends share no allowed layer and which may place no via MUST report reason `no-layer`.

#### Scenario: No common layer
- **GIVEN** a Kelvin route whose shunt pads are on `F.Cu` and whose amplifier pads are on `B.Cu`
- **WHEN** it is routed with the defaults, then with `kelvin-vias=2`
- **THEN** the first gives `no-layer`, and the second places one via per branch

### Requirement: Role check in job extras
In role mode, `fenolite route` SHALL add `role_check` to `RoutingJob.extra`: a callable from a design to findings `(code, group, severity, measure)` from `fenolite.roles.judge`. The router MUST remove the whole copper of a group that has a new code or a larger measure after routing and give its routes the outcome `refused`, and the reply MUST hold one `route.role-refused` for the group; `roles.loop-open` MUST count as no finding.

#### Scenario: A worse group is removed
- **GIVEN** a test `role_check` that reports a new `roles.near-switching` on the bench's Kelvin pair `kelvin_R1` after routing
- **WHEN** `uv run pytest tests/unit/routing/test_roleroute.py -k refused` routes the job
- **THEN** the result holds no copper of the pair's two routes, and both outcomes are `refused` with reason `role-check` and the finding

### Requirement: Role route codes
`ISSUE_CODES` SHALL hold `route.role-unrouted` and `route.role-refused` (warnings, which `--require-complete` turns into one `route.incomplete` error), and `route.role-unconfirmed`, `route.role-kept`, `route.role-placement` and `route.role-none` (info), each with an `explain.toml` entry and a row in `docs/cli-contract.md`. Equal inputs MUST give equal results.

#### Scenario: Codes explained
- **WHEN** `uv run pytest tests/unit/cli/test_explain_cmd.py tests/unit/routing -k codes` runs
- **THEN** the six codes have their severities, an entry and a documented row

## MODIFIED Requirements

### Requirement: Pairs and escape in a routing job
`fenolite.routing.protocol` SHALL define, as frozen dataclasses on `core` types only:
- `JobPair(name: str, positive: str, negative: str, width: Nm, gap: Nm, via_gap: Nm | None = None, skew_max: Nm | None = None)`: two nets of the job routed as one differential pair;
- `JobEscape(ref: str, kind: str, pitch: Nm, nets: tuple[str, ...])`: a part whose pads the router escapes before it routes, `kind` being `grid` or `perimeter`;

and SHALL add to `RoutingJob`, after every field that exists when this change is archived, `pairs: tuple[JobPair, ...] = ()` and `escape: tuple[JobEscape, ...] = ()`.
- `positive` and `negative` MUST name nets of `job.nets`, and a net MUST belong to at most one pair. `nets` of an escape request MUST name nets of `job.nets`.
- The four codes of "Pairs and escape in the route command" (`cli-contract`) MUST each have an entry in `src/fenolite/cli/data/explain.toml`.
- `routing.protocol.ROUTER_FEATURES` MUST be `frozenset({"pairs", "escape", "short", "roles"})`; `short` marks a router of short connections, not of whole boards (c0228), and `roles` a router that takes the role routes of `RoutingJob.roles` (c0244). `router_features(router) -> frozenset[str]` MUST return the router's attribute `features` when it is a `frozenset` of members of `ROUTER_FEATURES`, and an empty set when the attribute is missing or holds anything else. The `Router` protocol MUST NOT gain the attribute, so a router written before this change keeps satisfying it.
- A job given to a router whose features lack `pairs` MUST hold no pair, and one given to a router whose features lack `escape` MUST hold no escape request; the command removes them ("Pairs and escape in the route command", `cli-contract`).
- The built-in `direct` router MUST declare no feature.

#### Scenario: A job built as before
- **WHEN** `uv run pytest tests/unit/routing/test_protocol.py -k pairs` builds `RoutingJob(design, nets, layers)`
- **THEN** its `pairs` and `escape` are empty, and it equals a job built with `pairs=()` and `escape=()`

#### Scenario: A router without features
- **GIVEN** a test router class that defines `name`, `description`, `sends_data_offsite`, `available` and `route` only, and one whose `features` is the list `["pairs"]`
- **WHEN** `router_features` is called on each and on `DirectRouter()`
- **THEN** all three give an empty set, and `uv run pyright src` reports no error for `_ROUTER: Router = DirectRouter()`

#### Scenario: The octilinear router takes roles
- **WHEN** `router_features(OctilinearRouter())` is called
- **THEN** it gives `pairs`, `short` and `roles`
