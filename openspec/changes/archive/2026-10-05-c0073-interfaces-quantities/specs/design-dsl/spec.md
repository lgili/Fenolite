## ADDED Requirements

### Requirement: Quantities in the DSL
`fenolite.dsl.quantity` SHALL provide `Quantity`, an exact value of one unit among `ohm`, `farad`, `henry`, `volt`, `ampere`, `hertz`, `watt` and `second`, and the constructors `ohm(x)`, `farad(x)`, `henry(x)`, `volt(x)`, `amp(x)`, `hertz(x)`, `watt(x)` and `second(x)`; `fenolite.dsl` SHALL re-export `Quantity` and the constructors (an addition under "DSL package").
- **Input.** `x` MUST be an `int`, a `fractions.Fraction`, or a text: a decimal number, an optional SI prefix among `p`, `n`, `u`, `µ`, `m`, `k`, `M` and `G`, and an optional symbol of the constructor's unit (`Ω`, `ohm` or `R`; `F`; `H`; `V`; `A`; `Hz`; `W`; `s`), with optional blanks between number and prefix; or the IEC 60062 letter code, where the prefix letter, or `R` for ohms, stands for the decimal point (`4k7`, `2R2`, `1n5`).
- A `float`, a `bool`, a symbol of another unit, a text that does not parse, or a negative value for a unit other than volts and amperes MUST raise `DslError` naming the input.
- **Value.** The value MUST be held as a `Fraction` of the unit. Equality, ordering and hashing MUST compare the unit and the exact value; ordering between different units MUST raise `TypeError`.
- **Arithmetic.** `+` and `-` MUST take two quantities of one unit; `*` and `/` MUST take an `int` or a `Fraction`; any other operand MUST raise `TypeError`.
- **Text.** `text()` MUST print the value scaled by the largest SI prefix, in steps of 1 000 from `p` to `G`, that keeps its magnitude at least 1 (no prefix between 1 and 1 000), as the shortest exact decimal, followed by the prefix (`u` for micro) and the symbol (`Ω`, `F`, `H`, `V`, `A`, `Hz`, `W`, `s`). A value that is not a terminating decimal at that scale MUST raise `DslError`. `text(code=True)` MUST print the IEC 60062 letter code for ohms, farads and henries, the prefix letter (or `R` without a prefix, for ohms) standing for the decimal point and no symbol, and MUST raise `DslError` for the other units.
- No quantity MUST reach the model or `.fenolite/`: it is a script value.

#### Scenario: Equal forms
- **WHEN** `ohm("4k7")`, `ohm("4.7k")`, `ohm("4.7 kΩ")` and `ohm(4700)` are compared
- **THEN** they are equal, have one hash, and `text()` of each is `4.7kΩ`

#### Scenario: Canonical texts
- **WHEN** `farad("0.1u").text()`, `volt("3.30").text()`, `hertz(16_000_000).text()` and `ohm("2R2").text(code=True)` are computed
- **THEN** they are `100nF`, `3.3V`, `16MHz` and `2R2`

#### Scenario: Float refused
- **WHEN** `ohm(4.7e3)` is called
- **THEN** `DslError` is raised naming the value

#### Scenario: Wrong unit
- **WHEN** `farad("10V")` is called
- **THEN** `DslError` is raised naming `10V`

### Requirement: Part values from quantities
`Part(ref, lib_id, footprint=None, value="")` SHALL accept a `Quantity` as `value` and SHALL store its `text()`; a string value MUST keep working unchanged.
- The model's `Component.value` MUST be that text, so two parts given equal quantities have equal values whatever their spelling in the script.

#### Scenario: One value for two spellings
- **GIVEN** `Part("R1", "Mini:Mini_R", value=ohm("4k7"))` and `Part("R2", "Mini:Mini_R", value=ohm("4700"))` in one design
- **WHEN** `to_model` runs
- **THEN** both components have the value `4.7kΩ`

### Requirement: Typed interfaces in the DSL
`fenolite.dsl.interfaces` SHALL define `I2C(sda, scl, *, name=None)`, `SPI(sck, mosi, miso, *, cs=(), name=None)`, `UART(tx, rx, *, name=None)` and `USB2(dp, dn, *, vbus=None, gnd=None, name=None)`, subclasses of `Interface` re-exported by `fenolite.dsl` (an addition under "DSL package"), which record buses as model `Interface` entities without any model delta. This requirement extends "Interfaces in the DSL", whose rules hold for them.
- Kinds and members: `I2C` gives kind `i2c` with `sda` and `scl`; `SPI` gives `spi` with `sck`, `mosi`, `miso` and `cs0` … `cs<n-1>` for the nets of `cs` in order; `UART` gives `uart` with `tx` and `rx`, named from device A; `USB2` gives `usb2` with `dp` and `dn`, and `vbus` and `gnd` when given.
- Every argument naming a net MUST be a `Net`; two members of one interface MUST be distinct nets; otherwise `DslError` is raised. A net MAY be a member of several interfaces.
- The default name MUST be `"<first net name>/<second net name>"`, and the id MUST be `derived_id("itf", "dsl", "interface:<kind>:<name>")`. Member nets join the design.
- A KiCad build MUST keep the four kinds in `.fenolite/`, and the written KiCad files outside it MUST NOT depend on them.

#### Scenario: I2C in the model
- **GIVEN** `I2C(sda, scl)` on the nets `SDA` and `SCL`, added to a design
- **WHEN** `to_model` runs
- **THEN** the model holds an `Interface` named `SDA/SCL` with kind `i2c` and members `sda` and `scl` equal to the ids of the two nets

#### Scenario: SPI chip selects
- **GIVEN** `SPI(sck, mosi, miso, cs=(cs_flash, cs_adc))`
- **WHEN** `to_model` runs
- **THEN** the interface has the members `sck`, `mosi`, `miso`, `cs0` (the net of `cs_flash`) and `cs1` (the net of `cs_adc`)

#### Scenario: One net twice
- **WHEN** `USB2(dp, dp)` is called
- **THEN** `DslError` is raised naming the net

### Requirement: Attaching parts to interfaces
Each typed interface SHALL provide `attach(part, **roles)`, which connects pins of one part to the interface's nets by role through `connect`, so that every rule of `connect` applies.
- `I2C.attach(part, *, sda, scl)` and `USB2.attach(part, *, dp, dn, vbus=None, gnd=None)` MUST connect each given pin to the net of its role. A role whose net the interface does not have (`vbus` on a `USB2` without `vbus`) MUST raise `DslError`.
- `UART.attach(part, *, side, tx, rx)`: with `side="a"` the `tx` pin MUST join the `tx` net and the `rx` pin the `rx` net; with `side="b"` the `tx` pin MUST join the `rx` net and the `rx` pin the `tx` net. Any other `side` MUST raise `DslError`.
- `SPI.attach(part, *, role, sck, mosi, miso, cs=None, cs_index=None)`: `sck`, `mosi` and `miso` MUST join the nets of their names. With `role="controller"`, `cs` MUST be a sequence with one pin per chip-select net, joined in order, and `cs_index` MUST be `None`. With `role="peripheral"`, `cs` MUST be one pin and `cs_index` the index of its chip-select net. Any other combination MUST raise `DslError`.
- A pin argument MUST be a pin handle of `part`, or a designator, which MUST be resolved as `part[designator]`. A pin handle of another part MUST raise `DslError`.

#### Scenario: UART crossed for the second device
- **GIVEN** `uart = UART(a_tx, a_rx)`, `uart.attach(u1, side="a", tx=u1["TX"], rx=u1["RX"])` and `uart.attach(u2, side="b", tx=u2["TX"], rx=u2["RX"])`
- **WHEN** `to_model` runs
- **THEN** the net of `a_tx` holds `U1` pin `TX` and `U2` pin `RX`, and the net of `a_rx` holds `U1` pin `RX` and `U2` pin `TX`

#### Scenario: SPI peripheral on its chip select
- **GIVEN** the SPI of "SPI chip selects", a controller `U1` attached with `cs=(u1["CS0"], u1["CS1"])`, and a peripheral `U3` attached with `cs=u3["CS"]` and `cs_index=1`
- **WHEN** `to_model` runs
- **THEN** the net of `cs_adc` holds `U1` pin `CS1` and `U3` pin `CS`, and the net of `cs_flash` holds only `U1` pin `CS0`

#### Scenario: Pin of another part
- **WHEN** `bus.attach(u1, sda=u2["SDA"], scl=u1["SCL"])` is called on an `I2C`
- **THEN** `DslError` is raised naming `U2`, and nothing is connected

### Requirement: Interface checks in a build
A build SHALL check the interfaces of the design after the parts are resolved, as "Built project files" allows for added steps of `build_design`, and SHALL report two warnings, which join the closed build set ("Build issue codes"):

| code | severity | when |
|---|---|---|
| `build.diff-pair-name` | warning | the two nets of a `diff_pair` (`p`, `n`) or `usb2` (`dp`, `dn`) interface do not form a KiCad differential pair by name |
| `build.i2c-pullup-missing` | warning | an I2C line has no two-pin part to the `hv` net of a `power` interface |

- **Pair names** (`H-K-DIFFPAIR-NAMES`). The names, in KiCad's stored form, form a pair when they are equal except for the last character, which is `P` for the first net and `N` for the second, or `+` and `-`; letter case counts. The hint MUST propose a second name: the first name with its last character `P` or `+` replaced by `N` or `-`; when the first name ends in neither, it MUST propose `<first name>_P` and `<first name>_N`.
- **Pull-ups.** For the `sda` and `scl` nets of each `i2c` interface, a pull-up is a component whose resolved symbol has exactly two pins, one on that net and the other on the `hv` net of a `power` interface of the design. The issue MUST name the interface and the line.
- The checks MUST NOT change any file or the model, and a design without interfaces MUST give neither code.

#### Scenario: Pair names that KiCad does not pair
- **GIVEN** a blink variant with `USB2(usb_dp, usb_dm)` on the nets `USB_DP` and `USB_DM`
- **WHEN** it is built with `--dry-run --json`
- **THEN** `issues` hold one `build.diff-pair-name` naming `USB_DP` and `USB_DM`, with a hint naming `USB_DN`, and one `build.interface-not-lowered`

#### Scenario: Pair names that KiCad pairs
- **WHEN** the same variant uses the nets `USB_P` and `USB_N`
- **THEN** `issues` hold no `build.diff-pair-name`

#### Scenario: Missing pull-up
- **GIVEN** a design with `Power(vdd, gnd)`, `I2C(sda, scl)`, a resistor from `SDA` to `VDD` and none on `SCL`
- **WHEN** it is built with `--dry-run --json`
- **THEN** `issues` hold one `build.i2c-pullup-missing` naming the interface and `scl`

## MODIFIED Requirements

### Requirement: Interfaces in the DSL
`Interface(name, kind, members)`, `Power(hv, lv, *, name=None)` and `DiffPair(p, n, *, name=None)` SHALL record groups of nets as model `Interface` entities, without any model delta.
- `Power(hv, lv)` MUST become `Interface(kind="power", members={"hv": <net id>, "lv": <net id>})`, and `DiffPair(p, n)` MUST become `Interface(kind="diff_pair", members={"p": <net id>, "n": <net id>})`.
- The default name MUST be `"<first net name>/<second net name>"`.
- Member nets join the design.
- Interfaces are not lowered to KiCad. A build MUST give one `build.interface-not-lowered` info per `diff_pair` and per `usb2` interface ("Typed interfaces in the DSL"), and the nets of each such pair MUST pass the name check of "Interface checks in a build".

#### Scenario: Power interface
- **GIVEN** `Power(vin, gnd)` added to a design
- **WHEN** `to_model` runs
- **THEN** the model holds an `Interface` named `VIN/GND` with kind `power` and members `hv` and `lv` equal to the ids of `VIN` and `GND`

#### Scenario: Diff pair reported
- **GIVEN** a blink variant holding `DiffPair(usb_p, usb_n)` on nets `USB_P` and `USB_N`
- **WHEN** it is built with `--dry-run`
- **THEN** `issues` holds one info `build.interface-not-lowered` naming `USB_P/USB_N`

#### Scenario: Diff pair names checked
- **GIVEN** a blink variant holding `DiffPair(clk_p, clk_n)` on nets `CLK_P` and `CLKN`
- **WHEN** it is built with `--dry-run --json`
- **THEN** `issues` hold one info `build.interface-not-lowered` naming `CLK_P/CLKN` and one warning `build.diff-pair-name` naming both nets
