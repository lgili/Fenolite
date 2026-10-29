## ADDED Requirements

### Requirement: Part queries in the DSL
`fenolite.dsl` SHALL export `resistor(value, **constraints)`, `capacitor(value, **constraints)` and `inductor(value, **constraints)`, each returning a `PartQuery` of plain data. A `PartQuery` MUST be accepted as `device=` wherever a device id is (`design.part(device=query)`, `b.part(name, device=query)`), and the part's device MUST stay unresolved in the script; the build resolves it (`part-selection`). No query MUST reach the model except as its part's resolved device.

#### Scenario: A query part
- **GIVEN** `design.defaults(resistor={"case": "0603", "tolerance": pct(1)})` and `r = design.part(device=resistor(ohm("10k")))`
- **WHEN** `r.query.text()` is read in the script
- **THEN** it is `resistor(10kΩ, tolerance<=1%, case=0603)`, and the part has no device until the build

### Requirement: Pins of query parts
A query part SHALL expose the generic pins `1` and `2` of its kind, checked at the call as c0248 checks a device part's pins, and every pickable row of a kind MUST map exactly those two pins; a row with another pin map MUST be refused when the catalog is read, naming the row.

#### Scenario: Pins before the pick
- **GIVEN** `r = design.part(device=resistor(ohm("10k")))`
- **WHEN** `connect(vin, r[1])` and `connect(vin, r[3])` are called
- **THEN** the first is accepted, and the second raises `DslError` naming pin `3` and the pins `1` and `2`

### Requirement: Query arguments
`value` SHALL be a `Quantity` of the kind's unit or a c0246 range of it, and the constraint keys of each kind are closed (`design.md`, decision 3). An unknown key, a value of another unit, a `float`, or a range value combined with `tolerance=` MUST raise `DslError` at the call.

#### Scenario: Refused queries
- **WHEN** `resistor(ohm("10k"), colour="red")`, `capacitor(volt(5))` and `resistor(ohm("10k").pct(5), tolerance=pct(1))` are called
- **THEN** each raises `DslError` naming the key, the unit or the double tolerance

### Requirement: Defaults in the DSL
`Design.defaults(**kinds)` and the same method of a c0251 block builder SHALL take, per query kind, a mapping of that kind's constraint keys, where `None` removes the key at that level. An unknown kind or key, or a value of the wrong unit, MUST raise `DslError` at the call.

#### Scenario: Unknown kind
- **WHEN** `design.defaults(diode={"case": "0603"})` is called
- **THEN** `DslError` is raised naming `diode` and the kinds `resistor`, `capacitor` and `inductor`

### Requirement: Generators in the DSL
`fenolite.dsl` SHALL export `voltage_divider`, `rc_lowpass`, `led_resistor`, `i2c_pull_ups` and `shunt`. Each MUST check its arguments at the call, create its parts as query parts in the given block or design with a generator request attached, connect them to the given nets, and return the created parts (`top` and `bot` for the divider).

#### Scenario: Divider parts and nets
- **GIVEN** `top, bot = voltage_divider(b, out, fb, gnd, target=volt("3.3").pct(5), ref=volt("0.6").pct(1), current=between(ua(40), ua(100)))` in block `buck1`
- **WHEN** the design's connections are read
- **THEN** `buck1/FB_top` joins `VOUT` and `buck1/FB`, `buck1/FB_bot` joins `buck1/FB` and `GND`, and both parts carry the divider request

### Requirement: Generator arguments
A bare quantity where a generator needs a range (`current` of `voltage_divider`), a divider with neither `ref` nor an input voltage, or a part name already used in the block SHALL raise `DslError` at the call.

#### Scenario: The search window must be stated
- **WHEN** `voltage_divider(b, out, fb, gnd, target=volt("3.3").pct(5), ref=volt("0.6").pct(1), current=ua(50))` is called
- **THEN** `DslError` is raised saying that `current` must be a range
