## ADDED Requirements

### Requirement: Document exports are probed on both majors
`tests/kicad/export/test_document_probes.py` (marker `needs_kicad`, major-aware) SHALL settle `H-K-EXPORT-DOCS`, `H-K-EXPORT-DOCS-REPEAT`, `H-K-EXPORT-MODELS`, `H-K-EXPORT-SHEETS` and `H-K-EXPORT-PDF-PAGE` on the running `kicad-cli` through c0009's `KicadCli`, on copies with an empty `KICAD_CONFIG_HOME`, before `exports.plan` relies on them. The subjects are the authored project of the running major, a four-copper board written by the test, the authored hierarchy `tests/data/kicad/schematic/hier/` (`hier_v9/` for target 9), and the authored model `tests/data/models/Fenolite.3dshapes/Box_2x1.step`; no test downloads anything.
- **Files** (`test_files`): `export-files-<kind>` for the six document kinds MUST record `equal` when the files under the kind's folder are exactly the expected set of `H-K-EXPORT-DOCS`, the per-layer names of `pdf` and `dxf` included.
- **Repeat** (`test_repeat`): three runs per kind; `export-repeat-<kind>` MUST record `equal` when every file has one `content_sha256` over the runs and `different` otherwise. The byte equality of each kind MUST be recorded in `docs/evidence/kicad-export.md`, and `Kind.repeat` MUST be the weakest class over the two probe files.
- **Models** (`test_models`): `export-models-var` MUST record `equal` when a STEP with the model named through `KICAD<N>_3DMODEL_DIR=3dmodels` holds one `NEXT_ASSEMBLY_USAGE_OCCURRENCE` per footprint that names it; `export-models-missing` `equal` when, with the variable naming an empty folder, the run exits 0 and prints `Could not add 3D model for <ref>.` and `File not found: <path>` for each such footprint; `export-models-subst` `equal` when a `.wrl` path whose file is present gives the bodies of its `.step` sibling with `--subst-models`; `export-models-install` (10.0.6 only, recorded, skipped without an install) when, with no variable, the bodies of an official model come from the install.
- **Sheets** (`test_sheets`): `export-sheets-missing` MUST record `present` when the hierarchy without its child sheet still gives one page per sheet instance, exit 0 and no line other than `Plotted to '…'` and `Done.`.
- **Page** (`test_page`): `export-pdf-page` MUST record `equal` when the `/MediaBox` of `pcb export pdf --mode-separate --layers Edge.Cuts` on a board whose outline leaves its A4 paper is the A4 page.
- **Loop** (`test_document_loop`): `fenolite export --ipc2581 --odb --step --pdf --dxf --sch-pdf --manifest --confirm` on the authored project given the hierarchy and the model MUST exit 0, write the files of the probes, leave the project folder unchanged, and give a manifest whose entries match the files. When c0061 is archived, the same MUST hold for the built blink with its schematic.
- The outcomes MUST be recorded in both probe files and the facts written to `docs/formats/kicad/cli.md` with their sources and labels.

#### Scenario: Probes on both majors
- **WHEN** `uv run pytest tests/kicad/export/test_document_probes.py -rA` runs on the local KiCad 10.0.6 and inside the pinned 9.0.9 image
- **THEN** the six `export-files-*` probes record `equal`; `export-repeat-dxf`, `-pdf` and `-sch-pdf` record `equal` and `export-repeat-step` and `-odb` `different`; `export-models-var`, `-missing` and `-subst` record `equal`; `export-sheets-missing` records `present`; and `export-pdf-page` records `equal` on 10.0.6

#### Scenario: The loop leaves the project as it was
- **WHEN** `uv run pytest tests/kicad/export/test_document_probes.py::test_document_loop` runs on both majors
- **THEN** the manifest lists every written file with its hash and kind, `result.models` names the authored model with source `env` or `project`, and the SHA-256 of every file of the project folder is unchanged

## MODIFIED Requirements

### Requirement: Subcommand matrix from help text
`fenolite.backends.kicad.helpmatrix` SHALL tell which `kicad-cli` subcommands and options exist by reading `kicad-cli <words> --help` pages, run through c0009's `KicadCli`, because even `--help` writes a configuration folder (observed on 10.0.6).
- `parse_help(text) -> HelpPage | None` MUST read the `Usage:` line: its `{a,b,…}` group gives a group's subcommands, and its `[--name …]` groups give a leaf's long options. It MUST return `None` when no `Usage:` line is found. The grammar MUST be recorded in `docs/formats/kicad/cli.md` from observed runs (`H-K-CLI-HELP`); no KiCad or argument-parser source is read, and unit tests use authored synthetic pages.
- `MATRIX` MUST be a closed tuple of `MatrixEntry(command, options)`: `pcb drc` (`--format`, `--severity-all`, `--schematic-parity`, `--refill-zones`, `--save-board`), `pcb upgrade`, `pcb import`, `pcb render`, `pcb export ipcd356`, `pos`, `svg`, `gerbers`, `drill`, `stats`, `ipc2581`, `odb`, `step`, `pdf` and `dxf`, `fp upgrade`, `sym upgrade`, `sch erc`, `sch export netlist`, `sch export pdf` and `jobset run`.
- `command_matrix(cli) -> CommandMatrix(version, rows, unparsed)` MUST give one boolean row per command and per option of `MATRIX`. A command exists when its last word is a subcommand of its parent's page; an option exists when it is an option of the command's page. A page that does not parse MUST be listed in `unparsed`, and its rows MUST be left out of `rows`.
- Each row MUST be recorded as the probe `check-help-<words>[-<option>]`, such as `check-help-pcb-drc-refill-zones`, with outcome `present` or `absent`.

#### Scenario: Group page
- **GIVEN** the authored page `Usage: kicad-cli pcb [--help] {drc,export,upgrade}`
- **WHEN** `uv run pytest tests/unit/backends/kicad/test_helpmatrix.py -k group` calls `parse_help`
- **THEN** `subcommands` is `{"drc", "export", "upgrade"}`

#### Scenario: Leaf page
- **GIVEN** the authored page `Usage: kicad-cli pcb drc [--help] [--format VAR] [--severity-all] INPUT_FILE`
- **WHEN** `parse_help` is called
- **THEN** `options` is `{"--help", "--format", "--severity-all"}`

#### Scenario: Page without a usage line
- **WHEN** `parse_help("Error: unknown command")` is called
- **THEN** it returns `None`

#### Scenario: Matrix matches the documented command sets
- **GIVEN** kicad-cli 9.0.9 in the pinned image and 10.0.6 locally
- **WHEN** `uv run pytest tests/kicad/check/test_help_matrix.py::test_matrix_matches_facts` runs on each
- **THEN** every `MATRIX` page parses; `pcb import`, `pcb upgrade` and `pcb drc --refill-zones` and `--save-board` are present exactly on 10.0.6 (agreeing with `H-K-00` and `H-K-01`); `pcb drc --format`, `--severity-all`, `pcb export ipcd356`, `pos`, `svg`, `ipc2581`, `odb`, `step`, `pdf`, `dxf` and `sch export pdf` are present on both; and every row is recorded as a `check-help-*` probe
