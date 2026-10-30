## Context

- **Source.** `docs/research/circuit-as-code.md` (2026-10-29), section 5 "Interfaces with parameters,
  connected as a whole" and core change E. Concepts come from atopile (alias and sum parameters, a logic
  line with a reference rail, checks that travel with the interface type) and JITX (typed bundles connected
  and type-checked as a whole). No code, grammar, schema, library element name, constant or table of
  those projects is copied.
- **What exists on `dev` (0.6.0).**
  - `dsl/interfaces.py`: `Interface(name, kind, members)` and its subclasses:
    - `Power(hv, lv)` (kind `power`) and `DiffPair`;
    - `Harness`;
    - the buses `I2C`, `SPI`, `UART` and `USB2`, with `attach(part, **roles)`.

    None of them has parameters.
  - `model.circuit.Interface(name, kind, members)` and `power_interface_nets(circuit)`. The latter is the
    one set of "declared supplies" that ERC lite, the schematic writer's power flags and `fenolite ready`
    read.
  - `build.i2c-pullup-missing` (`lens/build.py`): a two-pin part from each I2C line to the `hv` net of a
    `power` interface.
  - `fenolite check` stages (`checks/stages.py`), with the closed table `checks.codes.ISSUE_CODES`. A stage
    may read the `.fenolite/` model.
- **What this change builds on.**
  - c0246's ranges (`volt("3.3").pct(3)`, `between`, `.min`, `.max`, `within`), with exact `ValueRange`s in the
    model.
  - c0248's device records and checked pin access.
  - c0251's block ports, port nets (the binding and naming rule) and the model `Port`.
  - c0247's `pull_up`.
- **Today vs proposed.** Today (`docs/research/circuit-as-code.md`, the last example, reduced):

  ```python
  v33, sda, scl = Net("3V3"), Net("SDA"), Net("SCL")
  connect(v33, l1[2], u2["VDD"], u3["VDD"], r3[1], r4[1])
  connect(sda, u2["PB7"], u3["SDA"], r3[2])
  connect(scl, u2["PB6"], u3["SCL"], r4[2])
  bus = I2C(sda, scl)
  design.add(bus, Power(v33, gnd))
  # Nothing checks the 3V3 current budget, the sensor's VDD range or the pull-up rail.
  ```

  Proposed:

  ```python
  power = design.use(buck, "buck", vout=volt("3.3").pct(3), current=amp(1))  # c0251 block
  gnd = design.ground("GND")
  v33 = design.rail("3V3", ground=gnd)  # voltage comes from the source port
  connect(v33, power.VOUT)
  connect(gnd, power.GND)

  mcu = design.part(device="Example:MCU_QFN32")  # c0248 device; declares vdd, gnd, i2c1, pa3
  sen = design.part(device="Example:SENSOR_I2C")  # declares vdd, gnd, i2c, int_
  connect(v33, mcu.vdd, sen.vdd)
  connect(gnd, mcu.gnd, sen.gnd)
  connect(mcu.i2c1, sen.i2c)  # SDA-SDA, SCL-SCL, through port nets
  connect(sen.int_, mcu.pa3)  # logic out -> logic in
  r_sda, r_scl = (design.part(device="Fenolite:R_0603_4k7") for _ in range(2))  # illustrative device
  pull_up(mcu.i2c1, v33, r_sda, r_scl)  # c0247 helper, widened to an i2c port
  ```

  `fenolite build` and `fenolite check` then report, for example:
  - `circuit.rail-current`: `3V3: loads up to 1.15 A exceed sources 1 A (buck.VOUT)`;
  - `circuit.rail-voltage`: `sen.vdd accepts 1.71–3.6 V; 3V3 is 3.201–3.399 V`. This is no finding, since
    the rail's range lies within it.

## Goals / Non-Goals

**Goals**

- An interface states its electrical parameters once (a rail's voltage, a source's capacity, a load's draw,
  an input's accepted range), and a connection carries them without user arithmetic.
- Whole interfaces connect in one statement, with a type check at the call.
- The faults of the proposal's list are found from the model alone, with no tool, and are explained with
  the numbers, the ports and the source of each limit.
- Existing scripts, models and outputs keep their bytes.

**Non-Goals**

- See the proposal. Also: no automatic choice of a rail for a port, no voltage domains inferred from
  names, and no change of `attach()`, which stays the pin-by-pin form.

## Decisions

### 1. Parameter semantics: alias, sum, bound, link

Each kind has a closed table, `fenolite.dsl.interfaces.PARAMETERS`, which `checks.circuit` mirrors on the
model side. Value units are c0246's unit names (`volt`, `ampere`, `ohm`):

| kind | parameter | semantics | unit | on an `out` port | on an `in` port | on an `inout` port | on the design interface |
|---|---|---|---|---|---|---|---|
| `power` | `voltage` | alias | volt | sets (an operating promise) | bounds (the operating range accepted) | bounds | sets (the declared range) |
| `power` | `current` | sum | ampere | adds capacity | adds draw | refused | refused |
| `logic`, buses | `abs_max` | bound | volt | the range the pin withstands | as `out` | as `out` | refused |
| `logic`, buses | `input_high_min`, `input_low_max` | bound | volt | refused | the input thresholds | the input thresholds | refused |
| `logic`, buses | `output_high_min`, `output_low_max` | bound | volt | the output levels | refused | the output levels | refused |
| `logic`, buses | `output_current_max` | bound | ampere | the most current the output sinks or sources at its levels | refused | as `out` | refused |
| `logic`, buses | `reference` | link | (a port or rail) | the reference rail | the reference rail | the reference rail | the reference rail |
| `i2c` | `pullup` | bound | ohm | refused | the accepted pull-up range | the accepted pull-up range | the accepted pull-up range |

"Buses" are `i2c`, `spi`, `uart` and `usb2`. A threshold is one quantity (a degenerate c0246 range) or a
one-sided range (`volt("1.3").min()`); each comes from the part's datasheet, through the device record or the
block author, never from a shipped table.

- **alias:** one value per connected group, the rail. The design interface and `out` ports *set* it. When
  several values are set, they must agree: the rail's value is their intersection, and an empty
  intersection is `circuit.rail-voltage`. Values on `in` ports *bound* it: the rail's range must lie within
  each of them (c0246's `within`).
- **sum:** `out` ports add capacity and `in` ports add draw. The check is the worst case: the sum of the
  draws' upper bounds must not exceed the sum of the capacities' lower bounds. A source states the
  capacity it guarantees: an exact value, or a range whose lower bound it guarantees.
  - **Direction is mandatory.** `current` is accepted only on a port whose direction was given explicitly
    as `in` or `out`. On an `inout` port, the default of c0251, it raises `DslError` ("say whether this port
    draws or sources current"), and a device `[[interfaces]]` table with `current` and `direction = "inout"`
    is refused. A pass-through port (a connector, a jumper, a test point) is `inout` and states no current.
  - **Loads against sources, never all ports.** Draws are never added to capacity, and capacity is never
    added to draws. Summing every port of both sides would compare a number with itself and could never
    fail; the scenario "1.2 A load on a 1 A source" keeps that mistake out.
- **bound:** a limit of one port, compared with the value that reaches it.
- **link:** `reference` names the rail that a logic level or a bus refers to. On a device port it names
  another port of the same device (`reference = "vdd"`). On a design interface or block port it is a
  `Rail` or a power port handle.
- `inout` power ports (a connector, a jumper, a test point) neither set nor add. Their `voltage`, when
  given, is a bound.
- **Operating values, not absolute limits.** A power port's `voltage` is an operating range: what an `in`
  port needs to work, what an `out` port promises. It is judged by `circuit.rail-voltage` exactly, never
  derated. Absolute maximum ratings live on the device's pins (c0248, split into `abs_max` and `operating`
  by c0274) and are c0253's, with the derating policy. The logic `abs_max` above is the one absolute value
  an interface carries, because the logic check needs it at the port.
- A parameter that the table does not allow for the kind and direction raises `DslError` at the call.
- **Alternatives considered.**
  - A general constraint solver (atopile). Rejected, as in the research page's "What we deliberately do not
    copy".
  - Nominal values with a tolerance field. Rejected: c0246's ranges already carry both, exactly.

### 2. `Rail`, `Ground`, `Logic`; `Power` kept

- `Rail(hv, lv=None, *, name=None, voltage=None, shared=False)`: model kind `power`, members `hv` and, when
  given, `lv`. The default name is `<hv>/<lv>`, or `<hv>` without `lv`.
- `Power` is the same class (`Power = Rail`). `Power(vin, gnd)` gives today's model bytes exactly: same
  kind, members, name and id, and no parameter. `power_interface_nets` therefore covers rails with no
  change, and ERC lite, the power flags and `ready` see rails as declared supplies.
- `Ground(gnd, *, name=None)`: kind `ground`, member `gnd`. Default name: the net name.
- `Logic(io, *, name=None, reference=None)`: kind `logic`, member `io`. Default name: the net name.
- **Main members**, which make an interface net-like: `power` → `hv`, `ground` → `gnd`, `logic` → `io`.
  The closed member table of c0251 gains `ground` (`gnd`) and `logic` (`io`).
- `design.rail(name, *, voltage=None, ground=None, shared=False) -> Rail` creates and adds `Net(name)` and
  the `Rail`. `ground` is a `Ground` or a `Net`, and gives `lv`. `design.ground(name) -> Ground` does the
  same for a ground.
- **Alternative considered:** a new model kind `rail` with a migration of `power`. Rejected: it would change
  the bytes and the ids of every model with a `Power`.

### 3. Net-like interfaces and `connect()` between whole interfaces

`connect(first, *rest)` keeps its current form and gains two:

1. **Net form**, as today. `first` is a `Net`, a port net, or a net-like interface or port, and `rest` holds
   pins, port nets, or net-like interfaces and ports. Each acts through its main member. A net-like
   argument in `rest` must be compatible with `first` (decision 4).
2. **Interface form.** Every argument is an interface or a port of more than one member, or all arguments
   are interfaces or ports. Each member joins the member of the same name of every other argument,
   through c0251's port nets. A member that only some arguments have joins when it is optional in the kind
   table (`power.lv`, `usb2.vbus`, `usb2.gnd`). Otherwise it raises `DslError`. Nothing is connected when
   one pair is refused.

- **Net names.** The c0251 rule applies unchanged: the group's one script-named net, or the path of its
  preferred port member. For example, `connect(mcu.i2c1, sen.i2c)` alone names the nets `U2/i2c1.scl` and
  `U2/i2c1.sda` (U2 being the MCU's component path). With `connect(I2C(sda, scl), mcu.i2c1, sen.i2c)` they
  are `SDA` and `SCL`.
- **UART.** Two UART ports (device or block, both named from their own side) cross: `tx` joins `rx`. A
  `UART` bus interface (named from device A) joined to a port raises `DslError`, with a hint to use
  `attach(side=...)`, because the side is not known.
- **SPI.** Member sets must be equal (same number of chip selects). A peripheral with one `cs` keeps
  `attach(role="peripheral", cs_index=...)`.
- **Parameters across `connect`.** Nothing is copied. The checks read each port's own values from the
  model and group them by net (decision 6).

### 4. Compatibility table

| first \ other | `net` | `power` | `ground` | `logic` | `i2c` | `spi` | `uart` | `usb2` | `diff_pair` | `harness` |
|---|---|---|---|---|---|---|---|---|---|---|
| `net` (a Net, a port net or a Net port) | yes | main | main | main | – | – | – | – | – | – |
| `power` | main | yes | – | – | – | – | – | – | – | – |
| `ground` | main | – | yes | – | – | – | – | – | – | – |
| `logic` | main | – | – | yes | – | – | – | – | – | – |
| `i2c`, `spi`, `uart`, `usb2`, `diff_pair` | – | – | – | – | same kind only | | | | | |
| `harness` | – | – | – | – | – | – | – | – | – | same entry names |

`main` means joined through the main member. `–` raises `DslError` naming both kinds and both names, for
example "cannot connect ground `GND` to power port `buck1/VIN`". A logic line joins a bus member through
the member's port net (`connect(mcu.pa3, bus.sda)`), which is the net form.

### 5. Ports with parameters and device ports

- **Block ports (c0251):** `b.port(name, kind, *, direction=..., optional=..., requires=(), **params)` and
  `handle.set(**params)`. Each parameter can be set once, and only as decision 1 allows. `reference` takes
  a power port handle of the same block or a `Rail`. `requires` is decision 7's companion list.
- **Device ports.** c0248's device record (`fenolite.device.v0`) reserves the key `interfaces`; this change
  defines it as an array of tables. Members name c0248 *functions* (the keys of `[pins]`), not raw pin
  numbers, and parameter values use c0248's `{ min = "...", max = "..." }` spelling. An illustrative record,
  authored for Fenolite:

  ```toml
  [[interfaces]]
  name = "vdd"
  kind = "power"
  direction = "in"
  members = { hv = ["VDD", "VDDA"], lv = ["VSS"] }     # c0248 function names
  voltage = { min = "1.71V", max = "3.6V" }             # operating range accepted
  current = { max = "12mA" }                           # draw
  evidence = "UNVERIFIED"                               # c0248's evidence vocabulary

  [[interfaces]]
  name = "i2c1"
  kind = "i2c"
  direction = "inout"
  members = { sda = ["PB7"], scl = ["PB6"] }
  reference = "vdd"
  requires = ["pullup", "supply"]
  abs_max = { min = "-0.3V", max = "3.9V" }
  input_high_min = "1.3V"
  input_low_max = "0.5V"
  output_low_max = "0.4V"
  output_current_max = "3mA"
  ```

  These are *operating* values and thresholds of an interface. The device's absolute maximum ratings are
  its pins' `abs_max` and its `[ratings]` (c0248, as c0274 splits them), which c0253 judges with derating.
  A threshold is one quantity text; a range keeps c0248's `{ min, max }` spelling. A missing `min` reads as
  0 for a draw and as unbounded for a voltage, as c0248 reads its ratings.

  Catalog validation refuses:
  - a kind or member outside the tables;
  - a function that the device does not have;
  - a function in two members of one interface;
  - a `reference` that names no `power` port of the device;
  - a parameter that decision 1 does not allow, `current` on an `inout` interface included;
  - a `requires` entry outside decision 7's vocabulary, or one that the kind does not take;
  - an interface name equal to a function of the device or to an attribute of `Part`.
- `part.port(name)` and `part.<name>` return a `PortHandle` whose members are the part's pins, through
  port nets owned by the component path. `to_model` gives one model `Port` per declared port, owned by the
  component, with the net of each member. The port parameters come from the device data that c0248 attaches
  to the part.
- A member whose pins end on two different nets (a user split `VDD` and `VDDA`) is left out of the model
  port's `members` and gives `circuit.port-split`, and its parameters are not judged.

### 6. The checks: stage `circuit.rules`

- **Package.** This change creates the package `checks/circuit/`, the one home of every `circuit.*` judge of
  the batch. `rails.py` imports `model` only and holds the rail, logic, bus, companion and port rules. The
  package exposes `circuit_issues(model) -> tuple[Issue, ...]`; c0253 adds its modules to the same package
  and a keyword to the same function, and creates no other.
- **Stage.** The stage `circuit.rules` is a default stage of `fenolite check`. It stands right after
  `model.validate` in `STAGE_ORDER` and in `DOCUMENT_STAGES`. It is not in `ORACLE_STAGES` and runs no
  tool. It reads the `.fenolite/` model of a built project. This change creates it (step 4); c0253 (step 5)
  adds its checks to it.
- **Skip vocabulary.** The batch has one vocabulary for this stage, shared with c0253:
  - `no-model`: there is no `.fenolite/` model (a native board), or it cannot be read (`read-refused` and
    `cache-unreadable` keep their meaning, as for `placement.rules`);
  - `no-parameters`: the model holds no parameter, no `ground` or `logic` interface, no port and no
    `requires`, so the rail half has nothing to judge;
  - `no-contracts`: c0253's, for the contract half.

  The stage is skipped with `no-model`, or with `no-parameters` when the contract half also has nothing
  (`no-contracts`). When it runs, `summary.halves` names the state of each half (`ran`, `no-parameters`,
  `no-contracts`), so a reader sees which half judged.
- **Build.** `cmd_build` calls `circuit_issues` on the model it builds and adds the issues to the build
  envelope, as later codes of "Build issue codes". An error stops the write, as every build error does.
  Waivers of `circuit.*` codes come with c0274 (a waiver keyed on the judged value's digest).
- **Rails.** A rail is an `hv` net of a `power` interface or of a `power` port. For each rail:
  - **voltage V:** the intersection of the values set by design interfaces and `out` ports;
  - **sources:** `out` power ports on the rail;
  - **loads:** `in` power ports;
  - **neither:** `inout` power ports, which state no current;
  - **hiding:** a block's `out` port hides the `out` ports of its own parts and inner blocks on the same
    rail, because the block's promise replaces them. A block's `in` port that states `current` hides the
    `in` ports inside it on that rail.

| code | severity | when | message example |
|---|---|---|---|
| `circuit.rail-voltage` | error | the set values do not intersect; or V is not within the operating range accepted by an `in` port | `sen.vdd accepts 1.71–3.6 V; 5V0 is 4.75–5.25 V` |
| `circuit.rail-current` | error | the sum of the loads' upper draws exceeds the sum of the sources' lower capacities | `3V3: loads up to 1.15 A exceed sources 1 A (buck.VOUT)` |
| `circuit.rail-sources` | error | two or more sources on a rail, unless the rail is `shared` or every source port has `share` | `buck1.VOUT and J2.vbus both drive 5V0` |
| `circuit.rail-unset` | warning | the ports on a rail state limits but no voltage is set; or loads state draw and no source states capacity | `3V3: no voltage is set; sen.vdd needs one to be judged` |
| `circuit.logic-level` | error | one of the three comparisons below fails | `sen.int_ drives mcu.pa3: output high 2.4 V is below input high 2.6 V` |
| `circuit.logic-unknown` | warning | the reference rails differ and a threshold that a comparison needs is not stated | `mcu.pa3 states no input_low_max` |
| `circuit.bus-pullup` | warning | a pull-up goes to a rail other than the bus's reference rail; its resistance range is not within the accepted `pullup` range; or its worst-case current exceeds a bus port's `output_current_max` | `SDA pulled up to 5V0; bus reference is 3V3` |
| `circuit.requires-missing` | warning | a port's declared companion is absent (decision 7) | `sen.i2c requires a pull-up on SCL` |
| `circuit.port-split` | warning | the pins of one member of a device port are on two nets | |

- **Logic.** A driver is an `out` logic port, or an `inout` port that states output levels. A reader is an
  `in` or `inout` logic port on the same net. Two ports with the same reference rail always pass: the
  datasheet levels of one supply domain are the part's own business. Otherwise three comparisons, each
  worst case:
  1. **high:** the driver's `output_high_min` is at least the reader's `input_high_min`;
  2. **low:** the driver's `output_low_max` is at most the reader's `input_low_max`;
  3. **withstand:** the upper bound of the driver's reference rail is at most the upper bound of the
     reader's `abs_max`.

  A comparison whose threshold is not stated gives `circuit.logic-unknown` naming the missing key; it is
  never passed by assuming that the driver's level is its rail.
- **I2C.** The high level comes from the pull-up rail, so on an I2C line the pull-up rail is the driver of
  comparison 1 (its lower bound stands for `output_high_min`) and comparison 3. Every bus port that states
  `output_low_max` is a driver of comparison 2 for every other port.
- **Bus reference.** The bus interface's `reference`, else the reference shared by all its ports. When the
  ports disagree, the pull-up rail is compared with each port as a logic reader.
- **Pull-up resistance.** The range is the part's c0246 value range when the part carries one (c0247,
  c0248), else its exact value. It is compared with the intersection of the `pullup` bounds of the bus and
  its ports. Its worst-case current, the pull-up rail's upper bound over the resistance's lower bound, is
  compared with each bus port's `output_current_max`. No range comes from a standard in this change (open
  question 3).
- **Evidence.** A finding's evidence is `INFERRED`, or the lowest evidence of the device rows it judged,
  whichever is lower. Every finding names its numbers in c0246's canonical text, its ports by path, and
  where each limit came from: `design.rail`, a block port, or a device record with its id.
- `checks.codes.ISSUE_CODES` gains the nine codes. `docs/cli-contract.md` and `explain.toml` document them.

### 7. Companions: `requires`

A port may state what must be connected for it to work. The vocabulary is closed:

| entry | kinds | met when |
|---|---|---|
| `pullup` | `i2c`, `logic` | each line (`sda` and `scl`, or `io`) has a pull-up as "Interface checks in a build" defines it |
| `supply` | `logic` and buses with a `reference`; `power` `in` ports | the reference port's `hv` net (or the port's own) is a rail with a voltage set and a source, or a rig supply (c0253) |
| `chip_select` | `spi` | each `cs` member is on a net with at least one other pin |

- A device states it in its `[[interfaces]]` table (`requires = ["pullup", "supply"]`), a block author on
  `b.port(..., requires=(...))`. It is recorded on the model `Port` as a sorted tuple.
- Each unmet entry gives one `circuit.requires-missing` warning naming the port, the entry and what is
  missing. A port that is not connected at all is left to the existing open-net and unconnected-pin checks.
- **Alternative considered:** one code per entry (`circuit.pullup-missing`, ...). Rejected: the vocabulary
  will grow (c0257, c0258), and one code with the entry in the message keeps the code table closed.

### 8. Pull-up on a bus and `build.i2c-pullup-missing`

- c0247's `pull_up(target, rail, *resistors)` takes a `Net` (one resistor) or an `I2C` interface (two
  resistors: the first on `sda`, the second on `scl`). This change widens `target`, as c0247 decision 4
  foresees:
  - an `i2c` port (device or block) takes two resistors, in the same order;
  - a `Logic` interface or a `logic` port takes one resistor, on its `io`;
  - a net-like `Rail` port is accepted as `rail`.

  Each resistor joins as in c0247 (its `a` end on the line, its `b` end on the rail). Nothing else is
  recorded.
- `build.i2c-pullup-missing` keeps its code and severity. A pull-up's other pin may now be on the `hv` net
  of a power port as well as on that of a `power` interface, because a rail may be declared only by device
  or block ports. Whether it is the *right* rail is `circuit.bus-pullup`.

### 9. Model

- `model.circuit.Interface` gains:
  - `params: dict[str, ValueRange]` (c0246's model range: exact decimals as integer mantissa and exponent);
  - `reference: str | None = None`: the id of a `power` interface;
  - `shared: bool = False`.
- c0251's `Port` gains:
  - `params`;
  - `reference: str | None = None`: the id of a `power` port or interface;
  - `share: bool = False`;
  - `requires: tuple[str, ...] = ()`, sorted (decision 7).
- Each field is omitted when empty or default, so old `circuit.json` files keep their bytes.
- **Encoding.** Every parameter is a c0246 `ValueRange` in c0246's encoding: the unit *name* (`volt`,
  `ampere`, `ohm`), and `low`, `nominal` and `high` as `Decimal10` objects (integer mantissa `m` and
  exponent `e`), each omitted when absent. No `min`/`max` text and no unit symbol is written. Example (ids
  shortened):

  ```json
  {"interfaces": [{"id": "itf_…", "kind": "power", "members": {"hv": "net_…(3V3)", "lv": "net_…(GND)"},
     "name": "3V3/GND"}],
   "ports": [{"direction": "out", "id": "prt_…", "kind": "power", "members": {"hv": "net_…(3V3)"},
     "name": "VOUT", "owner": "mod_…(buck)",
     "params": {"current": {"high": {"e": 0, "m": 1}, "low": {"e": 0, "m": 1},
                            "nominal": {"e": 0, "m": 1}, "unit": "ampere"},
                "voltage": {"high": {"e": -3, "m": 3399}, "low": {"e": -3, "m": 3201},
                            "nominal": {"e": -1, "m": 33}, "unit": "volt"}}},
     {"direction": "in", "id": "prt_…", "kind": "power", "members": {"hv": "net_…(3V3)"},
     "name": "vdd", "owner": "cmp_…(U3)", "requires": ["supply"],
     "params": {"voltage": {"high": {"e": -1, "m": 36}, "low": {"e": -2, "m": 171}, "unit": "volt"}}}]}
  ```

- New model kinds: `ground` and `logic`. `power_interface_nets` is unchanged and still reads kind `power`
  only.

### 10. Codes and errors

- New check and build issue codes: the nine `circuit.*` codes of decision 6.
- New skip reasons: `no-model` and `no-parameters` (decision 6; c0253 adds `no-contracts`).
- New `DslError` cases, each reported by `cmd_build` as `FEN-3004`:
  - an incompatible `connect` pair;
  - a missing required member;
  - a parameter not allowed for its kind or direction, or set twice;
  - `current` on a port whose direction is not `in` or `out`;
  - a `requires` entry outside the vocabulary or not taken by the kind;
  - a bad `reference`;
  - a UART bus joined to a port.
- No new `FEN-` code. The research sketch's "FEN- finding on a type mismatch" becomes a `DslError` at the
  call, which is earlier and points at the line.

## Risks / Trade-offs

- **Device data quality.** The checks are only as good as the `[[interfaces]]` values. Mitigation: each value
  carries c0248's evidence label, findings carry the lowest, and `UNVERIFIED` rows are shown as such.
- **False confidence from missing data.** A rail with no values gives no finding. Mitigation:
  `circuit.rail-unset` and `circuit.logic-unknown` say what could not be judged, and the stage summary
  counts judged and unjudged rails.
- **Build stops on circuit errors.** A real `circuit.rail-current` blocks the write. That is intended, and a
  waiver (c0274) states an accepted risk. Open question 1 asks whether 0.7 should start with warnings.
- **Thresholds missing from device data.** Most records will first state no logic thresholds, so mixed-rail
  connections give `circuit.logic-unknown`. That is intended: the alternative, assuming the driver's level
  is its rail, passes a 3.3 V output into a 5 V input whose high threshold is 3.5 V.
- **Auto-named nets from port-to-port connections** (`U2/i2c1.sda`). Mitigation: documented, and naming a
  bus interface first gives readable names.

## Open Questions

1. **Should `circuit.*` errors block `build --confirm` in 0.7?** Recommended: yes, with c0274's waivers. This is
   consistent with the other build errors, and the checks fire only on values the user or a device record
   stated.
2. **Should `Power` print a deprecation hint?** Recommended: no. It stays a silent alias, and the docs
   teach `Rail`.
3. **Should the I2C pull-up range be derived from a public method** (the bus specification's formulas for
   the minimum and maximum pull-up, given the low-level current, rise time and bus capacitance)?
   Recommended: later, in c0258, with the source registered under `docs/evidence/` and its values as user
   inputs. Here the range is the user's or the device's.
4. **Should `logic` ports also exist on single pins without a device record** (`part.logic("PA3",
   reference=v33)`)? Recommended: yes, as a small follow-up, once c0248's records cover the reference
   boards' parts.
5. **Should a bus speed parameter be added now?** Recommended: no. Speed belongs with topologies and
   constraints (c0258).

## Relation to the other changes of this batch

- **c0246 (A):** all values; `within`; canonical texts in messages.
- **c0247 (J):** `pull_up` grows a bus form. `decouple(rail, gnd, ...)` takes net-like rails, which works
  through decision 3 with no change in c0247.
- **c0248 (B):** its reserved key `interfaces` is defined here (`[[interfaces]]` tables). Its evidence labels flow into findings.
- **c0249 (C):** no change. Auto-named nets are not locked; only refs and picks are.
- **c0251 (D):** ports, port nets, naming and the model `Port` are its. This change adds parameters, kinds,
  the interface form of `connect` and device ports.
- **c0253 (F):** adds ratings with derating, `expect()` and `rig()` to the stage `circuit.rules` and to the
  package `checks/circuit/`, reading the rails defined here, with the same skip vocabulary and encoding.
- **c0274 (electrical requirements):** waivers of `circuit.*` findings keyed on a value digest; threshold
  keys on device pins that fill a logic port's missing thresholds; voltage propagated into rails through
  ferrites, fuses and 0 Ω links (with the value's origin); decidable stages and `fenolite check --matrix`
  over the rows of this stage.
- **c0254 (H):** a divider generator can promise a block port's `voltage` from its achieved range.
- **c0256 (K):** test helpers assert on `circuit_issues`.
- **c0257 (L):** chooses pins for a declared interface port. **c0258 (M):** bus speed and topology.
