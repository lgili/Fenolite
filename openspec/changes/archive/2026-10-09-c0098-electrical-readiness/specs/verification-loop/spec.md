## ADDED Requirements

### Requirement: Shared readiness definitions
`model.circuit.power_interface_nets(circuit)` SHALL return the ids of the nets that an interface of kind `power` names, and `checks.validate.unresolved_footprints(design)` SHALL return, in circuit order, the parts that are not DNP and have an empty `lib_footprint_ref` or no footprint instance.
- `checks.erc_lite` and `backends.kicad.schgen` MUST use the first in place of their own sets, and `validate_stage` the second, with their output unchanged.

#### Scenario: The shared helpers keep their callers' output
- **WHEN** `uv run pytest tests/unit/checks tests/unit/backends/kicad -k "validate or erc_lite or flag or power"` runs
- **THEN** every test passes unchanged

### Requirement: Open nets check
`checks.readiness.open_stage(nets, *, evidence, issues)` SHALL give the check `nets.open`, with one `ready.net-open` (error, `where` the net name) per net with open connections, whose message names the count and the ends and length of the shortest, and `summary` `{nets, connections}`.

#### Scenario: Two open nets
- **GIVEN** two `OpenNet` rows, `A` with 2 connections and `B` with 1
- **WHEN** `uv run pytest tests/unit/checks/test_readiness.py -k open_stage` runs
- **THEN** the stage has status `errors`, two `ready.net-open` issues and `summary` `{"nets": 2, "connections": 3}`

### Requirement: Unconnected pins rule
`checks.readiness.unconnected_pins(design, *, flagged)` SHALL return, in circuit order, each pin of a part that is not DNP whose type is not `no_connect`, that no `Circuit.no_connects` entry marks, that is not in `flagged`, and that is on no net or the only member of its net.
- `pins_stage` MUST give `pins.unconnected`, with one `ready.pin-unconnected` (error, `where` `REF-PIN`) per pin.

#### Scenario: A marked pin is not unconnected
- **GIVEN** `U1` with pin `1` on `VCC` with `R1-1`, `2` on no net, `3` on no net and marked, `4` of type `no_connect`, `5` alone on `X`, and a DNP part with a pin on no net
- **WHEN** `uv run pytest tests/unit/checks/test_readiness.py -k pins` runs
- **THEN** the rule returns `U1-2` and `U1-5` only, and with `U1-5` in `flagged` only `U1-2`

### Requirement: Power nets rule
`checks.readiness.power_nets(intent, *, board)` SHALL return one row per power net, sorted by name: a net of `power_interface_nets` (source `interface`), else a net with a `power_in` or `power_out` member pin (source `pin-type`).
- A row MUST hold `width` ("Power net coverage") and `zones`, the zones of `board` on a net of that name.
- `power_stage` MUST give `power.nets` with one `ready.power-net-unsized` (error) per row whose `width` is `null` and `zones` 0.

#### Scenario: Power nets and their coverage
- **GIVEN** a `Power` interface over `VCC` and `GND`, a net `V5` with a `power_out` pin, a net `SIG` of `passive` pins, and a zone on `GND`
- **WHEN** `uv run pytest tests/unit/checks/test_readiness.py -k power` runs
- **THEN** the rows name `GND` (`interface`, zones 1), `V5` (`pin-type`) and `VCC` (`interface`), and none names `SIG`; without the zone, `GND` gives one `ready.power-net-unsized`

### Requirement: Power net coverage
The `width` of a power net SHALL be `class:<name>` when its class is not `Default` and has a `track_width`, else `rule:<name>` for the first rule of kind `track_width`, of severity other than `ignore` and whose `selector_a` is not `all`, that selects `RuleSubject("track", net, netclass)`, else `null`.

#### Scenario: Class and rule widths
- **GIVEN** `VCC` in a class `PWR` with a track width, a `track_width` rule `v5` selecting `net V5`, and a `track_width` rule selecting `all`
- **WHEN** `uv run pytest tests/unit/checks/test_readiness.py -k width` runs
- **THEN** `VCC` has `class:PWR`, `V5` has `rule:v5`, and `GND`, which only the `all` rule selects, has `null`

### Requirement: Part fields rule
`checks.readiness.parts_stage(design)` SHALL give `parts.fields`, with one `check.footprint-unresolved` per part of `unresolved_footprints` and one `ready.part-value-missing` (error, `where` the reference) per part that is not DNP and whose value is empty after stripping.

#### Scenario: Part fields
- **GIVEN** `R1` without a value, `R2` without a footprint reference, and a DNP part `R3` without either
- **WHEN** `uv run pytest tests/unit/checks/test_readiness.py -k parts` runs
- **THEN** the stage reports `ready.part-value-missing` for `R1`, `check.footprint-unresolved` for `R2`, and nothing for `R3`

### Requirement: Readiness issue codes
`checks.readiness.READY_ISSUE_CODES` SHALL be the closed table of `ready.net-open`, `ready.pin-unconnected`, `ready.power-net-unsized`, `ready.part-value-missing` (error) and `ready.check-skipped` (warning, given by `skipped_check`); the three rules carry `EVIDENCE` (`INFERRED`, `H-G-READY-RULES`).
- `cli.explain.TABLES` MUST name the table, with an entry per code whose `see` is `ready`.

#### Scenario: Every code is explained
- **WHEN** `uv run pytest tests/unit/cli/test_explain_cmd.py` runs
- **THEN** it passes, and `fenolite explain ready.power-net-unsized --json` exits 0 with `see` `ready`
