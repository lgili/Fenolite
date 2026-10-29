## Why

Phase 1 of the router that works from electrical intent (c0222, "Plan of phases 1 to 4"; the maintainer's
decisions of 2026-10-28 and 2026-10-29). Phase 0 (c0222) gives every net a role, inferred and then
confirmed by the user, and checks a board against those roles. It changes no copper. The maintainer's
deliverable is different: the critical routes and the power copper are made automatically, and the rest is
proposed. The maintainer's boards are motor drives, switch-mode supplies, chargers and BMS, and
mixed-signal control, with 2 to 4 layers and up to about 150 parts.

The routers the maintainer tried draw a thin track where a polygon is needed and leave the switch node
sprawling. A human then draws the power copper by hand: the input supply, the switch node, the ground
plane, the vias where the current changes layer, and the keep-outs around a high-voltage bus. Each of
those follows from a net's role and current. `dev` already has the pieces:

- c0224's generated copper: `band` (45° widening between `width` and `max_width` where clearance allows),
  `stitch_pieces`, `barrier`, `keepout_ring` and `fanout_zone`, resolved after placement into locked items;
- zones, `fenolite fill`, and c0204's simulated pour;
- c0213's necks and loops, c0175's power paths and the S-0269 capacity fit;
- c0204's relief and dead-copper checks;
- c0215's computed Altium pours and Polygon Connect Style rules;
- c0225/c0209's DRC gate;
- c0222's roles, its role profile and its stage `roles.rules`.

What is missing is the step that turns roles into copper, and a way to carry generated copper to Altium.
Today the Altium target refuses generated copper (`kicad.generate.altium`).

## What Changes

- **Role copper.** A planner, `fenolite.roles.copper`, turns the confirmed and declared roles of a placed
  board into copper:
  - **Power:** one zone per `power` net and layer. It is the union of c0224 bands along a tree of
    horizontal and vertical spines between the net's pads. The width comes from the role's current, by
    c0222's two methods: the S-0851 rule of thumb, or the S-0269 fit when the user gives a temperature rise.
    The zone widens up to twice that width where clearance allows.
  - **Switch node:** the same at exactly the required width, so its area is as small as the current
    allows (S-0860, S-0852). It keeps the switching distance from sensitive copper on its own layer, and
    stays out from under it on the next layer.
  - **Ground:** a zone over the board on each reference layer, with stitching vias between ground zones
    on different layers.
  - **Pad connections per role:** solid for power, switch-node and high-voltage nets; thermal reliefs on
    through-hole pads only for ground (S-0861, S-0862).
  - **Via arrays:** where a power net's copper changes layer, vias are counted from its current
    (`milliamps_per_via`, S-0851).
  - **High voltage:** a clearance rule and a keep-out band around each `high_voltage` net, at the user's
    own distance. No distance is ever taken from a table.
  - **Corridors:** pour-free rule areas that keep the gate-loop and Kelvin paths free for phase 2.
- **One planner, two surfaces.**
  - The DSL call `design.role_copper(...)`, resolved by the build after placement, for both targets.
  - The command `fenolite copper PATH`, for a KiCad board or a built project, under the reviewed-plan
    protocol (`--dry-run`, then `--confirm --plan ID`).
- **Altium output.** The build already resolves script copper in an in-memory KiCad build and hands it to
  the Altium writer. That hand-over now also resolves generated copper and role copper. Zones become
  polygons, poured by c0215. Keep-outs become keep-out records, and connection styles become Polygon
  Connect Style rules per net. `kicad.generate.altium` remains only for `--copper-from`.
- **Kept copper and repeat runs.**
  - The planner never deletes copper that it did not generate, and it treats every other item as an
    obstacle.
  - Role copper that the user has since edited is kept. A manifest of fingerprints in `.fenolite/` finds
    those edits.
  - A second run gives the same bytes.
- **Verification.** The planner judges its result with c0222's role judge on the simulated pour. A new
  finding of warning or above on a role net is `roles.copper-worse` (error), and nothing is written.
  `--gate drc` adds KiCad's DRC through c0225.
- **Acceptance on c0222's reference boards.** Each board gets two more scripts, with the power copper of
  its good and bad variants left out and `design.role_copper()` called instead. The good ones must stay
  clean. On the bad ones, phase 1 must clear the copper findings and leave the routing findings to phase 2.
- **Eight issue codes**, `roles.copper-*` and `roles.corridor-blocked`, added to c0222's closed table.

## Capabilities

### New Capabilities

None. Phase 1 belongs to `net-roles`.

### Modified Capabilities

- `net-roles`:
  - ADDED "Role copper plan", "Copper width from current", "Power and switch-node copper", "Switch node kept from
    sensitive copper", "Ground copper and stitching", "Pad connections per role", "Via arrays at layer changes", "High-voltage copper",
    "Corridors for critical routes", "Kept copper and repeat runs", "Role copper verification", "Role
    copper on the reference boards" and "Role copper evidence";
  - MODIFIED "Role issue codes" (seventeen codes become twenty-five).
- `design-dsl`: ADDED "Role copper in the DSL"; MODIFIED "Generated copper codes" (`kicad.generate.altium`
  is narrowed to `--copper-from`).
- `cli-contract`: ADDED "Copper command".
- `altium-build`: MODIFIED "Script copper in an Altium build". The in-memory KiCad build also runs for
  generated copper and role copper.

## Non-goals

- No routing of tracks. The gate loops, Kelvin pairs and signals belong to phase 2 (`c0244-critical-routes`,
  written in parallel), to phase 4 and to phase 3. Phase 1 only keeps their corridors free.
- No placement. When the placement bound of a hot loop is over the user's `loop_max`, phase 1 reports it
  (`roles.copper-placement`) and does not move parts.
- No deletion of the user's copper, and no editing of a `.PcbDoc` that Fenolite did not build (c0241's edit
  sessions are not done). An Altium board receives role copper through a build.
- No creepage or clearance values, no default temperature rise and no default current. Nothing is taken
  from IPC-2152, IPC-2221 or IEC 60664, which are paid standards.
- No new measuring kernel. Verification is c0222's role judge over the analyses of `dev`.
- No code from a third-party router or EDA tool.

## Evidence level required

- The planner and its geometry: `INFERRED`, with the hypotheses `H-G-ROLE-COPPER-*` of `design.md`
  measured on the reference boards.
- KiCad builds of the role-copper variants: `KICAD-VERIFIED` that `kicad-cli` DRC, after a refill, finds no
  violation type with more entries than on the same board without role copper (the criterion of c0224's
  `H-K-GEN-DRC`).
- Altium builds: `INFERRED`, through c0215's experimental computed pour. `ALTIUM-VERIFIED` is not claimed.

## Impact

- **New:**
  - `src/fenolite/roles/copper.py` (the planner), `src/fenolite/roles/spine.py` (spine trees), and
    `src/fenolite/roles/rolemanifest.py` (the fingerprint manifest);
  - `src/fenolite/cli/cmd_copper.py`;
  - `src/fenolite/lens/rolecopper.py` (the planner protocol that the build takes, as `checks` takes a
    judge);
  - `src/fenolite/dsl/rolecopper.py`;
  - six scripts `examples/roles/<board>/good_roles.py` and `bad_roles.py`;
  - tests.
- **Changed:**
  - `backends/kicad/generate.py`: band records with a `group` are united into one zone; a net barrier is
    resolved after the bands; stitch candidates can be limited to a patch;
  - `lens/build.py`, `cli/cmd_build.py` (the Altium hand-over), `roles/codes.py`, `dsl/design.py` and
    `dsl/__init__.py`;
  - `cli/data/explain.toml`, `docs/roles.md`, `docs/copper.md`, `docs/cli-contract.md` and `docs/dsl.md`;
  - the guide pages `board-power`, `board-grounds` and `board-insulation`, and `docs/hypotheses.md`;
  - `CHANGELOG.md`, once `0.7.0.dev0` opens.
- **Sources:**
  - S-0860 to S-0863 are registered by this proposal, from the reserved block S-0860 to S-0889. The
    parallel `c0244-critical-routes` starts 30 ids later, at S-0890.
  - S-0269, S-0287, S-0834 and S-0851 to S-0854 are reused.
- **Size:** about 10 design-days (c0222's plan said 5; `design.md`, "Sizes", explains the difference).
