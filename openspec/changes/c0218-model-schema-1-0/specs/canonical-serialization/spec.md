## MODIFIED Requirements

### Requirement: Schema generation and drift control
`tools/gen_schemas.py` SHALL generate `schemas/fenolite.model.v<MAJOR>/<layer>.json` from the dataclasses, for the major of `SCHEMA_VERSION`, and `tests/unit/test_schema_drift.py` MUST fail if regeneration changes any byte of the committed schemas. The layer schemas of a major that was released MUST stay in `schemas/` byte for byte.

#### Scenario: Drift detected
- **GIVEN** a contributor adds a field to `Track` without regenerating schemas
- **WHEN** the drift test runs
- **THEN** it fails naming `board.json`

#### Scenario: The v0 schemas stay
- **WHEN** the schemas are regenerated for `SCHEMA_VERSION` `"1.0"`
- **THEN** `schemas/fenolite.model.v1/` holds the layer schemas and every file of `schemas/fenolite.model.v0/` is unchanged

## ADDED Requirements

### Requirement: Versioned schemas
Validation in `canonical.loads` and `canonical.load_dir` SHALL use the layer schemas of the major of `SCHEMA_VERSION`, after a folder of an older version is migrated (`model-versions`, "Migrators"); a document is never validated against the schema of the version it was written with.

#### Scenario: A v0 board validates after migration
- **GIVEN** `tests/data/model/v0.2.1/blink_2layer.board.json` in a folder of version `"0"`
- **WHEN** `canonical.load_dir` reads the folder
- **THEN** the board is validated against `schemas/fenolite.model.v1/board.json` after the migration, and no `FormatError` is raised
