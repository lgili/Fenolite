# manufacturing-exports Specification

## Purpose
Produce the fabrication files and review views of a board through `kicad-cli`, on a copy of the project, and describe them in a manifest (`fenolite-artifacts.json`) that ties each file to its board, its tool version and its hashes. Fenolite claims the file set and the hashes, never the fabrication data.
## Requirements
### Requirement: Export kinds and their arguments
`fenolite.exports.plan.KINDS` SHALL map each export kind to the `kicad-cli` words and fixed options it runs with, and `run_kind(cli, kind, board, files, *, major) -> KindResult` SHALL run one kind on the copy set and return its artefacts.
- The kinds MUST be `gerbers`, `drill`, `pos` and `ipcd356`, with these arguments, where `<stem>` is the board file's stem:
  - `gerbers`: `pcb export gerbers -o gerbers/ --no-protel-ext --layers <list>`;
  - `drill`: `pcb export drill -o drill/ --format excellon --excellon-units mm --excellon-separate-th --drill-origin absolute`;
  - `pos`: `pcb export pos --format csv --units mm --side both -o pos/<stem>-pos.csv`;
  - `ipcd356`: `pcb export ipcd356 -o netlist/<stem>.d356`.
- `gerber_layers(design)` MUST give the board's copper layers in stack order, then `F.Mask`, `B.Mask`, `F.Paste`, `B.Paste`, `F.SilkS`, `B.SilkS` where the board's layer table has them (by KiCad's canonical name), then `Edge.Cuts`.
- `--check-zones` and `--board-plot-params` MUST NOT be passed for any kind.
- `KindResult.artifacts` MUST hold one `Artifact(path, kind, layer, data, repeatable)` per file the run wrote under the kind's output folder, sorted by path; `path` is relative to the output folder and uses `/`.
- `Artifact.layer` MUST be the layer's canonical name for a Gerber, found from the file name's suffix through the canonical and the user names of the board's layer table (KiCad names the file after the name it shows, `F_Silkscreen` for `F.SilkS`), and `None` for any other kind, for the job file `<stem>-job.gbrjob` and for a suffix that matches no layer.
- Files the run wrote outside the kind's output folder MUST be listed in `KindResult.tool_writes` and MUST NOT become artefacts.
- A run that exits non-zero, or writes no file, MUST give one `export.failed` (error; `where` = the kind) whose message is the first line of the tool's output with every temporary path removed.
- A kind that the probes record as unavailable on the running major MUST give `export.kind-unavailable` (error) and MUST run no subprocess.
- `fenolite.exports.codes.ISSUE_CODES` MUST hold `export.failed`, `export.kind-unavailable` and `render.failed` with their severities.

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
- **THEN** none holds `--check-zones` or `--board-plot-params`

### Requirement: Artefact manifest
`fenolite.exports.manifest.build(*, board, tool_version, artifacts, timestamp) -> dict` SHALL build the manifest written as `fenolite-artifacts.json`, and `schemas/fenolite.artifacts.v0.json` SHALL validate it.
- The manifest MUST hold:
  - `schema`: `fenolite.artifacts.v0`;
  - `fenolite`: the package version;
  - `generated`: `timestamp` in the envelope's format;
  - `board`: `path` (relative to the project root, with `/`), `sha256`, `format_version`;
  - `tool`: `name` (`kicad-cli`) and `version`;
  - `artifacts`: one object per artefact, sorted by `path`, with `path`, `kind`, `layer` (or `null`), `bytes`, `sha256`, `content_sha256` and `evidence`.
- `content_sha256(data, kind)` MUST be the SHA-256 of `data` without the lines that start with any prefix in `exports.plan.VOLATILE_PREFIXES` for that kind. A line is compared after its leading blanks are removed. The prefixes MUST be the date-bearing lines recorded by `H-K-EXPORT-REPEAT`: `%TF.CreationDate`, `G04 Created by KiCad`, `; DRILL file`, `; #@! TF.CreationDate` and, for the Gerber job file, `"CreationDate":`.
- The manifest MUST NOT hold an absolute path, a temporary path, the home directory or a user name, and MUST NOT list itself.
- `dumps(manifest)` MUST be canonical JSON (sorted keys, two-space indent, a final newline).
- The artefact files MUST be written with the bytes `kicad-cli` produced; Fenolite MUST NOT edit them.
- `tools/gen_schemas.py --check` MUST cover the new schema.

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
`fenolite.exports.EVIDENCE` SHALL be the level of the export results, and SHALL be `INFERRED` (`H-K-EXPORT-FILES`, `H-K-EXPORT-REPEAT`) until both hypotheses are `KICAD-VERIFIED (9.0.x, 10.0.x)`.
- The envelope of `export` and `render` MUST carry `exports.EVIDENCE` with the oracle `kicad-cli <version>`.
- `docs/exports.md` MUST state that the content of an exported file is KiCad's, and that Fenolite claims the file set, the hashes and the board they came from.

#### Scenario: Evidence in the envelope
- **WHEN** `uv run pytest tests/unit/cli/test_export_cmd.py -k evidence` runs `fenolite export` with the fake `kicad-cli` 10.0.6
- **THEN** `evidence.level` equals `exports.EVIDENCE.level` and `evidence.oracle` is `kicad-cli 10.0.6`

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

