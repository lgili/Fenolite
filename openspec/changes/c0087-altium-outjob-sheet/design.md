## Context

- **Read side.** `read_outjob` returns `OutJobFile(ini, version, groups)` with `OutputGroup`, `OutputMedium` and `JobOutput`, byte for byte, from public corpus files; `docs/formats/altium/output-job.md` holds the keys. `import_sheet` turns a `.SchDot` or a `.SchDoc` into a `DrawingSheet` with twelve `altium.sheet.*` codes for what it cannot carry; `docs/formats/altium/sheet-template.md` holds the facts (`H-A-RD-SHT-*`, all `INFERRED`).
- **KiCad side.** `templates.build.build_sheet(spec)` gives a `DrawingSheet`; `design.sheet(drawing_sheet=…)` and `design.title_block(…)` put it on board and schematic; `exports.preset` reads `fenolite.export-preset.v0` with the tables of fab options.
- **What the project plan's sentence means here.** "From the same sheet spec": one `.sheet.toml` gives the KiCad `.kicad_wks` and the Altium `.SchDot`, and the two look alike within what each format draws.
- **Constraints.** The output job is an INI-like text whose unknown keys Altium fills with defaults; only keys whose meaning the facts page records are written. The template is a schematic document, so it uses the writers of c0032/c0033.

## Goals / Non-Goals

**Goals:**
- A built Altium project has a job that produces a fabrication set with two clicks, set up as the project's preset says.
- One sheet specification serves both targets.
- Both files are proved by the readers that were proved on public files.

**Non-Goals:**
- Everything under "Non-goals" in the proposal.

## Decisions

1. **Job content from the preset.** `outjob.from_preset(preset, *, name, layers)` returns the groups: one output group with a folder medium (`fab/`) and a PDF medium (`doc/`). Outputs: Gerber and NC drill bound to `<name>.PcbDoc` and enabled for the folder; pick and place and bill of materials likewise; schematic print bound to the project and enabled for the PDF; assembly drawing bound to the PCB document and enabled for the PDF. A kind the preset disables is written disabled, not left out, so the user sees it.
2. **Only documented settings.** Per-output configuration keys (`Configuration<i>_…`) are written only for the options that the preset has and the facts page maps (units, format digits, layers plotted, drill origin). Everything else is absent, and Altium's defaults apply. `result.outjob.defaults` lists the preset options that had no mapped key.
3. **Project file.** The job is listed as a document of the project, after the PCB document. A project file that exists is not rewritten (c0032's rule); then the build says that the job must be added by hand, with `altium.outjob-not-listed` (info).
4. **Template from the drawing sheet.** `schdot.write_template(sheet)` writes a schematic document without components: the sheet record with paper or custom size and margins, border and reference zones where the specification has them, lines and rectangles, texts, and the special strings for title, revision, date, sheet number and count, organisation and the user variables. The neutral text variables map to Altium's special strings by the table that c0046 uses in the other direction; a variable without a special string is written as a parameter reference `=Name`.
5. **Sheet in the build.** With `design.sheet(drawing_sheet=…)`, each `.SchDoc` gets the same graphics as sheet-level records and the title-block values as document parameters (`Title`, `Revision`, …), and no template link, so that the project needs no template file path. `template build --target altium` writes the standalone `.SchDot` for users who want it in their own templates folder.
6. **Loss is reported with c0046's codes.** What the drawing sheet holds and the Altium form cannot carry gives an `altium.sheet.*` code from the same closed table; a loss needs `--allow-lossy`.
7. **Cut order.** First the logo image, then per-output configuration keys, never the job's groups and the template's frame and texts.

## Files and public API

- `src/fenolite/backends/altium/outjob.py`: `from_preset`, `write_outjob(groups) -> bytes`, `OUTPUT_KINDS`, `EVIDENCE`.
- `src/fenolite/backends/altium/schdot.py`: `write_template(sheet, *, form) -> bytes`, `sheet_records(sheet)`, `SPECIAL_STRINGS`, `EVIDENCE`.
- `src/fenolite/cli/cmd_template.py`: `--target altium`, `--altium-format`.
- Tests: `tests/unit/backends/altium/test_outjob_write.py`, `test_schdot_write.py`, `tests/unit/lens/test_altium_outjob.py`, `test_altium_sheet.py`, `tests/unit/cli/test_template_altium.py`; committed samples under `tests/data/altium/outjob/` and `tests/data/altium/sheet/`.

## Sources registered by this change

- c0042's rows for output jobs and c0046's rows for sheet templates (registered).
- New: Altium's public documentation of output job files (containers, output kinds and their names) and of schematic templates and special strings (read for facts).
- Public corpus output jobs and templates already in the manifest, for the keys that the writer sets.

Each new source gets the next free `S-` number in `docs/evidence/sources.md` when its task runs (numbers are not reserved here, because changes that run in parallel would collide), with its licence and what was read. Sources under a copyleft or an all-rights-reserved licence are read for facts only; nothing is transcribed.

## Hypotheses registered by this change

| id | statement | settling test | criterion |
|---|---|---|---|
| H-A-OUTJOB-READBACK | An output job written from a preset reads back to the groups, media and outputs it was written from | `tests/unit/backends/altium/test_outjob_write.py::test_readback` | equal for the default preset and for three authored presets |
| H-A-OUTJOB-OPEN | Altium opens the written job without a message and lists the outputs with their source documents and containers | author report, Part V steps V1–V2 | the list equals the table sent |
| H-A-OUTJOB-RUN | Generating the folder container produces Gerber, drill, pick-and-place and BOM files, and the PDF container a schematic PDF | author report, Part V step V3 | both containers generate without an error; the file kinds are those of the table |
| H-A-OUTJOB-OPTIONS | The mapped configuration keys set the options they are mapped to (units, digits, plotted layers) | author report, Part V step V4 | the output's setup dialog shows the preset's values |
| H-A-SCHDOT-READBACK | A template written from a drawing sheet is imported by `import_sheet` to an equal drawing sheet, inside the written scope | `tests/unit/backends/altium/test_schdot_write.py::test_readback` | equal for the two shipped sheet examples and the authored one |
| H-A-SCHDOT-OPEN | Altium opens the written template and applies it to a sheet; border, zones, lines and texts are where the KiCad sheet of the same specification has them | author report, Part W steps W1–W3 | the printed sheet matches the reference PDF within what the two tools draw |
| H-A-SCHDOT-STRINGS | The written special strings show the document's title, revision, date, sheet number and count | author report, Part W step W4 | each of the five fields shows the value set in the document options |

All start `INFERRED`. No id above is in `docs/hypotheses.md` or in another active change (checked 2026-10-06).

## Author report: Parts V and W, output job and sheet template

Files: the routed blink project with `blink.OutJob`; `iso5457_generic.SchDot` and a one-sheet project that uses the sheet in the build, with the KiCad PDF of the same specification as reference.

1. V1: open the project; the Projects panel lists `blink.OutJob`. Open it. Expected: no message.
2. V2: read the outputs, their source documents and which container each is enabled for. Expected: the table sent.
3. V3: generate the folder container, then the PDF container. Expected: no error; report the kinds of files produced (not the files).
4. V4: open the setup of the Gerber and of the NC drill output and read units, format and plotted layers. Expected: the table.
5. W1: open `iso5457_generic.SchDot`. Expected: no message; a frame with a title block.
6. W2: in a new schematic, set the template to that file (Design » Sheet Templates). Expected: the frame appears.
7. W3: print the sheet of the one-sheet project to PDF and compare it with the reference PDF: frame, zones, title-block lines and labels. Report the differences in one sentence each.
8. W4: set title, revision and date in the document options and read the five fields of the title block. Expected: the values set, and sheet 1 of 1.

The maintainer reports one generic outcome per step (`as expected`, or what differed in one sentence), the tool as `AD <major>.<minor>` and the date. No file that Altium wrote is committed. A step that fails refutes the row it names: the row keeps its id and gets a registered successor (`verification-evidence`, "Refuted rows keep their id"). An author report never moves an operation out of `experimental` ("Author reports never promote an operation").

## Size (design-days)

| group | dd |
|---|---|
| entry, facts and sources | 0.75 |
| output job writer | 1.5 |
| job in the build and the project file | 0.75 |
| template writer | 1.75 |
| sheet in the build, template command | 1 |
| samples, reports, docs | 1 |
| closing | 0.25 |

Total: 7. This is a size, not a calendar estimate.

## Spec deltas and archive order

- `altium-build`, "Altium build outputs": the file list grows by the job (MODIFIED at task 0.1).
- `sheet-templates`, "Template build command": the target `altium` (MODIFIED at task 0.1).
- Archive order: independent of the other v0.4 changes; before c0091, whose kit runs the job.

## Risks / Trade-offs

- [Altium needs keys that the corpus files have and the facts page cannot explain] → written only when a public source gives their meaning; otherwise absent, and Part V says whether Altium opens the job without them.
- [The two sheets differ visibly] → the reference is "within what each tool draws"; differences are listed in the page, and the specification is not bent to hide them.
- [An existing project file] → not rewritten; the info issue tells the user.

## Migration Plan

- A build writes one more file, `<name>.OutJob`; `--altium-outjob off` leaves it out. Existing output jobs are never overwritten (the edited-output rule).
- Rollback: the option's default becomes `off`.

## Open Questions

- **Should the job include a STEP export and an ODB++ output?** Default: no, only kinds that `fenolite export` has.
- **Should the build link a template file instead of copying the graphics?** Default: copy, so the project is self-contained.
