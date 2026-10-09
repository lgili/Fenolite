## ADDED Requirements

### Requirement: Models command
`fenolite models PATH [--vendor]` SHALL be registered by `src/fenolite/cli/cmd_models.py` with `mutates=True`, and SHALL list the 3D models that the footprints of a board name, with the source where Fenolite finds each; with `--vendor` it SHALL plan copies of them into the project's `3dmodels/` folder, which the `step` export kind reads first (`manufacturing-exports`, "STEP export with 3D models").
- **Board.** `PATH` MUST resolve with `projectset.resolve_board`; the usage and input errors are `check`'s (`FEN-2001`, `FEN-3001`). A path that names no KiCad board (an Altium document or project) is refused there, as `export` refuses it.
- **Models.** The paths MUST be those of `models.board_models` on the board text, each located once as the `step` kind locates it. The command MUST run no tool and make no request.
- **Result.** `result.models` MUST hold one object per distinct path, sorted by path: `path`, `source` (`project`, `env`, `kicad-config`, `install`, `cache`, `in-place` or `missing`), `sha256` and `bytes` (`null` when missing or in place), and `refs` (sorted). `result.counts` MUST hold `paths`, `located` and `missing`.
- **Missing models.** Each path that is not located MUST give one `kicad.lib.missing-3d-model` (warning) naming the path and its references; the exit code stays 0.
- **`--vendor`.** The command MUST return one `PlannedWrite` of kind `3d-model` per located `${KICAD<N>_3DMODEL_DIR}/<rel>` path whose source is not `project`, at `<board folder>/3dmodels/<rel>` relative to the working directory, holding the bytes of the located file, and nothing else. Without `--vendor` it MUST return none. The mutation protocol applies. The board, its footprints and their model paths MUST NOT change.
- **Determinism.** No value MUST hold an absolute path or a date; two runs on unchanged inputs MUST give the same stdout apart from `elapsed_ms`.
- **Evidence.** The envelope evidence MUST be `models.EVIDENCE`, `INFERRED` (`H-K-EXPORT-MODELS`) until that hypothesis is `KICAD-VERIFIED (9.0.x, 10.0.x)`.
- `example_args` MUST be `(EXAMPLE_BOARD,)` and `mutation_example_args` `(EXAMPLE_BOARD, "--vendor")`, and both MUST run no subprocess. The command MUST declare `paged = "models"` ("Paged results").
- `docs/cli-contract.md` MUST describe the command, its result keys and the order of the sources.

#### Scenario: Located and missing models
- **GIVEN** a copy of `two_layer.kicad_pcb` in `tmp_path` whose `R1` names `${KICAD10_3DMODEL_DIR}/Fenolite.3dshapes/Box_2x1.step` and whose `D1` names `${KICAD10_3DMODEL_DIR}/Fenolite.3dshapes/Absent.step`, with `KICAD10_3DMODEL_DIR` set to `tests/data/models` and no install
- **WHEN** `uv run pytest tests/unit/cli/test_models_cmd.py -k list` runs `fenolite models <board> --json`
- **THEN** the exit code is 0, `result.counts` is `{"paths": 2, "located": 1, "missing": 1}`, the `Box_2x1.step` entry has source `env` and the file's SHA-256, and the issues hold one `kicad.lib.missing-3d-model` naming `D1`

#### Scenario: Vendored, then read from the project
- **GIVEN** the same board
- **WHEN** `fenolite models <board> --vendor --confirm` runs, and then `fenolite models <board> --json`
- **THEN** the first writes `3dmodels/Fenolite.3dshapes/Box_2x1.step` beside the board, byte-equal to its source, and nothing else; the second reports that path with source `project`; the board file is unchanged

#### Scenario: The command is hermetic
- **GIVEN** `subprocess.run` and `subprocess.Popen` patched to raise
- **WHEN** `uv run pytest tests/unit/cli/test_hermetic_examples.py tests/consistency -k models` runs the examples
- **THEN** both exit 0 and the outputs hold no absolute path

## MODIFIED Requirements

### Requirement: Export command
`fenolite export PATH --out DIR [--gerbers] [--drill] [--pos] [--ipcd356] [--ipc2581] [--odb] [--step] [--pdf] [--dxf] [--sch-pdf] [--all] [--altium-rul] [--manifest] [--preset FILE] [--kicad-cli PATH] [--timeout SECONDS]` SHALL be registered by `src/fenolite/cli/cmd_export.py` with `mutates=True`, and SHALL write the fabrication files and documents that `kicad-cli` produces from a copy of the board that `PATH` names and, for `--sch-pdf`, of its schematic, and, with `--altium-rul`, the project's rules as an Altium rule file (`manufacturing-exports`, "Altium rule file export").
- **Board.** `PATH` MUST resolve with `projectset.resolve_board`; the usage and input errors are `check`'s (`FEN-2001`, `FEN-3001`).
- **Kinds.** `--all` MUST select the four fabrication kinds (`FAB_KINDS`: `gerbers`, `drill`, `pos`, `ipcd356`) and MUST NOT select `altium-rul` or a document kind; each document kind (`DOCUMENT_KINDS`: `ipc2581`, `odb`, `step`, `pdf`, `dxf` and `sch-pdf`) MUST be selected by its own flag. A call that selects no kind and no `--altium-rul` MUST exit 2 with `FEN-2001`.
- **Schematic.** With `--sch-pdf`, a board without `<stem>.kicad_sch` beside it MUST exit 3 with `FEN-3001` before any run, with a hint that names the other kinds.
- **Preset.** `--preset FILE` MUST be read with `exports.preset.read_preset` before any run, and each selected kind MUST run with `arguments(kind, preset, …)` (`manufacturing-exports`, "Export presets"); a preset error MUST exit 3 with `FEN-3004`. `result.preset` MUST hold `file` (the name as given) and `sha256`, or be `null` without a preset. A document kind has no preset table: it MUST run with the fixed arguments of "Export kinds and their arguments" whatever the preset holds.
- **Tool.** When a fabrication kind or a document kind is selected, the command MUST exit 6 with `FEN-6001` when no `kicad-cli` is found and with `FEN-6002` for an unsupported major or a board newer than the tool reads. `--timeout` MUST default to 300 and apply to each run. With `--altium-rul` alone no tool is looked for or run.
- **Source.** The board, its project files and its folder MUST NOT change; every run happens on the copy set of `projectset.project_set`, with the model files of `manufacturing-exports`, "STEP export with 3D models", for the `step` kind.
- **Writes.** The command MUST return one `PlannedWrite` per artefact at `DIR/<artefact path>`, and with `--manifest` one for `DIR/fenolite-artifacts.json`; `DIR` is relative to the working directory. When any selected kind fails, the command MUST return no `PlannedWrite`, MUST report the kind's issue and MUST exit 5. The mutation protocol (`--dry-run`, `--confirm`, backup, receipt) applies unchanged.
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

### Requirement: Manifest option of producing commands
`export`, `render`, `bom` and `pnp` SHALL accept `--manifest`, and with it SHALL plan, beside their files, the manifest of their output folder merged with their entries (`manufacturing-exports`, "Manifest merging").
- The output folder is `--out DIR` for `export` and `render`, and the folder of `--out FILE` for `bom` and `pnp`; `--manifest` without `--out` MUST exit 2 with `FEN-2001` for `bom` and `pnp`.
- The entries MUST have the kinds of `KINDS` for `export`, `render` for each view, `bom` and `pnp`; `layer` is `Artifact.layer`: set for a Gerber and for each layer file of `pdf` and `dxf`, `null` otherwise.
- `from` MUST hold the SHA-256 of the board for `export` (for its `sch-pdf` entry that of the root schematic instead), `render` and `pnp`, and for `bom` that of the schematic (source `kicad`) or of the board (source `model`).
- `tool` MUST be `kicad-cli <version>` for files that tool wrote and `fenolite <version>` for the tables Fenolite rendered. `evidence` MUST be the level of the entry's own claim (`manufacturing-exports`, "Artefact manifest"): `exports.EVIDENCE`'s for a file of a fabrication kind or a view that `kicad-cli` wrote with the fixed options, `exports.DOCUMENTS_EVIDENCE`'s for a file of a document kind, the lower level of an export with a preset (c0074), and the level of the rows for a table.
- A folder whose manifest cannot be read (`manifest.unreadable`) MUST make the command plan no file at all, its own files included.
- `bom --source kicad` is not available yet (c0064 waits for the schematic writer); until it is, the `from` of a bill always holds the board's hash.
- A view that failed (`render.failed`) MUST have no entry.
- Without `--manifest`, each command MUST behave as before this requirement, and `export`'s result keys are unchanged.

#### Scenario: Views join the manifest
- **GIVEN** a folder `out` in which `export --all --manifest --confirm` ran, and a fake `kicad-cli`
- **WHEN** `uv run pytest tests/unit/cli/test_render_cmd.py -k manifest` runs `fenolite render <board> --out out --svg --manifest --confirm`
- **THEN** `out/fenolite-artifacts.json` lists the fabrication files and `front.svg` and `back.svg` with kind `render`

#### Scenario: Tables join the manifest
- **WHEN** `fenolite bom <dir> --source model --out out/bom.csv --manifest --confirm` and `fenolite pnp <dir> --out out/pnp.csv --manifest --confirm` run
- **THEN** the manifest of `out` lists `bom.csv` with kind `bom` and `pnp.csv` with kind `pnp`, each with `tool` naming `fenolite` and the board's hash in `from`

#### Scenario: Manifest needs a folder
- **WHEN** `fenolite pnp <dir> --manifest` runs without `--out`
- **THEN** the exit code is 2 and stderr carries `FEN-2001`

#### Scenario: Layer and source of document entries
- **GIVEN** a fake `kicad-cli` and a board with a schematic beside it
- **WHEN** `uv run pytest tests/unit/cli/test_export_cmd.py -k document_manifest` runs `fenolite export <board> --out out --pdf --sch-pdf --manifest --confirm`
- **THEN** each `pdf` entry of `out/fenolite-artifacts.json` has its layer's canonical name in `layer` and the board's hash in `from`, and the `sch-pdf` entry has `layer` `null` and the root schematic's hash in `from`
