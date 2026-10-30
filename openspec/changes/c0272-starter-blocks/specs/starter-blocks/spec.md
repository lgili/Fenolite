## ADDED Requirements

### Requirement: Starter block library
`fenolite.blocks` SHALL export the blocks `voltage_divider`, `rc_lowpass`, `led_indicator`, `i2c_pullups` and `protected_input`, with the ids `Fenolite:<name>`, version `1.0.0`, licence Apache-2.0 and evidence `INFERRED`, each with c0268's parameter metadata, port documentation and sources, and each with the usage example, tests, golden file and layout of c0270 and c0271.

#### Scenario: The five blocks are listed
- **WHEN** `uv run pytest tests/unit/blocks/test_starter.py -k listed` runs `fenolite blocks list --json`
- **THEN** the five ids are listed at version `1.0.0`, each `show` gives its ports, parameters with units and defaults, sources, `usage`, `tests`, `golden` and `layout`

#### Scenario: The starter library passes its own tests
- **WHEN** `uv run fenolite blocks test --json` runs on the installed package
- **THEN** the exit code is 0 and every usage, golden and test of the five blocks passes

### Requirement: Voltage divider block
`Fenolite:voltage_divider` SHALL have the ports `HI` (Rail, in), `OUT` (Net, out) and `LO` (Ground, in), the parameters `vin`, `vout`, `current` and `series`, choose its resistors with c0254's `voltage_divider`, and expect the output `voltage_of(HI) / (1 + value_of(top) / value_of(bot))` within `vout` and each resistor's power rating at least `voltage_of(HI)²` over its value.

#### Scenario: Default divider
- **GIVEN** `instantiate(voltage_divider, stimulus=stimulus(HI=volt("12").pct(2), LO=volt(0)))`
- **WHEN** `uv run pytest src/fenolite/blocks/tests/test_voltage_divider.py -k default` runs
- **THEN** the resistors are 137 kΩ and 52.3 kΩ, the output row's value is 3.202246 V to 3.430848 V (outward to 1 µV) and passes, and the top power value is at most 1.104606 mW

#### Scenario: Unreachable output
- **WHEN** the block is instantiated with `vin=volt("12").pct(10)`
- **THEN** `findings("gen.unachievable")` holds one finding naming the pair 107 kΩ over 40.2 kΩ and its range 2.906770 V to 3.657539 V

#### Scenario: Two dividers, no collision
- **WHEN** a design uses the block as `sense_a` and `sense_b` with different `vout`
- **THEN** the build exits 0, the four resistors have distinct refs, and the local nets are `sense_a/OUT` and `sense_b/OUT` unless named from outside

### Requirement: RC low-pass block
`Fenolite:rc_lowpass` SHALL have the ports `IN`, `OUT` (Net) and `GND` (Ground), the parameters `corner`, `c`, `c_tolerance`, `series` and `voltage`, choose its parts with c0254's `rc_lowpass`, and expect `1 / (2 · π · value_of(r) · value_of(c))` within `corner`, with π the rational enclosure `[3.14159265358, 3.14159265359]`, and the capacitor's voltage rating at least `voltage`.

#### Scenario: Default filter
- **WHEN** `uv run pytest src/fenolite/blocks/tests/test_rc_lowpass.py -k default` instantiates the block with its defaults
- **THEN** `r` is 1.58 kΩ and the cut-off row's value is 906.669 Hz to 1130.538 Hz (outward to 1 mHz) and passes

#### Scenario: A window narrower than the capacitor
- **WHEN** the block is instantiated with `corner=hertz("1k").pct(10)`
- **THEN** `findings("gen.unachievable")` holds one finding

### Requirement: LED indicator block
`Fenolite:led_indicator` SHALL have the ports `HI` and `LO`, a resistor `r` and an LED `led` from `HI` to `LO`, its LED's cathode on `LO`, and expect, with `i = (drive − vf) / value_of(r)`, `i` within `current`, the LED's current rating (or `led_current_max`) at least `i`, `source_limit` at least `i` when given, and the resistor's power rating at least `(drive − vf)²` over its value.

#### Scenario: Default indicator
- **WHEN** `uv run pytest src/fenolite/blocks/tests/test_led_indicator.py -k default` instantiates the block with `vf=volt("2").pct(10)` and `led_current_max=amp("20m")`
- **THEN** `r` is 649 Ω, the current row's value is 1.426413 mA to 2.591400 mA and passes, and the power value is at most 4.314680 mW

#### Scenario: A pin that cannot drive it
- **WHEN** the same block is instantiated with `source_limit=amp("1m")`
- **THEN** the source row fails and `findings("circuit.expect-failed")` holds one finding naming `dut/r`

### Requirement: LED data stated
`led_indicator` SHALL take the LED's forward voltage and current rating from the c0248 device record named by `led`, or from `vf` and `led_current_max`; with neither, `design.use` MUST raise `DslError` asking for the forward voltage. Fenolite MUST NOT ship an LED forward voltage or current default.

#### Scenario: No forward voltage
- **WHEN** `uv run pytest src/fenolite/blocks/tests/test_led_indicator.py -k stated` uses the block with neither `led` nor `vf`
- **THEN** `DslError` is raised naming `vf` and `led`, and the build of a script doing so exits 3 with `FEN-3004`

### Requirement: I2C pull-up block
`Fenolite:i2c_pullups` SHALL have the ports `BUS` (I2C, its `reference` set to `RAIL`) and `RAIL` (Rail, in), the parameters `mode`, `vdd`, `bus_capacitance` and `series`, choose one value for both lines with c0254's `i2c_pull_ups`, and expect each resistor at least `(voltage_of(RAIL) − vol) / iol` and at most `rp_max`, read from c0254's mode constants (UM10204, cited by id).

#### Scenario: Value inside the window for every mode
- **WHEN** `uv run pytest src/fenolite/blocks/tests/test_i2c_pullups.py -k window` instantiates the block for each mode and each bound of `bus_capacitance`
- **THEN** each chosen value lies within the window of the generator's `gen.achieved` finding, and both rows of each resistor pass

#### Scenario: Two buses
- **WHEN** a design uses the block twice on two different buses
- **THEN** the build exits 0 and no `circuit.pullup-parallel` is reported

### Requirement: Parallel pull-ups
The stage `circuit.rules` SHALL give `circuit.pullup-parallel` (warning) for each line of an `i2c` bus joined to a rail through more than one resistor, naming the line, the resistors and the range of their parallel resistance. The code MUST be explained by `fenolite explain` and listed in `docs/cli-contract.md`.

#### Scenario: Two pull-up sets on one bus
- **WHEN** `uv run pytest tests/unit/checks/circuit/test_pullup_parallel.py` checks a design that uses `i2c_pullups` twice on one bus
- **THEN** two `circuit.pullup-parallel` findings are reported, one for `sda` and one for `scl`, each naming two resistors

### Requirement: Protected input block
`Fenolite:protected_input` SHALL have the ports `EXT`, `INT` (Net) and `GND` (Ground), a protection device `tvs` from `EXT` to `GND` and a series resistor `r` from `EXT` to `INT`, and expect the protection's voltage rating at least `signal`, and either `clamp` at most `abs_max` or, when `inject_max` and `hold` are given, `inject_max` at least `(clamp − hold) / value_of(r)`.

#### Scenario: Injected current limited by the series resistor
- **GIVEN** `clamp=volt("9.2").max()`, `hold=volt("3.6")` and `inject_max=amp("5m")`
- **WHEN** `uv run pytest src/fenolite/blocks/tests/test_protected_input.py -k inject` instantiates it with `r_series=ohm("1k")` and with `ohm("1.5k")`
- **THEN** the first row's value reaches 5.656566 mA and fails, the second reaches 3.771044 mA and passes

#### Scenario: Clamp above the downstream maximum
- **WHEN** the block is instantiated with `abs_max=volt("3.6")` and no `inject_max`
- **THEN** the clamp row fails and `findings("circuit.expect-failed")` holds one finding

### Requirement: Starter block layouts
Each starter block SHALL ship `layouts/<name>.toml` captured by `fenolite blocks capture` from its usage board, used by its body with `copper=True`. The LED layout MUST put the LED's cathode pad on `LO` with its polarity mark on that side; the protection layout MUST put `tvs` nearest the `EXT` edge with at most 1.5 mm of copper from its ground pad to the ground via.

#### Scenario: Layout properties
- **WHEN** `uv run pytest tests/unit/blocks/test_starter_layouts.py` reads the five layouts
- **THEN** each digest equals that of its block's default instance, the LED and protection properties hold, and recapturing each usage board gives the same bytes

### Requirement: Starter block sources
Every relation of a starter block SHALL cite a source registered in `docs/evidence/sources.md` with its licence and what is used; the I2C-bus specification MUST be cited by document id only, and no vendor reference design, application note content or table MUST be used.

#### Scenario: Sources registered
- **WHEN** `uv run pytest tests/unit/test_provenance.py tests/unit/blocks/test_starter.py -k sources` runs
- **THEN** every source id of the five records is registered, and the I2C block cites `UM10204` through c0254's registered source

### Requirement: Generated block pages
`docs/blocks/index.md` and one page per starter block SHALL be generated from the records by `tools/gen_block_docs.py`, with ports, parameters, expectations, sources and the usage example; `tools/gen_block_docs.py --check` MUST fail when a page differs from its record.

#### Scenario: Pages up to date
- **WHEN** `uv run pytest tests/unit/blocks/test_block_docs.py` runs
- **THEN** the generated pages equal the committed ones, and a changed parameter `doc` makes the check fail
