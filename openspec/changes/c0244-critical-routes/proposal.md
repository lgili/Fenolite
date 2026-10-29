## Why

Phase 2 of the router that works from electrical intent (c0222, `design.md`, "Plan of phases 1 to 4"). Phase 0
gave every net a role and checks a board against its roles: a Kelvin sense taken from the outer half of a
shunt pad or from a pour, a gate return taken from the source pour, a gate loop far over its placement bound,
a sense pair over switching copper. Those findings now have a number and a place, but nothing in Fenolite
draws the copper that would clear them. The routers the maintainer tried draw these connections like any
other net, so the findings come back after every run.

The maintainer's decisions of 2026-10-28 and 2026-10-29 fix the deliverable: the critical connections and
the power copper are made automatically, the rest is proposed, and whatever could not be finished is marked
with its reason. The output serves KiCad and Altium. The phases come in the order 0, 1, 2, 4, 3; the boards
have 2 to 4 layers and up to about 150 parts. On 2026-10-29 the maintainer gave the hot loop to phase 1
(c0243, power copper as pours), set the run order (critical routes first, then phase 1's pours around
them) and one corridor name for both phases.

This change makes the critical connections. Before any general router runs, it routes, deterministically,
the connections that the role groups of c0222 define:

- **Gate loops:** the drive and its return routed together, the return starting at the source or
  Kelvin-source pad, side by side, or stacked on the adjacent layer when there is no room beside, with the
  smallest loop.
- **Kelvin pairs:** a coupled pair from the inner half of each shunt sense pad to the amplifier inputs.
  The pair touches no power copper, and it keeps away from switching copper.

The result is judged by c0222's `roles.rules` and by KiCad's DRC. The routed copper is locked so that the
later phases keep it, and it is fenced against pours.

## What Changes

- **Role routes, not a new router.** c0228's built-in `octilinear` router gains a role mode. The command
  derives a `JobRoleRoute` for each open connection of a confirmed or declared gate loop or Kelvin pair and
  puts it in a new `RoutingJob.roles` field. Each route carries its ends, layers, width, pairing, allowed
  vias, isolation and aggressor nets. The router declares a new feature `roles` and reports one
  `RoleOutcome` per route in a new `RoutingResult.roles` field. Role mode routes only those connections:
  gate loops first, then Kelvin pairs, as c0109 tiers, with c0228's rounds inside each tier.
- **Constraints per role**, each from a public source or the c0222 profile:
  - **Ends.** A Kelvin branch enters its sense pad on the inner half (S-0850). A gate return starts at the
    source or Kelvin-source pad (S-0853).
  - **Isolation.** A branch of a power, switch-node or ground net may touch its own net's copper only at
    its end pads (S-0892).
  - **Keep-away.** A sense or gate branch keeps the profile's `switching_distance_nm` from switching copper
    on its layer and does not overlap that copper on an adjacent layer. This is the same condition that
    `roles.near-switching` judges.
  - **Choice of shape.** Among the shapes that pass, the router picks the one with the smallest area of the
    gate loop (S-0891), and the shortest Kelvin pair.
  - **Vias.** A Kelvin branch gets none by default. A gate return may get one at each end, to run stacked
    on the adjacent layer when no shape beside its drive passes (S-0891).
  - **Z shapes.** The pattern-routing Z shapes of S-0837 join the five shapes of c0228, so that a route
    can pass around switching copper and beside its partner.
- **Judged twice.** A new `role_check` job extra reruns the c0222 judge before and after the job, and a
  group whose findings get worse is removed (`route.role-refused`). `--gate drc` drops a whole group at
  once through c0209's `together`.
- **Locked and fenced.**
  - Every item the role mode writes is `locked`.
  - Every routed branch gets a corridor: a rule area named `role.corridor.<group>.<net>` that forbids
    copper pours along the branch on its layer, and on every layer around its vias (S-0892). The name is
    the one c0243 uses; phase 2 replaces a provisional corridor of that name that phase 1 wrote first.
  - Pours of any net, phase 1's included, fill around that copper, and nothing later moves it.
- **Surface.** `fenolite route PATH --router octilinear --roles critical [--group NAME]... [--rip]
  [--gate drc]` works through the reviewed-plan protocol (`--dry-run`, then `--confirm --plan ID`). It
  answers with `result.roles`: one entry per gate loop and Kelvin pair, with its status, its connections,
  the role findings before and after, and the copper and corridor ids.
- **Never silently skipped.** A group that cannot be routed gets `route.role-unrouted` with one reason from
  a closed set (`no-room`, `too-long`, `no-layer`, `near-switching`, `isolation`, `role-check`, `drc`,
  `pads`). It also gets one proposal from a closed set (`confirm`, `allow-via`, `free-corridor`,
  `move-part`, `rip`, `raise-limit`, `power-copper`), with the command to run and a `render --region`
  command for the place. Unconfirmed inferred groups are listed and not routed (`route.role-unconfirmed`).
  A gate loop whose placement bound alone exceeds the user's `gate_max` gets `route.role-placement`. A hot
  loop named by `--group` is reported `skipped` with reason `phase-1` and the proposal `power-copper`.
- **Idempotent.**
  - The ids are derived from the content, so equal inputs give equal bytes.
  - A second run finds every group complete and writes nothing.
  - A rebuild keeps the copper and the corridors, as it keeps routed copper and rule areas that the board
    holds.
- **KiCad and Altium.** The KiCad board is written as every routing command writes it. The Altium project
  is `fenolite convert <routed project> --to altium`. The convert carries the tracks, vias and rule areas
  with the locked flag of c0108 (`H-A-PCB-CU-LOCK`). The roles of a `.PcbDoc` are judged as before. Routing
  a `.PcbDoc` in place waits for c0241's edit sessions.
- **Phase 1 interface (c0243).** The run order is critical routes first, then power copper; the other
  order keeps working. Phase 2 hands phase 1:
  - locked items, which phase 1 never moves or removes;
  - corridors `role.corridor.<group>.<net>`, which pours respect by themselves and phase 1 treats as
    obstacles;
  - `fenolite.roles.routes.critical_copper(design, roles)`, which lists the role copper and the corridors
    of each group.

  With phase 1's copper already on the board, its pours (their outlines) are obstacles of isolated and
  keep-away routes, its locked items are copper like any other, and its provisional corridors are replaced
  along the routes.
- **Acceptance on the reference boards.** Each `bad` variant gets an `open` mode: its placement and its
  faults that are not critical copper, without the critical copper of `bad`. Routing it with `--roles
  critical` must clear every role finding of critical copper that routing can clear, and leave exactly the
  faults of phase 1 (the buck's hot loop, narrow power copper, the bus via, the ground slot). A group that
  phase 1's copper blocks is reported with its reason and proposal. On the `good` variants the command must
  write nothing.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `routing`:
  - ADDED "Role routes in a routing job", "Role outcomes in a routing result", "Octilinear role tiers",
    "Octilinear role ends", "Octilinear isolated branches", "Octilinear switching keep-away", "Octilinear Z
    shapes", "Octilinear role cost", "Octilinear gate pairs", "Octilinear role vias", "Role check in job
    extras" and "Role route codes";
  - MODIFIED "Pairs and escape in a routing job": `ROUTER_FEATURES` gains `roles`.
- `cli-contract`: ADDED "Route command role mode" and "Role route result".
- `net-roles`: ADDED "Critical route plan", "Critical copper is locked and fenced", "Critical copper for
  later phases", "Critical route failures", "Open reference variants" and "Critical routes on both
  backends".

## Non-goals

- **No hot loop.** Its legs, the switch node and the input capacitor's copper are phase 1's pours (c0243),
  by the maintainer's decision of 2026-10-29.
- **No new router and no search.** No maze, no A*, no rip-up across nets: those are phase 3. A connection
  that the shapes cannot reach stays open with its reason and a proposal.
- **No power copper.** Pours, bands, plane stitching and current-sized polygons are phase 1 (c0243).
- **No placement.** A gate loop whose placement bound is too large is reported with a proposal. Fenolite
  moves no part (c0222, non-goals).
- **No routing of a `.PcbDoc` in place**, and no new Altium record. Altium output goes through `convert`.
- **No new measure.** Every finding is c0222's `roles.rules`. The shoelace area used to choose a shape is
  a cost, not a reported measure.
- **No unconfirmed roles routed.** Inferred groups are listed and not routed.
- **No code from third-party routers.** Freerouting, KiCadRoutingTools and the published algorithms are
  prior art only. No figure, table or value comes from a paid standard.
- **No design, value, name or layout from an employer or any organisation.** The open variants reuse the
  authored reference boards.

## Evidence level required

- Routing results: `UNVERIFIED` until checked, as every router's ("Router protocol").
- Role routes judged by `roles.rules`: `INFERRED`, with the hypotheses `H-G-CRIT-*` of `design.md`
  measured on the six reference variants and their open modes.
- KiCad boards written with `--gate drc` and no new finding: `KICAD-VERIFIED` per major (`H-K-CRIT-DRC`).
- Altium output: `INFERRED` from the read-back of the converted project (`H-A-CRIT-READBACK`).
  `ALTIUM-VERIFIED` is not claimed.

## Impact

- New:
  - `src/fenolite/roles/routes.py`: the critical route plan and `critical_copper`;
  - `src/fenolite/routing/roleroute.py`: the role mode of the octilinear router, on its world, shapes and
    acceptance;
  - `src/fenolite/cli/_roleroute.py`: the role mode of `route` (job, corridors, reply);
  - `tests/unit/routing/test_roleroute.py`, `tests/unit/roles/test_routes.py`,
    `tests/unit/roles/test_critical_reference.py`, `tests/kicad/roles/test_critical_drc.py`.
- Changed:
  - routing: `routing/protocol.py` (`JobRoleEnd`, `JobRoleRoute`, `RoleOutcome`, `RoutingJob.roles`,
    `RoutingResult.roles`, `roles` feature), `routing/octilinear.py` (role mode), `routing/codes.py`;
  - command and data: `cli/cmd_route.py` (`--roles`, `--group`, `--roles-file`), `cli/data/explain.toml`;
  - reference boards: `examples/roles/*/` (the `open` mode);
  - docs: `docs/routing.md`, `docs/roles.md`, `docs/cli-contract.md`;
  - guide: the agent guide's `routing` page and the generated `commands`;
  - registers: `docs/hypotheses.md`, `docs/evidence/sources.md`, `openspec/README.md`, `CHANGELOG.md`
    (once `0.7.0.dev0` opens).
- Sources: S-0890 to S-0892 are registered by this proposal. S-0837, S-0838 and S-0850 to S-0853 are reused.
- Size: about 6.5 design-days (c0222 planned 6; see `design.md`, "Size and cut order").
