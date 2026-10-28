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

### Requirement: Copper path between pads
`fenolite.roles.measure` SHALL find the copper path between two pads of a net: the shortest by plan length over the net's tracks, arc chords, vias and fill regions, with paths inside a fill taken over its ring's visibility graph, and ties broken by item id. When no path exists the measure MUST be `null` with `roles.loop-open` (warning).

#### Scenario: A path through a pour
- **GIVEN** an authored board where two pads 20 mm apart lie in one rectangular fill
- **WHEN** `uv run pytest tests/unit/roles/test_path.py -k fill` measures their path
- **THEN** the path is the straight 20 mm segment, and with an authored notch across it the path runs around the notch's corner

### Requirement: Loop area
A loop's `area_nm2` SHALL be `enclosed_nm2` (the non-zero winding area of the closed path) plus `stacked_nm2` (overlap length times layer distance from the stack-up). `bound_nm2` MUST be the enclosed area through the pad centres in loop order, and `ratio_permille` MUST be `area * 1000 // bound` when the bound is at least `loop_bound_floor_nm2`. Areas MUST be integers.

#### Scenario: Authored loops
- **WHEN** `uv run pytest tests/unit/roles/test_loop_area.py` measures a 10 mm × 5 mm rectangle, a figure-eight of two 4 mm² lobes, and a loop stacked over 20 mm at 0.2 mm
- **THEN** the areas are 50 mm², 8 mm² and 4 mm² plus the plan area, as integers of nm²

### Requirement: Hot and gate loop checks
Each `HotLoop` and `GateLoop` SHALL be measured. A loop over the user's `loop_max` or `gate_max` MUST be `roles.loop-area` or `roles.gate-loop`, and so MUST a ratio over `loop_ratio_max` or `gate_ratio_max`. A gate return that leaves from power copper instead of the `source` pad MUST be `roles.gate-return-shared`.

#### Scenario: The bad buck's hot loop
- **GIVEN** the `bad` variant of `buck_shunt`, whose input capacitor stands 15 mm from the switches
- **WHEN** `uv run pytest tests/unit/roles/test_reference_boards.py -k buck_loop` runs the check
- **THEN** one `roles.loop-area` names the loop, with an area within 10 % of 180 mm² and a ratio over 2000

### Requirement: Kelvin attachment
For each sense pad of a `KelvinPair`, the sense branch SHALL be the copper reached from the receiver without crossing the pad or entering power copper. Each attachment offset `t` along the axis to the other sense pad MUST be reported. `t < 0` MUST be `roles.kelvin-outer`. A branch that reaches power copper or a force pad MUST be `roles.kelvin-shared`.

#### Scenario: Sense lines of the bad buck
- **GIVEN** the `bad` variant of `buck_shunt`, where one sense line leaves the outer end of `R12`'s pad and the other leaves the pour
- **WHEN** `uv run pytest tests/unit/roles/test_kelvin.py -k reference` runs the check
- **THEN** one `roles.kelvin-outer` names `R12-1` with `t < 0`, and one `roles.kelvin-shared` names `R12-2` and the zone

### Requirement: Kelvin pair and switching distance
A `KelvinPair` SHALL be measured as a loop through its element and receiver pads, and a ratio over `pair_ratio_max` MUST be `roles.kelvin-apart` with the largest gap. Copper of a `kelvin` branch, of a `sensitive` `signal` or of another switch's gate loop closer than `switching_distance_nm` to `switch_node` copper on its layer, or over it on an adjacent layer, MUST be `roles.near-switching`.

#### Scenario: A sense pair over the switch node
- **GIVEN** the `bad` variant of `half_bridge`, whose sense pair crosses the switch node on the adjacent layer
- **WHEN** the check runs
- **THEN** one `roles.near-switching` names the pair, the switch node and the overlap length, and the `good` variant has none

### Requirement: Current capacity of role copper
For a role with `milliamps`, each track and arc on its path SHALL be judged against the width the method gives: `width_per_amp_nm` times the current, or the S-0269 fit at the user's rise and the stack-up's thickness. The narrowest section of its pours and the parallel vias at each layer change MUST be judged too. Findings: `roles.width-current`, `roles.section-current`, `roles.via-current`.

#### Scenario: A thin track on a 2 A net
- **GIVEN** an authored board whose 2 A `power` net runs through a 0.3 mm track and one via between two pours
- **WHEN** `uv run pytest tests/unit/roles/test_current.py` runs the check without and with `--temp-rise 10`
- **THEN** both runs give one `roles.width-current` naming 0.3 mm and the method, and the first gives one `roles.via-current` asking for 10 vias

### Requirement: Returns and high voltage
For `gate` and `sensitive` `signal` nets, each `split` span of `analyze_returns` against the `ground` nets SHALL be `roles.return-gap`. For each `high_voltage` net, and each net judged as one, distances SHALL come from `analysis` against the user's rows, keeping their `analysis.*` codes. A net without a row MUST be `roles.limit-missing`.

#### Scenario: A high-voltage bus without a requirement
- **GIVEN** the `good` variant of `half_bridge` with its distance rows removed
- **WHEN** the check runs
- **THEN** one `roles.limit-missing` names the bus, and no `analysis.clearance-below` is reported

### Requirement: Role issue codes
`fenolite.roles.codes.ISSUE_CODES` SHALL be the closed table of the design's eighteen `roles.*` codes with their severities, and an issue outside it MUST raise `ValueError`. `fenolite explain` MUST explain each code. No `FEN-` code is added.

#### Scenario: Codes in the table
- **WHEN** `uv run pytest tests/unit/roles/test_codes.py tests/unit/cli/test_explain_cmd.py -k roles` runs
- **THEN** every code has its severities and an explanation, and `roles.kelvin-outer` allows `warning` and `error`

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
Every reply of `fenolite roles` and of the stage SHALL carry the evidence level `INFERRED` with the hypotheses of the design that its checks rely on. The limit of each finding MUST name its source id or hypothesis.

#### Scenario: Evidence of a check
- **WHEN** `fenolite roles <bad buck> --check --json` runs
- **THEN** `evidence.level` is `INFERRED`, `evidence.hypotheses` holds `H-G-ROLE-LOOP-RATIO`, and the `roles.width-current` issue's message names `S-0851`
