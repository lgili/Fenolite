# manufacturing-exports Specification

## Purpose
Produce the fabrication files and review views of a board through `kicad-cli`, on a copy of the project, and describe them in a manifest (`fenolite-artifacts.json`) that ties each file to its board, its tool version and its hashes. Fenolite claims the file set and the hashes, never the fabrication data.

## Requirements

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

### Requirement: Render views
`fenolite render` and the `render` stage SHALL plot review views through `kicad-cli`, and a view that cannot be plotted SHALL be a warning.
- The views MUST be:
  - `front.svg`: `pcb export svg --mode-single --layers F.Cu,F.SilkS,F.Fab,Edge.Cuts`;
  - `back.svg`: the same with the `B.` layers and `--mirror`;
  - `top.png` and `bottom.png`: `pcb render --side top|bottom --width W --height H`.
- The SVG output argument MUST be the form the probes record for the running major.
- A view whose run exits non-zero or writes no file MUST give `render.failed` (warning; `where` = the view name), and the other views MUST still be produced.
- No render result MUST change an exit code to 5.

#### Scenario: Four views from a fake
- **GIVEN** a fake `kicad-cli` that writes an SVG for `pcb export svg` and a PNG for `pcb render`
- **WHEN** `uv run pytest tests/unit/cli/test_render_cmd.py -k views` runs `fenolite render <board> --out r --svg --png --confirm`
- **THEN** `r/front.svg`, `r/back.svg`, `r/top.png` and `r/bottom.png` exist and the exit code is 0

#### Scenario: A failing view is a warning
- **GIVEN** a fake `kicad-cli` that exits 1 for `pcb render`
- **WHEN** the same command runs
- **THEN** the exit code is 0, the two SVG files are written, and the issues hold two `render.failed` warnings

### Requirement: Export evidence
`fenolite.exports.EVIDENCE` SHALL be the level of the results of the four fabrication kinds and of `render`, and SHALL be `INFERRED` (`H-K-EXPORT-FILES`, `H-K-EXPORT-REPEAT`) until both hypotheses are `KICAD-VERIFIED (9.0.x, 10.0.x)`. `fenolite.exports.DOCUMENTS_EVIDENCE` SHALL be the level of the six document kinds, and SHALL be `INFERRED` (`H-K-EXPORT-DOCS`, `H-K-EXPORT-DOCS-REPEAT`, `H-K-EXPORT-MODELS`, `H-K-EXPORT-SHEETS`) until all four are `KICAD-VERIFIED (9.0.x, 10.0.x)`.
- The envelope of `render`, and of an `export` that selects only fabrication kinds, MUST carry `exports.EVIDENCE` with the oracle `kicad-cli <version>`. An `export` that selects a document kind MUST carry `Evidence.combine` of the evidence of the selected kinds, with the same oracle.
- The `evidence` of each manifest entry MUST be the level of its kind's evidence.
- `docs/exports.md` MUST state that the content of an exported file is KiCad's, and that Fenolite claims the file set, the hashes, the board or schematic they came from and, for a STEP, the model files it gave the run.

#### Scenario: Evidence in the envelope
- **WHEN** `uv run pytest tests/unit/cli/test_export_cmd.py -k evidence` runs `fenolite export` with the fake `kicad-cli` 10.0.6
- **THEN** `evidence.level` equals `exports.EVIDENCE.level` and `evidence.oracle` is `kicad-cli 10.0.6`

#### Scenario: Evidence of a document kind
- **GIVEN** `DOCUMENTS_EVIDENCE` at `KICAD-VERIFIED` (the four hypotheses hold on both majors) and the fake `kicad-cli` 10.0.6
- **WHEN** `fenolite export <board> --out fab --gerbers --step --manifest --dry-run` runs
- **THEN** `evidence.level` is `Evidence.combine` of `exports.EVIDENCE` and `DOCUMENTS_EVIDENCE`, `KICAD-VERIFIED`, `evidence.hypotheses` holds `H-K-EXPORT-MODELS`, and the planned manifest gives the Gerbers the level of `exports.EVIDENCE` and the STEP the level of `DOCUMENTS_EVIDENCE`

### Requirement: Export presets
`fenolite.exports.preset` SHALL read an export preset, a TOML file of the user's, and SHALL turn it into the arguments of each export kind, with `PRESET_SCHEMA = "fenolite.export-preset.v0"`, `read_preset(text, *, file="") -> Preset` and `arguments(kind, preset, *, stem, layers) -> tuple[str, ...]`.
- The text MUST be read with `tomllib`; a text that is not TOML, a `schema` other than `PRESET_SCHEMA`, a table other than `gerbers`, `drill` and `pos`, a key outside the table of Decision 4 of the design, or a value outside its allowed values MUST raise `FormatError` (`FEN-3004`) naming the file and the `table.key`.
- `arguments` MUST give, for each kind, c0024's arguments ("Export kinds and their arguments") with each given key replaced by its flag: the options c0024 gives keep their places, and the others follow in the order of Decision 4; a key not given MUST keep c0024's value. A key of the Excellon format given with `format = "gerber"`, and `gerber_precision` without it, MUST raise `FormatError` too. `arguments(kind, None, …)` MUST equal c0024's arguments exactly.
- Every flag a preset can give MUST be present on both majors in the probe rows `help-pcb-export-<kind>-<option>` (`H-K-EXPORT-OPTIONS`); `--check-zones`, `--board-plot-params`, `--variant` and `--generate-tenting` MUST NOT be given.
- With `pos.format`, the placement file MUST be `pos/<stem>-pos.csv`, `.pos` or `.gbr` for `csv`, `ascii` and `gerber`.
- Fenolite MUST NOT ship a preset.

#### Scenario: Protel extensions and inches
- **GIVEN** a preset with `[gerbers]` `protel_extensions = true` and `[drill]` `units = "in"`
- **WHEN** `arguments` runs for `gerbers` and for `drill`
- **THEN** the Gerber arguments hold no `--no-protel-ext`, and the drill arguments hold `--excellon-units in` with every other value of c0024

#### Scenario: Unknown key
- **GIVEN** a preset with `[drill]` `speed = 3`
- **WHEN** it is read with `file="fab.toml"`
- **THEN** `FormatError` is raised naming `fab.toml` and `drill.speed`

#### Scenario: Defaults equal no preset
- **GIVEN** a preset that gives every key its default value
- **WHEN** `arguments` runs for every kind
- **THEN** each list equals `arguments(kind, None, …)`

### Requirement: Artefact states
Every manifest entry SHALL carry one `state` of `manifest.STATES = ("generated", "checked", "roundtrip-ok", "oracle-verified", "native-verified")`, in rising order, and `fenolite.exports.states.assign(entries, *, stages, sheets_ok, current) -> tuple[ArtifactEntry, ...]` SHALL assign it: the highest rung a file reaches together with every lower rung that applies to its kind, with `held` saying what the next rung is missing (`<state>: <reason>`, or `""` when no higher rung applies). `stages` maps a stage name to its status and evidence level, `sheets_ok` a sheet path to its RT1 verdict, and `current` a path to the file's present SHA-256.
- **Current.** An entry is current when `current[path]` equals its `sha256` and every hash of its `from` equals the present hash of that source. A derived entry that is not current MUST be `generated` with `stale` true. A design entry whose file has another hash MUST be `generated`; `stale` is only ever true for a derived entry.
- **`generated`.** Every entry reaches it.
- **`checked`.** `model.validate` and `copper.clearance` are in `stages` with status `ok`. A derived entry (kinds `gerbers`, `drill`, `pos`, `ipcd356`, `ipc2581`, `odb`, `step`, `pdf`, `dxf`, `sch-pdf`, `fab-drawing`, `assembly-drawing`, `bom`, `pnp`, `testpoints`, `render`) reaches it when it is current and the sources its `from` names (`board`: the entry of kind `kicad_pcb`; `schematic`: an entry of kind `kicad_sch`) are `checked`, and reaches no higher rung. A derived entry whose `from` is empty or names another source MUST stay `generated`: nothing says what it was made from.
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

#### Scenario: A drawing follows its board
- **GIVEN** a `fab-drawing` entry whose `from` holds the board's present hash, and a board that reaches `native-verified`
- **WHEN** `uv run pytest tests/unit/exports/test_states.py -k drawing` calls `assign`, and again after the board's hash changed
- **THEN** the drawing is `checked` the first time, and `generated` and stale the second

#### Scenario: The test-point table follows its board
- **GIVEN** a `testpoints` entry whose `from` holds the board's present hash, and a board that is `checked`
- **WHEN** `uv run pytest tests/unit/exports/test_states.py -k testpoints` calls `assign`, and again after the board's hash changed
- **THEN** the entry is `checked` the first time, and `generated` and stale the second

### Requirement: Manifest merging
`manifest.merge(existing, entries, *, board, tool, timestamp) -> Manifest` SHALL return the manifest of an output folder after a command wrote files into it: the entries of `existing` with those of `entries` replacing equal paths, sorted by path.
- `existing` MAY be `None`: the result then holds only `entries`.
- Entries that the command did not write MUST be kept unchanged, their `state`, `held`, `from` and `tool` included.
- New entries MUST have the state `generated`, `stale` false, `from` holding the SHA-256 of the board and, when the command read one, of the schematic, and `tool` naming what wrote the file (`kicad-cli <version>` or `fenolite <version>`).
- `board`, `tool` and `generated` of the manifest MUST be those of the merging run (`tool.name` is `kicad-cli`, or `fenolite` for a run that started no tool), and `project` its board with no schematic; `check` MUST become `null`, because the merging run checked nothing; `states` MUST be recounted.
- `export --manifest` MUST merge in this way instead of replacing the file, and a manifest in the folder that `manifest.load` refuses MUST give `manifest.unreadable` (error) and no planned write.

#### Scenario: Two runs, one manifest
- **GIVEN** a folder in which `export --gerbers --manifest --confirm` ran, and then `export --drill --manifest --confirm`
- **WHEN** `uv run pytest tests/unit/cli/test_export_cmd.py -k merge` reads `fenolite-artifacts.json`
- **THEN** it lists the Gerbers and the drill files, sorted by path, each `generated`

#### Scenario: Re-export replaces by path
- **GIVEN** the same folder after the board changed and `export --gerbers --manifest --confirm` ran again
- **WHEN** the manifest is read
- **THEN** each Gerber entry has the new board hash in `from`, the drill entries keep the old one, and `check` is `null`

#### Scenario: Unreadable manifest refused
- **GIVEN** a folder whose `fenolite-artifacts.json` holds `{`
- **WHEN** `fenolite export <board> --out <folder> --gerbers --manifest --confirm` runs
- **THEN** the exit code is 5, the issues hold `manifest.unreadable`, and no file is written

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

### Requirement: Altium rule file export
`fenolite export` SHALL offer the kind `altium-rul` with the flag `--altium-rul`, which writes `<stem>.RUL` from the rules of the project with no external tool: `exports.altium_rul.export_rules` lowers the rules of `<stem>.kicad_dru` beside the board with `rulemap.lower` and writes them with `rulemap.write_rule_file`.
- The kind MUST NOT be part of `--all`. Selected alone it MUST need no `kicad-cli`.
- `result.rules` MUST name the rules written (`kind`, `selector`, `rule`) and the rules that were not lowered (`kind`, `selector`, `reason`). An artefact entry has no field for notes, so the result holds them.
- When the rules file cannot be read, or no rule of it has an exact Altium form, the export MUST report `export.failed` with `where` `altium-rul` and plan no file.
- The artefact's kind MUST be `altium-rul`; its manifest entry MUST name `fenolite <version>` as its tool and the level of `rulemap.EVIDENCE`, and the envelope's evidence MUST include that evidence.
- The export MUST follow "Writing files" of the CLI contract (dry run, confirm, receipt).

#### Scenario: Rule file from a built project
- **GIVEN** a KiCad project built from a script
- **WHEN** `fenolite export <dir> --out fab --altium-rul --confirm --json` runs with no `kicad-cli` on the machine
- **THEN** the receipt lists `fab/<stem>.RUL`, and reading it gives the rules that the Altium build of the same script writes into its PCB document under `result.rules.written`, with the same names and priorities

#### Scenario: No rule that can be written
- **GIVEN** a project whose only rule selects a net glob
- **WHEN** the same command runs
- **THEN** the exit code is 5, one `export.failed` has `where` `altium-rul`, `result.rules.not_lowered` holds the rule with `scope-unsupported`, and nothing is written

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

### Requirement: Drawing specification files
`fenolite.exports.drawing_spec.read_spec(text, *, file="") -> DrawingSpec` SHALL read a drawing specification, a TOML file of the user's whose `schema` is `fenolite.drawing-spec.v0`, and SHALL refuse anything else before any tool runs.
- The key set MUST be closed:
  - `[page]`: `paper` (`auto` or a name of `PAPER_SIZES`), `portrait` (bool), `drawing_sheet` (a path ending in `.kicad_wks` or `.sheet.toml`, relative to the file's folder), `text_size`, `gap` and `notes_width` (lengths);
  - `[fab]`: `title` (text), `tables` (a list of `board`, `stackup`, `drill`, `impedance`, `notes`; `impedance` is accepted so that the schema id need not change when a change gives that block content, "Drawing tables and notes"), `dimensions` (bool), `dimension_offset` (length), `dimension_precision` (an integer from 0 to 4), `notes` (a list of texts) and `at` (a table of block name to two lengths);
  - `[assembly]`: `title_top` and `title_bottom` (texts), `sides` (a list of `top`, `bottom`), `dnp` (`crossout`, `hide` or `show`), `values`, `pads` and `designators` (bools), `designator_size` (length), `notes` and `at`.
- Lengths MUST be strings with a unit, read by `core.units.parse_length`; the file MUST be parsed with `parse_float=Decimal`, and no float MUST be created.
- The defaults MUST be: `paper = "auto"`, `portrait = false`, no `drawing_sheet`, `text_size = "1.5mm"`, `gap = "5mm"`, `notes_width = "120mm"`, the titles `Fabrication drawing`, `Assembly drawing, top side` and `Assembly drawing, bottom side`, all five tables, `dimensions = true`, `dimension_offset = "8mm"`, `dimension_precision = 2`, no note, both sides, `dnp = "crossout"`, `values = false`, `pads = false`, `designators = true` and `designator_size = "1mm"`. `DEFAULT` MUST hold them, and `export` MUST use it when no file is given.
- A wrong or missing schema id, an unknown table or key, a value of the wrong type or outside its set, a length without a unit, `portrait = true` with `paper = "auto"`, an `at` entry naming a block that its page does not have, or a note holding a control character other than a line feed MUST raise `SpecError`, which MUST list every problem in file order with its dotted key.
- Fenolite MUST ship no note text and no default tolerance, class, material or finish.

#### Scenario: Defaults
- **WHEN** `uv run pytest tests/unit/exports/test_drawing_spec.py -k defaults` reads a file holding only `schema = "fenolite.drawing-spec.v0"`
- **THEN** the result equals `DEFAULT`, `fab.notes` is empty and `page.text_size` is 1500000

#### Scenario: Every problem in file order
- **GIVEN** a file with `[page] paper = "B9"`, `[fab] colour = "red"` and `[assembly] dnp = "maybe"`
- **WHEN** `read_spec` reads it
- **THEN** `SpecError` lists three problems naming `page.paper`, `fab.colour` and `assembly.dnp`, in that order

#### Scenario: Lengths carry units
- **GIVEN** a file with `[page] gap = 5`
- **WHEN** `read_spec` reads it
- **THEN** `SpecError` names `page.gap`

### Requirement: Drawing tables and notes
`fenolite.exports.drawing_tables` SHALL build the blocks of a drawing from the model read from the board, and SHALL size every block with the measured text bounds, so that KiCad never wraps a cell.
- A block MUST be a table of texts `text_size` high with strokes of 0.15 × `text_size`, 1 mm cell margins and a header row naming its columns (`Board` and `Value` for the board block); the notes block has no header row. Lengths MUST be printed in millimetres as exact decimals with at least three decimals (`0.300`, `1.600`, `0.2104`), and a stack-up thickness of 0 as an empty cell.
- **Board**: `Copper layers`; `Outline`, the width and height of the bounding box of the first ring of `board_outline` (`W x H`); with a stack-up, `Thickness` (`Stackup.thickness()`), `Finish` and `Impedance controlled` (`yes` or `no`); `Smallest drill`. The block MUST hold no row about via protection: the model of this change holds none.
- **Stack-up**: one row per entry of `Board.stackup` from the top, entries of kind `solderpaste` left out, with the columns `Layer`, `Type` (`copper`, `core`, `prepreg`, `soldermask`, `silkscreen`, or `dielectric` when `dielectric_kind` is unset), `Material`, `Thickness`, `Dk` (`epsilon_r`), `Df` (`loss_tangent`) and `Color`. A column empty in every row MUST be dropped, and a last row `Total` MUST hold `Stackup.thickness()`. A board without a stack-up MUST get no stack-up block and one `drawing.stackup-missing` (info).
- **Drill**: `drill_rows(design)` MUST give one row per plating, span, drill and slot length, with its count and kinds, from the pads of `board_pads` that have a drill (`thru_hole` plated, `np_thru_hole` not; the slot length from `Padstack.hole_length`, none for a round hole) and the vias of `Board.vias` (plated; the span from `layers`; a through via spans the outer copper layers). Rows MUST come in this order: through spans first, plated before unplated, then the other spans by the stack order of their first layer, then by drill and slot length. The block's columns MUST be `Drill`, `Slot`, `Plated`, `Layers`, `Count` and `Holes` (`via`, `pad` or `via, pad`), `Slot` dropped when no row has a slot, and a last row MUST hold the total count.
- **Impedance**: the model of this change holds no impedance target, so `impedance_block(design)` MUST return no block, and a `tables` list that names `impedance` MUST give neither a block nor an issue.
- **Notes**: one row per note of the spec, with `1.`, `2.`, … in the first column and the note in the second, `notes_width` wide, without border or separator; no block without a note.
- `text_width(text, size)` MUST count `GLYPH_BOUND`, 1.45 × `size`, for each character of `GLYPH_SET` (printable ASCII and `±µ°×ΩÄÖÜßéèçñ–—…`) and 2 × `size` for any other, plus `LINE_EXTRA`, 0.25 × `size`, for a text that holds any character (KiCad draws a line of n glyphs of advance a n × a + 0.25 × the size long, as the probe `draw-glyph-bound` measured on 2026-10-08); `LINE_PITCH` MUST be 1.61 × the size (`H-K-DRAW-TEXT`). A column MUST be as wide as its widest line by `text_width` plus 2 mm, and a row as high as the line count of its tallest cell × the pitch plus 2 mm.
- `break_lines(text, width, size)` MUST break a note at spaces, greedily, into lines that each fit `width` by `text_width`, MUST cut a word longer than `width`, MUST keep the note's own line feeds, and MUST join the lines with `\n`.
- The functions MUST be pure.

#### Scenario: Stack-up rows of a two-layer board
- **GIVEN** a model whose stack-up holds `F.SilkS` (silkscreen, 0), `F.Paste` (solderpaste, 0), `F.Mask` (0.01 mm), `F.Cu` (0.035 mm), `dielectric 1` (core, 1.51 mm, `FR4`, `epsilon_r` `4.5`), `B.Cu` (0.035 mm), `B.Mask` (0.01 mm), `B.Paste` and `B.SilkS`, without colours or loss tangents
- **WHEN** `uv run pytest tests/unit/exports/test_drawing_tables.py -k stackup` builds the block
- **THEN** it has seven entry rows from `F.SilkS` to `B.SilkS` without paste rows and without the columns `Color` and `Df`, the core row reads `core`, `FR4`, `1.510` and `4.5`, and the last row reads `Total` and `1.600`

#### Scenario: Drill rows of vias and pads
- **GIVEN** a four-layer model with three through vias of 0.3 mm, one blind via of 0.1 mm from `F.Cu` to `In1.Cu`, two `thru_hole` pads of 1.0 mm, one `thru_hole` pad with an oval drill of 1.0 mm by 2.0 mm and one `np_thru_hole` pad of 3.2 mm
- **WHEN** `drill_rows` runs
- **THEN** the rows are, in order: plated `F.Cu` to `B.Cu` 0.300 (3, `via`), 1.000 (2, `pad`) and 1.000 with slot 2.000 (1, `pad`); unplated `F.Cu` to `B.Cu` 3.200 (1, `pad`); plated `F.Cu` to `In1.Cu` 0.100 (1, `via`); and the block's total is 8

#### Scenario: No stack-up
- **GIVEN** a model whose `Board.stackup` is `None`
- **WHEN** the blocks of the fabrication page are built
- **THEN** there is no stack-up block, the board block has no `Thickness`, `Finish` or `Impedance controlled` row, and one `drawing.stackup-missing` info is returned

#### Scenario: Notes are broken by the bound
- **GIVEN** a note of 227 characters, a width of 78 mm and a size of 1.5 mm
- **WHEN** `break_lines` runs
- **THEN** every line's `text_width` is at most 78 mm, the lines joined with spaces give the note back, and its row is the line count × 2.415 mm plus 2 mm high

### Requirement: Drawing page layout
`fenolite.exports.drawing_layout` SHALL lay out each drawing page at 1:1 around the board, and SHALL choose the page's paper.
- The board MUST stay where the board file puts it: page coordinates MUST be board coordinates (`H-K-DRAW-PAGE`), and no scale option MUST be passed.
- The board box of a page MUST be:
  - fabrication: the bounding box of the outline, grown at the top and at the left by `dimension_offset` + 2 × `text_size` when `dimensions` is true, joined with the extent of every root item on `Dwgs.User`;
  - top assembly: the outline's box joined with the courtyard boxes of the top-side footprints (`placed_extents`) and the extent of the root items on `F.Fab`;
  - bottom assembly: the same for the bottom side and `B.Fab`, mirrored by x ↦ W − x for the page width W.
- For KiCad's default sheet the margin box MUST be the page less 10 mm on each side, and the obstacles the band from there to the border 12 mm inside each edge and the title block box [W − 120 mm, W − 12 mm] × [H − 44 mm, H − 12 mm] (`H-K-DRAW-SHEET`). For any other sheet the margin box MUST be the page less the sheet's margins, and the obstacles the boxes of the lines and texts that `templates.layout` predicts on the page. `cmd_export` MUST compute them and pass them as rectangles, so that `exports` imports no `templates`.
- `place(blocks, *, page, board_box, obstacles, gap, fixed)` MUST give each block, in the order board, stack-up, drill, impedance, notes, the first top-left corner, in the order of x then y, among the margin box's left edge and the right edges of every obstacle, of the board box and of every placed block plus `gap`, and the margin box's top edge and the bottom edges of the same boxes plus `gap`, at which the block lies in the margin box and is at least `gap` from every obstacle, the board box and every placed block. A block named in `fixed` MUST take that corner and MUST meet the same conditions.
- The paper MUST be the spec's when it names one; with `auto` it MUST be the first of A4, A3, A2, A1 and A0 in landscape on which the board box lies in the margin box at least `gap` from every obstacle and every block is placed. Page sizes MUST be those KiCad plots.
- When no paper is found, or the named paper does not hold the board box or a block, the page MUST give `drawing.no-room` (error) naming the page, the block or the board box with its corners in millimetres, and the smallest paper that holds it or that none does; `export` MUST then plan no write.
- `place` and `choose_paper` MUST be pure and deterministic.

#### Scenario: The 600-part probe board on KiCad's default sheet
- **GIVEN** a fabrication page whose board box spans (89 mm, 89 mm) to (258 mm, 279 mm), one block of 150 mm × 200 mm, `gap` 5 mm and KiCad's default sheet
- **WHEN** `uv run pytest tests/unit/exports/test_drawing_layout.py -k paper` chooses the paper with `auto`
- **THEN** A4 and A3 are refused, the paper is A2, and the block's corner is (263 mm, 17 mm)

#### Scenario: A fixed block over the title block
- **GIVEN** a top assembly page with `paper = "A3"`, KiCad's default sheet, a board box from (100 mm, 100 mm) to (176 mm, 192 mm), one note of one line and `at.notes = ["310mm", "260mm"]`
- **WHEN** the page is laid out
- **THEN** it gives `drawing.no-room` naming `notes` and A2 as the smallest paper that holds it

#### Scenario: The bottom page is mirrored
- **GIVEN** a bottom assembly page on A3, whose page width is 419.989 mm, and an unmirrored box from x = 100 mm to x = 176 mm
- **WHEN** its board box is computed
- **THEN** the box spans x = 243.989 mm to x = 319.989 mm

#### Scenario: A board outside every page
- **GIVEN** a fabrication page whose board box starts at x = −20 mm
- **WHEN** the paper is chosen with `auto`
- **THEN** the page gives `drawing.no-room` naming the board box and stating that no paper holds it

### Requirement: Drawing plot copies
`fenolite.backends.kicad.drawing.plot_copy(board_text, items, *, paper, portrait, major, layers) -> str` SHALL return the text of a copy of the board that holds a page's items, and no drawing kind SHALL write the board file.
- The copy MUST equal the board's text except for: the `paper` node, set to the page's paper and orientation; the item nodes, appended as root children; and, for each name in `layers` that the layer table lacks, the row `(17 "Dwgs.User" user "User.Drawings")`, `(35 "F.Fab" user)` or `(33 "B.Fab" user)`.
- A `PlotTable` MUST become a `table` node whose children come in the order `column_count`, `uuid` (major 10 only), `layer`, `border`, `separators`, `column_widths`, `row_heights`, `cells`, each `table_cell` holding `start`, `end`, `margins`, `span`, `layer`, `uuid` and `effects` (`H-K-DRAW-ITEMS`). A `PlotText` MUST become a `gr_text`, with `mirror` in its `justify` on a back layer. A `PlotDimension` MUST become an `orthogonal` `dimension` node in c0103's form (`H-K-DIM`).
- Every uuid MUST be `uuid5` of the page kind and the block and cell names, and two calls with equal arguments MUST return equal texts.
- `layer_extent(board_text, layer)` MUST give the bounding box of every coordinate (`at`, `start`, `end`, `mid`, `center`, `xy`) of the root items on `layer`, or `None` when there is none.
- `shows_reference(footprint, layer)` MUST be true when the footprint holds, on `layer`, a text `${REFERENCE}` or a `Reference` property that is not hidden.
- `KicadCli.run` and `KicadCli.export` MUST accept `bytes` as a source in `files`, written under its name in the run folder; such a file MUST NOT be among the outputs unless the run changed it.

#### Scenario: Only the page's changes
- **GIVEN** the text of `tests/data/kicad/board/two_layer.kicad_pcb`, whose layer table has no `Dwgs.User`
- **WHEN** `uv run pytest tests/unit/backends/kicad/test_drawing_copy.py -k copy` calls `plot_copy` with one table of three columns and two rows on `Dwgs.User`, paper `A3`, major 9 and `layers=("Dwgs.User",)`
- **THEN** the copy holds `(paper "A3")`, the `Dwgs.User` row and one `table` without `uuid`; with those three changes undone it is tree-equal to the board text; and the board file's SHA-256 is unchanged

#### Scenario: Target 10 table
- **WHEN** the same call runs with major 10
- **THEN** the table holds a `uuid` right after `column_count`, and every child follows the order of the requirement

#### Scenario: Same input, same copy
- **WHEN** `plot_copy` runs twice with equal arguments
- **THEN** the two texts are equal

#### Scenario: A footprint that shows its reference
- **GIVEN** a footprint of KiCad's libraries with a `${REFERENCE}` text on `F.Fab`, and a catalog footprint whose `F.Fab` holds only its body outline
- **WHEN** `shows_reference(footprint, "F.Fab")` runs on each
- **THEN** it is true for the first and false for the second

### Requirement: Fabrication drawing kind
The export kind `fab-drawing` SHALL produce the fabrication drawing from plot copies, and SHALL check its drill table against KiCad's drill report on every run.
- The page MUST be plotted by `pcb export pdf --mode-single --layers Edge.Cuts,Dwgs.User --include-border-title --drill-shape-opt 0 -D FENOLITE_DRAWING=<fab.title> [--drawing-sheet <sheet>] -o drawings/<stem>-fab.pdf <stem>.kicad_pcb` on a copy that holds the blocks of `fab.tables` that have content, placed by "Drawing page layout", and, when `dimensions` is true, the two dimensions of the outline's bounding box: horizontal at `dimension_offset` above it, vertical at `dimension_offset` left of it, in millimetres with `dimension_precision` decimals.
- The maps and the report MUST come from `pcb export drill -o drawings/ --format excellon --excellon-units mm --excellon-separate-th --drill-origin absolute --generate-map --map-format pdf --generate-report <stem>.kicad_pcb` on the copy set; every `*-drl_map.pdf` file and `<stem>-drill.rpt` that it writes MUST be an artefact, and its `.drl` files MUST NOT. The `drill` kind with the preset key `drill.map` ("Export presets") writes maps of its own under `drill/`; an export that selects both MUST keep both sets, each under its own kind, and `docs/drawings.md` MUST say that the two are the same maps.
- `read_drill_report(text)` MUST give, per drill file named in the report, each tool's diameter and hole count, reading tool lines that close with `)` or `))`. When the multiset of (diameter, count) of a file differs from the drill rows of that file (plated through, unplated through, each other span), the kind MUST give `drawing.drill-mismatch` (error) naming the file, the diameter and both counts. A report from which no file is read MUST give `drawing.drill-report-unread` (warning), and the drill block MUST stay.
- Artefacts MUST have the kind `fab-drawing` and the layer `None`; `VOLATILE_PREFIXES["fab-drawing"]` MUST be `/CreationDate` and `Created on` (`H-K-DRAW-REPEAT`).
- `--check-zones` and `--board-plot-params` MUST NOT be passed.

#### Scenario: Files of the kind
- **GIVEN** a fake `kicad-cli` whose `pcb export pdf` writes `drawings/b-fab.pdf`, and whose `pcb export drill` writes `drawings/b-PTH.drl`, `drawings/b-NPTH.drl`, both maps and a report that matches the board
- **WHEN** `uv run pytest tests/unit/exports/test_drawings.py -k fab` runs `run_fab_drawing`
- **THEN** the artefacts are `drawings/b-NPTH-drl_map.pdf`, `drawings/b-PTH-drl_map.pdf`, `drawings/b-drill.rpt` and `drawings/b-fab.pdf`, all of kind `fab-drawing`, and no `.drl` file is among them

#### Scenario: Both forms of a tool line
- **WHEN** `read_drill_report` reads the lines `T1  0.300mm  0.0118"  (83 holes))` and `T2  0.600mm  0.0236"  (6 holes)` under `Drill file 'b-PTH.drl' contains`
- **THEN** it gives, for `b-PTH.drl`, 83 holes of 0.300 mm and 6 holes of 0.600 mm

#### Scenario: A count that differs
- **GIVEN** a fake report giving 84 holes of 0.300 mm in `b-PTH.drl` for a board with 83
- **WHEN** `fenolite export <board> --out fab --fab-drawing --confirm` runs
- **THEN** the issues hold `drawing.drill-mismatch` naming `b-PTH.drl`, `0.300`, `83` and `84`, the exit code is 5, and `fab` does not exist

#### Scenario: Dates do not change the content hash
- **GIVEN** two drawing PDFs that differ only in their `/CreationDate` line, and two reports that differ only in their `Created on` line
- **WHEN** `content_sha256` is computed for each with the kind `fab-drawing`
- **THEN** both pairs have equal values

### Requirement: Assembly drawing kind
The export kind `assembly-drawing` SHALL produce a top page and, when a part sits on the bottom, a mirrored bottom page, from plot copies.
- The top page MUST be plotted by `pcb export pdf --mode-single --layers F.Fab,Edge.Cuts --include-border-title --drill-shape-opt 0 -D FENOLITE_DRAWING=<title_top> [--drawing-sheet <sheet>] <options> -o drawings/<stem>-assembly-top.pdf <stem>.kicad_pcb`, and the bottom page with `--layers B.Fab,Edge.Cuts`, `--mirror`, `<title_bottom>` and `-o drawings/<stem>-assembly-bottom.pdf`.
- `<options>` MUST be `--exclude-value` unless `values` is true, `--sketch-pads-on-fab-layers` when `pads` is true, and `--crossout-DNP-footprints-on-fab-layers` for `dnp = "crossout"`, `--hide-DNP-footprints-on-fab-layers` for `hide`, nothing for `show` (`H-K-DRAW-ASSEMBLY`).
- A side absent from `sides` MUST have no page. The bottom page MUST be left out, with one `drawing.side-empty` (info) naming `bottom`, when no footprint sits on the bottom.
- With `designators` true, each footprint of a page's side for which `shows_reference` is false on that side's fabrication layer MUST get a `PlotText` of its reference, `designator_size` high, at the centre of its courtyard's bounding box, or at its position when it has no courtyard, on `F.Fab`, or mirrored on `B.Fab`; under `dnp = "hide"` a do-not-populate footprint MUST get none; a page that adds any MUST give one `drawing.designators-added` (info) with the count.
- The notes of `[assembly]` MUST be placed on the top page, on `F.Fab`.
- Artefacts MUST have the kind `assembly-drawing` and the layer `None`; `VOLATILE_PREFIXES["assembly-drawing"]` MUST be `/CreationDate`.

#### Scenario: Default arguments
- **GIVEN** a board with parts on both sides and `DEFAULT`
- **WHEN** `uv run pytest tests/unit/exports/test_drawings.py -k assembly` runs `run_assembly_drawing` with a fake `kicad-cli`
- **THEN** two `pcb export pdf` runs are made: the top one with `--layers F.Fab,Edge.Cuts`, `--exclude-value` and `--crossout-DNP-footprints-on-fab-layers` and without `--mirror`, the bottom one with `--layers B.Fab,Edge.Cuts` and `--mirror`

#### Scenario: Options of the spec
- **GIVEN** a spec with `values = true`, `pads = true` and `dnp = "hide"`
- **WHEN** the kind runs
- **THEN** no run holds `--exclude-value`, and each holds `--sketch-pads-on-fab-layers` and `--hide-DNP-footprints-on-fab-layers`

#### Scenario: No part on the bottom
- **GIVEN** a board whose parts all sit on the top
- **WHEN** the kind runs
- **THEN** only `drawings/<stem>-assembly-top.pdf` is an artefact, and one `drawing.side-empty` info names `bottom`

#### Scenario: References added where none is shown
- **GIVEN** a board with a catalog resistor `R1` and a library capacitor `C1` whose footprint shows `${REFERENCE}` on `F.Fab`, both on the top
- **WHEN** the top copy is built
- **THEN** it holds one added `gr_text` `R1` on `F.Fab` at the centre of `R1`'s courtyard box and none for `C1`, and `drawing.designators-added` gives 1

### Requirement: Drawing kinds in the manifest
The artefacts of `fab-drawing` and `assembly-drawing` SHALL enter `fenolite-artifacts.json` as derived entries under "Artefact states" and "Manifest merging", like the files of the other kinds that `kicad-cli` writes from the board.
- An entry of either kind MUST be written by `manifest.merge` with the state `generated`, `tool` `kicad-cli <version>`, `layer` `null` (a page plots several layers), `from` holding the SHA-256 of the board and nothing else, and `evidence` the level of `exports.drawings.EVIDENCE`.
- `from` MUST NOT name the drawing spec or the drawing sheet: a changed spec does not mark a drawing stale, and `docs/drawings.md` MUST say so.
- `exports.states.DERIVED` MUST hold both kinds, and `manifest.design_kind` MUST NOT return either.

#### Scenario: Drawings join the manifest
- **GIVEN** a folder in which `export --gerbers --manifest --confirm` ran, and a fake `kicad-cli`
- **WHEN** `uv run pytest tests/unit/cli/test_export_drawings.py -k manifest` runs `fenolite export <board> --out <folder> --fab-drawing --assembly-drawing --manifest --confirm`
- **THEN** the manifest lists the Gerbers and every file under `drawings/` with kind `fab-drawing` or `assembly-drawing`, `layer` `null`, the board's hash in `from` and the state `generated`

### Requirement: Stack-up note in exports
`fenolite export` SHALL note when a kind it runs states a stack-up and the board holds none, because KiCad then states its own default (`H-K-STACKUP-DEFAULT`).
- `exports.plan.STACKUP_KINDS` MUST hold `gerbers`, whose job file states the stack-up. When a selected kind is in it and the read board's `Board.stackup` is `None`, one `export.stackup-default` (info; `where` the kind) MUST say that KiCad states there 0.035 mm copper, 0.01 mm masks, equal FR4 dielectrics that fill the board thickness, and the finish `None`; its hint MUST name `design.stackup()` and KiCad's Board Setup.
- `exports.codes.ISSUE_CODES` MUST gain `export.stackup-default` with severity `info`. An info MUST NOT stop the writes: by `cli-contract` "Export command" (MODIFIED by this change, on the text of `export-documents`) only an issue of severity `error` stops them.
- The note MUST NOT change the files that `kicad-cli` writes.

#### Scenario: Board without a stack-up
- **GIVEN** a fake `kicad-cli` 10.0.6 that writes the Gerbers and the job file of `two_layer.kicad_pcb`
- **WHEN** `uv run pytest tests/unit/cli/test_export_cmd.py -k stackup` runs `fenolite export <board> --out fab --gerbers --dry-run --json`
- **THEN** the exit code is 0, the issues hold one `export.stackup-default` info with `where` `gerbers`, and the plan lists every file the fake wrote

#### Scenario: Board with a stack-up
- **GIVEN** the same fake and the copy of `two_layer.kicad_pcb` with a complete node of "Stack-up thicknesses in analyze"
- **WHEN** the same command runs
- **THEN** the issues hold no `export.stackup-default`

#### Scenario: Other kinds
- **WHEN** the command runs on `two_layer.kicad_pcb` with `--drill --pos` only
- **THEN** the issues hold no `export.stackup-default`
