## Context

- **Request.** Phase 1 of c0222's plan: generate the power and ground copper from confirmed net roles. The
  maintainer decided the following on 2026-10-28 and 2026-10-29 (c0222, `design.md`):
  - roles are inferred and then confirmed;
  - the deliverable is the critical routes and the power copper made automatically, with the rest
    proposed;
  - the output goes to KiCad and to Altium;
  - default limits come from public sources and are warnings, while the user's limits on confirmed roles
    are errors;
  - the user declares the creepage distances;
  - the phases run in the order 0 → 1 → 2 → 4 → 3;
  - the target boards have 2 to 4 layers and at most 150 parts.
- **Base.** The branch `c0222-net-roles` at `ff9d9e4c` (c0222 implemented and archived, merged with
  `origin/dev`; `dev` is cut at `0.6.0` and not yet published).
- **What phase 1 builds on:**
  - **c0222.**
    - `RoleSet`, with net roles (`milliamps`, `working_mv`, `sensitive`), hot loops, Kelvin pairs and gate
      loops;
    - `roles.profile`, with `width_per_amp_nm` 0.381 mm/A (S-0851), `milliamps_per_via` 200 (S-0851) and
      `switching_distance_nm` 1 mm (`H-G-ROLE-NEAR-SW`);
    - the S-0269 fit when the user gives a rise;
    - `fenolite.roles.judge`, the judge of the stage `roles.rules`;
    - the three reference boards with good and bad variants, whose power copper is ordinary `zone()` and
      `track()` items of the script.
  - **c0224.** `band`, `barrier`, `keepout_ring`, `body_keepout`, `fanout_zone` and `stitch_pieces`.
    - They are recorded by the script and resolved by `backends.kicad.generate.resolve_generated` after
      placement and script copper, into locked zones, rule areas, tracks and vias whose ids derive from
      their keys.
    - The records are structural protocols (`BandLike`, `AreaLike`, …), so any package can make one
      without importing `dsl`.
    - Two zones of one net and one priority that overlap give KiCad's `zones_intersect`.
    - The Altium target refuses generated copper (`kicad.generate.altium`).
  - **Altium script copper.** `cmd_build` resolves the script's copper intents in an in-memory KiCad build
    and hands the result to `build_altium` as a `CopperSource(origin="script")` (`altium-build`, "Script
    copper in an Altium build"). Since c0215, the zones written there are poured by Fenolite. Their pad
    connections become one Polygon Connect Style rule per net (`backends/altium/connectstyle.py`, from the
    net's zone of highest priority). A pad's own `zone_connection` is not carried.
  - **Analyses and gates.**
    - c0204's simulated pour and relief and dead-copper checks;
    - c0213's necks and loop areas;
    - c0175's power paths;
    - c0225/c0209's `api.trial(..., gate=True)`;
    - the Clipper union backend of `geometry.boolean`, from the `geo` extra.
- **The layering constraint.** `roles` may import `model`, `geometry`, `backends.base` and `analysis`.
  `lens` may import `model` and `backends`. Only `cli` and the root modules may import `roles`. So the
  build cannot call the planner directly. It takes the planner as a callable from `cmd_build`, just as
  `checks.roles` takes `fenolite.roles.judge` from `cmd_check`.

## Goals / Non-Goals

**Goals**

- From the confirmed or declared roles of a placed board, write the power, switch-node, ground and
  high-voltage copper that a careful human would draw first: sized by current, compact where switching,
  solid where current flows, stitched where it changes layer, and kept away from high-voltage copper by the
  user's distance.
- Make the same copper reach a KiCad board and an Altium board from one script.
- Prove each result with c0222's own checks. A board that phase 1 touched must never judge worse.
- Leave phase 2 a stable interface: the corridors, the role-copper keys, and a rule that the two phases can
  run again in either order.

**Non-Goals**

- See the proposal. In addition:
  - no autorouting of signal nets;
  - no change of a role by phase 1;
  - no default current, rise or distance;
  - no edit of an existing `.PcbDoc`.

## Decisions

### 1. What phase 1 generates, per role

Phase 1 reads only roles whose source is `confirmed` or `declared`. An inferred role that the user has not
confirmed gets nothing, with `roles.copper-skipped` (reason `unconfirmed`). Copper is a write, and c0222
caps unconfirmed roles at a warning for the same reason.

| role | copper | pad connection | layers by default |
|---|---|---|---|
| `power` with `milliamps` | one zone per layer: the union of bands along the net's spine tree, `width` from the current (decision 2), `max_width` = 2 × `width` | solid | the layer of the net's SMD pads; both outer layers for a net of through-hole pads only |
| `switch_node` | as `power`, but `max_width` = `width` (no widening), and kept off sensitive copper (decision 4) | solid | the layer of the switch pads |
| `ground` | one zone over the board outline on each reference layer, lowest priority; stitching (decision 5) | thermal on through-hole pads, solid on SMD pads (`thru_hole_only`) | 2 layers: `B.Cu`; 4 layers: `In1.Cu` |
| `high_voltage` | as `power` when it has `milliamps`; a clearance rule and a keep-out band at the user's distance (decision 7) | solid | as `power` |
| `power` or `switch_node` without `milliamps` | nothing; `roles.copper-skipped` (reason `current-missing`) | — | — |
| `kelvin`, `gate`, `signal` | nothing; corridors for the groups (decision 8) | — | — |

- **Why solid for current-carrying roles.** A relief exists to ease soldering by raising the thermal
  resistance of the joint (S-0861, S-0862). On a pad that carries the role's current, its spokes narrow the
  copper path that phase 0 judges. Ground keeps reliefs on through-hole pads, where soldering is the risk
  that S-0861 names, and SMD ground pads of the hot loop stay solid.
- **Why only one setting per net.** c0215 lowers one Polygon Connect Style rule per net for Altium, and a
  pad's own `zone_connection` is not carried there. So phase 1 sets connections per zone (per net), and the
  two targets get the same copper.
- **Overrides:**
  - `role_copper(connection={"ground": "solid"})`, `layers={"power": ("F.Cu", "B.Cu")}` and
    `ground_layers=(...)` in a script;
  - `--connection KIND=MODE`, `--layers KIND=L,L` and `--ground-layers L,L` on the command line.
- **Nets with the user's own zones.** A role net that already holds a zone of the user on a layer gets no
  generated zone on that layer: `roles.copper-skipped` (info, reason `user-copper`). The user's tracks do
  not stop generation; a generated zone simply joins them. So a board poured by hand is left as it is.

### 2. Width from current

- **Without a rise** (S-0851): `width = ceil(milliamps × width_per_amp_nm / 1000)`.
- **With a rise** (`--temp-rise`, the requirements file, or `role_copper(temp_rise=...)`): the smallest
  integer width whose S-0269 capacity, at the layer's copper thickness from the stack-up, is at least the
  current. It is found by bisection over integer nanometres on `analysis.current`'s capacity function,
  which rises with width.
- The width is at least the net class's track width.
- The result names the method of each net (`rule-of-thumb` or `fit`), as c0222's findings do. Above 1 A
  without a rise, it adds c0222's hint to give a rise.
- `max_width` is `widen_permille × width / 1000` (default 2000 for `power` and `high_voltage`, 1000 for
  `switch_node`). Wider copper lowers resistance and heat. A switch node does not widen, because its
  copper area is a coupling plate (S-0860).

### 3. Spine trees and power zones

- **Terminals.** The pads of the net. Pads of one part closer than `2 × width` form one cluster, so a
  transistor's drain tab and pins are one terminal.
- **Tree.** `roles.spine` builds a rectilinear tree over the cluster centres:
  - Prim's order by Manhattan distance, in pad-key order on ties;
  - each edge is an L-shaped or Z-shaped path of horizontal and vertical segments on a grid of `step`
    (default `width / 2`, at least 0.1 mm), chosen as the cheapest path on that grid;
  - the cost of the path is its length, plus a penalty for each turn, plus the obstacle cells it would
    cross;
  - an obstacle is a pad, track, via or keep-out of another net, grown by the clearance plus half the
    width, or a corridor (decision 8).
  - An edge with no path is `roles.copper-blocked` (warning), naming the two clusters and the layer.
- **Hot loop first.** The edges between consecutive pads of a `HotLoop` that share a net are placed first,
  on the pads' own layer, so the commutation loop closes on one layer. The input capacitor joins the
  switches through the shortest straight leg (S-0860: first and widest). The rest of the tree follows.
- **Zone.** Each edge is a c0224 band record (`width`, `max_width`, `step`, `clearance`, the layer)
  carrying a new optional attribute `group`, `role.<kind>.<net>.<layer>`.
  - `resolve_generated` resolves each band's outline with c0224's cells and levels, unchanged, and then
    unites the bands of one group into one locked zone, with the `geo` extra's Clipper union. That avoids
    KiCad's `zones_intersect` between overlapping zones of one net.
  - A tree that is one chain (each cluster on at most two edges, joined end to end) is one band with no
    union, so it needs no extra.
  - A branching tree without the `geo` extra is `roles.copper-extra` (warning), and only its longest
    chain is generated.
- **Priority.** Switch node 3, power and high voltage 2, ground 0 (the ground pour gives way to every
  other role zone, where KiCad's fill and c0215's pour respect priority).

### 4. Switch node: compact and away from sensitive copper

- The zone has the required width only (decision 2), along the shortest tree between the switch pads and
  the inductor or winding pad.
- **Victims** are c0222's: each `kelvin` net or branch, each `gate` net of another switch, and each
  `signal` with `sensitive`.
- **On the zone's own layer:** a clearance rule `role.sw.<net>` of the model, between the switch node and
  each victim net, with `switching_distance_nm` (c0222's profile, 1 mm). KiCad's fill and DRC enforce it,
  and Altium lowers it as a clearance rule scoped by net.
- **On the adjacent layers:** the zone's spine treats the existing copper of a victim on a neighbouring
  layer, grown by the switching distance, as an obstacle. That is the overlap that c0222's
  `roles.near-switching` reads through the returns and coupling analyses.
- The ground plane on the adjacent layer is not cut. Ground under the switch node is what S-0851 asks.
- **Placement fault.** When the user gives a `loop_max` for a hot loop and the loop's placement bound
  (c0222) is already over it, no copper can meet it. That is `roles.copper-placement` (warning), naming
  the bound and the limit. Phase 1 still draws the copper.

### 5. Ground zones and stitching

- **Zones.** For each `ground` net, one zone over the board outline (inset by the board's edge clearance)
  on each reference layer: by default `B.Cu` on 2 layers and `In1.Cu` on 4 layers. `In2.Cu` is left to
  the user or to a `power` plane. On a 2-layer board, the free top area may also be poured with
  `ground_fill="all"` (default `"reference"`). The planner writes these zones directly as model zones,
  locked and with key-derived ids, because c0224 has no "zone" call.
- **Stitching.** One c0224 `stitch_pieces` record per ground net over the ground zones on different
  layers:
  - `pitch` is `stitch_pitch_nm` (default 5 mm, a Fenolite heuristic, `H-G-ROLE-COPPER-STITCH`);
  - `min_vias` is 2, so no piece is joined at one point only (S-0863);
  - the via size comes from the net's class.
- **Pitch.** `docs/roles.md` gives the public method behind a pitch: at most one twentieth of the
  wavelength in the board at the highest significant frequency (S-0863). The user who knows that frequency
  sets `stitch_pitch`. Fenolite takes no frequency default.
- **Islands.** A piece of a generated ground zone that the fill leaves unconnected is found by c0204's
  `dead` check. Since c0224's zones keep `island_removal` at its default, it is removed by the fill.

### 6. Via arrays at layer changes

- **Where.** A power, switch-node or high-voltage net changes layer where its terminals lie on two copper
  layers (SMD pads on both sides), or where the user gives it two layers. The planner then generates its
  zone on both layers, and the overlap of the two zones near the transition is a patch: the hull of the
  two terminal clusters' copper on both layers, grown by `width`.
- **How many vias.** A `stitch_pieces` record for the net, limited to that patch by a new optional
  attribute `patch`, with:
  - `min_vias = ceil(milliamps / milliamps_per_via)` (c0222's profile, 200 mA, S-0851);
  - `pitch` = via diameter + the net class's clearance.

  S-0860 gives a laxer rule of thumb (one via per ampere). The profile keeps S-0851's stricter figure, and
  `docs/roles.md` names both.
- A patch that holds fewer vias than `min_vias` is c0224's `kicad.generate.stitch-short`. It is reported
  again as `roles.via-current` by the phase-0 judge that verifies the result (decision 10), with the
  role's severity.
- **Placement of the vias.** They lie inside the patch, never between the input capacitor and the switch
  pads of a hot loop: the hot loop's pads, grown by `width`, are excluded from the patch (S-0860).

### 7. High voltage

- For each `high_voltage` net, and each `power` net whose `working_mv` is at or above `high_voltage_mv`,
  the distance is the largest `min` of the user's `[[distance]]` and `[[step]]` rows that name the net
  (c0222, "Returns and high voltage").
- **No row:** no copper of any kind is generated within reach of the net, and the net's own band is
  skipped. The reason is c0222's `roles.limit-missing` (warning), with the method named by S-0854.
- **With a row:**
  - **Rule:** a clearance rule `role.hv.<net>` between the net and every other net (`net` selectors) at
    the distance. KiCad's fill and DRC enforce it, and Altium lowers it as a clearance rule.
  - **Barrier:** a keep-out band around the net's copper, with the distance as `setback`, forbidding
    tracks, vias and pours of other nets. It is c0224's barrier geometry (convex envelopes, two rule areas
    per piece, `pieces` allowed), on the net's copper rather than a class's.
  - **Order:** the barrier is resolved after the bands, so the envelope holds the net's generated band.
    This is a new barrier form inside `resolve_generated` (a `nets` attribute instead of `netclass`).
    `Design.barrier` in a script is unchanged.
  - **Creepage.** On one surface, a creepage path is never shorter than the straight distance, so a
    clearance at the creepage distance is enough there. Slots and grooves stay judged by c0222's distance
    analyses.

### 8. Corridors for critical routes: the interface with phase 2

Phase 1 runs before phase 2 and leaves the critical paths free.

- **Gate loops.** For each `GateLoop`:
  - one corridor joins the driver output pad, the gate resistor pads and the gate pad;
  - one joins the source (or Kelvin-source) pad and the driver's return pad.
  
  When the two lie within one corridor width of each other, they become one corridor, where phase 2 routes
  out and return as one pair.
- **Kelvin pairs.** For each `KelvinPair`, one corridor runs from the inner half of each sense pad (c0222's
  attachment direction `u`) to the receiver pads.
- **Shape.** The convex hull of the straight segments between the pad centres, grown by half the corridor
  width. The default width is `2 × class width + pair gap + 2 × clearance`, where the pair gap is the
  class's differential gap, or else its clearance.
- **Written as** rule areas `role.corridor.<group>`, forbidding pours only, on the outer layer of the
  group's pads. The ground plane on the other layers stays whole, so the gate return can run over ground,
  as S-0853 wants.
- A corridor that would cover another net's pad, or a locked item, is not written. That is
  `roles.corridor-blocked` (warning), and phase 2 then routes around the copper.
- **The contract with `c0244-critical-routes`:**
  1. Phase 1 owns the keys `role.*`. Phase 2 never edits or removes an item with such a key, but it may
     connect to one.
  2. Phase 2 reads corridors by the name prefix `role.corridor.`. It may route outside them, and it does
     not delete them. A pour-only area does not hinder its tracks.
  3. Each phase treats the other's copper as obstacles. So the recommended order is 1 then 2, and either
     may run again after the other: a phase-1 run after phase 2 keeps phase 2's tracks as obstacles and
     its corridors as written.
  4. The result of `copper` lists `corridors[]` (group, kind `gate` or `kelvin`, layer, polygon, width),
     which phase 2 may take instead of reading the board.
  5. The hot loop is copper of phase 1 (c0222's plan). Phase 2 routes the gate loops, the Kelvin pairs
     and, after them, the switch-node connections that phase 1 left as `roles.copper-blocked`.

### 9. Surfaces

- **DSL:**

  ```python
  design.role_copper(kinds=("power", "switch_node", "ground", "high_voltage"), ground_layers=None,
                     layers=None, connection=None, ground_fill="reference", stitch_pitch=None,
                     temp_rise=None, widen=None, corridors=True, keep=(), regenerate=())
  ```

  - **Recording.** The call records plain data. A second call, an unknown kind or mode, or a layer that
    the board lacks raises `DslError`. `fenolite.dsl.role_copper(design)` returns the record.
  - **The build:**
    1. resolves the roles after placement (as c0222 does);
    2. resolves script copper and c0224's generated records;
    3. calls the planner it was given (`lens.rolecopper.RoleCopperPlanner`, a protocol: a callable from
       the placed model `Design`, the `RoleSet` and the request to a `RoleCopperPlan` of c0224-protocol
       records, plain zones and keep-outs, model rules and issues);
    4. resolves the plan with `resolve_generated`, in the order of decision 11.

    `cmd_build` passes `fenolite.roles.copper.plan`.
- **CLI:**

  ```
  fenolite copper PATH [--roles FILE] [--requirements FILE] [--kinds KIND,...] [--net GLOB]...
                       [--layers KIND=L,L]... [--ground-layers L,L] [--ground-fill reference|all]
                       [--connection KIND=MODE]... [--stitch-pitch LENGTH] [--temp-rise KELVIN]
                       [--widen PERMILLE] [--no-corridors] [--regenerate KEY]... [--gate drc]
                       [--kicad-cli PATH] [--dry-run | --confirm [--plan ID]]
  ```

  - **Input.** `PATH` is a `.kicad_pcb`, a `.kicad_pro` or a built project folder. The roles come from the
    companion document or `.fenolite/rules.json`, as in `fenolite roles`. A `.PcbDoc` is `FEN-2001`, with
    the hint to build its script with `design.role_copper()`.
  - **Output.** Schema `fenolite.copper.v0`. `result` holds `nets` (per net: kind, method, width,
    `max_width`, layers, zone keys, skipped reason), `vias`, `corridors`, `rules`, `kept`, `before` and
    `after` (the role findings), `plan` and `plan_id`.
  - **Writes.** The command never writes without `--confirm --plan ID`. It writes the board and
    `.fenolite/role-copper.json` together, or neither.
  - **Exit codes.** 0, or 4 without confirmation. 5 when an error finding stands (`roles.copper-worse`,
    a `kicad.generate.*` error); nothing is written then. 6 when `--gate drc` lacks `kicad-cli`. 2 for a
    bad option.
- **Why both.** The maintainer's boards are often drawn by hand in KiCad, and the command serves them. A
  script serves both targets. One planner keeps the two results equal: a test builds a script with
  `role_copper()` and runs `copper` on the same script's build without it, and compares the role items.

### 10. Verification

1. **Before:** the role judge (`fenolite.roles.judge`) runs on the input board.
2. **After:** the planner applies its plan in memory, simulates the pour of every zone it touched (c0204's
   `simulated` state), and runs the judge again.
3. **Worse:** a finding of warning or above on a role net that `after` holds and `before` did not (same
   code and subject) is `roles.copper-worse` (error), which names the finding. Nothing is written, and the
   build exits 5. A finding that `before` held and `after` lacks is listed as cleared.
4. **With `--gate drc`** (KiCad only), `api.trial(..., gate=True)` drops each generated item that brings a
   new KiCad DRC finding and reports it, as c0225 does for `route` and `tidy`.
5. **The written zones** are outlines. The reply names `fenolite fill` as the next step, and then `fenolite
   check` (whose `roles.rules` reads the saved fill).

### 11. Order inside a run

Each step runs in key order:

1. corridors;
2. high-voltage rules;
3. bands of the switch nodes, then of the power and high-voltage nets (hot-loop edges first);
4. net barriers;
5. ground zones;
6. ground stitching, then via arrays.

The vias see every zone, and the barriers see the bands. The script's own c0224 records are resolved
before all of these, so role copper respects the script's keep-outs.

### 12. Kept copper and repeat runs

- **Ids.** Every role item has a key `role.<kind>.<net>[.<layer>|.<n>]`, made safe as c0224's names are.
  Its id derives from the key, so a run replaces its own items and removes those whose key is gone (c0224's
  orphan rule).
- **Manifest.** `.fenolite/role-copper.json` (canonical JSON, schema `fenolite.role-copper.v0`) records,
  per key, the SHA-256 of the item's canonical model JSON as last written.
- **User edits.** On a run, an item with a role key whose fingerprint differs from the manifest was edited
  by the user. It is kept as an obstacle and not regenerated: `roles.copper-kept` (info). The user can
  force it back with `--regenerate KEY` or `role_copper(regenerate=...)`. `keep=` in a script, and a
  `locked` item without a role key, are always kept.
- **What is never touched.** Items without a role key. The planner deletes nothing else.
- **Repeat runs.** Two runs on the same input give the same plan. A run on its own output plans no change,
  so the command writes nothing and says so.

### 13. Altium output

- The in-memory KiCad build of "Script copper in an Altium build" now also runs when the script has
  generated records or a `role_copper` record. The `CopperSource` then carries:
  - the generated and role zones, which `build_altium` writes as polygons, poured by c0215 (`computed`);
  - the rule areas, which become keep-out records with their restrictions (the name is lost:
    `altium.not-lowered` info, as for any named keep-out);
  - the vias and tracks.
- The clearance rules `role.sw.*` and `role.hv.*` are model rules, which `rulemap` lowers as clearance
  rules scoped by net.
- Connections per net become c0215's Polygon Connect Style rules. One setting per net (decision 1) means
  that nothing is lost.
- `kicad.generate.altium` remains only for generated or role records with `--copper-from`. The board
  source wins, so the records would be silently lost; it stays an error.
- The equivalence test builds each role-copper reference variant for both targets, and compares the
  zones (outline points), keep-outs, vias and rules of the two readings.

### 14. Codes

Eight codes join c0222's closed table `fenolite.roles.codes.ISSUE_CODES`, which grows to twenty-five, each
explained by `fenolite explain`. No `FEN-` code is added.

| code | severities | meaning |
|---|---|---|
| `roles.copper-skipped` | info, warning | a role got no copper: `unconfirmed`, `current-missing` (warning), `user-copper` |
| `roles.copper-blocked` | warning | no spine path between two clusters of a net on its layers |
| `roles.copper-extra` | warning | a branching tree needs the `geo` extra; only the longest chain was generated |
| `roles.copper-kept` | info | a role item edited by the user was kept |
| `roles.copper-worse` | error | the generated copper adds a role finding of warning or above; nothing is written |
| `roles.copper-placement` | warning | the placement bound of a hot loop is over the user's `loop_max` |
| `roles.copper-narrow` | warning | a band could not reach its required width somewhere (c0224's `band-narrow` on a role band) |
| `roles.corridor-blocked` | warning | a corridor would cover another net's pad or a locked item, and was not written |

### 15. Defaults

These are generation parameters, not limits. They live in `roles/copper.py`, each with its source, and
`docs/roles.md`, "Copper defaults", lists them.

| key | default | source | label |
|---|---|---|---|
| width per ampere, vias per current | c0222's `width_per_amp_nm`, `milliamps_per_via` | S-0851 | `INFERRED` |
| `widen_permille` | 2000 (power, high voltage), 1000 (switch node) | S-0851 ("thick"), S-0860 (switch node minimal) | `INFERRED` (`H-G-ROLE-COPPER-SW`) |
| connection per role | solid; ground `thru_hole_only` | S-0861, S-0862 | `INFERRED` |
| ground layers | `B.Cu`; `In1.Cu` on 4 layers | S-0851 (ground plane), Fenolite heuristic for the layer | `INFERRED` |
| `stitch_pitch_nm` | 5 mm | Fenolite heuristic; method S-0863 | `INFERRED` (`H-G-ROLE-COPPER-STITCH`) |
| `min_vias` of stitching | 2 | S-0863 | `INFERRED` |
| corridor width | `2 × width + gap + 2 × clearance` of the class | Fenolite heuristic after S-0852, S-0853 | `INFERRED` |

## Hypotheses registered by this change

| id | statement | settling test | criterion |
|---|---|---|---|
| `H-G-ROLE-COPPER-CLEAN` | Role copper on the good reference variants, with their power copper left out, gives a board that c0222 judges clean | `tests/unit/roles/test_copper_reference.py -k good` | no `roles.*` finding of warning or above on the three `good_roles` variants, and none on the unchanged `good` variants after `copper` (every role net is `user-copper`) |
| `H-G-ROLE-COPPER-REPAIR` | On the bad variants, with their power copper left out, role copper clears the copper findings and leaves the routing findings | `tests/unit/roles/test_copper_reference.py -k bad` | `width-current`, `section-current`, `via-current`, `return-gap` and `near-switching` absent; `kelvin-outer`, `kelvin-shared`, `gate-return-shared` and `gate-loop` equal to the `bad` variant's (code, severity, subject); the bad buck's hot loop at or under 2000 per-mille of its bound, with the bound of at least 150 mm² in the reply |
| `H-G-ROLE-COPPER-SW` | A switch node at the required width and no widening has a smaller area than the hand-drawn pour of the good buck and half-bridge, and keeps the switching distance | `tests/unit/roles/test_copper_reference.py -k switch` | generated switch-node copper area ≤ the good variant's switch-node pour area, and no `roles.near-switching` |
| `H-G-ROLE-COPPER-STITCH` | A 5 mm stitching pitch with at least two vias per piece joins every ground piece on the reference boards, with no dead copper | `tests/unit/roles/test_copper_ground.py` | c0204's `dead` finds no generated ground piece, and every overlap has at least two vias |
| `H-G-ROLE-COPPER-IDEMPOTENT` | A second run on the output of a first plans no change, and a user edit is kept | `tests/unit/roles/test_copper_repeat.py` | zero planned changes and byte-identical boards; an edited zone gives `roles.copper-kept` and stays |
| `H-G-ROLE-COPPER-ALTIUM` | The Altium build of a role-copper script holds the same zones, keep-outs, vias and rules as the KiCad build, and c0215 pours every generated zone | `tests/unit/roles/test_copper_backends.py` | equal items within the readers' rounding, no `altium.zone-unpoured` on a role zone, no `kicad.generate.altium` |

## Evidence level per behaviour

| behaviour | level | proof |
|---|---|---|
| width from current | `INFERRED` (S-0851; S-0269 as c0222 uses it, `H-G-ROLE-CURRENT`) | `tests/unit/roles/test_copper_width.py` |
| spine trees and zones | `INFERRED` (`H-G-ROLE-COPPER-CLEAN`, `-REPAIR`, `-SW`) | the reference boards |
| KiCad builds | `KICAD-VERIFIED` that DRC after refill adds no violation type (c0224's criterion) | `tests/kicad/roles/test_copper_drc.py` |
| Altium builds | `INFERRED` (`H-G-ROLE-COPPER-ALTIUM`, c0215 experimental) | `tests/unit/roles/test_copper_backends.py` |
| repeat runs and kept copper | `INFERRED` (`H-G-ROLE-COPPER-IDEMPOTENT`) | `tests/unit/roles/test_copper_repeat.py` |

## Sizes

In design-days, as in `docs/roadmap.md`:

| package | days |
|---|---|
| width from current; spine trees with the hot loop first | 2.0 |
| band groups united; net barrier after bands; stitch patches (`backends/kicad/generate.py`) | 0.75 |
| ground zones, stitching, via arrays, connections per role | 1.0 |
| switch-node rules and adjacent-layer avoidance; high-voltage rules and barriers | 1.0 |
| corridors | 0.5 |
| DSL call, build hook, manifest and kept copper | 1.0 |
| Altium hand-over | 0.75 |
| `fenolite copper` with the plan protocol and `--gate drc` | 1.0 |
| reference-board scripts, acceptance and KiCad DRC tests | 1.5 |
| docs, guide, evidence, closing | 0.5 |
| **total** | **10** |

c0222's plan gave phase 1 five days. It counted the resolver and the band spine only. The difference comes
from four things that the plan left out:

- the Altium hand-over (generated copper was refused there);
- the command for boards drawn by hand;
- the band union, needed by branching nets and KiCad's `zones_intersect`;
- the corridors and kept-copper manifest, which phase 2 and repeat runs need.

**Cut order**, if time is short:

1. The DSL call with the KiCad build, ground, power and switch node, verification and the reference
   boards (about 6.5 days). This is the deliverable on KiCad.
2. High voltage and corridors (1.5).
3. The Altium hand-over (0.75).
4. `fenolite copper` for boards drawn by hand (1.0), which can move to phase 4's `--propose` if it must.

## Risks / Trade-offs

- **The grid search of spines** is coarse on dense boards. A blocked edge is reported, never forced, and
  phase 2 or the user finishes it.
- **Union needs the `geo` extra.** Without it, branching nets keep only their longest chain, with a
  warning. The test jobs run with all extras, as c0215's do.
- **Convex barriers** may enclose another net's pad (c0224's `kicad.generate.encloses`). `pieces` is
  allowed for role barriers, and the clearance rule still holds where the barrier is lax.
- **Ground on `In1.Cu` by default** may not match a user's stack-up. `ground_layers` overrides it, and the
  reply names the layers used.
- **Fill differences.** The judge reads the simulated pour, and KiCad's fill can differ (c0204's states).
  The KiCad DRC test refills with `kicad-cli`, and `roles.rules` on the saved fill is the final word.
- **A rule of thumb that is lenient at high current** (c0222, decision 7). The reply asks for a rise above
  1 A, as phase 0 does.
- **Routing findings may move.** Regenerated copper can change the subject of a phase-2 finding (for
  example, the item that a Kelvin branch shares). `H-G-ROLE-COPPER-REPAIR` compares code, severity and
  subject, and a mismatch is studied before the criterion is changed.

## Open Questions

1. Which surfaces? **Recommended:** both, the DSL call `design.role_copper()` and the command `fenolite
   copper`, sharing one planner. The command writes KiCad boards only, until c0241 edits `.PcbDoc` files.
2. Phase 1 before phase 2? **Recommended:** yes, with corridors as the interface (decision 8). Each phase
   keeps the other's copper, so either can run again.
3. Should the Altium refusal be lifted for every c0224 call, or only for role copper? **Recommended:** for
   every call, through the same in-memory hand-over. Two paths would differ, and generated items are
   ordinary zones, rule areas and vias. `kicad.generate.altium` stays for `--copper-from`.
4. What about a role net that already has the user's zone? **Recommended:** skip that layer
   (`user-copper`), so a board poured by hand is not doubled. The user removes the zone to get role copper.
5. What happens to a role item the user has edited? **Recommended:** keep it, found by the fingerprint
   manifest, with `--regenerate KEY` to force it back.
6. What about a power net without a current? **Recommended:** skip it with a warning. Fenolite infers no
   current (c0222), and a class-width pour would look sized when it is not.
7. Should the stitching pitch have a default? **Recommended:** yes, 5 mm as a stated Fenolite heuristic,
   measured on the reference boards, with S-0863's method in the docs for the user who knows the
   frequency.
8. Which pad connections by default? **Recommended:** solid for power, switch-node and high-voltage nets;
   thermal on through-hole pads only for ground.
9. Which ground layers by default? **Recommended:** `B.Cu` on 2 layers, `In1.Cu` on 4 layers, and the
   whole board on those layers.
10. Should unconfirmed inferred roles get copper? **Recommended:** no, since copper is a write. They get
    `roles.copper-skipped` with the reason `unconfirmed`, and `fenolite roles --accept` confirms them.
11. Should a branching power net without the `geo` extra be a refusal with exit 6? **Recommended:** no.
    It is a warning with the longest chain generated, because the rest of the board still gains.
