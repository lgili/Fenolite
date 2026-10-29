## ADDED Requirements

### Requirement: Interface parameters in the model
The model `Interface` SHALL gain `params` (name to a c0246 `ValueRange`), `reference: str | None = None` (the id of a `power` interface) and `shared: bool = False`. c0251's `Port` SHALL gain `params`, `reference` (the id of a `power` port or interface), `share: bool = False` and `requires: tuple[str, ...] = ()`, sorted. A param MUST be written in c0246's encoding (unit name, `Decimal10` bounds). Each field MUST be left out of `circuit.json` when empty or default.

#### Scenario: Parameters round trip
- **GIVEN** a `power` interface with the param `voltage` and `shared=True`, and a `power` port with the params `voltage` and `current`
- **WHEN** the design is written with `canonical.dump_dir` and loaded with `canonical.load_dir`
- **THEN** the loaded entities equal the originals, every bound in `circuit.json` is an integer mantissa and exponent, every unit is a c0246 unit name such as `volt`, and no `min` or `max` key is written

#### Scenario: Older circuit files keep their bytes
- **GIVEN** a `circuit.json` written before this change, holding a `power` interface
- **WHEN** it is loaded, validated against the regenerated schema and written again
- **THEN** the interface has no params, and the written bytes equal the input

### Requirement: Ground and logic kinds in the model
The circuit model SHALL know the interface kinds `ground` (member `gnd`) and `logic` (member `io`) beside the kinds it holds today. `power_interface_nets` MUST keep reading the kind `power` only. A param name outside the kind's table MUST raise `ValueError`.

#### Scenario: Unknown param refused
- **WHEN** a model `Interface` of kind `ground` is built with the param `voltage`
- **THEN** `ValueError` is raised naming `ground` and `voltage`

### Requirement: Device ports in the model
`to_model` SHALL give one `Port` per declared port of each part placed from a device record, owned by the component's id, with the id `derived_id("prt", "dsl", "port:<component path>:<port name>")`, the params of the record and the net of each member. A member whose pins are on two nets MUST be left out of `members`.

#### Scenario: Device port recorded
- **GIVEN** a sensor part `U3` whose device declares the `power` port `vdd` (pin `VDD`, `voltage` 1.71 V to 3.6 V), with `VDD` on the net `3V3`
- **WHEN** `to_model` runs
- **THEN** the model holds the `Port` `vdd`, owned by the id of `U3`, of kind `power` and direction `in`, whose `hv` member is the id of `3V3` and whose param `voltage` has the record's bounds
