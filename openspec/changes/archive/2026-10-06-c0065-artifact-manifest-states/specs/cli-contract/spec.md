## ADDED Requirements

### Requirement: Manifest command
`fenolite manifest PATH [--artifacts DIR]... [--stages a,b] [--no-check] [--verify] [--out FILE] [--kicad-cli PATH] [--timeout SECONDS]` SHALL be registered by `src/fenolite/cli/cmd_manifest.py` with `mutates=True`, and SHALL write the project manifest of `manufacturing-exports`, "Project manifest", with a state on every entry.
- **Project.** `PATH` MUST resolve with `projectset.resolve_board`; the usage and input errors are `check`'s. `--out` MUST default to `fenolite-artifacts.json` in the board's folder (the project folder). An `--artifacts DIR` that is not inside the project folder MUST exit 2 with `FEN-2001`, and one that is not a folder MUST exit 3 with `FEN-3001`. Every path in the manifest is relative to the project folder, wherever `--out` puts the file.
- **Check.** Unless `--no-check` or `--verify` is given, the command MUST run the stages `--stages` names (default `DEFAULT_STAGES`) exactly as `check` does, with the same pre-flight and exit 6 without the tool, and MUST pass their statuses and evidence levels, with `sch.roundtrip_schematic` of every sheet (false for a sheet Fenolite cannot read), to `states.assign`. The issues of the check MUST be the command's issues, followed by the `manifest.*` issues. `--no-check` MUST run no stage and no tool, and every entry is then `generated`; `--no-check` with `--stages` MUST exit 2 with `FEN-2001`. The stage run MUST be the one `check` uses (`cmd_check.run_stages`), not a copy of it.
- **Writes.** The command MUST return one `PlannedWrite` for the manifest, whether or not the check found errors, and no other write. With an error issue the exit code is 5 after the write is planned or done; the mutation protocol applies.
- **`--verify`.** The command MUST read the existing manifest, hash every listed file, and report `manifest.missing` and `manifest.changed` (errors), `manifest.stale` (warning, a derived entry whose source has another hash now) and `manifest.unlisted` (info). It MUST plan no write and run no check and no tool; a missing manifest MUST exit 3 with `FEN-3001`, and one that `manifest.load` refuses MUST exit 3 with `FEN-3004`. A manifest that lists no design file is the manifest of an artefact folder: its paths MUST be resolved from its own folder, its sources compared with the board and schematic of `PATH`, and `manifest.unlisted` looked for in that folder. In a project manifest `manifest.unlisted` is looked for in the folders the derived entries came from: for each, the nearest folder above the file and below the project folder that holds a `fenolite-artifacts.json`, and the project folder for a file directly in it. `--verify` with `--no-check`, `--stages` or `--artifacts` MUST exit 2 with `FEN-2001`.
- **Result.** `result` MUST hold `manifest` (the path relative to the working directory), `project`, `states`, `artifacts` (`path`, `kind`, `state`, `stale`, `held`; sorted by path) and `check` (`stages` and `tool_version` as in the manifest, or `null`); with `--verify`, `verified` (true when no difference is an error) and `differences` (`path` and `code`, sorted by path) instead of `check`. No value MUST hold an absolute path, unless `PATH` or `--out` was given as one, or a date.
- **Paging.** The command MUST declare `paged="differences|artifacts"`: `differences` under `--verify`, else `artifacts`. The planned manifest is whole whatever the page.
- **Determinism.** With `--timestamp`, two runs on unchanged files MUST plan byte-identical manifests.
- **Evidence.** The envelope evidence MUST be that of the stages that ran, combined as `check` combines them, combined with `sch.EVIDENCE` when a sheet was judged, and `UNVERIFIED` with `--no-check` or `--verify`.
- `example_args` MUST be `(EXAMPLE_BOARD, "--no-check", "--out", "fenolite-artifacts.json", "--dry-run")`, `mutation_example_args` the same without `--dry-run`, and both MUST run no subprocess.

#### Scenario: Hashes only
- **WHEN** `uv run fenolite manifest tests/data/kicad/board/two_layer.kicad_pcb --no-check --out m.json --dry-run --json` runs
- **THEN** the exit code is 0, `result.plan` lists `m.json`, every entry of `result.artifacts` has the state `generated`, and `result.check` is `null`

#### Scenario: States from a check
- **GIVEN** a fake `kicad-cli` whose DRC and ERC reports hold no violation, and a built project with an authored two-sheet schematic next to its board
- **WHEN** `uv run pytest tests/unit/cli/test_manifest_cmd.py -k states` runs `fenolite manifest <dir> --confirm --json`
- **THEN** the board and each sheet have the state `native-verified`, and `result.check` names `drc.kicad` and `erc.kicad` with status `ok`

#### Scenario: Errors still give a manifest
- **GIVEN** a fake whose DRC report holds one `clearance` violation of severity `error`
- **WHEN** the same command runs
- **THEN** the exit code is 5, the manifest is written, and the board's state is `roundtrip-ok`

#### Scenario: Verify an unchanged folder
- **GIVEN** a project whose manifest was just written
- **WHEN** `fenolite manifest <dir> --verify --json` runs
- **THEN** the exit code is 0, `result.verified` is `true`, and no file is written

#### Scenario: Verify after an edit
- **GIVEN** the same project with one byte of a Gerber changed and the board replaced
- **WHEN** `fenolite manifest <dir> --verify --json` runs
- **THEN** the exit code is 5, `result.verified` is `false`, and `result.differences` holds `manifest.changed` for the Gerber and for the board and `manifest.stale` for the other derived files

#### Scenario: Artefact folder outside the project
- **WHEN** `fenolite manifest <dir> --artifacts <a folder elsewhere> --no-check --dry-run` runs
- **THEN** the exit code is 2 and stderr carries `FEN-2001`

#### Scenario: No tool
- **GIVEN** no `kicad-cli` on `PATH` and no `FENOLITE_KICAD_CLI`
- **WHEN** `fenolite manifest <dir> --dry-run` runs
- **THEN** the exit code is 6, stderr carries `FEN-6001`, and the hint names `--no-check` and `--stages`

### Requirement: Manifest option of producing commands
`export`, `render`, `bom` and `pnp` SHALL accept `--manifest`, and with it SHALL plan, beside their files, the manifest of their output folder merged with their entries (`manufacturing-exports`, "Manifest merging").
- The output folder is `--out DIR` for `export` and `render`, and the folder of `--out FILE` for `bom` and `pnp`; `--manifest` without `--out` MUST exit 2 with `FEN-2001` for `bom` and `pnp`.
- The entries MUST have the kinds of `KINDS` for `export`, `render` for each view, `bom` and `pnp`; `layer` is set only for Gerbers.
- `from` MUST hold the SHA-256 of the board for `export`, `render` and `pnp`, and for `bom` that of the schematic (source `kicad`) or of the board (source `model`).
- `tool` MUST be `kicad-cli <version>` for files that tool wrote and `fenolite <version>` for the tables Fenolite rendered. `evidence` MUST be the level of the command's envelope: `exports.EVIDENCE`'s for a file `kicad-cli` wrote with the fixed options, the lower level of an export with a preset (c0074), and the level of the rows for a table.
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
