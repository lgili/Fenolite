## MODIFIED Requirements

### Requirement: Altium build outputs
`lens.altium.build_altium(design, *, name, placed=(), placements=None, project_exists=False, form=DEFAULT_FORM, resolver=None, sheets=DEFAULT_SHEETS, outjob=False, outjob_preset=None, outjob_listed=False, drawing_sheet=None, allow_lossy=False) -> BuildOutput` SHALL return every file of an Altium project for `design` as bytes, and SHALL return no file when any issue has severity `error`. `BuildOutput` is c0011's `lens.build.BuildOutput`.
- The steps MUST run in this order: the build checks of "Altium build issue codes" and "Hierarchy issue codes"; the symbol of every lib id and the pins of every component ("Altium symbol sources": generic pins for Altium links, the symbol's pins for KiCad lib ids) set as `Component.pins`; `Design.validate()`; the footprint of every footprint link, its checks and `lens.altium.pad_extras` ("Altium footprint sources", "PCB library outputs"); the PCB document's conditions and placements ("PCB document output"); `backends.altium.project.write_project(model, name=name, project=not project_exists, issues=…, form=form, symbols=…, footprints=…, pcb=…, sheets=sheets, outjob=…, frames=…)`, where `footprints` are the `pcblib.LibFootprint` values to write, `pcb` is a `pcbdoc.PcbDocSpec` or `None`, `outjob` is the bytes of the output job or `None` ("Output job in an Altium build") and `frames` maps a sheet file to its `schdot.SheetFrame` ("Drawing sheet in an Altium build"); the `.fenolite/` texts and record; evidence.
- An issue of severity `error` before the writer MUST give a `BuildOutput` with its issues and empty `files`.
- The layout MUST be `<name>.PrjPcb` (only when `project_exists` is false), `<name>.SchDoc`, every planned `<library>.SchLib` ("Schematic library outputs"), `<name>.PcbLib` when it holds a footprint ("PCB library outputs"), `<name>.PcbDoc` when its conditions hold ("PCB document output"), `<name>.OutJob` when `outjob` is true and the PCB document is written ("Output job in an Altium build"), with `sheets="modules"` one `<name>_<module>.SchDoc` per top-level module and the planned `.Harness` files ("Module sheets in an Altium build"), the six layer files under `.fenolite/` and `.fenolite/build.json`, with the design name as stem.
- The layer texts MUST come from `canonical.dump_texts` of the model with its pins and rewritten net members, with an empty `findings.json`.
- `.fenolite/build.json` MUST be `{"design": <name>, "files": {<path>: <sha256>, …}, "schema": "fenolite.build-record.v0", "target": "altium"}` with sorted keys, no date and a final newline, and MUST record the SHA-256 of every planned file outside `.fenolite/`.
- The build MUST NOT write a project structure file, a date or an absolute path, and MUST NOT write a PCB library or PCB document other than these two. With `outjob` false and `drawing_sheet` `None`, every file MUST hold the bytes it held before change c0087.
- `summary` MUST hold `components`, `nets`, `labels`, `power_ports`, `sheet`, `schematic_format`, `libraries`, `symbols`, `footprints`, `pcb_document`, `sheet_mode`, `sheets`, `ports`, `sheet_entries`, `harnesses`, `outjob` (`None` without a job), `drawing_sheet` (`None` without one), `kept` (paths relative to `--out`) and `experimental`, which `cmd_build` copies into `result`, with `kept` under `--out`.

#### Scenario: Files of the sample
- **WHEN** `build_altium` runs on the model of `examples/altium_sample/design.py` with `project_exists=False`
- **THEN** `files` holds exactly `altium_sample.PrjPcb`, `altium_sample.SchDoc`, `FenoliteSample.SchLib`, the six layer files under `.fenolite/` and `.fenolite/build.json`, with no `.PcbLib` or `.PcbDoc`, and `issues` holds no issue of severity `warning` or `error`

#### Scenario: Build record
- **WHEN** `.fenolite/build.json` of the sample build is read
- **THEN** its `schema` is `fenolite.build-record.v0`, its `target` is `altium`, it holds no date, and it maps `altium_sample.PrjPcb`, `altium_sample.SchDoc` and `FenoliteSample.SchLib` to their SHA-256

#### Scenario: Generic pins in the layer files
- **WHEN** `.fenolite/circuit.json` of the sample build is loaded with `canonical.load_dir`
- **THEN** the component `power/U1` has the pins `1`, `2` and `3`, each with its name equal to its number and type `passive`

#### Scenario: Errors produce no files
- **GIVEN** a sample variant whose `J1` has `lib_id="HDR2"`
- **WHEN** `build_altium` runs
- **THEN** `files` is empty and `issues` holds `altium.lib-id-form` naming `J1`

#### Scenario: Files of the KiCad-footprint sample
- **WHEN** `build_altium` runs on the model of `examples/blink_2layer/design.py` with its placements, `project_exists=False` and a resolver of the example's tables
- **THEN** `files` holds exactly `blink.PrjPcb`, `blink.SchDoc`, `blink.SchLib`, `blink.PcbLib`, `blink.PcbDoc`, the six layer files under `.fenolite/` and `.fenolite/build.json`, and `.fenolite/build.json` maps the five project files to their SHA-256

#### Scenario: Files of the hierarchy sample
- **WHEN** `build_altium` runs on the model of `examples/altium_hier/design.py` with `project_exists=False` and `sheets="modules"`
- **THEN** `files` holds exactly `altium_hier.PrjPcb`, `altium_hier.SchDoc`, `altium_hier_flash.SchDoc`, `altium_hier_mcu.SchDoc`, `altium_hier_flash.Harness`, `altium_hier_mcu.Harness`, `FenoliteHier.SchLib`, the six layer files under `.fenolite/` and `.fenolite/build.json`, and `.fenolite/build.json` maps the seven project files to their SHA-256

#### Scenario: Flat build of the hierarchy sample
- **WHEN** `build_altium` runs on the same model with the default `sheets`
- **THEN** `files` holds `altium_hier.SchDoc` and no other `.SchDoc` or `.Harness` file, and `summary["sheet_mode"]` is `flat`

#### Scenario: Files of the sample with a job
- **WHEN** `build_altium` runs on the model of `examples/blink_2layer/design.py` with its placements, a resolver of the example's tables and `outjob=True`
- **THEN** `files` holds the files of "Files of the KiCad-footprint sample" and `blink.OutJob`, and `.fenolite/build.json` maps the six project files to their SHA-256

## ADDED Requirements

### Requirement: Output job in an Altium build
`fenolite build --target altium` SHALL write `<name>.OutJob` with `backends.altium.outjob.write_outjob(from_preset(preset, name=<name>))` when the build writes a PCB document, and SHALL list it in the project file it writes, as the document after the PCB document.
- `--altium-outjob on|off` (default `on`) MUST select it, and `--altium-outjob-preset FILE` MUST name the export preset (`fenolite.export-preset.v0`, the file that `fenolite export --preset` reads); without it the preset is the default one. Both options MUST be a usage error (exit 2, `FEN-2001`) with `--target kicad`, and `--altium-outjob-preset` MUST be one with `--altium-outjob off`. A preset that cannot be read or is malformed MUST fail as it does for `export`.
- A build that writes no PCB document MUST write no output job, and `result.outjob` MUST be `null`.
- An output job that exists and differs from the one the build would write MUST be refused as an edited output, by the rule of every other planned file.
- When the project file exists and does not list `<name>.OutJob`, the build MUST report `altium.outjob-not-listed` (info) and MUST NOT rewrite the project file. A kept project file that lists it MUST give no such issue.
- `result.outjob` MUST hold `file` (under `--out`), `preset` (`null`, or the file as given and its SHA-256), `media` (name and type of each container), `outputs` (per output its `kind`, `type`, `name`, `category`, `document`, `enabled` and the name of its container, in the order of `OUTPUT_KINDS`) and `defaults`: the options that the preset sets and the writer has no key for, as sorted `table.key` texts.
- The evidence of a build with a job MUST name `H-A-OUTJOB-READBACK`, `H-A-OUTJOB-OPEN` and `H-A-OUTJOB-RUN`, and the level stays `INFERRED`.

#### Scenario: Job beside the board
- **WHEN** the routed blink is built for Altium into an empty folder
- **THEN** `blink.OutJob` is written, `blink.PrjPcb` lists it after `blink.PcbDoc`, `result.outjob.outputs` holds six entries, all enabled, and `result.outjob.defaults` is empty

#### Scenario: Turned off
- **WHEN** the same build runs with `--altium-outjob off`
- **THEN** no output job is written, `result.outjob` is `null`, and every other file holds the bytes it held before change c0087

#### Scenario: A preset names what the job does not set
- **GIVEN** a preset file with `[drill]` `units = "in"`
- **WHEN** the build runs with `--altium-outjob-preset` naming it
- **THEN** `result.outjob.defaults` is `["drill.units"]` and `result.outjob.preset.sha256` is the SHA-256 of the file

#### Scenario: Kept project file
- **GIVEN** a folder that holds the `blink.PrjPcb` of a build made with `--altium-outjob off`
- **WHEN** the build runs again with the job
- **THEN** `blink.PrjPcb` keeps its bytes and `altium.outjob-not-listed` is reported

### Requirement: Drawing sheet in an Altium build
When the script names a drawing sheet with `design.sheet(drawing_sheet=…)`, `fenolite build --target altium` SHALL draw it on every schematic document it writes, with `schdot.sheet_frame`, and SHALL write the title-block values of `design.title_block(…)` as sheet parameters.
- The sheet record MUST be a custom sheet of the exact size of the page: the paper and the orientation of `design.sheet()` when the layout of the document fits it, otherwise the smallest of A4, A3, A2, A1 and A0 in that orientation that holds the layout, otherwise the layout's own area. A page other than the paper of `sheet()` MUST give `altium.sheet-paper` (warning) naming the document and both sizes. The built-in border MUST be off.
- The graphics MUST be root records after every other record of the document, so that no owner index of the document changes, and the sheet parameters MUST follow them: `Title`, `Revision`, `Date`, `Organization`, `DocumentNumber`, `DrawnBy` and `ApprovedBy` for the fields of the title block that are not empty, `SheetNumber` and `SheetTotal` (the position of the document among the schematic documents of the build, from 1, and their count), and each variable of the title block under its own name, in code-point order. A value that a record cannot hold MUST give `altium.text-unwritable` (error).
- A part of the drawing sheet that the Altium form cannot carry MUST give its `altium.sheet.*` code ("Altium sheet template writing"); a loss MUST need `--allow-lossy`, and without it the build MUST fail with `FEN-7001` and write nothing.
- `result.drawing_sheet` MUST hold `source` (the path as written in the script), `items` and `pages`: per schematic document its paper name, width and height (nm).
- A script without a drawing sheet MUST give the schematic it gave before this change, byte for byte.
- The evidence of such a build MUST name `H-A-SCHDOT-READBACK`, `H-A-SCHDOT-OPEN` and `H-A-SCHDOT-STRINGS`.

#### Scenario: Frame on the sheet
- **GIVEN** the blink script with `design.sheet("A4", drawing_sheet="frames/generic.sheet.toml")` and `design.title_block(title="Blink", revision="B")`
- **WHEN** it is built for Altium and the schematic is read back
- **THEN** `import_sheet` of the document, with `allow_lossy`, gives a drawing sheet equal to that of the specification inside the written scope on an A4 landscape page, and the sheet parameters hold `Title` = `Blink`, `Revision` = `B`, `SheetNumber` = `1` and `SheetTotal` = `1`

#### Scenario: No drawing sheet
- **WHEN** the unchanged blink script is built for Altium
- **THEN** `blink.SchDoc` holds the bytes it held before change c0087 and `result.drawing_sheet` is `null`
