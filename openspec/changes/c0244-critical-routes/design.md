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

  c0222 (phase 0) is merged into `dev` and archived (`changes/archive/2026-10-29-c0222-net-roles`; `dev` at
  `dedad4c7`). This change is phase 2: in c0222's plan, a "role-ordered job, gate pairs, Kelvin entries,
  `role_check`, `--gate drc`", sized 6 design-days. c0243 (phase 1, power and ground copper from roles) is
  implemented in parallel.
- **The maintainer's decisions of 2026-10-29 on this change** (task 0.1):
  - every recommended answer of the open questions below is accepted, except where these points override;
  - **the hot loop belongs to phase 1** (c0243, as pours): phase 2 routes no hot-loop leg, and routes gate
    loops and Kelvin pairs only;
  - **run order:** critical routes first, then phase 1's pours around them; the other order keeps working;
  - **corridors:** one name for both changes, `role.corridor.<group>.<net>`, a no-pour rule area that phase
    2 writes along its locked routes and phase 1 treats as an obstacle;
  - **release note:** `dev` is at 0.6.0 (cut, not published) and the v0.6 guard requires `## [Unreleased]`
    empty, so no CHANGELOG line is added now.
- **What phase 0 gives** (`src/fenolite/roles/`, `docs/roles.md`):
  - **Roles and groups.** `NetRole` and the groups `HotLoop` (ordered pads), `KelvinPair` (sense pads of
    the element, receiver inputs, optional force pads) and `GateLoop` (drive, gate, source or
    Kelvin-source, return, optional resistor). Each records its source: `inferred`, `confirmed` or
    `declared`.
  - **Storage.** `RuleSet.roles` for a built project; `<stem>.roles.json` beside any other board.
  - **The profile.** `width_per_amp_nm`, `gate_ratio_max`, `pair_ratio_max`, `switching_distance_nm` and the
    rest, with their sources and overrides.
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
    `extra["copper_check"]`, and the ids are content-derived. Zone fills are no obstacle (c0228, decision
    3): a refill clears around new copper.
  - **c0225's `--gate drc`** through c0209's `api.trial(..., gate=True, together=...)`. `together` drops
    groups of ids as one.
  - **`route`'s handling of copper.** `--rip` keeps locked and script copper. Copper on open nets is
    merged and kept. Routed copper survives a rebuild ("Routes survive a rebuild"), and so does a rule
    area that the build did not create (`docs/lens.md`, "Board items declared in the script").
  - **Locks and keep-outs.** `Track.locked`, `Via.locked` and `Arc.locked` exist, and the Altium writer
    sets the locked flag of a free track, arc and via (c0108, `H-A-PCB-CU-LOCK`). `Keepout` has
    `no_copper_pour` and a `name`; both writers lower keep-outs.
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

- On a placed board with confirmed or declared gate loops and Kelvin pairs, one command routes every open
  critical connection deterministically, before any general router. Afterwards `roles.rules` gives no
  finding that critical copper can clear, and `--gate drc` gives no new DRC finding.
- Every planned group appears in the reply. It is routed, already complete, kept, refused, unrouted or
  skipped, and anything not routed gives a reason and a proposal.
- The routed copper is locked and fenced. Phase 1, phase 4 and any external router keep it, and pours
  cannot reach a sense or gate branch.
- KiCad and Altium output, equal inputs give equal bytes, and a second run writes nothing.

**Non-Goals.** See the proposal; above all, no hot-loop leg (phase 1's).

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
- **Code.** The role mode lives in `src/fenolite/routing/roleroute.py`. It imports `octilinear`'s private
  helpers (module-level names with a leading underscore, kept inside the package). `OctilinearRouter.route`
  calls it when `job.roles` is not empty, and in that case it routes nothing else. The command's side lives
  in `src/fenolite/cli/_roleroute.py`, so `cmd_route.py` only parses the options and hands over.

### 2. The job and the outcome

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
    kind: str                 # "gate-out", "gate-return", "kelvin"
    tier: int                 # 0 gate loops, 1 Kelvin pairs
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
    loop: tuple[Point, ...] = ()       # the rest of the role loop, from b back to a, for the area cost
    key: str = ""             # f"{group}:{kind}:{a.ref}-{a.number}:{b.ref}-{b.number}"

@dataclass(frozen=True, slots=True)
class RoleOutcome:
    key: str
    group: str
    status: str               # "routed", "plane-return", "unrouted", "refused"
    reason: str = ""          # for "unrouted" and "refused": a reason of decision 14
    form: str = ""            # "single", "pair", "side-by-side", "stacked", "plane-return"
    layer: str = ""
    length: Nm = 0
    vias: int = 0
    runs: tuple[tuple[str, Nm, tuple[Point, ...]], ...] = ()   # (layer, width, polyline) placed
    via_points: tuple[Point, ...] = ()
    blockers: tuple[str, ...] = ()     # what refused the shortest shape, for the proposal
    detail: str = ""          # the refusing finding of role_check, or the blocking zone
```

`RoutingJob` gains `roles: tuple[JobRoleRoute, ...] = ()` after `escape`, and `RoutingResult` gains `roles:
tuple[RoleOutcome, ...] = ()` after `not_attempted`. A job or a result built as before is equal to one
with `roles=()`. `job.nets` still names every net that a route touches, so the router has their class
values and the command its verdict. The outcome is what the command needs for `result.roles` and for the
corridors (decision 10); the router places no rule area itself, because `RoutingResult` carries copper only.

### 3. From roles to routes (`fenolite.roles.routes`)

`plan_critical(design, roles, frame_pads, ...) -> CriticalPlan` turns the role groups into plain-data
`CriticalRoute`s (roles' own types, the fields of `JobRoleRoute`) and group entries:

- **Which groups.** Gate loops and Kelvin pairs whose source is `confirmed` or `declared`. An `inferred`
  group gets an entry with status `skipped` and reason `unconfirmed`, and is not routed (open question 1).
  `--group NAME` limits the plan to the named groups. A hot loop is never planned; one named by `--group`
  gets status `skipped` with reason `phase-1` and the proposal `power-copper` (the maintainer's decision of
  2026-10-29: the hot loop is phase 1's).
- **Which connections.** Only the open ones. A connection whose two ends lie in one island of their net
  (`analysis.connectivity`, as the command already runs it) is joined.
  - A group whose connections are all joined is `complete` when the judge finds nothing on it, and `kept`
    otherwise; it is re-routed only with `--rip` (decision 9).
  - A group with an open connection is planned, and only its open connections become routes.
- **Gate loop** (`GateLoop(name, drive, gate, source, ret, resistor)`).
  - `gate-out` routes run drive → resistor pad 1 and resistor pad 2 → gate, or drive → gate without a
    resistor.
  - One `gate-return` route runs source → ret, where `source` is the Kelvin-source pad when the group
    names it. Its `partner` is the `gate-out` route of the longest segment.
  - All of them are tier 0.
- **Kelvin pair** (`KelvinPair(name, element, receiver, force)`). Two `kelvin` routes, element pad →
  receiver pad on each side, partnered, tier 1. Their element ends are entry points (decision 5). When the
  receiver's input lies on another net (a series resistor), the route ends at the resistor's pad on the
  element's net, as c0222's walk starts there.
- **Width.**
  - A `gate-out` takes its net's class width. A `gate-return` takes the width of its partner, the gate
    out: it carries the same gate current back (S-0891), and the class width of a power or switch-node
    return net is a power width.
  - A `kelvin` route takes the pair width when its two nets form a differential pair of the model, else the
    track width of the project's `Default` class, else the command's default track width: a sense branch
    carries no current, and its own class is often a power class.
- **Gap.** The gap of a Kelvin pair is the class pair gap when the nets form a pair of the model, else the
  clearance in force between the two nets. The gap of a gate pair is the clearance in force between the
  out and return nets.
- **Layers.** The layers both end pads reach, the pads' side first. A gate return also gets the copper
  layer adjacent to that side for its stacked form (decision 7).
- **Isolation.** A `gate-return` or `kelvin` route whose net has role `power`, `switch_node` or `ground`
  is `isolated`. Its branch must not touch its own net's copper except at its end pads (S-0892; c0222's
  `roles.kelvin-shared` and `roles.gate-return-shared`).
- **Aggressors.** For `kelvin` routes, the `switch_node` nets of the board; for gate routes, the
  `switch_node` nets that no switch of the loop sits on, as c0222's judge exempts a gate from its own
  switch's node. `keep_away` is the profile's `switching_distance_nm`, the same value and source that
  `roles.near-switching` judges (c0222, `H-G-ROLE-NEAR-SW`).
- **Loop points.** For each route, the rest of its role loop from `b` back to `a`: the pad centres of the
  group, with the existing copper path of a joined connection (its track ends in walk order) in its place.
  They feed the area cost of decision 6.

The command converts each `CriticalRoute` into a `JobRoleRoute`, and each group entry into the reply.

### 4. Order: tiers, then rounds

The tiers run in order: 0 (gate loops), 1 (Kelvin pairs). This is the order of c0222's plan.

- **Within a tier.** By group name, then route key. The routes of one group count as one unit: a group is
  routed whole or not at all.
- **Rounds.** c0228's rounds apply inside a tier only: the failed units go first in the next round of
  their tier. The copper of earlier tiers is a fixed obstacle, as c0109 says for tiers.
- **Why Kelvin last.** The keep-away is judged against switching copper, so the gate returns on the switch
  node must stand first.

### 5. Ends: Kelvin entries on the inner half

- **The entry point.** For a Kelvin route, the element end `a.at` is not the pad centre. Let `u` be the
  unit vector from the sense pad's centre `c` to the other sense pad's centre (c0222's axis), and `L` the
  pad's extent along `u`. Then:

  `a.at = c + u · (L/2 − w/2 − MARGIN)`, rounded to the nanometre toward `c`

  with `w` the route width and `MARGIN` c0228's 2 µm. The track end lies inside the pad's copper on its
  inner half, so c0222's offset `t` is positive. This follows S-0850: the sense lines connect inside the
  pads, off the path of the load current.
- **When it does not fit.** If `L/2 − w/2 − MARGIN ≤ 0`, the point is the centre (`t = 0`, which passes
  c0222's `t ≥ 0`).
- **Four-terminal shunts.** The ends are the sense pads, with the entry on the side facing the other sense
  pad. The force pads are obstacles of the route like any pad of another net.
- **Gate returns.** The return end is the source or Kelvin-source pad's centre. Isolation keeps the return
  from starting on the source pour (decision 6).
- **Pair joints.** A pair's coupled part starts and ends where c0228's diagonal from each end meets it. The
  ends are the entry points, so the pair leaves from between the two sense pads and converges to the
  receiver.

### 6. Acceptance and cost in role mode

A shape of a role route is accepted when it passes c0228's acceptance at the route's width and on its
layer, and also:

1. **Isolation.** For an `isolated` route, the copper of its own net is an obstacle, except the end pads and
   the tracks, arcs and vias joined to an end pad without passing another pad or a zone (the part of the
   branch that already stands). Pads, tracks, arcs and vias count at the clearance in force; the outline
   of every zone of the net on that layer must not be touched. A zone outline counts, not only its fill,
   because a later fill would reach the branch; the corridor of decision 10 then keeps the fill at its
   clearance. A shape refused only by this test counts toward reason `isolation`.
2. **Keep-away.** For a route with aggressors, no segment may come within `keep_away` of aggressor copper
   on its layer. The aggressor copper is pads, tracks, arcs, vias and zone outlines. No segment may overlap
   aggressor copper or an aggressor zone outline on an adjacent copper layer. This is the condition that
   `roles.near-switching` judges, tested on outlines instead of fills, so it is never weaker than the
   judge. A shape refused only by this test counts toward reason `near-switching`.
3. **Vias.** A route places no via beyond its `vias` (decision 8).

Among the accepted shapes of a unit, the router keeps the one with the least **cost**:

- **Gate routes:** the absolute shoelace area of the gate loop's centre polyline (the shape's points, then
  the loop points of the route with the partner's placed polyline in place of its straight line), then the
  length, then the shape order. This is a selection cost from S-0891's "minimise the enclosed area",
  computed with `geometry`'s `area2`; it is not a reported measure.
- **Kelvin pairs:** the length of the centre line, then the shape order. The pair's offset keeps the area
  between the branches at the pitch.

Role mode tries every shape and keeps the cheapest; c0228 keeps the first that passes. There are at most 5
plus 8 shapes per layer (decision 12), so the cost of this stays small.

### 7. Gate pairs: side by side, else stacked

For each gate loop the router routes the open `gate-out` routes first (decision 6, against the straight
line of an open return or the copper of a joined one), then the `gate-return`. It tries the forms in
S-0891's order and keeps the first form that passes:

- **Side by side** (S-0891, S-0852). The `gate-return` is routed on its pad's layer with the shapes of
  decision 12, whose Z lines include the lines at the pair pitch `(w_out + w_ret)/2 + gap + MARGIN` on both
  sides of each segment of the partner. The cost of decision 6 picks the shape that hugs the drive.
- **Stacked** (S-0891, "in the shadow of the drive trace on an adjacent layer"), only when no side-by-side
  shape passes. The return leaves the source pad on the pad's layer through a short entry to a via, runs on
  the adjacent copper layer, with Z lines at offset 0 under each segment of the partner, to a via near the
  driver's return pad, and an entry joins that via to the pad.
  - This needs `vias ≥ 2` (decision 8), and the adjacent layer must not be a plane layer of the job.
  - Each via is the return net's class via, placed beside its pad at the distance that keeps the pad
    clearance, in one of the eight octilinear directions; it must pass c0228's acceptance on every layer of
    its span.
  - The return is then measured by c0213's plan area as almost no area, as c0222 states for a stacked
    return.
- **A return carried by a plane.** When the return net is a `ground` net with a zone on the layer adjacent
  to the out route along its whole length, the return is not routed: the plane carries it (S-0891). The
  route's outcome is `plane-return`, and c0222's judge decides on the loop as measured.

Side by side comes first even where a stacked return would enclose less: S-0891 gives the stacked return
for a lack of room, and it costs two vias.

### 8. Vias per role

| route | default `vias` | why | router option to change it |
|---|---|---|---|
| `gate-out` | 0 | the out route is the reference of the stacked form | — |
| `gate-return` | 2 (one at each end, stacked form only) | S-0891's shadow route | `gate-vias=0` turns the stacked form off |
| `kelvin` | 0 | S-0852, S-0892: a pair on one layer; a via needs a keep-out on every layer around it | `kelvin-vias=2` allows one via per branch, each with a corridor on every layer of its span |

A connection whose ends share no allowed layer and whose `vias` is 0 gets reason `no-layer` and the
proposal `allow-via`. With `kelvin-vias`, a Kelvin branch may change layer once, at a via placed at the
corner of an L shape: the shape's first part on `a`'s layer and its second on `b`'s.

### 9. Existing critical copper and `--rip`

- **No silent rip.** Role mode never removes copper on its own. A group whose connections are joined by
  copper is `complete` when the judge finds nothing on it, and `kept` otherwise. A `kept` group gets one
  `route.role-kept` (info) that names its findings, with the proposal `rip`.
- **`--rip` in role mode.** It removes only the copper of the branches of the selected groups:
  - for a Kelvin branch or a gate return, the copper that c0222's branch walk reaches from the receiver or
    return pad without entering power copper;
  - for a gate out, the copper of the out net when no other pad than the group's lies on it.

  Locked copper and script copper are kept, as `--rip` keeps them now. A pour is never removed, nor a
  phase-1 item. `result.rip_kept` counts what was kept, so a group that stays `kept` because its copper is
  script copper says so, with the hint to change the script.

### 10. Locks and corridors

- **Locks.** Every track, arc and via that role mode writes has `locked=True`. KiCad writes
  `(locked yes)`; the Altium writer clears bit 2 of the first flag byte (c0108, `H-A-PCB-CU-LOCK`). c0208's
  `tidy` and `--rip` keep locked items, and so must phases 1 and 4.
- **Corridors** (S-0892: a pour keep-out along the sense trace from beginning to end, and on all layers
  around a via).
  - **Which branches.** Every routed branch, per group and net: the gate out, the gate return and both
    Kelvin branches. c0243's contract names a corridor for the gate net, the return net and each sense net,
    and phase 2 replaces phase 1's provisional ones along its routes, so phase 2 writes the same set.
  - **Name.** `role.corridor.<group>.<net>`, the net name with every character outside `A–Z a–z 0–9 _ + -`
    made `_`.
  - **Setting.** A `Keepout` with `no_copper_pour=True` and every other setting false: tracks, vias and pads
    stay allowed.
  - **Outline.** The route's polyline grown by `w/2 +` the zone clearance in force (the largest clearance of
    the zones on that layer, at least the clearance in force of the net), as an octilinear polygon in
    integer nanometres: the two offset lines of c0228's `offset` with square ends. A polyline whose grown
    outline would cross itself gets one area per segment, under the same name.
  - **Layers.** The route's layer, and every layer of a via's span over a square around the via.
  - **Replaced, never duplicated.** An existing rule area of that name (phase 1's provisional corridor, or
    an earlier run's) is replaced by the new one when the group is routed; a complete group keeps its areas.
  - **What it does.** The corridor keeps every pour off the branch, its own net's included, so the next
    `fill`, phase 1's pours and KiCad's own refill all leave it alone.
- **Ids.** A track is `derived_id("trk", "roles", content_hash(group, net, geometry))`, likewise `via` and
  `rul`. The KiCad uuids are derived from the ids without the build's `fenitm` marker, so a rebuild treats
  the corridors as rule areas drawn on the board and keeps them (`docs/lens.md`).

### 11. Interface with phase 1 (c0243) and the run order

- **Run order (decided 2026-10-29): critical routes first, then power copper, then the rest.**
  - A critical route is constrained: fixed ends, at most 13 shapes per layer, no search.
  - A pour, by contrast, fills around whatever stands, and c0224's `band` narrows within `width` and
    `max_width` where clearance allows.
  - Routing the constrained copper first gives it the room it needs, and leaves the flexible copper to
    adapt. S-0892 describes the same order: the sense trace first, then the keep-out that the pours obey.
- **The other order also works.** With phase 1's copper already on the board:
  - its fills are no obstacle (c0228, decision 3);
  - its zone outlines are obstacles of isolated and keep-away routes (decision 6);
  - its locked tracks and vias are copper of their nets, obstacles like any other;
  - its provisional corridors are replaced along the routes (decision 10);
  - the corridors cut the pours on the next fill.

  A pour that leaves no room gives reason `isolation` or `near-switching`, naming the zone, with the
  proposal `free-corridor`.
- **What phase 2 hands phase 1.**
  1. **Locked items.** Phase 1 never moves, narrows or removes them.
  2. **Corridors.** Pours respect them by the board's own rule areas; phase 1 treats every
     `role.corridor.*` area as an obstacle and never edits or removes one that it did not write.
  3. **`critical_copper(design, roles) -> CriticalCopper`** in `fenolite.roles.routes`, which returns, per
     gate loop and Kelvin pair, the corridor ids and the ids of the locked tracks, arcs and vias of the
     group's nets that lie inside the group's corridors of their net. It reads the board, so it works on a
     board read back from KiCad, whose ids are derived from uuids.
- **What phase 2 expects from phase 1.**
  - Phase 1's power copper keeps the clearance in force from locked copper, as any copper does.
  - After phase 1, `roles.rules` is run again as phase 1's own acceptance gate.
- **Not taken from c0243's text:** phase 2 does not route the switch-node connections that phase 1 leaves as
  `roles.copper-blocked`; those are hot-loop copper, which the maintainer gave to phase 1.

### 12. Z shapes (S-0837)

S-0837 describes pattern routing with L and Z patterns. c0228 has the L shapes and their 45° variants. Role
mode adds Z shapes: a first segment, a middle segment along a free line, a last segment, with 90° corners.

- **Middle lines.** For each axis, at most 4 coordinates are taken, nearest to the straight line between the
  ends first, from:
  - the two coordinates at `keep_away` plus half the width beyond each side of the bounding box of the
    aggressor copper and zone outlines between `a` and `b`;
  - the two coordinates at the clearance in force plus half the width beyond the bounding box of each
    obstacle that refused the shape of c0228 shape order;
  - for a gate route with a partner, the lines at the pair pitch on both sides of each partner segment
    (side by side), or at offset 0 (stacked).

  This gives at most 8 Z shapes per layer.
- **Order.** They are tried after the five shapes, every shape on every allowed layer, and the cost of
  decision 6 chooses among all the shapes accepted.
- **Pairs.** The centre line of a pair may be a Z shape, offset as c0228's pairs are.
- **Off for measurement.** `--router-option z-shapes=off` turns them off in role mode. A plain
  `octilinear` job keeps its five shapes and its bytes.

### 13. Judged twice: `role_check` and the DRC gate

- **`extra["role_check"]`.** The command adds to `RoutingJob.extra` a callable `role_check(design) ->
  tuple[RoleFinding, ...]`. Each finding is `(code, group, severity, measure)`, `measure` being an integer
  (the ratio in per-mille of a loop finding) or `None`. The callable runs `fenolite.roles.judge` on the
  design with the stored and declared roles. It is built by `cli`, as `copper_check` is, so `routing`
  imports nothing new.
- **The comparison.** After its last round and after `copper_check`, the router judges the board before and
  after the job's copper.
  - **Worse.** A group is worse when, after routing, it has a code it did not have before, or the same code
    with a larger measure. A worse group's copper is removed whole, both partners and every route, with one
    `route.role-refused` (warning) naming the group, the code and both measures. The check is not run
    again, because removing a group's copper cannot make another group worse.
  - **Better.** A group whose findings went away is `routed` with its before and after findings in the
    reply.
- **`roles.loop-open`** counts as no finding, before and after: it is the open connection that role mode is
  closing, and a group is routed whole or not at all.
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
| `skipped` | not attempted (`unconfirmed`, or a hot loop named by `--group`: `phase-1`) |

`unrouted` and `refused` give one issue each (`route.role-unrouted`, `route.role-refused`); the unconfirmed
groups give one `route.role-unconfirmed` that names them. Each carries one reason and one proposal from
closed tables, each with the command to run.

| reason | when | proposal |
|---|---|---|
| `no-room` | every shape on every layer refused by clearance | `free-corridor`: the three nearest blocking items of the shortest shape, a `render --region` command around the connection |
| `too-long` | every shape longer than `max-length` | `raise-limit` (`--router-option max-length=…`) or `move-part` |
| `no-layer` | the ends share no allowed layer and the route allows no via | `allow-via` (`kelvin-vias=2`) or `move-part` |
| `near-switching` | every shape that kept clearance broke the keep-away | `free-corridor` naming the aggressor items, or `move-part` |
| `isolation` | every shape that kept clearance touched its own net's power copper | `free-corridor` naming the zone or track of the net |
| `role-check` | routed, then a finding got worse | the finding; `free-corridor` |
| `drc` | dropped by `--gate drc` | the DRC finding's type and items |
| `pads` | a group pad is missing from the board | `move-part` or edit the role (`fenolite roles --set`) |
| `unconfirmed` | inferred and not confirmed | `confirm`: `fenolite roles PATH --accept-group NAME --dry-run` |
| `phase-1` | a hot loop named by `--group` | `power-copper`: the hot loop is phase 1's power copper |

- **The region.** The `render --region` command covers the bounding box of the group's pads, grown by
  2 mm, with `--nets --open`, as c0211 draws it.
- **`move-part`.** It names the connection and its two pads, and the length the shortest shape needs.
  Fenolite computes no new position.
- **`route.role-placement`** (info). A gate loop whose placement bound (c0222) is above the user's
  `gate_max` gets this info: no route can bring the area under the bound. It names the bound and the
  limit. Without a user limit there is nothing to compare.
- **`--require-complete`** adds one `route.incomplete` (error) naming the groups of every
  `route.role-unrouted` and `route.role-refused`, with exit 5 and no write, as it does for open nets; each
  code keeps its one severity in `ISSUE_CODES`.

### 15. Command line, result and protocol

- **Synopsis.** `fenolite route PATH --router NAME --roles critical [--group NAME]... [--roles-file FILE]
  [--rip] [--gate drc] [--router-option KEY=VALUE]... [--require-complete] [-o OUT] [--dry-run | --confirm
  [--plan ID]]`.
- **`--roles`.** It takes one value. This change defines `critical`; phase 4 will add `propose`.
  `--roles-file` names the role document, as `roles --roles FILE` does. `--group` and `--roles-file` are
  valid only with `--roles`. With `--roles`, `--nets`, `--escape`, `--order` and `--pairs-as-nets` are usage
  errors (`FEN-2001`): the roles choose the nets and their order.
- **The role options.** `octilinear` takes these router options in role mode: `gate-vias`, `kelvin-vias`,
  `keep-away=LENGTH` (default: the profile's `switching_distance_nm` with its overrides), `z-shapes=on|off`,
  and c0228's `max-length` and `rounds`.
- **Roles.** The command reads the stored roles (`.fenolite/rules.json` or the role document) and the
  declared ones. No roles, or no gate loop or Kelvin pair, means exit 0, nothing planned, and one
  `route.role-none` (info).
- **Verdict.** Per role connection, not per net. A critical net usually keeps other open connections (an
  output net's pour to its terminal is phase 1's work), so `route.unrouted` is not given for the nets of a
  role job. `result.selected`, `routed` and `unrouted` hold the nets of the routes, judged on the role
  connections only.
- **`result.roles`.** One entry per group of the plan, sorted by tier and name:
  - `group`, `kind` (`gate_loop`, `kelvin_pair`, `hot_loop`) and `status`;
  - `connections`: each with `key`, `net`, `a`, `b`, `layer`, `form` (`single`, `pair`, `side-by-side`,
    `stacked` or `plane-return`), `length` and `vias`;
  - `findings_before` and `findings_after`: the `role_check` findings of the group;
  - `reason` and `proposal` (`kind`, `text`, `command`, `region`) when not routed;
  - `copper` and `corridors`: the ids.
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
A fault of the netlist is not copper: the `open` netlist is the `good` one where `bad` connects a pin
otherwise.

| board | critical copper left out in `open` | phase 2 routes | faults that stay (phase 1's) |
|---|---|---|---|
| `buck_shunt` | both sense lines | the Kelvin pair from the inner halves of `R12`'s pads to `U3`, isolated from the `VL` and `VOUT` pours, fenced by two corridors | the hot loop with `C1` 15 mm away (`roles.loop-area`) and the 0.3 mm track on the 2 A output (`roles.width-current`) |
| `half_bridge` | the high side's gate return and its tie to the source pour (`ks_tie`, `gh_ret` and its via), the low side's gate detour (`gl`), the sense pair | gate loop `gate_Q1` (return on `SW` from `Q1`'s Kelvin-source pad, isolated from the switch-node pour) and gate loop `gate_Q2` (out `GL` against its return under it); the Kelvin pair on `R1`, which `SW_UNDER` on `In1.Cu` blocks | the single bus via (`roles.via-current`) and `SW_UNDER`, the switch-node pour under the sense path: the pair is `unrouted` with reason `near-switching` and the proposal `free-corridor` naming `SW_UNDER`; once that pour is gone, a second run routes the pair |
| `bms` | the two sense lines from the force pads; the monitor's sense inputs on the sense nets | the Kelvin pair from the inner halves of `R1`'s sense pads to the monitor, with the force pads as obstacles | the 1 mm pack neck at 20 A (`roles.width-current`) and the ground slot under `TAP0` (`roles.return-gap`) |

**The gate** (`tests/unit/roles/test_critical_reference.py`, and `tests/kicad/roles/test_critical_drc.py`
for DRC):

1. For each `open` variant, confirm its groups as the reference tests do, run `route --router octilinear
   --roles critical --confirm`, then `roles --check`. The findings left are exactly those of the table's
   last column (and, for the blocked pair, its `roles.loop-open`).
2. On each `good` variant the same command plans no write. Every group is `complete`, and the reply holds
   no `route.role-*` warning.
3. Run again on the routed `open` board: no write, every routed group `complete`.
4. Rebuild the routed `open` project twice: the role copper and corridors are kept, and the second rebuild
   writes the bytes of the first.
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
| `route.role-unrouted` | warning (`route.incomplete` with `--require-complete`) | a critical group not routed: reason and proposal |
| `route.role-refused` | warning (`route.incomplete` with `--require-complete`) | a routed group removed because a role finding got worse |
| `route.role-unconfirmed` | info | the inferred groups not routed, with their count and names |
| `route.role-kept` | info | a complete group with findings, not ripped |
| `route.role-placement` | info | a gate loop whose placement bound exceeds the user's limit |
| `route.role-none` | info | no gate loop or Kelvin pair to route |

## Hypotheses registered by this change

| id | statement | settling test | criterion |
|---|---|---|---|
| `H-G-CRIT-KELVIN` | Inner-half entries, isolation and corridors give Kelvin pairs that c0222 judges clean | `tests/unit/roles/test_critical_reference.py -k kelvin` | on the `buck_shunt` and `bms` `open` variants, and on `half_bridge` `open` once `SW_UNDER` is gone, no `roles.kelvin-outer`, `roles.kelvin-shared` or `roles.kelvin-apart` after routing; every entry offset `t > 0` |
| `H-G-CRIT-GATE` | Side by side, else stacked, keeps gate loops under `gate_ratio_max`, with the return from the source pad | `tests/unit/roles/test_critical_reference.py -k gate` | on `half_bridge` `open`, both gate loops at or under 2000 per-mille and no `roles.gate-return-shared` |
| `H-G-CRIT-KEEPAWAY` | The keep-away refuses every shape over switching copper, and the Z shapes route a sense pair clear of switching copper that the five shapes cross | `tests/unit/routing/test_roleroute.py -k keepaway` and `-k half_bridge` of the reference test | on the authored bench the five shapes alone fail with `near-switching` and the Z shapes pass; on `half_bridge` `open` the pair is refused with `near-switching` naming `SW_UNDER`, and no `roles.near-switching` is written |
| `H-G-CRIT-IDEMPOTENT` | Role routing is a fixed point: a second run and two rebuilds change no byte | `tests/unit/roles/test_critical_reference.py -k again` | no write on the second run; equal bytes after the second rebuild |
| `H-K-CRIT-DRC` | KiCad's DRC finds nothing new on the reference boards after role routing | `tests/kicad/roles/test_critical_drc.py` | on KiCad 9 and 10, `--gate drc` drops nothing and no violation type grows, on each `open` variant |
| `H-A-CRIT-READBACK` | The Altium convert of a routed board keeps the role copper, its locks and its corridors | `tests/unit/roles/test_critical_reference.py -k altium` | every role track and via read back at its position and width with `locked` true, each corridor as a pour keep-out on its layers, and equal `roles.*` findings on both readings |

## Evidence level per behaviour

| behaviour | level | proof |
|---|---|---|
| job, protocol, plan, codes | `INFERRED` until a release; plain data | `tests/unit/routing/test_protocol.py -k roles`, `tests/unit/roles/test_routes.py` |
| routed copper | `UNVERIFIED` until checked | "Router protocol" |
| role findings after routing | `INFERRED` (`H-G-CRIT-KELVIN`, `-GATE`, `-KEEPAWAY`), with c0222's hypotheses | the open variants |
| KiCad board with `--gate drc` | `KICAD-VERIFIED` per major (`H-K-CRIT-DRC`) | the kicad-9 and kicad-10 jobs |
| Altium output | `INFERRED` (`H-A-CRIT-READBACK`) | the read-back comparison |

## Size and cut order

Sizes in design-days, as in `docs/roadmap.md`:

| part | days |
|---|---|
| entry check, protocol fields, feature `roles`, codes | 0.5 |
| `roles.routes`: plan, widths, layers, entries, isolation, aggressors, `critical_copper` | 0.75 |
| command: `--roles`, `--group`, role extras, `result.roles`, rip of branches | 1.0 |
| role mode in `octilinear`: tiers, entries, isolation, keep-away, cost choice | 1.25 |
| gate pairs: side by side and stacked with vias, plane return | 1.0 |
| Z shapes | 0.5 |
| `role_check` comparison, reasons and proposals, `--gate drc` groups | 0.5 |
| locks, corridors, idempotence, rebuild | 0.5 |
| open variants and the acceptance gate, Altium read-back | 0.5 |
| docs, guide, evidence, closing | 0.5 |
| **total** | **7.0** |

The hot legs left with the maintainer's decision of 2026-10-29 (about 0.5 day); the corridors on every
branch and the outcome record came in.

**Cut order**, cheapest loss first, if time runs short:

1. **Z shapes.** Without them, a pair or a return that must pass beside an obstacle stays `unrouted`.
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
- **Power copper can block a sense pair.** The half-bridge `open` variant keeps `SW_UNDER`, phase 1's copper,
  under the only path to the amplifier's inputs, which lie between the switch-node pour, the source pour
  and the shunt's ground pour. Role mode refuses every shape over it and names it; it does not move power
  copper. Phase 1 places switch-node copper, and a second run of phase 2 then routes the pair.
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
- **Script copper blocks `--rip`.** The bad variants draw their faults as script copper, so the acceptance
  uses the `open` mode rather than `--rip`. A user whose script draws a bad sense line must edit the
  script, and the reply's `rip_kept` says so.
- **c0243 in parallel.** The corridor name and the obstacle rule are settled with c0243 (decision 11);
  `critical_copper` reads the board, so it does not depend on how either phase stores its ids.

## Open Questions

All decided by the maintainer on 2026-10-29.

1. Are inferred groups that are not confirmed routed? **Decided:** no. They are listed with
   `route.role-unconfirmed` and the `roles --accept-group` command.
2. Which run order of phases 1 and 2? **Decided:** critical routes first, then power copper (decision 11),
   with both orders supported through locks, corridors and outline-aware acceptance.
3. Does phase 2 route hot legs as tracks, or leave the whole hot loop to phase 1's pours? **Decided
   (overriding the recommendation):** the whole hot loop is phase 1's. Phase 2 routes no hot-loop leg, and
   `critical_copper` hands over no capped hot leg.
4. May a gate return use vias by default for the stacked form? **Decided:** yes, at most one at each end
   (S-0891). Kelvin branches get none unless a router option allows them (S-0892).
5. Are the route constraints (vias, keep-away, Z shapes) router options or new role limits? **Decided:**
   router options in this change, so the model and `rules.json` do not change.
6. How is the Altium deliverable made? **Decided:** `fenolite convert --to altium` of the routed KiCad
   project now. Routing a `.PcbDoc` in place waits for c0241's edit sessions.
7. What is the surface? **Decided:** `route --router octilinear --roles critical`, with `--router` still
   required and `roles` a router feature. Phase 4 then adds `--roles propose` beside it.
8. Does `--rip` in role mode remove only the groups' branches? **Decided:** yes: c0222's branch walk, never
   locked or script copper, never a pour.
9. What is the corridor name? **Decided:** `role.corridor.<group>.<net>` for both phases (c0243's decision 8).
