## MODIFIED Requirements

### Requirement: Altium build outputs
`lens.altium.build_altium(design, *, name, placed=(), placements=None, project_exists=False, form=DEFAULT_FORM, resolver=None, sheets=DEFAULT_SHEETS, outjob=False, outjob_preset=None, outjob_listed=False, drawing_sheet=None, allow_lossy=False) -> BuildOutput` SHALL return every file of an Altium project for `design` as bytes, and SHALL return no file when any issue has severity `error`. `BuildOutput` is c0011's `lens.build.BuildOutput`.
- The steps MUST run in this order: the build checks of "Altium build issue codes" and "Hierarchy issue codes"; the symbol of every lib id and the pins of every component ("Altium symbol sources": generic pins for Altium links, the symbol's pins for KiCad lib ids) set as `Component.pins`; `Design.validate()`; the footprint of every footprint link, its checks and `lens.altium.pad_extras` ("Altium footprint sources", "PCB library outputs"); the PCB document's conditions and placements ("PCB document output"); `backends.altium.project.write_project(model, name=name, project=not project_exists, issues=…, form=form, symbols=…, footprints=…, pcb=…, sheets=sheets, outjob=…, frames=…)`, where `footprints` are the `pcblib.LibFootprint` values to write, `pcb` is a `pcbdoc.PcbDocSpec` or `None`, `outjob` is the bytes of the output job or `None` ("Output job in an Altium build") and `frames` maps a sheet file to its `schdot.SheetFrame` ("Drawing sheet in an Altium build"); the `.fenolite/` texts and record; evidence.
- An issue of severity `error` before the writer MUST give a `BuildOutput` with its issues and empty `files`.
- The layout MUST be `<name>.PrjPcb` (only when `project_exists` is false), `<name>.SchDoc`, every planned `<library>.SchLib` ("Schematic library outputs"), `<name>.PcbLib` when it holds a footprint ("PCB library outputs"), `<name>.PcbDoc` when its conditions hold ("PCB document output"), `<name>.OutJob` when `outjob` is true and the PCB document is written ("Output job in an Altium build"), with `sheets="modules"` one `<name>_<module>.SchDoc` per top-level module and the planned `.Harness` files ("Module sheets in an Altium build"), the six layer files under `.fenolite/` and `.fenolite/build.json`, with the design name as stem.
- The layer texts MUST come from `canonical.dump_texts` of the model with its pins and rewritten net members, with an empty `findings.json`. When the build writes a PCB document, the board of that model is the board that was written ("Stored board of an Altium build"); `BuildOutput.design` stays the model of the script, and `BuildOutput.layout` is the stored model.
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

## ADDED Requirements

### Requirement: Stored board of an Altium build
An Altium build that writes a PCB document SHALL store in `.fenolite/board.json` the board that it wrote: `backends.altium.lower.stored_board(model, spec)` gives the board of the script's model with one `FootprintInstance` per placed component and the copper of the document, in the frame of the script.
- A footprint MUST hold the component's id, the footprint link, the placement (position, rotation, side, locked) and the pads that the document holds, in the footprint frame of the model: the position is the written position taken back through the placement without a mirror, the angle is relative to the footprint, the layers are those the pad lies on (a pad of a bottom-side component names the bottom layers), and `net_id` is the id of the net of the design. A pad keeps the extension bag of its library definition, so that a later write knows the corner ratio of a rounded rectangle.
- The tracks, arcs and vias MUST be those of the document with the net ids of the design. A zone MUST be one entity per written polygon (a zone on two layers is two), without fills.
- The outline, the layers, the stack-up, the texts, graphics, keep-outs, holes, the drawing sheet reference and the title block of the script's board MUST be kept as they are.
- Ids MUST be derived from the component's id and the entity's place, so two builds of one script store equal texts.
- A build that writes no PCB document MUST store the script's board unchanged. No project file of a build changes: the committed samples keep their bytes.
- The build does not go through `lower.from_design`: it writes library footprints with their graphics, pad settings and texts, which a footprint instance of the model does not hold, so a lowering from the model alone could not give the bytes of the committed samples.

#### Scenario: Stored board of the routed blink
- **WHEN** `uv run pytest tests/unit/backends/altium/test_lower.py -k build_agrees` builds `examples/blink_routed/design.py` and loads `.fenolite/`
- **THEN** the stored board holds the footprints and the tracks of the PCB document, and the samples under `tests/data/altium/` keep their bytes (`uv run pytest tests/unit/lens -k "altium and (samples or golden)"`)
