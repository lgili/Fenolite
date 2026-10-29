## ADDED Requirements

### Requirement: Critical route plan
`fenolite.roles.routes.plan_critical` SHALL turn each confirmed or declared `HotLoop`, `GateLoop` and `KelvinPair` into routes of its open connections: hot legs between pads of two parts on one net, gate out segments and one return from the source or Kelvin-source pad, and two partnered Kelvin branches from inner-half entries. An inferred group MUST be skipped with reason `unconfirmed`.

#### Scenario: Routes of the half-bridge
- **GIVEN** the `open` variant of `examples/roles/half_bridge` with its groups confirmed
- **WHEN** `uv run pytest tests/unit/roles/test_routes.py -k half_bridge` plans it
- **THEN** each gate loop has its out routes and one return starting at the Kelvin-source pad, the Kelvin pair has two partnered routes, and no route belongs to the complete hot loop

### Requirement: Critical copper is locked and fenced
Every track, arc and via written in role mode SHALL be `locked`. Each routed isolated branch MUST get one `Keepout` named `role-corridor:<group>:<net>` with only `no_copper_pour`, on the branch's layer and on every layer of its vias' spans, its outline the branch grown by half its width plus the zone clearance in force.

#### Scenario: The fill leaves the sense branch alone
- **GIVEN** the routed `open` variant of `buck_shunt`
- **WHEN** `uv run pytest tests/unit/roles/test_critical_reference.py -k corridor` fills the zones and runs `fenolite roles --check`
- **THEN** both sense branches are locked, each lies inside its corridor, and no `roles.kelvin-shared` is reported

### Requirement: Critical copper for later phases
`fenolite.roles.routes.critical_copper(design, roles)` SHALL return, per group, the ids of its role copper and corridors, and the hot legs whose track is narrower than the width their current needs (`power_copper_needed`, with net, required width and track id), so that later phases keep the copper and widen those legs.

#### Scenario: A capped hot leg
- **GIVEN** a bench hot leg of 5 A whose end pad is 1 mm wide
- **WHEN** `uv run pytest tests/unit/roles/test_routes.py -k power_copper` routes it and calls `critical_copper`
- **THEN** the leg's track is 1 mm wide and `power_copper_needed` names it with a required width of 1.905 mm

### Requirement: Critical route failures
A planned group that is not routed SHALL appear in the reply with one reason (`no-room`, `too-long`, `no-layer`, `near-switching`, `isolation`, `role-check`, `drc`, `pads`, `unconfirmed`) and one proposal (`confirm`, `allow-via`, `free-corridor`, `move-part`, `rip`, `raise-limit`, `power-copper`) with its command and a `render --region` command. A group MUST NOT be skipped silently.

#### Scenario: A blocked pair is reported
- **GIVEN** the `open` variant of `bms` with a part added across the path between the shunt and the monitor
- **WHEN** `fenolite route <board> --router octilinear --roles critical --dry-run --json` runs
- **THEN** the Kelvin pair's entry has status `unrouted`, reason `no-room`, proposal `free-corridor` naming the part, a `render --region` command, and one `route.role-unrouted`

### Requirement: Open reference variants
Each reference board's `make` SHALL accept the variant `open`: the `bad` placement and non-critical faults without the `bad` critical copper, built by `open.py`. After `route --roles critical --confirm`, each `open` variant MUST give no `roles.*` finding of a planned group, only the non-critical faults that design lists, and a second run MUST write nothing.

#### Scenario: Critical findings cleared
- **WHEN** `uv run pytest tests/unit/roles/test_critical_reference.py` routes and checks the three `open` variants and runs the command on the `good` ones
- **THEN** each `open` variant keeps exactly its listed non-critical findings, each `good` variant plans no write, and the second run on each routed board writes nothing

### Requirement: Critical routes on both backends
A routed `open` variant converted with `fenolite convert --to altium` SHALL read back with every role track and via at its position and width with `locked` true and every corridor as a pour keep-out on its layers. `roles --check` on the Altium reading MUST give the findings of the KiCad reading.

#### Scenario: Same critical copper in Altium
- **WHEN** `uv run pytest tests/unit/roles/test_critical_reference.py -k altium` converts the three routed `open` variants and reads them back
- **THEN** the role copper, the locks and the corridors match the KiCad model, and the `roles.*` findings of both readings are equal
