## ADDED Requirements

### Requirement: Device records
`fenolite.catalog.devices.parse_device(text, *, file) -> DeviceDef` SHALL read one TOML record of schema `fenolite.device.v0` with `tomllib` and `parse_float=Decimal`, and SHALL return a `fenolite.model.library.DeviceDef` that joins a symbol, a footprint, a function-to-pin-and-pad map, an identity, a reference prefix, a value, ratings, an evidence label, sources and an optional provenance. No float MUST be created.

#### Scenario: A device record is read
- **GIVEN** the authored file `tests/data/devices/example_buck.toml` with `id = "Example:BUCK_6V_2A"`, `symbol = "Example:Buck_6pin"` and `footprint = "Fenolite:SOT23_6_TI_DBV0006A"`
- **WHEN** `uv run pytest tests/unit/catalog/test_devices.py -k read` parses it
- **THEN** a `DeviceDef` with that id, symbol and footprint is returned, and no field holds a float

### Requirement: Device record keys
A device record SHALL hold `schema`, `id` (`<namespace>:<name>`, each part matching `[A-Za-z0-9_.+-]+`), `summary`, `symbol`, `footprint`, `evidence` and `pins`, and MAY hold `manufacturer`, `mpn`, `datasheet` (an `https://` URL), `ref_prefix` (`[A-Z][A-Z_]*`), `value`, `sources`, `ground`, `unused_pads`, `properties`, `ratings`, `ends` (two function names) and `provenance`. Another key, a missing key or a wrong type MUST raise `FormatError` (`FEN-3004`) naming the file and the key.

#### Scenario: Unknown key
- **WHEN** a record holding the key `colour` is parsed
- **THEN** `FormatError` with code `FEN-3004` is raised, naming the file and `colour`

#### Scenario: Shipped namespace needs sources
- **WHEN** a record with `id = "Fenolite:X"` and no `sources` is parsed
- **THEN** `FormatError` with code `FEN-3004` is raised, naming `sources`

### Requirement: Reserved device keys
The keys `interfaces` and `options`, and a schema version higher than `fenolite.device.v0`, SHALL raise `FormatError` mapped to `FEN-3002`, with a message that names the key as reserved for a later format (c0252 and c0257).

#### Scenario: Reserved key
- **WHEN** a record holding an `interfaces` table is parsed
- **THEN** `FormatError` with code `FEN-3002` is raised, naming `interfaces`

### Requirement: Device pin functions
Each key of `pins` SHALL be a function name matching `[A-Za-z_][A-Za-z0-9_+.~-]*`, unique under `str.casefold`. Its value MUST be a string (one symbol pin on the pad of its number), a list of strings (several such pins), or a table with exactly one of `pins` and `map` (symbol pin to pads, spelled as `Part.pad_map` is), plus optional `voltage`, `current` and `must_connect`. Each symbol pin MUST be in one function, and each pad MUST be on at most one pin.

#### Scenario: Three spellings
- **GIVEN** `BST = "1"`, `GND = { map = { "2" = ["2", "EP"] } }` and `VIN = { pins = ["5"] }`
- **WHEN** the record is parsed
- **THEN** `BST` has `pin_pads == (("1", "1"),)`, `GND` has `pin_pads == (("2", "2"), ("2", "EP"))` and `VIN` has `pin_pads == (("5", "5"),)`

#### Scenario: Refused pin tables
- **WHEN** records are parsed that repeat a symbol pin in two functions, name functions `vin` and `VIN`, name a function `1V8`, or give a table with both `pins` and `map`
- **THEN** each raises `FormatError` with code `FEN-3004`, naming the function

### Requirement: Device ratings in integers
Device ratings SHALL use only the keys `voltage`, `current`, `power` and `temperature`, and pin ratings only `voltage` and `current`. Each rating holds `min`, `max` or both, as text with a unit (`V`, `A`, `W`, `degC`, with an SI prefix), parsed by `fenolite.core.quantities` and stored as an exact integer in µV, µA, µW or m°C. A value that is not a whole number of these units, a unit that does not fit the key, or `min > max` MUST raise `FormatError` (`FEN-3004`).

#### Scenario: Ratings read exactly
- **GIVEN** `VIN = { pins = ["5"], voltage = { min = "2.7V", max = "6V" } }` and `temperature = { min = "-40degC", max = "125degC" }`
- **WHEN** the record is parsed
- **THEN** the pin `VIN` has `voltage.min == 2_700_000` and `voltage.max == 6_000_000` in µV, and the device rating `temperature` has `min == -40_000` and `max == 125_000` in m°C

#### Scenario: Refused ratings
- **WHEN** records with `voltage = { max = "6.0000005V" }`, `current = { max = "6V" }` and `power = { min = "2W", max = "1W" }` are parsed
- **THEN** each raises `FormatError` with code `FEN-3004`

### Requirement: Canonical device text
`fenolite.catalog.devices.device_text(device) -> str` SHALL give the canonical TOML of a record: a fixed key order, one table per long-form function, LF line ends and one final newline. `parse_device(device_text(d)) == d` MUST hold for every record.

#### Scenario: Canonical text round trip
- **WHEN** every shipped device and every device under `tests/data/devices` is written with `device_text` and parsed again
- **THEN** each record equals the one read, and writing it twice gives identical bytes

### Requirement: Device sources and precedence
The DSL SHALL resolve a device id from, in this order: the records given to `Design.devices(*records)`, the project devices of `devices/*.toml` beside the design script (installed by the script runner in file-name order), and `fenolite.catalog.devices.shipped_devices()`. The first source that holds the id MUST win. The DSL itself MUST read no file.

#### Scenario: Project device beside the script
- **GIVEN** `examples/devices/design.py` with `devices/example_buck.toml` beside it
- **WHEN** `fenolite build examples/devices/design.py --out B --dry-run --json` runs
- **THEN** the exit code is 4 and `result.devices` holds `Example:BUCK_6V_2A` with `origin` `authored`

### Requirement: Project devices override shipped ones
A project device whose id is a shipped id SHALL give `device.overrides-builtin` (info), and its `origin` SHALL be `authored`. An unmodified shipped device MUST be reported as `builtin`. Two project files with one id MUST raise `FormatError` (`FEN-3004`) naming both files.

#### Scenario: Override of a shipped device
- **GIVEN** a project file `devices/r0603.toml` whose id is `Fenolite:R_0603`
- **WHEN** a design that uses `Fenolite:R_0603` is built with `--dry-run`
- **THEN** `issues` holds one `device.overrides-builtin` info, and the device's `origin` is `authored`

#### Scenario: One id in two files
- **GIVEN** `devices/a.toml` and `devices/b.toml`, both with `id = "Proj:X"`
- **WHEN** the design is built with `--dry-run`
- **THEN** the exit code is 3, stderr carries `FEN-3004`, and the message names both files

### Requirement: Device files are build inputs
`cmd_build` SHALL list the name, relative to the script folder, and the SHA-256 of every project device file in `input`, so that a changed device file changes the plan.

#### Scenario: Device file in the input
- **WHEN** `examples/devices/design.py` is built with `--dry-run --json`
- **THEN** `input` lists `devices/example_buck.toml` with its SHA-256, and no absolute path

### Requirement: Shipped generic devices
The catalog SHALL ship the Fenolite-authored devices `Fenolite:R_0402`, `R_0603`, `R_0805`, `R_1206`, `C_0402`, `C_0603`, `C_0805`, `C_1206`, `LED_0603` and `Conn_1x2_P2.54`. Each MUST join one catalog symbol and one catalog footprint, have no manufacturer, MPN or ratings, carry `INFERRED` and the sources of its two entries, and pass `check_device`. Two-terminal devices name their functions `P1` and `P2` (the LED `A` and `K`) and list them in `ends`.

#### Scenario: Every shipped device agrees with the catalog
- **WHEN** `uv run pytest tests/unit/catalog/test_devices.py -k shipped` runs `check_device` on every shipped device with its catalog symbol and footprint
- **THEN** no issue is returned, every device has a non-empty `sources`, and none has a manufacturer or an MPN

#### Scenario: The LED keeps the cathode-first map
- **WHEN** `Fenolite:LED_0603` is read
- **THEN** its pin `A` has `pin_pads == (("1", "2"),)` and its pin `K` has `pin_pads == (("2", "1"),)`

### Requirement: Device digest
`fenolite.catalog.devices.device_digest(device) -> str` SHALL be the lowercase hex SHA-256 of the canonical JSON of the record with `provenance` set to `None`, so that a change of formatting or of key order does not change it.

#### Scenario: Reformatting keeps the digest
- **GIVEN** a device file and a copy with its keys reordered and blank lines added
- **WHEN** both are parsed
- **THEN** their digests are equal

### Requirement: Device provenance and edits
A `provenance` table SHALL hold `tool`, `source` (never an absolute path), `date` (an ISO 8601 date) and `sha256`. A record whose `provenance.sha256` differs from its digest SHALL be `edited`: the build reports `device.edited` (info) once per edited device it uses, and `catalog show` gives `"edited": true`. The evidence label written in an edited record MUST be kept. A record without `provenance` is never `edited`.

#### Scenario: A hand edit is detected
- **GIVEN** a device written by `fenolite catalog import --confirm`, whose `mpn` is then changed by hand
- **WHEN** a design that uses it is built with `--dry-run --json`
- **THEN** `issues` holds `device.edited` naming the device, and `result.devices[0].edited` is `true`

#### Scenario: Reformatting is not an edit
- **GIVEN** the same imported device with its keys reordered and no value changed
- **WHEN** it is loaded
- **THEN** it is not `edited`

### Requirement: Devices in the catalog list and show
`fenolite catalog list --kind device` SHALL list the shipped devices in id order, each with `id`, `kind` `device`, `summary`, `evidence` and `sources`; without `--kind` the list holds symbols, footprints and devices. `catalog show <id> --kind device` SHALL show the record, `digest`, `edited`, `shadowed` (functions that are `Part` attribute names) and, for catalog symbol and footprint, the `check_device` issues. Without `--kind`, `show` gives a device only when no symbol or footprint has the id.

#### Scenario: List devices
- **WHEN** `fenolite catalog list --kind device --json` runs
- **THEN** `result` lists the ten shipped devices in id order, each with `kind` `device`

#### Scenario: Show a device
- **WHEN** `fenolite catalog show Fenolite:R_0603 --kind device --json` runs
- **THEN** `result` holds the record, a 64-character `digest`, `edited` `false` and an empty `shadowed`

### Requirement: Device import
`fenolite catalog import --symbol LIB:SYM --footprint LIB:FP --id NS:NAME --out FILE [--pin FUNCTION=PIN[:PAD[+PAD]]]... [--manufacturer T] [--mpn T] [--datasheet URL] [--ref-prefix P]` SHALL plan one write of kind `device` holding `device_text` of a record with `evidence = "UNVERIFIED"` and a provenance whose `tool` is `fenolite catalog import`, `source` the two lib ids, `date` the date of `--timestamp` (else today in UTC) and `sha256` the digest.

#### Scenario: Import a template
- **WHEN** `fenolite catalog import --symbol Fenolite:Resistor --footprint Fenolite:Chip_0603 --id Proj:R_0603 --out devices/r.toml --timestamp 2026-10-29T00:00:00Z --confirm --json` runs
- **THEN** the exit code is 0, `receipt.written` lists `devices/r.toml`, the file parses with `evidence` `UNVERIFIED` and `provenance.date` `2026-10-29`, and a second run with the same flags writes identical bytes

### Requirement: Device import pins and pads
`catalog import` SHALL name functions after the symbol's pin names, grouping pins that share a name and naming an empty or `~` name `P<number>`, and SHALL map pins to the pads of their numbers unless `--pin` maps them. A pin without such a pad MUST give `catalog.pin-without-pad` (error), and no write is planned. A footprint pad that no pin names MUST give `catalog.pad-unmapped` (warning) and is left out.

#### Scenario: A pin without a pad
- **WHEN** `catalog import` pairs a three-pin symbol with a two-pad footprint and passes no `--pin`
- **THEN** the exit code is 5, `issues` holds `catalog.pin-without-pad` naming pin `3`, and nothing is written

#### Scenario: Grouped names
- **GIVEN** an authored symbol whose pins `2` and `9` are both named `GND`
- **WHEN** it is imported with a footprint that has pads `1` to `9`
- **THEN** the record has one function `GND` with `pin_pads == (("2", "2"), ("9", "9"))`

### Requirement: Device import keeps hand edits
`catalog import` onto an existing `FILE` that is `edited` SHALL exit 7 with `FEN-7001` and write nothing unless `--allow-lossy` is given; onto an existing file that is not edited it SHALL plan the replacement. Catalog ids MUST resolve offline, and other lib ids through the build's `LibraryResolver` with the project folder set to the folder of `--out`. `example_args` and `mutation_example_args` MUST use catalog ids and run no subprocess.

#### Scenario: Re-import over a hand edit
- **GIVEN** `devices/r.toml` from "Import a template", with its `summary` changed by hand
- **WHEN** the same import runs with `--confirm`
- **THEN** the exit code is 7, stderr carries `FEN-7001`, and the file is unchanged

#### Scenario: Re-import of an unedited file
- **GIVEN** `devices/r.toml` from "Import a template", unchanged
- **WHEN** the import runs again with `--mpn X-1 --confirm`
- **THEN** the exit code is 0 and the file holds `mpn = "X-1"` with a new `provenance.sha256`
