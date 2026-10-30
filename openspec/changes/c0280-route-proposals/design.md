## Context

- **The request.** The maintainer asked on 2026-10-28 for a router that works from electrical intent and
  decided on 2026-10-28 and 2026-10-29 (c0222, `design.md`; c0243 and c0244, task 0.1):
  - roles are inferred and confirmed by the user;
  - critical routes and power copper are made automatically (phases 1 and 2); **everything else is
    proposed, never silently committed**, and what could not be finished is marked with its reason;
  - the phase order is 0 → 1 → 2 → 4 → 3: this change is phase 4, phase 3 (a search router for the
    rest) comes after;
  - output for KiCad and Altium; default limits from public sources are warnings, the user's limits on
    confirmed roles are errors; creepage and clearance distances are declared by the user;
  - boards of 2 to 4 layers and up to about 150 parts.
- **The lesson behind "no single score".** The maintainer tried a commercial automated layout service
  that returns several finished layouts ranked by one number. A number hides the trade-off the engineer
  must make (a shorter route that passes over switching copper, a via in a sense line, a connection
  closed by breaking a keep-away). Phase 4 therefore shows facts per candidate and lets the user lock one.
  No public source is cited for this: it is the maintainer's product decision, not a format fact.
- **What the archived phases give** (`openspec/changes/archive/2026-10-29-c0222-net-roles`, `-c0243-role-copper`,
  `-c0244-critical-routes`; living specs `net-roles`, `routing`, `cli-contract`):
  - **Phase 0.** `RoleSet`, `fenolite.roles.judge` (`roles.rules`), the role profile, the branch walks,
    the three reference boards with `good`, `bad` and `open` variants.
  - **Phase 1.** `fenolite.roles.copper.plan`, `design.role_copper()`, `fenolite copper`: power and
    switch-node bands, ground planes and stitching, via arrays, provisional corridors, loose-end joins
    (`role.join.*`), `roles.copper-blocked` for an edge without a path, the manifest
    `.fenolite/role-copper.json`. The six scripts `good_roles.py` and `bad_roles.py` call it.
  - **Phase 2.** `route --router octilinear --roles critical`: role routes in `RoutingJob.roles`, outcomes in
    `RoutingResult.roles`, tiers, inner-half entries, isolation, keep-away, Z shapes, gate pairs (side by
    side, stacked), `role_check`, locked copper and `role.corridor.<group>.<net>` corridors, `result.roles`
    with reasons and proposals from closed tables.
  - **Routing on `dev`.** c0228's `octilinear` (five shapes, rounds, pairs, copper check from
    `RoutingJob.extra`), c0107's plane fan-out (`backends.kicad.fanout.plan_fanout`), c0225's `--gate drc`
    through c0209's `api.trial(..., gate=True, together=...)`, c0211's `render --region`, c0199's
    crossings, the reviewed-plan protocol ("Staged plans": `--dry-run`, `--confirm --plan ID`, `FEN-4002`).
- **The real opens left after phases 1 and 2.** c0243's task 4.3 ran KiCad DRC on the six role-copper
  scripts (KiCad 10.0.6, refilled): 1 or 2 unconnected items per board against 8 to 13 without role
  copper. They are, in its words, real opens:
  - **buck:** `C3-2` and `J2-2`, ground pads on `F.Cu` with the ground plane on `B.Cu` and no via;
  - **half-bridge:** the Kelvin-source track that does not reach its source copper (`ks_tie`);
  - **bms:** `FET_S`, inferred and not declared, so role copper skipped it; a neighbour's band may also
    block the straight way between its pads (task 0.1 measures it).
  Phase 1 joins loose ends where a band fits; these are the cases it could not, or did not consider.
  **Measured in task 0.1 (2026-10-30, KiCad 10.0.7):** the buck's open is `C3-2` alone (its connection runs
  to `J2-2`, a through-hole pad on the plane), and `bad_roles` adds `C3-1` outside the VOUT pour; the
  half-bridge's opens are the Kelvin-source pads' gate-return copper apart from their source pours (`Q2-2`
  on both variants, `Q1-2` on `good_roles`); the bms `FET_S` has two opens, each source pad 3.5 mm from its
  own Kelvin-source pad, with no band across. Decision 11 holds the table.
- **Package layering.** `routing` may import `core`, `model` and `geometry`; `roles` may import `model`,
  `geometry`, `backends.base` and `analysis`; `cli` imports both, `view` imports neither (it reads replies).
  So: `roles` finds subjects in its own types, `cli` turns them into `routing.protocol` types and judges
  the candidates, `routing` generates candidates. No import edge changes.

## Goals / Non-Goals

**Goals**

- On a board after phases 1 and 2, one read-only command lists every open connection as a proposal with
  candidates and facts, and every connection without a candidate with its reason and alternatives.
- The user locks a candidate through the reviewed-plan protocol; locked copper is locked, survives
  rebuilds and is replayable; rejected candidates are remembered.
- The viewer can show proposals and accept or reject them through c0303's action protocol.
- The six role-copper reference variants become fully connected with phases 1, 2 and 4: KiCad DRC finds
  no unconnected item and no violation type grows.
- KiCad and Altium output; equal inputs give equal bytes.

**Non-Goals.** See the proposal. Above all: no score, no automatic choice, no search router (phase 3).

## Decisions

### 1. Surface: a proposal mode of `route`

- **Alternatives weighed:**
  - a new command `fenolite propose` (a second option set, a second reply and a second plan path);
  - `--roles propose`, which c0244's design anticipated (it ties proposals to roles, while most subjects
    are plain signal connections);
  - mode flags of `route`: `--propose`, `--accept`, `--reject`, `--replay`, `--forget`.

  **Chosen:** the mode flags, as the maintainer's brief names them (`fenolite route --propose`, `--accept
  ID`). `--roles propose` is not added; `--roles critical` stays phase 2 (open question 1).
- **Synopsis.**

  ```
  fenolite route PATH --router octilinear --propose [--kind KIND]... [--nets GLOB]... [--group NAME]...
                 [--candidates N] [--show-rejected] [--gate drc] [--roles-file FILE]
                 [--router-option KEY=VALUE]... [--timeout SECONDS]
  fenolite route PATH --router octilinear --accept ID... [--reject ID... [--reason TEXT]] [--gate drc]
                 [--dry-run | --confirm [--plan ID]]
  fenolite route PATH --router octilinear --reject ID... [--reason TEXT] [--dry-run | --confirm [--plan ID]]
  fenolite route PATH --router octilinear --replay [--dry-run | --confirm [--plan ID]]
  fenolite route PATH --router octilinear --forget ID... [--dry-run | --confirm [--plan ID]]
  ```

- **Exclusive modes.** `--propose`, `--accept`/`--reject`, `--replay`, `--forget` and `--roles` exclude
  each other, except that `--accept` and `--reject` may be combined. Each excludes `--rip`, `--escape`,
  `--order`, `--pairs-as-nets` and `--require-complete`. A misuse is `FEN-2001` (exit 2).
- **Router.** The modes need a router whose features name `propose` (decision 3); today only
  `octilinear`. Another router is `FEN-2001` with a hint naming the routers that have it.
- **`--propose` writes nothing.** It returns no plan and no `plan_id`; exit 0 unless an option or input
  fails. This is the rule "never silently committed": proposals reach the board only through
  `--accept` and a confirmed plan.

### 2. Subjects

`fenolite.roles.proposals.subjects(design, roles, *, outcomes, manifest) -> SubjectPlan` reads the board
(open connections from `analysis.connectivity`, as `route` computes them) and gives one subject per open
connection, each of exactly one kind, tried in this order:

| kind | when | ends | key |
|---|---|---|---|
| `fanout` | a pad of net N on layer L is in an island with no via or through-hole pad, and a zone of N on another copper layer covers a point within `fanout_reach` (default 2 mm, the plane fan-out's nine steps at most) of the pad | the pad, and the zone | `fanout:<net>:<ref>-<pad>` |
| `join` | two islands of one net, at least one holding role copper (a `role.*` item of the manifest, locked role copper of c0244, or a zone of a role net), or an edge that phase 1 reported `roles.copper-blocked` | the nearest pair of attach points: pad copper, free track ends, zone outlines grown inward by half the width plus the zone clearance | `join:<net>:<a>~<b>` |
| `role-net` | an open connection of a role net (`power`, `switch_node`, `ground`, `high_voltage`) that phase 1 sized no copper for: inferred and not confirmed, or without a stated current (task 2.1: the reference tests confirm every inferred role, which leaves the bms `FET_S` a confirmed `power` net without a current) | the connection's MST edge | `role-net:<net>:<a>~<b>` |
| `group` | a critical group (gate loop, Kelvin pair) whose phase-2 status is `unrouted` or `refused` (from c0244's planner and router run in memory) | its open role routes | `group:<group>` |
| `connection` | any other open connection | c0228's MST edge between pad groups | `connection:<net>:<a>~<b>` |

- **One subject per open connection** (corrected in task 0.1: the bms `FET_S` has two open connections, so
  the `role-net` key names the connection as the `join` and `connection` keys do). A `group` subject is one
  per group; its role routes are open by c0222's walk, and may be closed on the board's connectivity (task
  0.1 found such groups on the role-copper variants).
- **Along the power pads** (added in task 4.1): the open connections of a role net are taken along its
  power pads (`roles.measure.power_pads`): the islands that hold a power pad are joined first, then each other
  island by its nearest edge. Measured on the bms: the nearest-anchor tree of `connectivity` joins each source
  pad to its own Kelvin-source pad, and every candidate of both edges then makes the gate returns the path of
  the pack current (`roles.gate-return-shared`, error, on both gate loops); along the power pads the two
  sources are joined and one Kelvin-source pad, and clean candidates exist. The count of open connections is
  the same.
- **Pad entry** (added in task 4.1): a pad end whose island has a track, arc or via touching the pad is moved
  to the nearest point of the pad (50 µm grid) whose disc of the net's width keeps 50 µm from that copper, so
  that new copper meets the pad and not the branch that leaves it. Measured on the half-bridge: from the
  Kelvin-source pad's centre, where the gate return starts, every candidate touched the return and gave
  `roles.gate-return-shared`; from the moved end most candidates are clean, and the facts name the others.
- **Covered by a group:** an open connection whose two islands hold the two pads of a role route of an open
  `group` subject is not a subject of its own (the half-bridge `open` variant's sense branches), so the
  group's role-aware candidates are not doubled by plain ones.
- **Attach-point names** in keys: a pad `REF-N`, a track end `trk@<x>,<y>` in nanometres, a zone by its
  name or `zone@<layer>`. Keys are sorted, so equal boards give equal keys.
- **Hot loops** are never subjects of their own: an open hot-loop connection is a `join` (phase 1's
  copper), with the alternative `power-copper` (`fenolite copper` again) beside its candidates.
- **Selection.** `--kind`, `--nets` (on the subject's net) and `--group` narrow the subjects; a proposal
  rejected as a whole (decision 8) is listed in `result.rejected`, not in `result.proposals`.
- **Proposal id.** `p-` and the first 16 hex digits of the SHA-256 of the canonical JSON of the subject key
  and its ends' positions. It changes when the ends move.

### 3. The protocol: subjects in, candidates out

`routing.protocol` gains frozen dataclasses on `core` and `model` types only, and the feature `propose`:

```python
from dataclasses import dataclass

from fenolite.core.coords import Point
from fenolite.core.units import Nm
from fenolite.model.board import Arc, Track, Via


@dataclass(frozen=True, slots=True)
class JobAttach:
    kind: str  # "pad", "track-end", "zone"
    net: str
    at: Point  # where copper must end: pad centre, entry point, track end, or a point inside the zone
    layers: tuple[str, ...]
    name: str = ""  # REF-N, trk@x,y or the zone name


@dataclass(frozen=True, slots=True)
class JobSubject:
    key: str  # "fanout:GND:C3-2"
    kind: str  # "fanout", "join", "role-net", "group", "connection"
    net: str
    a: JobAttach
    b: JobAttach
    width: Nm
    layers: tuple[str, ...]  # allowed layers, preference order
    via_diameter: Nm = 0
    via_drill: Nm = 0
    group: str = ""  # for "group": the c0244 group whose role routes are in RoutingJob.roles


@dataclass(frozen=True, slots=True)
class Candidate:
    id: str  # "c-" + 16 hex digits of the content hash
    subject: str  # JobSubject.key
    source: str  # "shape", "z-shape", "via-l", "fanout", "role" (a future family may add "external:<router>")
    relaxed: tuple[str, ...] = ()  # e.g. ("keep-away=clearance",)
    tracks: tuple[Track, ...] = ()
    arcs: tuple[Arc, ...] = ()
    vias: tuple[Via, ...] = ()
    length: Nm = 0
    layers: tuple[str, ...] = ()
```

- `RoutingJob` gains `subjects: tuple[JobSubject, ...] = ()` after `roles`, with `options["candidates"]`;
  `RoutingResult` gains `candidates: tuple[Candidate, ...] = ()` after `roles`, and after it `refusals:
  tuple[tuple[str, str, tuple[str, ...]], ...] = ()`, the subject key, reason (decision 6) and blockers of
  each subject left without a candidate (added in task 1.1: the command needs the reason, and a message
  is no contract). Jobs and results built as before are equal to ones with `()`.
- **Propose mode.** With a non-empty `job.subjects`, a router whose features name `propose` returns
  candidates only: `tracks`, `arcs` and `vias` of the result stay empty and nothing is merged.
- `ROUTER_FEATURES` becomes `{"pairs", "escape", "short", "roles", "propose"}`; `OctilinearRouter.features`
  is `{"pairs", "short", "roles", "propose"}` (MODIFIED "Pairs and escape in a routing job").
- **Id.** `Candidate.id` is `c-` and the first 16 hex digits of the SHA-256 of the canonical JSON of the
  subject key, the source, the relaxations and the items' geometry (layer, width, points, via sizes),
  never of the rest of the board: a candidate keeps its id while unrelated copper changes.

### 4. Candidate families

`routing/propose.py` generates, per subject, candidates from these families in this order, and keeps the
first `N` (default 4, at most 8) that pass c0228's acceptance (clearance in force plus 2 µm, edge, holes,
no acute joint) and differ from the ones kept (another layer set, another via count, or a centre line
apart by more than the clearance in force anywhere):

1. **`shape`**: c0228's five shapes on each allowed layer.
2. **`z-shape`**: c0244's Z shapes (decision 12 of c0244), whose middle lines come from the blocking
   obstacles' bounding boxes, for every subject (in role mode they also come from partners and aggressors).
3. **`via-l`**: an L shape whose bend is a via of the net's class, the first leg on `a`'s layer and the
   second on `b`'s or on the other allowed layer, the via accepted on every layer of its span.
4. **`fanout`** (for `fanout` subjects only): a neck and a via, searched as c0107's plane fan-out searches
   (eight directions in the order of their angle to the outward direction, steps of a quarter via
   diameter, nine distances), keeping the first passing position of each direction; the via must lie
   inside the zone outline by half its diameter and in its simulated fill (c0204). The search lives in
   `routing/propose.py` because `routing` may not import `backends`; it follows the documented method, and
   a test compares it with `plan_fanout` on c0107's bench.
5. **`role`** (for `group` subjects only): c0244's role mode on the group's routes, first with its
   defaults (a shape that phase 2 refused because of its rounds or another group can pass now), then with
   one relaxation at a time from a closed list: `kelvin-vias=2`, `gate-vias=2`, `keep-away=clearance` (the
   keep-away lowered to the clearance in force: the aggressors drop out of the route, and the clearance test,
   which keeps the clearance in force from every other net's copper, keeps it from them; task 2.4 found that
   lowering the in-plane distance alone leaves c0244's test of no overlap on the next layer, so a pair over a
   switch-node pour stays refused). Isolation is never relaxed: a sense branch on its own pour is the fault
   the phase exists to avoid.
6. **`external:<router>`** (`--propose-with ROUTER`): moved to a future change by the maintainer's decision
   of 2026-10-30. The protocol takes it without change (a candidate's `source` is free text); the reason
   `external-trial-failed` of `not_evaluated` stays reserved for it, and this change never gives it.

- **Width.** The net's class width, else the default class; for a `role-net` subject the class width with
  the fact `current: not-declared` (phase 1 sizes copper from a confirmed current only).
- **Shared rule.** `max-length` (c0228's default 20 mm) and `rounds` apply; a subject whose every shape
  fails gets one reason (decision 6).
- **Ordering.** Candidates appear in family order, then shape order, then layer order. The reply says
  `"order": "generation"`: it is not a ranking.

### 5. Facts per candidate

`cli/_propose.py` judges every candidate alone against the current board, the candidate's items added in
memory with `locked=True`. Facts are measured, never weighted:

| fact | what | how |
|---|---|---|
| `closes` | the subject's connections it closes | `analysis.connectivity` after the add |
| `open` | `{before, after}` open connections of the board | the same |
| `copper_check` | `{before, after, new}` findings of the project's copper check on items within the candidate's bounding box grown by the largest clearance | `extra["copper_check"]`, c0228 |
| `roles` | `{before, after, new, cleared}` role findings of the groups and nets the candidate touches, with severities and measures | `role_check` of c0244 on the simulated pour |
| `drc` | `{new: [{type, items}]}` and its evidence | only with `--gate drc` (decision 12) |
| `vias`, `length`, `layers`, `bends` | counts and lengths in nm | the items |
| `loop` | `{group, area, ratio_permille, bound}` | only for a `group` subject, or a subject on a net of a role loop, as the judge measures it |
| `relaxed` | the relaxations of a `role` candidate | the family |
| `conflicts` | ids of candidates of other subjects whose copper clashes with this one | pairwise copper check of the kept candidates |
| `fill` | `saved`, `simulated` or `stale` | the board's fill state used for `roles` and `fanout` |
| `not_evaluated` | `[{fact, why}]` | every fact above that was not measured, with a reason from a closed list: `no-gate` (no `--gate drc`), `no-role-loop`, `outside-role-reach`, `no-kicad-cli`, `budget`, `external-trial-failed` |

- **Role reach.** `role_check` runs for a candidate whose items lie on a role net, or within
  `switching_distance_nm` of switch-node copper, or inside a group's pad box grown by 2 mm; otherwise
  `roles` is absent and `not_evaluated` holds `outside-role-reach`.
- **No score.** The candidate object has no `score`, `rank`, `best`, `recommended` or `cost` key, and the
  proposal no ordering claim. A test asserts the closed key set (`H-G-PROP-FACTS`). c0244's internal cost
  (loop area, length) still chooses *within* a role-mode run; it is a generation detail, and the facts
  show the loop area itself.

### 6. Proposals without a candidate

A subject whose families give no candidate is in `result.proposals` with `candidates: []`, one `reason`
and `alternatives`, and gives one `route.proposal-open` (warning):

| reason | when | alternatives |
|---|---|---|
| `no-room` | every shape refused by clearance | `free-corridor` (the three nearest blockers, e.g. a neighbour's band), `move-part`, `external-router` |
| `no-layer` | the ends share no allowed layer and no via fits | `allow-via`, `move-part` |
| `too-long` | every shape over `max-length` | `raise-limit`, `move-part` |
| `near-switching`, `isolation` | every shape of a `group` broke keep-away or isolation, relaxations included | `free-corridor`, `move-part`, `power-copper` |
| `pads` | an end pad is missing | `move-part`, `edit-script` |
| `all-rejected` | every candidate was rejected (decision 8) | `--show-rejected`, `move-part` |
| `budget` | `--timeout` ended before the subject | run again |

Each alternative carries `kind`, `text`, `command` and a `render --region` command for the subject's box
grown by 2 mm (c0211). `role-net` subjects always carry the alternative `confirm` (`fenolite roles PATH
--accept NET --dry-run`, then `fenolite copper`), beside their candidates: phase 1 then makes copper sized
from the confirmed current.

### 7. The reply of `--propose`

Schema of `result` (in `fenolite.envelope.v0`, command `route`):

```json
{
  "mode": "propose",
  "order": "generation",
  "open": {"before": 3},
  "proposals": [
    {
      "id": "p-3f0c9a1d2e4b5c6a",
      "subject": "fanout:GND:C3-2",
      "kind": "fanout",
      "net": "GND",
      "ends": [{"kind": "pad", "name": "C3-2", "at": [52100000, 9600000], "layers": ["F.Cu"]},
               {"kind": "zone", "name": "role.ground.GND.B.Cu", "layers": ["B.Cu"]}],
      "region": "fenolite render BOARD --region 49.1,6.6,55.1,12.6 --nets --open",
      "candidates": [
        {
          "id": "c-9b1e0d77a4c2f310",
          "source": "fanout",
          "relaxed": [],
          "items": {"tracks": 1, "vias": 1},
          "geometry": [{"kind": "track", "layer": "F.Cu", "width": 250000,
                        "points": [[52100000, 9600000], [52100000, 10650000]]},
                       {"kind": "via", "at": [52100000, 10650000], "diameter": 600000, "drill": 300000}],
          "facts": {
            "closes": ["GND:C3-2"],
            "open": {"before": 3, "after": 2},
            "copper_check": {"before": 0, "after": 0, "new": []},
            "vias": 1, "length": 1050000, "layers": ["F.Cu", "B.Cu"], "bends": 0,
            "conflicts": [],
            "fill": "simulated",
            "not_evaluated": [{"fact": "drc", "why": "no-gate"},
                              {"fact": "roles", "why": "outside-role-reach"},
                              {"fact": "loop", "why": "no-role-loop"}]
          },
          "rejected": false
        }
      ],
      "reason": null,
      "alternatives": []
    }
  ],
  "rejected": [],
  "locked": [{"candidate": "c-…", "subject": "join:SW:…", "present": true}],
  "next": ["fenolite route BOARD --router octilinear --accept c-9b1e0d77a4c2f310 --dry-run"]
}
```

The numbers above illustrate the shape, not a measurement. Proposals are sorted by kind (the table order
of decision 2), then key. `locked` lists the decisions of the record and whether their copper is on the
board. The envelope evidence is `UNVERIFIED` (as every route), lowered by no fact; each `drc` fact carries
its own `KICAD-VERIFIED(kicad-cli <version>)` when it ran.

### 8. Accept and reject through a reviewed plan

- **`--accept ID`** (candidate ids, repeatable). The command recomputes the proposals of the subjects of
  those ids (deterministic, so the ids come back), and plans:
  - the board with each candidate's items added, `locked=True`, ids in the namespace `proposal`
    (`derived_id("trk", "proposal", content_hash(candidate id, geometry))`, likewise `via`), KiCad uuids
    without the build's item marker, so rebuilds keep them (c0244, decision 10);
  - for a `group` candidate, c0244's corridors `role.corridor.<group>.<net>` along its branches;
  - the decision record (decision 9) with the entries added.

  Both are one plan of "Staged plans": `--confirm --plan ID` writes the reviewed bytes, a changed board or
  record gives `FEN-4002`. The reply repeats each accepted candidate's facts.
- **Checks before planning:**
  - an id that is not among the recomputed candidates gives `route.proposal-unknown` (error, exit 5, no
    write: "Error findings plan no write"), naming the id and the hint to run `--propose` again;
  - two accepted candidates of one subject, or whose copper clashes, give `route.proposal-conflict`
    (error);
  - an accepted candidate with a `new` copper-check or role finding is accepted (the user saw the facts)
    and gives `route.proposal-findings` (warning) naming them; with `--gate drc`, a candidate whose items
    bring a new KiCad finding is dropped whole (`together` = its items) and not recorded.
- **`--reject ID`** (candidate or proposal ids) with an optional `--reason TEXT` (1 to 300 printable
  characters) plans only the decision record. A rejected candidate keeps its id; `--propose` marks it
  `rejected: true` and leaves it out unless `--show-rejected`; a rejected proposal is listed in
  `result.rejected` with its reason. `route.proposal-rejected` (info) counts what was left out.
- **Why a plan for a reject.** The record is a file of the user's tree; every write of Fenolite goes
  through plan and confirm.

### 9. The decision record

`fenolite.route-decisions.v0`, canonical JSON (sorted keys, integers, no clock), stored like the roles
document: `.fenolite/route-decisions.json` for a built project, `<board stem>.route-decisions.json` beside
any other board. `routing/decisions.py` reads and writes it; a malformed record is `FEN-3004`.

```json
{
  "schema": "fenolite.route-decisions.v0",
  "board": "buck_shunt.kicad_pcb",
  "locked": [
    {
      "candidate": "c-9b1e0d77a4c2f310",
      "proposal": "p-3f0c9a1d2e4b5c6a",
      "subject": "fanout:GND:C3-2",
      "net": "GND",
      "ends": [{"kind": "pad", "name": "C3-2", "at": [52100000, 9600000]},
               {"kind": "zone", "name": "role.ground.GND.B.Cu"}],
      "items": [{"kind": "track", "layer": "F.Cu", "width": 250000,
                 "points": [[52100000, 9600000], [52100000, 10650000]]},
                {"kind": "via", "at": [52100000, 10650000], "diameter": 600000, "drill": 300000,
                 "layers": ["F.Cu", "B.Cu"]}],
      "corridors": [],
      "relaxed": [],
      "plan": "5e1d0c3b2a491807"
    }
  ],
  "rejected": [
    {"id": "c-0a6f2d3e9c1b4d58", "subject": "connection:SDA:U1-5~R7-1", "reason": "crosses the gate loop"}
  ]
}
```

- `plan` is the id of the decision: the first 16 hex digits of the SHA-256 of the canonical JSON of the
  board's SHA-256 before the write and the accepted candidate ids. The id of the reviewed plan cannot be
  written into the bytes it digests (corrected in task 1.3). No timestamp, so the record is byte-stable.
- Entries are sorted by subject, then id.

### 10. Replay and forget

- **`--replay`** plans, for each locked entry whose items are not on the board (a board rebuilt into a new
  folder, copper deleted in KiCad, a new board from the same script), the entry's items again, when every
  end still lands in copper of its net at the recorded position and the items pass the copper check. An
  entry that cannot be replayed gives `route.proposal-stale` (warning) with the reason (`moved`, `blocked`,
  `net-gone`) and the alternative to run `--propose` again; it stays in the record. A run on a board that
  holds every entry plans no write.
- **Rebuilds.** A script-built project keeps the accepted copper as it keeps routed copper ("Routes
  survive a rebuild"); replay is for the cases a rebuild does not cover. Locked copper is also kept by
  `--rip`, `tidy`, phase 1 and phase 2.
- **`--forget ID`** removes a locked or rejected entry from the record; for a locked entry it also plans
  removing its items (and corridors) from the board, through the same review. Unlocking without removing
  is done in KiCad: the next `--propose` lists the copper as plain board copper.

### 11. The three leftover opens of phase 1

Measured in task 0.1 (KiCad 10.0.7 after a refill, and Fenolite's connectivity on the pour, which agree):

| variant | open | subject | candidates expected |
|---|---|---|---|
| buck, both | `C3-2` on `F.Cu`, ground plane on `B.Cu`, no via; its connection runs to `J2-2`, a through-hole pad on the plane | `fanout:GND:C3-2` | neck and via positions, each with `open.after` one lower and no new finding |
| buck `bad_roles` | `C3-1` outside the VOUT pour | one VOUT `join` | shapes from the pad into the pour |
| half-bridge, both | the low side's Kelvin-source pad `Q2-2` and its gate return apart from the SRC pour that holds `Q2-3` | one SRC `join` | shapes from the pad into the pour; the facts show the role findings of `gate_Q2` before and after |
| half-bridge `good_roles` | the high side's `Q1-2` and its gate return apart from the SW pour (`bad`'s `ks_tie` closes it) | one SW `join` | as above, for `gate_Q1` |
| bms, both | `FET_S`: `Q1-3` 3.5 mm from `Q1-2`'s copper, `Q2-3` from `Q2-2`'s; no band across | two `role-net` | shapes at the class width, with `current: not-declared`, plus the alternative `confirm` |

The `C3-2` and `J2-2` of c0243's report are the two ends of one connection, and the `ks_tie` it named is
the high side's tie of `bad`, which reaches its pour.

### 12. KiCad DRC per candidate, in batches

KiCad DRC per candidate would cost one `kicad-cli` run per candidate. With `--gate drc`, the command packs
the kept candidates, in reply order, into batches where no two share a subject and no two conflict, runs
c0209's `api.trial(..., gate=True)` once per batch with each candidate's items as one `together` set, and
attributes each new violation to the candidate whose items it names. The number of runs is about the
largest number of candidates per subject plus the conflicts (4 to 8 on the reference boards). A violation
that names items of two candidates of one batch cannot happen (they do not conflict); one that names no
candidate item is reported once in `result.drc_unattributed`. Without `kicad-cli`, `--gate drc` exits 6.

### 13. Viewer contract (c0303, c0305)

- **Data.** `fenolite view BOARD --proposals run` runs `route BOARD --router octilinear --propose` in process
  (read-only); `--proposals FILE` reads a saved reply. `fenolite.view.proposals.overlay(reply, scene)`
  returns `scene.proposals` (`fenolite.view_proposals.v0`): per proposal its id, kind, net, subject, box,
  reason and alternatives; per candidate its id, source, polylines and via points per layer in scene units,
  and its facts unchanged; the record's locked entries as `locked` outlines. A value the reply lacks is
  left out.
- **Actions.** With `--allow-actions` the served page gets two actions in c0303's allow-list:
  - `route-accept`: option `candidates`, ids shown by the session's proposal data; words
    `route PATH --router octilinear --accept ID...`;
  - `route-reject`: options `candidates` (candidate or proposal ids of the session) and `reason` (c0303's
    reason rule); words `route PATH --router octilinear --reject ID... --reason TEXT`.

  Both go through c0303's plan, review, confirm and undo (`restore` of the receipt). The run allow-list
  gains `proposals` (no option). Unknown ids are refused with 400.
- **Page.** Candidates drawn dashed in their layer colour, locked ones solid with a lock glyph, a
  comparison table of the facts per proposal with no sort by default, accept and reject buttons. This
  drawing is the viewer line's work: this change fixes the data and the actions, and the page follows in
  c0305's successor (open question 6).

### 14. Altium

As c0244: `route` writes KiCad boards. The Altium deliverable is `fenolite convert <board> --to altium`; the
accepted tracks and vias keep their locked flag (c0108, `H-A-PCB-CU-LOCK`), group corridors become pour
keep-out regions. The read-back compares the accepted items (`H-A-PROP-READBACK`). Proposals on a
`.PcbDoc` wait for c0241's edit sessions; `route` resolves KiCad boards only. A build for the Altium target
does not read the KiCad board's routed copper, so for a script-built project the Altium deliverable is the
convert, as `docs/roles.md` says for phase 2.

### 15. Reference boards: the acceptance gate

`tests/unit/roles/test_proposal_reference.py`, and `tests/kicad/roles/test_proposal_drc.py` for DRC:

1. **Full chain on the six role-copper variants** (`good_roles.py`, `bad_roles.py`; phase 1 runs in their
   build): confirm the groups and roles as the reference tests do, run `route --roles critical --confirm`
   (phase 2; `good` groups `complete`, `bad` groups `kept` as script copper), then `route --propose`.
2. **The leftovers** of decision 11 appear as their subjects with at least one candidate each.
3. **The test's selection, not Fenolite's.** For each proposal that holds an open connection of the board
   (every kind but `group`) the test locks the first candidate in reply order whose facts show
   `open.after < open.before`, no `new` copper-check finding, and no `new` role finding of warning or above;
   it fails if such a proposal has none. A `group` proposal (task 0.1: groups that phase 2 left `unrouted`
   with their connections closed on the board) is recorded under task 4.2 and rejected whole by the test
   (`--reject p-…`), so the designed findings of `bad_roles` stay. This rule lives in the test: the product
   offers no automatic choice.
4. `--accept` all chosen ids in one plan, `--confirm --plan ID`, fill, `roles --check`.
5. **Criteria:** no open connection; the `good_roles` variants give no role warning; the `bad_roles`
   variants give exactly their designed routing findings (c0243's `H-G-ROLE-COPPER-REPAIR` list); the facts
   at proposal time equal the measures after the write (`H-G-PROP-FACTS`).
6. **Again:** `--propose` on the result gives `route.proposal-none` and lists every decision as present; a
   rejected candidate is not listed again; `--replay` on a fresh build of the same script restores the
   accepted copper and the second replay writes nothing (`H-G-PROP-REPLAY`).
7. **KiCad DRC** on 9 and 10 after refill (on 9 with the unit tests' fill, as c0244): zero unconnected
   items, no violation type grows against the variant after phase 2 (`H-K-PROP-DRC`). Corrected in task 4.3:
   the proposals are made on the board as built (zones unfilled, the simulated pour) on both majors, and the
   outline fill goes only on the copy that `kicad-cli` 9 judges; since that fill stands for KiCad's, the zero
   of unconnected items is claimed on 10 and the no-growth on both (the first CI run, which proposed on the
   outline fill, found other subjects there). The second found that the job `kicad-9` synced without the
   `geo` extra, so phase 1's planner ran without its `clipper` backend and left other opens (the buck's `SW`,
   the half-bridge's `GND`); the job now syncs `geo`, as `unit` and `kicad-10` do, and the test skips without
   that backend.
8. **Altium:** convert each accepted variant and compare the read-back (`H-A-PROP-READBACK`).
9. **`good` and `open` variants:** `--propose` on each `good` variant gives `route.proposal-none`. On the
   `open` variants after phase 2, the proposals are recorded under task 4.2; the half-bridge's sense pair
   blocked by `SW_UNDER` is a `group` subject whose candidates (if any) show their relaxation and their
   `roles.near-switching` fact, or `near-switching` as its reason. Nothing is claimed beyond the record.

### 16. Codes

`routing.codes.ISSUE_CODES` gains these codes, each with an entry in `explain.toml` and a row in
`docs/cli-contract.md`, "route". No `FEN-` code is added: misuse is `FEN-2001`, a malformed record
`FEN-3004`, the write `FEN-4001`/`FEN-4002`, an error finding `FEN-5001`, `kicad-cli` missing `FEN-6001`.

| code | severity | meaning |
|---|---|---|
| `route.proposal-none` | info | no open connection to propose for |
| `route.proposal-open` | warning | a proposal without a candidate: reason and alternatives |
| `route.proposal-unknown` | error | an id given to `--accept`, `--reject` or `--forget` that is not current |
| `route.proposal-conflict` | error | accepted candidates share a subject or clash |
| `route.proposal-findings` | warning | an accepted candidate brings findings, named |
| `route.proposal-rejected` | info | candidates or proposals left out as rejected, counted |
| `route.proposal-stale` | warning | a locked decision that cannot be replayed, with its reason |
| `route.proposal-limit` | info | subjects not evaluated or candidates cut by `--candidates` or `--timeout` |

### 17. Relation to other changes

- **c0243, c0244 (archived):** phase 4 reads phase 1's manifest and `roles.copper-blocked`, reruns phase 2's
  planner in memory for group statuses, and reuses its role mode, Z shapes, corridors and `role_check`.
  MODIFIED "Critical route failures": the closed proposal set gains `propose`, the command
  `route PATH --router octilinear --propose --group NAME`.
- **c0303, c0305 (open):** the actions and the run join their allow-lists; this change's viewer tasks wait
  for them to land.
- **c0249 (design lock) and c0250 (manual-edit merge):** a lock of refs and picks, not of copper; locked
  copper going back into the script is c0250's subject (open question 5).
- **Phase 3 (next free id):** a search router becomes one more candidate family; the protocol of decision
  3 takes it without change.
- **The circuits-as-code batch (c0246 to c0258):** independent.

## Hypotheses registered by this change

| id | statement | settling test | criterion |
|---|---|---|---|
| `H-G-PROP-LEFTOVERS` | The real opens that phase 1 leaves on the role-copper variants each get a subject with at least one candidate that closes it without a new finding | `tests/unit/roles/test_proposal_reference.py -k leftovers` | the buck `fanout:GND:C3-2`, the half-bridge `join` subjects and the bms `role-net` subjects (task 0.1) each have a candidate with `open.after < open.before` and no `new` copper-check or role finding of warning or above |
| `H-G-PROP-FACTS` | The facts of a candidate equal what the checks measure once it is locked, and the reply holds no score | `tests/unit/roles/test_proposal_reference.py -k facts`, `tests/unit/cli/test_route_propose.py -k keys` | for every accepted candidate, `open.after`, the copper-check and role findings equal the measures after the write and refill; the candidate keys are the closed set |
| `H-G-PROP-COMPLETE` | Phases 1, 2 and 4 leave the six role-copper variants fully connected with only their designed role findings | `tests/unit/roles/test_proposal_reference.py -k complete` | zero open connections; no role warning on `good_roles`; exactly the designed routing findings on `bad_roles` |
| `H-G-PROP-REPLAY` | Decisions are a fixed point: a second proposal run lists them present and proposes nothing; rejected candidates stay out; replay on a fresh build restores the same bytes | `tests/unit/roles/test_proposal_reference.py -k again` | `route.proposal-none`; no rejected id listed; second replay writes nothing; the replayed board equals the accepted one byte for byte |
| `H-K-PROP-DRC` | KiCad's DRC finds no unconnected item and no new violation type on the accepted role-copper variants | `tests/kicad/roles/test_proposal_drc.py` in `kicad-9` and `kicad-10` | zero `unconnected_items`; no violation type with more entries than after phase 2 |
| `H-A-PROP-READBACK` | The Altium convert of an accepted variant keeps the accepted copper and its locks | `tests/unit/roles/test_proposal_reference.py -k altium` | every accepted track and via read back at its place (to 1 µm) and width with `locked` true; group corridors as pour keep-out regions |

## Evidence level per behaviour

| behaviour | level | proof |
|---|---|---|
| subjects, protocol, codes, record | `INFERRED` until a release; plain data | `tests/unit/roles/test_proposals.py`, `tests/unit/routing/test_protocol.py -k propose`, `tests/unit/routing/test_decisions.py` |
| candidates and facts | `INFERRED` (`H-G-PROP-LEFTOVERS`, `-FACTS`) | the reference variants and authored benches |
| written copper | `UNVERIFIED` until checked; `KICAD-VERIFIED` per major with `--gate drc` (`H-K-PROP-DRC`) | the kicad jobs |
| completeness and replay | `INFERRED` (`H-G-PROP-COMPLETE`, `-REPLAY`) | the reference variants |
| Altium output | `INFERRED` (`H-A-PROP-READBACK`) | the read-back comparison |

## Size and cut order

| part | days |
|---|---|
| entry check, protocol, feature `propose`, codes | 0.5 |
| subjects (`roles/proposals.py`): kinds, attach points, keys | 1.0 |
| candidate families: shape, z-shape, via-l, fanout | 1.25 |
| `role` family with relaxations | 0.5 |
| facts, role reach, conflicts, `not_evaluated` | 1.0 |
| reply, accept, reject, decision record, replay, forget | 1.25 |
| DRC batches | 0.5 |
| viewer data and actions | 0.5 |
| reference gate, KiCad DRC, Altium read-back | 1.0 |
| docs, guide, evidence, closing | 0.5 |
| **total** | **8.0** |

c0222 planned 7 days for phase 4; the decision record, replay and the viewer contract came in.

**Cut order**, cheapest loss first: (1) `external:<router>` candidates (moved to a future change by the
maintainer's decision of 2026-10-30); (2) DRC batches (`drc` stays in
`not_evaluated` without them, and the accept-time `--gate drc` still runs); (3) `--forget` (edit the record by
hand); (4) the viewer actions (the data join stays). Never cut: the no-score reply, the reasons and
alternatives, accept through a reviewed plan, the decision record, the reference gate.

## Risks / Trade-offs

- **Many subjects on a dense board.** About 150 parts give a few hundred connections; with 4 candidates
  each, a copper check and a role check per candidate. Mitigation: the copper check is local to the
  candidate's box, the role check runs only within role reach, and `--timeout` cuts with
  `route.proposal-limit`. Measured on the reference boards and recorded under task 3.1.
- **Facts against each candidate alone.** Two accepted candidates can interact; `conflicts` lists clashes,
  and the accept recomputes; role measures of several candidates together are judged after the write.
- **Generation order looks like a ranking.** The reply says `"order": "generation"`, the docs say it, and
  the viewer shows no default sort.
- **Fewer shapes than a search.** Subjects left without candidates get `no-room` and the alternative
  `external-router`; phase 3 adds the search.
- **Relaxed group candidates** may break a keep-away. They are labelled, their `roles` facts show it, and
  only the user can lock one.
- **Stale ids.** Ids depend on the candidate's geometry, so a board change near a subject gives new ids;
  `route.proposal-unknown` tells the user to propose again.

## Open Questions

1. **`--propose` or `--roles propose`?** c0244's design anticipated `--roles propose`; the brief names
   `--propose`. **Decided (maintainer, 2026-10-30), as recommended:** `--propose` and the other mode flags, `--roles` stays `critical` only.
2. **Should the reply mark dominated candidates** (worse or equal on every numeric fact than another)?
   **Decided (maintainer, 2026-10-30), as recommended:** not in this change; it is a partial order, not a score, and can be added to the facts
   later if users ask.
3. **Default `--candidates`?** **Decided (maintainer, 2026-10-30), as recommended:** 4, at most 8.
4. **Candidates for an unconfirmed role net** (bms `FET_S`): copper at the class width, or only `confirm`?
   **Decided (maintainer, 2026-10-30), as recommended:** both: class-width candidates labelled `current: not-declared`, and the `confirm`
   alternative that lets phase 1 size the copper.
5. **Locked copper back into the script?** **Decided (maintainer, 2026-10-30), as recommended:** not here; c0250's manual-edit merge carries
   board edits to the script, and locked proposals are such edits.
6. **Who draws the proposals in the viewer?** **Decided (maintainer, 2026-10-30), as recommended:** this change fixes the data and the actions;
   the drawing goes to the next viewer change after c0305, so the viewer line keeps one owner.
7. **External router candidates in this change?** **Decided (maintainer, 2026-10-30):** no; the optional
   family `--propose-with` moved to a future change by the maintainer's decision of 2026-10-30 (it was first in
   the cut order). A subject without candidate names an external router as its `external-router` alternative.
