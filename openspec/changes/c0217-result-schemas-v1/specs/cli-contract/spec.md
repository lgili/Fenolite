## MODIFIED Requirements

### Requirement: Consistency test covers every command
`tests/consistency/test_cli_consistency.py` SHALL enumerate all registered commands and verify `--help`, JSON envelope validity, text mode, `--fields`, error mapping and, for mutating commands, the mutation protocol. For every visible command it MUST also find a result schema ("Result schemas") and validate the `result` of the command's example against the closed form of that schema (`tests/_schema.closed`: no key that the schema does not name).

#### Scenario: New command without envelope fails the suite
- **GIVEN** a contributor registers `cmd_foo.py` whose `run` returns a plain dict
- **WHEN** the consistency test runs
- **THEN** it fails naming `foo`

#### Scenario: New command without a result schema fails the suite
- **GIVEN** a contributor registers a visible command `foo` with no entry in `fenolite.cli.results.RESULTS`
- **WHEN** the consistency test runs
- **THEN** it fails naming `foo` and the missing schema

#### Scenario: An undocumented key fails the suite
- **GIVEN** a command whose example result holds a key that its wire class does not name
- **WHEN** the consistency test runs
- **THEN** it fails naming the command and the key's path

## ADDED Requirements

### Requirement: Result schemas
Every visible command SHALL have a wire class in `fenolite.cli.results.RESULTS` that describes its `result`, and `tools/gen_schemas.py` SHALL write `schemas/fenolite.<command>.<CONTRACT_VERSION>.json` from it, with `additionalProperties: true` on every object (the published form). `tools/gen_schemas.py --check` MUST exit 1 when a committed schema differs from a fresh generation. After the release of `1.0.0`, a release of the `1.x` series MUST NOT remove a property of a result schema nor change its type: the drift test compares the property names and types of each schema with the file of the last release tag. `docs/cli-contract.md` MUST name each command's schema file in its section.

#### Scenario: Every command has a schema
- **WHEN** `uv run python tools/gen_schemas.py --check` runs
- **THEN** it exits 0 and `schemas/` holds one result schema for each of the visible commands

#### Scenario: A published schema accepts an added key
- **GIVEN** the published schema of `check` and a result of `check` with one more key at its top level
- **WHEN** the result is validated against the published schema
- **THEN** it validates, and against the closed form it does not

#### Scenario: A removed property is refused after 1.0
- **GIVEN** a schema of `bom` without the property `rows` against a last release tag whose schema holds it
- **WHEN** `uv run pytest tests/unit/test_schema_drift.py` runs
- **THEN** it fails naming `bom` and `rows`

### Requirement: File format schemas
Each file format that Fenolite reads or writes beside a design and that is classified public (written by a user, or read by an agent as a command's output) SHALL have a schema file `schemas/fenolite.<name>.v1.json` generated from its dataclass, and its reader MUST accept a document of `fenolite.<name>.v0` and of `fenolite.<name>.v1`. `schemas/README.md` MUST list each format id found in `src/fenolite` with its class, `public` or `internal`; an internal format carries no promise between releases.

#### Scenario: A v0 document is still read
- **GIVEN** a `requirements` file of `fenolite.requirements.v0` that `fenolite analyze` read in `0.5.0`
- **WHEN** `fenolite analyze --requirements FILE` runs
- **THEN** it reads the file as before, with no issue about its version

#### Scenario: Every format id is classified
- **WHEN** `uv run python tools/gen_schemas.py --formats --check` runs
- **THEN** it exits 0, and every `fenolite.<name>.v0` id of `src/fenolite` is listed in `schemas/README.md` as `public` or `internal`
