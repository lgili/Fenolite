## ADDED Requirements

### Requirement: Verification matrix of check
`fenolite check PATH --matrix` SHALL add `result.matrix` with `receipt` (`fenolite`, `model_sha256`, `devices_sha256`, `stages`) and `rows`: the requirement rows of the stages that ran, sorted by id, each with `id`, `check`, `value`, `limit`, `source`, `origin`, `status` (`pass`, `fail`, `unsure`, `unknown`, `deferred` or `waived`), `evidence`, `decidable`, `digest` and `waiver`. The command MUST stay read-only. Without `--matrix` the result MUST NOT hold `matrix`.

#### Scenario: The matrix of the bad sensor
- **GIVEN** the `bad` variant of `examples/circuit/sensor` built in `tmp_path`, with one waiver of the capacitor's row at its current digest
- **WHEN** `uv run pytest tests/unit/cli/test_check_matrix.py` runs `fenolite check <dir> --matrix --json` twice
- **THEN** both replies are byte-identical, `result.matrix.rows` holds `circuit.rating-voltage:C1:voltage` with status `waived` and `circuit.rating-current:L1:current` with status `fail`, `receipt.model_sha256` is the SHA-256 of the model texts, and the folder is unchanged

#### Scenario: The matrix in a terminal
- **WHEN** the same command runs with `--matrix --text`
- **THEN** stdout is a table with the columns `id`, `check`, `value`, `limit`, `source` and `status`, one line per row
