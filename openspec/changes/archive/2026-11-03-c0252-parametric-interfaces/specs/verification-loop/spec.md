## ADDED Requirements

### Requirement: Circuit stage
`fenolite check` SHALL gain the default stage `circuit.rules`, right after `model.validate` in `STAGE_ORDER` and `DOCUMENT_STAGES`, judging the `.fenolite/` model through the package `checks.circuit`. It MUST run no tool and MUST NOT be in `ORACLE_STAGES`. It MUST be skipped with `no-model` without a readable model, and with `no-parameters` when the model holds no param, port or `ground` or `logic` interface and the contract half (c0253) has nothing either.

#### Scenario: A board without parameters is unchanged
- **WHEN** `fenolite check` runs with `--stages circuit.rules --json` on the built blink of `examples/blink_2layer/`
- **THEN** the stage is `skipped` with the reason `no-parameters`, and the exit code is 0

#### Scenario: A native board has no model
- **WHEN** `fenolite check tests/data/kicad/board/two_layer.kicad_pcb --stages circuit.rules --json` runs
- **THEN** the stage is `skipped` with the reason `no-model`, and the exit code is 0

#### Scenario: The good variant passes
- **GIVEN** the `good` variant of `examples/sensor_rails/`, built in `tmp_path`
- **WHEN** `uv run pytest tests/unit/checks/test_circuit_stage.py -k good` runs `fenolite check <dir> --json`
- **THEN** `result.stages` names `circuit.rules` after `model.validate` with status `ok`, and no issue starts with `circuit.`

### Requirement: Rail voltage check
The stage SHALL give the error `circuit.rail-voltage`, a key of `ISSUE_CODES`, for a rail whose set voltages (from design interfaces and `out` power ports) do not intersect, and for each `in` power port whose accepted range does not contain the rail's voltage. The issue MUST name the rail, the port and both ranges.

#### Scenario: Sensor on a 5 V rail
- **GIVEN** a model whose rail `5V0` has the voltage 4.75 V to 5.25 V and a sensor port `vdd` that accepts 1.71 V to 3.6 V
- **WHEN** `circuit_issues` runs
- **THEN** it returns one `circuit.rail-voltage` naming `5V0`, the sensor's `vdd`, `1.71V..3.6V` and `4.75V..5.25V` in c0246's text

### Requirement: Rail current check
The stage SHALL give the error `circuit.rail-current`, a key of `ISSUE_CODES`, when the sum of the upper bounds of the draws of a rail's loads exceeds the sum of the lower bounds of its sources' capacities. A block's `out` port hides the `out` ports inside that block on the same rail. The issue MUST name both sums and the sources.

#### Scenario: Over budget
- **GIVEN** the `bad` variant of `examples/sensor_rails/`, whose loads on `3V3` draw up to 1.15 A from the block port `buck/VOUT` of 1 A
- **WHEN** `circuit_issues` runs on its model
- **THEN** it returns one `circuit.rail-current` naming `3V3`, `1.15A`, `1A` and `buck/VOUT`, and no finding for the regulator part inside `buck`

#### Scenario: 1.2 A load on a 1 A source fails
- **GIVEN** a rail `5V0` with one `out` port stating `current` 1 A, one `in` port stating `current` up to 1.2 A, and one `inout` connector port that states no current
- **WHEN** `circuit_issues` runs
- **THEN** it returns one `circuit.rail-current` naming `1.2A` and `1A`, because draws are never added to capacity; with the load at 0.8 A it returns none

### Requirement: Rail sources check
The stage SHALL give the error `circuit.rail-sources`, a key of `ISSUE_CODES`, for each rail driven by two or more unhidden `out` power ports, unless the rail is `shared` or every one of those ports has `share`. The issue MUST name the rail and the ports.

#### Scenario: Two regulators on one rail
- **GIVEN** a rail `5V0` with the `out` ports `buck1/VOUT` and `J2.vbus`, and no sharing declared
- **WHEN** `circuit_issues` runs
- **THEN** it returns one `circuit.rail-sources` naming `5V0`, `buck1/VOUT` and `J2.vbus`; with `shared=True` on the rail it returns none

### Requirement: Rails without a value
The stage SHALL give the warning `circuit.rail-unset`, a key of `ISSUE_CODES`, for a rail whose ports state limits when no voltage is set, and for a rail whose loads state a draw when no source states a capacity. The issue MUST name what could not be judged.

#### Scenario: No voltage to judge against
- **GIVEN** a rail `3V3` with no voltage set and a sensor port `vdd` that accepts 1.71 V to 3.6 V
- **WHEN** `circuit_issues` runs
- **THEN** it returns one `circuit.rail-unset` naming `3V3` and the sensor's `vdd`, and no `circuit.rail-voltage`

### Requirement: Logic level check
For each logic reader and driver on one net (the driver being an `out` port, an `inout` port with output levels, or an I2C line's pull-up rail) whose reference rails differ, the stage SHALL give the error `circuit.logic-level` when the driver's `output_high_min` is below the reader's `input_high_min`, its `output_low_max` is above the reader's `input_low_max`, or its rail's upper bound is above the reader's `abs_max`, and the warning `circuit.logic-unknown` naming each missing threshold.

#### Scenario: 3.3 V output into a 1.8 V input
- **GIVEN** a sensor port `int_` (`out`, reference `3V3` at 3.201 V to 3.399 V, `output_high_min` 2.9 V, `output_low_max` 0.4 V) on one net with an MCU port `pa3` (`in`, reference `1V8`, `abs_max` -0.3 V to 1.98 V, `input_high_min` 1.17 V, `input_low_max` 0.63 V)
- **WHEN** `circuit_issues` runs
- **THEN** it returns one `circuit.logic-level` naming `int_`, `pa3`, `3V3`, `3.399V` and `1.98V`, for the withstand comparison only

#### Scenario: A weak high level
- **GIVEN** a driver with `output_high_min` 2.4 V and `output_low_max` 0.4 V on a 3.3 V rail and a reader on a 5 V rail with `input_high_min` 3.5 V, `input_low_max` 1.5 V and `abs_max` up to 5.5 V
- **WHEN** `circuit_issues` runs
- **THEN** it returns one `circuit.logic-level` naming `2.4V` and `3.5V`

#### Scenario: Thresholds not stated
- **GIVEN** the ports of "A weak high level" without `output_high_min` on the driver
- **WHEN** `circuit_issues` runs
- **THEN** it returns one `circuit.logic-unknown` naming the driver and `output_high_min`, and no `circuit.logic-level`, although the driver's rail is 3.3 V

#### Scenario: Same reference passes
- **WHEN** both ports refer to `3V3`
- **THEN** it returns no `circuit.logic-level` and no `circuit.logic-unknown`

### Requirement: Bus pull-up check
The stage SHALL give the warning `circuit.bus-pullup`, a key of `ISSUE_CODES`, for each pull-up of an I2C line (as "Interface checks in a build" of `design-dsl` defines it) whose rail is not the bus's reference rail, whose resistance range is not within the intersection of the `pullup` bounds of the bus and its ports, or whose worst-case current (the rail's upper bound over the resistance's lower bound) exceeds a bus port's `output_current_max`.

#### Scenario: Pulled up to the wrong rail
- **GIVEN** an I2C bus with the reference `3V3` and 4.7 kΩ pull-ups to `5V0`
- **WHEN** `circuit_issues` runs
- **THEN** it returns two `circuit.bus-pullup`, naming `SDA` and `SCL`, `5V0` and `3V3`

#### Scenario: A pull-up stronger than a port sinks
- **GIVEN** an I2C bus pulled up to `3V3` (up to 3.399 V) through 470 Ω ± 1 % resistors, and a sensor port with `output_current_max` 3 mA
- **WHEN** `circuit_issues` runs
- **THEN** it returns two `circuit.bus-pullup` naming the sensor port, `3mA` and the pull-up current in c0246's text

### Requirement: Companion check
The stage SHALL give the warning `circuit.requires-missing`, a key of `ISSUE_CODES`, for each `requires` entry of a port that is not met: `pullup` when a line of the port has no pull-up, `supply` when the reference port's `hv` net (or the port's own) is not a rail with a set voltage and a source or rig supply, and `chip_select` when a `cs` member's net has no other pin. The issue MUST name the port, the entry and what is missing.

#### Scenario: A sensor without pull-ups
- **GIVEN** a sensor whose device port `i2c` has `requires = ["pullup", "supply"]`, joined to an MCU's `i2c1` with a pull-up on `SDA` only, and its `vdd` on a rail `3V3` with a voltage and a source
- **WHEN** `circuit_issues` runs
- **THEN** it returns one `circuit.requires-missing` naming the sensor's `i2c`, `pullup` and `SCL`, and none for `supply`

### Requirement: Split device ports
The stage SHALL give the warning `circuit.port-split`, a key of `ISSUE_CODES`, for each member of a device port whose pins are on two nets, naming the part, the port and the nets. The parameters of that member MUST NOT be judged.

#### Scenario: VDD and VDDA split
- **GIVEN** an MCU whose port `vdd` holds `VDD` and `VDDA`, with `VDD` on `3V3` and `VDDA` on `3V3A`
- **WHEN** `circuit_issues` runs
- **THEN** it returns one `circuit.port-split` naming the MCU, `vdd`, `3V3` and `3V3A`, and no `circuit.rail-voltage` for that port
