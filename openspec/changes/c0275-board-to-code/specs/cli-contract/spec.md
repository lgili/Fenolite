## ADDED Requirements

### Requirement: Import command
`fenolite import PATH --to python --out DIR` SHALL be a mutating command of the registry (`src/fenolite/cli/cmd_import.py`), described in `docs/cli-contract.md` ("import") with its options, result schema `fenolite.import.v0` and codes. Its declared inputs MUST be every file it read, upgraded sources by their original bytes. Its example arguments MUST name an authored board under `tests/data/import_python/`.

#### Scenario: Consistency suite covers the import
- **WHEN** `uv run pytest tests/consistency -q` runs
- **THEN** `import` is planned with its example arguments, its run without `--confirm` exits 4 with `FEN-4001`, and the confirmed plan writes only under the temporary project

#### Scenario: Plan id binds the inputs
- **GIVEN** a dry run of the import of the authored project
- **WHEN** one of its sheet files is edited and `--confirm --plan <plan_id>` runs
- **THEN** the exit code is 4 with `FEN-4002` and nothing is written
