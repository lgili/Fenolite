# canonical-serialization Specification

## Purpose
Give every design one byte-stable JSON representation that re-serialises idempotently, diffs cleanly in Git and is validated on read.
## Requirements
### Requirement: Canonical JSON form
`fenolite.model.canonical.dumps(design)` SHALL produce UTF-8 text with LF line endings and two-space indentation, keys in dataclass field order, collections sorted by `(kind, path-or-ref-or-name, id)`, default values omitted, integers only, and `ext` emitted verbatim with sorted backend keys.

#### Scenario: Idempotence
- **GIVEN** any design produced by the hypothesis strategy
- **WHEN** `dumps(loads(dumps(d)))` is computed
- **THEN** it equals `dumps(d)` byte for byte

#### Scenario: Order independence
- **GIVEN** two designs equal except for the insertion order of their tracks
- **WHEN** both are serialised
- **THEN** the outputs are identical

#### Scenario: Defaults omitted
- **GIVEN** a component with `dnp = False`
- **WHEN** it is serialised
- **THEN** the key `dnp` is absent

### Requirement: One file per layer
`canonical.dump_dir(design, path)` SHALL write `meta.json`, `circuit.json`, `board.json`, `rules.json`, `manufacturing.json` and `findings.json` under `path`, and `meta.json` MUST contain `schema_version = "0"` and the `fenolite_version`.

#### Scenario: Directory layout
- **WHEN** a design is dumped to `.fenolite/`
- **THEN** exactly those six files exist and `meta.json` carries `schema_version` `"0"`

### Requirement: Schema generation and drift control
`tools/gen_schemas.py` SHALL generate `schemas/fenolite.model.v0/<layer>.json` from the dataclasses, and `tests/unit/test_schema_drift.py` MUST fail if regeneration changes any byte of the committed schemas.

#### Scenario: Drift detected
- **GIVEN** a contributor adds a field to `Track` without regenerating schemas
- **WHEN** the drift test runs
- **THEN** it fails naming `board.json`

### Requirement: Validation against schema
`canonical.loads` MUST validate the document against the layer schema before constructing objects and MUST raise `FormatError` with the JSON pointer of the first violation.

#### Scenario: Wrong type reported with pointer
- **GIVEN** `board.json` where `tracks[3].width` is a string
- **WHEN** `canonical.load_dir` runs
- **THEN** `FormatError.locator` equals `/tracks/3/width`

### Requirement: Readable diffs
Renaming a component reference or moving a footprint SHALL change only the lines that describe that object in the canonical files.

#### Scenario: Move one footprint
- **GIVEN** a canonical dump of a design
- **WHEN** one footprint is moved by 1 mm and the design is dumped again
- **THEN** `diff` between the two `board.json` files touches only that footprint's `position` lines

