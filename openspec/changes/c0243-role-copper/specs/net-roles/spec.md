## ADDED Requirements

### Requirement: Role copper plan
`fenolite.roles.copper.plan` SHALL turn the `confirmed` and `declared` roles of a placed `Design` into a `RoleCopperPlan` of c0224 records, zones, keep-outs, rules and issues, in key order, with item keys `role.*`. An unconfirmed inferred role MUST get nothing (`roles.copper-skipped`, `unconfirmed`), and a role net with the user's zone on a layer MUST get no zone there (`user-copper`).

#### Scenario: Only confirmed roles get copper
- **GIVEN** a reference board whose `VOUT` role is inferred and not confirmed
- **WHEN** `uv run pytest tests/unit/roles/test_copper_plan.py -k unconfirmed` plans its role copper
- **THEN** no item key names `VOUT`, and one `roles.copper-skipped` info names `VOUT` and `unconfirmed`

### Requirement: Copper width from current
The required width of a role net with `milliamps` SHALL be `ceil(milliamps × width_per_amp_nm / 1000)` without a temperature rise, and with one the smallest integer width whose S-0269 capacity reaches the current. It MUST be at least the class width, and the reply MUST name the method. A rise without a copper thickness MUST fall back to the rule of thumb. A `power` or `switch_node` net without `milliamps` MUST be skipped (`current-missing`).

#### Scenario: Both methods
- **WHEN** `uv run pytest tests/unit/roles/test_copper_width.py` sizes 2 A on 35 µm outer copper without a rise and with a 10 K rise
- **THEN** the widths are 762 000 nm (`rule-of-thumb`) and the smallest width whose fit capacity is at least 2 A (`fit`), one nanometre less falling short

### Requirement: Bands drawn for the pour
Each role band SHALL be drawn one pour grid cell (0.1 mm) wider than the required width of its net, so that the simulated pour, measured on that grid, holds at least the required width.

#### Scenario: Switch-node bands one cell wider
- **WHEN** `uv run pytest tests/unit/roles/test_copper_plan.py -k zones` plans the bare good buck
- **THEN** every `SW` band has `width` and `max_width` equal to the required width plus 0.1 mm

### Requirement: Power and switch-node copper
Each `power` and `switch_node` net SHALL get one locked zone per layer: the union of c0224 bands along a rectilinear tree between its pad clusters, hot-loop legs first on the pads' layer. `max_width` MUST be twice the width for `power` and equal to it for `switch_node` and `high_voltage`. An edge without a path MUST give `roles.copper-blocked`; a branching tree without the `geo` extra, `roles.copper-extra`.

#### Scenario: One zone per net and layer
- **WHEN** `uv run pytest tests/unit/roles/test_copper_plan.py -k zones` resolves the role copper of the bare good buck
- **THEN** `VIN`, `SW`, `VL` and `VOUT` each hold exactly one generated zone on `F.Cu`, KiCad's zone check finds no `zones_intersect`, and the `SW` zone is no wider than its required width plus one pour grid cell

### Requirement: Loose ends joined
A loose end of a role net's own track on a layer where the net gets bands SHALL be joined to the net's planned copper by a band, or, where no band fits, by locked tracks of the loose track's width with ids from the keys `role.join.<net>.<layer>.<n>.<i>`; without a path it MUST give `roles.copper-blocked`.

#### Scenario: Loose ends joined
- **WHEN** `uv run pytest tests/unit/roles/test_copper_plan.py -k loose` plans the bare good buck and the bare good BMS
- **THEN** the buck's switch node has one band `role.switch_node.SW.F.Cu.join0`, and the BMS board holds the plan's locked join tracks

### Requirement: Switch node kept from sensitive copper
A `switch_node` net with victim nets of c0222 (Kelvin, other switches' gates, sensitive signals) SHALL get a clearance rule `role.sw.<net>` at `switching_distance_nm` to each of them; without victims it gets no rule. Its spine MUST avoid victim copper on an adjacent layer grown by that distance. The ground plane MUST NOT be cut for it.

#### Scenario: Sense pair not under the switch node
- **GIVEN** the bare bad half-bridge, whose sense pair runs on `In1.Cu`
- **WHEN** `uv run pytest tests/unit/roles/test_copper_plan.py -k victims` resolves its role copper
- **THEN** the switch-node zone does not overlap the sense pair grown by 1 mm, and the model holds the rule `role.sw.SW` naming both Kelvin nets

### Requirement: Ground copper and stitching
Each `ground` net SHALL get one locked zone over the board outline on each ground layer (default `B.Cu` on 2 layers, `In1.Cu` on 4), priority 0, and one stitching record over its zones on different layers with `stitch_pitch_nm` (default 5 mm) and `min_vias` 2. `ground_fill="all"` MUST also pour the free outer area.

#### Scenario: Ground joined in pieces
- **WHEN** `uv run pytest tests/unit/roles/test_copper_ground.py` resolves the ground of the bare good half-bridge with `ground_layers=("In1.Cu", "B.Cu")`
- **THEN** each overlap of two ground zones holds at least two vias, no `kicad.generate.stitch-short` is reported, and c0204's `dead` check finds no generated ground piece

### Requirement: Stitching vias keep off other bands
A via of a role stitching record SHALL keep off the band of every other net, on every layer, by that band's clearance, so that the fill around it never narrows the band below its width; the ground stitching clearance MUST be the largest class clearance in force.

#### Scenario: Two planes under the switch node
- **WHEN** the same test builds the half-bridge with ground planes on `In1.Cu` and `B.Cu`
- **THEN** the run is not refused: no `roles.copper-worse`, so the `SW` fill keeps its required section

### Requirement: Pad connections per role
Generated zones SHALL connect pads `solid` for `power`, `switch_node` and `high_voltage` nets and `thru_hole_only` for `ground` nets, set per zone so that one setting holds per net. An override by kind MUST apply to every zone of that kind. No pad's own `zone_connection` is written.

#### Scenario: Ground reliefs on through-hole pads
- **WHEN** `uv run pytest tests/unit/roles/test_copper_plan.py -k connection` plans the bare good `bms`
- **THEN** every `GND` zone has the connection `thru_hole_only`, every power zone `solid`, and with `connection={"ground": "solid"}` the `GND` zones are `solid`

### Requirement: Via arrays at layer changes
Where a role net with `milliamps` has terminals on two copper layers, the plan SHALL generate its zone on both and one stitching record limited to the transition patch with `min_vias = ceil(milliamps / milliamps_per_via)`, the patch excluding the hot loop's pads grown by the width. Too few vias MUST be judged as `roles.via-current`.

#### Scenario: Five vias for one ampere
- **GIVEN** a power net of 1 A with SMD pads on `F.Cu` and `B.Cu`
- **WHEN** `uv run pytest tests/unit/roles/test_copper_vias.py` resolves its role copper
- **THEN** the patch holds at least five vias of the net, all inside both zones

### Requirement: High-voltage copper
For a `high_voltage` net, or a `power` net at or over `high_voltage_mv`, with a user `[[distance]]` or `[[step]]` row, the plan SHALL add a clearance rule `role.hv.<net>` and a keep-out band at the largest such distance around the net's copper, its band included. The net's band MUST NOT widen, and high-voltage nets MUST be planned before the others, whose spines keep out of the envelope. Without a row it MUST generate nothing near the net and give `roles.limit-missing`.

#### Scenario: The bus keeps the user's distance
- **GIVEN** the bare good half-bridge, whose bus has a 400 V working voltage and a user distance row of 3 mm
- **WHEN** `uv run pytest tests/unit/roles/test_copper_hv.py` resolves its role copper
- **THEN** the model holds `role.hv.VBUS` at 3 mm, the barrier encloses the bus band, and no generated copper of another net lies within 3 mm of the bus

### Requirement: Corridors for critical routes
For each net of a gate loop or Kelvin pair without a `role.corridor.<group>.<net>` area, the plan SHALL write that provisional pour-only rule area on the outer layer of its pads: the hull of the net's pad-to-pad segments grown by half the corridor width, Kelvin ends on the inner half of the sense pads. A corridor over another net's pad or a locked item of another net MUST be left out with `roles.corridor-blocked`.

#### Scenario: Corridors keep pours out
- **WHEN** `uv run pytest tests/unit/roles/test_copper_corridors.py` resolves the bare good half-bridge
- **THEN** the gate nets `GH` and `GL` and the two nets of its Kelvin pair each have one corridor `role.corridor.<group>.<net>`, and no generated zone's simulated pour enters a corridor on its layer

### Requirement: No corridor over planned copper
A gate-loop return net with a copper role of its own SHALL get no corridor, since its copper is planned, and a Kelvin branch whose sense track ends loose MUST get none.

#### Scenario: Returns with copper roles
- **WHEN** the same test plans the bare good half-bridge
- **THEN** its gate returns `SW` and `GND`, both with copper roles, have no corridor

### Requirement: Phase 2 copper kept
Phase 1 SHALL treat every locked item of another net and every rule area named `role.corridor.*` as an obstacle (decided by the maintainer on 2026-10-29: phase 2 runs first and writes these corridors; the hot loop is phase 1's). It MUST NOT edit or remove such an area unless it wrote it and the manifest holds its current fingerprint.

#### Scenario: Phase 2's corridors are kept
- **GIVEN** the bare good half-bridge with a rule area `role.corridor.gate_Q1.GH` that the manifest does not hold
- **WHEN** `uv run pytest tests/unit/roles/test_copper_corridors.py -k kept` resolves its role copper
- **THEN** that area is unchanged, no provisional corridor is written for `gate_Q1`'s `GH`, and no generated zone's simulated pour enters it

### Requirement: Kept copper and repeat runs
Role items SHALL have ids from their keys, and `.fenolite/role-copper.json` MUST record each key's fingerprint. An item edited since then, an item in `keep`, and every item without a role key MUST be kept (`roles.copper-kept` for an edit). `regenerate` MUST replace an edited item. A run on its own output MUST plan no change.

#### Scenario: Second run and a user edit
- **WHEN** `uv run pytest tests/unit/roles/test_copper_repeat.py` runs the role copper twice on a bare board, then moves one corner of the `VIN` zone and runs again
- **THEN** the second run plans no change, and the third keeps the edited zone with one `roles.copper-kept`

### Requirement: Role copper verification
A role-copper run SHALL judge the board with `fenolite.roles.judge` before and after its plan, on the simulated pour. A finding of warning or above on a role net present after and not before MUST be `roles.copper-worse` (error), and nothing is written. The topological findings (where a Kelvin branch or a gate return attaches) belong to the routes that phase 1 keeps: they MUST be reported and MUST NOT count as worse. The reply MUST list the cleared findings.

#### Scenario: A worse result is refused
- **GIVEN** a test planner that joins a 2 A net with a 0.2 mm track
- **WHEN** `uv run pytest tests/unit/roles/test_copper_verify.py` runs it
- **THEN** the result holds `roles.copper-worse` naming `roles.width-current`, the exit code is 5 and no file is planned

### Requirement: Role copper on the reference boards
Each reference board SHALL have `good_roles.py` and `bad_roles.py`: the variant without its power, switch-node, ground and high-voltage copper, with `design.role_copper()`. `good_roles` MUST give no `roles.*` warning. `bad_roles` MUST give none of the copper codes and exactly the `bad` variant's routing findings.

#### Scenario: Copper findings cleared
- **WHEN** `uv run pytest tests/unit/roles/test_copper_reference.py` builds and checks the six scripts
- **THEN** the good ones have no warning; the bad ones have no `width-current`, `section-current`, `via-current`, `return-gap` or `near-switching`, and the same `kelvin-*`, `gate-return-shared` and `gate-loop` findings as `bad`

### Requirement: Role copper evidence
The KiCad builds of the six role-copper scripts, refilled by `kicad-cli`, SHALL show no DRC violation type with more entries than the same board without role copper, unconnected items aside, and are `KICAD-VERIFIED` for that only. The planner stays `INFERRED`, citing `H-G-ROLE-COPPER-*`.

#### Scenario: DRC on the bench
- **WHEN** `uv run pytest tests/kicad/roles/test_copper_drc.py` builds, refills and checks each script on KiCad 10
- **THEN** no violation type has more entries than on the board without role copper

## MODIFIED Requirements

### Requirement: Role issue codes
`fenolite.roles.codes.ISSUE_CODES` SHALL be the closed table of the twenty-five `roles.*` codes of c0222's and c0243's designs with their severities, and an issue outside it MUST raise `ValueError`. `fenolite explain` MUST explain each code. No `FEN-` code is added.

#### Scenario: Codes in the table
- **WHEN** `uv run pytest tests/unit/roles/test_codes.py tests/unit/cli/test_explain_cmd.py -k roles` runs
- **THEN** every code has its severities and an explanation, `roles.kelvin-outer` allows `warning` and `error`, and `roles.input-missing` is not in the table

#### Scenario: Copper codes in the table
- **WHEN** the same tests run
- **THEN** the table holds `roles.copper-skipped`, `copper-blocked`, `copper-extra`, `copper-kept`, `copper-worse` (error only), `copper-placement`, `copper-narrow` and `roles.corridor-blocked`, each explained
