## ADDED Requirements

### Requirement: Device item kinds
A `symbol` item of `fenolite-library` SHALL hold one c0259 `pins` record with `[symbol]`, a `footprint` item one `package` record, and a `device` item one `device` record with its parts, whose `depends` names its symbol and footprint items. Each record's id MUST equal the item id and its `licence` the item's `spdx`, else `library.provenance-invalid`. The namespace `Fenolite` MUST be refused.

#### Scenario: Device item read
- **GIVEN** the authored library fixture `tests/data/library/demo/` with the items `symbol`, `footprint` and `device` `Demo:EXB`
- **WHEN** `fenolite library audit tests/data/library/demo --json` runs
- **THEN** it exits 0 and reports three device-kind items with their records

#### Scenario: Reserved namespace
- **GIVEN** a fixture device item with the id `Fenolite:X`
- **WHEN** the audit runs
- **THEN** it exits 5 with `library.provenance-invalid` naming the namespace `Fenolite`

### Requirement: Authored device items
An authored device-kind item SHALL use `spdx = "CC0-1.0"`, the family `cc0`, and record `sources` naming only `D-` ids of the library's `sources.toml`, whose rows hold `id`, `title`, `url`, `licence`, `retrieved` and `used`. An unregistered id MUST give `FEN-3004` naming the record and the id; a record that `shippable()` rejects MUST give `library.not-shippable`.

#### Scenario: Unregistered source
- **WHEN** a fixture authored record names `D-0099` and `sources.toml` lacks it
- **THEN** the audit fails with `FEN-3004` naming the record and `D-0099`

### Requirement: Device kinds in the library CI
The library's CI SHALL run, for changed device-kind items: `fenolite library check` (c0262), regeneration of generated footprints and symbols compared with committed outputs, c0259's version rules against the base branch, the rule that seeded records are `UNVERIFIED` or reviewed, and c0262 sheets with an old/new visual diff as a pull-request artefact.

#### Scenario: Version step missing
- **GIVEN** a fixture base tree and a head tree whose `Demo:EXB` record changed without a version step
- **WHEN** `fenolite library audit <head> --base <base> --json` runs
- **THEN** it exits 5 with `library.version-rule` naming `Demo:EXB`

### Requirement: Seeded records from LibrePCB
`fenolite library seed --from-librepcb DIR --commit SHA` SHALL convert LibrePCB packages, components with symbols, and devices with parts into `cc0` library items, each with `item.json`, the CC0 legal code as `LICENSE`, a dated `NOTICE` and `PROVENANCE.json` (`origin: seeded`), and records with `origin` (library, commit, element UUID), `CC0-1.0` and `UNVERIFIED`. A non-CC0 licence file MUST give `FEN-3004`.

#### Scenario: Seed items carry their origin
- **GIVEN** the authored fixture `tests/data/librepcb/demo/` (CC0 legal code, one package, one component with a symbol, one device with two parts), written for Fenolite from the public format page
- **WHEN** `fenolite library seed --from-librepcb tests/data/librepcb/demo --commit <40 hex> --library Demo --into out --dry-run --json` runs
- **THEN** the plan lists one footprint, one symbol and one device item, each with `PROVENANCE.json` of origin `seeded` and records whose `origin.element` is their element UUID and evidence `UNVERIFIED`

#### Scenario: Not a CC0 library
- **GIVEN** the same fixture with another licence file
- **WHEN** the command runs
- **THEN** it exits 3 with `FEN-3004` naming the licence file and plans nothing

### Requirement: Seed determinism and safety
Two seed runs on the same checkout and commit SHALL give the same ids and bytes. Ids SHALL be `<namespace>:<name>` with other characters replaced by `_`; a collision SHALL append `_` and the first 8 hex digits of the element UUID (`library.seed-renamed`). An element that cannot be converted SHALL be skipped with `library.seed-skipped`. A reviewed record MUST NOT be overwritten (`FEN-7001`).

#### Scenario: Same bytes twice
- **WHEN** the seed of the fixture is confirmed into two empty folders
- **THEN** both folders have one tree digest

#### Scenario: Custom pad outline skipped
- **GIVEN** a fixture package with a custom pad outline
- **WHEN** it is seeded
- **THEN** `issues` holds `library.seed-skipped` naming the package UUID and the reason, and the device using it is skipped too

#### Scenario: Reviewed record kept
- **GIVEN** a seeded item in `--into` whose record has a `reviewed_by` entry
- **WHEN** the seed runs again over it with `--confirm`
- **THEN** it exits 7 with `FEN-7001` naming the record and writes nothing
