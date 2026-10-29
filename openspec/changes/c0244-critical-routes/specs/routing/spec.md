## ADDED Requirements

### Requirement: Role routes in a routing job
`fenolite.routing.protocol` SHALL define the frozen dataclasses `JobRoleEnd` and `JobRoleRoute` (group, kind, tier, net, ends, width, layers, vias, isolated, aggressors, keep_away, partner, gap, loop, key) on `core` types only, and `RoutingJob.roles: tuple[JobRoleRoute, ...] = ()` after `escape`. A router whose features lack `roles` MUST get no role route.

#### Scenario: A job built as before
- **WHEN** `uv run pytest tests/unit/routing/test_protocol.py -k roles` builds `RoutingJob(design, nets, layers)`
- **THEN** its `roles` is empty and the job equals one built with `roles=()`

### Requirement: Octilinear role tiers
With a non-empty `job.roles`, `OctilinearRouter` SHALL route only the role routes, in tiers 0 (hot legs), 1 (gate loops) and 2 (Kelvin pairs), each tier by group name then key, partnered routes as one unit. Rounds MUST reorder failed units within their tier only, and earlier tiers' copper MUST be fixed.

#### Scenario: Kelvin pair after the switch node
- **GIVEN** an authored bench with one hot leg and one Kelvin pair whose straight route would cross the leg
- **WHEN** `uv run pytest tests/unit/routing/test_roleroute.py -k tiers` routes the job
- **THEN** the hot leg is routed first and straight, and the pair avoids it

### Requirement: Octilinear role ends
A role route SHALL end at `JobRoleEnd.at`, not at the pad centre. For a Kelvin route the element end MUST lie on the inner half of the sense pad, at `c + u·(L/2 − w/2 − 2 µm)` along the axis `u` to the other sense pad, or at the centre when that offset is not positive.

#### Scenario: Entry on the inner half
- **GIVEN** a 2512 two-pad shunt and an amplifier on the authored bench
- **WHEN** `uv run pytest tests/unit/routing/test_roleroute.py -k entry` routes its Kelvin pair
- **THEN** each track end lies inside its pad with an offset `t > 0` toward the other pad

### Requirement: Octilinear isolated branches
For an `isolated` role route, every item of its own net (pad copper, track, arc, via and zone outline on its layer) other than its two end pads SHALL be an obstacle at the clearance in force. A connection whose every shape is refused by this test MUST report reason `isolation`.

#### Scenario: A sense branch beside its own pour
- **GIVEN** a Kelvin route of net `VOUT` whose straight shape crosses the outline of a `VOUT` zone
- **WHEN** `uv run pytest tests/unit/routing/test_roleroute.py -k isolated` routes it
- **THEN** the placed branch keeps the clearance in force from the zone outline and touches only its end pads

### Requirement: Octilinear switching keep-away
A role route with aggressors SHALL keep `keep_away` from aggressor copper and zone outlines on its layer, and MUST NOT overlap aggressor copper or zone outlines on an adjacent copper layer. A connection whose every clear shape breaks this MUST report reason `near-switching`.

#### Scenario: A pair over a switch-node pour
- **GIVEN** a bench whose sense pair's straight path runs over a switch-node zone on the adjacent layer
- **WHEN** `uv run pytest tests/unit/routing/test_roleroute.py -k keepaway` routes it with `z-shapes=off`, then with the default
- **THEN** the first run reports `near-switching` and the second places the pair clear of the zone

### Requirement: Octilinear Z shapes
In role mode the router SHALL try, after c0228's five shapes, at most 8 Z shapes per layer whose middle segment runs on a line taken from the keep-away and blocking bounding boxes, made octilinear with no acute joint. `--router-option z-shapes=off` MUST turn them off; a job without role routes MUST keep its five shapes and bytes.

#### Scenario: Plain jobs unchanged
- **WHEN** `uv run pytest tests/unit/routing/test_octilinear.py` runs after the role mode lands
- **THEN** every existing octilinear test passes with the same copper

### Requirement: Octilinear hot legs
A `hot-leg` route SHALL place no via unless `hot-vias` allows one, SHALL prefer its first listed layer, and SHALL choose among accepted shapes the one of least role-loop area (shoelace of the centre polyline and the loop's fixed points), then length, then shape order.

#### Scenario: The smaller loop wins
- **GIVEN** a bench capacitor 15 mm from a switch pair, with two clear shapes for its return leg enclosing 40 mm² and 90 mm²
- **WHEN** `uv run pytest tests/unit/routing/test_roleroute.py -k hot` routes the legs
- **THEN** the return leg takes the 40 mm² shape and no via is placed

### Requirement: Octilinear gate pairs
A gate loop SHALL be routed as its `gate-out` routes plus one `gate-return`, either side by side at the pair pitch or stacked under the out route on the adjacent layer through one via at each end, keeping the form of smaller loop area and side by side on equal area. A return net with a plane under the whole out route MUST NOT be routed.

#### Scenario: Stacked when the side is blocked
- **GIVEN** a bench gate loop with a pad of another net beside the out route on both sides
- **WHEN** `uv run pytest tests/unit/routing/test_roleroute.py -k gate` routes it
- **THEN** the return runs under the out route on the adjacent layer with two vias, and its form is `stacked`

### Requirement: Octilinear role vias
A role route SHALL place at most its `vias`: 0 by default for `hot-leg`, `gate-out` and `kelvin`, 2 for `gate-return`, changed by the router options `hot-vias`, `gate-vias` and `kelvin-vias`. A connection whose ends share no allowed layer and which may place no via MUST report reason `no-layer`.

#### Scenario: No common layer
- **GIVEN** a Kelvin route whose shunt pads are on `F.Cu` and whose amplifier pads are on `B.Cu`
- **WHEN** it is routed with the defaults, then with `kelvin-vias=2`
- **THEN** the first gives `no-layer`, and the second places one via per branch

### Requirement: Role check in job extras
In role mode, `fenolite route` SHALL add `role_check` to `RoutingJob.extra`: a callable from a design to findings `(code, group, severity, measure)` from `fenolite.roles.judge`. The router MUST remove the whole copper of a group that has a new code or a larger measure after routing, with one `route.role-refused`; `roles.loop-open` before routing MUST count as no finding.

#### Scenario: A worse group is removed
- **GIVEN** a test `role_check` that reports a new `roles.near-switching` on group `isense` after routing
- **WHEN** `uv run pytest tests/unit/routing/test_roleroute.py -k refused` routes the job
- **THEN** the result holds no copper of `isense`'s two routes and one `route.role-refused` naming it

### Requirement: Role route codes
`ISSUE_CODES` SHALL hold `route.role-unrouted` and `route.role-refused` (warnings, errors under `--require-complete`), and `route.role-unconfirmed`, `route.role-kept`, `route.role-placement` and `route.role-none` (info), each with an `explain.toml` entry and a row in `docs/cli-contract.md`. Equal inputs MUST give equal results.

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
