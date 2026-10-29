## ADDED Requirements

### Requirement: Roles command
`fenolite roles PATH` SHALL infer, show, confirm and check net roles (schema `fenolite.roles.v0`, `src/fenolite/cli/cmd_roles.py`). It MUST be read-only without an accept, set or reject option, and a writing command of "Mutation protocol" with one. `--check` MUST add `measures` and `summary` and run no tool. A bad option MUST be `FEN-2001`. `docs/cli-contract.md` MUST document it under the heading `roles`.

#### Scenario: Read-only by default
- **GIVEN** `subprocess.run` patched to raise and a snapshot of the folder of a reference board
- **WHEN** `uv run pytest tests/unit/cli/test_roles_cmd.py -k readonly` runs `fenolite roles <board> --check --json`
- **THEN** it exits 0 and the folder is unchanged

#### Scenario: Write needs confirmation
- **WHEN** `fenolite roles <board> --accept SW --json` runs without `--dry-run` or `--confirm`
- **THEN** the exit code is 4, stderr holds `FEN-4001`, and nothing is written

#### Scenario: Usage error
- **WHEN** `fenolite roles <board> --set SW=motor` runs
- **THEN** the exit code is 2 and stderr holds `FEN-2001`
