## MODIFIED Requirements

### Requirement: Export kinds and their arguments
`fenolite.exports.plan.KINDS` SHALL map each export kind to the `kicad-cli` words and fixed options it runs with, and `run_kind(cli, kind, board, files, *, major, design=None, args=None, layers=None, models=None) -> KindResult` SHALL run one kind on the copy set and return its artefacts.
- The kinds MUST be the four fabrication kinds `gerbers`, `drill`, `pos` and `ipcd356` (`FAB_KINDS`), and the six document kinds `ipc2581`, `odb`, `step`, `pdf`, `dxf` and `sch-pdf` (`DOCUMENT_KINDS`), with these arguments, where `<stem>` is the board file's stem:
  - `gerbers`: `pcb export gerbers -o gerbers/ --no-protel-ext --layers <list>`;
  - `drill`: `pcb export drill -o drill/ --format excellon --excellon-units mm --excellon-separate-th --drill-origin absolute`;
  - `pos`: `pcb export pos --format csv --units mm --side both -o pos/<stem>-pos.csv`;
  - `ipcd356`: `pcb export ipcd356 -o netlist/<stem>.d356`;
  - `ipc2581`: `pcb export ipc2581 -o ipc2581/<stem>.xml --version C --units mm --precision 6`;
  - `odb`: `pcb export odb -o odb/<stem>.zip --compression zip --units mm`;
  - `step`: `pcb export step -o 3d/<stem>.step --subst-models`, with the files and variables of "STEP export with 3D models";
  - `pdf`: `pcb export pdf -o pdf/ --mode-separate --layers <list> --common-layers Edge.Cuts --include-border-title`;
  - `dxf`: `pcb export dxf -o dxf/ --mode-multi --output-units mm --layers <list>`;
  - `sch-pdf`: `sch export pdf -o schematic/<stem>.pdf <stem>.kicad_sch`, with the files of "Schematic PDF export sheets".
- `gerber_layers(design)` MUST give the board's copper layers in stack order, then `F.Mask`, `B.Mask`, `F.Paste`, `B.Paste`, `F.SilkS`, `B.SilkS` where the board's layer table has them (by KiCad's canonical name), then the user layer whose user name is `V-Score` where the board has one (the score lines of a panel board, change c0173), then `Edge.Cuts`.
- `pdf_layers(design)` MUST give the layers of `gerber_layers(design)` with `F.Fab` and `B.Fab`, where the board has them, before `Edge.Cuts`. `dxf_layers(design)` MUST give `Edge.Cuts`, then `F.Fab`, `B.Fab`, `F.CrtYd` and `B.CrtYd` where the board has them. `layers`, when given, MUST replace the list of `pdf` or `dxf`, and MUST raise `ValueError` for any other kind. `args`, the callback through which an export preset reaches a run ("Export presets"), MUST NOT be called for a document kind.
- `--check-zones`, `--board-plot-params`, `--variant`, `--drawing-sheet` and `--define-var` MUST NOT be passed for any kind. Without a preset, every kind MUST run with the same arguments on 9.0 and 10.0 (`Kind.majors` = `(9, 10)`).
- `Kind.repeat` MUST be the weakest class that the probes record for two runs of one board over both majors (`H-K-EXPORT-REPEAT`, `H-K-EXPORT-DOCS-REPEAT`): `bytes` for `pos`, `ipcd356` and `dxf`; `content` for `gerbers`, `drill`, `pdf` and `sch-pdf`, whose runs differ only in the lines that `VOLATILE_PREFIXES` names; `none` for `ipc2581`, `odb` and `step`.
- `KindResult.artifacts` MUST hold one `Artifact(path, kind, layer, data, repeatable)` per file the run wrote under the kind's output folder, sorted by path; `path` is relative to the output folder and uses `/`. `repeatable` MUST be true exactly when the kind's `repeat` is `bytes`.
- `Artifact.layer` MUST be the layer's canonical name for a Gerber and for each file of `pdf` and `dxf`, found from the file name's suffix through the canonical and the user names of the board's layer table and the names KiCad shows (`F_Silkscreen` for `F.SilkS`, `F_Courtyard` for `F.CrtYd`), and `None` for any other kind, for the job file `<stem>-job.gbrjob` and for a suffix that matches no layer.
- Files the run wrote outside the kind's output folder MUST be listed in `KindResult.tool_writes` and MUST NOT become artefacts.
- A run that exits non-zero, or writes no file, MUST give one `export.failed` (error; `where` = the kind) whose message is the first line of the tool's output with every temporary path removed.
- A kind that the probes record as unavailable on the running major MUST give `export.kind-unavailable` (error) and MUST run no subprocess.
- `fenolite.exports.codes.ISSUE_CODES` MUST hold `export.failed` (error), `export.kind-unavailable` (error), `render.failed` (warning), `export.sheet-missing` (error), `export.model-unread` (warning) and `export.page-too-small` (warning).

#### Scenario: Gerber layers of a two-copper board
- **GIVEN** the model of `tests/data/kicad/board/two_layer.kicad_pcb`
- **WHEN** `uv run pytest tests/unit/exports/test_plan.py -k layers` calls `gerber_layers`
- **THEN** the list starts with `F.Cu`, `B.Cu` and ends with `Edge.Cuts`, and holds no fabrication or courtyard layer

#### Scenario: Artefacts from a fake run
- **GIVEN** a fake `kicad-cli` whose `gerbers` run writes `gerbers/b-F_Cu.gbr`, `gerbers/b-Edge_Cuts.gbr` and `b.kicad_prl`
- **WHEN** `run_kind(cli, "gerbers", …)` runs
- **THEN** there are two artefacts with layers `Edge.Cuts` and `F.Cu`, and `tool_writes` is `("b.kicad_prl",)`

#### Scenario: Failed kind
- **GIVEN** a fake `kicad-cli` that exits 1 for `pcb export drill` with a message holding its temporary folder
- **WHEN** `run_kind(cli, "drill", …)` runs
- **THEN** the result holds no artefact and one `export.failed` whose message holds no temporary path

#### Scenario: Forbidden options are absent
- **WHEN** `uv run pytest tests/unit/exports/test_plan.py -k options` reads every argument list `KINDS` produces for majors 9 and 10
- **THEN** none holds `--check-zones`, `--board-plot-params`, `--variant`, `--drawing-sheet` or `--define-var`, and the lists of 9 and 10 are equal for every kind

#### Scenario: Layer lists of the document kinds
- **GIVEN** the model of `two_layer.kicad_pcb`
- **WHEN** `uv run pytest tests/unit/exports/test_plan_documents.py -k layers` calls `pdf_layers` and `dxf_layers`, and `run_kind(cli, "gerbers", …, layers=("F.Cu",))`
- **THEN** `pdf_layers` starts with `F.Cu`, `B.Cu`, holds `F.Fab` and `B.Fab` and ends with `Edge.Cuts`; `dxf_layers` starts with `Edge.Cuts` and holds no copper layer; and the Gerber call raises `ValueError`

#### Scenario: One artefact per layer
- **GIVEN** a fake `kicad-cli` whose `pdf` run writes `pdf/b-F_Cu.pdf` and `pdf/b-F_Fab.pdf`, and whose `dxf` run writes `dxf/b-Edge_Cuts.dxf` and `dxf/b-F_Courtyard.dxf`
- **WHEN** both kinds run
- **THEN** the artefacts have the layers `F.Cu`, `F.Fab`, `Edge.Cuts` and `F.CrtYd`; the `dxf` artefacts are `repeatable` and the `pdf` ones are not

#### Scenario: Gerber layers of a panel board
- **GIVEN** the model of a panel board written from `tests/data/panels/mixed.py` (V-score between rows), whose layer table holds `User.1` with the user name `V-Score`
- **WHEN** `uv run pytest tests/unit/exports/test_plan.py -k panel` calls `gerber_layers`
- **THEN** the list holds `User.1` directly before `Edge.Cuts`, and the list of `two_layer.kicad_pcb` is unchanged
