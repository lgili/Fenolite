## ADDED Requirements

### Requirement: Fill command
`fenolite fill PATH [--from REFILLED] [-o OUT] [--kicad-cli PATH] [--timeout SECONDS]` SHALL be registered by `src/fenolite/cli/cmd_fill.py` with `mutates=True`, and SHALL write the board that `PATH` names with the zone fills that `kicad-cli` 10 computes.
- **Board.** `PATH` MUST resolve with `projectset.resolve_board`; the usage and input errors are `check`'s (`FEN-2001`, `FEN-3001`).
- **Refill.** Without `--from`, the command MUST refill the project's copy set through `KicadOracle.refill` and MUST exit 6 with `FEN-6001` when no `kicad-cli` is found and with `FEN-6002` when its major is below 10; the hint MUST name `--from` and `--kicad-cli docker:<image>`. `--timeout` MUST default to 300.
- **From a file.** With `--from REFILLED`, the command MUST lift from that board and MUST run no subprocess.
- **Write.** The command MUST return one `PlannedWrite` for the board, at `--out` when given and at the board's own path otherwise, both relative to the working directory, and none when nothing changes. The mutation protocol (`--dry-run`, `--confirm`, backup, receipt) applies unchanged.
- **Result.** `result` MUST hold `board`, `target`, `changed`, `zones` (`id`, `name`, `layers`, `fills`, `islands`, `filled`; sorted by name, then id), `tool_version` and `tool_writes`. No value MUST hold a temporary path, the home directory or a date.
- **Exit codes.** 0 when the board is written or already current; 5 with `zone.fill-mismatch`; 3 for a board Fenolite cannot read; 7 for a board older than KiCad 9 (`FEN-7003`).
- `example_args` MUST be `(EXAMPLE_UNFILLED, "--from", EXAMPLE_REFILLED, "--out", "fenolite-filled.kicad_pcb", "--dry-run")`, and `mutation_example_args` the same without `--dry-run`; both MUST run no subprocess from any working directory.

#### Scenario: Plan, then write
- **GIVEN** a confirmed blink build and a fake `kicad-cli` 10.0.6 that saves a refilled board
- **WHEN** `uv run pytest tests/unit/cli/test_fill_cmd.py -k plan` runs `fenolite fill <dir> --dry-run` and then `--confirm`
- **THEN** the first exits 0 with a one-file plan and writes nothing, and the second writes the board, keeps a `.bak`, and its receipt names the board

#### Scenario: Already current
- **GIVEN** the board that the previous scenario wrote
- **WHEN** `fenolite fill <dir> --confirm` runs again
- **THEN** the exit code is 0, `result.changed` is `false`, and no file changes

#### Scenario: KiCad 9 only
- **GIVEN** a fake `kicad-cli` whose `version` prints `9.0.9`
- **WHEN** `fenolite fill <dir> --confirm` runs
- **THEN** the exit code is 6, stderr carries `FEN-6002`, and the hint names `--from` and `docker:`

#### Scenario: Lift from a file
- **GIVEN** `subprocess.run` and `subprocess.Popen` patched to raise
- **WHEN** `uv run pytest tests/unit/cli/test_hermetic_examples.py` runs `fill` with its `example_args`
- **THEN** the exit code is 0 and the plan names `fenolite-filled.kicad_pcb`

#### Scenario: Fill is deterministic
- **WHEN** `uv run pytest tests/kicad/fill/test_fill_oracle.py -k deterministic` runs `fenolite fill --confirm` on two copies of the built blink on 10.0.6
- **THEN** the two boards have equal bytes
