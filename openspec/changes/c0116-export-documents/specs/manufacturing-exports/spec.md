## ADDED Requirements

### Requirement: STEP export with 3D models
The `step` kind SHALL give `kicad-cli` the 3D model files that Fenolite locates for the board's footprints, and SHALL report every model it could not give, because `pcb export step` leaves out a body it cannot find and still exits 0 (`H-K-EXPORT-MODELS`).
- **Model paths.** `fenolite.backends.kicad.models.board_models(text) -> tuple[ModelRef, ...]` MUST give one `ModelRef(ref, path)` per `(model "<path>" …)` child of each footprint of the board text, `ref` being the footprint's reference, in board order.
- **Location.** Each distinct path MUST be located once with `LibraryResolver.locate_model` (`kicad-library-resolution`, "3D model location"), the resolver having the board's folder as `project_dir`, the major of the board's format as `target_major` and `read_common=True`.
- **Run files and variables.** `models.plan_models(refs, resolver) -> ModelPlan` MUST give the files and the environment of the run:
  - a located `${KICAD<N>_3DMODEL_DIR}/<rel>` as `3dmodels/<rel>`, and for a `.wrl` path also its `.step` and `.stp` siblings found in the same source;
  - a located `${KIPRJMOD}/<rel>` inside the board's folder as `<rel>`;
  - `KICAD<N>_3DMODEL_DIR=3dmodels` for every N that a model path of the board names, also when none of its paths was located, so that `kicad-cli` never reads a model that Fenolite did not report;
  - a path of another form left as written and reported with the source `in-place`.
- `run_kind(cli, "step", …, models=plan)` MUST copy `plan.files` into the run beside the copy set and apply `plan.env` to it; with `models=None` it MUST build the plan from the board itself as above.
- **Missing models.** Each path that is not located MUST give one `kicad.lib.missing-3d-model` (warning) naming the path and the references that use it. The STEP MUST still be written, and the kind MUST NOT fail for it.
- **Cross-check.** `models.unread_refs(stdout)` MUST give the references of the lines `Could not add 3D model for <ref>.` of the run's output; each such reference whose model paths were all located MUST give one `export.model-unread` (warning) naming it.
- **Report.** `KindResult.models` MUST hold one `ModelUse(path, source, sha256, bytes, refs)` per distinct path, sorted by path: `source` one of `project`, `env`, `kicad-config`, `install`, `cache`, `in-place` and `missing`; `sha256` and `bytes` of the file given, `None` when missing or in place; `refs` sorted. No value MUST hold an absolute path.
- Every other kind MUST give an empty `KindResult.models`.

#### Scenario: Located models go into the run
- **GIVEN** a board whose footprints `U1` and `U2` name `${KICAD10_3DMODEL_DIR}/Fenolite.3dshapes/Box_2x1.step`, a resolver whose `env` sets `KICAD10_3DMODEL_DIR` to `tests/data/models` and names no install, and a recording fake `kicad-cli`
- **WHEN** `uv run pytest tests/unit/exports/test_plan_documents.py -k step_models` runs `run_kind(cli, "step", …)`
- **THEN** the fake saw `3dmodels/Fenolite.3dshapes/Box_2x1.step` in its run folder, `KICAD10_3DMODEL_DIR=3dmodels` in its environment and `--subst-models` in its arguments, and `models` holds one use with source `env`, the file's SHA-256 and the references `U1` and `U2`

#### Scenario: A missing model is a warning
- **GIVEN** the same board, `KICAD10_3DMODEL_DIR` naming an empty folder, and no install and no cache
- **WHEN** the kind runs
- **THEN** the issues hold one `kicad.lib.missing-3d-model` warning naming the path, `U1` and `U2`; the artefact `3d/<stem>.step` is returned; the fake still saw `KICAD10_3DMODEL_DIR=3dmodels`; and the use has source `missing`

#### Scenario: KiCad could not use a located model
- **GIVEN** the setup of the first scenario and a fake that prints `Could not add 3D model for U1.`
- **WHEN** the kind runs
- **THEN** the issues hold one `export.model-unread` warning naming `U1` and none naming `U2`

#### Scenario: A VRML path brings its STEP sibling
- **GIVEN** a footprint that names `${KICAD10_3DMODEL_DIR}/Fenolite.3dshapes/Box_2x1.wrl`, and a source folder holding `Box_2x1.wrl` and `Box_2x1.step`
- **WHEN** the kind runs with a recording fake
- **THEN** the fake saw both files under `3dmodels/Fenolite.3dshapes/`

### Requirement: Schematic PDF export sheets
The `sch-pdf` kind SHALL plot the schematic `<stem>.kicad_sch` beside the board with every sheet of its hierarchy, and SHALL refuse a hierarchy that names a sheet the run cannot be given, because `sch export pdf` plots an empty page for a missing sheet file and exits 0 with no message, on both majors (`H-K-EXPORT-SHEETS`).
- **Files.** The run MUST get the copy set of `projectset.project_set(board)`, whose "Schematic" clause (`kicad-oracle`, "Check project copy set") already holds the root schematic, the sheet files that `sch.sheet_files(<stem>.kicad_sch)` lists inside the board's folder, the project file, the symbol table with its `${KIPRJMOD}` libraries and the schematic's drawing sheet. `documents.schematic_files(board) -> SchematicFiles(root, files, issues)` MUST give the root, the sheet files of that set and the issues of the walk; it MUST NOT plan a second copy set.
- **Refusal.** A sheet that the walk reports with `kicad.sch.sheet-missing`, `kicad.sch.sheet-outside` or `kicad.sch.sheet-cycle`, and a sheet file that the copy set skipped (`too-large`), MUST give one `export.sheet-missing` (error; `where` = the sheet file as the hierarchy names it), and the kind MUST then run no subprocess.
- **Output.** The kind MUST run `sch export pdf -o schematic/<stem>.pdf <stem>.kicad_sch` and give one artefact `schematic/<stem>.pdf` with `layer` `None`.

#### Scenario: The hierarchy goes whole
- **GIVEN** a copy of `tests/data/kicad/schematic/hier/` whose root is renamed `<stem>.kicad_sch` beside a board, and a recording fake `kicad-cli`
- **WHEN** `uv run pytest tests/unit/exports/test_plan_documents.py -k sch_pdf` runs `run_kind(cli, "sch-pdf", …)`
- **THEN** the fake saw the root and `child.kicad_sch` in its run folder and the arguments `sch export pdf -o schematic/<stem>.pdf <stem>.kicad_sch`, and the result holds the one artefact `schematic/<stem>.pdf`

#### Scenario: A missing sheet refuses the kind
- **GIVEN** the same project without `child.kicad_sch`
- **WHEN** the kind runs
- **THEN** the issues hold one `export.sheet-missing` error naming `child.kicad_sch`, the result holds no artefact, and the fake saw no run

### Requirement: Board PDF export page check
The `pdf` kind SHALL give `export.page-too-small` (warning; `where` = `pdf`) when the bounding box of the board outline is not inside the board's page, because `pcb export pdf` plots on the board's paper whatever the extent of the board (`H-K-EXPORT-PDF-PAGE`).
- `documents.page_check(design) -> Issue | None` MUST take the page as the rectangle from (0, 0) to the width and height of `Board.sheet`: `model.presentation.PAPER_SIZES` for a named paper, landscape unless `portrait`, or the custom size. The outline's box MUST come from `outline.board_outline`; a board without a closed outline MUST give no warning.
- The message MUST name the outline's size and the page's size in millimetres, and the hint MUST name the paper of the drawing sheet.
- The files MUST be written all the same.

#### Scenario: Board past its paper
- **GIVEN** a board model with the paper `A4` and a rectangular outline from (100 mm, 100 mm) to (258 mm, 279 mm)
- **WHEN** `uv run pytest tests/unit/exports/test_documents.py -k page` calls `page_check`
- **THEN** it returns one `export.page-too-small` warning naming 158 × 179 mm and 297 × 210 mm

#### Scenario: Board on its paper
- **GIVEN** the same model with an outline from (100 mm, 100 mm) to (176 mm, 192 mm)
- **WHEN** `page_check` runs
- **THEN** it returns `None`

### Requirement: Document kinds in the manifest
The artefacts of the six document kinds SHALL enter `fenolite-artifacts.json` as derived entries under "Artefact states" and "Manifest merging", like the files of the four fabrication kinds.
- An entry of `ipc2581`, `odb`, `step`, `pdf`, `dxf` and `sch-pdf` MUST be written by `manifest.merge` with the state `generated`, `tool` `kicad-cli <version>`, `layer` `Artifact.layer` and the `evidence` of its kind ("Artefact manifest").
- `from` MUST hold the SHA-256 of the board for the five board kinds and of the root schematic `<stem>.kicad_sch` for `sch-pdf`, and nothing else. A `step` entry's `from` MUST NOT name model files: they are listed in the export's `result.models`, so a changed model does not mark a STEP stale. A `sch-pdf` entry's `from` MUST NOT name sub-sheets: a changed sub-sheet does not mark it stale (`docs/exports.md` MUST say both).
- `exports.states.DERIVED` MUST hold the six kinds, and `manifest.design_kind` MUST NOT return any of them.

#### Scenario: Two document kinds join the manifest
- **GIVEN** a folder in which `export --gerbers --manifest --confirm` ran, a fake `kicad-cli`, and a board with a schematic beside it
- **WHEN** `uv run pytest tests/unit/cli/test_export_cmd.py -k document_manifest` runs `fenolite export <board> --out <folder> --step --sch-pdf --manifest --confirm`
- **THEN** the manifest lists the Gerbers, `3d/<stem>.step` with the board's hash in `from`, and `schematic/<stem>.pdf` with the schematic's hash in `from`, each `generated`

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
- `gerber_layers(design)` MUST give the board's copper layers in stack order, then `F.Mask`, `B.Mask`, `F.Paste`, `B.Paste`, `F.SilkS`, `B.SilkS` where the board's layer table has them (by KiCad's canonical name), then `Edge.Cuts`.
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

### Requirement: Artefact manifest
`fenolite.exports.manifest.build(*, board, tool_version, artifacts, timestamp) -> dict` SHALL build the manifest written as `fenolite-artifacts.json`, and `schemas/fenolite.artifacts.v0.json` SHALL validate it.
- The manifest MUST hold:
  - `schema`: `fenolite.artifacts.v0`;
  - `fenolite`: the package version;
  - `generated`: `timestamp` in the envelope's format;
  - `board`: `path` (relative to the project root, with `/`), `sha256`, `format_version`;
  - `tool`: `name` (`kicad-cli`) and `version`;
  - `artifacts`: one object per artefact, sorted by `path`, with `path`, `kind`, `layer` (or `null`), `bytes`, `sha256`, `content_sha256`, `evidence`, `state`, `stale`, `from`, `tool` and `held` ("Artefact states");
  - `project`: `board` and `schematic`, each `{path, sha256, format_version}` or `null`;
  - `check`: `null`, or `{stages, tool_version}` with one `{name, status, level, oracle}` per stage that ran ("Project manifest");
  - `states`: the number of artefacts per state, with every state of `manifest.STATES` as a key.
- `content_sha256(data, kind)` MUST be the SHA-256 of `data` without the lines that start with any prefix in `exports.plan.VOLATILE_PREFIXES` for that kind. A line is compared after its leading blanks are removed. The prefixes MUST be the date-bearing lines recorded by `H-K-EXPORT-REPEAT` and `H-K-EXPORT-DOCS-REPEAT`: `%TF.CreationDate`, `G04 Created by KiCad`, `; DRILL file`, `; #@! TF.CreationDate`, for the Gerber job file `"CreationDate":`, and for `pdf` and `sch-pdf` `/CreationDate`. A kind whose `repeat` is `none` (`ipc2581`, `odb`, `step`) MUST have no prefix, so that its `content_sha256` equals its `sha256`.
- The manifest MUST NOT hold an absolute path, a temporary path, the home directory or a user name, and MUST NOT list itself.
- `dumps(manifest)` MUST be canonical JSON (sorted keys, two-space indent, a final newline).
- The artefact files MUST be written with the bytes `kicad-cli` produced; Fenolite MUST NOT edit them.
- `tools/gen_schemas.py --check` MUST cover the schema, whose id stays `fenolite.artifacts.v0`: the fields that this requirement adds to c0024's manifest have defaults, so a manifest written before them still validates. The entry's dataclass field `from_` MUST be written, and named in the schema, as `from`.
- `evidence` of an entry stays the level of the entry's own claim: `exports.EVIDENCE` for a file of a fabrication kind or a view that `kicad-cli` wrote (the level of the run when an export preset lowers it), `exports.DOCUMENTS_EVIDENCE` for a file of a document kind ("Export evidence"), the command's level for a table of `bom` or `pnp`, and `UNVERIFIED` for a design file, whose entry claims a hash only. What was verified about a file is its `state`.
- `manifest.load(text) -> Manifest` MUST read a manifest and give an entry without `state` the state `generated`, `stale` false, an empty `from`, `tool` `None` and an empty `held`. A text that is not JSON, whose `schema` is not `fenolite.artifacts.v0`, or that has not the manifest's shape (an unknown state, a hash that is not 64 hex digits, a path that is absolute or leaves the folder) MUST raise `FormatError` (`FEN-3004`).

#### Scenario: Manifest validates
- **WHEN** `uv run pytest tests/unit/exports/test_manifest.py -k schema` builds a manifest for three artefacts
- **THEN** it validates against `schemas/fenolite.artifacts.v0.json`, and the artefacts are sorted by path

#### Scenario: Dates do not change the content hash
- **GIVEN** two Gerber texts that differ only in their `%TF.CreationDate` and `G04 Created by KiCad` lines
- **WHEN** `content_sha256` is computed for each
- **THEN** the two values are equal and the two `sha256` values differ

#### Scenario: A changed aperture changes the content hash
- **GIVEN** two Gerber texts that differ in one `%ADD` line
- **WHEN** `content_sha256` is computed for each
- **THEN** the values differ

#### Scenario: Reproducible with a timestamp
- **WHEN** `build` runs twice with the same arguments and `timestamp`
- **THEN** `dumps` gives equal text, and the text holds no absolute path

#### Scenario: Entries carry a state
- **WHEN** `uv run pytest tests/unit/exports/test_manifest.py -k state` builds a manifest for three artefacts
- **THEN** each entry has `state` `generated`, `stale` false, an empty `held`, a `from` with the board's SHA-256 and a `tool`, and `states.generated` is 3

#### Scenario: Manifest of v0.1 still read
- **GIVEN** the authored `tests/data/exports/manifest_v01.json`, written in the shape of c0024 without the added fields
- **WHEN** `manifest.load` reads it and the text is validated against the schema
- **THEN** it validates, and every loaded entry has the state `generated`

#### Scenario: The creation date of a PDF
- **GIVEN** two PDF byte strings that differ only in their `/CreationDate (D:…)` line
- **WHEN** `uv run pytest tests/unit/exports/test_manifest.py -k pdf_date` computes `content_sha256` with the kinds `pdf` and `sch-pdf`
- **THEN** the two values are equal for each kind, and with the kind `step` the two values differ

### Requirement: Artefact states
Every manifest entry SHALL carry one `state` of `manifest.STATES = ("generated", "checked", "roundtrip-ok", "oracle-verified", "native-verified")`, in rising order, and `fenolite.exports.states.assign(entries, *, stages, sheets_ok, current) -> tuple[ArtifactEntry, ...]` SHALL assign it: the highest rung a file reaches together with every lower rung that applies to its kind, with `held` saying what the next rung is missing (`<state>: <reason>`, or `""` when no higher rung applies). `stages` maps a stage name to its status and evidence level, `sheets_ok` a sheet path to its RT1 verdict, and `current` a path to the file's present SHA-256.
- **Current.** An entry is current when `current[path]` equals its `sha256` and every hash of its `from` equals the present hash of that source. A derived entry that is not current MUST be `generated` with `stale` true. A design entry whose file has another hash MUST be `generated`; `stale` is only ever true for a derived entry.
- **`generated`.** Every entry reaches it.
- **`checked`.** `model.validate` and `copper.clearance` are in `stages` with status `ok`. A derived entry (kinds `gerbers`, `drill`, `pos`, `ipcd356`, `ipc2581`, `odb`, `step`, `pdf`, `dxf`, `sch-pdf`, `bom`, `pnp`, `render`) reaches it when it is current and the sources its `from` names (`board`: the entry of kind `kicad_pcb`; `schematic`: an entry of kind `kicad_sch`) are `checked`, and reaches no higher rung. A derived entry whose `from` is empty or names another source MUST stay `generated`: nothing says what it was made from.
- **`roundtrip-ok`.** Applies to kinds `kicad_pcb` and `kicad_sch` only: the board needs `roundtrip` with status `ok`, and a sheet needs `sheets_ok[path]` true. Every other design kind skips the rung.
- **`oracle-verified`.** No rule assigns it; every kind skips the rung. The state is reserved for a tool that is neither the producer of a file nor its format's own application.
- **`native-verified`.** The board needs `drc.kicad` with status `ok` and level exactly `KICAD-VERIFIED`. The files KiCad loads to judge the board (kinds `kicad_pro`, `kicad_dru`, `kicad_mod`, `kicad_wks`, and a `lib-table` other than `sym-lib-table`) reach it exactly when the board does. A file of kind `file` (any other file of a library folder) stops at `checked`: no tool is known to load it. A file of kind `3d-model` (a model vendored below `3dmodels/`, "Project manifest") stops at `checked` too: the DRC does not load it, and the `step` export that reads it judges nothing about it.
- **Schematic side.** A sheet (`kicad_sch`), a symbol library (`kicad_sym`) and the `lib-table` named `sym-lib-table` are judged by KiCad's ERC, not by its DRC. Each reaches `native-verified` when `erc.kicad` (change c0062) is in `stages` with status `ok` and level exactly `KICAD-VERIFIED`: the ERC loaded the sheets with the libraries the table names. A sheet needs `roundtrip-ok` first; a symbol library and the symbol table skip that rung. Without that stage, or with an ERC error, a sheet stops at `roundtrip-ok` and a symbol library and the symbol table at `checked`, and `held` names `erc.kicad`. `states.PENDING` MUST be empty: no role waits for a stage that `check` lacks.
- A stage that is missing from `stages`, skipped, or below the level its rule names MUST NOT give its rung, and a rung that is not reached MUST stop the ladder for that file.
- `assign` MUST be pure, MUST import nothing from `checks`, and with an empty `stages` MUST leave every entry `generated`.

#### Scenario: Board up the ladder
- **GIVEN** a board entry that is current, and `stages` with `model.validate`, `copper.clearance` and `roundtrip` `ok` and `drc.kicad` `ok` at `KICAD-VERIFIED`
- **WHEN** `uv run pytest tests/unit/exports/test_states.py -k ladder` calls `assign`
- **THEN** the board's state is `native-verified`

#### Scenario: A failed rung stops the ladder
- **GIVEN** the same stages with `roundtrip` `errors`
- **WHEN** `assign` runs
- **THEN** the board's state is `checked`, although `drc.kicad` is `ok`

#### Scenario: DRC below KICAD-VERIFIED
- **GIVEN** the stages of the first scenario with `drc.kicad` `ok` at `UNVERIFIED`
- **WHEN** `assign` runs
- **THEN** the board's state is `roundtrip-ok`

#### Scenario: Derived file of a checked board
- **GIVEN** a Gerber entry whose `from` holds the board's present hash, and a board that reaches `native-verified`
- **WHEN** `assign` runs
- **THEN** the Gerber's state is `checked`

#### Scenario: Stale artefact
- **GIVEN** a Gerber entry whose `from` holds another hash than the board's present one
- **WHEN** `assign` runs
- **THEN** its state is `generated` and `stale` is true

#### Scenario: Schematic follows the ERC
- **GIVEN** the stages of the first scenario, with and without an `erc.kicad` entry that is `ok` at `KICAD-VERIFIED`, and a sheet whose RT1 verdict is true
- **WHEN** `uv run pytest tests/unit/exports/test_states.py -k erc` calls `assign`
- **THEN** with the entry the sheet, the symbol library and `sym-lib-table` are `native-verified` with an empty `held`; without it, with status `errors`, or at another level, the sheet is `roundtrip-ok`, the other two are `checked`, and each `held` names `erc.kicad`

#### Scenario: No check, no claim
- **WHEN** `assign` runs with `stages` empty
- **THEN** every entry is `generated`, and none is `oracle-verified` under any input of the test's generator

#### Scenario: Documents follow their source
- **GIVEN** a `step` entry whose `from` holds the board's present hash, a `sch-pdf` entry whose `from` holds the root sheet's present hash, a board and a sheet that are `checked`, and a `3d-model` entry
- **WHEN** `uv run pytest tests/unit/exports/test_states.py -k documents` calls `assign` with the stages of the first scenario
- **THEN** the two documents are `checked` with an empty `held`, the model is `checked`, and after the board's hash changes the `step` entry is `generated` and stale while the `sch-pdf` entry stays `checked`

### Requirement: Project manifest
The manifest that `fenolite manifest` writes SHALL list the design files of a project and the artefacts of the folders it is given, with the states of "Artefact states".
- **Design files.** One entry per file of `projectset.project_set(<board>)` (the copy set of a DRC run), of the schematic `<stem>.kicad_sch` with the sheets it names below the project folder (`sch.sheet_files`), of `sym-lib-table` with the `${KIPRJMOD}` libraries it names, and of each file below `<root>/3dmodels/` that is not hidden (the copies of `fenolite models --vendor`, `cli-contract`, "Models command"): `kind` from `manifest.design_kind(path)` (`kicad_pcb`, `kicad_sch`, `kicad_pro`, `kicad_dru`, `kicad_mod`, `kicad_sym`, `kicad_wks`, `lib-table`, `3d-model` for a file below `3dmodels/`, or `file` for any other file of a library folder), `layer` `null`, an empty `from`, `content_sha256` equal to `sha256`, `evidence` `UNVERIFIED`, and `tool` `fenolite <running version>` when `.fenolite/build.json` records that hash for the file and `null` otherwise. A library folder MUST be listed file by file, without its hidden files. `cmd_manifest.design_files(board)` MUST return the list.
- **Artefacts.** For each artefact folder, the derived entries of its `fenolite-artifacts.json` ("Artefact states" names the derived kinds), with paths relative to the project folder; without such a file the folder contributes nothing, and a file that `manifest.load` refuses gives `manifest.unreadable` and contributes nothing. A listed file that does not exist MUST be dropped with `manifest.missing` (warning). A listed file whose SHA-256 differs from the listed one MUST give `manifest.changed` (warning) and MUST be listed with its present hash, an empty `from` and `tool` `null`, so that it stays `generated`. A file under the folder that no entry lists MUST give `manifest.unlisted` (info). An entry that `states.assign` marks stale MUST give `manifest.stale` (warning).
- **Hashes.** `bytes` and `sha256` of every entry MUST be computed from the file as it is when the command runs.
- **Check.** `check` MUST hold the stages that ran, each with its status, evidence level and oracle, and `tool_version`; with no check it MUST be `null`.
- **Codes.** `exports.codes.ISSUE_CODES` MUST gain `manifest.unreadable` (error), `manifest.missing` and `manifest.changed` (each a warning when the command writes and an error under `--verify`), `manifest.stale` (warning) and `manifest.unlisted` (info). `codes.issue(code, …, severity=…)` MUST refuse a severity the table does not give the code.
- The manifest MUST NOT list itself, another `fenolite-artifacts.json`, any file under `.fenolite/`, a `.bak` file or a hidden file. KiCad's local settings (`<stem>.kicad_prl`) are no file of the project set and are never listed; Fenolite names that suffix nowhere in `src/`. A KiCad file (a name with a `.kicad_*` suffix, or a library table) in an artefact folder MUST NOT give `manifest.unlisted`.
- `docs/exports.md` MUST state each state's rule in one line and what the state does not claim.

#### Scenario: Design files of a built project
- **GIVEN** the blink built into `tmp_path`, with an authored schematic of two sheets, an authored symbol table and its library put next to the board (`build` writes none of them yet)
- **WHEN** `uv run pytest tests/unit/cli/test_manifest_cmd.py -k design` runs `fenolite manifest <dir> --no-check --confirm`
- **THEN** the manifest lists the triad, both sheets, both tables, the symbol library and every file under `lib/` that is not hidden, each `generated`, with `tool` naming `fenolite` for the files the build wrote and `null` for the others, and lists neither `.fenolite/build.json` nor itself

#### Scenario: Edited file loses its writer
- **GIVEN** the same project with one byte of the board changed
- **WHEN** the command runs again
- **THEN** the board's entry has `tool` `null` and the new hash

#### Scenario: Artefact folder included
- **GIVEN** `fab/` inside the project, written by `export --all --manifest`, with one extra file `notes.txt`
- **WHEN** `fenolite manifest <dir> --artifacts <dir>/fab --no-check --confirm` runs
- **THEN** the manifest lists the fabrication files as `fab/…`, and the issues hold one `manifest.unlisted` info naming `fab/notes.txt`

#### Scenario: Vendored models are design files
- **GIVEN** a built project with `3dmodels/Fenolite.3dshapes/Box_2x1.step` written by `fenolite models --vendor`
- **WHEN** `uv run pytest tests/unit/cli/test_manifest_cmd.py -k vendored_model` runs `fenolite manifest <dir> --no-check --confirm`
- **THEN** the manifest lists that file with kind `3d-model`, `layer` `null`, an empty `from`, `tool` `null` and state `generated`

### Requirement: Export evidence
`fenolite.exports.EVIDENCE` SHALL be the level of the results of the four fabrication kinds and of `render`, and SHALL be `INFERRED` (`H-K-EXPORT-FILES`, `H-K-EXPORT-REPEAT`) until both hypotheses are `KICAD-VERIFIED (9.0.x, 10.0.x)`. `fenolite.exports.DOCUMENTS_EVIDENCE` SHALL be the level of the six document kinds, and SHALL be `INFERRED` (`H-K-EXPORT-DOCS`, `H-K-EXPORT-DOCS-REPEAT`, `H-K-EXPORT-MODELS`, `H-K-EXPORT-SHEETS`) until all four are `KICAD-VERIFIED (9.0.x, 10.0.x)`.
- The envelope of `render`, and of an `export` that selects only fabrication kinds, MUST carry `exports.EVIDENCE` with the oracle `kicad-cli <version>`. An `export` that selects a document kind MUST carry `Evidence.combine` of the evidence of the selected kinds, with the same oracle.
- The `evidence` of each manifest entry MUST be the level of its kind's evidence.
- `docs/exports.md` MUST state that the content of an exported file is KiCad's, and that Fenolite claims the file set, the hashes, the board or schematic they came from and, for a STEP, the model files it gave the run.

#### Scenario: Evidence in the envelope
- **WHEN** `uv run pytest tests/unit/cli/test_export_cmd.py -k evidence` runs `fenolite export` with the fake `kicad-cli` 10.0.6
- **THEN** `evidence.level` equals `exports.EVIDENCE.level` and `evidence.oracle` is `kicad-cli 10.0.6`

#### Scenario: Evidence of a document kind
- **GIVEN** `DOCUMENTS_EVIDENCE` at `INFERRED` and the fake `kicad-cli` 10.0.6
- **WHEN** `fenolite export <board> --out fab --gerbers --step --manifest --dry-run` runs
- **THEN** `evidence.level` is `INFERRED`, `evidence.hypotheses` holds `H-K-EXPORT-MODELS`, and the planned manifest gives the Gerbers the level of `exports.EVIDENCE` and the STEP `INFERRED`
