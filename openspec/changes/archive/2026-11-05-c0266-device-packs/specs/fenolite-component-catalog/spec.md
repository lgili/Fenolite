## MODIFIED Requirements

### Requirement: Build resolves built-in definitions
The KiCad `fenolite build` SHALL resolve catalog symbol and footprint lib ids without consulting global/project CAD library tables for those ids. It SHALL write the definitions used by the design into the generated project's local libraries. A project-authored definition whose lib id exactly matches a catalog entry MUST take precedence for that build only; other catalog entries remain available. Vendored records rank between them. Origins MUST be reported as `builtin`, `library` or `authored`.

#### Scenario: Offline built-in build
- **GIVEN** a design that names a shipped symbol and footprint
- **WHEN** it is built with empty library tables and offline resolver configuration
- **THEN** its definitions resolve, the generated local tables point to the local output libraries, and the result labels their origin `builtin`

#### Scenario: User customizes a standard definition
- **GIVEN** a project-authored symbol or footprint with the same lib id as a catalog entry
- **WHEN** the project is built
- **THEN** the authored definition is used and labelled `authored`, with no mutation of the shipped catalog

#### Scenario: Vendored definition resolved offline
- **GIVEN** a design that names the footprint of a `footprint` item vendored under `fenolite_library/footprints/`, with empty library tables
- **WHEN** it is built
- **THEN** the footprint is written into the local output library and the result labels its origin `library`, with the item id and version

## ADDED Requirements

### Requirement: Vendored library records
The runner SHALL read `fenolite_library/symbols`, `fenolite_library/footprints` and `fenolite_library/devices` beside the script as project records with c0259's `load_tree`, importing no module. For each id, authored records SHALL win over vendored ones (`library.overrides-item`, info), and vendored over the shipped catalog. One id in two vendored items MUST give `library.item-conflict` (error) naming both folders.

#### Scenario: Authored record wins
- **GIVEN** the vendored device `Demo:EXB` and a project device in `devices/` with the same id
- **WHEN** a design using it is built
- **THEN** the project device is used and `issues` holds `library.overrides-item`

#### Scenario: Two vendored items, one id
- **GIVEN** two vendored device folders that both hold the record `Shop:X`, and a design using `Shop:X`
- **WHEN** it is built
- **THEN** the build reports `library.item-conflict` naming both folders and writes nothing

#### Scenario: Unused vendored item changes nothing
- **GIVEN** a design using only shipped devices, built once without and once with a vendored `Demo:EXB`
- **WHEN** both output trees are compared
- **THEN** they are byte-identical

### Requirement: Vendored records in checks and private tests
Circuit checks and private block tests SHALL use the owning project's authored records before vendored records, with native reference files preserved. Private tests MUST leave source files and locks unchanged. Conflicting vendored identities MUST remain error findings in circuit checks. A golden plan MUST bind the device inputs used by its private build.

#### Scenario: Vendored block uses a vendored device
- **GIVEN** a block and its device items fetched from authored local releases, with an optional authored device override
- **WHEN** its usage example and a plain test calling `instantiate` run
- **THEN** both private builds resolve the device and the original project bytes are unchanged

#### Scenario: Circuit check finds conflicting vendored data
- **GIVEN** a built design whose device id now occurs in two vendored folders, with or without an authored override
- **WHEN** `check --stages circuit.rules` runs
- **THEN** it reports `library.item-conflict` and does not select a conflicting vendored device

#### Scenario: Device edit after golden review
- **GIVEN** a dry-run golden plan for a vendored block using an authored device override
- **WHEN** the device record changes before confirmation
- **THEN** confirmation gives `FEN-4002` and writes no golden

### Requirement: Device builds stay offline
No build, check, `capabilities` or `doctor` run SHALL open a network connection or read device data outside the project, the shipped catalog and, for hints only, the cached library index. An unknown id whose namespace is in the newest cached index SHALL get the hint `fenolite get device <id> --dry-run`.

#### Scenario: Build with vendored records and no network
- **GIVEN** `socket.socket.connect` patched to raise and a vendored `Demo:EXB`
- **WHEN** a design using it is built
- **THEN** it succeeds and no connection was attempted

#### Scenario: Hint for a library id
- **GIVEN** a cached library index holding `device` `Demo:OTHER` and a design naming `Demo:OTHER`, not vendored
- **WHEN** the design is built
- **THEN** it fails as an unknown device and the message names `fenolite get device Demo:OTHER --dry-run`
