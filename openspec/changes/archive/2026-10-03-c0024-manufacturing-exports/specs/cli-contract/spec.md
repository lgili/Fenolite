## ADDED Requirements

### Requirement: Export command
`fenolite export PATH --out DIR [--gerbers] [--drill] [--pos] [--ipcd356] [--all] [--manifest] [--kicad-cli PATH] [--timeout SECONDS]` SHALL be registered by `src/fenolite/cli/cmd_export.py` with `mutates=True`, and SHALL write the fabrication files that `kicad-cli` produces from a copy of the board that `PATH` names.
- **Board.** `PATH` MUST resolve with `projectset.resolve_board`; the usage and input errors are `check`'s (`FEN-2001`, `FEN-3001`).
- **Kinds.** `--all` MUST select the four kinds. A call that selects none MUST exit 2 with `FEN-2001`.
- **Tool.** The command MUST exit 6 with `FEN-6001` when no `kicad-cli` is found and with `FEN-6002` for an unsupported major or a board newer than the tool reads. `--timeout` MUST default to 300 and apply to each run.
- **Source.** The board, its project files and its folder MUST NOT change; every run happens on the copy set of `projectset.project_set`.
- **Writes.** The command MUST return one `PlannedWrite` per artefact at `DIR/<artefact path>`, and with `--manifest` one for `DIR/fenolite-artifacts.json`; `DIR` is relative to the working directory. When any selected kind fails, the command MUST return no `PlannedWrite`, MUST report the kind's issue and MUST exit 5. The mutation protocol (`--dry-run`, `--confirm`, backup, receipt) applies unchanged.
- **Result.** `result` MUST hold `board`, `out`, `kinds`, `artifacts` (`path`, `kind`, `layer`, `bytes`, `sha256`, `content_sha256`; sorted by path), `tool_version` and `tool_writes`. No value MUST hold a temporary path, the home directory or a date.
- **Exit codes.** 0 when the files are planned or written; 5 with `export.failed` or `export.kind-unavailable`; 3 for a board Fenolite cannot read.
- `example_args` MUST be `(EXAMPLE_BOARD, "--out", "fab", "--all", "--manifest", "--dry-run")`, `mutation_example_args` the same without `--dry-run`, and `example_tools` MUST be `("kicad-cli",)`.

#### Scenario: Plan, then write
- **GIVEN** a fake `kicad-cli` 10.0.6 that writes two Gerbers, two drill files, a position file and a netlist
- **WHEN** `uv run pytest tests/unit/cli/test_export_cmd.py -k plan` runs `fenolite export <board> --out fab --all --manifest --dry-run` and then `--confirm`
- **THEN** the first exits 0 with a seven-file plan and writes nothing, and the second writes the seven files and its receipt lists each with its SHA-256

#### Scenario: Manifest matches the files
- **GIVEN** the folder the previous scenario wrote
- **WHEN** `fab/fenolite-artifacts.json` is read
- **THEN** each entry's `sha256` and `bytes` equal the file's, and `board.sha256` equals the source board's

#### Scenario: One failing kind writes nothing
- **GIVEN** a fake `kicad-cli` that exits 1 for `pcb export drill`
- **WHEN** `fenolite export <board> --out fab --all --confirm` runs
- **THEN** the exit code is 5, the issues hold one `export.failed` with `where` `drill`, and `fab` does not exist

#### Scenario: No kind selected
- **WHEN** `fenolite export <board> --out fab --confirm` runs
- **THEN** the exit code is 2 and stderr carries `FEN-2001`

#### Scenario: Source is untouched
- **WHEN** `uv run pytest tests/unit/cli/test_check_readonly.py -k export` hashes the project folder before and after `fenolite export … --out <elsewhere> --confirm`
- **THEN** the folder holds the same files with the same bytes

#### Scenario: No tool
- **GIVEN** no `kicad-cli` on `PATH` and no `FENOLITE_KICAD_CLI`
- **WHEN** `fenolite export <board> --out fab --all --dry-run` runs
- **THEN** the exit code is 6 and stderr carries `FEN-6001`

### Requirement: Render command
`fenolite render PATH --out DIR [--svg] [--png] [--width PX] [--height PX] [--kicad-cli PATH] [--timeout SECONDS]` SHALL be registered by `src/fenolite/cli/cmd_render.py` with `mutates=True`, and SHALL write the review views of the board that `PATH` names.
- A call with neither `--svg` nor `--png` MUST exit 2 with `FEN-2001`. `--width` MUST default to 1600 and `--height` to 1200; both MUST be between 64 and 8192.
- The tool errors, the copy set and the mutation protocol MUST be `export`'s.
- The command MUST return one `PlannedWrite` per view produced, at `DIR/<view name>`.
- `result` MUST hold `board`, `out`, `views` (`path`, `kind`, `bytes`, `sha256`; sorted by path) and `tool_version`.
- A view that fails MUST give `render.failed` (warning) and the exit code MUST stay 0.
- `example_args` MUST be `(EXAMPLE_BOARD, "--out", "views", "--svg", "--png", "--dry-run")`, `mutation_example_args` the same without `--dry-run`, and `example_tools` MUST be `("kicad-cli",)`.

#### Scenario: Plan, then write
- **GIVEN** a fake `kicad-cli` 10.0.6
- **WHEN** `uv run pytest tests/unit/cli/test_render_cmd.py -k plan` runs `fenolite render <board> --out views --svg --dry-run` and then `--confirm`
- **THEN** the first plans `views/front.svg` and `views/back.svg` and writes nothing, and the second writes both

#### Scenario: Size out of range
- **WHEN** `fenolite render <board> --out views --png --width 10 --dry-run` runs
- **THEN** the exit code is 2 and stderr carries `FEN-2001`

### Requirement: Tool-backed command examples
`fenolite.cli.api.Command` SHALL have the field `example_tools: tuple[str, ...]`, default `()`, naming the external tools the command's examples need, and the suites SHALL provide a fake for each.
- The only name accepted in v0.1 MUST be `kicad-cli`; `tests/consistency/test_cli_consistency.py` MUST fail for any other.
- For a command with `kicad-cli` in `example_tools`, `tests/consistency/test_cli_consistency.py` and `tests/unit/cli/test_hermetic_examples.py` MUST run its examples with `FENOLITE_KICAD_CLI` set to a fake built by `tests/_fakecli.py`, and the examples MUST then meet every rule of the consistency suite: exit 0, a valid envelope, and for `mutation_example_args` the planned files written in an empty folder.
- A command with `example_tools == ()` MUST still run its examples with `subprocess.run` and `subprocess.Popen` patched to raise.
- `capabilities` MUST list `example_tools` for each command that has any.

#### Scenario: Export example runs against the fake
- **WHEN** `uv run pytest tests/consistency -k export` runs
- **THEN** `export`'s `example_args` exit 0, and its `mutation_example_args` write `fab/fenolite-artifacts.json` and at least one Gerber in an empty folder

#### Scenario: Tool-free commands stay hermetic
- **WHEN** `uv run pytest tests/unit/cli/test_hermetic_examples.py` runs
- **THEN** every command with `example_tools == ()` passes with subprocess creation patched to raise

#### Scenario: Unknown tool name
- **GIVEN** a test command with `example_tools=("ngspice",)`
- **WHEN** the consistency suite's name check runs on it
- **THEN** it fails and names the command
