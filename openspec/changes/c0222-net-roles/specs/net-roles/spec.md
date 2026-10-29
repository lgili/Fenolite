## ADDED Requirements

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
`fenolite.roles.codes.ISSUE_CODES` SHALL be the closed table of the design's seventeen `roles.*` codes with their severities, and an issue outside it MUST raise `ValueError`. `fenolite explain` MUST explain each code. No `FEN-` code is added.

#### Scenario: Codes in the table
- **WHEN** `uv run pytest tests/unit/roles/test_codes.py tests/unit/cli/test_explain_cmd.py -k roles` runs
- **THEN** every code has its severities and an explanation, `roles.kelvin-outer` allows `warning` and `error`, and `roles.input-missing` is not in the table
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