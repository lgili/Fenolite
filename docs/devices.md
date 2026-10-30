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
evidence = "UNVERIFIED"
ground = "GND"

[pins]
BST = "1"
GND = "2"
FB  = { pins = ["3"], voltage = { max = "6V" } }
EN  = { pins = ["4"], voltage = { max = "6V" }, must_connect = true }
VIN = { pins = ["5"], voltage = { min = "2.7V", max = "6V" } }
SW  = "6"

[ratings]
current = { max = "2A" }
temperature = { min = "-40degC", max = "125degC" }
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
| `value` | no | the default part value; default `mpn`, else the name part of `id` |
| `evidence` | yes | one label of the evidence vocabulary |
| `sources` | no | source ids of `docs/evidence/sources.md`; required for a `Fenolite:` device |
| `ground` | no | the function pin voltages are measured from; default `GND` when it exists |
| `unused_pads` | no | pads deliberately left without a pin (mechanical, shield) |
| `ends` | no | two functions that the named ends `part.a` and `part.b` resolve to |
| `properties` | no | extra BOM properties, string to string |
| `pins` | yes | function → pins and pads (below) |
| `ratings` | no | device ratings (below) |
| `provenance` | no | the stamp of `fenolite catalog import` (below) |
| `interfaces`, `options` | reserved | refused with `FEN-3002` until later formats define them |

Any other key, a missing key or a wrong type gives `FEN-3004`, naming the file and the key.

### Pins: three spellings

A function name matches `[A-Za-z_][A-Za-z0-9_+.~-]*`: it never starts with a digit, so it is never read as
a pin number. Functions differ under `str.casefold`.

- `VIN = "5"`: symbol pin 5 on pad 5;
- `GND = ["2", "9"]`: symbol pins 2 and 9, each on the pad of its number;
- `GND = { map = { "2" = ["2", "EP"], "9" = "9" }, must_connect = true }`: symbol pin to pads, as
  `Part.pad_map` spells them. The long form takes `pins` or `map`, never both, and optionally `voltage`,
  `current` and `must_connect`.

Each symbol pin is in exactly one function, and each pad is on at most one symbol pin. The union of the
`map` entries is the device's pad map: it lowers to `Component.pin_pad_map` exactly as a `pad_map` does.

### Ratings and units

Device ratings take the keys `voltage`, `current`, `power` and `temperature`; pin ratings take `voltage`
(measured from `ground`) and `current`. Each holds `min`, `max` or both, as text with a unit and an SI
prefix: `"6V"`, `"500mA"`, `"250mW"`, `"-40degC"`. They are parsed exactly by `fenolite.core.quantities`
and stored as integers: µV, µA, µW and m°C. A value that is not a whole number of these units
(`"6.0000005V"`), a unit that does not fit the key, or `min` above `max` gives `FEN-3004`.

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
