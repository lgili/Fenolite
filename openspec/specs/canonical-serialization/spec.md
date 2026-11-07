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
`tools/gen_schemas.py` SHALL generate `schemas/fenolite.model.v<MAJOR>/<layer>.json` from the dataclasses, for the major of `SCHEMA_VERSION`, and `tests/unit/test_schema_drift.py` MUST fail if regeneration changes any byte of the committed schemas. The layer schemas of a major that was released MUST stay in `schemas/` byte for byte.

#### Scenario: Drift detected
- **GIVEN** a contributor adds a field to `Track` without regenerating schemas
- **WHEN** the drift test runs
- **THEN** it fails naming `board.json`

#### Scenario: The v0 schemas stay
- **WHEN** the schemas are regenerated for `SCHEMA_VERSION` `"1.0"`
- **THEN** `schemas/fenolite.model.v1/` holds the layer schemas and every file of `schemas/fenolite.model.v0/` is unchanged

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

### Requirement: Layer texts in memory
`fenolite.model.canonical.dump_texts(design) -> dict[str, str]` SHALL return the six layer files of "One file per layer" as a mapping from file name (`meta.json`, `circuit.json`, `board.json`, `rules.json`, `manufacturing.json`, `findings.json`) to text, without touching the file system.
- `dump_dir(design, path)` MUST write exactly the texts of `dump_texts(design)`, encoded as UTF-8, so its output bytes do not change.
- A command that writes the layer files through the mutation protocol, such as `build`, MUST take them from `dump_texts` and MUST NOT call `dump_dir`.
- `load_dir` MUST read only the six layer files, so another file in the same folder, such as `.fenolite/build.json`, is ignored and does not count as a layer file.

#### Scenario: Same bytes as dump_dir
- **GIVEN** the model of the built blink design
- **WHEN** `uv run pytest tests/unit/model/test_dump_texts.py` compares `dump_texts(design)` with the files `dump_dir(design, tmp_path)` writes
- **THEN** the keys are the six layer file names and each text, encoded as UTF-8, equals the bytes of the file with that name

#### Scenario: Nothing written
- **GIVEN** an empty temporary working directory
- **WHEN** `dump_texts(design)` is called
- **THEN** the directory is still empty

#### Scenario: Build record ignored on load
- **GIVEN** a folder written by `dump_dir` that also holds a `build.json`
- **WHEN** `load_dir` reads it
- **THEN** it returns the design without error, equal to the design read from the same folder without `build.json`

### Requirement: Versioned schemas
Validation in `canonical.loads` and `canonical.load_dir` SHALL use the layer schemas of the major of `SCHEMA_VERSION`, after a folder of an older version is migrated (`model-versions`, "Migrators"); a document is never validated against the schema of the version it was written with.

#### Scenario: A v0 board validates after migration
- **GIVEN** `tests/data/model/v0.2.1/blink_2layer.board.json` in a folder of version `"0"`
- **WHEN** `canonical.load_dir` reads the folder
- **THEN** the board is validated against `schemas/fenolite.model.v1/board.json` after the migration, and no `FormatError` is raised

### Requirement: Drawn style default omission
New optional drawn style fields SHALL be omitted when absent. Old canonical JSON and drawn TOML without them MUST retain exact bytes, ids and ordering. Explicit false and zero MUST remain distinguishable from absence. All existing example build maps MUST pass without rebaselining.

#### Scenario: Legacy drawing
- **GIVEN** a canonical drawing without optional fonts or new sheet-property poses
- **WHEN** it is read, serialized and built
- **THEN** its canonical bytes and existing planned-file digests are unchanged

#### Scenario: Explicit false
- **WHEN** a drawing with explicit false bold is read and written twice
- **THEN** false remains present and both canonical texts are identical

