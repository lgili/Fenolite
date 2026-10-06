## Why

Two files of an Altium project are still only read: the output job and the sheet template. A user who builds for Altium gets a project without a way to produce fabrication data from it except by setting up every output by hand, and a schematic on a blank A4 sheet whatever `design.sheet()` says.

For KiCad both exist: `export` with a preset (c0030, c0074) and the drawing sheet from a `.sheet.toml` (c0012, c0074). The roadmap lists for v0.4 "Project-file and output-job writers" and "Sheet templates for the second backend, from the same sheet spec as c0012". The project-file writer exists since c0032; this change adds the two others and the project keys that list them.

## What Changes

- **Output job.** `build --target altium` writes `<name>.OutJob` with one container per kind of output that the export preset of the project selects (Gerber, NC drill, pick and place, bill of materials, schematic PDF, assembly drawing), each bound to its source document, and lists the job in the project file.
- **Sheet template.** `fenolite template build … --target altium` writes a `.SchDot` from a `.sheet.toml`: paper, margins, border and zones, title-block lines and texts, special strings, and an optional logo. The build writes the same sheet into each `.SchDoc` when `design.sheet()` names a drawing sheet, with the title-block values as document parameters.
- **Round trip without Altium.** A written `.SchDot` is read by `import_sheet` (c0046) back to the drawing sheet it was written from; a written `.OutJob` is read by `read_outjob` (c0042) to the groups it was written from.

Size: 7 design-days (a size, not time); cut order in the design.

## Capabilities

### New Capabilities
None.

### Modified Capabilities
- `altium-build`: ADDED "Output job in an Altium build", "Drawing sheet in an Altium build".
- `altium-project-reader`: ADDED "Output job written".
- `sheet-templates`: ADDED "Altium sheet template writing", "Template build for Altium".

## Non-goals

- Fenolite does not run an output job and does not produce Altium's outputs: the job is a file for the user to run in Altium. Fenolite's own fabrication exports stay those of `fenolite export` on the KiCad target.
- No Draftsman documents, no PCB print templates, no release configurations of a managed project.
- No sheet template for the PCB document (title blocks on mechanical layers are board graphics, which c0085 writes when the script draws them).
- No output settings beyond those the preset of c0074 has and Altium's output has in the same meaning; every other setting keeps Altium's default.
- No code or constant from any private project or organisation; test data is authored for Fenolite or fetched from the public rows of the corpus manifest.
- No format fact from a decompiled tool or a transcribed parser: every fact gets a row in `docs/formats/altium/*.md` with a public source of `docs/evidence/sources.md` and a label.

## Evidence level required

- Own readback of both files: `INFERRED` under `H-A-OUTJOB-READBACK` and `H-A-SCHDOT-READBACK`.
- That Altium opens the job, lists the outputs and generates them, and that it opens the template and fills the special strings: `INFERRED` until Part V and Part W are reported.
- The KiCad drawing sheet built from the same `.sheet.toml` is the visual reference of Part W; no evidence level follows from it.

## Impact

- New: `backends/altium/outjob.py`, `backends/altium/schdot.py`; changed `read/outjob.py` (shared names), `prjpcb.py`, `schdoc.py`, `lens/altium.py`, `templates/build.py`, `cli/cmd_template.py`.
- Pages: `docs/altium.md` ("Output job", "Drawing sheet"), `docs/sheet-templates.md`, `docs/formats/altium/{output-job,sheet-template,project}.md`, `docs/evidence/altium-schematic.md`.
- Depends on: c0032 (project file), c0042 (output job read), c0046 (sheet template read), c0012 and c0074 (sheet spec, preset, `design.sheet()`). Nothing else of v0.4.
