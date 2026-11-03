## ADDED Requirements

### Requirement: Device parts in the DSL
`Part(ref, lib_id=None, footprint=None, value="", *, device=None, properties=None, pad_map=None, height=None)` SHALL accept a device id in `device` in place of `lib_id`. Exactly one of the two MUST be given. An unknown device id MUST raise `DslError` at the call, naming the closest known ids. `part.device` SHALL return the `DeviceDef` of a device part and `None` for any other part.

#### Scenario: Neither or both
- **WHEN** `Part("U1")` and `Part("U1", "Fenolite:Resistor", device="Fenolite:R_0603")` are called
- **THEN** each raises `DslError`

#### Scenario: Unknown device
- **WHEN** `Part("R1", device="Fenolite:R_0630")` is called
- **THEN** `DslError` is raised, naming `Fenolite:R_0603` as the closest id

### Requirement: Parts created and added in one call
`Design.part(*args, **kwargs) -> Part` and `Module.part(*args, **kwargs) -> Part` SHALL build a `Part` with the arguments of `Part` and `add()` it to the design or module. `Design.devices(*records)` SHALL register `DeviceDef` records for the design (capability `fenolite-component-catalog`, "Device sources and precedence").

#### Scenario: Created in a module
- **GIVEN** `m = Module("power")` added to a design
- **WHEN** `c = m.part("C1", device="Fenolite:C_0603")` is called
- **THEN** `c.path` is `"power/C1"` and the design holds the part

### Requirement: What a device gives a part
With `device`, giving `footprint` or `pad_map` SHALL raise `DslError` saying that the device names them. `value` defaults to the device value, and a given value wins. The part's properties are the user's merged with `Manufacturer` and `MPN` (when the device has them) and the device's `properties`. A user property equal to one of these under `str.casefold`, with another value, MUST raise `DslError`.

#### Scenario: Footprint given with a device
- **WHEN** `Part("R1", device="Fenolite:R_0603", footprint="Fenolite:Chip_0805")` is called
- **THEN** `DslError` is raised, saying that the device names the footprint

#### Scenario: A generic device takes a value
- **WHEN** `design.part("R1", device="Fenolite:R_0603", value=ohm("4k7"))` is lowered
- **THEN** the component `R1` has the value `4.7k` and the footprint `Fenolite:Chip_0603`

#### Scenario: Conflicting MPN
- **WHEN** `design.part("U1", device="Example:BUCK_6V_2A", properties={"mpn": "OTHER"})` is called
- **THEN** `DslError` is raised, naming `MPN`

### Requirement: Device parts in the model
`to_model` SHALL give a device part the device's symbol and footprint lib ids, its derived pad map as `pin_pad_map` (by "Per-component pin-to-pad mapping"), its value, its merged properties, and the reserved properties `fenolite.device` (the id) and `fenolite.device.sha256` (`device_digest`). A design without device parts MUST give the same model bytes as before this requirement.

#### Scenario: A part from a device
- **GIVEN** `u1 = design.part("U1", device="Example:BUCK_6V_2A")` with the authored example device registered
- **WHEN** `to_model(design)` runs
- **THEN** the component `U1` has `lib_symbol_ref` `Example:Buck_6pin`, `lib_footprint_ref` `Fenolite:SOT23_6_TI_DBV0006A`, value `EXB6202`, the properties `MPN` `EXB6202`, `Manufacturer` `Example Semi` and `fenolite.device` `Example:BUCK_6V_2A`, and `pin_pad_map` holds `("2", "EP")`

#### Scenario: Designs without devices are unchanged
- **WHEN** `canonical.dump_texts(to_model(d))` is computed for `examples/blink_2layer/design.py` before and after this change
- **THEN** the texts are equal

### Requirement: Checked pin access on device parts
On a device part, `part.NAME` and `part["NAME"]` SHALL return `PinHandle(part, NAME)` when `NAME` is a function of the device, and `PinHandle(part, NUMBER)` for a symbol pin number that the device lists. Any other designator SHALL raise `PinNameError`, a subclass of `DslError` and `AttributeError`, at the call. On a part without a device, attribute access raises `AttributeError` and `part[designator]` stays unchecked, as before.

#### Scenario: Pin by function
- **GIVEN** `u1 = design.part("U1", device="Example:BUCK_6V_2A")` and `connect(vin, u1.VIN)`
- **WHEN** `to_model(design)` runs
- **THEN** the net `VIN` holds one member for `U1` with `pin == "VIN"`

#### Scenario: Non-device parts are unchanged
- **WHEN** `r1 = Part("R1", "Mini:Mini_R")` is followed by `r1["X"]`
- **THEN** a pin handle with designator `X` is returned, and the build reports `build.unknown-pin` as before

### Requirement: Closest pin names
The message of `PinNameError` SHALL name the part, the device and the designator, then `closest:` with up to three names, then `pins:` with every function in code-point order, cut at 24 entries with `…`. The closest names MUST be a case-insensitive exact match when there is one, and otherwise `difflib.get_close_matches(name, functions, n=3, cutoff=0.6)`. `closest:` is left out when it is empty.

#### Scenario: A typo names the closest pin
- **WHEN** `u1.VINN` is read
- **THEN** `PinNameError` is raised with the message `part U1 (device Example:BUCK_6V_2A) has no pin 'VINN'; closest: VIN; pins: BST, EN, FB, GND, SW, VIN`, and `hasattr(u1, "VINN")` is `False`

#### Scenario: Wrong case
- **WHEN** `u1["vin"]` is called
- **THEN** `PinNameError` is raised, and its message holds `closest: VIN`

### Requirement: Attribute access never hides the part
Attribute pin access SHALL go through `__getattr__` only, so every attribute that `Part` defines wins. Names that start with `_` MUST raise a plain `AttributeError`. `Part.__dir__` of a device part MUST add the functions that are Python identifiers and not attributes of `Part`.

#### Scenario: Part attributes win
- **WHEN** `u1.place` is read on a device part
- **THEN** the bound method `Part.place` is returned

#### Scenario: Private names
- **WHEN** `u1._missing` is read on a device part
- **THEN** a plain `AttributeError` is raised, which is not a `DslError`

### Requirement: Device ends and pads by function
On a device with `ends`, `part.a` and `part.b` (change c0247) SHALL return the handles of the two named functions. On any device part, `part.pad(name)` SHALL also accept a function name and return the `PadRef` of its first pad in map order, with `index=` choosing another pad of that function. A name that is neither a pad nor a function MUST raise `PinNameError`.

#### Scenario: LED ends follow the anode
- **GIVEN** `d = design.part("D1", device="Fenolite:LED_0603")`
- **WHEN** `d.a` and `d.pad("A")` are read
- **THEN** `d.a` is the handle of function `A`, and `d.pad("A")` names pad `2`, the anode of the cathode-first land

### Requirement: Device functions in a build
For a device part, the build SHALL resolve a designator that is a function to every symbol pin of that function, before the rules of "Pins and pads in a build", which apply unchanged to every other designator.

#### Scenario: Function joins its pins
- **GIVEN** an authored device whose function `GND` lists symbol pins `2` and `9`, and `connect(gnd, u1.GND)`
- **WHEN** the design is built
- **THEN** the net `GND` holds `PinRef(<U1 id>, "2")` and `PinRef(<U1 id>, "9")`, and the pads of both pins carry `GND`

### Requirement: Device agreement in a build
The build SHALL check each device against the symbol and footprint it resolved with `check_device`. A symbol pin the device does not list, a device pin the symbol lacks, or a mapped pad the footprint lacks MUST give `build.device-mismatch` (error) naming the device, the function and the pin or pad, and no write is planned. A pad in `unused_pads` gives no issue; another pad without a pin keeps `build.pad-without-pin`. The code joins "Build issue codes".

#### Scenario: Device disagrees with its symbol
- **GIVEN** an authored device that lists symbol pins `1` to `5` for a symbol with pins `1` to `6`
- **WHEN** a design that uses it is built with `--confirm`
- **THEN** the exit code is 5, `issues` holds `build.device-mismatch` naming pin `6`, and nothing is written

#### Scenario: Unused pad declared
- **GIVEN** a device with `unused_pads = ["MP"]` on a footprint with a mechanical pad `MP`
- **WHEN** a design that uses it is built
- **THEN** `issues` holds no `build.pad-without-pin` for `MP`

### Requirement: Device fields on built parts
A non-empty device `datasheet` SHALL be written as the `Datasheet` field of the placed footprint and of the schematic symbol, in place of the library's value. `Manufacturer`, `MPN`, `fenolite.device` and `fenolite.device.sha256` SHALL be written as `fenolite.path` is.

#### Scenario: Datasheet field
- **WHEN** `examples/devices/design.py` is built with `--confirm`
- **THEN** the footprint of `U1` in the written board has the `Datasheet` field `https://example.invalid/exb6202.pdf` and the property `fenolite.device` `Example:BUCK_6V_2A`

#### Scenario: Device build passes the KiCad oracle
- **WHEN** `uv run pytest tests/kicad/build/test_device_build.py -rA` builds `examples/devices/design.py` and runs ERC and DRC with `kicad-cli` (in CI)
- **THEN** neither reports a finding that the same design written with plain `Part` calls does not report

### Requirement: Devices in the build result
`result.devices` SHALL list each device used, in id order, with `id`, `origin` (`builtin` or `authored`), `evidence`, `edited`, `sha256` and `parts` (component paths), empty without device parts (a key added under "Build command"). `lens.build.DEVICE_EVIDENCE` (`INFERRED`, `H-K-BUILD-DEVICE`) MUST join the envelope only when a device part is built ("Build evidence"), and the envelope level MUST NOT be lowered to a device's label. Device issues are reported once per device.

#### Scenario: Result lists the devices
- **WHEN** `examples/devices/design.py` is built with `--dry-run --json`
- **THEN** `result.devices` lists `Example:BUCK_6V_2A` with `origin` `authored` and `evidence` `UNVERIFIED`, `evidence.hypotheses` holds `H-K-BUILD-DEVICE`, and `evidence.level` is `INFERRED`

#### Scenario: No devices, no rows
- **WHEN** the blink is built with `--dry-run --json`
- **THEN** `result.devices` is empty and `evidence.hypotheses` does not hold `H-K-BUILD-DEVICE`

## MODIFIED Requirements

### Requirement: Connections and pin designators
`part[designator]` SHALL return a pin handle and `connect(net, *pins) -> Net` SHALL record that each pin joins `net`. Designators MUST be stored as written. On a part without a device they MUST be resolved only by the build ("Pins and pads in a build"). On a device part they MUST also be checked at the call against the device's functions and symbol pin numbers ("Checked pin access on device parts").
- A designator MUST be a non-empty `str` or an `int`; `part[1]` and `part["1"]` MUST name the same pin. A pin name such as `part["GND"]` is accepted as written.
- `net` MUST be a `Net`; any other value MUST raise `DslError`. There are no implicit nets and no net merges.
- A net joins the design when it is added, or when it is connected to a pin of an added part.
- Connecting the same designator of one part to two different nets MUST raise `DslError` at the second `connect`. Connecting it twice to the same net MUST keep one membership.

#### Scenario: Integer and string designators
- **GIVEN** `connect(vin, u1[1])` and `connect(vin, u1["1"])`
- **WHEN** `to_model(design)` runs
- **THEN** the net `VIN` holds one member for `U1` with `pin == "1"`

#### Scenario: Designator on two nets
- **WHEN** `connect(a, r1["1"])` is followed by `connect(b, r1["1"])`
- **THEN** `DslError` is raised naming `R1` and `1`

#### Scenario: Net given as a string
- **WHEN** `connect("GND", r1["2"])` is called
- **THEN** `DslError` is raised

#### Scenario: Device part checked at the call
- **GIVEN** `u1 = design.part("U1", device="Example:BUCK_6V_2A")`
- **WHEN** `connect(vin, u1["VIM"])` is called
- **THEN** `DslError` is raised at that call, naming `VIM` and `closest: VIN`
