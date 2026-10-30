## MODIFIED Requirements

### Requirement: Pairs and escape in a routing job
`fenolite.routing.protocol` SHALL define, as frozen dataclasses on `core` types only:
- `JobPair(name: str, positive: str, negative: str, width: Nm, gap: Nm, via_gap: Nm | None = None, skew_max: Nm | None = None)`: two nets of the job routed as one differential pair;
- `JobEscape(ref: str, kind: str, pitch: Nm, nets: tuple[str, ...])`: a part whose pads the router escapes before it routes, `kind` being `grid` or `perimeter`;

and SHALL add to `RoutingJob`, after every field that exists when this change is archived, `pairs: tuple[JobPair, ...] = ()` and `escape: tuple[JobEscape, ...] = ()`.
- `positive` and `negative` MUST name nets of `job.nets`, and a net MUST belong to at most one pair. `nets` of an escape request MUST name nets of `job.nets`.
- The four codes of "Pairs and escape in the route command" (`cli-contract`) MUST each have an entry in `src/fenolite/cli/data/explain.toml`.
- `routing.protocol.ROUTER_FEATURES` MUST be `frozenset({"pairs", "escape", "short", "roles", "propose"})`; `short` marks a router of short connections, not of whole boards (c0228), `roles` a router that takes the role routes of `RoutingJob.roles` (c0244), and `propose` a router that answers the subjects of `RoutingJob.subjects` with candidates (c0280). `router_features(router) -> frozenset[str]` MUST return the router's attribute `features` when it is a `frozenset` of members of `ROUTER_FEATURES`, and an empty set when the attribute is missing or holds anything else. The `Router` protocol MUST NOT gain the attribute, so a router written before this change keeps satisfying it.
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
- **THEN** it gives `pairs`, `short`, `roles` and `propose`

## ADDED Requirements

### Requirement: Proposal subjects in a routing job
`fenolite.routing.protocol` SHALL define the frozen dataclasses `JobAttach` (kind, net, at, layers, name) and `JobSubject` (key, kind, net, a, b, width, layers, via sizes, group) on `core` types only, and `RoutingJob.subjects: tuple[JobSubject, ...] = ()` after `roles`. A subject's kind MUST be one of `fanout`, `join`, `role-net`, `group` and `connection`. A router whose features lack `propose` MUST get no subject.

#### Scenario: A job built as before
- **WHEN** `uv run pytest tests/unit/routing/test_protocol.py -k propose` builds `RoutingJob(design, nets, layers)`
- **THEN** its `subjects` is empty and the job equals one built with `subjects=()`

### Requirement: Candidates in a routing result
`fenolite.routing.protocol` SHALL define the frozen dataclass `Candidate` (id, subject, source, relaxed, tracks, arcs, vias, length, layers), `RoutingResult.candidates: tuple[Candidate, ...] = ()` after `roles`, and after it `RoutingResult.refusals`, the subject key, reason and blockers of each subject left without a candidate. A router given subjects MUST return candidates only, with no merged copper. `Candidate.id` MUST be `c-` and 16 hex digits of the SHA-256 of the subject key, source, relaxations and item geometry.

#### Scenario: Candidates only
- **GIVEN** an authored bench with one open connection given as a `connection` subject
- **WHEN** `uv run pytest tests/unit/routing/test_propose.py -k only` runs the octilinear router on it twice
- **THEN** the result holds candidates and no track, arc or via, and both runs give equal candidates with equal ids

#### Scenario: Ids ignore unrelated copper
- **GIVEN** the same bench with a track of another net added far from the connection
- **WHEN** the router runs again
- **THEN** every candidate keeps its id

### Requirement: Octilinear candidate families
In propose mode `OctilinearRouter` SHALL try, per subject, the families `shape`, `z-shape`, `via-l`, then `fanout` (for `fanout` subjects) and `role` (for `group` subjects), and keep the first N (option `candidates`, default 4, at most 8) that pass c0228's acceptance and differ by layer set, via count or a centre line apart by more than the clearance in force. Candidates MUST be in family, shape, then layer order.

#### Scenario: Distinct candidates
- **GIVEN** an authored two-layer bench whose connection has room for L shapes on both layers and for a via-L
- **WHEN** `uv run pytest tests/unit/routing/test_propose.py -k families` asks for 4 candidates
- **THEN** it gets at most 4 candidates, no two with the same layer set, via count and centre line, `shape` ones before `via-l` ones

### Requirement: Zone fan-out candidates
For a `fanout` subject the router SHALL search a neck and a via of the net's class in the eight 45° directions ordered by their angle to the outward direction, in steps of a quarter via diameter over nine distances, keep the first passing position per direction, and require the via inside the zone outline by half its diameter and inside its simulated fill.

#### Scenario: The same search as plane fan-out
- **GIVEN** c0107's plane fan-out bench
- **WHEN** `uv run pytest tests/unit/routing/test_propose.py -k fanout` proposes for each pad of the plane net
- **THEN** each pad's first candidate has the via position that `plan_fanout` chooses

### Requirement: Relaxed group candidates
For a `group` subject the router SHALL run c0244's role mode on the group's routes with its defaults, then once per relaxation of the closed list `kelvin-vias=2`, `gate-vias=2`, `keep-away=clearance`, and label each candidate with its relaxation. Isolation MUST NOT be relaxed.

#### Scenario: A pair over switching copper
- **GIVEN** c0244's keep-away bench with `z-shapes=off`, whose pair is refused with `near-switching`
- **WHEN** `uv run pytest tests/unit/routing/test_propose.py -k relaxed` proposes for the group
- **THEN** no default candidate exists, a candidate labelled `keep-away=clearance` exists, and no candidate touches its own net's zone outline

### Requirement: Proposal codes
`routing.codes.ISSUE_CODES` SHALL hold `route.proposal-unknown` and `route.proposal-conflict` (error), `route.proposal-open`, `route.proposal-findings` and `route.proposal-stale` (warning), and `route.proposal-none`, `route.proposal-rejected` and `route.proposal-limit` (info), each with an `explain.toml` entry and a row in `docs/cli-contract.md`.

#### Scenario: Codes explained
- **WHEN** `uv run pytest tests/unit/cli/test_explain_cmd.py tests/unit/routing -k proposal` runs
- **THEN** the eight codes have their severities, an entry and a documented row
