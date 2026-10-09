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

1. **Job content from the preset.** `outjob.from_preset(preset, *, name, disabled=())` returns the groups: one output group with a folder medium (`fab`) and a PDF medium (`doc`). Outputs: Gerber, NC drill and pick and place bound to `<name>.PcbDoc` and enabled for the folder; bill of materials bound to the project and enabled for the folder; schematic print bound to the project and enabled for the PDF; PCB print bound to the PCB document and enabled for the PDF. A disabled kind is written disabled, not left out, so the user sees it (corrected on 2026-10-06, below).
2. **Only documented settings.** Per-output configuration keys (`Configuration<i>_…`) would be written only for the options that the preset has and the facts page maps. The facts page maps none (cut on 2026-10-06, below), so none is written and Altium's defaults apply. `result.outjob.defaults` lists the preset options that had no mapped key: all that the preset sets.
3. **Project file.** The job is listed as a document of the project, after the PCB document. A project file that exists is not rewritten (c0032's rule); then the build says that the job must be added by hand, with `altium.outjob-not-listed` (info).
4. **Template from the drawing sheet.** `schdot.write_template(sheet, *, width, height, paper)` writes a schematic document without components: the sheet record as a custom sheet of the page's size, the frame and the reference zones as drawn lines and texts, lines and rectangles, texts, and the special strings for title, revision, date, sheet number and count, organisation and the user variables. The neutral text variables map to Altium's special strings by the table that c0046 uses in the other direction; a variable without a special string is written as a parameter reference `=Name`.
5. **Sheet in the build.** With `design.sheet(drawing_sheet=…)`, each `.SchDoc` gets the same graphics as sheet-level records and the title-block values as document parameters (`Title`, `Revision`, …), and no template link, so that the project needs no template file path. `template build --target altium` writes the standalone `.SchDot` for users who want it in their own templates folder.
6. **Loss is reported with c0046's codes.** What the drawing sheet holds and the Altium form cannot carry gives an `altium.sheet.*` code from the same closed table; a loss needs `--allow-lossy`.
7. **Cut order.** First the logo image, then per-output configuration keys, never the job's groups and the template's frame and texts.

## Found on 2026-10-06 (tasks 0.1 to 3.2), and what changed

The proposal was written from a survey. Where it differs from the code and from what public sources hold,
the specs, this design and the tasks were corrected in the same commit:

- **The export preset has no table for a bill of materials, a schematic print or a drawing, and no key that
  enables or disables a kind** (`exports/preset.py`: `gerbers`, `drill`, `pos`; the kinds of an export are
  options of the command). There is also no "preset of the project": `export --preset FILE` names a file.
  So `from_preset(preset, *, name, disabled=())` takes the disabled kinds as an argument, the build takes
  the preset with `--altium-outjob-preset FILE`, and the build enables all six kinds. Whether the preset
  schema should get an `[outputs]` table is a question for the maintainer (below).
- **No public source gives the output type of an assembly drawing.** The two drawings of the corpus jobs
  are outputs of the type `PCBDrawing` that name a drawing document of their own, a non-goal. The sixth
  kind is the PCB print (`PCB Print`, category `Documentation`), which one corpus job binds to a PCB
  document. The kinds are `gerbers`, `drill`, `pos`, `bom`, `schematic_print` and `pcb_print`.
- **The bill of materials is bound to the project, not to the PCB document**: the corpus jobs give it an
  empty or a bracketed document path, never a PCB document.
- **Per-output configuration keys are cut (cut order, second item).** A saved job holds the settings of an
  output as one record of some twenty fields. The facts page can name the fields, but no source says what
  Altium does with a record that holds a few of them, and a Gerber record without its layer list could plot
  nothing. Decision 2 therefore maps no option: `outjob.MAPPED_OPTIONS` is empty, `from_preset` does not
  depend on the options, `layers` left its signature, and `result.outjob.defaults` lists every option the
  preset sets. `H-A-OUTJOB-OPTIONS` is restated: step O4 reads Altium's defaults.
- **Only typed keys are written.** `TargetOutputMedium`, `VariantScope`, the printer keys, `OutputDefault<i>`
  and the keys of `[PublishSettings]` and `[GeneratedFilesSettings]` have no recorded meaning; the two
  sections are written empty, and the containers have a name and a type but no path. The containers are
  named `fab` and `doc`.
- **`backends.altium` may import neither `exports` nor `templates`** (`tests/unit/test_import_graph.py`).
  `outjob.unmapped` reads a preset through a protocol, the options a preset sets are listed without the
  defaults of `exports.preset`, and `schdot` holds its own copy of the repeat rule of `templates.layout`,
  which a unit test compares with `layout`.
- **A drawing sheet has no size; a template has one.** `write_template(sheet, *, width, height, paper, …)`
  takes the page, `template build --target altium` takes `--size` (default: the first listed size), and a
  repeat is written as its copies.
- **The sheet record is a custom sheet of the paper's exact size, without the built-in border.** The
  drawing area of a standard style is smaller than its paper and no source says where it lies, so a style
  cannot hold the positions of the neutral sheet. The frame and the zones are drawn records, because the
  built-in border has equal divisions and a specification has a zone pitch; the margins are the positions
  of the records. "Paper and orientation follow the drawing sheet" therefore means the size of the page.
- **The import is not an exact inverse.** It anchors each item to the nearest corner, expands nothing back
  into a repeat, reads four line widths and whole-point text sizes, and always reports the font name. So
  "equal inside the written scope" is defined by `schdot.written_scope` (positions, texts, justification,
  turns, style, size in points, width code), and the scenarios ask for no warning, not for no issue.
- **The scenario's `${PROJECT_CODE}` is KiCad's form.** The neutral text is `{param:PROJECT_CODE}`.
- **`{paper}` has no special string and both shipped examples use it.** It is written as the paper's name,
  which is exact for a template of one size, and is not a loss.
- **The logo is cut (cut order, first item).** A bitmap gives `altium.sheet.image-not-kept` and needs
  `allow_lossy`. The embedded-file record is a recorded fact; the size an image gets is not kept by the
  import either, so the round trip could not prove it.
- **The layout of a built schematic picks its own sheet size.** When it does not fit the paper of
  `sheet()`, the drawing sheet is drawn on the next ISO paper that holds it, with the new warning
  `altium.sheet-paper`. The layout does not know the title block: this is a documented limit.
- **Part V of `docs/evidence/altium-schematic.md` is the Viewer's.** The output job's part is Part O, with
  the steps O1 to O4; Part W keeps its name.
- **No sheet template is committed.** `tests/residue/test_template_residue.py` (change c0046, "Authored sheet fixtures and corpus rows") refuses every tracked file with the extension `.SchDot`, so that no vendor or company template can enter the repository. The rule looks at tracked files, so a run before staging did not see it, and the first commit of this change held three samples under `tests/data/altium/sheet/`. They were removed: the tests write the templates in memory and in `tmp_path`, and prove them by own readback, by two writes giving equal bytes, by a record census and by a SHA-256 pinned in `test_schdot_write.py`. The sample of the output job stays: the rule names templates only, and the residue and manifest tests pass on it.
- **`build_altium` writes no job by default** (`outjob=False`), so the lens goldens and the scenarios of
  "Altium build outputs" keep their file lists; the default `on` is the command's.
- **`capabilities` is not changed.** The two new write kinds, `altium_outjob` and `altium_schdot`, are rows
  of the evidence matrix; they are not added to the `write_kinds` of an experimental entry, which c0092
  restates.

## Files and public API

- `src/fenolite/backends/altium/outjob.py`: `from_preset`, `unmapped`, `kind_of`, `write_outjob(groups) -> bytes`, `OUTPUT_KINDS`, `MAPPED_OPTIONS`, `OUTJOB_KIND`, `EVIDENCE`.
- `src/fenolite/backends/altium/schdot.py`: `write_template(sheet, *, width, height, paper, form, allow_lossy) -> TemplateWrite`, `sheet_frame(…) -> FrameResult`, `SheetFrame`, `written_scope`, `SPECIAL_STRINGS`, `SCHDOT_KIND`, `EVIDENCE`.
- `src/fenolite/backends/altium/schdoc.py`, `binary.py`, `project.py`, `prjpcb.py`: an optional `frame` (or `frames`) and `outjob` argument; without them the bytes do not change.
- `src/fenolite/lens/altium.py`: `build_altium(…, outjob, outjob_preset, outjob_listed, drawing_sheet, allow_lossy)`, `sheet_page`, `sheet_parameters`, `sheet_frames`, `outjob_summary`; the codes `altium.outjob-not-listed` and `altium.sheet-paper`.
- `src/fenolite/cli/cmd_build.py`: `--altium-outjob`, `--altium-outjob-preset`; `src/fenolite/cli/cmd_template.py`: `--target altium`, `--size`, `--altium-format`.
- Tests: `tests/unit/backends/altium/test_outjob_write.py`, `test_schdot_write.py`, `tests/unit/lens/test_altium_outjob.py`, `test_altium_sheet.py`, `tests/unit/cli/test_template_altium.py`, the shared cases in `tests/_altium_job.py`; one committed sample under `tests/data/altium/outjob/`. No template sample is committed: the templates are written in the tests and their bytes pinned by SHA-256 (below).

## Sources registered by this change

- c0042's rows for output jobs and c0046's rows for sheet templates (registered).
- New: Altium's public documentation of output job files (containers, output kinds and their names) and of schematic templates and special strings (read for facts).
- Public corpus output jobs and templates already in the manifest, for the keys that the writer sets.

No new source was needed (2026-10-06): every fact the two writers use comes from sources that are registered, S-0130, S-0131, S-0187, S-0188, S-0261 to S-0265, S-0293, S-0297 and S-0299, and the block S-0490 to S-0499 reserved for this change stays unused. Sources under a copyleft or an all-rights-reserved licence are read for facts only; nothing is transcribed.

## Hypotheses registered by this change

| id | statement | settling test | criterion |
|---|---|---|---|
| H-A-OUTJOB-READBACK | An output job written from a preset reads back to the groups, media and outputs it was written from | `tests/unit/backends/altium/test_outjob_write.py::test_readback` | equal for the default preset and for three authored presets |
| H-A-OUTJOB-OPEN | Altium opens the written job without a message and lists the outputs with their source documents and containers | author report, Part O steps O1–O2 | the list equals the table sent |
| H-A-OUTJOB-RUN | Generating the folder container produces Gerber, drill, pick-and-place and BOM files, and the PDF container a PDF of the schematic and of the board | author report, Part O step O3 | both containers generate without an error; the file kinds are those of the table |
| H-A-OUTJOB-OPTIONS | An output without configuration keys takes Altium's defaults, and a configuration record with only the mapped fields would set those and keep the defaults of the others | author report, Part O step O4 | the output's setup dialog opens with default values (the second half has no file yet) |
| H-A-SCHDOT-READBACK | A template written from a drawing sheet is imported by `import_sheet` to an equal drawing sheet, inside the written scope | `tests/unit/backends/altium/test_schdot_write.py::test_readback` | equal for the two shipped sheet examples and the authored one |
| H-A-SCHDOT-OPEN | Altium opens the written template and applies it to a sheet; border, zones, lines and texts are where the KiCad sheet of the same specification has them | author report, Part W steps W1–W3 | the printed sheet matches the reference PDF within what the two tools draw |
| H-A-SCHDOT-STRINGS | The written special strings show the document's title, revision, date, sheet number and count | author report, Part W step W4 | each of the five fields shows the value set in the document options |

All start `INFERRED`. No id above is in `docs/hypotheses.md` or in another active change (checked 2026-10-06).

## Author report: Parts O and W, output job and sheet template

Files: the routed blink project with `blink_routed.OutJob`; `iso5457_generic.SchDot` and a one-sheet project that uses the sheet in the build, with the KiCad PDF of the same specification as reference. The steps, the tables and the SHA-256 of the files are in `docs/evidence/altium-schematic.md` (Part V of that page is the Viewer's, so the job's part is Part O).

1. O1: open the project; the Projects panel lists `blink_routed.OutJob`. Open it. Expected: no message.
2. O2: read the outputs, their source documents and which container each is enabled for. Expected: the table sent.
3. O3: generate the folder container, then the PDF container. Expected: no error; report the kinds of files produced (not the files).
4. O4: open the setup of the Gerber and of the NC drill output and read units, format and plotted layers. Expected: Altium's defaults, since the job holds no setting.
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
- Archive order: independent of the other changes of the write part of v0.3; before c0091, whose kit runs the job.

## Risks / Trade-offs

- [Altium needs keys that the corpus files have and the facts page cannot explain] → written only when a public source gives their meaning; otherwise absent, and Part V says whether Altium opens the job without them.
- [The two sheets differ visibly] → the reference is "within what each tool draws"; differences are listed in the page, and the specification is not bent to hide them.
- [An existing project file] → not rewritten; the info issue tells the user.

## Migration Plan

- A build writes one more file, `<name>.OutJob`; `--altium-outjob off` leaves it out. Existing output jobs are never overwritten (the edited-output rule).
- Rollback: the option's default becomes `off`.

## Open Questions

- **Should the job include a STEP export and an ODB++ output?** Default: no, only kinds that `fenolite export` has.
- **Should the export preset get an `[outputs]` table that enables and disables kinds, for `export` and for the job alike?** Default: no; `from_preset` takes `disabled` and the build enables every kind (found on 2026-10-06).
- **Should the two new write kinds be listed by an experimental entry of `capabilities`?** Default: no; they are rows of the evidence matrix, and c0092 restates the entries.
- **Should the build link a template file instead of copying the graphics?** Default: copy, so the project is self-contained.
