## ADDED Requirements

### Requirement: Library record kinds
`fenolite.catalog.records.parse_record(text, *, file)` SHALL read one TOML record of schema `fenolite.pins.v0`, `fenolite.package.v0`, `fenolite.device.v1` (or c0248's `v0`) or `fenolite.part.v0` with `tomllib` and `parse_float=Decimal`, and SHALL return a frozen record of that kind. No float MUST be created. A higher schema version MUST raise `FormatError` with `FEN-3002`.

#### Scenario: Each kind is read
- **GIVEN** the authored files under `tests/data/library/` for the four kinds
- **WHEN** `uv run pytest tests/unit/catalog/test_records.py -k kinds` runs
- **THEN** each parses to a record of its kind and no field holds a float

#### Scenario: Newer schema
- **WHEN** a record with `schema = "fenolite.package.v1"` is parsed
- **THEN** `FormatError` with code `FEN-3002` is raised naming the schema

### Requirement: Common record header
Every record SHALL hold `schema`, `id` (`<namespace>:<name>`, each part matching `[A-Za-z0-9_.+-]+`), `version`, `summary`, `licence` and `evidence`, and MAY hold `category`, `sources`, `origin`, `reviewed_by`, `replaces` and `deprecated`. A missing or unknown key, or a wrong type, MUST raise `FormatError` (`FEN-3004`) naming the file and the key. A `Fenolite:` record MUST hold `sources`.

#### Scenario: Unknown header key
- **WHEN** a package record holding the key `colour` is parsed
- **THEN** `FormatError` with code `FEN-3004` is raised naming the file and `colour`

#### Scenario: Missing licence
- **WHEN** a pins record without `licence` is parsed
- **THEN** `FormatError` with code `FEN-3004` is raised naming `licence`

### Requirement: Exact lengths in records
Lengths and angles in records SHALL be text with a unit (`mm`, `um`, `nm`, `mil`; `deg`) parsed exactly to integer nanometres and microdegrees. A value that is not a whole number of those units, a missing or wrong unit, or a range whose minimum exceeds its maximum MUST raise `FormatError` (`FEN-3004`) naming the key.

#### Scenario: Mils are exact
- **WHEN** a pad with `size = ["25mil", "50mil"]` is parsed
- **THEN** its size is 635000 by 1270000 nm

#### Scenario: Sub-nanometre length refused
- **WHEN** a pad with `at = ["0.0000001mm", "0mm"]` is parsed
- **THEN** `FormatError` with code `FEN-3004` is raised naming `at`

### Requirement: Stable record ids
`record_uid(kind, id)` SHALL return the text of `uuid5(FENOLITE_NS, "fenolite.library:<kind>:<id>")`; it MUST NOT be stored in the file. Definitions given by a record MUST keep the model ids derived from the lib id (`derived_id("sym"|"fpd", "fenolite.catalog", id)`), pads and graphics keyed by `<name>:<key>`. Two records of one kind and id in one tree MUST raise `FEN-3004` naming both files.

#### Scenario: Regeneration keeps the uid
- **GIVEN** a package record written, deleted and written again with other lands
- **WHEN** `record_uid("package", "Fenolite:Chip_0603")` is computed before and after
- **THEN** both values are equal

#### Scenario: Duplicate id in a tree
- **GIVEN** a tree with two package files both holding `id = "Fenolite:X"`
- **WHEN** `load_tree` reads it
- **THEN** `FEN-3004` is raised naming both files

### Requirement: Canonical record text and digests
`record_text(record)` SHALL write canonical TOML: a fixed key order per kind, arrays in the order of the record (the order of a symbol's pins and of a footprint's pads is part of its definition), LF and one final newline, so that `parse_record(record_text(r)) == r`. `record_digest` SHALL be the SHA-256 of the record's canonical JSON without `reviewed_by`; `output_digest` that of the definition it gives; `interface_digest` that of its interface.

#### Scenario: Round trip
- **WHEN** every shipped record is written with `record_text` and parsed again
- **THEN** it equals the record read from the file, and the text equals the file's bytes

#### Scenario: A review does not change the digest
- **WHEN** a `reviewed_by` entry is added to a record
- **THEN** its `record_digest` is unchanged

### Requirement: Record versions
`version` SHALL be `MAJOR.MINOR.PATCH` with decimal parts and no leading zeros. A changed record digest with an unchanged definition MUST raise PATCH or more; a changed definition with an unchanged interface MUST raise MINOR. MAJOR MUST stay `1` for the life of a shipped id. `catalog/data/VERSIONS.toml` SHALL hold each shipped id's kind, version, digest, output and interface digests.

#### Scenario: Changed land without a new version
- **GIVEN** a shipped package whose pad size changed while `version` and `VERSIONS.toml` did not
- **WHEN** `uv run pytest tests/unit/catalog/test_versions.py` runs
- **THEN** it fails naming the id and asking for a MINOR version

#### Scenario: Metadata change is a patch
- **GIVEN** a shipped pins record whose only change is a new source id and version `1.0.1`
- **WHEN** the version test runs after `tools/catalog/versions.py --update`
- **THEN** it passes

### Requirement: Interface changes make new ids
An id's interface (pins: numbers, names, types and units; package: pad numbers and kind; device: symbol, footprint, functions with pins and pads; part: device and MPN) MUST NOT change. A successor SHALL be a new record with `replaces`; the old one SHALL gain `deprecated = {by, since, reason}`. A removed id MUST stay in `VERSIONS.toml` with `removed = true` and MUST NOT be reused.

#### Scenario: Pad renumbered under an id
- **GIVEN** a shipped package whose pad `2` became `3` under the same id
- **WHEN** the version test runs
- **THEN** it fails naming the id, stating that an interface change needs a new id and a deprecation

#### Scenario: Removed id reused
- **GIVEN** `VERSIONS.toml` marks `Fenolite:Old` removed and a record with that id is added
- **WHEN** the version test runs
- **THEN** it fails naming `Fenolite:Old`

#### Scenario: Replaces must match a deprecation
- **WHEN** a record with `replaces = "Fenolite:A"` is read and `Fenolite:A` is not deprecated by it
- **THEN** `FEN-3004` is raised naming `replaces`

### Requirement: Deprecated records in a build
A build that uses a deprecated record SHALL still build and SHALL report `library.deprecated` (warning) once per record, naming the record and its replacement. A shipped deprecated record MUST NOT be removed before one published `CATALOG_VERSION` has carried its deprecation.

#### Scenario: Deprecated footprint used
- **GIVEN** a design using a project package marked `deprecated = { by = "Proj:B", since = "1.0.1", reason = "pad 3 added" }`
- **WHEN** it is built
- **THEN** the build succeeds and `issues` holds one `library.deprecated` naming `Proj:B`

### Requirement: Record licences
`licence` SHALL be an SPDX expression. A `Fenolite:` record MUST be `CC0-1.0` (the maintainer's decision of 2026-10-29); a record whose `origin` is set MUST be `CC0-1.0`. Any other value in a shipped record MUST raise `FEN-3004`. Project records MAY hold any text.

#### Scenario: Shipped record with another licence
- **WHEN** a `Fenolite:` package with `licence = "CC-BY-SA-4.0"` or `licence = "Apache-2.0"` is read
- **THEN** `FEN-3004` is raised naming `licence`

### Requirement: Origin of records from CC0 libraries
`origin` SHALL hold `library`, `version` (a release or a 40-hex commit), `element` (the element's id in that library) and `licence`, which MUST be `CC0-1.0`. A record with `origin` MUST have evidence `UNVERIFIED` unless `reviewed_by` holds a review of its current `record_digest`; otherwise `FEN-3004` MUST be raised naming `evidence`.

#### Scenario: Unreviewed seeded record claims a higher label
- **WHEN** a record with `origin` and `evidence = "CORPUS-VERIFIED"` and no review is read
- **THEN** `FEN-3004` is raised naming `evidence`

#### Scenario: Origin from a non-CC0 library
- **WHEN** a record with `origin.licence = "CC-BY-SA-4.0"` is read
- **THEN** `FEN-3004` is raised naming `origin.licence`

### Requirement: Review entries
Each `reviewed_by` entry SHALL hold `who`, `date` (ISO date), `version`, `digest` and `evidence`, and MAY hold `sheet` (a path relative to the tree). An entry whose `digest` differs from the current `record_digest` is stale: a build using the record SHALL report `library.review-stale` (info), and the entry MUST NOT support a label above `UNVERIFIED` for an `origin` record.

#### Scenario: Stale review
- **GIVEN** a project record whose only review names an older digest
- **WHEN** a design using it is built
- **THEN** `issues` holds one `library.review-stale` naming the record

### Requirement: Pins records
A pins record SHALL hold `[[pin]]` tables with unique `number`, `name` and `type`, and optional `shape`, `hidden`, `unit`, `group` and `alternates`. With a `[symbol]` table that places every pin once and lists its graphics, it SHALL give a `SymbolDef` whose properties are `Reference`, `Value` and `Description` (the summary). Without `[symbol]`, using its symbol MUST give `library.generator-missing`.

#### Scenario: Pin placed twice
- **WHEN** a pins record whose `[symbol]` places pin `1` twice is read
- **THEN** `FEN-3004` is raised naming pin `1`

#### Scenario: No drawing and no generator
- **GIVEN** a project pins record without `[symbol]`, and no symbol generator installed
- **WHEN** a design using its id is built
- **THEN** the build reports `library.generator-missing` (error) and writes nothing

### Requirement: Package records
A package record SHALL hold `generator` and `kind`. With `generator = "explicit"` its `[[pad]]` and `[[graphic]]` tables, whose keys mirror `Pad` and `Graphic`, SHALL give a `FootprintDef`. Other generators MUST give `library.generator-missing` at use until their change lands. The description MUST end with "; land pattern remains INFERRED and requires part-specific review" when evidence is `INFERRED`.

#### Scenario: Explicit footprint
- **WHEN** `tests/data/library/packages/two_pad.toml` is read and its footprint built
- **THEN** the `FootprintDef` has its two pads with the ids `derived_id("pad", "fenolite.catalog", "<name>:1")` and `…:2`

#### Scenario: Family package before its generator
- **GIVEN** a project package with `generator = "gullwing"` and no c0260
- **WHEN** a design using it is built
- **THEN** `library.generator-missing` names the record and the generator

### Requirement: Orderable parts inherit from their device
A device SHALL hold `[[part]]` tables, or a `fenolite.part.v0` file SHALL name it with `device`. A part MUST hold a unique `mpn` and MAY hold `extends`, `manufacturer`, `packing`, `lifecycle`, `grade`, `datasheet`, `properties`, `ratings`, `summary`. The effective part SHALL be the device, then its `extends` chain from the root, then the part; properties merge by key.

#### Scenario: A grade variant inherits the packing
- **GIVEN** part `B` with `extends = "A"` and `grade = "automotive"`, and part `A` with `packing = "reel 2500"`
- **WHEN** the effective part `B` is computed
- **THEN** it has the device's pins and footprint, packing `reel 2500` and grade `automotive`

#### Scenario: Cycle refused
- **WHEN** parts `A` and `B` extend each other
- **THEN** `FEN-3004` is raised naming both

### Requirement: Parts never change the interface
A part MUST NOT hold `symbol`, `footprint`, `pins`, `ground`, `unused_pads`, `ends` or `ref_prefix`; such a key MUST raise `FEN-3004` with the hint that a different interface is a different device. A part rating MUST lie within the device's rating of the same key, else `FEN-3004`.

#### Scenario: Footprint in a part
- **WHEN** a part holding `footprint = "Fenolite:Chip_0805"` is read
- **THEN** `FEN-3004` is raised naming `footprint` and the hint

#### Scenario: Wider temperature
- **WHEN** a device rated -40 to 85 degC holds a part rated -40 to 125 degC
- **THEN** `FEN-3004` is raised naming the part's `ratings.temperature`

### Requirement: Placing an orderable part
`design.part(ref, device="<device id>@<mpn>")` SHALL place the device and give the component the part's `MPN`, `Manufacturer`, `Datasheet` and properties. An unknown MPN MUST raise `DslError` listing the device's MPNs. The part's uid SHALL be `record_uid("part", "<device id>@<mpn>")`.

#### Scenario: Reel variant placed
- **GIVEN** the device `Example:BUCK_6V_2A` with part `EXB6202DR`
- **WHEN** `design.part("U1", device="Example:BUCK_6V_2A@EXB6202DR")` is built
- **THEN** the footprint's `MPN` property is `EXB6202DR` and its pads are those of the device

#### Scenario: Unknown MPN
- **WHEN** `design.part("U1", device="Example:BUCK_6V_2A@NOPE")` runs
- **THEN** `DslError` is raised listing `EXB6202DR`

### Requirement: Library trees
`load_tree(root)` SHALL read every `*.toml` below `root` in POSIX path order, take the kind from `schema`, join part files to their devices, and return the records with their issues. `shipped_tree()` SHALL read `fenolite/catalog/data/` once per process. The project folder `devices/` beside a script SHALL be read with `load_tree`, and its records SHALL override shipped ones per id.

#### Scenario: Project package overrides a shipped footprint
- **GIVEN** `devices/packages/Chip_0603.toml` beside a script with `id = "Fenolite:Chip_0603"` and wider pads
- **WHEN** the design is built
- **THEN** the project footprint is used and its origin is `authored`

#### Scenario: Load time
- **WHEN** `shipped_tree()` is first called in a fresh process
- **THEN** it returns within 2.5 times the time `tomllib` alone takes to read the same files, plus 50 ms (a budget that holds on any runner; about 150 ms on CI)
