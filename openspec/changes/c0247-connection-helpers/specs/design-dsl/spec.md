## MODIFIED Requirements

### Requirement: No-connect marks in the DSL
`fenolite.dsl.part.no_connect(*pins) -> None` SHALL mark each pin handle as intentionally unconnected, and `fenolite.dsl` SHALL re-export `no_connect` (an addition under "DSL package": `part.py` imports nothing new).
- Each argument MUST be a pin handle such as `u1[11]` or `u1["TP"]`; any other value MUST raise `DslError`. A call without arguments does nothing. Pins of several parts MAY be marked in one call.
- The designator MUST be stored as written in `Part.no_connects`, a set of `str`, and resolved only by the build ("No-connect marks in a build"). `u1[11]` and `u1["11"]` name the same mark, and marking a designator twice keeps one mark.
- `no_connect` on a designator that `connect` joined to a net MUST raise `DslError` naming the ref, the designator and the net. `connect` on a marked designator MUST raise `DslError` naming the ref and the designator. In both cases the earlier call stays in force.
- A mark belongs to its part: it joins the design when the part is added, before or after the call, and a part that is never added carries no mark into the model.
- `to_model` MUST set `Circuit.no_connects` to one `PinRef(<component id>, <designator as written>)` per mark, in `PinRef` order (`design-model`, "No-connect marks in the circuit model"), and MUST change nothing else: `Component.pins` stays empty and no net is created.
- `Part.unused_no_connect()` asks the build to mark the part's open pins ("Unused pins marked in the DSL"); the marks it gives are marks of this requirement once resolved. There is no way to remove a mark.
- `docs/dsl.md` MUST gain a section "No-connect marks" with the call, the errors, the stored form and what each target does with a mark.

#### Scenario: Marks in the model
- **GIVEN** `u1 = Part("U1", "Mini:Mini_QFP32_IC")` added to a design, and `no_connect(u1[12], u1[11], u1["11"])`
- **WHEN** `to_model(design)` runs
- **THEN** `circuit.no_connects` is `(PinRef(<U1 id>, "11"), PinRef(<U1 id>, "12"))`, `U1` has `pins == ()`, and the circuit holds no net

#### Scenario: Marking a connected designator
- **WHEN** `connect(en, u1[11])` is followed by `no_connect(u1[11])`
- **THEN** `DslError` is raised naming `U1`, `11` and `EN`, and `to_model` gives no mark

#### Scenario: Connecting a marked designator
- **WHEN** `no_connect(u1[11])` is followed by `connect(en, u1[11])`
- **THEN** `DslError` is raised naming `U1` and `11`, and the net `EN` gets no member

#### Scenario: Not a pin handle
- **WHEN** `no_connect("U1.11")` or `no_connect(u1)` is called
- **THEN** `DslError` is raised

#### Scenario: Re-export and import rule
- **WHEN** `python -c "from fenolite.dsl import no_connect; print(no_connect.__module__)"` and `uv run pytest tests/unit/test_import_graph.py` run
- **THEN** the first prints `fenolite.dsl.part`, and the second passes with no `ALLOWED` change

## ADDED Requirements

### Requirement: Named ends of two-pin parts
`Part.a` and `Part.b` SHALL be read-only properties returning the pin handles `part["1"]` and `part["2"]`, and SHALL set `Part.two_terminal` to `True`. When the part comes from a catalog device that names its ends (change c0248), `a` and `b` MUST name those pins instead.

#### Scenario: Ends are pins one and two
- **GIVEN** `r1 = Part("R1", "Mini:Mini_R")` added to a design, and `connect(a, r1.a)` and `connect(b, r1.b)`
- **WHEN** `to_model` runs
- **THEN** the net `A` holds `PinRef(<R1 id>, "1")`, the net `B` holds `PinRef(<R1 id>, "2")`, and `r1.two_terminal` is `True`

### Requirement: Two-pin parts checked in a build
A build SHALL check every part whose `two_terminal` is set: a resolved symbol with other than two pins MUST give `build.not-two-terminal` (error) naming the ref and the pin count, and the build MUST exit 5 and write nothing. The code MUST be a key of `lens.build.BUILD_ISSUE_CODES` and of the Altium build's codes with severity `error`, listed in `docs/cli-contract.md` and explained in `explain.toml`.

#### Scenario: A three-pin part used through its ends
- **GIVEN** `connect(vin, q1.a)` on a part `Q1` whose symbol has three pins
- **WHEN** the design is built with `--confirm`
- **THEN** the exit code is 5, `issues` holds `build.not-two-terminal` naming `Q1` and `3`, and nothing is written

#### Scenario: New code in the closed set
- **WHEN** `uv run pytest tests/unit/lens/test_build_issues.py -k closed_set` and `uv run pytest tests/consistency` run
- **THEN** both pass, and `BUILD_ISSUE_CODES["build.not-two-terminal"]` is `error`

### Requirement: Series chains in the DSL
`fenolite.dsl.wiring.series(*chain) -> tuple[Net, ...]` SHALL connect a chain whose first and last items are `Net`s, with at least one part between them. An inner item MUST be a `Part` (entered at `a`, left at `b`), a tuple of two distinct pin handles of one part (entered at the first), or a `Net` naming the joint between the parts on its two sides. The function MUST return the nets it created, in chain order.

#### Scenario: Fuse and diode in series
- **GIVEN** parts `F1` and `D1` in a design, and `series(vin, f1, d1, vprot)`
- **WHEN** `to_model` runs
- **THEN** `VIN` holds `F1` pin `1`, a new net `F1-D1` holds `F1` pin `2` and `D1` pin `1`, `VPROT` holds `D1` pin `2`, and the call returned that one new net

#### Scenario: A part turned around and a named joint
- **GIVEN** `series(led_drv, r1, led_a, (d1.b, d1.a), gnd)`
- **WHEN** `to_model` runs
- **THEN** `LED_A` holds `R1` pin `2` and `D1` pin `2`, `GND` holds `D1` pin `1`, and the call returned `()`

### Requirement: Series chain refusals
`series` SHALL raise `DslError`, connecting nothing, when the chain does not start and end with a `Net`, holds no part, holds two `Net`s next to each other, holds a tuple that is not two distinct pin handles of one part, or holds any other value. A generated joint net is named `<left path>-<right path>`, and a name another net of the design holds MUST raise `DslError` by the rule of distinct net names.

#### Scenario: Refused chains
- **WHEN** `series(f1, vin)`, `series(vin, vout)`, `series(vin, f1, a, b, d1, vout)`, `series(vin, (f1.a, d1.b), vout)` and `series(vin, "F1", vout)` are called
- **THEN** each raises `DslError`, and no net gets a member

### Requirement: Decoupling in the DSL
`fenolite.dsl.wiring.decouple(rail, ground, *capacitors, near=None, within=None, severity="error")` SHALL join each capacitor's `a` to `rail` and its `b` to `ground`. With `near` and `within`, it SHALL record for each capacitor the rule `design.near("decouple/<capacitor path>", capacitor, near, within=within, severity=severity)`, so that every rule of "Placement rules in the DSL" applies.

#### Scenario: Decoupling rule recorded
- **GIVEN** the blink with a capacitor `C1` added, and `decouple(vin, gnd, c1, near=u1.pad(9), within=mm(3))`
- **WHEN** `to_model` runs
- **THEN** `VIN` holds `C1` pin `1`, `GND` holds `C1` pin `2`, and `RuleSet.proximity` holds `ProximityRule("decouple/C1", (PadSelection("C1"),), (PadSelection("U1", "9"),), 3_000_000)`

#### Scenario: Without a rule
- **WHEN** `decouple(vin, gnd, c1, c2)` runs and `to_model` follows
- **THEN** both capacitors join the two nets, and `RuleSet.proximity` is empty

### Requirement: Decoupling refusals
`decouple` SHALL raise `DslError`, connecting nothing, when no capacitor is given, when only one of `near` and `within` is given, when `rail` is `ground`, when `near` is given and a capacitor is in no design, or when `near()` would refuse the rule; a pin handle as `near` MUST give the hint `part.pad(<number>)`. There is no default `within`.

#### Scenario: Refused decoupling
- **WHEN** `decouple(vin, gnd)`, `decouple(vin, gnd, c1, near=u1.pad(9))`, `decouple(vin, vin, c1)` and `decouple(vin, gnd, c1, near=u1[9], within=mm(3))` are called
- **THEN** each raises `DslError`, the last with the hint `part.pad(<number>)`

### Requirement: Pull resistors in the DSL
`fenolite.dsl.wiring.pull_up(target, rail, *resistors)` and `pull_down(target, ground, *resistors)` SHALL join each resistor's `a` to a signal net and its `b` to `rail` or `ground`. `target` MUST be a `Net` (one resistor) or an `I2C` (two resistors: the first on `sda`, the second on `scl`).

#### Scenario: I2C pull-ups
- **GIVEN** `bus = I2C(sda, scl)` and `pull_up(bus, v33, r3, r4)`
- **WHEN** `to_model` runs
- **THEN** `SDA` holds `R3` pin `1`, `SCL` holds `R4` pin `1`, and `3V3` holds `R3` pin `2` and `R4` pin `2`

#### Scenario: A pull-down on one net
- **WHEN** `pull_down(en, gnd, r5)` runs and `to_model` follows
- **THEN** `EN` holds `R5` pin `1` and `GND` holds `R5` pin `2`

### Requirement: Pull resistor refusals
`pull_up` and `pull_down` SHALL raise `DslError`, connecting nothing, when the number of resistors differs from the number of target nets, when a target net is the rail or ground net, when `target` is another interface (naming its kind), or when a resistor is not a `Part`; a `Quantity` or `Range` MUST give a message saying that a value does not choose a part.

#### Scenario: Refused pull resistors
- **WHEN** `pull_up(bus, v33, r3)`, `pull_up(v33, v33, r3)`, `pull_up(SPI(sck, mosi, miso), v33, r3, r4, r5)` and `pull_up(sda, v33, ohm("4k7"))` are called
- **THEN** each raises `DslError`, the third naming `spi` and the fourth saying that a value does not choose a part

### Requirement: Unused pins marked in the DSL
`Part.unused_no_connect(*, keep=())` SHALL record a request, as `Part.unused_request`, that the build marks every open pin of the part, except the designators of `keep` (`str` or `int`, as written). A second call on one part MUST raise `DslError`. `connect` and `no_connect` stay allowed after it. `to_model` MUST NOT change; `dsl.convert.unused_marks(design)` and `dsl.convert.two_terminal(design)` MUST give the requests and two-pin parts by path, in path order.

#### Scenario: Request recorded, model unchanged
- **GIVEN** the blink with its `no_connect` call replaced by `u1.unused_no_connect()`
- **WHEN** `to_model` and `unused_marks` run
- **THEN** `circuit.no_connects` is empty, and `unused_marks` is `{"U1": ()}`

#### Scenario: Called twice
- **WHEN** `u1.unused_no_connect()` is called twice
- **THEN** the second call raises `DslError` naming `U1`

### Requirement: Unused pins resolved in a build
A build SHALL resolve each request after the explicit marks: in pin-number order, a pin with no net, no mark, not in `keep` and of a type other than `no_connect` MUST become `PinRef(<component id>, <pin number>)` in `Circuit.no_connects`, unless it is a must-connect pin. The new marks MUST follow "No-connect marks in a build" in both the KiCad and the Altium build; an unknown `keep` designator MUST give `build.unknown-pin`.

#### Scenario: The blink keeps its pinned bytes
- **GIVEN** `examples/blink_2layer/design.py` with its `no_connect` call replaced by `u1.unused_no_connect()`
- **WHEN** `uv run pytest tests/unit/lens/test_build_bytes_pinned.py` builds it
- **THEN** every digest of `blink@9` and `blink@10` is unchanged, and `.fenolite/circuit.json` holds the 29 marks

#### Scenario: Kept pins stay open without a mark
- **GIVEN** `u1.unused_no_connect(keep=(5, "PA7"))` on a part whose pin `12` is named `PA7`
- **WHEN** the design is built
- **THEN** pins `5` and `12` have no mark, and every other open pin of `U1` has one

### Requirement: Must-connect pins
A pin SHALL be must-connect when its symbol type is `power_in`, or when the part comes from a catalog device that flags the pin `must_connect` (change c0248). An open must-connect pin met by an unused-pin request MUST give `build.must-connect-unconnected` (error) naming the ref, the pin number and the name, and the build MUST exit 5 and write nothing. The code joins the closed sets like `build.not-two-terminal`.

#### Scenario: An open supply pin is not marked
- **GIVEN** the blink without `connect(vin, u1[9])` and with `u1.unused_no_connect()`
- **WHEN** the design is built with `--confirm`
- **THEN** the exit code is 5, `issues` holds `build.must-connect-unconnected` naming `U1` and `9`, and nothing is written

#### Scenario: A kept supply pin is not reported
- **GIVEN** the same design with `u1.unused_no_connect(keep=(9,))`
- **WHEN** the design is built with `--confirm`
- **THEN** no `build.must-connect-unconnected` is reported and pin `9` has no mark

### Requirement: Connection helper names and documentation
`fenolite.dsl` SHALL re-export `series`, `decouple`, `pull_up` and `pull_down` (an addition under "DSL package"; `wiring.py` imports only `dsl` modules). `docs/dsl.md` MUST gain a section "Connection helpers" with the ends, each helper, the generated net names, the unused-pin request, the must-connect rule and the two codes.

#### Scenario: Re-exports
- **WHEN** `python -c "from fenolite.dsl import series, decouple, pull_up, pull_down; print(series.__module__)"` and `uv run pytest tests/unit/test_import_graph.py` run
- **THEN** the first prints `fenolite.dsl.wiring`, and the second passes with no `ALLOWED` change
