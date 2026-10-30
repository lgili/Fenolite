# Devices

A **device** is one reviewed record that joins a symbol, a footprint, the map from pin function to pins and
pads, an identity (manufacturer, part number, datasheet), ratings and an evidence label (change c0248). A
part placed from a device needs no `pad_map`, MPN or datasheet in the script, and its pins are named by
function and checked at the line that names them.

```python
design = Design("supply")
u1 = design.part("U1", device="Example:BUCK_6V_2A")  # created and added
c1 = design.part("C1", device="Fenolite:C_0805", value=farad("10u"))
connect(vin, u1.VIN, c1.P1)  # u1.VINN stops the script: "...; closest: VIN; pins: BST, EN, ..."
```

`examples/devices/` is a complete board built this way.

## The record (`fenolite.device.v0`)

A device is one TOML file. It is read with `tomllib` and no float is created: a number with a fraction is
refused, and ratings are text with a unit.

```toml
schema = "fenolite.device.v0"
id = "Example:BUCK_6V_2A"
summary = "6 V 2 A step-down regulator (illustrative)"
manufacturer = "Example Semi"
mpn = "EXB6202"
datasheet = "https://example.invalid/exb6202.pdf"
symbol = "Example:Buck_6pin"
footprint = "Fenolite:SOT23_6_TI_DBV0006A"
ref_prefix = "U"
class = "controller"
evidence = "UNVERIFIED"
ground = "GND"

[pins]
BST = "1"
GND = "2"
FB  = { pins = ["3"], voltage = { abs_max = "6.5V" } }
EN  = { pins = ["4"], voltage = { abs_max = { min = "-0.3V", max = "6.5V" } }, input_high_min = "1.2V", input_low_max = "0.4V", must_connect = true }
VIN = { pins = ["5"], voltage = { operating = { min = "2.7V", max = "6V" }, abs_max = "6.5V" } }
SW  = "6"

[[limits]]
between = ["BST", "SW"]
voltage = { abs_max = "6V" }

[ratings]
current = { abs_max = "2.5A", operating = "2A" }
temperature = { abs_max = { min = "-55degC", max = "150degC" }, operating = { min = "-40degC", max = "125degC" } }
```

| key | required | meaning |
|---|---|---|
| `schema` | yes | `"fenolite.device.v0"`; a higher version gives `FEN-3002` |
| `id` | yes | `<namespace>:<name>`, each part `[A-Za-z0-9_.+-]+`; `Fenolite:` is the shipped namespace |
| `summary` | yes | one printable line |
| `symbol`, `footprint` | yes | lib ids, resolved as any part's ids |
| `manufacturer`, `mpn` | no | printable text; a generic device has neither |
| `datasheet` | no | an `https://` URL |
| `ref_prefix` | no | `[A-Z][A-Z_]*`; default: the prefix of a catalog symbol, else required |
| `class` | no | one part class of the roles' vocabulary (`docs/roles.md`), evidence for `roles.classify` (change c0274) |
| `value` | no | the default part value; default `mpn`, else the name part of `id` |
| `evidence` | yes | one label of the evidence vocabulary |
| `sources` | no | source ids of `docs/evidence/sources.md`; required for a `Fenolite:` device |
| `ground` | no | the function pin voltages are measured from; default `GND` when it exists |
| `unused_pads` | no | pads deliberately left without a pin (mechanical, shield) |
| `ends` | no | two functions that the named ends `part.a` and `part.b` resolve to |
| `properties` | no | extra BOM properties, string to string |
| `pins` | yes | function → pins and pads (below) |
| `ratings` | no | device ratings (below) |
| `limits` | no | `[[limits]]` tables: a voltage limit between two functions (below) |
| `interfaces` | no | `[[interfaces]]` tables: the interface ports of the device (below; change c0252) |
| `provenance` | no | the stamp of `fenolite catalog import` (below) |
| `options` | no | `[[options]]` tables: the interface options a part can `take` (`docs/pins.md`; change c0257) |

Any other key, a missing key or a wrong type gives `FEN-3004`, naming the file and the key.

### Pins: three spellings

A function name matches `[A-Za-z_][A-Za-z0-9_+.~-]*`: it never starts with a digit, so it is never read as
a pin number. Functions differ under `str.casefold`.

- `VIN = "5"`: symbol pin 5 on pad 5;
- `GND = ["2", "9"]`: symbol pins 2 and 9, each on the pad of its number;
- `GND = { map = { "2" = ["2", "EP"], "9" = "9" }, must_connect = true }`: symbol pin to pads, as
  `Part.pad_map` spells them. The long form takes `pins` or `map`, never both, and optionally `voltage`,
  `current`, the logic thresholds and `must_connect`.

Each symbol pin is in exactly one function, and each pad is on at most one symbol pin. The union of the
`map` entries is the device's pad map: it lowers to `Component.pin_pad_map` exactly as a `pad_map` does.

### Ratings, limits and units

Device ratings take the keys `voltage`, `current`, `power` and `temperature`; pin ratings take `voltage`
(measured from `ground`) and `current`. Every limit (change c0274) is a table of `abs_max` and/or
`operating`:

| kind | meaning |
|---|---|
| `abs_max` | an absolute maximum rating: beyond it the part may be damaged; judged worst case and derated |
| `operating` | the range in which the part works as specified; judged exactly and never derated |

Each kind is a `{ min, max }` table (one bound or both) or a string, which is the maximum (`"6.5V"` is
`{ max = "6.5V" }`). The single form `voltage = { min = "2.7V", max = "6V" }` is refused with
`FEN-3004` and the hint to say `abs_max` or `operating`: reading it as either kind would be a guess. An
`operating` range outside its `abs_max` range is refused as well.

Values are text with a unit and an SI prefix: `"6V"`, `"500mA"`, `"250mW"`. A temperature is written in
degrees Celsius (`"-40degC"`, no prefix) or in kelvin (`"233.15K"`), and both read the same value. They are
parsed exactly by `fenolite.core.quantities` and stored as integers: µV, µA, µW and mK (millikelvin; the
canonical text prints temperatures back in `degC`). A value that is not a whole number of these units
(`"6.0000005V"`, `"-40.0001degC"`), a unit that does not fit the key, or `min` above `max` gives
`FEN-3004`.

### Limits between two pins

`[[limits]]` states a voltage limit between two functions: `between = ["BST", "SW"]` names two distinct
functions of the device, and the voltage is the first's minus the second's (`voltage = { abs_max = "6V" }`,
in the shape above). An unknown function, a pair stated twice (in either order) or another key gives
`FEN-3004`. The canonical text orders the tables by `between`.

### Logic thresholds

A pin may state `input_high_min`, `input_low_max`, `output_high_min`, `output_low_max` (voltages from
`ground`) and `output_current_max` (a current), each one quantity text from the datasheet. They are stored
as `Threshold(key, unit, value)` on the pin; no threshold is shipped or assumed.

### Interface ports

`[[interfaces]]` (change c0252) declares the interface ports of the device, which a script reaches as
`part.port("vdd")` or `part.vdd` (`docs/dsl.md`, "Device ports") and which `fenolite check` judges in the
stage `circuit.rules`. Each table holds:

| key | required | meaning |
|---|---|---|
| `name` | yes | a Python identifier; not a function of the device, not an attribute of `Part` |
| `kind` | yes | `power`, `ground`, `logic`, `i2c`, `spi`, `uart`, `usb2` or `diff_pair` |
| `direction` | no | `in`, `out` or `inout` (default) |
| `members` | yes | member → the device functions it joins (`hv = ["VDD", "VDDA"]`), each function in one member |
| `reference` | no | another `power` interface of the device that the levels refer to (logic and buses) |
| `requires` | no | the companions the port needs: `pullup` (`i2c`, `logic`), `supply`, `chip_select` (`spi`) |
| `evidence` | no | the evidence label of these values; default the device's `evidence` |

and the parameters its kind and direction take (`docs/dsl.md`, "Interface parameters"): `voltage` and
`current` on a `power` port (`current` only on `in` and `out`), `abs_max` and the thresholds on `logic`
and bus ports, `pullup` on an `i2c` port. A parameter is a quantity text (the exact value: a threshold) or
a `{ min, max }` table; a missing `min` reads as 0 for a current or a resistance and as unbounded for a
voltage. A power `voltage` is an *operating* range, never an absolute rating; the absolute ratings stay on
the pins and in `[ratings]`.

```toml
[[interfaces]]
name = "vdd"
kind = "power"
direction = "in"
members = { hv = ["VDD", "VDDA"], lv = ["VSS"] }
voltage = { min = "1.71V", max = "3.6V" }
current = { max = "12mA" }
```

An unknown kind or member, a function the device lacks or one in two members, a `reference` that names no
other `power` interface, a parameter the kind and direction do not take (`current` on an `inout` port
included), a `requires` entry the kind does not take, or a name equal to a function or to an attribute of
`Part` gives `FEN-3004`, naming the file, the interface and the rule.

## Where devices come from

A device id resolves from, in this order (the first source that holds it wins):

1. the records given to `design.devices(*records)` (from `fenolite.catalog.devices.parse_device` or
   `load_devices`), reached through `design.part(...)` and `module.part(...)`;
2. `devices/*.toml` beside the design script, read by the script runner in file-name order before the script
   runs (the DSL itself reads no file);
3. the shipped generic `Fenolite:` devices: `R_0402`, `R_0603`, `R_0805`, `R_1206`, `C_0402`, `C_0603`,
   `C_0805`, `C_1206` (functions `P1` and `P2`), `LED_0603` (functions `A` and `K` on the cathode-first
   land, pin `A` on pad 2) and `Conn_1x2_P2.54`. They have no manufacturer, MPN or ratings, the label
   `INFERRED` and the sources of their catalog symbol and footprint.

A project device with a shipped id overrides it and gives `device.overrides-builtin` (info). Two project
files with one id give `FEN-3004` naming both files. The device files are inputs of `build`: their paths and
SHA-256 are in `result.device_files`, and a changed file changes the plan. An unknown id raises `DslError` at
the call, with the closest ids.

## Parts from devices

`Part(ref, device="NS:NAME")` (or `design.part(...)`, `module.part(...)`, which also add the part):

- `footprint` and `pad_map` must not be given: the device names them;
- `value` defaults to the device value, and a given value wins (`value=ohm("4k7")` on a generic resistor);
- `properties` are merged with `Manufacturer`, `MPN` and the device's properties; a user property of one of
  those names with another value raises `DslError` (a different MPN is a different device);
- `part.device` is the `DeviceDef`, `None` on any other part.

The built component carries the properties `fenolite.device` (the id) and `fenolite.device.sha256` (its
digest), written as `fenolite.path` is, and a non-empty `datasheet` becomes the `Datasheet` field of the
footprint and of the schematic symbol.

### Checked pins

On a device part, `part.NAME` and `part["NAME"]` give the pin of a function, and `part["5"]` a symbol pin
number the device lists. Anything else raises `PinNameError` (a `DslError` and an `AttributeError`) with the
closest names: a case-insensitive match first (`u1["vin"]` → `closest: VIN`), else up to three close names.
Attributes of `Part` always win (`u1.place` is the method), so a function named like one is reached as
`part["place"]`; `catalog show` lists such functions as `shadowed`. `part.pad("VIN")` gives the first pad of
a function (`index=` another one). Parts without a device keep their designators unchecked, as before.

### In a build

A designator that is a function names every symbol pin of the function. The build checks each device once
against the symbol and footprint it resolved: a symbol pin in no function, a function pin the symbol lacks,
or a mapped pad the footprint lacks gives `build.device-mismatch` (error), and nothing is written. A pad of
`unused_pads` gives no `build.pad-without-pin`. `result.devices` lists each device used: `id`, `origin`
(`builtin` or `authored`), `evidence`, `edited`, `sha256` and `parts`. The envelope gains `H-K-BUILD-DEVICE`
and is never lowered to a device's own label: read each device's label in `result.devices`.

## Provenance and hand edits

`fenolite catalog import --symbol LIB:SYM --footprint LIB:FP --id NS:NAME --out FILE` writes a device
template through plan and confirm:

- functions are the symbol's pin names (pins sharing a name are grouped; an empty or `~` name gives
  `P<number>`); `--pin FUNCTION=PIN[:PAD[+PAD]]` sets a pin's function and pads;
- pads are the pins' own numbers: a pin without such a pad is `catalog.pin-without-pad` (error, nothing is
  written), and a pad no pin names is `catalog.pad-unmapped` (warning, left out);
- the label is always `UNVERIFIED`, and `[provenance]` holds the tool, the two lib ids, the date of
  `--timestamp` (else today, UTC) and the SHA-256 of the record (`device_digest`: the canonical JSON of the
  record without its provenance, so reformatting is not an edit).

A stamped record whose digest no longer matches is **edited**: the build reports `device.edited` (info),
`catalog show` gives `"edited": true`, and the label stays as written. Reviewing a pin map and raising the
label is the edit that is expected. A re-import onto an edited file is refused with `FEN-7001` unless
`--allow-lossy` is given; onto an unedited file it plans the replacement.

## How to review a pin map

1. `fenolite catalog show <symbol>` and `fenolite catalog show <footprint>`: the pin numbers and names, and
   the pads.
2. Compare every function with the datasheet's pin table: which package pin is which signal, and which
   pins share a pad (an exposed pad, several ground pins).
3. Check the land: pad numbering, pin 1, the polarity of two-pin parts (a cathode-first LED land puts the
   anode pin on pad 2).
4. Fill in `ratings` from the absolute maximum ratings, with their units.
5. Raise `evidence` only when the map was checked against a primary source, and add that source to
   `sources`.
