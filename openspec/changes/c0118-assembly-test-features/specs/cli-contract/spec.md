## ADDED Requirements

### Requirement: Testpoints command
`fenolite testpoints PATH [--side top|bottom|both] [--template FILE] [--min-coverage PERCENT] [--min-pitch LENGTH] [--min-fiducials N] [-o FILE] [--manifest]` SHALL be registered by `src/fenolite/cli/cmd_testpoints.py`, with `mutates=True` for `--out` only, and SHALL report the test points, fiducials, holes and net coverage of a board (`assembly-test-features`).
- `PATH` is a `.kicad_pcb`, a `.kicad_pro` or a project folder, read as `pnp` reads it: from the board file, with no tool run. An Altium document or project is refused as `pnp` refuses it: marks are read from KiCad's pad property, and no Altium record is known to hold one.
- The command MUST declare `paged = "test_points"` ("Paged results").
- `result` MUST hold `side`; `test_points`, `fiducials` and `holes`, rows of "Test-point report rows" with lengths in integer nanometres in the board frame; `coverage` with `eligible`, `covered` and `uncovered`; `counts` with `test_points`, `fiducials_top`, `fiducials_bottom`, `holes` and `tooling_holes`; and `template`, `units`, `origin` and `y_axis`. `issues` MUST hold the findings of "Assembly and test findings", and `evidence` MUST combine `exports.testpoints.EVIDENCE` with the read's.
- `--min-coverage` MUST be an integer from 0 to 100, `--min-pitch` a positive length with a unit, and `--min-fiducials` an integer of at least 1; another value MUST exit 2 (`FEN-2001`).
- `-o FILE` MUST plan one CSV file through the mutation protocol. Its header is `kind,ref,pad,net,x,y,side,access,width,height,drill`, with `kind` `test_point`, `fiducial`, `tooling_hole` or `hole`, one row per report row in that order; positions and sizes in the origin, Y axis, units and decimals of the template's `[placement]` table, sides by its side names, and its CSV options. No file MUST be planned when a finding is an error, or when the origin needs a board outline the board lacks (`pnp.no-outline`).
- `--manifest` follows "Manifest option of producing commands": with `-o FILE` it plans the manifest of the file's folder with one entry of kind `testpoints`; without `-o` it MUST exit 2 with `FEN-2001`.
- The exit code MUST be 0 without an error finding, 5 with one, and 3 for a file that cannot be read.
- The command MUST name `example_args` on the example board, and `mutation_example_args` that write `testpoints.csv`.
- `docs/cli-contract.md` MUST hold a section `testpoints` with its options, its result and its codes.

#### Scenario: A board without marks
- **WHEN** `fenolite testpoints tests/data/kicad/board/two_layer.kicad_pcb --json` runs
- **THEN** it exits 0, `result.test_points` is empty, `result.coverage.covered` is 0, and `issues` holds one `testpoint.none` info

#### Scenario: A coverage target missed
- **GIVEN** the build of "Features in a build" (`design-dsl`, "Assembly and test features in a build")
- **WHEN** `fenolite testpoints <board> --min-coverage 100 --out tp.csv --dry-run --json` runs
- **THEN** it exits 5, `issues` holds `testpoint.coverage-low`, `result.coverage.covered` is 1, and no write is planned

#### Scenario: The CSV of a build
- **GIVEN** the same build
- **WHEN** `fenolite testpoints <board> --out tp.csv --dry-run --json` runs
- **THEN** it exits 0 and plans `tp.csv`, whose first line is `kind,ref,pad,net,x,y,side,access,width,height,drill` and which holds a `test_point` row for `TP1` with the net `LED_A` and the access `top`, two `fiducial` rows and one `tooling_hole` row for `TH1`

#### Scenario: The CSV joins the manifest
- **GIVEN** the same build
- **WHEN** `uv run pytest tests/unit/cli/test_testpoints_cmd.py -k manifest` runs `fenolite testpoints <board> --out out/tp.csv --manifest --confirm`, and `fenolite testpoints <board> --manifest`
- **THEN** the first writes `out/tp.csv` and `out/fenolite-artifacts.json`, which lists `tp.csv` with kind `testpoints`, `tool` naming `fenolite` and the board's hash in `from`; the second exits 2 with `FEN-2001`

## MODIFIED Requirements

### Requirement: Manifest option of producing commands
`export`, `render`, `bom`, `pnp` and `testpoints` SHALL accept `--manifest`, and with it SHALL plan, beside their files, the manifest of their output folder merged with their entries (`manufacturing-exports`, "Manifest merging").
- The output folder is `--out DIR` for `export` and `render`, and the folder of `--out FILE` for `bom`, `pnp` and `testpoints`; `--manifest` without `--out` MUST exit 2 with `FEN-2001` for `bom`, `pnp` and `testpoints`.
- The entries MUST have the kinds of `KINDS` for `export`, `render` for each view, `bom`, `pnp` and `testpoints`; `layer` is `Artifact.layer`: set for a Gerber and for each layer file of `pdf` and `dxf`, `null` otherwise.
- `from` MUST hold the SHA-256 of the board for `export` (for its `sch-pdf` entry that of the root schematic instead), `render`, `pnp` and `testpoints`, and for `bom` that of the schematic (source `kicad`) or of the board (source `model`).
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

#### Scenario: The test-point table joins the manifest
- **WHEN** `uv run pytest tests/unit/cli/test_testpoints_cmd.py -k manifest` runs `fenolite testpoints <dir> --out out/tp.csv --manifest --confirm` in a folder where `pnp --manifest` ran
- **THEN** the manifest of `out` lists `pnp.csv` and `tp.csv`, the second with kind `testpoints`, `tool` naming `fenolite` and the board's hash in `from`
