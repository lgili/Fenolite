## ADDED Requirements

### Requirement: Bom command
`fenolite bom PATH [--source kicad|model] [--template FILE] [--out FILE] [--against OTHER] [--kicad-cli PATH] [--timeout SECONDS]` SHALL be registered by `src/fenolite/cli/cmd_bom.py` with `mutates=True`, and SHALL give the bill of materials of a project as a neutral table, written as a CSV file only with `--out`.
- **Project.** `PATH` MUST resolve with `projectset.resolve_board`; the usage and input errors are `check`'s (`FEN-2001`, `FEN-3001`).
- **Source `kicad`** (the default). The parts MUST come from `KicadCli.export_bom` on a copy of the project's `<stem>.kicad_sch`, of its project file and of every other `.kicad_sch` under the project folder, read with `read_bom_csv` and `parts_from_kicad`. A project without that schematic MUST exit 3 with `FEN-3001` and a hint that names `--source model`. No tool MUST exit 6 with `FEN-6001`. A run that writes no bill, or a bill with another header, MUST exit 3 with `FEN-3004`. `counts.left_out` MUST be `null` for this source, because KiCad does not say what it leaves off a bill.
- **Source `model`.** The parts MUST come from `bom.parts_from_model` of the `.fenolite/` model on built input and of the board read on native input, with no subprocess.
- **Template.** `--template FILE` MUST be read with `assembly.read_template`; without it `assembly.DEFAULT` applies. A template error MUST exit 3 with `FEN-3004` and its issues in the envelope.
- **Result.** `result` MUST hold `source`, `template` (the file name without its folder, or `default`), `columns` (the column names), `lines` (one object per line, keyed by column name, as rendered text), `counts` (`parts`, `lines`, `dnp`, `left_out`) and, with `--against`, `changes` (each `{key, change, a_refs, b_refs}`). A column whose `property:<NAME>` no part has MUST give one `bom.property-missing` info.
- **`--against OTHER`.** `OTHER` MUST be read as `PATH` is, with the same source and template, and `changes` MUST be `bom.difference` of the two.
- **Writes.** With `--out FILE`, the command MUST return one `PlannedWrite` of kind `bom` whose bytes are `assembly.render_csv` of the table; without it, none. The mutation protocol applies; the project folder MUST NOT change otherwise.
- **Determinism.** Two runs on an unchanged project MUST give the same stdout apart from `elapsed_ms` and the same file bytes; no value MUST hold a date or an absolute path.
- **Evidence.** The envelope evidence MUST be `bom.EVIDENCE_KICAD` with the oracle `kicad-cli <version>`, or `bom.EVIDENCE_MODEL` under the rule of `assembly-outputs`, "Assembly issue codes and evidence".
- `example_args` MUST be `(EXAMPLE_BOARD, "--source", "model")`, `mutation_example_args` the same with `"--out", "bom.csv"`, and both MUST run no subprocess.

#### Scenario: Table as JSON
- **WHEN** `uv run fenolite bom tests/data/kicad/board/two_layer.kicad_pcb --source model --json` runs
- **THEN** the exit code is 0, `result.columns` is `["refs", "quantity", "value", "footprint"]`, `result.lines` holds one object per group, and no file is written

#### Scenario: File with a template
- **GIVEN** the blink built into `tmp_path`
- **WHEN** `fenolite bom <dir> --source model --template tests/data/assembly/columns.toml --out bom.csv --confirm` runs
- **THEN** `bom.csv` starts with the header `Parts,Count,Marking,Shape,Bin`, `receipt.written` lists it with its SHA-256, and a second run writes identical bytes

#### Scenario: Confirmation required
- **WHEN** the same command runs without `--confirm`
- **THEN** the exit code is 4, `result.plan` lists `bom.csv`, and no file is written

#### Scenario: From kicad-cli
- **GIVEN** a fake `kicad-cli` that writes the authored `bom_export.csv`
- **WHEN** `uv run pytest tests/unit/cli/test_bom_cmd.py -k kicad` runs `fenolite bom <project with a schematic> --json`
- **THEN** `result.source` is `kicad`, the fake saw `sch export bom` with `--fields` starting `Reference,Value,Footprint`, and `evidence.oracle` names the fake's version

#### Scenario: No schematic
- **WHEN** `fenolite bom tests/data/kicad/board/two_layer.kicad_pcb` runs
- **THEN** the exit code is 3, stderr carries `FEN-3001`, and the hint names `--source model`

#### Scenario: Difference of two projects
- **GIVEN** two builds of the blink, the second with the value of `R1` changed
- **WHEN** `fenolite bom <second> --source model --against <first> --json` runs
- **THEN** `result.changes` holds one `added` and one `removed` entry

### Requirement: Pnp command
`fenolite pnp PATH [--template FILE] [--side top|bottom|both] [--out FILE]` SHALL be registered by `src/fenolite/cli/cmd_pnp.py` with `mutates=True`, and SHALL give the placement table of a board from its model, written as a CSV file only with `--out`. It MUST run no subprocess.
- **Board.** `PATH` MUST resolve with `projectset.resolve_board`. The design MUST be read from the board file for built and native input alike, never from the `.fenolite/` model: `place`, `route` and `fill` write the board only, so the board is the one description of where the parts are.
- **Rows.** The rows MUST be `placement.apply(placement.rows_from_model(design), template, outline=<the board outline>)`, filtered by `--side` (default `both`).
- **Result.** `result` MUST hold `template`, `columns`, `rows` (one object per row, keyed by column name, as rendered text), `counts` (`rows`, `top`, `bottom`, `dnp`, `left_out`), `units`, `origin` and `y_axis`.
- **Writes.** With `--out FILE`, one `PlannedWrite` of kind `pnp`; without it, none.
- **Errors.** A template error MUST exit 3 with `FEN-3004`; `pnp.no-outline` MUST exit 5 and plan no file.
- **Evidence.** The envelope evidence MUST be `Evidence.combine(placement.EVIDENCE, <the board read's evidence>)`.
- `example_args` MUST be `(EXAMPLE_BOARD,)` and `mutation_example_args` `(EXAMPLE_BOARD, "--out", "pnp.csv")`.

#### Scenario: Rows of the authored board
- **WHEN** `uv run fenolite pnp tests/data/kicad/board/two_layer.kicad_pcb --json` runs
- **THEN** the exit code is 0, `result.columns` is `["ref", "value", "footprint_name", "x", "y", "rotation", "side"]`, `result.units` is `mm`, and `result.rows` holds one row per footprint

#### Scenario: One side
- **GIVEN** the built blink, whose `D1` is on the bottom
- **WHEN** `fenolite pnp <dir> --side bottom --json` runs
- **THEN** `result.rows` holds only `D1`

#### Scenario: File with rotation rules
- **WHEN** `fenolite pnp <dir> --template tests/data/assembly/rotated.toml --out pnp.csv --confirm` runs
- **THEN** `pnp.csv` holds the columns of the template, the rotation of `U1` is its stored rotation plus the footprint offset of the template, and a second run writes identical bytes

#### Scenario: After a move
- **GIVEN** the built blink, and `fenolite place <dir> --move R1=12mm,8mm --confirm`
- **WHEN** `fenolite pnp <dir> --json` runs
- **THEN** the row of `R1` holds the position the board file has, and the other rows are unchanged

#### Scenario: Hermetic
- **GIVEN** `subprocess.run` and `subprocess.Popen` patched to raise
- **WHEN** `uv run pytest tests/unit/cli/test_hermetic_examples.py` runs `pnp` and `bom` with their `example_args`
- **THEN** both exit 0
