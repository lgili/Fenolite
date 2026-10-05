## ADDED Requirements

### Requirement: Evidence matrix in capabilities
`fenolite capabilities` SHALL fill `result.matrix` with `MatrixRow.to_json()` of every row of `fenolite.backends.matrix.rows()`, in that order (`backend-protocol`, "Evidence matrix rows"). Each entry MUST have exactly the keys `backend`, `kind`, `detect`, `read`, `write`, `roundtrip_exact`, `roundtrip_modified`, `verified_by` and `experimental`.
- An operation is `null` when the backend package does not implement it for that kind, and the label of its evidence otherwise. The label states what holds for an arbitrary file of the kind. It is never stronger than the register row of an id in `verified_by` (`verification-evidence`, "Declared levels agree with the register").
- `verified_by` lists the hypothesis ids behind the row, sorted. Their statements, tests and results are rows of `docs/hypotheses.md`, and `docs/evidence/matrix.md` shows the level of each.
- An operation listed in `experimental` MAY change its output, its options or its issue codes in any release. An operation labelled `UNVERIFIED` MUST be listed there.
- Every write kind of every entry of `result.experimental` MUST have a row whose `write` is set and whose `experimental` contains `write`.
- Listing the matrix MUST NOT run an external tool, so `result.matrix` is the same with `--no-tools`. The `claims` modules MUST be imported inside `cmd_capabilities._run`, not when `fenolite.cli.cmd_capabilities` is imported.
- `result.backends` and `result.experimental` MUST stay as they are: the matrix adds a key and changes none.
- `docs/cli-contract.md` MUST describe `result.matrix` under "Discovery", with the meaning of the five operations and one example row.

#### Scenario: Matrix listed
- **WHEN** `uv run fenolite capabilities --json --no-tools` runs
- **THEN** the exit code is 0, `result.matrix` is sorted by `backend` and then `kind`, its row for `kicad` and `kicad_pcb` has `read`, `write`, `roundtrip_exact` and `roundtrip_modified` set and `H-K-PCB-READ` and `H-K-PCB-WRITE` in `verified_by`, and the envelope validates against `schemas/fenolite.envelope.v0.json`

#### Scenario: Missing operation is null
- **WHEN** `uv run pytest tests/unit/cli/test_capabilities_matrix.py -k null` reads the row for `specctra` and `specctra_dsn`
- **THEN** its `write` is a label, and its `read`, `roundtrip_exact` and `roundtrip_modified` are `null`

#### Scenario: Board row and backend report agree
- **WHEN** `uv run pytest tests/unit/cli/test_capabilities_matrix.py -k agree` compares the `kicad_pcb` row with the `kicad` entry of `result.backends`
- **THEN** the row's `roundtrip_modified` starts with the entry's `evidence.level`, and every id of the entry's `evidence.hypotheses` is in the row's `verified_by`

#### Scenario: Experimental writers are marked
- **WHEN** `uv run pytest tests/unit/cli/test_capabilities_matrix.py -k experimental` reads `result.experimental` and `result.matrix`
- **THEN** every kind of every entry's `write_kinds` has a row with `write` set and `write` in `experimental`

#### Scenario: Same matrix without tool detection
- **WHEN** `uv run fenolite capabilities --json` and `uv run fenolite capabilities --json --no-tools` run
- **THEN** both `result.matrix` values are equal

#### Scenario: Field projection
- **WHEN** `uv run fenolite capabilities --json --no-tools --fields matrix` runs
- **THEN** `result` contains only `matrix`, and the exit code is 0

#### Scenario: Importing the command stays light
- **WHEN** `uv run python -c "import sys, fenolite.cli.cmd_capabilities; print(sorted(m for m in sys.modules if m.endswith('.claims')))"` runs
- **THEN** it prints `[]` and exits 0
