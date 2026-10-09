## ADDED Requirements

### Requirement: Stack-up in inspect
`fenolite inspect` SHALL report the stack-up of a board it reads, as an addition to the `result` of "Inspect command".
- For a board, `result.stackup` MUST be `null` when `Board.stackup` is `None`, and otherwise hold `thickness` (`Stackup.thickness()`, in nm), `finish`, `impedance_controlled` and `layers`: one object per entry, top to bottom, with `name`, `kind` and `thickness`, and with `dielectric_kind`, `material`, `epsilon_r`, `loss_tangent` and `color` when they are set. Footprint files and symbol libraries MUST NOT carry the key.
- The `kicad.board.stackup-*` issues of the reader MUST be reported as reader issues, as "Inspect command" requires of every reader issue.
- `docs/cli-contract.md` MUST describe the key under `inspect`.

#### Scenario: Board with a stack-up
- **WHEN** `uv run fenolite inspect tests/data/kicad/board/stackup_four.kicad_pcb --json` runs
- **THEN** the exit code is 0, `result.stackup.thickness` is 2025000, `result.stackup.finish` is `ENIG`, and `result.stackup.layers` holds 14 objects, the first named `F.SilkS` with kind `silkscreen` and thickness 0

#### Scenario: Board without a stack-up
- **WHEN** `uv run fenolite inspect tests/data/kicad/board/two_layer.kicad_pcb --json` runs
- **THEN** `result.stackup` is `null`, and the other keys are those of "Authored board summary"

## MODIFIED Requirements

### Requirement: Export command
`fenolite export PATH --out DIR [--gerbers] [--drill] [--pos] [--ipcd356] [--ipc2581] [--odb] [--step] [--pdf] [--dxf] [--sch-pdf] [--all] [--altium-rul] [--manifest] [--preset FILE] [--kicad-cli PATH] [--timeout SECONDS]` SHALL be registered by `src/fenolite/cli/cmd_export.py` with `mutates=True`, and SHALL write the fabrication files and documents that `kicad-cli` produces from a copy of the board that `PATH` names and, for `--sch-pdf`, of its schematic, and, with `--altium-rul`, the project's rules as an Altium rule file (`manufacturing-exports`, "Altium rule file export").
- **Board.** `PATH` MUST resolve with `projectset.resolve_board`; the usage and input errors are `check`'s (`FEN-2001`, `FEN-3001`).
- **Kinds.** `--all` MUST select the four fabrication kinds (`FAB_KINDS`: `gerbers`, `drill`, `pos`, `ipcd356`) and MUST NOT select `altium-rul` or a document kind; each document kind (`DOCUMENT_KINDS`: `ipc2581`, `odb`, `step`, `pdf`, `dxf` and `sch-pdf`) MUST be selected by its own flag. A call that selects no kind and no `--altium-rul` MUST exit 2 with `FEN-2001`.
- **Schematic.** With `--sch-pdf`, a board without `<stem>.kicad_sch` beside it MUST exit 3 with `FEN-3001` before any run, with a hint that names the other kinds.
- **Preset.** `--preset FILE` MUST be read with `exports.preset.read_preset` before any run, and each selected kind MUST run with `arguments(kind, preset, …)` (`manufacturing-exports`, "Export presets"); a preset error MUST exit 3 with `FEN-3004`. `result.preset` MUST hold `file` (the name as given) and `sha256`, or be `null` without a preset. A document kind has no preset table: it MUST run with the fixed arguments of "Export kinds and their arguments" whatever the preset holds.
- **Tool.** When a fabrication kind or a document kind is selected, the command MUST exit 6 with `FEN-6001` when no `kicad-cli` is found and with `FEN-6002` for an unsupported major or a board newer than the tool reads. `--timeout` MUST default to 300 and apply to each run. With `--altium-rul` alone no tool is looked for or run.
- **Source.** The board, its project files and its folder MUST NOT change; every run happens on the copy set of `projectset.project_set`, with the model files of `manufacturing-exports`, "STEP export with 3D models", for the `step` kind.
- **Writes.** The command MUST return one `PlannedWrite` per artefact at `DIR/<artefact path>`, and with `--manifest` one for `DIR/fenolite-artifacts.json`; `DIR` is relative to the working directory. When any selected kind fails, the command MUST return no `PlannedWrite`, MUST report the kind's issue and MUST exit 5. Only an issue of severity `error` stops the writes: an issue of severity `info` MUST NOT (`manufacturing-exports`, "Stack-up note in exports", gives the first one), and neither does a warning, as "Exit codes" states. The mutation protocol (`--dry-run`, `--confirm`, backup, receipt) applies unchanged.
- **Result.** `result` MUST hold `board`, `out`, `kinds`, `artifacts` (`path`, `kind`, `layer`, `bytes`, `sha256`, `content_sha256`; sorted by path), `tool_version` (`null` when no tool ran), `tool_writes`, `repeat` (each selected fabrication or document kind mapped to its `Kind.repeat`) and `models` (the `ModelUse` objects of the `step` kind, `[]` without it), and with `--altium-rul` `rules` (`written`, `not_lowered`). No value MUST hold a temporary path, the home directory or a date.
- **Exit codes.** 0 when the files are planned or written, whatever the warnings (`kicad.lib.missing-3d-model`, `export.model-unread`, `export.page-too-small`); 5 with `export.failed`, `export.kind-unavailable` or `export.sheet-missing`; 3 for a board Fenolite cannot read or a missing schematic.
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

#### Scenario: The rule file needs no tool
- **GIVEN** an authored project with one clearance rule on a net, and no `kicad-cli` on the machine
- **WHEN** `uv run pytest tests/unit/cli/test_export_cmd.py -k altium_rule_file_needs_no_tool` runs `fenolite export <dir> --out fab --altium-rul --dry-run` and then `--manifest --confirm`
- **THEN** the first plans `fab/board.RUL` and writes nothing, the second writes it and the manifest, `result.kinds` is `["altium-rul"]`, `result.tool_version` is `null`, and the evidence is `INFERRED` with no oracle

#### Scenario: Document kinds
- **GIVEN** a fake `kicad-cli` 10.0.6 that writes one file for `ipc2581`, `odb` and `step`, two layer files for `pdf` and one for `dxf`
- **WHEN** `uv run pytest tests/unit/cli/test_export_cmd.py -k documents` runs `fenolite export <board> --out fab --ipc2581 --odb --step --pdf --dxf --dry-run`
- **THEN** the exit code is 0, the plan holds the six files, `result.repeat` maps `ipc2581`, `odb` and `step` to `none`, `pdf` to `content` and `dxf` to `bytes`, and `result.models` is a list

#### Scenario: All keeps the four kinds
- **GIVEN** a recording fake `kicad-cli`
- **WHEN** `fenolite export <board> --out fab --all --dry-run` runs
- **THEN** the fake saw exactly the runs of `gerbers`, `drill`, `pos` and `ipcd356`, and `result.kinds` holds neither a document kind nor `altium-rul`

#### Scenario: A preset leaves a document kind alone
- **GIVEN** a recording fake `kicad-cli` and a preset with `[drill]` `units = "in"`
- **WHEN** `fenolite export <board> --out fab --drill --dxf --preset fab.toml --dry-run` runs
- **THEN** the drill run saw `--excellon-units in`, and the `dxf` run saw exactly the arguments of "Export kinds and their arguments"

#### Scenario: Schematic PDF without a schematic
- **GIVEN** `two_layer.kicad_pcb`, which has no `two_layer.kicad_sch` beside it
- **WHEN** `fenolite export <board> --out fab --sch-pdf --dry-run` runs
- **THEN** the exit code is 3, stderr carries `FEN-3001` naming `two_layer.kicad_sch`, and the fake saw no run

#### Scenario: A missing sheet writes nothing
- **GIVEN** a board with a schematic whose sub-sheet file is missing, and a fake `kicad-cli`
- **WHEN** `fenolite export <board> --out fab --pdf --sch-pdf --confirm` runs
- **THEN** the exit code is 5, the issues hold `export.sheet-missing`, and `fab` does not exist

#### Scenario: An info does not stop the writes
- **GIVEN** a fake `kicad-cli` 10.0.6 and a run of the drill kind that reports one issue of severity `info` that is not `export.stackup-default`
- **WHEN** `uv run pytest tests/unit/cli/test_export_cmd.py -k severity` runs `fenolite export <board> --out fab --drill --dry-run` and then `--confirm`
- **THEN** the first exits 0 with the plan of the drill files and the info among its issues, and the second writes those files

#### Scenario: An error stops the writes
- **GIVEN** the same run reporting one issue of severity `error`
- **WHEN** `fenolite export <board> --out fab --drill --confirm` runs
- **THEN** the exit code is 5, `result` holds no plan, the receipt is `null` and `fab` does not exist

