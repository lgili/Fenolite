# fenolite-library Specification

## Purpose
TBD - created by archiving change c0281-import-copy-fidelity. Update Purpose after archive.
## Requirements
### Requirement: Skipped levels in the proof gate
The proof gate SHALL accept a level `skipped` only when `fidelity.proof.skipped` gives its reason and the reason is not `build-failed`; the derived result is unchanged by a skipped level and MUST list the skipped levels with their reasons. Until c0278's level S runs on drawn imports, `S` skipped with `drawn-unavailable` passes.

#### Scenario: Level S skipped with a reason
- **GIVEN** a fixture proof whose levels are `equal` and whose `S` is `skipped` with `fidelity.proof.skipped.S` `drawn-unavailable`
- **WHEN** `uv run pytest tests/unit/library/test_proof_gate.py -k skipped` runs
- **THEN** the gate result is `pass` and lists `S: drawn-unavailable`; without the reason, or with `build-failed`, it is `fail`

### Requirement: Replayable conversion steps
A step of `conversion.steps` SHALL NOT hold `--plan`: a plan id hashes its working folder and cannot replay elsewhere. A writing step MUST be recorded with `--confirm` alone. `library audit` MUST give `library.provenance-invalid` for a step with `--plan`; `replay` runs each step as recorded.

#### Scenario: Step with a plan id
- **GIVEN** a fixture board item whose second step ends with `--confirm --plan 0123456789abcdef`
- **WHEN** `uv run pytest tests/unit/library/test_audit.py -k plan_step` runs
- **THEN** the audit reports `library.provenance-invalid` naming the step; with `--confirm` alone it passes, and its replay in a fresh folder gives the recorded `outputs_tree`

### Requirement: Preserve approved licence registry entries across repositories
The shipped registry SHALL retain all previously approved text digests and
match the library registry after incorporating documented maintainer approvals.

#### Scenario: Synchronize the reviewed registry union
- **WHEN** both old registries and new text approvals are reconciled
- **THEN** every old approved digest remains allowed
- **AND** the shipped registry equals the library registry without relaxing any other licence rule

### Requirement: Conservative LibrePCB legacy metadata and pads
The bounded 0.1 seed SHALL select a unique unlocalized name alongside well-formed unique locale alternatives. It SHALL accept a scalar drill only when zero and unaccompanied by a hole. An absent package_pad MAY use the pad UUID only when declared by the package. Ambiguous names, unknown references and nonzero or malformed legacy drills SHALL remain explicit refusals.

#### Scenario: Localized metadata preserves the default
- **GIVEN** an authored element with one default name and distinct valid localized names
- **WHEN** it is read
- **THEN** its default name is kept and no translated text replaces it

#### Scenario: Ambiguous defaults refuse
- **WHEN** two unlocalized names or duplicate locale identities are present
- **THEN** the element is explicitly refused

#### Scenario: Legacy surface pad binds safely
- **GIVEN** a zero scalar drill and pad UUID declared in its package
- **WHEN** the footprint is seeded
- **THEN** its exact surface pad geometry and package mapping are retained

#### Scenario: Drill information cannot disappear
- **WHEN** a scalar drill is nonzero, malformed or coexists with a hole
- **THEN** the footprint is refused without a fabricated surface pad

#### Scenario: Declared reference prefix remains visible
- **GIVEN** an authored component declaring a valid prefix
- **WHEN** symbol and device records are seeded
- **THEN** both keep that prefix; a missing field alone uses U and an invalid field is refused

### Requirement: Numeric internal function normalization is reversible
The seed converter SHALL normalize an ASCII numeric internal function name to
Pin_<original>, without changing the symbol's visible pin name, pin number,
UUID relationship or electrical mapping. It SHALL refuse identifier collisions
and other invalid names. It SHALL emit library.seed-function-normalized and
record the ordered UUID/original/normalized map in the existing dated provenance
modification_notice and NOTICE. Geometry and evidence SHALL remain unchanged.

#### Scenario: Numeric resistor functions
- **WHEN** authored signals named 1 and 2 map to two symbol pins and package pads
- **THEN** device functions are Pin_1 and Pin_2, symbol names/numbers remain 1/2,
  and replay preserves the same partition and source-bound normalization map

#### Scenario: Legal identifier collision
- **WHEN** signals 1 and Pin_1 would share a normalized identifier
- **THEN** the device is refused explicitly and no device is planned

### Requirement: Signed cardinal pin angles retain exact orientation
The seed converter SHALL canonicalize only exact cardinal pin rotations modulo
360 degrees, preserve a source-bound map in warning and existing provenance
notice, and refuse noncardinal input without rounding.

#### Scenario: Signed cardinal and near-cardinal
- **WHEN** a source pin has rotation -90deg
- **THEN** it emits270deg with the same native orientation and partition
- **WHEN** it has45deg or -90.0001deg
- **THEN** its component and dependent devices are explicitly refused

### Requirement: Curated artwork is explicit and reproducible
The review draft SHALL retain its immutable raw seed separately and record its
exact source-bound change in existing provenance notice and NOTICE. Only two
resistor graphical pin lengths SHALL change from2,000,000nm to2,032,000nm; pin
anchors/names/numbers, device mappings and physical footprint geometry SHALL
remain unchanged. No checker waiver or source-parser rounding is permitted.

#### Scenario: Reproducible four-item review candidate
- **WHEN** the external recipe runs twice on the same byte-attested raw seed
- **THEN** all candidate file hashes match, complete library check returns exit0 with zero ERROR and all four preferred100mil WARN visible,
  and native before/after partitions match the same expected three nets
- **AND** the generated preview identifies the two changed lengths explicitly
- **AND** human acceptance, integration and release gates remain pending

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

### Requirement: Device source registers in library checks
`library check` SHALL read an external `fenolite.library-sources.v0` D-id register through the validated device-register loader. Registered D ids MUST pass the source check; unregistered ids MUST produce `library.source-unknown` even when mentioned in comments or the register is missing. Malformed register rows MUST fail with `FEN-3004`. Existing shipped S-id checks SHALL remain available.

#### Scenario: Registered external device sources
- **GIVEN** authored external symbol, footprint and device items citing registered `D-0003`
- **WHEN** `library check` checks their records
- **THEN** source validation passes for all three kinds

#### Scenario: Unregistered external source in a comment
- **GIVEN** the records cite `D-0099`, mentioned only in a source-register comment
- **WHEN** `library check` checks them
- **THEN** it exits 5 with `library.source-unknown` naming `D-0099`

#### Scenario: Missing external source register
- **GIVEN** authored item records cite D ids but have no source register
- **WHEN** `library check` checks them
- **THEN** it exits 5 with `library.source-unknown` rather than accepting unchecked D ids

#### Scenario: Malformed external source row
- **GIVEN** `D-0003` lacks its required `used` field
- **WHEN** `library check` checks a record citing it
- **THEN** it exits 3 with `FEN-3004` and plans no write

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

