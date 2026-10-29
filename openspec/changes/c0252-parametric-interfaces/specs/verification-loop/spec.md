## ADDED Requirements

### Requirement: Circuit stage
`fenolite check` SHALL gain the default stage `circuit.rules`, right after `model.validate` in `STAGE_ORDER` and in `DOCUMENT_STAGES`, unless c0253 has created it. It MUST run no tool, MUST NOT be in `ORACLE_STAGES`, and MUST judge the `.fenolite/` model through `checks.circuit.rails.circuit_issues`. Without that model, or with no param, port, `ground` or `logic` interface in it, the rail checks MUST be skipped with `no-parameters`.

#### Scenario: A board without parameters is unchanged
- **WHEN** `fenolite check` runs with `--stages circuit.rules --json` on the built blink of `examples/blink_2layer/`
- **THEN** the stage is `skipped` with the reason `no-parameters`, and the exit code is 0

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
The stage SHALL compare each logic reader with the driver on its net: the `out` logic port, or the pull-up rail of an I2C line. When their reference rails differ, it SHALL give the error `circuit.logic-level` if the driver rail's voltage is not within the reader's `voltage` or is below its `high_min`, and the warning `circuit.logic-unknown` if the reader states neither. Both codes are keys of `ISSUE_CODES`.

#### Scenario: 3.3 V output into a 1.8 V input
- **GIVEN** a sensor port `int_` (`out`, reference `3V3` at 3.201 V to 3.399 V) on one net with an MCU port `pa3` (`in`, reference `1V8`, `voltage` -0.3 V to 1.98 V)
- **WHEN** `circuit_issues` runs
- **THEN** it returns one `circuit.logic-level` naming `int_`, `pa3`, `3V3`, `1V8` and `1.98V`

#### Scenario: Same reference passes
- **WHEN** both ports refer to `3V3`
- **THEN** it returns no `circuit.logic-level` and no `circuit.logic-unknown`

### Requirement: Bus pull-up check
The stage SHALL give the warning `circuit.bus-pullup`, a key of `ISSUE_CODES`, for each pull-up of an I2C line (as defined by "Interface checks in a build" of `design-dsl`) whose rail is not the bus's reference rail, or whose resistance range is not within the intersection of the `pullup` bounds of the bus and its ports.

#### Scenario: Pulled up to the wrong rail
- **GIVEN** an I2C bus with the reference `3V3` and 4.7 kΩ pull-ups to `5V0`
- **WHEN** `circuit_issues` runs
- **THEN** it returns two `circuit.bus-pullup`, naming `SDA` and `SCL`, `5V0` and `3V3`

### Requirement: Split device ports
The stage SHALL give the warning `circuit.port-split`, a key of `ISSUE_CODES`, for each member of a device port whose pins are on two nets, naming the part, the port and the nets. The parameters of that member MUST NOT be judged.

#### Scenario: VDD and VDDA split
- **GIVEN** an MCU whose port `vdd` holds `VDD` and `VDDA`, with `VDD` on `3V3` and `VDDA` on `3V3A`
- **WHEN** `circuit_issues` runs
- **THEN** it returns one `circuit.port-split` naming the MCU, `vdd`, `3V3` and `3V3A`, and no `circuit.rail-voltage` for that port
