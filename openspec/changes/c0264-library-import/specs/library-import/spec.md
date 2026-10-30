## ADDED Requirements

### Requirement: Local library import
`fenolite library import SOURCE... --into DIR` SHALL write one project device from files the user already has, under the mutation protocol. It MUST run no subprocess, make no network request and write nothing outside `DIR`. A source is a `.kicad_sym`, `.kicad_mod`, `.SchLib`, `.PcbLib`, `.step` or `.stp` file, or a `.zip` that holds them.

#### Scenario: Import an authored archive
- **GIVEN** the authored archive `tests/data/library_import/exb6202.zip` holding one `.kicad_sym`, one `.kicad_mod` and one `.step`
- **WHEN** `fenolite library import <archive> --into devices --dry-run --json` runs
- **THEN** the exit code is 4, the plan writes `device.toml`, `pins.toml`, `package.toml`, one `.kicad_sym`, one `.kicad_mod` and one `.step` under `devices/Imported/EXB6202/`, and no other path

#### Scenario: Confirmed import builds
- **GIVEN** the reviewed plan of the previous scenario
- **WHEN** it is written with `--confirm --plan <id>` and `examples/library_import/design.py` places `Imported:EXB6202`
- **THEN** `fenolite build` of that design exits 0 and its result lists the device with `evidence` `UNVERIFIED`

### Requirement: Import origin and licence
Every record written by an import SHALL hold `evidence = "UNVERIFIED"`, `licence = "see source terms"` and an `[origin]` table with `tool`, `date` (from `--timestamp`, else today in UTC), `shippable = false` and one `source` row per file read: its base name, the member path inside an archive, and the SHA-256 of its bytes. No absolute path MUST be written.

#### Scenario: Origin rows
- **WHEN** the authored archive is imported with `--timestamp 2026-10-29T00:00:00Z`
- **THEN** `device.toml` holds one `origin.source` row for the archive and one per member read, each SHA-256 equals the digest of those bytes, and no value starts with `/` or a drive letter

### Requirement: Deterministic import
Two imports of the same sources with the same arguments and `--timestamp` SHALL plan the same files with the same bytes and the same plan id. Record ids MUST be derived from kind and canonical name as the record format defines.

#### Scenario: Same bytes twice
- **WHEN** the authored archive is imported twice in two empty folders with the same `--timestamp`
- **THEN** the two plans have the same id and every planned file has the same SHA-256

### Requirement: Import sources
A KiCad symbol and footprint SHALL be kept as read and written by Fenolite's KiCad writers. An Altium `.PcbLib` footprint SHALL be imported through `import_footprints`. An Altium `.SchLib` SHALL give only its pins, and the symbol MUST be drawn from the pin table with `library.import-symbol-regenerated` (info). A STEP file MUST be copied byte for byte.

#### Scenario: Altium symbol drawn from pins
- **GIVEN** the authored `tests/data/library_import/exb6202.SchLib` and `.PcbLib`
- **WHEN** they are imported with `--dry-run`
- **THEN** the planned symbol has the pins of the `.SchLib` by number, name and type, and the issues hold `library.import-symbol-regenerated`

#### Scenario: STEP copied unchanged
- **WHEN** the authored archive is imported
- **THEN** the planned `.step` file has the SHA-256 of the archive member

### Requirement: Unsupported sources
An `.IntLib` source SHALL exit 2 with `FEN-2001` and a hint to export the `.SchLib` and `.PcbLib`. A member of an archive that is not a supported source, a nested archive or a legacy KiCad 5 library MUST NOT be decompressed, and MUST be listed in `result.skipped` with `library.import-skipped` (info) and its reason.

#### Scenario: IntLib refused
- **WHEN** `fenolite library import part.IntLib --into devices --dry-run --json` runs
- **THEN** the exit code is 2, stderr carries `FEN-2001`, and nothing is planned

#### Scenario: Legacy library skipped
- **GIVEN** an authored archive that also holds `part.lib` and `inner.zip`
- **WHEN** it is imported with `--dry-run`
- **THEN** `result.skipped` lists both with the reasons `legacy KiCad 5 library` and `nested archive`

### Requirement: Item selection
When the sources hold more than one symbol or footprint, `--symbol NAME` and `--footprint NAME` SHALL pick one; without them the command MUST exit 2 with `FEN-2001` and a hint listing the names in code-point order. Without any source, `--symbol` and `--footprint` SHALL be lib ids resolved as a build resolves them.

#### Scenario: Two footprints, none picked
- **GIVEN** an authored archive with two `.kicad_mod` members
- **WHEN** it is imported without `--footprint`
- **THEN** the exit code is 2 and the hint names both footprints

### Requirement: Zip limits
An archive SHALL be read in memory with the standard library and never extracted. It MUST hold at most 2 000 entries; a member MUST inflate to at most 64 MiB and the members read to at most 256 MiB in total, counted while reading; a member past 1 MiB MUST stay within a ratio of 200:1. A breach MUST exit 3 with `FEN-3004` naming the archive, the member and the limit.

#### Scenario: A compression bomb
- **GIVEN** an archive built in the test whose `.kicad_mod` member inflates past 64 MiB from a few KiB
- **WHEN** it is imported
- **THEN** the exit code is 3, the message names the member and the limit, and less than 65 MiB was inflated

### Requirement: Zip member names
A member name with an absolute path, a drive letter, a `..` segment or a NUL, a member that is a symbolic link, an encrypted member, and two names equal under `str.casefold` after `\` is read as `/` SHALL exit 3 with `FEN-3004`. Output paths MUST be built from the device id, never from member names.

#### Scenario: Path traversal refused
- **GIVEN** archives built in the test with the members `../evil.kicad_mod`, `/abs.kicad_mod`, `C:/x.kicad_mod`, a symbolic link and `A.kicad_mod` beside `a.kicad_mod`
- **WHEN** each is imported
- **THEN** each exits 3 with `FEN-3004` and nothing is planned

### Requirement: Import target inside the project
`--into` SHALL be a relative folder that resolves inside the working directory. A target inside the installed `fenolite` package, inside a vendored `fenolite_library/` folder or the library cache, or outside the working directory MUST exit 2 with `FEN-2001`.

#### Scenario: Shipped catalog refused
- **WHEN** an import names `--into` a path that resolves into the installed `fenolite/catalog` folder, or `../outside`
- **THEN** each exits 2 with `FEN-2001` and nothing is planned

### Requirement: Imported records are not shippable
`fenolite.library.importer.shippable(record)` SHALL be false for a record with `origin.shippable = false` or `licence = "see source terms"`. A check of a shipped catalog or of `fenolite-library` MUST report such a record as `library.not-shippable` (error).

#### Scenario: An imported device in a library item
- **GIVEN** a library item folder built in the test that holds one imported device
- **WHEN** the library check of the library rules runs on it
- **THEN** it reports one `library.not-shippable` error naming the device

### Requirement: STEP bodies
A STEP source SHALL start with `ISO-10303-21;` and hold `FILE_SCHEMA`, else exit 3 with `FEN-3004`. Its geometry MUST NOT be read (`library.import-step-unchecked`, info). The footprint's model entry MUST name the copied file; with no entry, one at offset 0 and rotation 0 MUST be added with `library.import-step-placement` (info).

#### Scenario: Not a STEP file
- **WHEN** a file `body.step` holding text that is not a STEP header is imported
- **THEN** the exit code is 3 and the message names `body.step`

### Requirement: Footprint cross-check
Unless `--no-crosscheck` is given, the importer SHALL classify the imported footprint into a family of the footprint generators, draw the generator's footprint for the derived parameters, or for the package of `--package`, and compare pads by number. An unknown family MUST give `library.import-family-unknown` (info) and no comparison.

#### Scenario: A matching download
- **GIVEN** an authored `.kicad_mod` drawn from the SOIC-8 package record of the test data
- **WHEN** it is imported with `--package` naming that record
- **THEN** no `library.import-*` warning or error is reported, and `result.family` is `gullwing`

### Requirement: Cross-check findings
A pad count, numbering or pin-1 position that differs SHALL be `library.import-pad-count`, `-numbering` or `-pin1`: an error with `--package`, else a warning. A pitch, pad centre or pad size outside the tolerances of `docs/formats/library/import-crosscheck.md` MUST be `library.import-pitch` or `library.import-land` (warning), naming the pad and both values in nm.

#### Scenario: Clockwise numbering caught
- **GIVEN** the authored SOIC-8 footprint renumbered clockwise
- **WHEN** it is imported with `--package` naming the SOIC-8 record
- **THEN** the exit code is 5, the issues hold `library.import-numbering`, and nothing is written

#### Scenario: A pad moved
- **GIVEN** the authored SOIC-8 footprint with pad 3 moved by 0.2 mm
- **WHEN** it is imported without `--package`
- **THEN** one `library.import-land` warning names pad 3, and the plan is made

### Requirement: Two sources of one footprint
When the sources hold a KiCad and an Altium footprint for one part, `--prefer` (default `kicad`) SHALL pick the one imported, and the other MUST be compared with it by the cross-check rules, any difference giving `library.import-sources-disagree` (warning).

#### Scenario: KiCad and Altium differ
- **GIVEN** an authored archive whose `.PcbLib` footprint has one pad wider than its `.kicad_mod`
- **WHEN** it is imported
- **THEN** the `.kicad_mod` is imported and one `library.import-sources-disagree` warning names the pad

### Requirement: Re-import rules
An import whose device folder exists SHALL plan nothing and set `result.unchanged` when every source SHA-256 equals the recorded one. It MUST replace an unedited record, and MUST exit 7 with `FEN-7001` when the record is edited, unless `--allow-lossy` is given.

#### Scenario: Re-import over a reviewed device
- **GIVEN** an imported device whose `device.toml` was edited by hand after the import
- **WHEN** the import runs again with another source
- **THEN** the exit code is 7, stderr carries `FEN-7001`, and nothing is written

### Requirement: Catalog import alias
`fenolite catalog import` SHALL run the importer of this capability with lib-id sources, write the same record bytes as before this change, and add `catalog.import-deprecated` (info) naming `fenolite library import`.

#### Scenario: Alias keeps its bytes
- **GIVEN** the arguments of c0248's scenario "Import a template"
- **WHEN** `fenolite catalog import` runs with `--dry-run`
- **THEN** the planned record has the bytes c0248 specified, and the issues hold `catalog.import-deprecated`

### Requirement: Import result
The result of `library import` (schema `fenolite.library-import.v0`) SHALL hold `device`, `folder`, `sources` (`file`, `member`, `kind`, `sha256`), `skipped` (`file`, `member`, `reason`), `symbol`, `footprint`, `step`, `family`, `crosscheck` and `unchanged`. The envelope evidence MUST be `INFERRED` with `H-L-IMPORT`.

#### Scenario: Result fields
- **WHEN** the authored archive is imported with `--dry-run --json`
- **THEN** the result holds every field above, and `evidence.level` is `INFERRED`
