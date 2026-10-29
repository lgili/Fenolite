## ADDED Requirements

### Requirement: Critical route plan
`fenolite.roles.routes.plan_critical` SHALL turn each confirmed or declared `GateLoop` and `KelvinPair` into routes of its open connections: gate out segments and one return from the source or Kelvin-source pad, and two partnered Kelvin branches from inner-half entries. An inferred group MUST be skipped with reason `unconfirmed`. A `HotLoop` MUST NOT be planned (its copper is phase 1's); one named by `--group` MUST be skipped with reason `phase-1`.

#### Scenario: Routes of the half-bridge
- **GIVEN** the `open` variant of `examples/roles/half_bridge` with its groups confirmed
- **WHEN** `uv run pytest tests/unit/roles/test_routes.py -k half_bridge` plans it
- **THEN** gate loop `gate_Q1` has one return starting at `Q1`'s Kelvin-source pad, gate loop `gate_Q2` one out route, the Kelvin pair two partnered routes, and no route belongs to the hot loop

### Requirement: Critical copper is locked and fenced
Every track, arc and via written in role mode SHALL be `locked`. Each routed branch MUST get a `Keepout` named `role.corridor.<group>.<net>` with only `no_copper_pour`, on the branch's layer and on every layer of its vias' spans, its outline the branch grown by half its width plus the zone clearance in force. An existing rule area of that name (a provisional corridor of phase 1) MUST be replaced, not duplicated.

#### Scenario: The fill leaves the sense branch alone
- **GIVEN** the routed `open` variant of `buck_shunt`
- **WHEN** `uv run pytest tests/unit/roles/test_critical_reference.py -k corridor` fills the zones and runs `fenolite roles --check`
- **THEN** both sense branches are locked, each lies inside its corridor, and no `roles.kelvin-shared` is reported

### Requirement: Critical copper for later phases
`fenolite.roles.routes.critical_copper(design, roles)` SHALL return, per gate loop and Kelvin pair, the ids of its `role.corridor.<group>.<net>` areas and of the locked tracks, arcs and vias of its nets that lie inside its corridors of their net, read from the board, so that later phases keep that copper and fill around it.

#### Scenario: Copper and corridors of a routed group
- **GIVEN** the routed `open` variant of `buck_shunt`, read back from its KiCad board
- **WHEN** `uv run pytest tests/unit/roles/test_routes.py -k critical_copper` calls `critical_copper`
- **THEN** the Kelvin pair's entry holds its two corridors and every locked track of its branches, and the gate loops' entries hold no copper written by role mode

### Requirement: Critical route failures
A planned group that is not routed SHALL appear in the reply with one reason (`no-room`, `too-long`, `no-layer`, `near-switching`, `isolation`, `role-check`, `drc`, `pads`, `unconfirmed`) and one proposal (`confirm`, `allow-via`, `free-corridor`, `move-part`, `rip`, `raise-limit`, `power-copper`) with its command and a `render --region` command. A group MUST NOT be skipped silently.

#### Scenario: A blocked pair is reported
- **GIVEN** the `open` variant of `bms` with a part added across the path between the shunt and the monitor
- **WHEN** `fenolite route <board> --router octilinear --roles critical --dry-run --json` runs
- **THEN** the Kelvin pair's entry has status `unrouted`, reason `no-room`, proposal `free-corridor` naming the part, a `render --region` command, and one `route.role-unrouted`

### Requirement: Open reference variants
Each reference board's `make` SHALL accept the variant `open`: the `bad` placement and the faults that are not critical copper, without the `bad` critical copper, built by `open.py`. After `route --roles critical --confirm`, each `open` variant MUST give no `roles.*` finding of a routed group, only the findings that `design.md` lists, and a second run MUST write nothing.

#### Scenario: Critical findings cleared
- **WHEN** `uv run pytest tests/unit/roles/test_critical_reference.py` routes and checks the three `open` variants and runs the command on the `good` ones
- **THEN** each `open` variant keeps exactly the findings `design.md` lists (phase 1's faults, and the blocked half-bridge pair reported with `near-switching` naming `SW_UNDER`), each `good` variant plans no write, and the second run on each routed board writes nothing

### Requirement: Critical routes on both backends
A routed `open` variant converted with `fenolite convert --to altium` SHALL read back with every role track and via at its position and width with `locked` true and every corridor as a pour keep-out region on its layer. The role copper MUST change the `roles.*` findings of the Altium reading exactly as it changes those of the KiCad reading: it adds none, and it removes the same ones.

#### Scenario: Same critical copper in Altium
- **WHEN** `uv run pytest tests/unit/roles/test_critical_reference.py -k altium` converts the three routed `open` variants and reads them back
- **THEN** the role copper, the locks and the corridors match the KiCad model, and against the convert of the unrouted `open` variant both readings lose the same `roles.*` findings and gain none
