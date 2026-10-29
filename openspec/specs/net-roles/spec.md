# net-roles Specification

## Purpose
TBD - created by archiving change c0222-net-roles. Update Purpose after archive.

## Requirements

### Requirement: Role kinds
`fenolite.roles.ROLE_KINDS` SHALL be the closed tuple `power`, `switch_node`, `ground`, `kelvin`, `gate`, `signal`, `high_voltage`. Each net of a design MUST get exactly one role: stored, declared or inferred. A role MAY carry `milliamps` and `working_mv` (integers) and `sensitive`. A `power` net whose `working_mv` is at or above the profile's `high_voltage_mv` MUST be judged for distances as a `high_voltage` net.

#### Scenario: One role per net
- **GIVEN** the `good` variant of `examples/roles/buck_shunt`
- **WHEN** `uv run pytest tests/unit/roles/test_infer_reference.py -k buck` infers its roles
- **THEN** every net of the circuit has one row, and each `kind` is a member of `ROLE_KINDS`

### Requirement: Role groups
The roles SHALL hold three groups that name pads as `REF-PIN`: `HotLoop(name, pads)` (ordered, at least three pads), `KelvinPair(name, element, receiver, force=())` and `GateLoop(name, drive, gate, source, ret, resistor=())`. A group name MUST match the copper key pattern and MUST be unique per kind of group.

#### Scenario: Groups of the half-bridge
- **GIVEN** the `good` variant of `examples/roles/half_bridge`
- **WHEN** its roles are inferred
- **THEN** it holds one `HotLoop` through the bus capacitor and both switches, two `GateLoop`s whose `source` is each switch's Kelvin-source pad, and one `KelvinPair` on the low-side shunt

### Requirement: Role sources
Each role and group SHALL record its source: `inferred`, `confirmed` or `declared`. A `declared` role MUST win over a stored `confirmed` role and over an inferred one of the same net, with `roles.declared-differs` (info) when they differ. Inferred roles that are not confirmed MUST NOT be stored.

#### Scenario: A declaration wins
- **GIVEN** a script that declares `SW` as `signal` on a board where `SW-1` infers `switch_node`
- **WHEN** `fenolite roles <board> --json` runs
- **THEN** the row of `SW` has `kind` `signal` and source `declared`, and the issues hold one `roles.declared-differs`

### Requirement: Role document
A board that Fenolite did not build SHALL keep its roles in `<board stem>.roles.json` beside it, or in the file of `--roles FILE`: canonical JSON with schema `fenolite.roles.v0`, holding one `RoleSet`. The board file MUST NOT be written. The same document MUST serve a KiCad and an Altium board. A malformed document MUST be `FEN-3004`, exit 3.

#### Scenario: Roles beside a hand-routed board
- **GIVEN** a copy of the `bad` variant's KiCad board in `tmp_path` and a role document beside it that confirms `SW`
- **WHEN** `fenolite roles <board> --json` runs
- **THEN** the row of `SW` has source `confirmed`, and the board's bytes are unchanged

### Requirement: Part classes
`fenolite.roles.classify` SHALL give each component one class of `transistor`, `diode`, `inductor`, `capacitor`, `resistor`, `shunt`, `driver`, `amplifier`, `controller`, `connector`, `net_tie` or `other`, with its terminal map and a confidence. The evidence MUST be weighed in this order: the user's class, pin names, pin types, the value or pad count, the reference prefix. A class from the prefix alone MUST be `low`.

#### Scenario: Classes from pin names
- **GIVEN** an authored circuit with a part `Q7` whose pins are named `G`, `D`, `S` and `KS`, and a part `X1` whose pins are `IN+`, `IN-`, `OUT`
- **WHEN** `uv run pytest tests/unit/roles/test_classify.py` classifies them
- **THEN** `Q7` is `transistor` with `kelvin_source` on `KS`, `X1` is `amplifier`, both `high`

### Requirement: Inference rules
`fenolite.roles.infer` SHALL apply the closed, ordered rule table of the design (`SW-1` to `SIG-0`), deterministically. Each inferred role and group MUST name its rule, its confidence (the lowest of the classes it read) and the pads it read. Two rules giving different kinds at one confidence MUST give the first kind and `roles.ambiguous` (warning). `HV-1` MUST NOT fire from a net name.

#### Scenario: Switching node and hot loop of a buck
- **GIVEN** the `good` variant of `buck_shunt`
- **WHEN** its roles are inferred
- **THEN** `SW` is `switch_node` by `SW-1` with confidence `high`, and the hot loop holds the input capacitor's two pads and the two switches' drain and source pads

#### Scenario: No high voltage from a name
- **GIVEN** an authored circuit with a net `HV_BUS` and no `working_mv`
- **WHEN** its roles are inferred
- **THEN** `HV_BUS` is not `high_voltage`

### Requirement: Currents are never inferred
A role's `milliamps` SHALL come from the role, then from a `[[current]]` row of the requirements file, then from `--current NET=AMPS`. Fenolite MUST NOT infer or assume a current. A `power`, `switch_node` or `ground` role without one MUST get `roles.current-missing` (info), and its current MUST NOT be judged.

#### Scenario: A power net without a current
- **GIVEN** the `good` variant of `bms` with no requirements file
- **WHEN** `fenolite roles <board> --check --json` runs
- **THEN** no `roles.width-current` is reported, and one `roles.current-missing` names each power net

### Requirement: Roles show and confirm
`fenolite roles PATH` SHALL show one row per net and the groups. `--accept`, `--accept-all [--min-confidence]`, `--set NET=KIND[:KEY=N]`, `--reject`, `--accept-group`, `--reject-group` and `--current` SHALL change the stored roles only through the reviewed-plan protocol. They MUST write only the role document, or `.fenolite/rules.json` of a built project. A rejected net MUST be stored as a confirmed `signal`.

#### Scenario: Confirm through a plan
- **GIVEN** a copy of the `bad` variant of `buck_shunt` in `tmp_path`
- **WHEN** `fenolite roles <board> --accept-all --min-confidence high --dry-run --json` runs, then `--confirm --plan <plan_id>`
- **THEN** the first exits 0 and writes nothing, the second writes `<stem>.roles.json` only, and its `receipt` lists that file with its SHA-256

### Requirement: Role profile
`fenolite.roles.profile` SHALL hold the default limits of the design's table. Each constant MUST name its source id or hypothesis and its label. The profile MUST hold no creepage or clearance value, no temperature rise, no copper thickness and no current. `docs/roles.md`, "Default limits", MUST list every key with its value, source and label.

#### Scenario: Every default has a source
- **WHEN** `uv run pytest tests/unit/roles/test_profile.py` reads the profile and `docs/roles.md`
- **THEN** every key names an `S-` id or an `H-G-ROLE-` id and a label, and the page lists the same keys

### Requirement: Role limit overrides
`RoleLimit(key, value, net=None, kind=None)` SHALL override a profile key for the design, a kind or one net, and the most specific MUST win. An unknown key or a value of the wrong unit MUST be refused (`DslError` in a script, `FEN-3004` in a document). A finding MUST name its limit's key, value and source: `profile`, `override` or `requirements`.

#### Scenario: A net override wins
- **GIVEN** a design limit `loop_max` of 200 mm² and a limit of 60 mm² for the net `SW`
- **WHEN** the hot loop of `SW` measures 150 mm²
- **THEN** one `roles.loop-area` is reported with the limit 60 mm² and the source `override`

### Requirement: Finding severities
A finding against a profile default SHALL be a `warning`. It MUST be an `error` only when the limit comes from the user and the role is `confirmed` or `declared`. `roles.kelvin-outer`, `roles.kelvin-shared` and `roles.gate-return-shared` MUST be an `error` on a confirmed or declared group. A finding on an unconfirmed inferred role MUST be at most a `warning`.

#### Scenario: Unconfirmed roles warn only
- **GIVEN** the `bad` variant of `buck_shunt` without a role document
- **WHEN** `fenolite roles <board> --check --json` runs
- **THEN** every `roles.*` issue has severity `warning` or `info`, the exit code is 0, and one `roles.unconfirmed` gives the count

### Requirement: Role measures come from the analyses
`fenolite.roles.measure` SHALL measure roles only by calling `fenolite.analysis`: `loop_areas`, `analyze_power`, `analyze_split`, `analyze_necks`, `analyze_distances`, `analyze_returns`, `analyze_coupling` and `analyze_ties`, with inputs derived from the roles. Each measure MUST name its analysis and copper state, and the analyses' input warnings MUST pass through unchanged.

#### Scenario: Measures name their analysis
- **GIVEN** the `bad` variant of `buck_shunt`
- **WHEN** `uv run pytest tests/unit/roles/test_measure.py -k sources` runs `fenolite roles <board> --check --json`
- **THEN** each entry of `result.measures` names one of those analyses and a copper state, and `src/fenolite/roles/` defines no loop area, section, capacity or gap function of its own

#### Scenario: A missing input is the analysis's warning
- **GIVEN** the same board without a stack-up thickness and a role current of 2 A
- **WHEN** `fenolite roles <board> --check --temp-rise 10 --json` runs
- **THEN** the issues hold the `analysis.input-missing` of `analyze_power` naming `copper thickness`, and no `roles.input-missing`

### Requirement: Role loops
Each `HotLoop`, `GateLoop` (drive, resistor, gate, source, return) and `KelvinPair` (element, receiver, receiver, element) SHALL become one derived `[[loop]]` row measured by `loop_areas`. Roles MUST add `bound_nm2`, the shoelace area through the pad centres in loop order, and `ratio_permille = area * 1000 // bound` when the bound is at least `loop_bound_floor_nm2`. A straight leg between pads of one net MUST give `roles.loop-open` and no judged area.

#### Scenario: A rectangle and its bound
- **GIVEN** an authored board whose gate loop's four pads stand at the corners of a 10 mm × 5 mm rectangle, its out and return nets as straight tracks along the two long sides, and a copy whose out track detours as a U reaching 5 mm beyond the rectangle
- **WHEN** `uv run pytest tests/unit/roles/test_loops.py` measures both
- **THEN** the areas are 50 mm² and 100 mm² as `loop_areas` gives them, the bound is 50 mm² both times, and the ratios are 1000 and 2000, all integers

#### Scenario: An unrouted leg
- **GIVEN** the same board with one track removed
- **WHEN** it is measured
- **THEN** one `roles.loop-open` names the two pads of the leg, and no `roles.gate-loop` is reported

### Requirement: Hot and gate loop checks
Each `HotLoop` and `GateLoop` SHALL be judged on its role loop. An area over the user's `loop_max` or `gate_max` MUST be `roles.loop-area` or `roles.gate-loop`, and so MUST a ratio over `loop_ratio_max` or `gate_ratio_max`. A gate return that reaches the switch's power source copper before its `source` pad MUST be `roles.gate-return-shared`.

#### Scenario: The bad buck's hot loop
- **GIVEN** the `bad` variant of `buck_shunt`, whose input capacitor stands 15 mm from the switches
- **WHEN** `uv run pytest tests/unit/roles/test_reference_boards.py -k buck_loop` runs the check
- **THEN** one `roles.loop-area` names the loop, with an area within 10 % of 180 mm² and a ratio over 2000

#### Scenario: A gate return from the source pour
- **GIVEN** the `bad` variant of `half_bridge`, whose high-side gate return joins the source pour away from the Kelvin-source pad
- **WHEN** `uv run pytest tests/unit/roles/test_kelvin.py -k gate_return` runs the check
- **THEN** one `roles.gate-return-shared` names the gate loop and the pour

### Requirement: Kelvin attachment
For each sense pad of a `KelvinPair`, the sense branch SHALL be the copper reached from the receiver without crossing the pad or entering power copper (the active elements of `path_network`). Each attachment offset `t` along the axis to the other sense pad MUST be reported; `t < 0` MUST be `roles.kelvin-outer`. A branch that reaches power copper or a force pad, or a sense net that `analyze_ties` finds shared, MUST be `roles.kelvin-shared`.

#### Scenario: Sense lines of the bad buck
- **GIVEN** the `bad` variant of `buck_shunt`, where one sense line leaves the outer end of `R12`'s pad and the other leaves the pour
- **WHEN** `uv run pytest tests/unit/roles/test_kelvin.py -k reference` runs the check
- **THEN** one `roles.kelvin-outer` names `R12-1` with `t < 0`, and one `roles.kelvin-shared` names `R12-2` and the zone

### Requirement: Kelvin pair and switching distance
A `KelvinPair`'s role loop ratio over `pair_ratio_max` SHALL be `roles.kelvin-apart`. A `kelvin` branch, a `sensitive` `signal` or another switch's gate net SHALL be `roles.near-switching` when the `analyze_distances` gap to `switch_node` copper on its layer is under `switching_distance_nm`, or when it overlaps switching copper on an adjacent layer: its length over switching fills (`analyze_returns`) or its broadside overlap (`analyze_coupling`).

#### Scenario: A sense pair over the switch node
- **GIVEN** the `bad` variant of `half_bridge`, whose sense pair crosses the switch node's pour on the adjacent layer
- **WHEN** the check runs
- **THEN** one `roles.near-switching` names the pair, the switch node and the overlap length, and the `good` variant has none

### Requirement: Current capacity of role copper
For a role with `milliamps`, the active elements of `analyze_power` on its paths SHALL be judged: with the user's rise by their fit capacity (a parallel element by its `analyze_split` share, else at most a warning), without one by width or section against `width_per_amp_nm` times the current and by via count against `ceil(milliamps / milliamps_per_via)`. `analyze_necks` MUST screen its pours at the required width. Findings: `roles.width-current`, `roles.section-current`, `roles.via-current`.

#### Scenario: A thin track on a 2 A net
- **GIVEN** an authored board whose 2 A `power` net runs through a 0.3 mm track and one via between two pours
- **WHEN** `uv run pytest tests/unit/roles/test_current.py` runs the check without and with `--temp-rise 10`
- **THEN** both runs give one `roles.width-current` naming 0.3 mm and the method, and the first gives one `roles.via-current` asking for 10 vias

#### Scenario: No analysis finding from the profile
- **GIVEN** the same board and no requirements file
- **WHEN** the check runs without a rise
- **THEN** the issues hold no `analysis.path-exceeded`, `analysis.path-undecided` or `analysis.neck-narrow`

### Requirement: Returns and high voltage
For `gate` and `sensitive` `signal` nets, each `split` span of `analyze_returns` with the `ground` nets as `reference` SHALL be `roles.return-gap`, and its `analysis.return-split` MUST NOT be repeated. For each `high_voltage` net, and each net judged as one, distances SHALL come from `analyze_distances` against the user's rows, keeping their `analysis.*` codes. A net without a row MUST be `roles.limit-missing`.

#### Scenario: A high-voltage bus without a requirement
- **GIVEN** the `good` variant of `half_bridge` with its distance rows removed
- **WHEN** the check runs
- **THEN** one `roles.limit-missing` names the bus, and no `analysis.clearance-below` is reported

#### Scenario: A cell tap across a ground gap
- **GIVEN** the `bad` variant of `bms` with its roles confirmed
- **WHEN** the check runs
- **THEN** one `roles.return-gap` names the cell-tap net and the span, and no `analysis.return-split` names the same span

### Requirement: Role issue codes
`fenolite.roles.codes.ISSUE_CODES` SHALL be the closed table of the twenty-five `roles.*` codes of c0222's and c0243's designs with their severities, and an issue outside it MUST raise `ValueError`. `fenolite explain` MUST explain each code. No `FEN-` code is added.

#### Scenario: Codes in the table
- **WHEN** `uv run pytest tests/unit/roles/test_codes.py tests/unit/cli/test_explain_cmd.py -k roles` runs
- **THEN** every code has its severities and an explanation, `roles.kelvin-outer` allows `warning` and `error`, and `roles.input-missing` is not in the table

#### Scenario: Copper codes in the table
- **WHEN** the same tests run
- **THEN** the table holds `roles.copper-skipped`, `copper-blocked`, `copper-extra`, `copper-kept`, `copper-worse` (error only), `copper-placement`, `copper-narrow` and `roles.corridor-blocked`, each explained

### Requirement: Reference boards
`examples/roles/` SHALL hold `buck_shunt` (2 layers), `half_bridge` (4 layers) and `bms` (2 layers), authored for Fenolite with CC0 libraries, each with `good.py` and `bad.py`. The `good` variants MUST give no `roles.*` finding of warning or above once their roles are confirmed. The `bad` variants MUST give exactly their designed findings.

#### Scenario: Good and bad variants
- **WHEN** `uv run pytest tests/unit/roles/test_reference_boards.py` builds and checks the six variants
- **THEN** each `good` variant has no warning, and each `bad` variant has exactly the findings listed in the test, with measures within their tolerances

### Requirement: Roles on both backends
The inference, the measures and the checks SHALL read only the `Design` that a backend gives. For each reference variant built for KiCad and for Altium, the role rows and the measures of the two readings MUST be equal within the readers' known rounding.

#### Scenario: Same roles from both builds
- **WHEN** `uv run pytest tests/unit/roles/test_backends.py` reads both builds of each variant
- **THEN** the role rows are equal, and each loop area differs by less than 0.01 mm²

### Requirement: Role evidence
Every reply of `fenolite roles` and of the stage SHALL carry the evidence level `INFERRED`, combining the role hypotheses of the design that its checks rely on with the evidence of the analyses that measured its rows. The limit of each finding MUST name its source id or hypothesis.

#### Scenario: Evidence of a check
- **WHEN** `fenolite roles <bad buck> --check --json` runs
- **THEN** `evidence.level` is `INFERRED`, `evidence.hypotheses` holds `H-G-ROLE-LOOP-RATIO` and `H-G-SHAPE-LOOP`, and the `roles.width-current` issue's message names `S-0851`

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
Each `power` and `switch_node` net SHALL get one locked zone per layer: the union of c0224 bands along a rectilinear tree between its pad clusters, hot-loop legs first on the pads' layer. `max_width` MUST be twice the width for `power` and equal to it for `switch_node` and `high_voltage`. An edge without a path MUST give `roles.copper-blocked`. Without the `geo` extra a group of several bands MUST keep its longest band, with `roles.copper-extra`.

#### Scenario: One zone per net and layer
- **WHEN** `uv run pytest tests/unit/roles/test_copper_plan.py -k zones` resolves the role copper of the bare good buck
- **THEN** `VIN`, `SW`, `VL` and `VOUT` each hold exactly one generated zone on `F.Cu`, KiCad's zone check finds no `zones_intersect`, and the `SW` zone is no wider than its required width plus one pour grid cell

### Requirement: Loose ends joined
A loose end of a role net's own track on a layer where the net gets bands SHALL be joined to the net's planned copper by a band, or, where no band fits, by locked tracks of the loose track's width with ids from the keys `role.join.<net>.<layer>.<n>.<i>`; without a path it MUST give `roles.copper-blocked`.

#### Scenario: Loose ends joined
- **WHEN** `uv run pytest tests/unit/roles/test_copper_plan.py -k loose` plans the bare good buck and the bare good BMS
- **THEN** the buck's switch node has one band `role.switch_node.SW.F.Cu.join0`, and the BMS board holds the plan's locked join tracks

### Requirement: Switch node kept from sensitive copper
A `switch_node` net with victim nets of c0222 (Kelvin, other switches' gates, sensitive signals) SHALL get a clearance rule at `switching_distance_nm` to each of them, between two nets: `role.sw.<net>` for one victim, `role.sw.<net>.<victim>` for each of several; without victims it gets no rule. Its spine MUST avoid victim copper on an adjacent layer grown by that distance. The ground plane MUST NOT be cut for it.

#### Scenario: Sense pair not under the switch node
- **GIVEN** the bare bad half-bridge, whose sense pair runs on `In1.Cu`
- **WHEN** `uv run pytest tests/unit/roles/test_copper_plan.py -k victims` resolves its role copper
- **THEN** the switch-node zone does not overlap the sense pair grown by 1 mm, its plan holds no `role.sw.*` rule (the sense lines are branches of the switch node's own nets), and the bare good buck with a sensitive `ISNS` net gets `role.sw.SW` to `ISNS` at 1 mm

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

### Requirement: User copper respected
A role net SHALL get no role copper where the user drew it: a net whose terminals are all through-hole and which holds the user's zone on one of its default layers gets none (`user-copper`), a ground net with zones of the user gets no plane unless `ground_layers` is given, and a high-voltage net without role copper gets no `role.hv.*` rule or barrier.

#### Scenario: Copper on an unchanged good variant
- **GIVEN** each `good` reference variant built for KiCad, with every inferred role confirmed
- **WHEN** `uv run pytest tests/unit/roles/test_copper_reference.py -k good_variant` runs `fenolite copper --dry-run` on it
- **THEN** the plan changes nothing, and every role net is skipped as `user-copper` or `current-missing`

### Requirement: Corridors only against the run's pours
A provisional corridor SHALL NOT be written on a layer where the run pours nothing, and a corridor over a zone of the user of another net MUST be left out with `roles.corridor-blocked`: a no-pour corridor would cut the user's pour.

#### Scenario: No corridor on an unchanged good variant
- **WHEN** the same test runs `fenolite copper --dry-run` on each unchanged `good` variant
- **THEN** `result.corridors` is empty

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
The KiCad builds of the six role-copper scripts, refilled by `kicad-cli`, SHALL show no DRC violation type with more entries than the same board without role copper, unconnected items aside (and, on KiCad 9, which refills no zone, the dangling vias and tracks of the unfilled zones), and are `KICAD-VERIFIED` for that only. The planner stays `INFERRED`, citing `H-G-ROLE-COPPER-*`.

#### Scenario: DRC on the bench
- **WHEN** `uv run pytest tests/kicad/roles/test_copper_drc.py` builds, refills and checks each script on KiCad 10
- **THEN** no violation type has more entries than on the board without role copper
