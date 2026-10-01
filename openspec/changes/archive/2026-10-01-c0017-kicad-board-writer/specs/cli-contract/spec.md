## ADDED Requirements

### Requirement: KiCad target and lossy flags
Every `fenolite` command SHALL accept the global flags `--kicad-version {9,10}` (default 10) and `--allow-lossy`, before or after the command name, like `--seed`. The dispatcher MUST pass them to the command as `Context.kicad_target: int` and `Context.allow_lossy: bool`.
- Any other `--kicad-version` value MUST be a usage error: exit 2 with `FEN-2001`.
- A command that writes KiCad files MUST use `Context.kicad_target` as its target and `Context.allow_lossy` as its lossy switch.
- `docs/cli-contract.md` MUST describe both flags.
- The `FEN-7001` hint, "re-run with --allow-lossy to accept the loss", refers to this flag.

#### Scenario: Flags reach the context
- **GIVEN** a test command that returns `ctx.kicad_target` and `ctx.allow_lossy` in its result
- **WHEN** `fenolite --kicad-version 9 --allow-lossy <test command> --json` runs
- **THEN** the result holds `9` and `true`

#### Scenario: Defaults
- **GIVEN** the same test command
- **WHEN** it runs without either flag
- **THEN** the result holds `10` and `false`

#### Scenario: Unsupported target is a usage error
- **WHEN** `fenolite --kicad-version 8 capabilities --json` runs
- **THEN** the exit code is 2 and stderr carries `FEN-2001`

#### Scenario: Consistency test covers the flags
- **WHEN** `uv run pytest tests/consistency` runs
- **THEN** it passes, and every command's `--help` lists `--kicad-version` and `--allow-lossy`

### Requirement: Legacy board edits are refused
The registry in `src/fenolite/cli/errors.py` SHALL contain `FEN-7003` with exit code 7, message "input from KiCad 8.0 is read-only; writing needs a KiCad 9.0 or newer source" and a hint naming `kicad-cli pcb upgrade`. `fenolite.backends.kicad.versions.LegacyEditRefusedError` MUST carry `cli_code = "FEN-7003"`, and `LossyWriteError` MUST carry `cli_code = "FEN-7001"`, so the dispatcher maps both through "Library errors map to registered codes". `docs/cli-contract.md` MUST list `FEN-7001` (`LossyWriteError`) and `FEN-7003` (`LegacyEditRefusedError`) in its codes table.

#### Scenario: Legacy edit maps to exit 7
- **GIVEN** the test command of the `run_raising` fixture in `tests/unit/cli/test_library_errors.py`, raising `LegacyEditRefusedError` for a board at `20240108`
- **WHEN** it runs with `--json`
- **THEN** the exit code is 7, stderr carries `FEN-7003`, and its `hint` contains `kicad-cli pcb upgrade`

#### Scenario: Lossy write maps to exit 7
- **GIVEN** the same fixture's command raising `LossyWriteError` with `droppable == True`
- **WHEN** it runs with `--json`
- **THEN** the exit code is 7, stderr carries `FEN-7001`, and its `hint` contains `--allow-lossy`

#### Scenario: Non-droppable loss keeps its own hint
- **GIVEN** the same fixture's command raising `LossyWriteError` with `droppable == False` and an issue `kicad.board.opaque-net-ref`
- **WHEN** it runs with `--json`
- **THEN** the exit code is 7, stderr carries `FEN-7001`, and its `hint` does not contain `--allow-lossy`

#### Scenario: Codes documented
- **WHEN** `docs/cli-contract.md` is read
- **THEN** its codes table has rows for `FEN-7001` and `FEN-7003`
