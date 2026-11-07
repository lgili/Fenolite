## ADDED Requirements

### Requirement: Model schema version
`fenolite.model.design.SCHEMA_VERSION` SHALL be `"1.0"`, of the form `MAJOR.MINOR`. A release that changes the model only by adding optional fields with a default MUST raise the minor; a release that changes a field's type, meaning or name, or removes a field, MUST raise the major. `docs/design-model.md` MUST state the rule and list, per version, what it added. A model folder written by Fenolite MUST carry `SCHEMA_VERSION` in `meta.json`.

#### Scenario: A build writes 1.0
- **WHEN** `fenolite build examples/blink_2layer/design.py --out OUT --confirm` runs
- **THEN** `OUT/.fenolite/meta.json` holds `"schema_version": "1.0"`

### Requirement: Migrators
`fenolite.model.migrate` SHALL hold the chain of migration steps from `"0"` to `SCHEMA_VERSION`, each a pure function of the JSON of a whole model folder. `canonical.load_dir` MUST migrate a folder of an older version in memory before it validates it against the current schemas, MUST write nothing, and MUST add one `model.migrated` issue (info, `where` the folder) that names the steps taken. A folder at the current version MUST load without that issue.

#### Scenario: Every release's folder loads
- **GIVEN** the model folders that the releases `0.1.0` to `0.5.0` wrote for `examples/blink_2layer` (`tests/data/model/<tag>/`)
- **WHEN** `uv run pytest tests/unit/model/test_migrate.py` loads each with `canonical.load_dir`
- **THEN** each loads with one `model.migrated` info, and the design dumps to the layer files that the current release writes for the same board, but for the fields the current release adds

#### Scenario: A current folder is not migrated
- **WHEN** a folder written with `SCHEMA_VERSION` is loaded
- **THEN** no `model.migrated` issue is given

### Requirement: Future versions are refused
A model folder whose `schema_version` has a higher major than `SCHEMA_VERSION`, or the same major and a higher minor, SHALL be refused with `FEN-3002` (exit 3), and the message MUST name the version of the folder and the version the reader supports. A folder whose version has no known form MUST be refused with `FEN-3004`.

#### Scenario: A newer minor is refused
- **GIVEN** a model folder whose `meta.json` holds `"schema_version": "1.1"`
- **WHEN** `fenolite diff OUT1 OUT2` reads it
- **THEN** the exit code is 3, the error is `FEN-3002`, and its message names `1.1` and `1.0`

### Requirement: Migrate command
`fenolite migrate DIR` SHALL plan the layer files of the model folder `DIR` migrated to `SCHEMA_VERSION` under the mutation protocol (`cli-contract`, "Mutation protocol"): `--dry-run` writes nothing, `--confirm` writes every file or none and keeps a `.bak` of each. `result` MUST hold `from`, `to` and `steps`. A folder already at `SCHEMA_VERSION` MUST plan no write and exit 0.

#### Scenario: A 0.5.0 folder is rewritten
- **GIVEN** a copy of `tests/data/model/v0.5.0`
- **WHEN** `fenolite migrate COPY --confirm --json` runs
- **THEN** the exit code is 0, `result.from` is `0` and `result.to` is `1.0`, every layer file is rewritten with a `.bak`, and `canonical.load_dir(COPY)` gives no `model.migrated` issue

### Requirement: Pre-freeze review of the model
Before `SCHEMA_VERSION` becomes `"1.0"`, `tools/model_review.py` SHALL list every dataclass of `fenolite.model` with its fields, types and defaults, and every extension-bag key of each backend, each with the modules that read it, and the maintainer's decision for each item (keep, rename, drop) MUST be recorded in the change. Each rename and drop MUST be a part of the step `"0" -> "1.0"`.

#### Scenario: The review lists every field
- **WHEN** `uv run python tools/model_review.py` runs
- **THEN** its list holds every field of `fenolite.model.board.Track`, among the others, with its type and default
