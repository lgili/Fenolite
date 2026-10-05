## ADDED Requirements

### Requirement: BOM export through the package runner
`KicadCli.export_bom(schematic, *, fields, files=None) -> CliRun` SHALL run `sch export bom` through `KicadCli.run` on a copy, with `--fields <fields joined by commas>`, `--labels` equal to the fields, an empty `--ref-range-delimiter`, `--field-delimiter ,`, `--string-delimiter "` and `-o <out>`, and without `--group-by`, `--preset`, `--format-preset`, `--exclude-dnp` and `--include-excluded-from-bom`.
- It MUST NOT raise for a non-zero exit; the written CSV is among `CliRun.outputs`.
- `tests/kicad/assembly/test_bom_probes.py` (marker `needs_kicad`, major-aware) MUST settle `H-K-BOM-CSV` on 9.0.9 and 10.0.6 with projects that `tests/kicad/assembly/_asmcases.py` builds into `tmp_path`, each outcome a probe of `PROBES`:
  - the header equals the labels (`bom-csv-header`);
  - one row per reference, two parts of one value on two rows (`bom-csv-rows`);
  - a three-unit symbol on one row (`bom-csv-units`);
  - a DNP part listed with `DNP` in its `${DNP}` cell and the others with an empty cell (`bom-csv-dnp`);
  - no power flag and no part whose footprint has `exclude_from_bom` (`bom-csv-left-out`);
  - a field that no symbol has gives an empty column and exit 0 (`bom-csv-unknown-field`).
  Each probe's outcome MUST be `equal`; a probe that is `different` on a major MUST change `read_bom_csv` or the argument list before the command relies on it, and the task note MUST say how.
- Both probe files MUST be regenerated with `FENOLITE_PROBES_WRITE=1`.

#### Scenario: Arguments
- **GIVEN** a fake `kicad-cli` that records its arguments
- **WHEN** `uv run pytest tests/unit/backends/kicad/test_cli_runner.py -k export_bom` calls `KicadCli.export_bom(schematic, fields=("Reference", "Value", "MPN"))`
- **THEN** the fake saw `sch export bom` with `--fields Reference,Value,MPN`, `--labels Reference,Value,MPN` and an empty `--ref-range-delimiter`, and no `--group-by`

#### Scenario: Probes on both majors
- **GIVEN** `kicad-cli` 9.0.9 in the pinned image and 10.0.6 locally
- **WHEN** `uv run pytest tests/kicad/assembly/test_bom_probes.py tests/kicad/test_probe_results.py -rA` runs on each
- **THEN** the six `bom-csv-*` probes have an outcome in the probe file of that version

### Requirement: Assembly tables agree with kicad-cli
`tests/kicad/assembly/test_assembly_oracle.py` (marker `needs_kicad`, major-aware) SHALL prove on 9.0.9 and 10.0.6 that the neutral tables hold what KiCad exports.
- **BOM sources** (`H-K-BOM-MODEL`). For the blink built with user properties on two parts and one DNP part, and for c0061's units design, `bom.parts_from_model` of the built model MUST equal `read_bom_csv` of `KicadCli.export_bom` on the built schematic, part by part: reference, value, footprint, DNP flag and the user properties the fields name (probes `bom-model-blink`, `bom-model-units`, outcome `equal`).
- **Placement rows** (`H-K-POS-ROWS`). For the built blink, whose `D1` is on the bottom, for that blink with its parts turned to 180° and 270°, for that blink with one part marked DNP and one left out of position files, and for `tests/data/kicad/board/two_layer.kicad_pcb`, the table of `placement.apply` under `assembly.DEFAULT` with `exclude_dnp` false MUST have the rows of `pcb export pos --format csv --units mm --side both`: equal references, values and package names, X and Y equal to the micrometre, rotations equal modulo 360°, and equal sides (probe `pos-rows`, outcome `equal`).
- **Commands.** `fenolite bom <dir> --json` and `fenolite bom <dir> --source model --json` MUST give equal `result.lines` on the built blink, and the project folder's snapshot MUST be equal before and after.
- Tools MUST run through `KicadCli` on copies; both probe files MUST be regenerated with `FENOLITE_PROBES_WRITE=1`.

#### Scenario: Two sources, one BOM
- **WHEN** `uv run pytest tests/kicad/assembly/test_assembly_oracle.py -k bom_sources -rA` runs on 9.0.9 and on 10.0.6
- **THEN** `bom-model-blink` and `bom-model-units` record `equal`

#### Scenario: Placement equals the position file
- **WHEN** `uv run pytest tests/kicad/assembly/test_assembly_oracle.py -k pos_rows -rA` runs on both majors
- **THEN** `pos-rows` records `equal`, the bottom-side part included

#### Scenario: Project untouched
- **WHEN** the command comparison runs
- **THEN** the built folder holds the same files with the same bytes afterwards
