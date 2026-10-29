## MODIFIED Requirements

### Requirement: Evidence matrix in capabilities
`fenolite capabilities` SHALL fill `result.matrix` with `MatrixRow.to_json()` of every row of `fenolite.backends.matrix.rows()`, in that order (`backend-protocol`, "Evidence matrix rows"). Each entry MUST have exactly the keys `backend`, `kind`, `detect`, `read`, `write`, `roundtrip_exact`, `roundtrip_modified`, `verified_by`, `experimental` and `versions`.
- An operation is `null` when the backend package does not implement it for that kind, and the label of its evidence otherwise. The label states what holds for an arbitrary file of the kind. It is never stronger than the register row of an id in `verified_by` (`verification-evidence`, "Declared levels agree with the register").
- `verified_by` lists the hypothesis ids behind the row, sorted. Their statements, tests and results are rows of `docs/hypotheses.md`, and `docs/evidence/matrix.md` shows the level of each.
- `versions` maps each operation that is not `null` to the format versions it was verified on, each `{version, tool, level, source}`: the version of the file format (a KiCad file version such as `20260206`, or an Altium Designer version such as `AD 26.5`), the tool that verified it, the level reached, and the test file or the kit run that reached it. An operation's label MUST NOT be stronger than the lowest level of its versions, and an operation with no version MUST be labelled `INFERRED` or lower.
- An operation listed in `experimental` MAY change its output, its options or its issue codes in any release. An operation labelled `UNVERIFIED` MUST be listed there.
- Every write kind of every entry of `result.experimental` MUST have a row whose `write` is set and whose `experimental` contains `write`.
- Listing the matrix MUST NOT run an external tool, so `result.matrix` is the same with `--no-tools`. The `claims` modules MUST be imported inside `cmd_capabilities._run`, not when `fenolite.cli.cmd_capabilities` is imported.
- `result.backends` and `result.experimental` MUST stay as they are: the matrix adds a key and changes none.
- `docs/cli-contract.md` MUST describe `result.matrix` under "Discovery", with the meaning of the five operations, of `versions` and one example row.

#### Scenario: Matrix listed
- **WHEN** `uv run fenolite capabilities --json --no-tools` runs
- **THEN** the exit code is 0, `result.matrix` is sorted by `backend` and then `kind`, its row for `kicad` and `kicad_pcb` has `read`, `write`, `roundtrip_exact` and `roundtrip_modified` set and `H-K-PCB-READ` and `H-K-PCB-WRITE` in `verified_by`, and the envelope validates against the envelope schema of `CONTRACT_VERSION`

#### Scenario: Board versions listed
- **WHEN** `uv run fenolite capabilities --json --no-tools` runs
- **THEN** the `versions` of the row for `kicad` and `kicad_pcb` hold, under `read`, the versions `20241229` with the tool `kicad-cli 9.0.9` and `20260206` with `kicad-cli 10.0.6`, each with a `source` that is a test file of the repository

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

## ADDED Requirements

### Requirement: Evidence of every reply
Every reply SHALL follow two rules: an `evidence.level` other than `UNVERIFIED` and `UNKNOWN` MUST name at least one hypothesis in `evidence.hypotheses`, and an `UNVERIFIED` level MUST come from a command of `fenolite.cli.api.NO_CLAIM` (the commands whose replies state nothing about a design or a file) or from a reply that names an experimental feature in its issues; an `UNKNOWN` level MUST come only from the detection of a file that no backend knows. `fenolite capabilities` MUST mark each command's entry with `claims` (`false` for the commands of `NO_CLAIM`). With `FENOLITE_CONTRACT_CHECK=1` a reply that breaks a rule MUST end in `FEN-1001`; without it the reply MUST be written with one more issue `cli.evidence-unsound` (warning) that names the rule. The consistency suite MUST run every command's example with `FENOLITE_CONTRACT_CHECK=1`.

#### Scenario: Every example follows the rules
- **WHEN** `uv run pytest tests/consistency` runs every command's example with `FENOLITE_CONTRACT_CHECK=1`
- **THEN** no reply ends in `FEN-1001`

#### Scenario: INFERRED without a hypothesis is caught
- **GIVEN** `_echo` set in a test to answer `INFERRED` with no hypothesis
- **WHEN** it runs with `FENOLITE_CONTRACT_CHECK=1`
- **THEN** the exit code is 1 and the error is `FEN-1001`; without the variable the exit code is 0 and `issues` holds one `cli.evidence-unsound`

#### Scenario: A no-claim command may be UNVERIFIED
- **WHEN** `uv run fenolite explain FEN-2001 --json` runs with `FENOLITE_CONTRACT_CHECK=1`
- **THEN** the exit code is 0 and `evidence.level` is `UNVERIFIED`
