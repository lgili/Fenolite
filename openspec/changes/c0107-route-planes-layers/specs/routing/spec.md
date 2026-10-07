## ADDED Requirements

### Requirement: Plane and routing layers in a routing job
`routing.protocol.RoutingJob` SHALL gain the field `plane_layers: tuple[str, ...] = ()` after `extra`, and `JobNet` SHALL gain `layers: tuple[str, ...] | None = None` after `via_drill`. This extends "Router protocol" as "Job extras" did: a job built without them MUST mean what it meant before.
- `plane_layers` names the copper layers, in stack order, that hold planes and take no track. `JobNet.layers` is `None` when the net may use every routing layer, else the non-empty tuple, in stack order, of the routing layers its tracks may use.
- `routing.layers.routing_layers(layers, plane_layers)` MUST return the members of `layers` that are not in `plane_layers`, in order.
- `routing.layers.allowed_layers(design, net, routing_layers)` MUST return the members of `routing_layers` that no `no_tracks` rule of `design.rules` forbids to the net (`rules-model`, "Track layer rules"): a rule of severity other than `ignore` forbids its `layers` when its `selector_a` matches `RuleSubject("track", net=<the net's name>, netclass=<its class name, or Default>)`. It MUST import only `core` and `model`.
- **Direct router.** `DirectRouter` MUST route a two-pad net on the first shared copper layer, in stack order, that is not in `plane_layers` and, when `layers` is not `None`, is in `layers`; a net without such a layer is unrouted. It still avoids nothing.
- **KiCadRoutingTools.** Its command line takes no layer or plane option, so the plugin MUST add one `route.constraint-not-sent` (warning) per run whose job has plane layers or a net with `layers`, naming them; the board and rules files of its run hold the row types and the track layer rules (`H-K-KRT-PLANES`).
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
- **Pads.** For each net of `nets`, in board footprint order then pad order, its pads without a drill. A pad is joined, and skipped, when a via of its net overlaps its copper, or when a chain of its net's tracks and arcs on its layer runs from an end inside its copper, through equal end points or ends inside another pad of the net, to a via of the net or to a pad of the net with a drill; the copper made so far counts.
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
- **THEN** `joined` names `C1-2`, which gets no via; of `C2-2` and `U1-4`, the first in board order gets one via and the other is in `joined` through the track

#### Scenario: A pad without room
- **GIVEN** the bench with a keep-out that forbids vias on every copper layer over the whole part `U1` and 2 mm around it
- **WHEN** `plan_fanout` runs
- **THEN** `U1-4` and `U1-8` are in `failed`, two `kicad.fanout.failed` warnings name them, their nets and the keep-out, and the other pads get their vias

#### Scenario: Deterministic
- **WHEN** `plan_fanout` runs twice on the bench with `PYTHONHASHSEED=1` and `PYTHONHASHSEED=2`
- **THEN** the two plans are equal, item ids included

### Requirement: Freerouting plugin sends planes, layers and rules
The Freerouting plugin SHALL pass `job.plane_layers` as `plane_layers` and the `layers` of the job's nets as `net_layers` to `write_dsn`, and the job's design carries the rules that "Routing rules in design files" lowers. This extends "Freerouting plugin"; a job without plane layers, layer sets or rules MUST give the command line and file it gave before. The writer's issues MUST join the result's issues, as they do today.

#### Scenario: Recorded design file
- **GIVEN** `tests/_fakefreerouting.py`, a fake `java` that keeps the design file it is given, and a job of the bench with `plane_layers=("In1.Cu", "In2.Cu")`, `SIG1` with `layers=("F.Cu",)` and the rule `hv-sig`
- **WHEN** `uv run pytest tests/unit/routing/test_freerouting.py -k planes` routes it
- **THEN** the kept file holds `(layer In1.Cu (type power))`, a `plane` of `GND`, `(use_layer F.Cu)` and `class_class` for `HV` and `SIG`, and the arguments are those of a job without them
