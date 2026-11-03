## Why

Interfaces in Fenolite 0.6.0 are records of nets. `Power(hv, lv)` says which net is a supply but not its
voltage. `I2C(sda, scl)` says which nets form a bus, but not to which rail its levels refer or which
pull-up it needs. Two interfaces cannot be connected: every member is wired pin by pin
(`bus.attach(u1, sda=u1["PB7"], scl=u1["PB6"])`). As a result nothing can check the faults that a
schematic review catches first:

- a sensor rated 3.6 V on a 5 V rail;
- a 3.3 V rail asked for more current than its regulator gives;
- two regulators tied to one rail;
- a 3.3 V output driving a 1.8 V input;
- an I2C bus pulled up to the wrong rail.

The research of 2026-10-29 (`docs/research/circuit-as-code.md`, section 5 and core change E) takes two
ideas from atopile:

- interface parameters are either *equal across a connection* (a rail has one voltage) or *summed*
  (loads must not exceed sources);
- a logic line carries its reference rail.

From JITX it takes typed bundles that connect as a whole and are type-checked. Only the concepts are
taken. There is no solver: Fenolite compares exact ranges (c0246) and explains each finding.

## What Changes

- **Parameter tables.** Each interface kind gets a closed parameter table. Each parameter is marked `alias`
  (one value per connected rail or bus), `sum` (sources add capacity, loads add draw), `bound` (a limit of
  one port) or `link` (a reference to a rail). Values are exact c0246 ranges (`Range` in the DSL, `ValueRange` in the model, with c0246's
  encoding: unit name, mantissa and exponent), never floats.
- **Direction is mandatory for sum parameters.** A port that states `current` MUST say `direction="in"` (a load) or
  `direction="out"` (a source). A pass-through port (`inout`, c0251's default) states no current. A rail is judged
  as loads against sources, never as all ports summed on both sides.
- **Operating values, not absolute limits.** A power port's `voltage` is the *operating* range it accepts or
  promises, judged by the rail checks and never derated. Absolute maximum ratings stay on the device's pins
  (c0248, split into `abs_max` and `operating` by c0274) and are judged by c0253 with derating.
- **Logic thresholds.** Logic and bus ports take the datasheet thresholds `input_high_min`, `input_low_max`,
  `output_high_min`, `output_low_max` and `output_current_max`, and `abs_max` (the input range it withstands).
  The driver's level is its stated output threshold, never assumed to be its rail.
- **Companions.** A port may declare `requires` (`pullup`, `supply`, `chip_select`): what must be connected
  for it to work, judged as `circuit.requires-missing`.
- **New interface classes.**
  - `Rail(hv, lv=None, *, voltage=None, shared=False)`. `Power` stays as an alias of `Rail`, and the model
    kind stays `power`, so existing scripts and models keep their bytes.
  - `Ground(gnd)`, kind `ground`.
  - `Logic(io, *, reference=None)`, kind `logic`.
  - The buses `I2C`, `SPI`, `UART` and `USB2` take `reference=`, and `I2C` also takes `pullup=` (an
    accepted resistance range).
- **Design helpers.** `design.rail(name, *, voltage=None, ground=None, shared=False)` and
  `design.ground(name)` create the net and the interface in one call.
- **Net-like interfaces.** A `Rail`, a `Ground` or a `Logic` can stand where a net stands:
  `connect(v12, j1[1])` acts on the main member.
- **`connect()` between whole interfaces.** `connect(mcu.i2c1, sen.i2c)` joins each member to the member of
  the same name, through c0251's port nets. A closed compatibility table governs it; an incompatible pair
  raises `DslError` at the call. UART ports cross `tx` and `rx`.
- **Port parameters.** Block ports (c0251) take parameters: `b.port("VOUT", Rail, direction="out",
  voltage=vout, current=amp(2))`, or `port.set(...)` later in the block.
- **Device-declared interface ports.** c0248's device records fill their reserved key `interfaces` with `[[interfaces]]` tables: name, kind,
  direction, member to pin names, parameters and evidence. `part.port("vdd")` and `part.vdd` give the
  port.
- **Pull-up on a bus.** c0247's `pull_up(target, rail, *resistors)` also accepts an `i2c` port (two
  resistors) and a `Logic` interface or port (one resistor).
- **Checks.** A new default stage `circuit.rules` of `fenolite check`, right after `model.validate`, runs no
  tool and reads only the model. This change creates it (step 4), and c0253 (step 5) adds its checks to it.
  The build reports the same findings through `cmd_build`. The codes:
  - `circuit.rail-voltage`, `circuit.rail-current` and `circuit.rail-sources` (errors);
  - `circuit.rail-unset` (warning);
  - `circuit.logic-level` (error) and `circuit.logic-unknown` (warning);
  - `circuit.bus-pullup` (warning): wrong rail, resistance outside the accepted range, or a pull-up stronger
    than a port can sink;
  - `circuit.requires-missing` (warning): a declared companion is absent;
  - `circuit.port-split` (warning).

  The stage is skipped with `no-model` (no `.fenolite/` model) or `no-parameters` (nothing to judge). These
  are the batch's one skip vocabulary, with c0253's `no-contracts` for the contract half of the stage.
- **Pull-up target.** `build.i2c-pullup-missing` now also accepts a pull-up to the `hv` net of a power port,
  not only to that of a `power` interface.
- **Model.** `Interface` and c0251's `Port` gain `params` (name to c0246 `ValueRange`), `reference` and a
  sharing flag, and `Port` gains `requires`. The model kinds `ground` and `logic` are new. Device ports become `Port` entities owned by
  their component. Every new field is omitted when empty.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `design-dsl`:
  - MODIFIED "Interfaces in the DSL" (`Power` is an alias of `Rail`) and "Interface checks in a build"
    (pull-ups to power ports).
  - ADDED "Rail interface", "Ground and logic interfaces", "Rails and grounds of a design", "Interface
    parameters in the DSL", "Port parameters", "Net-like interfaces", "Connecting whole interfaces",
    "Interface compatibility", "Device interface ports in the DSL", "Bus reference rails", "Pull-ups on a
    bus", "Interface companions" and "Circuit findings in a build".
- `design-model`: ADDED "Interface parameters in the model", "Ground and logic kinds in the model" and
  "Device ports in the model".
- `fenolite-component-catalog`: ADDED "Interface ports of a device" and "Refused device interfaces".
- `verification-loop`: ADDED "Circuit stage", "Rail voltage check", "Rail current check", "Rail sources
  check", "Rails without a value", "Logic level check", "Bus pull-up check", "Companion check" and "Split
  device ports".

## Dependencies

- **c0246 quantity-ranges:** every parameter value is a c0246 range, in the DSL and in the model, with
  c0246's `ValueRange` and canonical text.
- **c0247 connection-helpers:** `pull_up` is c0247's helper. This change widens its target to `i2c` ports and `Logic`.
- **c0248 device-catalog:** device records and the part's checked pin access. This change adds their
  `[[interfaces]]` tables (its reserved `interfaces` key).
- **c0251 circuit-blocks:** block ports, port nets, their binding and naming, and the model `Port`. It is
  implemented first, in the same step 4.
- **c0253 electrical-contracts** adds part ratings with derating, `expect()` and `rig()` to the stage
  `circuit.rules`. This change lands first (step 4) and creates the stage and the package `checks/circuit/`.
- **c0274 electrical-requirements** (after c0253): waivers of `circuit.*` findings (with a value digest),
  voltage propagation through ferrites and links, threshold keys on device pins, decidable stages and the
  verification matrix. Until it lands, nothing waives a `circuit.*` finding; 0.7.0 is not released before it.

## Non-goals

- No constraint solver and no parameter propagation beyond the alias and sum rules. A rail's voltage is
  declared or promised, never inferred from equations.
- No ratings of passives against rails (c0253), no divider arithmetic (c0254), and no bus speed or
  capacitance budget (later, with c0258).
- No interface-level pin choice (c0257).
- No change of KiCad or Altium output: parameters live in `.fenolite/` only.
- No numeric default: every limit comes from the user's script or from a device record with its evidence.

## Evidence level required

- Interface connection and lowering: `KICAD-VERIFIED`, from the read-back of the built example through
  `kicad-cli` ("Built boards read back with the same connectivity").
- `circuit.*` findings: `INFERRED`, combined (lowest wins) with the evidence of the device records whose
  parameters were judged.

## Impact

- New:
  - `src/fenolite/dsl/rails.py` (`Rail`, `Ground`, `Logic`, the parameter table, compatibility,
    interface-to-interface `connect`).
  - the package `src/fenolite/checks/circuit/` with `rails.py` (the pure judge `circuit_issues(model)`),
    which c0253 extends with its own modules, and the stage `circuit.rules`.
  - `examples/sensor_rails/` (the board of the research page's last section, with illustrative devices
    authored for Fenolite, in a good and a bad variant).
  - Tests under `tests/unit/dsl/` (`test_rails.py`, `test_interface_connect.py`, `test_device_ports.py`),
    `tests/unit/checks/test_circuit_stage.py`, `tests/unit/catalog/test_device_ports.py` and
    `tests/unit/model/test_circuit.py`.
- Changed:
  - `dsl/interfaces.py` (`Power = Rail`, `reference` and `pullup` on buses), `dsl/part.py` (`connect`,
    `Part.port`), `dsl/design.py` (`rail`, `ground`), `dsl/convert.py` (params, device ports).
  - `model/circuit.py` (`params`, `reference`, `shared`, `share`), the device record loader of c0248,
    `checks/stages.py`, `checks/codes.py`, `cli/cmd_check.py` and `cli/cmd_build.py`.
  - `lens/build.py` (the pull-up target), `cli/data/explain.toml`, `schemas/`.
  - `docs/dsl.md`, `docs/design-model.md`, `docs/cli-contract.md`, `docs/catalog/README.md`.
  - The agent guide pages `design-script`, `checks` and `board-power`, and `CHANGELOG.md`.
- Size: about 10 design-days.
