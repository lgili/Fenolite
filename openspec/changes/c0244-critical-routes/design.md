## Context

- **The request.** The maintainer asked on 2026-10-28 for a router that works from electrical intent, and
  decided on 2026-10-28 and 2026-10-29 (c0222, `design.md`):
  - roles are inferred and confirmed by the user;
  - the deliverable makes the critical routes and the power copper automatically, proposes the rest, and
    marks what could not be finished;
  - the output serves KiCad and Altium;
  - default limits from public sources are warnings, and the user's limits on confirmed roles are errors;
  - the phase order is 0 → 1 → 2 → 4 → 3;
  - the boards have 2 to 4 layers and up to about 150 parts.

  c0222 (phase 0) is implemented and archived (`changes/archive/2026-10-29-c0222-net-roles`, branch
  `c0222-net-roles`, head `ff9d9e4c`). This change is phase 2: in c0222's plan, a "role-ordered job, gate
  pairs, Kelvin entries, `role_check`, `--gate drc`", sized 6 design-days. c0243 (phase 1, power and ground
  copper from roles) is being written in parallel.
- **What phase 0 gives** (`src/fenolite/roles/`, `docs/roles.md`):
  - **Roles and groups.** `NetRole` and the groups `HotLoop` (ordered pads), `KelvinPair` (sense pads of
    the element, receiver inputs, optional force pads) and `GateLoop` (drive, gate, source or
    Kelvin-source, return, optional resistor). Each records its source: `inferred`, `confirmed` or
    `declared`.
  - **Storage.** `RuleSet.roles` for a built project; `<stem>.roles.json` beside any other board.
  - **The profile.** `width_per_amp_nm`, `milliamps_per_via`, `loop_ratio_max`, `gate_ratio_max`,
    `pair_ratio_max`, `switching_distance_nm` and the rest, with their sources and overrides.
  - **The judge.** `fenolite.roles.judge` behind the check stage `roles.rules`, and `fenolite roles
    --check`. Its findings are `roles.loop-area`, `roles.gate-loop`, `roles.gate-return-shared`,
    `roles.kelvin-outer`, `roles.kelvin-shared`, `roles.kelvin-apart`, `roles.near-switching`,
    `roles.loop-open` and the current findings, all measured through the analyses of `dev`.
  - **The two branch walks.** The Kelvin attachment walks the sense branch from the receiver pad without
    entering power copper and reports the offset `t` along the axis to the other sense pad. The gate
    return is walked the same way, from the driver's return pad to the source pad.
  - **The reference boards.** `examples/roles/{buck_shunt,half_bridge,bms}`, each with `good.py` and
    `bad.py` built by a shared `*_board.py`, checked on the KiCad and Altium builds.
- **What `dev` gives for routing.**
  - **The plugin protocol** (`routing/protocol.py`). `RoutingJob` with `nets`, `layers`, `extra` (the
    board-frame pads, the outline, `clearance` and `copper_check`), `plane_layers`, tiers (c0109),
    `pairs` and `escape` (c0110). `ROUTER_FEATURES` is `{"pairs", "escape", "short"}`.
  - **c0228's `octilinear` router.** Connections are a minimum spanning tree between pad groups. Five
    0/45/90° shapes per connection are tried on each allowed layer, accepted at the clearance in force
    plus 2 µm, with no acute joint and no via. Up to `rounds` rounds put the failed connections first.
    A pair is routed as two offset tracks at its gap, with entries. The result is judged by
    `extra["copper_check"]`, and the ids are content-derived.
  - **c0225's `--gate drc`** through c0209's `api.trial(..., gate=True, together=...)`. `together` drops
    groups of ids as one.
  - **`route`'s handling of copper.** `--rip` keeps locked and script copper. Copper on open nets is
    merged and kept. Routed copper survives a rebuild ("Routes survive a rebuild"), and so does a rule
    area that the build did not create (`docs/lens.md`, "Board items declared in the script").
  - **Locks and keep-outs.** `Track.locked`, `Via.locked` and `Arc.locked` exist, and the Altium writer
    sets the locked flag of a free track, arc and via (c0108, `H-A-PCB-CU-LOCK`). `Keepout` has
    `no_copper_pour`; both writers lower keep-outs.
  - **Convert.** `fenolite convert --to altium` refuses any loss of tracks, vias and zones, so routed copper
    reaches an Altium project or the command writes nothing.
  - **Review.** `render --region` (c0211) draws one rectangle of the board from the model, and c0199 shows
    crossings.
- **Package layering.** `routing` may import `core`, `model` and `geometry` only. `roles` may import
  `model`, `geometry`, `backends.base` and `analysis`. `cli` may import both. So the command is where
  roles become a routing job: `roles` plans in its own types, and `cli` translates the plan into
  `routing.protocol` types. No import edge changes.

## Goals / Non-Goals

**Goals**

- On a placed board with confirmed or declared role groups, one command routes every open critical
  connection deterministically, before any general router. Afterwards `roles.rules` gives no finding that
  critical copper can clear, and `--gate drc` gives no new DRC finding.
- Every critical group appears in the reply. It is routed, already complete, kept, refused or unrouted,
  and anything not routed gives a reason and a proposal.
- The routed copper is locked and fenced. Phase 1, phase 4 and any external router keep it, and pours
  cannot reach a sense or gate branch.
- KiCad and Altium output, equal inputs give equal bytes, and a second run writes nothing.

**Non-Goals.** See the proposal.

## Decisions

### 1. A role mode of the octilinear router, not a new router

- **Alternatives weighed:**
  - a new plugin `roles` (a second world, acceptance and judge: duplicated code);
  - pre-routing in the command (bypasses the plugin protocol and its gate);
  - a role mode of `octilinear`.

  **Chosen:** the role mode. It reuses c0228's `_World` (obstacles, clearance in force, edge, holes),
  shapes, acceptance, rounds, pair offsets and copper check.
- **Feature `roles`.** `ROUTER_FEATURES` gains `roles`, and `OctilinearRouter.features` becomes
  `{"pairs", "short", "roles"}`. The command gives role routes only to a router that declares `roles`.
  `--roles` with any other router is `FEN-2001` (exit 2), with a hint naming the routers that have it.
- **Code.** The role mode lives in `src/fenolite/routing/roleroute.py`. It imports `octilinear`'s
  internals, which become module-level names with a leading underscore, kept private to the package.
  `OctilinearRouter.route` calls it when `job.roles` is not empty, and in that case it routes nothing
  else.

### 2. The job: `JobRoleRoute`

`routing.protocol` gains frozen dataclasses on `core` types only:

```python
@dataclass(frozen=True, slots=True)
class JobRoleEnd:
    ref: str                  # pad reference
    number: str               # pad number
    net: str
    at: Point                 # where the track must end: the pad centre, or an entry point inside the pad
    layers: tuple[str, ...]   # copper layers of the pad

@dataclass(frozen=True, slots=True)
class JobRoleRoute:
    group: str                # the role group's name
    kind: str                 # "hot-leg", "gate-out", "gate-return", "kelvin"
    tier: int                 # 0 hot legs, 1 gate loops, 2 Kelvin pairs
    net: str
    a: JobRoleEnd
    b: JobRoleEnd
    width: Nm
    layers: tuple[str, ...]   # allowed layers in preference order
    vias: int = 0             # vias this route may place
    isolated: bool = False    # copper of its own net is an obstacle except at a and b
    aggressors: tuple[str, ...] = ()   # nets whose copper it keeps away from
    keep_away: Nm = 0
    partner: str = ""         # the paired route's key ("" for none)
    gap: Nm = 0               # the pair's gap, when partner is set
    loop: tuple[Point, ...] = ()       # the role loop's other fixed points, for the area cost
    key: str = ""             # f"{group}:{kind}:{a.ref}-{a.number}:{b.ref}-{b.number}"
```

`RoutingJob` gains `roles: tuple[JobRoleRoute, ...] = ()` after `escape`. A job built as before is equal to
one with `roles=()`. `job.nets` still names every net that a route touches, so the router has their class
values and the command its verdict.

### 3. From roles to routes (`fenolite.roles.routes`)

`plan_critical(design, roles, frame_pads, profile) -> CriticalPlan` turns the role groups into plain-data
`CriticalRoute`s (roles' own types, the fields of `JobRoleRoute`) and `Skipped` entries:

- **Which groups.** Groups whose source is `confirmed` or `declared`. An `inferred` group gets a `Skipped`
  entry with reason `unconfirmed` and is not routed (open question 1). `--group NAME` limits the plan to
  the named groups.
- **Which connections.** Only the open ones. A connection whose two ends are already joined by copper (the
  open-connection analysis the command already runs) is `complete`.
  - A complete group that still has findings is `kept`, and is re-routed only with `--rip` (decision 9).
  - A complete group without findings is `complete`.
- **Hot loop** (`HotLoop(name, pads)`). Each pair of consecutive pads of two parts on one net is a leg (the
  leg rule of c0213's loops), routed as one `hot-leg` route of that net, tier 0.
  - Pads of one part are crossed inside the part and are not routed.
  - The leg between the high-side source and the low-side drain is the switch node, and it comes first.
- **Gate loop** (`GateLoop(name, drive, gate, source, ret, resistor)`).
  - `gate-out` routes run drive → resistor pad 1 and resistor pad 2 → gate, or drive → gate without a
    resistor.
  - One `gate-return` route runs source → ret, where `source` is the Kelvin-source pad when the group
    names it. Its `partner` is the `gate-out` route of the longest segment.
  - All of them are tier 1.
- **Kelvin pair** (`KelvinPair(name, element, receiver, force)`). Two `kelvin` routes, element pad →
  receiver pad on each side, partnered, tier 2. Their element ends are entry points (decision 5).
- **Width.**
  - A `hot-leg` gets `max(class width, ceil(width_per_amp_nm × milliamps / 1000))` when the role has
    `milliamps`, else the class width. The result is capped at the narrower end pad's width across the
    leg's direction. When the cap applies, the route is marked `power_copper_needed` (decision 11), so that
    the leg fixes the geometry and phase 1 carries the current.
  - `gate-out`, `gate-return` and `kelvin` routes take their net's class width. Kelvin routes take the
    pair width when the two nets form a differential pair of the model.
- **Gap.** The gap of a Kelvin pair is the class pair gap when the nets form a pair of the model, else the
  clearance in force between the two nets. The gap of a gate pair is the clearance in force between the
  out and return nets.
- **Layers.**
  - **Hot legs.** The outer copper layers that both end pads reach. The one whose adjacent layer holds a
    zone or plane of a `ground` net of the board comes first: the layer facing the return (S-0890). On a
    2-layer board, the pads' own side comes first. The chosen reference layer is reported.
  - **Gate and Kelvin routes.** The layers both end pads reach, the pads' side first. A gate return also
    gets the adjacent inner layer for its stacked form (decision 7).
- **Isolation.** A `gate-return` or `kelvin` route whose net has role `power`, `switch_node` or `ground`
  is `isolated`. Its branch must not touch its own net's copper except at its end pads (S-0892; c0222's
  `roles.kelvin-shared` and `roles.gate-return-shared`). Hot legs are never isolated: they join the
  copper of their net.
- **Aggressors.** For `kelvin` routes and for gate routes of another switch, the aggressors are the
  `switch_node` nets of the board. `keep_away` is the profile's `switching_distance_nm`, the same value and
  source that `roles.near-switching` judges (c0222, `H-G-ROLE-NEAR-SW`).
- **Loop points.** For each route, the fixed points of its role loop: the pad centres of the other legs, or
  the partner's ends. They feed the area cost of decision 6.

The command converts each `CriticalRoute` into a `JobRoleRoute`, and each `Skipped` entry into the reply.

### 4. Order: tiers, then rounds

The tiers run in order: 0 (hot legs, the switch node first), 1 (gate loops), 2 (Kelvin pairs). This is the
order of c0222's plan and of S-0852, which names the switch node the most critical net.

- **Within a tier.** By group name, then route key. Partnered routes count as one unit.
- **Rounds.** c0228's rounds apply inside a tier only: the failed units go first in the next round of
  their tier. The copper of earlier tiers is a fixed obstacle, as c0109 says for tiers.
- **Why Kelvin last.** The keep-away is judged against switching copper, so the switch-node legs and the
  gate returns on the switch node must stand first.

### 5. Ends: Kelvin entries on the inner half

- **The entry point.** For a Kelvin route, the element end `a.at` is not the pad centre. Let `u` be the
  unit vector from the sense pad's centre `c` to the other sense pad's centre (c0222's axis), and `L` the
  pad's extent along `u`. Then:

  `a.at = c + u · (L/2 − w/2 − MARGIN)`, rounded to the nanometre toward `c`

  with `w` the route width and `MARGIN` c0228's 2 µm. The track end lies inside the pad's copper on its
  inner half, so c0222's offset `t` is positive. This follows S-0850: the sense lines connect inside the
  pads, off the path of the load current.
- **When it does not fit.** If `L/2 − w/2 − MARGIN ≤ 0`, the point is the centre (`t = 0`, which passes
  c0222's `t ≥ 0`). If the pad is too small for the width, the group gets reason `pads`.
- **Four-terminal shunts.** The ends are the sense pads, with the entry on the side facing the other sense
  pad. The force pads are obstacles of the route even though they are on its net.
- **Gate returns.** The return end is the source or Kelvin-source pad's centre. Isolation keeps the return
  from starting on the source pour (decision 6).
- **Pair joints.** A pair's coupled part starts and ends where c0228's diagonal from each end meets it. The
  ends are the entry points, so the pair leaves from between the two sense pads, under the shunt's body
  when it fits, and converges to the receiver.

### 6. Acceptance and cost in role mode

A shape of a role route is accepted when it passes c0228's acceptance at the route's width and on its
layer, and also:

1. **Isolation.** For an `isolated` route, every item of its own net is an obstacle at the clearance in
   force, except the copper of `a`'s and `b`'s pads. The items are pad copper, tracks, arcs, vias and the
   outline of every zone of the net on that layer. A zone outline counts, not only its fill, because a
   later fill would reach the branch. The corridor of decision 10 then keeps the zone out.
2. **Keep-away.** For a route with aggressors, no segment may come within `keep_away` of aggressor copper
   on its layer. The aggressor copper is pads, tracks, arcs, vias and zone outlines. No segment may overlap
   aggressor copper or an aggressor zone outline on an adjacent copper layer. This is the condition that
   `roles.near-switching` judges, tested on outlines instead of fills, so it is never weaker than the
   judge. A shape refused only by this test counts toward reason `near-switching`.
3. **Vias.** A route places no via beyond its `vias` (decision 8).

Among the accepted shapes of a unit, the router keeps the one with the least **cost**:

- **Hot legs and gate pairs:** the absolute shoelace area of the role loop's centre polyline (the shape's
  points and the loop's fixed points), then the length, then c0228's shape order. Each leg is chosen
  against the legs already placed and straight lines for the others. This is a selection cost from
  S-0890's and S-0891's "minimise the enclosed area", computed with `geometry`'s polygon area; it is not a
  reported measure.
- **Kelvin pairs:** the length of the centre line, then the shape order. The pair's offset keeps the area
  between the branches at the pitch.

Role mode tries every shape and keeps the cheapest. c0228 keeps the first that passes. There are at most 5
plus 8 shapes per layer (decision 12), so the cost of this stays small.

### 7. Gate pairs: side by side, then stacked

For each gate loop, the router tries two forms and keeps the accepted one of smaller loop area. On equal
area it keeps side by side, which places no via.

- **Side by side** (S-0891, S-0852). The `gate-out` route is routed first by decision 6. The
  `gate-return` route is routed as c0228's pair offset of the out route's centre line, at the pitch
  `(w_out + w_ret)/2 + gap + 1 nm`, on the side from which both return pads are reached. Short entries join
  it to the source pad and to the driver's return pad. With a gate resistor, the return follows the
  out route's polyline through both segments, and the resistor's body lies inside the loop, as placement
  fixed it.
- **Stacked** (S-0891, "in the shadow of the drive trace on an adjacent layer"). The `gate-return` route
  leaves the source pad on the pad's layer through an entry to a via. It runs on the adjacent copper layer
  exactly under the out route's centre line (offset 0), to a via near the driver's return pad, and an entry
  joins that via to the pad.
  - This needs `vias ≥ 2` (decision 8), and the adjacent layer must not be a plane layer of the job.
  - Each via is the return net's class via, placed on the out route's first or last segment and outside
    both pads by the clearance in force. It must pass c0228's acceptance on every layer of its span.
  - The return is then measured by c0213's plan area as almost no area, as c0222 states for a stacked
    return.
- **A return carried by a plane.** When the return net is a `ground` net with a zone on the layer
  adjacent to the out route along its whole length, the return is not routed: the plane carries it
  (S-0891). The group is `routed` with form `plane-return`, and c0222's judge decides on the loop as
  measured.

### 8. Vias per role

| route | default `vias` | why | router option to change it |
|---|---|---|---|
| `hot-leg` | 0 | S-0890: vias in the power loop let the noise current leave the top layer | `hot-vias=N` |
| `gate-out` | 0 | the out route is the reference of the stacked form | — |
| `gate-return` | 2 (one at each end, stacked form only) | S-0891's shadow route | `gate-vias=0` turns the stacked form off |
| `kelvin` | 0 | S-0852, S-0892: a pair on one layer; a via needs a keep-out on every layer around it | `kelvin-vias=2` allows one via per branch, each with a corridor on every layer of its span |

A connection whose ends share no allowed layer and whose `vias` is 0 gets reason `no-layer` and the
proposal `allow-via`. With `kelvin-vias` or `hot-vias`, the route may change layer once, at a via placed on
a corner of an accepted two-layer shape: the shape's first part on `a`'s layer and its second on `b`'s.

### 9. Existing critical copper and `--rip`

- **No silent rip.** Role mode never removes copper on its own. A group whose connections are joined by
  copper is `complete` when the judge finds nothing on it, and `kept` otherwise. A `kept` group gets one
  `route.role-kept` (info) that names its findings, with the proposal `rip`.
- **`--rip` in role mode.** It removes only the copper of the branches of the selected groups:
  - for a Kelvin branch or a gate return, the copper that c0222's branch walk reaches from the receiver or
    return pad without entering power copper;
  - for a gate out, the copper between the drive pad and the gate pad that carries no other pad;
  - for a hot leg, the tracks and vias of the leg's net that lie on no other pad's path.

  Locked copper and script copper are kept, as `--rip` keeps them now. A pour is never removed.
  `result.rip_kept` counts what was kept, so a group that stays `kept` because its copper is script copper
  says so, with the hint to change the script.

### 10. Locks and corridors

- **Locks.** Every track, arc and via that role mode writes has `locked=True`. KiCad writes
  `(locked yes)`; the Altium writer clears bit 2 of the first flag byte (c0108, `H-A-PCB-CU-LOCK`). c0208's
  `tidy` and `--rip` keep locked items, and so must phases 1 and 4.
- **Corridors** (S-0892: a pour keep-out along the sense trace from beginning to end, and on all layers
  around a via).
  - **Which branches.** Each `isolated` route that is routed gets one `Keepout`, with
    `no_copper_pour=True` and every other setting false.
  - **Name.** `role-corridor:<group>:<net>`.
  - **Outline.** The route's polyline grown by `w/2 +` the zone clearance in force of the net's zones (the
    largest, at least the clearance in force), as an octilinear polygon in integer nanometres.
  - **Layers.** The route's layer, and every layer of a via's span over a square around the via.
  - **What it does.** The corridor keeps every pour off the branch, its own net's included, so the next
    `fill`, phase 1's pours and KiCad's own refill all leave it alone. Tracks and vias are not forbidden.
- **Hot legs and gate outs get no corridor.** A hot leg is meant to merge with its net's pour. A gate out
  net has no pour.
- **Ids.** A track is `derived_id("trk", "roles", content_hash(group, net, geometry))`, likewise `via` and
  `rule`. The KiCad uuids are derived from the ids without the build's `fenitm` marker, so a rebuild treats
  the corridors as rule areas drawn on the board and keeps them (`docs/lens.md`).

### 11. Interface with phase 1 (c0243) and the recommended order

- **Recommended run order: critical routes first, then power copper, then the rest.**
  - A critical route is constrained: fixed ends, at most 13 shapes per layer, no search.
  - A pour, by contrast, fills around whatever stands, and c0224's `band` narrows within `width` and
    `max_width` where clearance allows.
  - Routing the constrained copper first gives it the room it needs, and leaves the flexible copper to
    adapt. S-0892 describes the same order: the sense trace first, then the keep-out that the pours obey.
- **The other order also works.** With phase 1's pours already on the board:
  - their fills are no obstacle (c0228, decision 3);
  - their outlines are obstacles of isolated and keep-away routes (decision 6);
  - the corridors cut the pours on the next fill.

  A pour that leaves no corridor gives reason `isolation` or `near-switching`, naming the zone, with the
  proposal `free-corridor`.
- **What phase 2 hands phase 1.**
  1. **Locked items.** Phase 1 never moves, narrows or removes them.
  2. **Corridors.** Pours respect them by the board's own rule areas: no code in phase 1 needs to know
     them, but phase 1 must not delete or edit a `Keepout` whose name starts with `role-corridor:`.
  3. **`critical_copper(design, roles) -> CriticalCopper`** in `fenolite.roles.routes`, which returns:
     - `items`: the ids of the role copper per group, recognised by their `trk`, `via` and `rule` ids in
       the `roles` namespace and their locked flag;
     - `corridors`: the corridor ids per group;
     - `power_copper_needed`: the hot legs whose track is narrower than their current needs (decision 3),
       each with its net, its required width and its track id. Phase 1 widens such a leg with a band or
       pour of the same net that overlaps the track.
- **What phase 2 expects from phase 1.**
  - Phase 1's power copper keeps the clearance in force from locked copper, as any copper does.
  - Phase 1's bands of a hot loop's nets may start from the hot legs, which are copper of their net.
  - After phase 1, `roles.rules` is run again as phase 1's own acceptance gate. A hot leg that phase 1
    widened is judged by c0222's current checks as one element of its net.
- **Open points for c0243.** The names `critical_copper`, `power_copper_needed` and `role-corridor:` are
  this change's proposal. Task 0.1 compares them with c0243 as it lands. If c0243 settles different names
  first, this change takes c0243's names and records the mapping.

### 12. Z shapes (S-0837)

S-0837 describes pattern routing with L and Z patterns. c0228 has the L shapes and their 45° variants. Role
mode adds Z shapes: a first segment, a middle segment along a free line, a last segment.

- **Middle lines.** For each axis, at most 4 coordinates are taken, in order:
  - the two coordinates at `keep_away` plus half the width beyond each side of the bounding box of the
    aggressor copper and zone outlines between `a` and `b`;
  - the two coordinates at the clearance in force plus half the width beyond the bounding box of the
    obstacle that refused the straight shape.

  This gives at most 8 Z shapes per layer, made octilinear by c0228's diagonal rule at each bend: a 45°
  run where the offset allows, else 90° corners.
- **Order.** They are tried after the five shapes, every shape on every allowed layer, and the cost of
  decision 6 chooses among all the shapes accepted.
- **Pairs.** The centre line of a pair may be a Z shape, offset as c0228's pairs are.
- **Off by default outside role mode.** `--router-option z-shapes=off` turns them off in role mode, for
  measurement. A plain `octilinear` job keeps its five shapes and its bytes.

### 13. Judged twice: `role_check` and the DRC gate

- **`extra["role_check"]`.** The command adds to `RoutingJob.extra` a callable `role_check(design) ->
  tuple[RoleFinding, ...]`. Each finding is `(code, group, severity, measure)`, `measure` being an integer
  (area in nm², ratio in per-mille or offset in nm) or `None`. The callable runs `fenolite.roles.judge` on
  the design with the stored and declared roles. It is built by `cli`, as `copper_check` is, so `routing`
  imports nothing new.
- **The comparison.** After its last round and after `copper_check`, the router judges the board before and
  after the job's copper.
  - **Worse.** A group is worse when, after routing, it has a code it did not have before, or the same code
    with a larger measure. A worse group's copper is removed whole, both partners and every leg, with one
    `route.role-refused` (warning) naming the group, the code and both measures. The check is not run
    again, because removing a group's copper cannot make another group worse.
  - **Better.** A group whose findings went away is `routed` with its before and after findings in the
    reply.
- **Only judged groups.** `roles.loop-open` before routing counts as no finding. It is the open leg that
  role mode is closing.
- **`--gate drc`** works as c0225 defines it, with `together` set to the item ids of each group. A group
  that brings a new KiCad DRC finding is dropped whole, with reason `drc`. Without `--gate`, the result is
  `UNVERIFIED` as every route is.

### 14. Failures: reasons and proposals

Each group the plan names ends in exactly one status:

| status | meaning |
|---|---|
| `routed` | open connections routed and kept by both judges |
| `complete` | already joined, no finding |
| `kept` | already joined, with findings, not ripped |
| `refused` | routed, removed by `role_check` |
| `unrouted` | not routed |
| `skipped` | not attempted (`unconfirmed`) |

`unrouted`, `refused` and `skipped` give one issue (`route.role-unrouted`, `route.role-refused`,
`route.role-unconfirmed`). Each carries one reason and one proposal from closed tables, each with the
command to run.

| reason | when | proposal |
|---|---|---|
| `no-room` | every shape on every layer refused by clearance | `free-corridor`: the three nearest blocking items of the shortest shape, a `render --region` command around the connection |
| `too-long` | every shape longer than `max-length` | `raise-limit` (`--router-option max-length=…`) or `move-part` |
| `no-layer` | the ends share no allowed layer and the route allows no via | `allow-via` (`kelvin-vias=2`, `hot-vias=1`) or `move-part` |
| `near-switching` | every shape that kept clearance broke the keep-away | `free-corridor` naming the aggressor items, or `move-part` |
| `isolation` | every shape touched its own net's power copper | `free-corridor` naming the zone or track of the net |
| `role-check` | routed, then a finding got worse | the finding; `free-corridor` |
| `drc` | dropped by `--gate drc` | the DRC finding's type and items |
| `pads` | a group pad is missing from the board, or too small for its entry | `move-part` or edit the role (`fenolite roles --set`) |
| `unconfirmed` | inferred and not confirmed | `confirm`: `fenolite roles PATH --accept-group NAME --dry-run` |

- **The region.** The `render --region` command covers the bounding box of the group's pads, grown by
  2 mm, with `--nets --open`, as c0211 draws it.
- **`move-part`.** It names the leg and its two pads, and the length the shortest shape needs. Fenolite
  computes no new position.
- **`route.role-placement`** (info). After routing, a hot or gate loop whose placement bound (c0222) is
  above the user's `loop_max` or `gate_max` gets this info: no route can bring the area under the bound. It
  names the bound, the limit and the longest leg. Without a user limit there is nothing to compare, and the
  reply only states the bound.
- **`--require-complete`** makes each `route.role-unrouted` and `route.role-refused` an error, with exit 5
  and no write, as `route.incomplete` does.

### 15. Command line, result and protocol

- **Synopsis.** `fenolite route PATH --router NAME --roles critical [--group NAME]... [--roles-file FILE]
  [--rip] [--gate drc] [--router-option KEY=VALUE]... [--require-complete] [-o OUT] [--dry-run | --confirm
  [--plan ID]]`.
- **`--roles`.** It takes one value. This change defines `critical`; phase 4 will add `propose`.
  `--roles-file` names the role document, as `roles --roles FILE` does. `--group` is valid only with
  `--roles`. With `--roles`, `--nets`, `--escape` and `--pairs-as-nets` are usage errors (`FEN-2001`): the
  roles choose the nets.
- **The role options.** `octilinear` takes these router options in role mode: `hot-vias`, `gate-vias`,
  `kelvin-vias`, `keep-away=LENGTH` (default: the profile's `switching_distance_nm` with its overrides),
  `z-shapes=on|off`, and c0228's `max-length` and `rounds`.
- **Roles.** The command reads the stored roles (`.fenolite/rules.json` or the role document) and the
  declared ones. No roles, or no critical group, means exit 0, nothing planned, and one
  `route.role-none` (info).
- **Verdict.** Per role connection, not per net. A critical net usually keeps other open connections (an
  output net's pour to its terminal is phase 1's work), so `route.unrouted` is not given for the nets of a
  role job. `result.selected`, `routed` and `unrouted` hold the nets of the routes, judged on the role
  connections only.
- **`result.roles`.** One entry per group of the plan, sorted by tier and name:
  - `group`, `kind` (`hot_loop`, `gate_loop`, `kelvin_pair`) and `status`;
  - `connections`: each with `key`, `net`, `a`, `b`, `layer`, `form` (`single`, `pair`, `side-by-side`,
    `stacked` or `plane-return`), `length` and `vias`;
  - `findings_before` and `findings_after`: the `role_check` findings of the group;
  - `reason` and `proposal` (`kind`, `text`, `command`) when not routed;
  - `copper` and `corridors`: the ids;
  - `reference_layer` for a hot loop;
  - `power_copper_needed` for each hot leg capped by its pads.
- **Write.** The board is written as `route` writes it, through the mutation protocol: `--dry-run` plans,
  `--confirm --plan ID` writes the reviewed bytes, and a changed input gives `FEN-4002`. A run that adds
  nothing writes nothing.
- **Evidence.** `UNVERIFIED`, with `INFERRED` hypotheses cited when `role_check` ran. It is
  `KICAD-VERIFIED` under `--gate drc` with no new finding, as c0225 says.
- **MCP and API.** The tool `fenolite_route` and `fenolite.api.run("route", ...)` take the new options
  through the dispatcher. Nothing else changes.

### 16. KiCad and Altium output

- **KiCad.** `route` writes the board for its own major. The role copper is ordinary tracks and vias with
  `(locked yes)`, and the corridors are rule areas with `(keepout (tracks allowed) (vias allowed) (pads
  allowed) (copperpour not_allowed) (footprints allowed))`, as the KiCad writer lowers a `Keepout` today.
  No new token is written.
- **Altium.** `fenolite convert <routed project> --to altium --out DIR` converts the routed KiCad project.
  The tracks and vias keep their locked flag (c0108). A corridor becomes the keep-out that the Altium
  writer lowers for a `Keepout` with `no_copper_pour`, the region on the copper layer that
  `H-A-POUR-KEEPOUT` covers. The read-back of the written project is compared item by item with the KiCad
  model (`H-A-CRIT-READBACK`), and `roles.rules` gives the same findings on both readings, as c0222's
  "Roles on both backends" requires.
- **A board that Fenolite did not build.** The roles of a `.kicad_pcb` come from its role document, and the
  routed board is written as `route` writes any board. `route` takes no `.PcbDoc` (it resolves KiCad boards
  only): an Altium board's roles are checked by `roles --check`, and routing it in place waits for c0241's
  edit sessions (open question 6).
- **Script-built projects.** The routed copper survives a rebuild, as routed copper does ("Routes survive a
  rebuild"), and so do the corridors. A build for the Altium target does not read the KiCad board's routed
  copper. The Altium deliverable of a routed board is therefore the convert, and `docs/roles.md` says so.

### 17. Reference boards: the open mode and the acceptance gate

Each `*_board.make(design, variant)` accepts a third variant, `open`: the `bad` placement and every `bad`
fault that is not critical copper, without the critical copper of `bad`. The scripts `open.py` build it.

| board | critical copper left out in `open` | phase 2 routes | faults that stay (not phase 2) |
|---|---|---|---|
| `buck_shunt` | the input capacitor's two legs (`vin_c1`, `gnd_c1`) and both sense lines | the hot loop's VIN and GND legs on `F.Cu`, side by side, with no via and the smallest loop for the capacitor 15 mm away; the Kelvin pair from the inner halves of `R12`'s pads to `U3`, isolated from the `VL` and `VOUT` pours, fenced by two corridors | the 0.3 mm track on the 2 A output (`roles.width-current`, phase 1). The capacitor's placement stays: the reply states the loop's bound, and with no user `loop_max` nothing is judged against it |
| `half_bridge` | the high side's gate return and its tie to the source pour (`ks_tie`, `gh_ret`), the low side's gate detour (`gl`), the sense pair | gate loop `hs` (out `GH`, return `SW` from `Q1`'s Kelvin-source pad), isolated from the switch-node pours; gate loop `ls` (out `GL`, return from `Q2`'s Kelvin-source pad). Each is side by side or stacked on `In1.Cu`, whichever encloses less. The Kelvin pair on `R1`, kept off the switch-node pour `SW_UNDER` on `In1.Cu` by keep-away and Z shapes | the single bus via (`roles.via-current`, phase 1). `SW_UNDER` stays as the obstacle the pair must avoid |
| `bms` | the two sense lines from the force pads | the Kelvin pair from the inner halves of `R1`'s sense pads to the monitor, with the force pads as obstacles | the 1 mm pack neck at 20 A (`roles.width-current`, phase 1) and the ground slot under `TAP0` (`roles.return-gap`, ground copper) |

**The gate** (`tests/unit/roles/test_critical_reference.py`, and `tests/kicad/roles/test_critical_drc.py`
for DRC):

1. For each `open` variant, confirm its groups as the reference tests do, run `route --router octilinear
   --roles critical --confirm`, then `roles --check`. No `roles.*` finding of a group in the plan remains,
   and the findings left are exactly those in the table's last column.
2. On each `good` variant the same command plans no write. Every group is `complete`, and the reply holds
   no `route.role-*` warning.
3. Run again on the routed `open` board: no write, every group `complete`.
4. Rebuild the routed `open` project twice: the role copper and corridors are kept with their ids, and the
   second rebuild writes the bytes of the first.
5. With `--gate drc` on KiCad 9 and 10: no new DRC finding, and nothing dropped (`H-K-CRIT-DRC`).
6. Convert each routed `open` project to Altium. The read-back holds the same role copper with the locked
   flags and the corridors, and `roles --check` on the Altium reading gives the findings of the KiCad one
   (`H-A-CRIT-READBACK`).

### 18. Codes

`routing.codes.ISSUE_CODES` gains the codes below, each with an entry in `explain.toml` and a row in
`docs/cli-contract.md`, "route". No `FEN-` code is added: an option misuse is `FEN-2001`, a malformed role
document `FEN-3004`, a write `FEN-4001` and `FEN-4002`, and `--require-complete` gives `FEN-5001`.

| code | severity | meaning |
|---|---|---|
| `route.role-unrouted` | warning (error with `--require-complete`) | a critical group not routed: reason and proposal |
| `route.role-refused` | warning (error with `--require-complete`) | a routed group removed because a role finding got worse |
| `route.role-unconfirmed` | info | the inferred groups not routed, with their count and names |
| `route.role-kept` | info | a complete group with findings, not ripped |
| `route.role-placement` | info | a loop whose placement bound exceeds the user's limit |
| `route.role-none` | info | no critical group to route |

## Hypotheses registered by this change

| id | statement | settling test | criterion |
|---|---|---|---|
| `H-G-CRIT-KELVIN` | Inner-half entries, isolation and corridors give Kelvin pairs that c0222 judges clean | `tests/unit/roles/test_critical_reference.py -k kelvin` | on the three `open` variants, no `roles.kelvin-outer`, `roles.kelvin-shared` or `roles.kelvin-apart` after routing and a fill; every entry offset `t > 0` |
| `H-G-CRIT-GATE` | The side-by-side and stacked forms keep gate loops under `gate_ratio_max`, with the return from the source pad | `tests/unit/roles/test_critical_reference.py -k gate` | on `half_bridge` `open`, both gate loops at or under 2000 per-mille and no `roles.gate-return-shared` |
| `H-G-CRIT-HOT` | Area-cost choice of the hot legs brings a loop placed far apart under `loop_ratio_max` | `tests/unit/roles/test_critical_reference.py -k hot` | on `buck_shunt` `open`, the hot loop at or under 2000 per-mille, no via on a hot leg |
| `H-G-CRIT-KEEPAWAY` | The keep-away with Z shapes routes a sense pair clear of switching copper that the five shapes cross | `tests/unit/routing/test_roleroute.py -k keepaway` and `-k half_bridge` of the reference test | on the authored bench the five shapes alone fail with `near-switching` and the Z shapes pass; on `half_bridge` `open` no `roles.near-switching` |
| `H-G-CRIT-IDEMPOTENT` | Role routing is a fixed point: a second run and two rebuilds change no byte | `tests/unit/roles/test_critical_reference.py -k again` | no write on the second run; equal bytes after the second rebuild; ids unchanged |
| `H-K-CRIT-DRC` | KiCad's DRC finds nothing new on the reference boards after role routing | `tests/kicad/roles/test_critical_drc.py` | on KiCad 9 and 10, `--gate drc` drops nothing and no violation type grows, on each `open` variant |
| `H-A-CRIT-READBACK` | The Altium convert of a routed board keeps the role copper, its locks and its corridors | `tests/unit/roles/test_critical_reference.py -k altium` | every role track and via read back at its position and width with `locked` true, each corridor as a pour keep-out on its layers, and equal `roles.*` findings on both readings |

## Evidence level per behaviour

| behaviour | level | proof |
|---|---|---|
| job, protocol, plan, codes | `INFERRED` until a release; plain data | `tests/unit/routing/test_protocol.py -k roles`, `tests/unit/roles/test_routes.py` |
| routed copper | `UNVERIFIED` until checked | "Router protocol" |
| role findings after routing | `INFERRED` (`H-G-CRIT-KELVIN`, `-GATE`, `-HOT`, `-KEEPAWAY`), with c0222's hypotheses | the open variants |
| KiCad board with `--gate drc` | `KICAD-VERIFIED` per major (`H-K-CRIT-DRC`) | the kicad-9 and kicad-10 jobs |
| Altium output | `INFERRED` (`H-A-CRIT-READBACK`) | the read-back comparison |

## Size and cut order

Sizes in design-days, as in `docs/roadmap.md`:

| part | days |
|---|---|
| entry check, protocol fields, feature `roles`, codes | 0.5 |
| `roles.routes`: plan, widths, layers, entries, isolation, aggressors, `critical_copper` | 1.0 |
| command: `--roles`, `--group`, role extras, `result.roles`, rip of branches | 1.0 |
| role mode in `octilinear`: tiers, entries, isolation, keep-away, cost choice | 1.5 |
| gate pairs: side by side and stacked with vias, plane return | 1.0 |
| Z shapes | 0.5 |
| `role_check` comparison, reasons and proposals, `--gate drc` groups | 0.5 |
| locks, corridors, idempotence, rebuild | 0.5 |
| open variants and the acceptance gate, Altium read-back | 0.5 |
| docs, guide, evidence, closing | 0.5 |
| **total** | **7.5** |

c0222 planned 6 days. The 1.5 more are the corridors and isolation (S-0892 showed that a sense branch of a
power net is otherwise swallowed by its own pour), the stacked gate form with its vias, and the Z shapes.

**Cut order**, cheapest loss first, if time runs short:

1. **Z shapes.** Without them, the half-bridge's sense pair may stay `unrouted` with `near-switching`.
   That is reported and proposed, and `H-G-CRIT-KEEPAWAY` stays open.
2. **The stacked gate form.** Side by side only. A gate loop with no room beside its out route stays
   `unrouted` with `no-room` and the proposal `allow-via`.
3. **`--rip` of branches.** Users remove the old copper by hand or in the script. `kept` groups are
   reported.
4. **The Altium read-back test.** The convert still runs; the evidence stays a claim of the model.

Never cut: the reasons and proposals (no silent skip), the locks and corridors (the interface with phase 1),
`role_check` and the open-variant gate.

## Risks / Trade-offs

- **Shapes are few.** A board with a part between the shunt and its amplifier leaves the pair `unrouted`,
  even with the Z shapes. That is by design until phase 3's search. The proposal names what blocks the
  pair and draws the region.
- **The hot loop is mostly placement.** Routing can only approach the placement bound. The bad buck's loop
  stays near its bound, about the area its placement fixes. The reply states the bound, and
  `route.role-placement` speaks only against a user limit.
- **Corridors cost pour area.** A corridor removes pour around a branch on its layer, the branch's own net
  included. That is S-0892's advice. Its width is the zone clearance plus half the track, so the loss is a
  thin band.
- **Outline-based tests are stricter than the judge.** Isolation and keep-away test zone outlines, not
  fills, so a route may be refused where a fill would have left room. A refusal names the zone; the user
  can shrink the outline. The reverse error, a route the judge then flags, cannot happen through those
  two tests.
- **Area cost uses centre lines.** The cost is the shoelace area of centre polylines, while c0222's judge
  measures c0213's legs along copper. Both are plan areas of nearly the same polylines, and `role_check`
  has the last word.
- **Stacked returns read as almost no area** (c0222, "Loop area is c0213's plan area"). The form choice
  prefers side by side on equal area. A stacked form wins when the side-by-side form is refused or larger.
  This is S-0891's order of advice.
- **Script copper blocks `--rip`.** The bad variants draw their faults as script copper, so the acceptance
  uses the `open` mode rather than `--rip`. A user whose script draws a bad sense line must edit the
  script, and the reply's `rip_kept` says so.
- **c0243 in parallel.** The names of the interface may move. Task 0.1 reconciles them, and decision 11 is
  written so that either order of the two changes works.

## Open Questions

1. Are inferred groups that are not confirmed routed? **Recommended:** no. They are listed with
   `route.role-unconfirmed` and the `roles --accept-group` command. Copper is placed and locked; a wrong
   guess would be fenced in.
2. Which run order of phases 1 and 2? **Recommended:** critical routes first, then power copper (decision
   11), with both orders supported through locks, corridors and outline-aware acceptance.
3. Does phase 2 route hot legs as tracks, or leave the whole hot loop to phase 1's pours? **Recommended:**
   tracks of the role's width, capped by the pads, locked. They fix the smallest loop geometry, and phase 1
   widens the capped ones (`power_copper_needed`). The geometry of the loop is the critical part, and the
   current is phase 1's part.
4. May a gate return use vias by default for the stacked form? **Recommended:** yes, at most one at each
   end (S-0891). Hot legs and Kelvin branches get none unless a router option allows them (S-0890, S-0892).
5. Are the route constraints (vias, keep-away, Z shapes) router options or new role limits?
   **Recommended:** router options in this change, so the model and `rules.json` do not change. They can be
   promoted to per-net role limits later if users ask.
6. How is the Altium deliverable made? **Recommended:** `fenolite convert --to altium` of the routed KiCad
   project now. Routing a `.PcbDoc` in place waits for c0241's edit sessions, and is its own change.
7. What is the surface? **Recommended:** `route --router octilinear --roles critical`, with `--router` still
   required and `roles` a router feature. Phase 4 then adds `--roles propose` beside it. c0222's sketch
   `--router roles` would have hidden which engine routes.
8. Does `--rip` in role mode remove only the groups' branches? **Recommended:** yes: c0222's branch walk,
   never locked or script copper, never a pour.
