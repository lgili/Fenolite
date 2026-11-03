## ADDED Requirements

### Requirement: Contract judge on the model
`fenolite.checks.circuit` SHALL judge the electrical contracts of a design from its `.fenolite/` model and the device records (`DeviceDef`) and part classes that the command passes. The model supplies the circuit, `Component.value_range`, the rails, the stored net roles and `RuleSet.contracts`. The judge MUST run no tool, MUST read no board, MUST NOT import `fenolite.catalog`, `fenolite.roles` or `fenolite.analysis`, and MUST give the same issues and table, byte for byte, for the same inputs.

#### Scenario: Deterministic and tool-free
- **GIVEN** the `bad` variant of `examples/circuit/sensor` built in `tmp_path`, and `subprocess.run` patched to raise
- **WHEN** `uv run pytest tests/unit/checks/circuit/test_stage.py -k deterministic` judges its model twice with the same device records and classes
- **THEN** both judgements give the same canonical JSON, and no process is started

#### Scenario: Layering holds
- **WHEN** `uv run pytest tests/unit/test_import_graph.py` runs
- **THEN** no module of `src/fenolite/checks/circuit/` imports `fenolite.catalog`, `fenolite.roles` or `fenolite.analysis`

### Requirement: Applied values from stated sources
Each net SHALL get a voltage bound and a current bound only from stated sources, in this order: a rig element; a c0252 rail (its voltage, the upper sum of its loads); a declared or confirmed `NetRole` (`working_mv` read as `-v` to `+v`, `milliamps`); for the current, then a `[[current]]` row and then `--current` when the command has them; and a c0252 `Ground` or `ground` role (0 V). An unconfirmed inferred role MUST give no bound, and Fenolite MUST NOT infer a value.

#### Scenario: A rig bounds the input
- **GIVEN** a design whose rig holds `supply(v12, gnd, voltage=volt("12").pct(10), current=amp(3), name="bench")`
- **WHEN** `uv run pytest tests/unit/checks/circuit/test_values.py -k rig` resolves the bounds
- **THEN** the net `V12` has the voltage 10.8 V to 13.2 V and the current bound 3 A, each with source `user` and basis `rig bench`, and `GND` has 0 V

#### Scenario: Unconfirmed roles give nothing
- **GIVEN** a built design with device parts and no rig, no rail and only inferred roles
- **WHEN** the bounds are resolved
- **THEN** no net has a voltage or current bound, and every rating row has status `unknown`

#### Scenario: Currents in the order of roles
- **GIVEN** a net `SW` whose confirmed role states no `milliamps`, a `[[current]]` row of 0.8 A for `SW` and `--current SW=1.1`
- **WHEN** `uv run pytest tests/unit/checks/circuit/test_values.py -k current_order` resolves the bounds as `fenolite roles --check` does
- **THEN** `SW` has the current bound 0.8 A with basis `requirements.toml`, the role row of `SW` uses the same 0.8 A, and without the `[[current]]` row both use 1.1 A with basis `--current`

### Requirement: Conflicting sources
When stated sources of different kinds bound one net with ranges that do not overlap, the first source in the order SHALL be used, and `circuit.value-conflict` (warning) MUST name both. Rail values that do not intersect MUST remain c0252's `circuit.rail-voltage`.

#### Scenario: Two sources disagree
- **GIVEN** a net that is a c0252 rail of 3.3 V ± 3 % and a declared role with `working_mv` 1800 on the same net
- **WHEN** `uv run pytest tests/unit/checks/circuit/test_values.py -k conflict` resolves the bounds
- **THEN** the rail's range is used and one `circuit.value-conflict` warning names the rail and the role

### Requirement: Part classes for contracts
The judge SHALL take each part's class from the `classes` mapping that the command computes with `fenolite.roles.classify`, the one classifier, with the user's `PartClass` entries. Without the mapping, a part SHALL take its user's `PartClass` from the model, and a part without one has no class: its class-specific rows MUST be `unknown` with the basis `no class`. No module of `checks` MAY hold a reference-prefix table.

#### Scenario: A stated class wins
- **GIVEN** a device part `L1` with `design.part_class(l1, "resistor")`
- **WHEN** `uv run pytest tests/unit/checks/circuit/test_values.py -k classes` runs the command's classification and the judge
- **THEN** its class is `resistor`, and without the call it is `inductor`, as `roles.classify` gives

#### Scenario: One prefix table
- **WHEN** `uv run pytest tests/unit/checks/circuit/test_values.py -k one_table` scans `src/fenolite/checks/`
- **THEN** no module defines a mapping from reference prefixes to classes, and the judge called without `classes` gives `unknown` rows with basis `no class` for the series and power checks

### Requirement: Absolute and operating limits
The judge SHALL read each device limit as `abs_max` or `operating` (c0274). An `abs_max` limit MUST be judged on the worst case, through the derating policy, as `circuit.rating-*`. An `operating` limit MUST be judged without derating or margin: the applied range MUST lie within it, else `circuit.operating-range` (error). An `operating` pin voltage already judged by a c0252 device port's `voltage` MUST NOT give a second row.

#### Scenario: A derating never loosens a minimum
- **GIVEN** a regulator whose `VIN` has `operating` 2.7 V to 6 V and `abs_max` up to 6.5 V, on a rail of 2.5 V to 2.6 V, and `design.derating(pin_voltage=ratio(50))`
- **WHEN** `uv run pytest tests/unit/checks/circuit/test_ratings.py -k operating` runs the judge
- **THEN** one `circuit.operating-range` error names `VIN`, 2.5 V and 2.7 V, and the `abs_max` row passes against 3.25 V with source `policy`

### Requirement: Voltage ratings
For each device part, the judge SHALL judge on the worst case of the stated bounds: the device `voltage` rating of a two-pin part as `max(a.max - b.min, b.max - a.min)` over its two nets, and each pin `voltage` as the voltage of the pin's net from the net of the device's `ground` function (from the design's ground when the device has none), at its `min` and `max`. A worst case beyond the limit MUST be `circuit.rating-voltage`. An unbounded net MUST make the row `unknown`.

#### Scenario: Input capacitor without a policy
- **GIVEN** the rig `bench` above and a capacitor rated `voltage = { abs_max = { max = "10V" } }` between `V12` and `GND`, with no derating rule
- **WHEN** `uv run pytest tests/unit/checks/circuit/test_ratings.py -k capacitor` runs the judge
- **THEN** one `circuit.rating-voltage` error names the capacitor, the value 13.2 V and the limit 10 V with source `device`

#### Scenario: Pin rating of a regulator
- **GIVEN** a device whose pin `VIN` has `abs_max` up to 6 V, on `V12` of the rig `bench`, and whose `GND` function is on `GND`
- **WHEN** the judge runs
- **THEN** one `circuit.rating-voltage` error names the part, the function `VIN`, 13.2 V and 6 V

#### Scenario: Drain to source
- **GIVEN** a transistor device with `ground = "S"` and a pin `D` with `abs_max` up to 40 V, its `D` on a rig supply of 48 V ± 5 % and its `S` on `GND`
- **WHEN** the judge runs
- **THEN** one `circuit.rating-voltage` error names the function `D` with the value 50.4 V and the limit 40 V

### Requirement: Pin-pair limits
Each `[[limits]]` row of a device record (c0274) SHALL be judged as the voltage of the net of its first function minus that of its second, worst case at both `min` and `max`: an `abs_max` limit as `circuit.rating-voltage` with the derating key `pin_voltage`, an `operating` limit as `circuit.operating-range`. The row id MUST be `circuit.rating-voltage:<ref>:<first>-<second>`. A row whose second net has no bound MUST be `unknown`.

#### Scenario: Bootstrap to switch node
- **GIVEN** a regulator `U1` with `[[limits]] between = ["BST", "SW"]`, `voltage = { abs_max = { max = "6V" } }`, `BST` on a net declared at 17 V to 19 V and `SW` on a net declared at 12 V to 13.2 V
- **WHEN** `uv run pytest tests/unit/checks/circuit/test_ratings.py -k pair` runs the judge
- **THEN** one `circuit.rating-voltage` error has the id `circuit.rating-voltage:U1:BST-SW`, the value 7 V and the limit 6 V; with `SW` unbounded the row is `unknown`

### Requirement: Device current by class
A device `current` limit SHALL be judged by the part's role: for a part that owns an `out` power port (c0252), against the upper load sum of that port's rail with c0252's hiding; for a part of class `inductor` or `shunt`, against the smaller of its two nets' current bounds, only when both exist; for any other class it MUST NOT be judged. A pin `current` SHALL be judged only when the pin is the part's only pin on its net. A bound beyond the limit MUST be `circuit.rating-current`.

#### Scenario: Inductor on a busier rail
- **GIVEN** an inductor rated `current = { abs_max = { max = "1A" } }` between the net `SW`, declared with `current=amp("1.5")`, and the rail `3V3`, whose c0252 loads sum to at most 1.2 A
- **WHEN** the judge runs
- **THEN** one `circuit.rating-current` error names the inductor with the value 1.2 A and the limit 1 A

#### Scenario: A regulator judged by its output port
- **GIVEN** a regulator device with `current = { abs_max = { max = "2A" } }` and the `out` power port `vout` on the rail `3V3`, whose loads sum to at most 2.4 A
- **WHEN** the judge runs
- **THEN** one `circuit.rating-current` error names the regulator, `vout`, 2.4 A and 2 A

#### Scenario: A pull-up is not judged by current
- **GIVEN** a resistor device with a `current` rating between the rail `3V3` (loads 1.2 A) and the net `SDA` with no bound
- **WHEN** the judge runs
- **THEN** no `circuit.rating-current` is reported and the resistor has no current row, because a resistor is not a series class and owns no `out` port

### Requirement: Resistor power
The device `power` rating of a part of class `resistor` or `shunt` SHALL be judged against `V_across.max² / R.min` when both nets have a voltage bound, else, for a `shunt` with a current bound, against `I.max² × R.max`, where `R` is `Component.value_range` (c0246) and the products are c0274's. A part with no `value_range` MUST make the row `unknown`. A worst case beyond the limit MUST be `circuit.rating-power`.

#### Scenario: A bleeder across the input
- **GIVEN** a resistor of 1 kΩ ± 1 % rated `power = { abs_max = { max = "0.1W" } }` between `V12` of the rig `bench` and `GND`
- **WHEN** the judge runs
- **THEN** one `circuit.rating-power` error names the resistor with the value 0.176 W, computed exactly, and the limit 0.1 W

### Requirement: Temperature ratings
When the design states an ambient range (`design.operating(ambient=...)`, a kelvin range), the ambient range SHALL lie within each device `abs_max` temperature range narrowed at each end by the policy's `temperature_margin`, else `circuit.rating-temperature`, and within each `operating` temperature range with no margin, else `circuit.operating-range`. Without an ambient range, temperature rows MUST be `unknown`.

#### Scenario: A commercial part in a cold box
- **GIVEN** `design.operating(ambient=between(celsius(-20), celsius(70)))` and a device whose `temperature` has `operating = { min = "0degC", max = "70degC" }`
- **WHEN** the judge runs
- **THEN** one `circuit.operating-range` error names the part, the ambient range and the operating range, both printed in degrees Celsius

### Requirement: Derating policy
`design.derating(...)` SHALL set per-mille limits on `abs_max` ratings by the closed key table `DERATING_KEYS`, optionally scoped by `parts=`. A value MUST be `ratio(p)`, "at most p % of the rating"; c0246's `pct()` MUST raise `DslError` with the hint `ratio()`. The most specific rule MUST win: part scope, then class key, then generic key. A ratio MUST be above 0 and at most 100 %. A policy limit MUST have source `policy` and a basis naming the key, the ratio, the rating and the device.

#### Scenario: The policy tightens the input capacitor
- **GIVEN** the rig `bench`, a capacitor rated `abs_max` 16 V between `V12` and `GND`, and `design.derating(capacitor_voltage=ratio(50))`
- **WHEN** `uv run pytest tests/unit/checks/circuit/test_policy.py -k tightens` runs the judge
- **THEN** one `circuit.rating-voltage` error has the value 13.2 V and the limit 8 V with source `policy` and a basis naming `capacitor_voltage`, 500‰ and 16 V

#### Scenario: A part scope wins
- **GIVEN** the same design with also `design.derating(capacitor_voltage=ratio(90), parts=select.ref("C1"))`, the capacitor being `C1`
- **WHEN** the judge runs
- **THEN** the limit is 14.4 V and the row passes

#### Scenario: Bad ratios
- **WHEN** a script calls `design.derating(capacitor_voltage=ratio(120))`, `design.derating(capacitor_voltage=pct(50))` or `design.derating(gate_charge=ratio(50))`
- **THEN** each raises `DslError`; the second names `ratio(50)` as the hint, and the third lists the keys of `DERATING_KEYS`

### Requirement: Ratings without a policy
A rating that no derating rule covers SHALL be judged at 100 %: its limit is the rating, with source `device`. One `circuit.policy-missing` (info) per judgement MUST name the ratings judged that way.

#### Scenario: No policy, no derating
- **GIVEN** the rig `bench` and a capacitor rated `abs_max` 16 V between `V12` and `GND`, with no derating rule
- **WHEN** `uv run pytest tests/unit/checks/circuit/test_policy.py -k missing` runs the judge
- **THEN** the capacitor's row passes with the limit 16 V and source `device`, and one `circuit.policy-missing` info names it

### Requirement: No shipped derating values
Fenolite SHALL ship no derating rule, preset or default ratio. Every derating limit MUST come from a `design.derating(...)` call of the user's script. A later preset MUST NOT be added without an `S-` source in `docs/evidence/sources.md` and an evidence label for each value.

#### Scenario: No defaults in the code
- **WHEN** `uv run pytest tests/unit/checks/circuit/test_policy.py -k no_defaults` builds a design with ratings and no `derating` call and inspects `fenolite.model.rules` and `fenolite.checks.circuit`
- **THEN** every rating row's limit has source `device`, and neither module defines a per-mille constant for a key of `DERATING_KEYS`

### Requirement: Device records of the judgement
Without a device record for a component's `fenolite.device`, its rating rows SHALL be `unknown`, counted by `circuit.rating-missing` with the parts that have no rating for a check that applies. When a record's digest differs from the component's `fenolite.device.sha256`, the record MUST still be used, and `circuit.device-changed` (warning) MUST name both digests.

#### Scenario: A device edited after the build
- **GIVEN** the `good` variant built in `tmp_path`, then its input capacitor's project device record edited to a new digest
- **WHEN** `uv run pytest tests/unit/checks/circuit/test_stage.py -k device_changed` runs `fenolite check <dir> --stages circuit.rules --json`
- **THEN** one `circuit.device-changed` warning names the part and both digests, and its row uses the edited rating

### Requirement: Expectation judgement
Each `Expectation` SHALL be evaluated on the model and the device records by worst-case range arithmetic and judged pass, fail or unsure. `within(a, b)` passes when `a` lies inside `b` and fails when they do not overlap. `at_least(a, b)` passes when `a.min >= b.max` and fails when `a.max < b.min`, and `at_most` is its mirror. A fail MUST be `circuit.expect-failed` (error), and an unsure result `circuit.expect-unsure` (warning), each naming the id, the reason and both ranges.

#### Scenario: The divider of a buck
- **GIVEN** a block instance `buck1` that records `b.expect(within(vref * (1 + value_of(top) / value_of(bot)), vout), "VOUT set by the divider")` with `vref` 0.6 V ± 1 %, `top` 45.3 kΩ ± 1 %, `bot` 10 kΩ ± 1 % and `vout` 3.3 V ± 3 %
- **WHEN** `uv run pytest tests/unit/checks/circuit/test_expect.py -k divider` runs the judge
- **THEN** one `circuit.expect-unsure` warning names `buck1/expect#1`, the reason, the value from 3.2315 V to 3.4066 V and the limit from 3.201 V to 3.399 V; with `vref` ± 0.5 % the expectation passes

#### Scenario: Judged again after an edit
- **GIVEN** the same design whose `value_range` of `top` is 49.9 kΩ ± 1 % after a manual edit kept by c0250
- **WHEN** the judge runs
- **THEN** one `circuit.expect-failed` error names `buck1/expect#1` with the value from 3.4994 V to 3.6910 V

### Requirement: Unresolved expectations
An expectation with a handle that the judge cannot resolve or bound SHALL be `circuit.expect-unknown` (warning), naming the handle. An unresolved or failing expectation MUST NOT stop the judgement of the others.

#### Scenario: A value without a range
- **GIVEN** the divider design and a second expectation, where the model's `top` has the text value `45k3 trimmed` and no `value_range`
- **WHEN** the judge runs
- **THEN** one `circuit.expect-unknown` warning names `buck1/expect#1` and the value of `top`, and the second expectation is judged

### Requirement: Expectations are recorded data
`expect(test, reason)` SHALL record an `Expectation` whose test is `within`, `at_least` or `at_most` over expressions of handles (`value_of`, `rating_of`, `voltage_of`, `current_of`) and c0246 ranges under `+ - * /`. Its id MUST be `<instance path>/expect#<n>` in call order, with the path `design` at the top level. The `__bool__` of a handle, expression or test MUST raise `DslError`, as MUST `expect()` given a `bool`, an empty reason or a reason used twice in one instance.

#### Scenario: No silent branch
- **WHEN** a script evaluates `if rating_of(l1, "current"):`
- **THEN** `DslError` says to use `design.expect(...)`

#### Scenario: An unknown rating key
- **WHEN** a script calls `rating_of(l1, "saturation")` on a device whose ratings are `current` and `temperature`
- **THEN** `DslError` lists `current` and `temperature`

#### Scenario: A literal comparison is refused
- **WHEN** a script calls `design.expect(volt("3.3").pct(3).within(volt("3.3").pct(5)), "rail")`
- **THEN** `DslError` says that `expect` needs `within(a, b)` so that both ranges are recorded

#### Scenario: Ids take the instance path
- **GIVEN** the block `buck` used twice, as `buck1` and `buck2`, each recording one expectation, and one `design.expect(...)` at the top level
- **WHEN** `uv run pytest tests/unit/dsl/test_contracts.py -k ids` converts the design
- **THEN** the ids are `buck1/expect#1`, `buck2/expect#1` and `design/expect#1`

### Requirement: Test rig
`design.rig(*elements)` SHALL record `supply(pos, neg=None, *, voltage, current=None, name=None)` and `sink(net, ret=None, *, current, name=None)` elements in `RuleSet.contracts.rig`. An omitted `neg` or `ret` MUST be the design's one ground, and the build MUST raise `DslError` when there is not exactly one. A rig MUST name only nets that have a pin of a board part, and rig names MUST be unique keys. In c0252's rail checks, a supply MUST count as a source and a sink as a load.

#### Scenario: A rig on a net without parts
- **WHEN** a script calls `design.rig(supply(Net("EXT"), gnd, voltage=volt(5), name="ext"))` and no part pin is on `EXT`
- **THEN** the build raises `DslError` naming `EXT` and the rig `ext`

#### Scenario: A rig supply beside a regulator
- **GIVEN** a rig supply named `ext3` on the rail `3V3`, which the buck block's output port also drives
- **WHEN** `uv run pytest tests/unit/checks/circuit/test_values.py -k rig_source` runs the judge
- **THEN** one `circuit.rail-sources` names the rig `ext3` and the buck's port

### Requirement: Rig corners
Every row and expectation whose value reads a rig supply's voltage SHALL also be evaluated at each corner: the design's supplies each at its minimum or maximum, all combinations, the other inputs kept as ranges. The row MUST list each corner with its status and value, and a failing row's issue MUST name the failing corners. Corners MUST NOT change a verdict. With more than six supplies, corners MUST NOT be evaluated and `summary.corners` MUST say `too-many-supplies`.

#### Scenario: The corners of the bench
- **GIVEN** the rig `bench` (10.8 V to 13.2 V), a capacitor rated `abs_max` 12 V between `V12` and `GND`, and no policy
- **WHEN** `uv run pytest tests/unit/checks/circuit/test_corners.py` runs the judge
- **THEN** the row fails, its `corners` hold `bench=min` passing at 10.8 V and `bench=max` failing at 13.2 V, and the issue names `bench=max`

### Requirement: Rig never reaches outputs
A rig element SHALL NOT be a component, and SHALL NOT appear in the netlist, the schematic, the board, the BOM, the pick-and-place file, any export, ERC, DRC or parity. A build with and without `design.rig(...)` MUST write byte-identical files, except `.fenolite/rules.json`.

#### Scenario: Outputs are unchanged by a rig
- **GIVEN** the `good` variant of `examples/circuit/sensor` and a copy without its `design.rig(...)` call
- **WHEN** `uv run pytest tests/unit/dsl/test_contracts.py -k rig_outputs` builds both with `--seed 1 --timestamp 2026-01-01T00:00:00Z` and exports the BOM and pick-and-place files
- **THEN** every written file but `.fenolite/rules.json` has the same SHA-256 in both builds

### Requirement: Requirement table
`core.requirement_table.RequirementRow` SHALL hold `id`, `check`, `entities`, `subject`, `quantity`, `unit`, `value` and `limit` (each with `range`, `text`, `source`, `basis`; the limit also `evidence` and `kind`), `corners`, `status` (`pass`, `fail`, `unsure`, `unknown`) and `severity`. `range` MUST use c0246's encoding (unit name, `Decimal10` bounds). `source` MUST be `device`, `role`, `policy` or `user`. The stage MUST give one row per judged limit, expectation and c0252 check, by `id`.

#### Scenario: Rows of the bad sensor
- **GIVEN** the `bad` variant of `examples/circuit/sensor` built in `tmp_path`
- **WHEN** `uv run pytest tests/unit/checks/circuit/test_table.py` runs `fenolite check <dir> --stages circuit.rules --json`
- **THEN** `summary.requirements` holds the row `circuit.rating-voltage:C1:voltage` whose value has `range.unit` `volt` and `range.high` `{"m": 132, "e": -1}` (source `user`, basis `rig bench`), whose limit has `range.high` `{"m": 8, "e": 0}` (source `policy`, kind `abs_max`) and status `fail`, its `entities` hold the ids of `C1` and `V12`, and no number in the reply is a JSON float

### Requirement: Contract issue codes
`ISSUE_CODES` SHALL gain the thirteen codes of decision 11: the four `circuit.rating-*` codes, `circuit.operating-range` and `circuit.expect-failed` (error); `circuit.expect-unsure`, `circuit.expect-unknown`, `circuit.value-conflict` and `circuit.device-changed` (warning); `circuit.value-unknown` and `circuit.rating-missing` (info, warning); `circuit.policy-missing` (info). An issue outside the table MUST raise `ValueError`. `fenolite explain` MUST explain each code.

#### Scenario: Codes explained
- **WHEN** `uv run pytest tests/unit/checks/test_codes.py tests/unit/cli/test_explain_cmd.py -k circuit` runs
- **THEN** every new code has its severities and an explanation, and `issue("circuit.expect-unsure", "error", ...)` raises `ValueError`

### Requirement: Contract severities
A `fail` against a device rating, an operating range, the user's derating policy or an expectation SHALL be an `error`. An unsure expectation, an unresolved expectation, a value conflict and a changed device SHALL be warnings. By default the count findings (`circuit.value-unknown`, `circuit.rating-missing`, `circuit.policy-missing`) SHALL be `info`, and an `unknown` row MUST give no issue of its own. The evidence label of a device record MUST NOT change a severity.

#### Scenario: Unknown rows stay quiet by default
- **GIVEN** a design with ten device parts with ratings and no rig, rail or role voltage, and no `design.contracts(...)` call
- **WHEN** the judge runs
- **THEN** its only issues are one `circuit.value-unknown` info giving the count of unknown rows and one `circuit.policy-missing` info

### Requirement: Strictness of unknown rows
`design.contracts(unknown=...)` SHALL take `info` (the default) or `warning`, stored in `RuleSet.contracts`. With `warning`, each `unknown` row MUST give one `circuit.value-unknown` warning naming the row and its missing input, and each part without a needed rating one `circuit.rating-missing` warning. Another value MUST raise `DslError`. The default MUST stay `info` until a change states the test that proves every shipped device carries its ratings.

#### Scenario: A design that states nothing does not pass quietly
- **GIVEN** the design of "Unknown rows stay quiet by default" with `design.contracts(unknown="warning")`
- **WHEN** the judge runs
- **THEN** it gives one `circuit.value-unknown` warning per unknown row, each naming the missing voltage or current, and `design.contracts(unknown="error")` raises `DslError` listing `info` and `warning`

### Requirement: Contracts in the build
`fenolite build` SHALL report the contract findings through c0252's build hook (`circuit_issues` on the model it builds, with the device records and classes it resolved), under the same rule as c0252's `circuit.*` findings, so the build and `fenolite check` give the same `circuit.*` codes on the same model.

#### Scenario: Build and check agree
- **GIVEN** the `bad` variant of `examples/circuit/sensor`
- **WHEN** `uv run pytest tests/unit/cli/test_build_cmd.py -k circuit` runs `fenolite build examples/circuit/sensor/bad.py --out <tmp> --dry-run --json`
- **THEN** the build's issues hold the same four contract codes, at the same severities, as the stage `circuit.rules` gives on the same model, and the exit code is the one c0252's build rule gives for error findings

### Requirement: Contract evidence
The stage SHALL carry the evidence level `INFERRED` with the hypothesis `H-G-CIRCUIT-EXAMPLE`, combined with the evidence of every device record whose rating it judged, the lowest label winning. Each row's `limit.evidence` MUST be the label of the device record, or `INFERRED` for the user's numbers.

#### Scenario: An unverified device lowers the stage evidence
- **GIVEN** the `bad` variant, whose capacitor device is `UNVERIFIED`
- **WHEN** the stage runs
- **THEN** the stage's `evidence.level` is `UNVERIFIED`, and the capacitor's row has `limit.evidence` `UNVERIFIED`

### Requirement: Contract reference example
`examples/circuit/sensor/` SHALL hold `good.py`, `bad.py` and `requirements.toml`, authored for Fenolite with round illustrative values and marked as such. The `good` variant MUST give no contract finding above `info`. The `bad` variant MUST give exactly `circuit.rating-voltage` (input capacitor, policy), `circuit.rating-current` (inductor), `circuit.expect-unsure` (divider) and `circuit.rating-power` (bleeder). `requirements.toml` MUST use unit keys only.

#### Scenario: Good and bad sensors
- **WHEN** `uv run pytest tests/unit/checks/circuit/test_example.py` builds and checks both variants
- **THEN** the `good` variant has no warning or error of the stage, and the `bad` variant has exactly the four designed findings with their values
