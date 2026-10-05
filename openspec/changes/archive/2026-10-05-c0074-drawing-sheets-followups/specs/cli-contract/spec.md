## MODIFIED Requirements

### Requirement: Export command
`fenolite export PATH --out DIR [--gerbers] [--drill] [--pos] [--ipcd356] [--all] [--manifest] [--preset FILE] [--kicad-cli PATH] [--timeout SECONDS]` SHALL be registered by `src/fenolite/cli/cmd_export.py` with `mutates=True`, and SHALL write the fabrication files that `kicad-cli` produces from a copy of the board that `PATH` names.
- **Board.** `PATH` MUST resolve with `projectset.resolve_board`; the usage and input errors are `check`'s (`FEN-2001`, `FEN-3001`).
- **Kinds.** `--all` MUST select the four kinds. A call that selects none MUST exit 2 with `FEN-2001`.
- **Preset.** `--preset FILE` MUST be read with `exports.preset.read_preset` before any run, and each selected kind MUST run with `arguments(kind, preset, …)` (`manufacturing-exports`, "Export presets"); a preset error MUST exit 3 with `FEN-3004`. `result.preset` MUST hold `file` (the name as given) and `sha256`, or be `null` without a preset.
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

#### Scenario: Preset changes the drill units
- **GIVEN** a recording fake `kicad-cli` and a preset with `[drill]` `units = "in"`
- **WHEN** `fenolite export <board> --out fab --drill --preset fab.toml --dry-run` runs
- **THEN** the drill run saw `--excellon-units in`, and `result.preset.file` is `fab.toml`

#### Scenario: Invalid preset
- **WHEN** the same command runs with a preset whose schema is `other.v1`
- **THEN** the exit code is 3, stderr carries `FEN-3004`, and the fake saw no run
