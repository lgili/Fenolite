## Context

- **Source.** `docs/research/circuit-as-code.md`, section 1 ("Parts that are complete devices") and core
  change B. Step 2 of the batch order: c0248 is implemented with c0249 (design lock), after c0246 (ranges)
  and c0247 (connection helpers).
- **What exists on `dev` (0.6.0).**
  - `fenolite.catalog` ships Fenolite-authored symbols and footprints. Each `CatalogEntry` carries a lib id,
    kind, category, summary, evidence and sources. `default_pad_map` gives the one built-in pin-to-pad
    rule, for an anode-first symbol on a cathode-first land.
  - `Part(ref, lib_id, footprint=None, value="", *, properties, pad_map, height)` records designators as
    written. The build resolves them: a pin number first, then a pin name that names every pin with that
    name ("Pins and pads in a build").
  - `pad_map` lowers to `Component.pin_pad_map` ("Per-component pin-to-pad mapping").
  - User properties reach the footprint, and through `property:<NAME>` columns they reach `fenolite bom`.
    `Datasheet` is a reserved property name that comes from the library.
  - The catalog browser can already select a symbol and a footprint with a reviewed map and emit a `Part`
    snippet ("Reviewed catalog component selection"). Nothing stores that review.
  - `dsl` may import only `model` (and `schematic`). The DSL "reads no library, file or environment".
  - Quantities (`dsl/quantity.py`) are exact `Fraction`s, but the catalog cannot import `dsl`.
- **What the public tools do** (concepts only; see the research page). One keeps three layers per
  component: logical port, schematic pin, physical pad, together with the MPN and the manufacturer. One
  stamps an imported part with its source, date and checksum, so that a hand edit is detected. One carries
  the MPN and pin labels on a chip element. Nothing of their schemas or names is taken.

## Goals / Non-Goals

**Goals**

- One reviewed record per device: symbol, footprint, function-to-pad map, identity, ratings and evidence.
  A part placed from it needs no `pad_map`, MPN or datasheet in the script.
- A wrong pin name fails at the line that wrote it and names the closest valid names.
- Ratings stored in integers that c0253 can compare, with no float.
- A device written by a tool can be told apart from the same device edited by hand.
- Designs without devices build byte for byte as before.

**Non-Goals**

- See the proposal. In addition:
  - no symbol or footprint is generated from a device;
  - no device variants (one footprint per device; a second footprint is a second device);
  - no change to how a non-device part resolves its pins.

## Decisions

### 1. The device record (`fenolite.device.v0`)

A device is one TOML file read with `tomllib` (`parse_float=Decimal`, so no float is created). Example,
authored for Fenolite (illustrative, not a real product):

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

- **Keys.**

  | key | required | meaning |
  |---|---|---|
  | `schema` | yes | `"fenolite.device.v0"`. A higher version gives `FEN-3002`. |
  | `id` | yes | `<namespace>:<name>`, each part matching `[A-Za-z0-9_.+-]+`. `Fenolite:` is the shipped namespace. |
  | `summary` | yes | One line, printable. |
  | `symbol`, `footprint` | yes | Lib ids, resolved like any part's ids ("Library resolution during build"). |
  | `manufacturer`, `mpn` | no | Printable text. A generic device has neither. |
  | `datasheet` | no | An `https://` URL. |
  | `ref_prefix` | no | `[A-Z][A-Z_]*`. Default: the reference prefix of a catalog symbol, else required. |
  | `value` | no | The default part value. Default: `mpn`, else the name part of `id`. |
  | `evidence` | yes | One label of the evidence vocabulary. |
  | `sources` | no | Source ids of `docs/evidence/sources.md`. Required for a `Fenolite:` device. |
  | `ground` | no | The function that pin voltages are measured from. Default `GND` when that function exists. |
  | `unused_pads` | no | Pads that are deliberately left without a pin (mechanical, shield). |
  | `ends` | no | Two function names that c0247's named ends `part.a` and `part.b` resolve to (`["A", "K"]`). Without it, `a` and `b` stay symbol pins `1` and `2`, as c0247 defines. |
  | `properties` | no | Extra BOM properties (string to string), under the rules of "User properties in the DSL". |
  | `pins` | yes | Function → pins and pads (below). |
  | `ratings` | no | Device ratings (below). |
  | `provenance` | no | The stamp (decision 6). |
  | `interfaces`, `options` | reserved | Refused with `FEN-3002` ("newer format") until c0252 and c0257 define them. |

  Any other key gives `FEN-3004`, naming the file and the key.
- **Pins.** A function name matches `[A-Za-z_][A-Za-z0-9_+.~-]*`. It never starts with a digit, so it can
  never be read as a pin number. Functions are unique when compared with `str.casefold`. Three spellings:
  - `VIN = "5"`: symbol pin `5` on pad `5`;
  - `GND = ["2", "9"]`: symbol pins `2` and `9`, each on the pad of its number;
  - `GND = { map = { "2" = ["2", "EP"], "9" = "9" }, must_connect = true }`: symbol pin to pads, in the
    spelling of `Part.pad_map`. The long form takes `pins` (a list) or `map`, never both, plus the
    optional `voltage`, `current` and `must_connect`.

  Each symbol pin appears in exactly one function. Each pad appears for at most one symbol pin (the rule
  of `model.pin-pad-map`). The device's **derived pad map** is the union of its `map` entries. It lowers
  to `Component.pin_pad_map` exactly as a `pad_map` would, so the build has no second path for pads.
- **Ratings.** The keys are closed: `voltage`, `current`, `power`, `temperature`. Each takes `min` and/or
  `max`. A pin takes `voltage` (measured from `ground`) and `current`. Values are text with a unit
  (`"6V"`, `"500mA"`, `"250mW"`, `"-40degC"`). They are parsed exactly and stored as integers: µV, µA, µW,
  and m°C (millidegrees Celsius). A value that is not a whole number of these units, a wrong unit, or
  `min > max` gives `FEN-3004`. These are the units c0253 judges in. With c0246, the DSL reads a rating
  as a `Range` (`u1.device.pin("VIN").voltage`).
- **Why TOML.** Hand-reviewed files sit in git next to `requirements.toml` and `placements.toml`.
  `tomllib` is stdlib, and every write goes through the canonical writer of decision 6.

### 2. Model and package placement

- `fenolite.model.library` gains frozen value objects: `DeviceDef(id, summary, symbol, footprint,
  manufacturer="", mpn="", datasheet="", ref_prefix="", value="", evidence, sources=(), ground="",
  unused_pads=(), properties={}, pins=(), ratings=(), provenance=None)`, `DevicePin(function, pin_pads,
  voltage=None, current=None, must_connect=False)`, `Rating(key, unit, min=None, max=None)` and
  `DeviceProvenance(tool, source, date, sha256)`. `Library` gains `devices`. The library schema is
  regenerated. Library definitions stay out of `Design` and `.fenolite/` ("Library definitions").
- `fenolite.catalog.devices` holds:
  - `parse_device(text, *, file) -> DeviceDef` (pure);
  - `device_text(device) -> str` (canonical TOML);
  - `device_digest(device) -> str` (SHA-256 of the canonical JSON of the record with `provenance`
    cleared, so a change of formatting is not an edit);
  - `shipped_devices()` (package data, read with `importlib.resources`);
  - `load_devices(folder) -> tuple[tuple[DeviceDef, ...], tuple[Issue, ...]]`;
  - `check_device(device, symbol, footprint) -> tuple[Issue, ...]`.
- The exact unit parser moves from `dsl/quantity.py` to `fenolite.core.quantities` (stdlib only). `dsl`
  and `catalog` both use it, so the two read units alike. `dsl.quantity` keeps its public names. This is
  the module that c0246 extends with ranges. Whichever of the two lands second rebases on the other.
- **Layering.** `dsl` → `catalog` is a new edge. `catalog` imports only `model` and `core`, so no cycle
  appears. *Alternative considered:* the build injects every device, shipped ones included, into the DSL.
  It was rejected because `to_model` in a test, in `fenolite.api` or in a notebook would then lose the
  shipped devices, and pin checks would depend on who ran the script.

### 3. Where devices come from, and precedence

1. Devices given to `design.devices(*records)` (records from `load_devices` or `parse_device`).
2. `devices/*.toml` beside the design script, read by the script runner (`cli/_script.py`) in file-name
   order before the script runs, and installed for that run through a context variable of
   `fenolite.dsl.devices`. The DSL itself reads no file.
3. The shipped `Fenolite:` devices.

A device of a higher row wins for its id. A project device whose id is a shipped id gives
`device.overrides-builtin` (info), as an authored symbol does ("Build resolves built-in definitions").
Two project files with one id give `FEN-3004` naming both files. Device files are inputs of the build:
their names and SHA-256 join `input`, so a changed device file changes the plan. An unknown id raises
`DslError` at the call, with the closest ids.

### 4. Parts from devices in the DSL

```python
# Today (0.6.0)
u1 = Part(
    "U1",
    "Example:Buck_6pin",
    footprint="Fenolite:SOT23_6_TI_DBV0006A",
    value="EXB6202",
    properties={"MPN": "EXB6202", "Manufacturer": "Example Semi"},
)
design.add(u1)
connect(vin, u1["5"])  # which pin was VIN again?

# Proposed
u1 = design.part("U1", device="Example:BUCK_6V_2A")  # created and added
connect(vin, u1.VIN)  # checked now; a typo names the closest pins
c1 = design.part("C1", device="Fenolite:C_0805", value=farad("10u"))
```

- `Part(ref, lib_id=None, footprint=None, value="", *, device=None, ...)`. Exactly one of `lib_id` and
  `device` is required. With `device`:
  - `footprint` and `pad_map` must not be given (`DslError`: "the device names them");
  - `value` defaults to the device value, and a given value wins (a generic resistor device takes
    `ohm("10k")`);
  - `properties` are merged with `Manufacturer`, `MPN` and the device's `properties`. A user property of
    the same name with another value raises `DslError` (a different MPN is a different device);
  - `part.device` returns the `DeviceDef`. On a non-device part it is `None`.
- `Design.part(*args, **kwargs) -> Part` and `Module.part(...)` build a `Part` and `add()` it. They work
  for non-device parts too. In this change the ref stays required; c0249 makes it optional.
- **Lowering.** `to_model` gives the component the device's symbol, footprint and derived pad map, its
  value, and the properties `Manufacturer`, `MPN`, `fenolite.device` and `fenolite.device.sha256`. The
  `fenolite.` prefix is reserved, so no user can set these. A design without device parts lowers to the
  same bytes as before.

### 5. Checked pin access

- On a device part, `part.NAME` (through `__getattr__`, so it is reached only for names that `Part` does
  not define) and `part["NAME"]` return `PinHandle(part, "NAME")` when `NAME` is a function. They return
  `PinHandle(part, "5")` when the designator is a symbol pin number that the device lists. Anything else
  raises `PinNameError`, a subclass of both `DslError` and `AttributeError` (so `hasattr` and `copy` keep
  working). The message reads:
  `part U1 (device Example:BUCK_6V_2A) has no pin 'VINN'; closest: VIN; pins: BST, EN, FB, GND, SW, VIN`.
- **Closest names.** First a case-insensitive exact match, then `difflib.get_close_matches(name,
  functions, n=3, cutoff=0.6)`. The "pins" list holds every function sorted by code point, cut at 24 with
  `…`. Both are deterministic.
- Dunder and private names (`_x`) always raise a plain `AttributeError`. A function whose name is an
  attribute of `Part` (`ref`, `place`, `pad`, `device`, …) can be reached only through `part["place"]`.
  `catalog show` lists such names as `shadowed`.
- Non-device parts keep "stored as written, resolved by the build", so existing scripts are unchanged.
- **Pads by function.** On a device part, `part.pad("VDD")` also accepts a function name and gives the
  `PadRef` of the function's first pad in map order (`index=` picks another pad of that function). A
  `PinHandle` of a device part is accepted wherever c0247's `near=` takes a pad. A wrong name raises
  `PinNameError`, as attribute access does.
- *Alternative considered:* generated classes per device, for IDE completion. Rejected: it means
  metaclass magic, a code generator, and stale stubs. A typed stub generator can come later as a tool.

### 6. Provenance and checksum

- `fenolite catalog import --symbol LIB:SYM --footprint LIB:FP --id NS:NAME --out FILE [--pin
  FUNCTION=PIN[:PAD[+PAD]]]... [--manufacturer T] [--mpn T] [--datasheet URL] [--ref-prefix P]` writes a
  device template through plan and confirm.
  - Functions default to the symbol's pin names: pins with one name are grouped, and an empty or `~` name
    gives `P<number>`.
  - Pads default to the identity, which is checked: a pin whose number is not a pad is refused with
    `catalog.pin-without-pad` (error) unless `--pin` maps it. Pads without a pin give
    `catalog.pad-unmapped` (warning) and are left out.
  - Evidence is always `UNVERIFIED`.
  - The `[provenance]` table holds `tool = "fenolite catalog import"`, `source` (the two lib ids, never a
    path), `date` (the date of `--timestamp`, else today in UTC) and `sha256` (`device_digest` of the
    record).
- **Detection.** On load, a record whose provenance `sha256` differs from its digest is `edited`. The
  build reports `device.edited` (info) once per device, and `catalog show` sets `"edited": true`. The
  label in the file stays as the person wrote it: reviewing a pin map and raising its label is the edit
  that is expected.
- **No clobbering.** `catalog import` onto an existing file that is `edited` exits 7 with `FEN-7001`, and
  a hint to keep the file or to pass `--allow-lossy`. Onto an unedited file it plans a replacement.
- The canonical writer (`device_text`) gives a fixed key order, one table per function, LF line ends and
  a final newline. The same device always gives the same bytes.

### 7. Device parts in a build

- **Resolution.** For a device part, a designator that is a function resolves to the function's symbol
  pins. Every other designator follows "Pins and pads in a build" unchanged.
- **Agreement.** The build checks the device against the symbol and footprint it resolved, with
  `check_device`. A symbol pin missing from the device, a device pin missing from the symbol, or a mapped
  pad missing from the footprint gives `build.device-mismatch` (error, naming device, function and pin or
  pad), and the build writes nothing. A footprint pad that no pin names and that `unused_pads` does not
  list keeps `build.pad-without-pin` (info).
- **Fields.** A non-empty datasheet becomes the footprint's and symbol's `Datasheet` field, in place of
  the library's value. `Manufacturer`, `MPN`, `fenolite.device` and `fenolite.device.sha256` are written
  as `fenolite.path` is.
- **Result and evidence.** `result.devices` lists each device used: `id`, `origin` (`builtin` or
  `authored`), `evidence`, `edited`, `sha256` and `parts` (component paths). `lens.build.DEVICE_EVIDENCE`
  (`INFERRED`, `H-K-BUILD-DEVICE`) joins the envelope when a device part is built. The envelope level is
  **not** lowered to a device's label: the build's evidence speaks of the written files, and each device's
  label is shown next to it (open question 2).
- **Issue codes** (they join "Build issue codes"): `build.device-mismatch` (error), `device.edited`
  (info), `device.overrides-builtin` (info).

### 8. Shipped generic devices

Ten records under `src/fenolite/catalog/devices/`, each joining catalog entries whose pin maps the
catalog already reviewed:

- `Fenolite:R_0402`, `R_0603`, `R_0805` and `R_1206` (`Fenolite:Resistor` on `Chip_*`, functions `P1`
  and `P2`, `ends = ["P1", "P2"]`);
- `Fenolite:C_0402`, `C_0603`, `C_0805` and `C_1206` (`Fenolite:Capacitor`, the same functions and
  ends);
- `Fenolite:LED_0603` (`Fenolite:LED` on `LED0603_Kingbright_APT1608SURCK`, functions `A` and `K`,
  mapped cathode-first, `ends = ["A", "K"]`, so `led.a` is the anode wherever its pad is);
- `Fenolite:Conn_1x2_P2.54` (`Fenolite:Connector_2` on `Header_1x2_P2.54`, functions `P1` and `P2`).

They have no manufacturer, MPN or ratings, the label `INFERRED`, and the sources of their two catalog
entries. Functions are not named `a` and `b`, because c0247 makes those attributes of every `Part`, and an
attribute of `Part` always wins over a function (decision 5); `ends` ties the two together instead.

### 9. CLI

- `fenolite catalog list --kind device` and `catalog show <device id>` (a device id and a footprint id may
  be the same text, so `show` takes `--kind` to choose; without it a device is shown only when no symbol
  or footprint has the id). `show` returns the record, `digest`, `edited`, `shadowed`, and the issues of
  `check_device` against the catalog definitions when both are `Fenolite:` entries.
- `catalog import` (decision 6) is `mutates=True`. Its `example_args` and `mutation_example_args` use
  catalog ids only, so the consistency suite runs offline.

## Codes introduced

| code | severity / exit | when |
|---|---|---|
| `build.device-mismatch` | error | the device disagrees with its resolved symbol or footprint |
| `device.edited` | info | a stamped record's digest differs from its provenance |
| `device.overrides-builtin` | info | a project device has a shipped id |
| `catalog.pin-without-pad` | error | `catalog import`: a symbol pin has no pad and no `--pin` |
| `catalog.pad-unmapped` | warning | `catalog import`: a footprint pad has no pin |
| `FEN-3004` | exit 3 | malformed device file (existing code) |
| `FEN-3002` | exit 3 | device schema newer, or a reserved key (existing code) |
| `FEN-7001` | exit 7 | `catalog import` would overwrite an edited device (existing code) |

No new `FEN-` code.

## Risks / Trade-offs

- **`__getattr__` on `Part`.** It can hide attribute typos on device parts (`u1.palce` becomes "no pin
  'palce'"). Mitigation: the message lists the pins, and `Part` defines `__dir__` with its own attributes
  and the functions.
- **The layering edge `dsl` → `catalog`.** It is small and acyclic. It is guarded by the import-graph test.
- **A reviewed pin map is still a human claim.** Labels stay as written, `UNVERIFIED` by default for
  imports, and the build reports them per device.
- **Moving the unit parser** touches c0246's file. The two changes are ordered (c0246 first), and task 1.1
  rebases.

## Open questions

Decided by the maintainer on 2026-10-29; each answer is the recommended one.

1. *Should a project device be allowed to use the `Fenolite:` namespace?* Decided: yes, as an override
   with `device.overrides-builtin`, mirroring authored symbols.
2. *Should the build envelope's level drop to the lowest device label?* Decided: no. Keep
   `result.devices[].evidence` per device, and let c0253's checks cap their own evidence by the labels of the
   devices they read.
3. *Should the catalog browser emit a device TOML from a reviewed pair?* Decided: yes, in a follow-up
   change. This change only defines the format the browser would emit.
4. *Should attribute access fold case (`u1.vin` → `VIN`)?* Decided: no. The error suggests the exact
   spelling, so that scripts spell functions one way.

## Relation to the batch

- **c0246** (ranges): ratings are integer bounds. With c0246 the DSL exposes them as `Range`.
- **c0247** (helpers): this change extends its two hooks. `Part._end(index)` reads `ends`, and
  `must_connect_pins(component, device)` reads `must_connect`. `part.pad(function)` (decision 5) gives
  `near()` and `decouple(..., near=u.VDD)` the pads that c0247 waits for. c0247's open question 3 is
  answered: `part.a` and `part.b` are attributes of `Part`, so a function named `a` is reached only through
  `part["a"]`.
- **c0249** (lock): `ref_prefix` feeds automatic refs. Device id and digest are what c0254 records as a
  pick.
- **c0250** (manual edits): a footprint changed in KiCad on a device part is a conflict with the device,
  per property.
- **c0251** (blocks): `b.part(device=...)` is `Module.part`.
- **c0252** (interfaces): fills the reserved `interfaces` key.
- **c0253** (contracts): reads `DevicePin.voltage`, `current` and the device `ratings`, injected into the
  check stage by the command (checks cannot import `catalog`).
- **c0254** (picking): adds parametric rows next to device records, and picks resolve to device ids.
- **c0257** (pin assignment): fills the reserved `options` key.
