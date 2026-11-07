## MODIFIED Requirements

### Requirement: Interfaces in the DSL
`Interface(name, kind, members)`, `Power(hv, lv, *, name=None)` and `DiffPair(p, n, *, name=None)` SHALL record groups of nets as model `Interface` entities. `Power` MUST be the class `Rail` ("Rail interface"), and an interface without parameters MUST give the model of this requirement byte for byte.
- `Power(hv, lv)` MUST become `Interface(kind="power", members={"hv": <net id>, "lv": <net id>})`, `Power(hv)` MUST become an interface of kind `power` with the member `hv` only, and `DiffPair(p, n)` MUST become `Interface(kind="diff_pair", members={"p": <net id>, "n": <net id>})`.
- The default name MUST be `"<first net name>/<second net name>"`, or the net name for an interface of one net.
- Member nets join the design.
- Interfaces are not written to KiCad files, which hold no pair object: a pair reaches KiCad through its net names and the rules that select it (`rules-model`, "Closed selector grammar"). A build MUST give one `build.interface-not-lowered` info per `diff_pair` and per `usb2` interface ("Typed interfaces in the DSL") that no rule of the design selects, a rule selecting it when one of its `diff_pair` leaves matches the pair's base (`design-model`, "Differential pairs in the model"). The nets of each such pair MUST pass the name check of "Interface checks in a build".

#### Scenario: Power interface
- **GIVEN** `Power(vin, gnd)` added to a design
- **WHEN** `to_model` runs
- **THEN** the model holds an `Interface` named `VIN/GND` with kind `power` and members `hv` and `lv` equal to the ids of `VIN` and `GND`

#### Scenario: Power is Rail
- **GIVEN** the same design written with `Rail(vin, gnd)` instead of `Power(vin, gnd)`
- **WHEN** `canonical.dump_texts(to_model(design))` is computed for both
- **THEN** the texts are equal, and `Power is Rail` holds

#### Scenario: Diff pair reported
- **GIVEN** a blink variant holding `DiffPair(usb_p, usb_n)` on nets `USB_P` and `USB_N`
- **WHEN** it is built with `--dry-run`
- **THEN** `issues` holds one info `build.interface-not-lowered` naming `USB_P/USB_N`

#### Scenario: Diff pair names checked
- **GIVEN** a blink variant holding `DiffPair(clk_p, clk_n)` on nets `CLK_P` and `CLKN`
- **WHEN** it is built with `--dry-run --json`
- **THEN** `issues` hold one info `build.interface-not-lowered` naming `CLK_P/CLKN` and one warning `build.diff-pair-name` naming both nets

#### Scenario: Pair selected by a rule
- **GIVEN** the variant of "Diff pair reported" with `d.rules.pair(pair, uncoupled_max=mm(5))`, or with a rule on `select.pair("*")`
- **WHEN** it is built with `--dry-run --json`
- **THEN** `issues` hold no `build.interface-not-lowered`

### Requirement: Interface checks in a build
A build SHALL check the interfaces of the design after the parts are resolved, as "Built project files" allows for added steps of `build_design`, and SHALL report three warnings, which join the closed build set ("Build issue codes"):

| code | severity | when |
|---|---|---|
| `build.diff-pair-name` | warning | the two nets of a `diff_pair` (`p`, `n`) or `usb2` (`dp`, `dn`) interface do not form a KiCad differential pair by name |
| `build.i2c-pullup-missing` | warning | an I2C line has no two-pin part to the `hv` net of a `power` interface |
| `build.diff-pair-gap-shadowed` | warning | KiCad would report two tracks of a pair interface laid at its class pair gap |

- **Pair names** (`H-K-DIFFPAIR-NAMES-2`). The names, in KiCad's stored form, form a pair when `fenolite.model.pairs.pair_base(<positive name>, <negative name>)` is not `None` (`design-model`, "Differential pairs in the model"). The hint MUST propose a second name: `coupled_name(<positive name>)` when the positive name has the polarity `P` or `+`; otherwise `<positive name>_P` and `<positive name>_N`.
- **Pull-ups.** For the `sda` and `scl` nets of each `i2c` interface, a pull-up is a component whose resolved symbol has exactly two pins, one on that net and the other on the `hv` net of a `power` interface of the design or on the `hv` member net of a `power` port ("Block ports in the DSL", "Device interface ports in the DSL"). Whether that rail is the bus's reference rail is judged by `circuit.bus-pullup` (`verification-loop`, "Bus pull-up check"). The issue MUST name the interface and the line.
- **Shadowed pair gap** (`H-K-PRO-PAIR`). For each `diff_pair` or `usb2` interface whose nets form a pair by name and are in one model class whose `diff_pair_gap` `g` is set, the warning MUST be given when the clearance in force between a track of each net on one copper layer (`copper-check`, "Clearance in force" and "Clearance between the nets of a differential pair", with the switches of the target) is above `g`, or when the board minimum clearance that the build writes for the target is above `g` and no rule of kind `diff_pair_gap` selects the pair's tracks. The message MUST name both nets, `g` and what governs (a rule, a class or the board minimum); the hint MUST name `design.rules.pair(…, clearance=…, gap_min=…)`.
- The checks MUST NOT change any file or the model, and a design without interfaces MUST give none of the three codes.

#### Scenario: Pair names that KiCad does not pair
- **GIVEN** a blink variant with `USB2(usb_dp, usb_dm)` on the nets `USB_DP` and `USB_DM`
- **WHEN** it is built with `--dry-run --json`
- **THEN** `issues` hold one `build.diff-pair-name` naming `USB_DP` and `USB_DM`, with a hint naming `USB_DN`, and one `build.interface-not-lowered`

#### Scenario: Pair names that KiCad pairs
- **WHEN** the same variant uses the nets `USB_P` and `USB_N`
- **THEN** `issues` hold no `build.diff-pair-name`

#### Scenario: Pair names with a tail
- **WHEN** the same variant uses the nets `D_P0` and `D_N0`, and then `D_P0` and `D_N1`
- **THEN** the first build's `issues` hold no `build.diff-pair-name`, and the second's hold one whose hint names `D_N0`

#### Scenario: Missing pull-up
- **GIVEN** a design with `Power(vdd, gnd)`, `I2C(sda, scl)`, a resistor from `SDA` to `VDD` and none on `SCL`
- **WHEN** it is built with `--dry-run --json`
- **THEN** `issues` hold one `build.i2c-pullup-missing` naming the interface and `scl`

#### Scenario: Pull-up to a device power port
- **GIVEN** a design with no `power` interface, an MCU part whose device declares the `power` port `vdd` on the net `VDD`, `I2C(sda, scl)`, and a resistor from each line to `VDD`
- **WHEN** it is built with `--dry-run --json`
- **THEN** `issues` hold no `build.i2c-pullup-missing`

#### Scenario: Pair gap under a board-wide clearance rule
- **GIVEN** a blink variant with `usb = USB2(usb_p, usb_n)` on `USB_P` and `USB_N`, both in the class `USB` (clearance 0.2 mm, `diff_pair_gap` 0.15 mm), and `d.rules.minimum(clearance=mm(0.2))`
- **WHEN** it is built for target 10 with `--dry-run --json`
- **THEN** `issues` hold one `build.diff-pair-gap-shadowed` naming `USB_P`, `USB_N`, `0.15` and the rule `min_clearance`; after `d.rules.pair(usb, clearance=mm(0.15), gap_min=mm(0.13))` they hold none

## ADDED Requirements

### Requirement: Rail interface
`fenolite.dsl` SHALL provide `Rail(hv, lv=None, *, name=None, voltage=None, shared=False)`, an addition under "DSL package", recorded as an interface of kind `power` with the members `hv` and, when given, `lv`. `voltage` MUST be a c0246 range or quantity of volts, and `shared` states that several sources may drive the rail. `Power` MUST be another name of `Rail`.

#### Scenario: Rail with a voltage
- **GIVEN** `Rail(v33, gnd, voltage=volt("3.3").pct(3))` added to a design
- **WHEN** `to_model` runs
- **THEN** the interface `3V3/GND` has kind `power` and the param `voltage` with the `ValueRange` (c0246) from 3.201 V to 3.399 V

#### Scenario: Wrong unit refused
- **WHEN** `Rail(v33, voltage=amp(1))` is called
- **THEN** `DslError` is raised naming `voltage` and the unit

### Requirement: Ground and logic interfaces
`fenolite.dsl` SHALL provide `Ground(gnd, *, name=None)`, of kind `ground` with the member `gnd`, and `Logic(io, *, name=None, reference=None)`, of kind `logic` with the member `io`, both additions under "DSL package". `reference` MUST be a `Rail` or a power port handle. Otherwise `DslError` is raised. The default name of each is its net's name.

#### Scenario: Logic with a reference rail
- **GIVEN** `rail = Rail(v18)` and `Logic(irq, reference=rail)` added to a design
- **WHEN** `to_model` runs
- **THEN** the interface `IRQ` has kind `logic` and `reference` equal to the id of the interface `1V8`

### Requirement: Rails and grounds of a design
`Design` SHALL offer `rail(name, *, voltage=None, ground=None, shared=False) -> Rail` and `ground(name) -> Ground`. Each MUST create and add a `Net` of that name and the interface. `ground`, when given, MUST be a `Ground` or a `Net` and gives the member `lv`. A name already used by a net of the design MUST raise `DslError`.

#### Scenario: Rail in one call
- **GIVEN** `gnd = d.ground("GND")` and `v12 = d.rail("V12", voltage=volt("12").pct(10), ground=gnd)`
- **WHEN** `to_model` runs
- **THEN** the model holds the nets `GND` and `V12`, the interface `GND` of kind `ground`, and the interface `V12/GND` of kind `power` with the param `voltage`

### Requirement: Interface parameters in the DSL
Each interface kind SHALL have a closed parameter table, `fenolite.dsl.interfaces.PARAMETERS`, that marks each parameter `alias`, `sum`, `bound` or `link` and says where it may be set (`design.md`, decision 1). A value MUST be a c0246 range or quantity of the parameter's unit. A parameter outside the table, not allowed for the kind and direction, or a sum parameter (`current`) on a port whose direction is not explicitly `in` or `out`, MUST raise `DslError` at the call.

#### Scenario: Current on a design rail refused
- **WHEN** `Rail(v33, current=amp(1))` is called
- **THEN** `DslError` is raised naming `current` and saying that it is set on ports only

#### Scenario: Current on a pass-through port refused
- **WHEN** a block calls `b.port("VBUS", Rail, current=amp(1))`, whose direction is c0251's default `inout`
- **THEN** `DslError` is raised naming `VBUS` and `current`, and asking for `direction="in"` or `direction="out"`

#### Scenario: Logic thresholds on a block port
- **GIVEN** a block with `b.port("INT", Logic, direction="out", output_high_min=volt("2.4"), output_low_max=volt("0.4"))`
- **WHEN** `to_model` runs
- **THEN** the model `Port` `INT` holds the params `output_high_min` and `output_low_max` in c0246's encoding, and `input_high_min` on that port raises `DslError`

### Requirement: Port parameters
c0251's `port(name, kind, *, direction="inout", optional=False, **params)` SHALL accept the parameters of the kind's table for that direction, and `PortHandle.set(**params)` SHALL set them later in the block. A parameter set twice MUST raise `DslError`. `to_model` MUST record each on the model `Port`.

#### Scenario: Source port of a block
- **GIVEN** a block `buck` with `out = b.port("VOUT", Rail, direction="out")` and `out.set(voltage=vout, current=current)`, used as `buck1` with `vout=volt("3.3").pct(3)` and `current=amp(1)`
- **WHEN** `to_model` runs
- **THEN** the port `VOUT` of `buck1` has the params `current` (1 A to 1 A) and `voltage` (3.201 V to 3.399 V)

### Requirement: Net-like interfaces
A `Rail`, a `Ground` or a `Logic`, and a port of kind `power`, `ground` or `logic`, SHALL be net-like through its main member (`hv`, `gnd`, `io`). `connect` MUST accept it as its first argument with pins after it, and as an argument after a compatible net-like first argument.

#### Scenario: Rail joined to a pin
- **GIVEN** `v12 = d.rail("V12")` and `connect(v12, j1[1])`
- **WHEN** `to_model` runs
- **THEN** the net `V12` holds pin 1 of `J1`

### Requirement: Connecting whole interfaces
When every argument of `connect` is an interface or a port, and one of them has more than one member, `connect` SHALL join each member to the member of the same name of every other argument, through c0251's port nets. An optional member (`power.lv`, `usb2.vbus`, `usb2.gnd`) joins only where both sides have it; a missing required member MUST raise `DslError`. Two UART ports MUST cross `tx` and `rx`. Nothing is connected when one pair is refused.

#### Scenario: Two I2C ports
- **GIVEN** an MCU part with the device port `i2c1` (`sda` on `PB7`, `scl` on `PB6`) and a sensor part with the device port `i2c` (`SDA`, `SCL`), and `connect(I2C(Net("SDA"), Net("SCL")), mcu.i2c1, sen.i2c)`
- **WHEN** `to_model` runs
- **THEN** the net `SDA` holds `PB7` of the MCU and `SDA` of the sensor, and the net `SCL` holds `PB6` and `SCL`

#### Scenario: UART ports cross
- **GIVEN** two parts with device UART ports `u1.uart` and `u2.uart`, and `connect(u1.uart, u2.uart)`
- **WHEN** `to_model` runs
- **THEN** the `TX` pin of each part is on one net with the `RX` pin of the other

### Requirement: Interface compatibility
`connect` SHALL accept only the pairs of the closed compatibility table of `design.md` (decision 4): equal kinds (a harness with equal entry names, an SPI with equal chip selects), and a net with the main member of a `power`, `ground` or `logic` interface or port. Any other pair, and a `UART` bus interface joined to a port, MUST raise `DslError` naming both kinds and both names.

#### Scenario: Ground on a rail refused
- **WHEN** `connect(d.ground("GND"), buck1.VIN)` is called, `VIN` being a `Rail` port
- **THEN** `DslError` is raised naming `ground`, `GND`, `power` and `buck1/VIN`, and nothing is connected

### Requirement: Device interface ports in the DSL
For a part placed from a c0248 device record, `part.port(name)` and the attribute `part.<name>` SHALL return a `PortHandle` for each `[[interfaces]]` table of the record, whose members are the pins of the part's c0248 functions through port nets owned by the component path. `to_model` MUST give one model `Port` per declared port ("Device ports in the model"). An unknown port name MUST raise `DslError` naming the device's ports.

#### Scenario: Rail joined to two device ports
- **GIVEN** `v33 = d.rail("3V3")` and `connect(v33, mcu.vdd, sen.vdd)`, where the MCU's `vdd` port holds the pins `VDD` and `VDDA`
- **WHEN** `to_model` runs
- **THEN** the net `3V3` holds `VDD` and `VDDA` of the MCU and `VDD` of the sensor, and the model holds a `Port` `vdd` for each part whose `hv` member is the id of `3V3`

### Requirement: Bus reference rails
`I2C`, `SPI`, `UART` and `USB2` SHALL accept `reference=`, a `Rail` or a power port handle, recorded as the interface's `reference`. `I2C` SHALL also accept `pullup=`, a c0246 range of ohms, recorded as the param `pullup`.

#### Scenario: I2C with a reference and a pull-up range
- **GIVEN** `I2C(sda, scl, reference=v33, pullup=between(ohm("2k"), ohm("10k")))` added to a design
- **WHEN** `to_model` runs
- **THEN** the interface has `reference` equal to the id of the rail `3V3` and the param `pullup` from 2 kΩ to 10 kΩ

### Requirement: Pull-ups on a bus
c0247's `pull_up(target, rail, *resistors)` SHALL also accept an `i2c` port as `target`, with two resistors (the first on `sda`, the second on `scl`), and a `Logic` interface or `logic` port, with one resistor on `io`. Each resistor MUST join as in c0247, and a wrong number of resistors MUST raise `DslError`.

#### Scenario: One call, two resistors
- **GIVEN** the design of "Two I2C ports" with `v33 = d.rail("3V3")`, two resistors `r_sda` and `r_scl`, and `pull_up(mcu.i2c1, v33, r_sda, r_scl)`
- **WHEN** it is built with `--dry-run --json`
- **THEN** `r_sda` is between `SDA` and `3V3`, `r_scl` between `SCL` and `3V3`, and `issues` hold no `build.i2c-pullup-missing`

### Requirement: Interface companions
A port SHALL accept `requires`, a list of entries of the closed vocabulary `pullup` (`i2c`, `logic`), `supply` (`logic` and buses with a `reference`, `power` `in` ports) and `chip_select` (`spi`): what must be connected for the port to work. Block ports take it as `b.port(..., requires=(...))`. An entry outside the vocabulary, or one that the port's kind does not take, MUST raise `DslError`. `to_model` MUST record it on the model `Port`.

#### Scenario: A sensor port that needs pull-ups
- **GIVEN** a block with `b.port("I2C", I2C, requires=("pullup", "supply"), reference=vdd)`
- **WHEN** `to_model` runs
- **THEN** the model `Port` `I2C` has `requires == ("pullup", "supply")`, and `requires=("chip_select",)` on that port raises `DslError` naming `chip_select` and `i2c`

### Requirement: Circuit findings in a build
`cmd_build` SHALL run `checks.circuit.circuit_issues` on the model that it builds, and SHALL add the `circuit.*` issues to the build envelope as codes added under "Build issue codes". Each issue keeps the severity of `verification-loop`, "Circuit stage". An error issue MUST stop the write, as other build errors do; c0274 adds the waivers that accept one.

#### Scenario: Over-budget rail stops the build
- **GIVEN** the `bad` variant of `examples/sensor_rails/`, whose loads on `3V3` draw up to 1.15 A from a source of 1 A
- **WHEN** it is built with `--confirm --json`
- **THEN** the exit code is 5, `issues` hold one `circuit.rail-current` naming `3V3` and `buck/VOUT`, and no file is written
