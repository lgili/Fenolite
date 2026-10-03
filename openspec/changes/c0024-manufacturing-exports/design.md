## Context

- **Scope.** The unowned v0.1 deliverables "exports via `kicad-cli` + `fenolite-artifacts.json`, `render`" (plan, v0.1), the loop steps `fenolite export … --gerbers --drill --pos --manifest` and `fenolite render … --png --svg` (plan, appendix B), and stage 6 of plan D9: "`render`: `kicad-cli pcb render` / `export svg` attached to the manifest, never a gate". c0013 left the commands, the manifest and the stage to this change.
- **The tool.** Usage lines read on 9.0.9 and 10.0.6 at proposal time (S-0020):
  - both majors have `pcb export gerbers`, `drill`, `pos`, `ipcd356`, `svg`, `pdf` and `pcb render`;
  - `pcb export stats`, `--check-zones` (gerbers, svg, pdf, odb) and `--variant` exist on 10.0 only; `pcb export svg --output` is a folder on 10.0 and a file on 9.0, and c0009's load check already uses `-o out.svg` with `--mode-single` on both;
  - `gerbers` takes `--layers`, `--no-protel-ext`, `--no-x2`, `--use-drill-file-origin`, `--board-plot-params`; `drill` takes `--format`, `--excellon-units`, `--excellon-separate-th`, `--drill-origin`, `--generate-map`; `pos` takes `--format`, `--units`, `--side`; `render` takes `--side`, `--width`, `--height`, `--background`, `--quality`.
- **Observed with 10.0.6 on `two_layer.kicad_pcb` (2026-10-03), through the package runner:**
  - `gerbers -o out/ --no-protel-ext` writes 15 files named `<stem>-<Layer>.gbr` (for example `two_layer-F_Cu.gbr`, `two_layer-Edge_Cuts.gbr`);
  - `drill --format excellon --excellon-units mm --excellon-separate-th` writes `<stem>-PTH.drl` and `<stem>-NPTH.drl`;
  - two runs of `gerbers`, `drill` and `svg` differ only in lines that carry the creation date (`%TF.CreationDate,…*%`, `G04 Created by KiCad (…) date …*`, `; DRILL file … date …`, `; #@! TF.CreationDate,…`, the SVG `<title>`); `pos` (CSV), `ipcd356` and the `render` PNG are byte-equal across two runs;
  - `pcb render --side top --width 400 --height 300` writes a PNG headless, on macOS.
- **What exists in Fenolite.** c0009's `KicadCli.run` (copies, isolated environment, `CliRun.outputs`), `export_pos_csv`, `export_ipcd356`, `load_board_svg`; c0013's `projectset.project_set`, the pre-flight of `check`, `STAGE_ORDER` open to inserted stages and `tests/_fakecli.py`; the mutation protocol (`PlannedWrite`, plan, receipt with SHA-256, backups); `--timestamp` and `Context.timestamp` for reproducible output.
- **Consistency suite.** Every command's `example_args` must exit 0, and a mutating command's `mutation_example_args` must write its planned files in an empty folder (living `cli-contract`). `export` and `render` have no path without `kicad-cli`.
- **Layering.** The rows `exports` and `render` exist (`model`, `geometry`, any `backends`).
- **Constraints.** Stdlib only. The roadmap gives this change 4.5 days.

## Goals / Non-Goals

**Goals:**
- One command produces the fabrication files of a board through `kicad-cli`, on a copy, and writes them only with `--confirm`.
- The manifest ties every artefact to the board's SHA-256, the tool version and its own hash, and lets two exports be compared although KiCad stamps dates.
- Renders for review, never a gate.
- The same proof on 9.0.9 and 10.0.6.

**Non-Goals:**
- Everything under "Non-goals" in the proposal.
- Options of `kicad-cli` beyond the fixed argument tables: v0.1 has one way to export each kind.

## Decisions

1. **Probe first.** Task group 2 pins on both majors, as probes: the file names of each kind (`export-files-<kind>`), byte repeatability and the date-stripped comparison (`export-repeat-<kind>`), and renders (`export-render-png`, `export-render-svg`). The argument tables of Decision 2 are final only after the probes; a kind that fails on a major is reported by `export` as unavailable there (`export.kind-unavailable`), never emulated.

2. **One argument table per kind.** `exports/plan.py::KINDS` maps each kind to its `kicad-cli` words and fixed options, with per-major differences in the same table:
   - `gerbers`: `pcb export gerbers -o gerbers/ --no-protel-ext --layers <copper layers in stack order, then the mask, paste and silkscreen pairs, then Edge.Cuts>`, layer names from the board's own layer table;
   - `drill`: `pcb export drill -o drill/ --format excellon --excellon-units mm --excellon-separate-th --drill-origin absolute`;
   - `pos`: `pcb export pos --format csv --units mm --side both -o pos/<stem>-pos.csv`;
   - `ipcd356`: `pcb export ipcd356 -o netlist/<stem>.d356`.
   - `--board-plot-params` and `--check-zones` are never passed: the first would make the result depend on settings stored in the board, the second would refill zones in the copy, so the files would not show the board as it is.
   - Rejected: passing free `kicad-cli` options through. Each option changes what a fab receives; v0.2a adds named presets.

3. **Runner.** `KicadCli.export(args, board, *, files=None, out) -> CliRun` and `KicadCli.render(board, *, side, width, height, files=None) -> CliRun` are thin wrappers over `run`: they pre-create `out` in the run folder and never raise for a non-zero exit. `exports.plan.run_kind` reads the produced files from `CliRun.outputs` under `out`.
   - The copy set is c0013's `project_set`: the drawing sheet and libraries a plot may read are already in it.

4. **Artefacts.** `exports.plan.Artifact(path, kind, layer, data, repeatable)`:
   - `path` is relative to the output folder (`gerbers/board-F_Cu.gbr`);
   - `layer` is the layer name for Gerbers, taken from the file name's suffix through the board's layer table, and `None` otherwise;
   - `repeatable` is false for kinds whose files carry a date (from the probe).

5. **Manifest.** `exports/manifest.py::build(…) -> dict` and `fenolite-artifacts.json`, validated by `schemas/fenolite.artifacts.v0.json`:
   - `schema` (`fenolite.artifacts.v0`), `fenolite` (version), `generated` (`Context.timestamp`, so `--timestamp` makes it reproducible);
   - `board`: `path` (relative to the project root), `sha256`, `format_version`;
   - `tool`: `name` (`kicad-cli`), `version`;
   - `artifacts`: a list sorted by path, each `{path, kind, layer, bytes, sha256, content_sha256, evidence}`.
   - **`content_sha256`** is the SHA-256 of the file with its date-bearing lines removed: lines that start with `%TF.CreationDate`, `G04 Created by KiCad`, `; DRILL file` or `; #@! TF.CreationDate`, and the `"CreationDate":` line of the Gerber job file (leading blanks ignored). Render views are not artefacts of the manifest, so the SVG `<title>` date needs no rule. For a repeatable kind it equals `sha256` of the same bytes without those (absent) lines. Two exports of an unchanged board have equal `content_sha256` for every file (`H-K-EXPORT-REPEAT`).
   - The files themselves are written exactly as KiCad wrote them.
   - The manifest holds no absolute path. It lists itself nowhere.
   - Rejected: rewriting dates in the fab files for byte-identical exports. A fab file is KiCad's; Fenolite does not edit it.
   - Rejected: a state per artefact and a complete project manifest (v0.2a).

6. **`fenolite export PATH --out DIR`** (`cli/cmd_export.py`, `mutates=True`). Flags: `--gerbers`, `--drill`, `--pos`, `--ipcd356`, `--all` (the four), `--manifest`, `--kicad-cli`, `--timeout` (default 300).
   - No kind selected exits 2 (`FEN-2001`).
   - Pre-flight as `check`'s `drc.kicad`: `FEN-6001` without a binary, `FEN-6002` for an unsupported major or a board newer than the tool reads.
   - Each selected kind runs once on the copy set. A kind whose run exits non-zero or writes no file gives `export.failed` (error) with the first sanitised line of the tool's output; the other kinds still run, and the command returns no `PlannedWrite` at all when any kind failed, so a folder never holds a partial set.
   - Planned writes: every artefact at `DIR/<path>`, and `DIR/fenolite-artifacts.json` with `--manifest`. `DIR` is relative to the working directory. The mutation protocol applies; `--dry-run` runs the tool on the copy and shows the plan.
   - `result`: `board`, `out`, `kinds`, `artifacts` (path, kind, layer, bytes, sha256, content_sha256), `tool_version`, `tool_writes` (files the tool wrote outside its output folders, such as `<stem>.kicad_prl`).
   - Evidence: `exports.EVIDENCE` with oracle `kicad-cli <version>`.

7. **`fenolite render PATH --out DIR`** (`cli/cmd_render.py`, `mutates=True`). Flags: `--svg`, `--png`, `--width` (default 1600), `--height` (default 1200), `--kicad-cli`, `--timeout`.
   - `--svg`: `front.svg` (the front copper, silkscreen, fabrication and `Edge.Cuts` layers, `--mode-single`) and `back.svg` (the back counterparts, `--mirror`), through `pcb export svg`;
   - `--png`: `top.png` and `bottom.png`, through `pcb render --side top|bottom --width W --height H`.
   - A view that fails gives `render.failed` (warning) and is left out; the exit code stays 0 unless no tool is found (exit 6). A render is never a gate.
   - `result`: `views` (path, kind, bytes, sha256), `tool_version`. Evidence as `export`.

8. **`render` stage in `check`.** `checks/render.py::render_stage(plotter, project) -> StageResult`, after `roundtrip`, selected only when named in `--stages` (opt-in, as c0020's `roundtrip.rt2`).
   - `backends.base` gains the protocol `Plotter` (`name`, `plot(project: ProjectSet) -> PlotOutcome(views, tool_version, message, evidence)`), satisfied by `KicadOracle`; a view is `(name, bytes, sha256)`, and no bytes leave the oracle.
   - The stage reports `render.failed` (warning) for a view that could not be plotted, and never an error. `summary`: `views` (`name`, `bytes`, `sha256`).
   - `check` stays read-only: nothing is written.
   - Rejected: a default stage. It adds a tool run to every check for no verdict.

9. **Tool-backed command examples.** `cli.api.Command` gains `example_tools: tuple[str, ...] = ()`. For a command that names `kicad-cli` there, `tests/consistency/test_cli_consistency.py` and `tests/unit/cli/test_hermetic_examples.py` set `FENOLITE_KICAD_CLI` to a fake built by `tests/_fakecli.py`, extended with `export_files` (the files a fake export or render writes). The example then exits 0 and the mutation example writes its plan in an empty folder, as for any command. A command with `example_tools == ()` must still run with no subprocess.
   - The living requirement "Consistency test covers every command" is not modified: its text names no hermeticity rule; this change ADDs the rule for tool-backed commands.
   - Rejected: a tool-free "export" of something Fenolite writes itself. It would not be the command agents use.

10. **Determinism.** With `--timestamp`, two `export --confirm` runs on an unchanged board give a manifest that differs only in the `sha256` and `bytes` of non-repeatable kinds; `content_sha256`, paths and order are equal. `result` holds no temporary path.

11. **No model change, no FEN code.** `export.*` and `render.*` codes live in `exports.codes.ISSUE_CODES`; `checks.codes.ISSUE_CODES` gains `render.failed`.

## Files and public API

| file | public API |
|---|---|
| `src/fenolite/backends/base.py` (extended) | `PlotView(name, bytes, sha256)`, `PlotOutcome`, `Plotter` |
| `src/fenolite/backends/kicad/cli.py` (extended) | `KicadCli.export(args, board, *, files=None, out) -> CliRun`; `KicadCli.render(board, *, side, width, height, files=None) -> CliRun` |
| `src/fenolite/backends/kicad/oracle.py` (extended) | `KicadOracle.plot(project) -> PlotOutcome` |
| `src/fenolite/exports/__init__.py`, `codes.py` (new) | `EVIDENCE`, `ISSUE_CODES` |
| `src/fenolite/exports/plan.py` (new) | `KINDS`; `Artifact`; `gerber_layers(design) -> tuple[str, ...]`; `run_kind(cli, kind, board, files, *, major) -> KindResult(artifacts, issues, tool_writes)`; `VOLATILE_PREFIXES` |
| `src/fenolite/exports/manifest.py` (new) | `SCHEMA = "fenolite.artifacts.v0"`; `content_sha256(data, kind) -> str`; `build(*, board, tool_version, artifacts, timestamp) -> dict[str, object]`; `dumps(manifest) -> str` |
| `schemas/fenolite.artifacts.v0.json` (new) | the manifest schema |
| `src/fenolite/cli/cmd_export.py`, `cmd_render.py` (new) | `COMMAND`s (`mutates=True`, `example_tools=("kicad-cli",)`) |
| `src/fenolite/cli/api.py` (extended) | `Command.example_tools` |
| `src/fenolite/checks/render.py` (new); `stages.py`, `codes.py` (extended) | `render_stage`; `render` in `STAGE_ORDER`, opt-in; `render.failed` |
| `tests/_fakecli.py` (extended) | `export_files: Mapping[str, Mapping[str, str]]` (per kind: relative name → text) |
| `tests/unit/exports/`, `tests/unit/cli/test_export_cmd.py`, `test_render_cmd.py`, `tests/unit/checks/test_render_stage.py` (new) | hermetic |
| `tests/kicad/export/` (new) | `_exportcases.py`, `test_export_probes.py`, `test_export_oracle.py` |
| `docs/exports.md` (new); `docs/cli-contract.md`; `docs/formats/kicad/cli.md` | user guide and manifest reference; the two command sections; export facts per major |

## Sources registered by this change

None. Rows of other changes cited here: S-0020 (observed `kicad-cli` behaviour), S-0022 and S-0037 (CLI manuals: the export and render commands and their options). Task 1.1 widens S-0020 (file names, date-bearing lines, headless render), S-0022 and S-0037 (the options of Decision 2), only with what each page states. The date-bearing lines are observed facts (S-0020); no format specification is read for them. S-0230 to S-0234 stay unused.

## Hypotheses registered by this change

| id | statement | settling test | criterion |
|---|---|---|---|
| H-K-EXPORT-FILES | With the arguments of Decision 2, `kicad-cli` writes, for a two-copper board: one Gerber per requested layer named `<stem>-<Layer with dots as underscores>.gbr`, `<stem>-PTH.drl` and `<stem>-NPTH.drl`, one position CSV and one IPC-D-356 file (S-0022, S-0037, S-0020) | `tests/kicad/export/test_export_probes.py::test_files` | on 9.0.9 and 10.0.6 for `two_layer.kicad_pcb` and the authored project: the expected names and no other file under the output folders; probes `export-files-gerbers`, `-drill`, `-pos`, `-ipcd356` = `equal` |
| H-K-EXPORT-REPEAT | Two exports of one board differ only in lines carrying the creation date, so `content_sha256` is equal for every file; `pos` and `ipcd356` are byte-equal (S-0020) | `tests/kicad/export/test_export_probes.py::test_repeat` | on both majors: probes `export-repeat-gerbers`, `-drill`, `-pos`, `-ipcd356` = `equal` under `content_sha256`; byte equality recorded per kind in `docs/evidence/kicad-export.md` |
| H-K-EXPORT-RENDER | `pcb render` writes a PNG of the requested size and `pcb export svg` an SVG, headless, on both majors (S-0022, S-0037, S-0020) | `tests/kicad/export/test_export_probes.py::test_render` | on 9.0.9 (pinned image, no display) and 10.0.6: probes `export-render-png` and `export-render-svg` = `present`; a PNG's header gives a width and a height above zero and at most the requested ones. If `png` is `absent` on a major, `render --png` reports `render.failed` there and the row records it |

Ids used without changing their level: `H-K-CHECK-COPYSET`, `H-K-PRO-PRL`, `H-K-WKS-SVG`, `H-K-PCB-POS`, `H-K-CLI-HELP`.

## Evidence level per behaviour (before merge)

| behaviour | level required | proof |
|---|---|---|
| File sets per kind | KICAD-VERIFIED (9.0.x, 10.0.x), `H-K-EXPORT-FILES` | `test_export_probes.py::test_files` |
| Date-stripped equality | KICAD-VERIFIED (9.0.x, 10.0.x), `H-K-EXPORT-REPEAT` | `::test_repeat` |
| Renders | KICAD-VERIFIED where present, `H-K-EXPORT-RENDER` | `::test_render` |
| Manifest, schema, planning | mechanical | `tests/unit/exports` |
| `export`, `render`, read-only source | mechanical with the fake; observed on both majors | `test_export_cmd.py`, `test_export_oracle.py` |
| `render` stage | `exports.EVIDENCE`; never an error | `test_render_stage.py` |

`exports.EVIDENCE` starts `INFERRED` (`H-K-EXPORT-FILES`, `H-K-EXPORT-REPEAT`) and is raised only when both are `KICAD-VERIFIED (9.0.x, 10.0.x)`.

## Budget (5.25 days; the roadmap gives 4.5)

| work | days |
|---|---|
| registers, fact rows | 0.25 |
| probes | 1.0 |
| runner helpers, `exports.plan` | 1.0 |
| manifest and schema | 0.5 |
| `export` command | 0.75 |
| `render` command | 0.5 |
| example tools in the suites | 0.5 |
| `render` stage | 0.25 |
| docs, closing | 0.5 |
| **total** | **5.25** |

Cut order: (1) the `render` stage; (2) `render --png`; (3) `--ipcd356` (c0009 already exports it for tests). Not optional: Gerbers, drill, position, the manifest with both hashes, the proofs on both majors.

## Risks / Trade-offs

- [A date-bearing line this change does not know] → `export-repeat-*` compares two runs on both majors; an unknown differing line fails the probe and joins `VOLATILE_PREFIXES` with its fact row.
- [`pcb render` needs a display in the 9.0.9 image] → the probe decides; `render --png` degrades to a warning there.
- [A fab needs other options] → out of scope; `docs/exports.md` says exactly which options are used.
- [Exporting a board whose fills are stale] → `check`'s `zone.fill` stage (c0015) is the proof; `export` never refills.
- [Backups of many files clutter the folder] → the mutation protocol's `--no-backup`; `docs/exports.md` recommends a fresh `--out`.

## Migration Plan

Additive: a package, two commands, a schema, an opt-in stage and one field on `Command`. To roll back, remove them.

## Open Questions

- **`--manifest` on by default.** Default: opt-in, as the plan writes the loop; c0025's agent guide always passes it.
- **Gerber layer set.** Default: every copper layer, both masks, pastes and silkscreens, and `Edge.Cuts`; courtyard and fabrication layers are left out. To confirm.
- **Should `export` refuse a board that fails `check`?** Default: no; the loop order is the guide, and `export` stays a pure wrapper.
- **PDF.** Default: not in v0.1.
