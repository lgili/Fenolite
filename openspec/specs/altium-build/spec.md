# altium-build Specification

## Purpose
Build a design script into an experimental Altium project with `fenolite build --target altium`: which files are written, the issues the build reports, when an edited output is refused, how builds stay reproducible, and the evidence the outputs carry. The committed samples and the protocol of the maintainer's author reports belong here; the bytes of each file belong to the writer capabilities.

## Requirements

### Requirement: Altium build target
`fenolite build DESIGN.py --out DIR --target altium` SHALL build the design into an experimental Altium project instead of a KiCad project. This requirement adds the option `--target` to the `design-dsl` requirement "Build command", whose rules hold unchanged for `--target kicad`, the default.
- `--target` MUST accept `kicad` and `altium`. Any other value MUST be a usage error (exit 2, `FEN-2001`).
- With `--target altium`, `cmd_build` MUST run the script, convert it with `to_model` and `placements` (a `DslError` of either becoming `DesignScriptError`, `FEN-3004`, as for KiCad), build it with `lens.altium.build_altium(model, name=<design name>, placed=<placed component paths>, placements=<placements>, project_exists=<DIR/<name>.PrjPcb is a file>, form=<form>, resolver=<resolver>)`, where `<placements>` is the mapping that `placements` returned and `<resolver>` is a `LibraryResolver` built as for `--target kicad` (`LibraryConfig(target_major=<--kicad-version>, project_dir=<the script's folder>)`) when `lens.altium.kicad_lib_ids(model)` or `lens.altium.kicad_footprint_ids(model)` is not empty, and `None` otherwise, read the record once with `lens.build.read_record(DIR)`, call `lens.build.check_existing` with every planned file before it returns the plan, and return every file of the `BuildOutput` as a planned write under `DIR`, sorted by path.
- It MUST read only the symbol libraries of KiCad lib ids and the footprint libraries of KiCad footprint links, through that resolver (`altium-build`, "Altium symbol sources" and "Altium footprint sources"). It MUST NOT parse an Altium file or start an external tool. `check_existing` only compares the bytes and hashes of existing outputs.
- The `--out` rule, `input`, `script_output`, the mutation protocol, `--seed`, `--timestamp`, `--no-backup` and `--discard-layout` MUST behave as for `--target kicad`. `--kicad-version` MUST change planned bytes only through the library configuration it selects for KiCad lib ids, and `--allow-lossy` MUST NOT change any planned byte.
- `result` MUST hold `design` (the name), `target` (the string `altium`), `out`, `files` (the planned paths), `components`, `nets`, `labels` and `power_ports` (counts), `sheet` (the sheet size name, or `custom`), `schematic_format`, `libraries` (the planned library paths, `.SchLib` and `.PcbLib`), `symbols` (the number of library components), `footprints` (the number of footprints in the planned `.PcbLib`, 0 when none), `pcb_document` (the planned `.PcbDoc` path, or `null`), `kept` (output paths that exist and are not planned), `experimental` (`true`) and `script_output`, plus the dispatcher's `plan`.
- Planned writes MUST have the kinds `altium_prjpcb`, `altium_schdoc_binary` or `altium_schdoc_ascii` (c0033), `altium_schlib`, `altium_pcblib`, `altium_pcbdoc` and `fenolite` (files under `.fenolite/`).

#### Scenario: Dry run of the sample
- **GIVEN** an empty folder `B`
- **WHEN** `fenolite build examples/altium_sample/design.py --out B --target altium --dry-run --json` runs
- **THEN** the exit code is 0, `result.plan` lists `B/altium_sample.PrjPcb`, `B/altium_sample.SchDoc`, `B/FenoliteSample.SchLib` and seven files under `B/.fenolite/`, and no `.PcbLib` or `.PcbDoc`, `result.footprints` is `0`, `result.pcb_document` is `null`, `result.target` is `altium`, `result.experimental` is `true`, and `B` is still empty

#### Scenario: Confirmed build
- **WHEN** the same command runs with `--confirm` instead of `--dry-run`
- **THEN** the exit code is 0 and `receipt.written` lists the ten planned files with their SHA-256

#### Scenario: Unknown target
- **WHEN** `fenolite build examples/altium_sample/design.py --out B --target eagle --dry-run` runs
- **THEN** the exit code is 2, stderr carries `FEN-2001`, and nothing is written

#### Scenario: Default target unchanged
- **WHEN** `fenolite build examples/blink_2layer/design.py --out B --dry-run --json` runs with and without `--target kicad`
- **THEN** both `result` objects are equal, `result.target` is `10`, and no planned path ends in `.SchDoc` or `.PrjPcb`

#### Scenario: No library is read
- **GIVEN** `KICAD_CONFIG_HOME` set to an empty folder and the sample, whose libraries exist nowhere on the machine
- **WHEN** it is built with `--target altium --dry-run --json`
- **THEN** the exit code is 0, no resolver is built, and no issue code starts with `kicad.lib.` or is `altium.footprint-unresolved`

#### Scenario: Dry run with KiCad footprints
- **GIVEN** `KICAD_CONFIG_HOME` set to an empty folder and an empty folder `B`
- **WHEN** `fenolite build examples/blink_2layer/design.py --out B --target altium --dry-run --json` runs
- **THEN** the exit code is 0, `result.plan` lists `B/blink.PrjPcb`, `B/blink.SchDoc`, `B/blink.SchLib`, `B/blink.PcbLib` with the kind `altium_pcblib` and `B/blink.PcbDoc` with the kind `altium_pcbdoc`, `result.footprints` is `3`, `result.pcb_document` is `B/blink.PcbDoc`, and `B` is still empty

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

### Requirement: Altium build issue codes
The Altium build SHALL report its own findings only with the codes of the closed table `lens.altium.ALTIUM_ISSUE_CODES`. The codes of `Design.validate()` (`model.*`) and the `build.layout-exists` issues of `LayoutExistsError` MUST pass through unchanged.

| code | severity | when |
|---|---|---|
| `altium.lib-id-form` | error | a `lib_id` is not `<library>:<name>` with both parts non-empty |
| `altium.footprint-form` | error | a non-empty `footprint` is not `<library>:<name>` with both parts non-empty |
| `altium.text-unwritable` | error | `text_problem` refuses a written text: a character outside printable 7-bit ASCII, the vertical bar, an empty text, a leading or trailing space, or a comment that starts with `=` (`altium-schematic-writer`, "Text the ASCII form cannot carry") |
| `altium.name-case-collision` | error | two net names, or two refs, differ only in letter case |
| `altium.unique-id-collision` | error | two components get the same unique id |
| `altium.no-footprint` | warning | a part names no footprint, so the engineering change order cannot place it |
| `altium.sheet-custom` | warning | the layout does not fit the largest standard sheet, and a custom sheet size is written |
| `altium.generic-symbols` | info | the components got generic bodies; the message names the count and the Altium command that replaces them |
| `altium.not-lowered` | info | a design item has no place in the written files: the board, placements, net classes or diff pairs; one issue per kind, naming the items |
| `altium.project-kept` | info | `<name>.PrjPcb` exists in `--out` and is kept |

- A build with an issue of severity `error` MUST exit 5 and write nothing.

#### Scenario: Closed set enforced
- **WHEN** `uv run pytest tests/unit/lens/test_altium_issues.py -k closed_set` collects every issue code produced by the Altium build tests
- **THEN** each code other than `model.*` and `build.layout-exists` is a key of `ALTIUM_ISSUE_CODES` with the severity of this table, and every key of the table is produced by at least one test

#### Scenario: Malformed lib id writes nothing
- **GIVEN** a sample variant whose `J1` has `lib_id="HDR2"`, in a folder `V`
- **WHEN** `fenolite build V/design.py --out B --target altium --confirm --json` runs
- **THEN** the exit code is 5, `issues` holds `altium.lib-id-form`, and `B` holds no file

#### Scenario: Items not lowered are reported, not refused
- **GIVEN** a sample variant with `design.board(mm(50), mm(30))`, one placed part and one net class
- **WHEN** it is built with `--target altium --confirm`
- **THEN** the exit code is 0 and `issues` holds three `altium.not-lowered` infos, for the board, the placements and the net class

### Requirement: Edited Altium outputs are not overwritten
The Altium build SHALL apply the rule of the `design-dsl` requirement "Edited outputs are not overwritten" to every planned file outside `.fenolite/`: a file changed since Fenolite last wrote it is refused with `LayoutExistsError` (`FEN-7001`, exit 7, one `build.layout-exists` issue per file) unless `--discard-layout` is given, before the plan is returned.
- `<name>.PrjPcb` MUST be planned when it does not exist in `--out`, and in one more case (change c0138): the build writes an output job, the existing project file does not list it, and the SHA-256 of the existing file is the one that `.fenolite/build.json` of `--out` records for it, so that the file is as a build wrote it. The project file is then planned with the bytes that a build into an empty folder writes, it is replaced like every other planned file whose bytes the record names (a `.bak` is kept unless `--no-backup` is given), it MUST NOT be listed in `result.kept`, and none of the infos about a kept project file (`altium.project-kept`, `altium.schlib-not-in-project`, `altium.pcb-not-in-project`, `altium.sheets-not-in-project`, `altium.outjob-not-listed`) MUST be given. `cmd_build` MUST pass that digest to `build_altium` as `project_digest`, and `None` for a file whose digest the record does not hold.
- Every other existing project file MUST be kept, whatever its content and whatever `--discard-layout`, and MUST be listed in `result.kept` with the info `altium.project-kept`: one that was changed since a build wrote it, one in a folder without a record, one that lists the job, and every one of a build that writes no job.
- **The record of a kept project file.** `.fenolite/build.json` of the build MUST hold `<name>.PrjPcb` with its digest when the project file is kept and `project_digest` is given, that is when the bytes of the kept file are the ones the record of `--out` held before the build, and MUST NOT hold it for any other kept project file: one that was changed since a build wrote it, and one in a folder whose record did not hold it. So a rebuild that keeps an unchanged project file keeps it known as built, and no build records an edited file as built. The keys of the record's `files` stay sorted. A kept project file MUST NOT be in `result.files`, in the plan or in the receipt, whether the record holds it or not.
- **What a kept project file lacks.** `cmd_build` MUST read an existing project file with `read.project.read_project` and pass the document paths it lists to `build_altium` as `project_listed` (`lens.altium.kept_documents`: case-folded). With `project_listed`, each of `altium.schlib-not-in-project`, `altium.pcb-not-in-project`, `altium.sheets-not-in-project` and `altium.outjob-not-listed` MUST be given only when the kept file does not list a document of its kind that the build writes, and MUST name those documents alone; a kept file that lists them all gets `altium.project-kept` and none of the four. This takes precedence over the requirements that state the four infos for a kept project file. Without `project_listed` (`None`: a caller that did not read the file) every document is named, as those requirements say. A project file that cannot be read MUST be passed as `project_listed=None` with `project_unreadable=True`, and each of the infos MUST then carry the hint `lens.altium.UNREAD_PROJECT_HINT`.
- `--discard-layout` MUST replace an edited `<name>.SchDoc`, and the mutation protocol keeps a `.bak` of it unless `--no-backup` is given.

#### Scenario: Edited schematic refused
- **GIVEN** a confirmed sample build in `B` and one byte of `B/altium_sample.SchDoc` changed afterwards
- **WHEN** the Altium build runs again with `--confirm`, and then with `--dry-run`
- **THEN** both exit 7 with `FEN-7001`, the envelope's `issues` holds `build.layout-exists` naming `B/altium_sample.SchDoc`, and no file under `B` changes

#### Scenario: Discarding the edited schematic
- **GIVEN** the same edited schematic
- **WHEN** the Altium build runs with `--discard-layout --confirm`
- **THEN** the exit code is 0, `B/altium_sample.SchDoc` holds the planned bytes, and `B/altium_sample.SchDoc.bak` holds the edited bytes

#### Scenario: Project saved by Altium is kept
- **GIVEN** a confirmed sample build in `B` whose `B/altium_sample.PrjPcb` gets a line appended afterwards, as when a PCB document is added to the project
- **WHEN** the Altium build runs again with `--confirm`, and then with `--discard-layout --confirm`
- **THEN** both exit 0, `B/altium_sample.PrjPcb` keeps the appended line, `result.kept` lists `B/altium_sample.PrjPcb`, no planned write names it, and `issues` holds `altium.project-kept`

#### Scenario: Project file of an earlier build gains the job
- **GIVEN** a folder `B` built with `--altium-outjob off` from the routed blink, whose `B/blink.PrjPcb` does not list an output job and whose record holds its digest (the folder a build of 0.2.x leaves)
- **WHEN** the Altium build runs again with `--confirm` and the job
- **THEN** the exit code is 0, `B/blink.PrjPcb` has the bytes of a build into an empty folder and lists `blink.OutJob` after `blink.PcbDoc`, `B/blink.PrjPcb.bak` holds the earlier bytes, `result.files` names the project file, `result.kept` is empty, and `issues` holds neither `altium.project-kept` nor `altium.outjob-not-listed`

#### Scenario: Changed project file without the job is kept
- **GIVEN** the same folder with a line appended to `B/blink.PrjPcb`, and a second such folder whose `.fenolite` folder was deleted
- **WHEN** the Altium build runs with `--confirm`, and in the first folder also with `--discard-layout --confirm`
- **THEN** every run exits 0, the project file keeps its bytes, no `blink.PrjPcb.bak` is written, `result.kept` lists the project file, `issues` holds `altium.outjob-not-listed` with a hint that names deleting the project file, and the record that the build writes does not hold the project file

#### Scenario: Unchanged kept project file stays known
- **GIVEN** a folder `B` built twice with `--altium-outjob off` from the routed blink
- **WHEN** the record of `B` is read, and the build then runs with the job
- **THEN** the record holds `blink.PrjPcb` with the SHA-256 of the file although the second build kept it, the second build's `result.files` and receipt do not name it, and the third build writes the project file again with `blink.OutJob` listed and `B/blink.PrjPcb.bak`

#### Scenario: Kept project file that lists everything
- **GIVEN** an Altium build of the routed blink with `project_exists=True` and `project_listed` holding the schematic document, the PCB document, the output job and both libraries
- **WHEN** `build_altium` runs with the job
- **THEN** the infos about the kept project file are `altium.project-kept` alone; with the PCB document taken out of `project_listed` they are `altium.project-kept` and one `altium.pcb-not-in-project` that names `blink.PcbDoc` and not `blink.PcbLib`

### Requirement: Reproducible Altium builds
Two Altium builds of the same script SHALL give byte-identical files under `--out`, `.fenolite/` included and `.bak` files excluded, whatever the values of `--seed`, `--timestamp` and `PYTHONHASHSEED`.
- Every record and output collection MUST be in a fixed order derived from component paths, pin designators and net names. Outputs MUST hold no date and no absolute path.
- A component's unique id MUST depend only on its component path (`altium-schematic-writer`, "Stable component unique ids"), so inserting or removing another part changes no other component's unique id.
- A build MUST leave the script folder unchanged.

#### Scenario: Twice in-process and twice by subprocess
- **WHEN** `uv run pytest tests/unit/lens/test_altium_determinism.py` builds the sample twice in-process, and twice by subprocess with `PYTHONHASHSEED=1`, `--seed 1` and `--timestamp 2026-01-01T00:00:00Z`, then `PYTHONHASHSEED=2`, `--seed 2` and `--timestamp 2027-06-01T00:00:00Z`
- **THEN** every file under `--out` is byte-identical across the four builds

#### Scenario: Inserting a part keeps the other unique ids
- **GIVEN** the sample and a variant with one more part `R9` on the net `EN`
- **WHEN** both are built
- **THEN** every component of the sample has the same unique id in both schematics

### Requirement: Altium build evidence
The Altium `build` envelope SHALL carry `lens.altium.ALTIUM_BUILD_EVIDENCE`, whose level is `INFERRED` and whose hypotheses are every `H-A-SCH-*` and `H-A-PRJ-*` row registered by this change, combined (lowest wins) with `backends.altium.project.EVIDENCE`.
- The level MUST stay `INFERRED` for every build, even after author reports: an author report covers the files the maintainer opened, never an arbitrary design, and never promotes an operation (`verification-evidence`, "Author reports never promote an operation").
- `fenolite capabilities` MUST list the writer as experimental with this evidence (`cli-contract`, "Experimental features in capabilities").

#### Scenario: Sample envelope
- **WHEN** the sample is built with `--target altium --dry-run --json`
- **THEN** `evidence.level` is `INFERRED`, and `evidence.hypotheses` contains `H-A-SCH-OPEN`, `H-A-SCH-NETS` and `H-A-PRJ-OPEN`

### Requirement: Altium sample project
`examples/altium_sample/design.py` (CC0-1.0, authored for Fenolite) SHALL be a design for the Altium target that uses every feature of this change: parts in two modules and at the top level, a part with four used pins, two `Power` interfaces sharing their low net, signal nets of two pins, and a footprint on every part.
- Its lib ids MUST name the libraries `FenoliteSample.SchLib` and `FenoliteSample.PcbLib`, which Fenolite does not ship; every designator MUST be a pin number.
- Its Altium build MUST give no issue of severity `warning` or `error`.
- Its built `altium_sample.PrjPcb` and `altium_sample.SchDoc` MUST be committed under `tests/data/altium/sample/` and compared byte for byte with a fresh build by `tests/unit/lens/test_altium_golden.py`. `FENOLITE_GOLDEN_WRITE=1` MUST rewrite them instead.
- Two check variants MUST be committed under `tests/data/altium/sample/variants/` and derived by the same test from the built schematic: `altium_sample_lf.SchDoc` (every CR LF replaced by LF) and `altium_sample_nouid.SchDoc` (every `|UNIQUEID=…` field removed, nothing else changed).
- `examples/altium_sample/design.py` and the four committed files MUST be declared in `tests/data/MANIFEST.toml` with `origin = "authored"`.
- `.gitattributes` MUST mark `*.SchDoc` and `*.PrjPcb` as `-text`, so Git never changes their line endings.

#### Scenario: Sample builds clean
- **WHEN** `fenolite build examples/altium_sample/design.py --out B --target altium --confirm --json` runs
- **THEN** the exit code is 0, `result.components` is `8`, `result.nets` is `6`, `result.power_ports` is `13`, `result.labels` is `6`, and every issue has severity `info`

#### Scenario: Golden files and variants
- **WHEN** `uv run pytest tests/unit/lens/test_altium_golden.py` runs
- **THEN** the freshly built files equal `tests/data/altium/sample/altium_sample.PrjPcb` and `altium_sample.SchDoc` byte for byte, and the variants derived from the fresh schematic equal the two committed variants

### Requirement: Altium author reports
`docs/evidence/altium-schematic.md` SHALL hold the protocol by which the maintainer checks a built Altium project in Altium Designer, and the record of each report.
- Part A MUST use the committed files of `tests/data/altium/sample/`, named by their SHA-256, in the steps of design Decision 17: open the project (A1) and the schematic (A2), compile and compare the nets with the page's table (A3), read the library link, footprint and footprint mode of `U2` (A4), save as ASCII and note only the key names Altium added and whether the unique ids are kept (A5), and open the LF variant and the variant without unique ids (A6).
- Part B MUST use a design and libraries that the maintainer created or may use for this purpose, opened with a licence the maintainer may use for it (`LEGAL.md`, block A, P3 and P4): the change order into a new PCB document (B1), a rebuild with one changed value and a second change order (B2), and "Tools » Update From Libraries" on copies, with full replacement and with "Replace selected attributes" without graphics (B3).
- The page MUST name, for each step, the hypotheses it settles, and MUST list the expected nets of the sample as (ref, pin) pairs.
- A report MUST record the Altium Designer version as `AD <major>.<minor>`, the date, and one outcome per step in generic format terms. It MUST NOT hold an artefact, a screenshot, a path, a design name, a library name or an identifier from any organisation, and no file opened or saved in the session enters the repository.
- Each confirmed `H-A-SCH-*` or `H-A-PRJ-*` row MUST get the level `ALTIUM-VERIFIED(author-report; AD <major>.<minor or x>; <YYYY-MM-DD>; no artefact)`. A refuted row MUST keep its id, start its result with `refuted; superseded by <id>-2` and get a registered successor. Without a report, a row MUST stay `INFERRED` with a result that starts with `pending (author report)`.

#### Scenario: Protocol names the sample bytes
- **WHEN** `uv run pytest tests/unit/lens/test_altium_golden.py -k protocol` reads `docs/evidence/altium-schematic.md`
- **THEN** the page names the SHA-256 of the four committed files, each equal to the file's digest, and its net table equals the nets of the sample's model

#### Scenario: Report rows are well formed
- **GIVEN** the register before and after the report is recorded
- **WHEN** `uv run pytest tests/unit/test_hypotheses_register.py tests/unit/test_altium_rows.py` runs
- **THEN** it passes: every `H-A-SCH-*` and `H-A-PRJ-*` row is refuted with a registered successor, or has the level `INFERRED` with a result that starts with `pending (author report)`, or an `ALTIUM-VERIFIED(author-report; …)` cell whose four fields match the form of this requirement

#### Scenario: Malformed report row
- **GIVEN** rows with one `H-A-SCH-*` row whose level cell is the bare `ALTIUM-VERIFIED(author-report)`
- **WHEN** the row check of `tests/unit/test_altium_rows.py` runs on them
- **THEN** it reports that row and the expected form

### Requirement: Building for Altium is documented
`docs/altium.md` SHALL describe the Altium target: the command, the lib id and footprint forms, designators as pin numbers, the generic bodies, labels and power ports, the layout, the written-once project file, the edited-output rule, the issue codes, the experimental status and its evidence, and the Altium steps: open the project, compile, put the libraries beside the project or install them, add a PCB document, run "Design » Update PCB Document", and use "Tools » Update From Libraries" with "Replace selected attributes" and graphics off, because a full replacement may detach the stubs. `docs/dsl.md` MUST point to it from a section "Building for Altium", and `docs/cli-contract.md` MUST list `--target` for `build`.
- The format facts MUST be in `docs/formats/altium/schematic-ascii.md` and `docs/formats/altium/project.md`, as fact tables (`| fact | source | label | hypothesis |`) that `tests/unit/test_format_facts.py` checks; a row below `KICAD-VERIFIED` and `CORPUS-VERIFIED` MUST name an `H-A-SCH-*` or `H-A-PRJ-*` hypothesis.
- `src/fenolite/backends/altium/PROVENANCE.md` MUST list every source the writer relies on.

#### Scenario: Fact tables are checked
- **WHEN** `uv run pytest tests/unit/test_format_facts.py tests/unit/test_provenance.py` runs
- **THEN** it checks the pages under `docs/formats/altium/` and `src/fenolite/backends/altium/PROVENANCE.md`, and passes

#### Scenario: Workflow steps documented
- **WHEN** `docs/altium.md` is read
- **THEN** it names `--target altium`, "Design » Update PCB Document", "Tools » Update From Libraries", "Replace selected attributes" and the rule that designators are pin numbers

### Requirement: Altium schematic format option
`fenolite build DESIGN.py --out DIR --target altium` SHALL write the schematic in the binary form by default, and in c0032's ASCII form with `--altium-format ascii`. This requirement extends c0032's "Altium build target", "Altium build outputs", "Altium build issue codes", "Edited Altium outputs are not overwritten", "Reproducible Altium builds" and "Altium build evidence", and the `cli-contract` requirement "Experimental features in capabilities"; their rules hold for both forms except where this requirement says otherwise.
- `--altium-format` MUST accept `binary` and `ascii`; any other value MUST be a usage error (exit 2, `FEN-2001`). Given with `--target kicad`, explicitly or by default, it MUST be a usage error (exit 2, `FEN-2001`), and nothing is written.
- `cmd_build` MUST pass the form to `lens.altium.build_altium(design, *, name, placed=(), project_exists=False, form=DEFAULT_FORM, resolver=None)`, which passes it to `write_project` (`altium-schematic-writer`, "Binary schematic form"). Without the option the form is `project.DEFAULT_FORM`, `binary`.
- The planned schematic MUST have the write kind `altium_schdoc_binary` in the binary form and `altium_schdoc_ascii` in the ASCII form. `result` and the lens summary MUST also hold `schematic_format` (`binary` or `ascii`). File names, the project file, `.fenolite/` and the build record are the same in both forms.
- With `--altium-format ascii`, the planned schematic MUST equal the bytes of c0032's ASCII writer for the same sheet plan, and every other planned file outside `.fenolite/` (the project file and the libraries, which are always compound files) MUST equal the binary build's. c0032's golden schematic and check variants are the ASCII build of the sample.
- A rebuild that only switches the form MUST replace an unchanged schematic without `--discard-layout`: the edited-output rule compares the existing file with the build record, not with the new form.
- `lens.altium.ALTIUM_ISSUE_CODES` MUST gain one row: `altium.schematic-too-large`, severity `error`, when `cfb.CompoundTooLarge` is raised (the binary schematic needs more than 109 FAT sectors). The build then returns no file and exits 5. `--altium-format ascii` never gives it. Libraries are compound files in both forms, so a library over the limit gives `altium.library-too-large` ("Schematic library issue codes") with either form, and an ASCII build then returns no file either.
- `ALTIUM_BUILD_EVIDENCE` MUST also name every `H-A-SCHBIN-*` row, combined with `binary.EVIDENCE`; its level stays `INFERRED`.
- The `capabilities` entry `altium-schematic-writer` MUST list `write_kinds` `["altium_prjpcb", "altium_schdoc_ascii", "altium_schdoc_binary", "altium_schlib"]`, which is `project.WRITE_KINDS` ("Schematic library evidence and capabilities").

#### Scenario: Binary by default
- **GIVEN** an empty folder `B`
- **WHEN** `fenolite build examples/altium_sample/design.py --out B --target altium --dry-run --json` runs
- **THEN** the exit code is 0, `result.schematic_format` is `binary`, the planned write `B/altium_sample.SchDoc` has the kind `altium_schdoc_binary`, and `B` is still empty

#### Scenario: ASCII on request
- **WHEN** the same build runs with `--altium-format ascii --confirm` into an empty folder
- **THEN** the exit code is 0, `result.schematic_format` is `ascii`, and `B/altium_sample.SchDoc` equals `tests/data/altium/sample/altium_sample.SchDoc` byte for byte

#### Scenario: Option without the Altium target
- **WHEN** `fenolite build examples/blink_2layer/design.py --out B --altium-format binary --dry-run` runs
- **THEN** the exit code is 2, stderr carries `FEN-2001`, and nothing is written

#### Scenario: Switching the form is not an edit
- **GIVEN** a confirmed ASCII build of the sample in `B`
- **WHEN** the build runs again with `--confirm` and no `--altium-format`
- **THEN** the exit code is 0, `B/altium_sample.SchDoc` holds the binary bytes, and the record maps it to their SHA-256

#### Scenario: Too large refused
- **GIVEN** `cfb.MAX_FAT_SECTORS` patched to 0 in the test process
- **WHEN** `build_altium` runs on the sample's model
- **THEN** `files` is empty and `issues` holds `altium.schematic-too-large`; with `form="ascii"` `files` is also empty and `issues` holds `altium.library-too-large` and no `altium.schematic-too-large`, because the sample's libraries are compound files

#### Scenario: Reproducible binary builds
- **WHEN** `uv run pytest tests/unit/lens/test_altium_determinism.py` builds the sample in the binary form in-process and by subprocess with different `PYTHONHASHSEED`, `--seed` and `--timestamp`
- **THEN** every file under `--out` is byte-identical across the builds

#### Scenario: Capabilities entry
- **WHEN** `uv run fenolite capabilities --json --no-tools` runs
- **THEN** the entry `altium-schematic-writer` of `result.experimental` lists the four write kinds, its `evidence.level` is `INFERRED`, and its `evidence.hypotheses` contains `H-A-SCHBIN-VIEWER`

### Requirement: Binary sample and Viewer check
The binary build of `examples/altium_sample/design.py` SHALL be committed as `tests/data/altium/sample/binary/altium_sample.SchDoc`, beside a copy of the project file, `binary/altium_sample.PrjPcb`, and SHALL be checked by the maintainer in the free Altium 365 Viewer. This requirement extends c0032's "Altium sample project" and "Altium author reports".
- `tests/unit/lens/test_altium_binary_golden.py` MUST compare a fresh binary build with both files byte for byte, check that the project copy equals `tests/data/altium/sample/altium_sample.PrjPcb`, and rewrite them when `FENOLITE_GOLDEN_WRITE=1`. Both files MUST be declared in `tests/data/MANIFEST.toml` with `origin = "authored"`.
- `docs/evidence/altium-schematic.md` MUST name the SHA-256 of both files and hold Part V, "Altium 365 Viewer opens the binary sample": upload `binary/altium_sample.SchDoc` alone (V1); upload a Zip holding the two files of `binary/` (V2); upload c0032's ASCII `altium_sample.SchDoc` in the same way as V1 (V3). Each step records the Viewer's message, or what it renders: the sheet, the 8 components with pin numbers, designators and comments, the 13 power ports and the 6 net labels. Only Fenolite's authored sample files are uploaded.
- The page MUST hold step A7 for Altium Designer: open `binary/altium_sample.SchDoc`, compile, and compare the nets with the page's table.
- The page MUST name the rows each step settles: V1 and V2 `H-A-SCHBIN-VIEWER`, `H-A-SCHBIN-CFB`, `H-A-SCHBIN-FRAME` and `H-A-SCHBIN-STORAGE`; V3 data for `H-A-SCHBIN-VIEWER`; A7 `H-A-SCHBIN-AD`, `H-A-SCHBIN-CFB`, `H-A-SCHBIN-FRAME` and `H-A-SCHBIN-STORAGE`.
- A confirmed Viewer row MUST get `ALTIUM-VERIFIED(author-report; A365 Viewer; <YYYY-MM-DD>; no artefact)`, and an Altium Designer row the form of c0032's "Altium author reports". Refuted and pending rows follow that requirement. `tests/unit/test_altium_rows.py` MUST check the stem `H-A-SCHBIN-` and accept `A365 Viewer` as the tool field.

#### Scenario: Binary golden files
- **WHEN** `uv run pytest tests/unit/lens/test_altium_binary_golden.py` runs
- **THEN** a fresh binary build equals `tests/data/altium/sample/binary/altium_sample.SchDoc`, its project file equals both committed project files, and the protocol page names the SHA-256 of both binary files, each equal to the file's digest

#### Scenario: Viewer report form
- **GIVEN** rows with `H-A-SCHBIN-VIEWER` at `ALTIUM-VERIFIED(author-report; A365 Viewer; 2026-10-03; no artefact)` and `H-A-SCHBIN-AD` at the bare `ALTIUM-VERIFIED(author-report)`
- **WHEN** the row check of `tests/unit/test_altium_rows.py` runs on them
- **THEN** it reports only `H-A-SCHBIN-AD`, with the expected form

### Requirement: Binary schematic is documented
The binary form SHALL be documented as c0032's "Building for Altium is documented" requires for the ASCII form.
- The format facts MUST be rows of `docs/formats/altium/compound-file.md` (the MS-CFB rules the writer and the test reader rely on) and `docs/formats/altium/schematic-binary.md` (streams, framing, header text, `Storage`, the Viewer), in the fact-table form that `tests/unit/test_format_facts.py` checks. A row below `KICAD-VERIFIED` and `CORPUS-VERIFIED` MUST name an `H-A-SCH-*`, `H-A-SCHBIN-*` or `H-A-PRJ-*` hypothesis.
- `src/fenolite/backends/altium/PROVENANCE.md` MUST list S-0145 to S-0148 and the extended sources.
- `docs/altium.md` MUST describe the two forms, the default, `--altium-format`, the size limit and the Viewer route; `docs/cli-contract.md` MUST list `--altium-format` for `build`.

#### Scenario: Fact pages checked
- **WHEN** `uv run pytest tests/unit/test_format_facts.py tests/unit/test_provenance.py` runs
- **THEN** it checks `compound-file.md` and `schematic-binary.md`, and passes

#### Scenario: Option documented
- **WHEN** `docs/altium.md` and `docs/cli-contract.md` are read
- **THEN** both name `--altium-format`, and `docs/altium.md` names the Altium 365 Viewer

### Requirement: Altium symbol sources
The Altium build SHALL take each lib id's symbol from one of two sources, chosen by the lib id's form; `lens.altium.symbol_source(lib_id)` returns `altium` or `kicad`.
- A lib id whose library part ends with `.SchLib` in any letter case is an Altium link (`altium`). Its symbol is generic: c0032's body over the union of the designators that the nets or the no-connect marks (`Circuit.no_connects`) name on the components of that lib id (`altium-schematic-writer`, "Generic library symbols"). No library is opened for it.
- Every other lib id is a KiCad lib id (`kicad`). Its symbol MUST be resolved with c0011's `LibraryResolver.symbol` and mapped with `altsym.from_symbol_def`. A lib id that does not resolve MUST raise c0011's `UnresolvedLibrariesError` (`FEN-3001`) with its `kicad.lib.*` issues, which pass through like `model.*` codes, and nothing is written.
- A component of a KiCad lib id MUST get one pin per pin number of body style 1 and the common style, over units 1 … n in order, with the pin's name and electrical type, ids keyed `pin:<path>:<number>`. A net member that names a pin number MUST stay; one that names a pin name MUST be rewritten to every pin number with that name; one that names neither MUST give `altium.unknown-pin`.
- A component of a KiCad lib id without `footprint` MUST take the symbol's `Footprint` property, which then follows c0032's footprint-form check. Footprint libraries are opened only as "Altium footprint sources" says: never for an Altium footprint link, and only through the same resolver for a KiCad one.
- An empty component value MUST take the symbol's `Value` property, as c0011 does.

#### Scenario: Sample reads no library
- **GIVEN** `KICAD_CONFIG_HOME` set to an empty folder
- **WHEN** the sample is built with `--target altium --dry-run --json`
- **THEN** the exit code is 0, every lib id's source is `altium`, and no issue code starts with `kicad.lib.`

#### Scenario: KiCad example resolves from its own table
- **GIVEN** `KICAD_CONFIG_HOME` set to an empty folder
- **WHEN** `fenolite build examples/altium_kicad/design.py --out B --target altium --dry-run --json` runs
- **THEN** the exit code is 0, every lib id's source is `kicad`, and the symbols come from `examples/altium_kicad/FenoliteDemo.kicad_sym` through the example's `sym-lib-table`

#### Scenario: Unknown KiCad symbol
- **GIVEN** an example variant with `lib_id="FenoliteDemo:NOPE"`
- **WHEN** it is built with `--target altium --dry-run`
- **THEN** the exit code is 3, stderr carries `FEN-3001`, and nothing is written

#### Scenario: Net member by pin name
- **GIVEN** an example variant that connects `U1["VCC"]`, where `VCC` is the name of pin `8`
- **WHEN** it is built
- **THEN** `.fenolite/circuit.json` names pin `8` in that net, and a member named `XYZ` instead gives `altium.unknown-pin`

#### Scenario: Marked designator in a generic symbol
- **GIVEN** a variant of the sample where `no_connect(u2[5])` marks a designator of `U2` that no net names
- **WHEN** it is built with `--target altium`
- **THEN** the generic symbol of `U2`'s lib id in `FenoliteSample.SchLib` holds the pins `1` to `5`, and `result.no_connects` is `1`

### Requirement: Schematic library outputs
The Altium build SHALL plan one `.SchLib` per library file that the components' lib ids give (`project.schlib_name`): `<name>.SchLib` for the KiCad lib ids, and the named file for each Altium link library; each comes from `schlib.write_schlib` with the symbols of its lib ids.
- Lib ids that give one library file, such as `Device:R` and `Power:LDO` in a design named `board`, or `board.SchLib:X`, MUST share that file. Two lib ids that give one library and one storage name under the MS-CFB order, such as `Device:R` and `Other:R`, MUST give `altium.symbol-name-collision`.
- The planned writes MUST have the kind `altium_schlib`. `project.WRITE_KINDS` MUST gain it.
- `<name>.PrjPcb`, when it is planned, MUST list every planned library (`altium-schematic-writer`, "Project file"). When the project file is kept, the build MUST add one `altium.schlib-not-in-project` info that names the libraries to add in Altium.
- A library written with generic symbols MUST give one `altium.schlib-generic` info that names it and says that it stands in for a real library of the same name.
- `result` and `summary` MUST gain `libraries` (the planned library paths) and `symbols` (the number of library components). The info `altium.generic-symbols` MUST count only components of Altium links, and MUST NOT be given when there are none.
- The library files MUST follow the edited-output rule and the build record of c0032, and MUST be byte-identical across builds of one script with one library configuration.

#### Scenario: Library of the sample
- **WHEN** the sample is built with `--target altium --confirm --json` into an empty folder `B`
- **THEN** the exit code is 0, `B/FenoliteSample.SchLib` is written with the kind `altium_schlib`, `result.libraries` lists it, `result.symbols` is `6`, and `B/altium_sample.PrjPcb` lists it as `[Document2]`

#### Scenario: Kept project
- **GIVEN** a confirmed sample build in `B` whose project file was changed afterwards
- **WHEN** the build runs again with `--confirm`
- **THEN** `issues` holds `altium.project-kept` and one `altium.schlib-not-in-project` naming `FenoliteSample.SchLib`

#### Scenario: Edited library refused
- **GIVEN** a confirmed sample build in `B` and one byte of `B/FenoliteSample.SchLib` changed afterwards
- **WHEN** the build runs again with `--confirm`
- **THEN** the exit code is 7 with `FEN-7001`, `build.layout-exists` names `B/FenoliteSample.SchLib`, and no file changes

### Requirement: Schematic library issue codes
`lens.altium.ALTIUM_ISSUE_CODES` SHALL gain these rows. This requirement extends c0032's "Altium build issue codes", whose closed-set rule and scenarios hold for them; `kicad.lib.*` issues of `UnresolvedLibrariesError` pass through like `model.*`.

| code | severity | when |
|---|---|---|
| `altium.unknown-pin` | error | a net member names neither a pin number nor a pin name of a resolved symbol |
| `altium.symbol-off-grid` | error | a pin position or length of a resolved symbol is not a multiple of 10 mil |
| `altium.pin-text-too-long` | error | a pin name or number is longer than 255 bytes |
| `altium.symbol-name-collision` | error | two lib ids give one library and one storage name, or two library file names differ only in letter case |
| `altium.library-too-large` | error | a library's compound file raises `cfb.CompoundTooLarge` |
| `altium.pin-lossy` | warning | a pin's electrical type or shape has no Altium equivalent and is mapped ("Library symbols from KiCad symbols") |
| `altium.symbol-simplified` | info | a resolved symbol's graphics became rectangles, or its other body styles or pin alternates were dropped |
| `altium.section-key` | info | a lib ref longer than 31 characters is stored under a section key |
| `altium.schlib-generic` | info | a library is written with generic symbols |
| `altium.schlib-not-in-project` | info | the project file is kept, so the libraries are not listed in it |

- A text of a library name, lib ref, description or pin MUST pass `text_problem`, else `altium.text-unwritable` (c0032).

#### Scenario: Closed set with the new rows
- **WHEN** `uv run pytest tests/unit/lens/test_altium_issues.py -k closed_set` runs
- **THEN** every row of this table is produced by at least one test with its severity

#### Scenario: Off-grid symbol writes nothing
- **GIVEN** an example variant whose library symbol has a pin 1 µm off the 10-mil grid
- **WHEN** it is built with `--target altium --confirm`
- **THEN** the exit code is 5, `issues` holds `altium.symbol-off-grid` naming the symbol and pin, and nothing is written

### Requirement: Schematic library evidence and capabilities
`ALTIUM_BUILD_EVIDENCE` SHALL also name every `H-A-SCHLIB-*` row, combined with `schlib.EVIDENCE`, and its level SHALL stay `INFERRED`. This requirement extends c0032's "Altium build evidence" and the `cli-contract` requirement "Experimental features in capabilities".
- The `capabilities` entry `altium-schematic-writer` MUST list `write_kinds` equal to `project.WRITE_KINDS`, which then holds `altium_prjpcb`, `altium_schdoc_ascii`, `altium_schdoc_binary` and `altium_schlib`.
- An `ORACLE-VERIFIED(kicad-cli)` fact row never raises the build's level: the envelope stays `INFERRED`.

#### Scenario: Capabilities entry with the library kind
- **WHEN** `uv run fenolite capabilities --json --no-tools` runs
- **THEN** the entry `altium-schematic-writer` lists the four write kinds, its `evidence.level` is `INFERRED`, and its `evidence.hypotheses` contains `H-A-SCHLIB-OPEN` and `H-A-SCHLIB-UPDATE`

### Requirement: Schematic library samples
The sample's library and an authored KiCad-sourced example SHALL be committed and checked.
- `tests/unit/lens/test_altium_schlib_golden.py` MUST compare a fresh build of `examples/altium_sample/design.py` with `tests/data/altium/sample/FenoliteSample.SchLib` byte for byte, and rewrite it when `FENOLITE_GOLDEN_WRITE=1`. c0032's and c0033's committed project files MUST be rebuilt, now listing the library; both committed schematics MUST stay unchanged.
- `examples/altium_kicad/` (CC0-1.0, authored for Fenolite) MUST hold `design.py`, `FenoliteDemo.kicad_sym` and a `sym-lib-table` naming it. Its symbols MUST cover: a two-pin part with vertical pins, a part with pins on all four sides, one hidden pin, the shapes inverted and clock, an overbar name, two units with common power pins, and a footprint named by the symbol only. It names footprints `FenoliteDemo:<name>`, never opened.
- Its build (`altium_kicad.PrjPcb`, `altium_kicad.SchDoc` binary, `altium_kicad.SchLib`) MUST be committed under `tests/data/altium/kicad_example/` and compared byte for byte by the same test.
- Every committed file MUST be declared in `tests/data/MANIFEST.toml` with `origin = "authored"`, and `.gitattributes` MUST mark `*.SchLib` as binary.

#### Scenario: Golden libraries
- **WHEN** `uv run pytest tests/unit/lens/test_altium_schlib_golden.py` runs
- **THEN** fresh builds equal the committed libraries, project files and schematics, and the sample's committed schematics equal their c0033 bytes

### Requirement: Schematic library author reports
`docs/evidence/altium-schematic.md` SHALL gain Part L, the maintainer's check of the committed libraries in Altium Designer, under the rules of c0032's "Altium author reports" and with a licence the maintainer may use for it (LEGAL.md block A, P3 and P4). A result obtained with a licence the maintainer may not use for this purpose MUST NOT be recorded.
- Steps, each naming the SHA-256 of its files and the hypotheses it settles: L1 open `FenoliteSample.SchLib` and `altium_kicad.SchLib`, and read the component list and descriptions (`H-A-SCHLIB-OPEN`, `H-A-SCHLIB-SECTIONKEY` when a keyed symbol is added); L2 pins: numbers, names, types, directions, hidden pin, shapes, parts A and B, Part Zero (`H-A-SCHLIB-PIN`, `H-A-SCHLIB-PARTS`); L3 the footprint model and its library mode (`H-A-SCHLIB-IMPLIDX`, c0032's `H-A-SCH-LINK`); L4 open each project, check that the library is listed, compile, and compare the nets with the page's tables (`H-A-SCHLIB-PRJ`, `H-A-SCHLIB-SCHDOC`, `H-A-SCHLIB-MULTIPART`); L5 "Tools » Update From Libraries" on a copy with full replacement: no component not found, pins unmoved, nets unchanged (`H-A-SCHLIB-UPDATE`); L6 re-save a copy of each library and note only the names of the keys Altium adds.
- The page MUST list the expected nets of the KiCad example as (ref, pin) pairs, and `test_altium_rows.py` MUST check the stem `H-A-SCHLIB-`.

#### Scenario: Protocol names the library bytes
- **WHEN** `uv run pytest tests/unit/lens/test_altium_schlib_golden.py -k protocol` reads the page
- **THEN** Part L names the SHA-256 of every committed library and project file of this change, each equal to the file's digest, and the example's net table equals its model's nets

### Requirement: Schematic library is documented
The library writer SHALL be documented as c0032's "Building for Altium is documented" requires.
- `docs/formats/altium/schematic-library.md` MUST hold the fact rows of the container, the header, `SectionKeys`, the `Data` records, the binary pin layout, the mappings and the oracle results, in the fact-table form that `tests/unit/test_format_facts.py` checks. A row below `KICAD-VERIFIED` and `CORPUS-VERIFIED` MUST name an `H-A-SCHLIB-*` hypothesis, and a row resting on S-0150 MUST say that S-0150 is AltiumSharp version 1 at commit `afe796434b6d2110c745c90abe44a6ddf64f5bca`.
- `docs/formats/altium/compound-file.md` MUST gain the storage rows.
- `docs/altium.md` MUST describe the two symbol sources, the library file names, the libraries in the project, the generic stand-in libraries, and the oracle. `PROVENANCE.md` MUST list S-0150 … S-0155.

#### Scenario: Fact page checked
- **WHEN** `uv run pytest tests/unit/test_format_facts.py tests/unit/test_provenance.py` runs
- **THEN** it checks `schematic-library.md` and passes

### Requirement: Altium footprint sources
The Altium build SHALL take the footprint of each footprint link from one of two sources, chosen by the link's form; `lens.altium.footprint_source(link)` returns `altium` or `kicad`.
- A component's footprint link is its `footprint`, or, for a KiCad lib id without one, the symbol's `Footprint` property ("Altium symbol sources"). A component without a link has no footprint and keeps c0032's `altium.no-footprint` warning.
- A link whose library part ends with `.PcbLib` in any letter case is an Altium link (`altium`). No library is opened and no footprint is written for it.
- Every other link is a KiCad footprint id (`kicad`). Its footprint MUST be resolved with c0011's `LibraryResolver.footprint`. A link that does not resolve MUST give one `altium.footprint-unresolved` warning, which names the link and carries the resolver's `kicad.lib.*` message in its text; those `kicad.lib.*` issues MUST NOT pass through, the footprint is not written, and the build goes on.
- `lens.altium.kicad_footprint_ids(design)` MUST return the sorted distinct `kicad` links of the components' `footprint` fields.
- The KiCad-only pad facts that the model keeps opaque in `ext["kicad"]` (corner ratio, drill form and offset, chamfer, padstack, margins) MUST be read by `lens.altium.pad_extras(defn)`, which returns one `pcblib.PadExtras` per pad. `backends.altium` MUST NOT import `backends.kicad`.

#### Scenario: Sample reads no footprint library
- **GIVEN** `KICAD_CONFIG_HOME` set to an empty folder
- **WHEN** the sample is built with `--target altium --dry-run --json`
- **THEN** the exit code is 0, every footprint link's source is `altium`, and no issue code is `altium.footprint-unresolved`

#### Scenario: KiCad footprints from the example's table
- **GIVEN** `KICAD_CONFIG_HOME` set to an empty folder
- **WHEN** `fenolite build examples/blink_2layer/design.py --out B --target altium --dry-run --json` runs
- **THEN** the exit code is 0, every footprint link's source is `kicad`, and the three footprints come from `tests/data/libs/Mini_v9.pretty` through the example's `fp-lib-table`, `U1`'s from its symbol's `Footprint` property

#### Scenario: Unresolved footprints warn
- **GIVEN** `KICAD_CONFIG_HOME` set to an empty folder
- **WHEN** c0034's `examples/altium_kicad/design.py`, whose `FenoliteDemo:<name>` footprint links name no footprint library, is built with `--target altium --dry-run --json`
- **THEN** the exit code is 0, `issues` holds one `altium.footprint-unresolved` per distinct link, no planned path ends in `.PcbLib` or `.PcbDoc`, and no issue code starts with `kicad.lib.`

### Requirement: PCB library outputs
The Altium build SHALL plan `<name>.PcbLib` (`project.pcblib_name`) when at least one KiCad footprint is written, with `pcblib.write_pcblib` and one `pcblib.LibFootprint` per distinct `kicad` link whose footprint resolves and passes `pcblib.check_footprint`.
- A refused footprint MUST give one `altium.footprint-unsupported` warning that names the link and the reason, and MUST NOT be written. Items the check drops MUST give one `altium.primitive-dropped` warning per footprint, naming each kind and count; texts, properties and 3D model links MUST give one `altium.footprint-extras-dropped` info per footprint.
- Two distinct `kicad` links whose footprints get equal storage names under the MS-CFB order (`project.storage_name`), such as `Mini:R` and `Other:R`, MUST give `altium.footprint-name-collision` (warning), and neither footprint is written: no part gets the wrong footprint.
- The planned write MUST have the kind `altium_pcblib`. `lens.altium.PCB_WRITE_KINDS` MUST be `("altium_pcbdoc", "altium_pcblib")`; `project.WRITE_KINDS` MUST NOT change.
- `<name>.PrjPcb`, when planned, MUST list the PCB library (`altium-schematic-writer`, "Project file"). When the project file is kept and a PCB file is planned, the build MUST add one `altium.pcb-not-in-project` info that names the PCB files to add in Altium.
- A compound file that raises `cfb.CompoundTooLarge` MUST give `altium.pcb-too-large` (error), and the build writes nothing.
- The library MUST follow c0032's edited-output rule and build record, and MUST be byte-identical across builds of one script with one library configuration.

#### Scenario: Library of the KiCad-footprint sample
- **WHEN** `examples/blink_2layer/design.py` is built with `--target altium --confirm --json` into an empty folder `B`
- **THEN** the exit code is 0, `B/blink.PcbLib` is written with the kind `altium_pcblib`, `result.libraries` lists it, `result.footprints` is `3`, `B/blink.PrjPcb` lists it, and `issues` holds one `altium.primitive-dropped` naming the filled polygon of `Mini_QFP-32_7x7mm_P0.8mm`

#### Scenario: Name collision writes neither
- **GIVEN** a blink variant whose `R1` uses `Mini:Mini_R_0603` and a second part uses `Other:Mini_R_0603`, where `Other` is a second `fp-lib-table` entry naming `tests/data/libs/Mini.pretty`
- **WHEN** it is built with `--target altium --dry-run --json`
- **THEN** the exit code is 0, `issues` holds `altium.footprint-name-collision` naming both links, the planned library holds neither footprint, and `altium.pcbdoc-not-written` names both parts

#### Scenario: Refused footprint
- **GIVEN** a blink variant whose `R1` names an authored footprint with a `trapezoid` pad
- **WHEN** it is built with `--target altium --dry-run --json`
- **THEN** the exit code is 0, `issues` holds `altium.footprint-unsupported` naming the pad, and the planned library holds the two other footprints

#### Scenario: Edited library refused
- **GIVEN** a confirmed blink build in `B` and one byte of `B/blink.PcbLib` changed afterwards
- **WHEN** the build runs again with `--confirm`
- **THEN** the exit code is 7 with `FEN-7001`, `build.layout-exists` names `B/blink.PcbLib`, and no file changes

### Requirement: PCB document output
The Altium build SHALL plan an experimental `<name>.PcbDoc` from `pcbdoc.write_pcbdoc` when the design has a board outline without cutouts and without arcs (`design-model`, "Board outline arcs") and every component that has a footprint link has a `kicad` link whose footprint is in the planned `<name>.PcbLib`. Otherwise it MUST give one `altium.pcbdoc-not-written` info that names the reason (no board, cutouts, arcs, Altium footprint links, or the footprints not written) and the components concerned.
- Components without a footprint link MUST be left off the board, as Altium's change order would leave them.
- The parts of `design.hole()` (`design-dsl`, "Board holes in the DSL"), whose symbols are in the library `Fenolite_Holes`, are not components of the Altium build: they MUST be left out of the schematic, of `<name>.PcbLib` and of the components of the document, and they do not count as components with a footprint link. The build MUST hand each one to the document as a board hole instead (`altium-pcb-writer`, "Non-plated holes and slots"). A round hole that is not plated becomes a `Hole` of the part's `drill` at the part's placement, written as the free pad record of that requirement and counted under the kind `hole` of `result.pcb.written`. A slot (`length`) and a plated hole (`pad`) have no record there, because the board hole of the model is round and has neither copper nor a net: each MUST give one `altium.not-lowered` info whose `where` is `hole/<component id>`, naming the ref and what the record lacks, and MUST be counted under `hole` of `result.pcb.not_lowered`. The pin of a plated hole is then absent from its net in the Altium project, and the message MUST say so. The courtyard of a hole part has no counterpart on a free pad and is not written. Without a PCB document the hole parts are counted by the `holes` issue of the next rule.
- A placed component MUST take its DSL placement. An unplaced component MUST be staged right of the outline as the KiCad build stages it (`lens.build.STAGING_OFFSET`, `STAGING_GAP`, top side, angle 0), and the build MUST give one `altium.pcb-staged` info naming the staged refs. With a copper source, a component takes the source's placement instead, and none is staged ("Copper from a routed KiCad board").
- When the PCB document is planned, the board, the placements and the net classes MUST NOT be reported by `altium.not-lowered`: the document holds them ("Copper in an Altium build"). Differential pairs still are. A board's keep-outs, texts, graphics and holes are written, or reported item by item, as "Complete board in an Altium build" states; only a build without a PCB document reports them with one issue per kind, and these kinds extend the list of c0032's `altium.not-lowered` row.
- The planned write MUST have the kind `altium_pcbdoc`, and the project file MUST list it as `[Document2]`.
- The document MUST follow c0032's edited-output rule: a document changed in Altium is refused with `FEN-7001`, and `--discard-layout` replaces it with a `.bak`. Fenolite never merges an edited document.

#### Scenario: Document of the KiCad-footprint sample
- **WHEN** `examples/blink_2layer/design.py` is built with `--target altium --confirm --json` into an empty folder `B`
- **THEN** the exit code is 0, `B/blink.PcbDoc` is written with the kind `altium_pcbdoc`, `result.pcb_document` is `B/blink.PcbDoc`, `B/blink.PrjPcb` lists it as `[Document2]`, and `issues` holds no `altium.not-lowered` and no `altium.pcb-staged`

#### Scenario: No board, no document
- **GIVEN** a blink variant without `design.board(...)`
- **WHEN** it is built with `--target altium --dry-run --json`
- **THEN** the exit code is 0, `B/blink.PcbLib` is planned, no `.PcbDoc` is planned, and `issues` holds `altium.pcbdoc-not-written` naming the missing board

#### Scenario: Unplaced part is staged
- **GIVEN** a blink variant whose `R1` is not placed
- **WHEN** it is built with `--target altium --dry-run --json`
- **THEN** `B/blink.PcbDoc` is planned, `issues` holds `altium.pcb-staged` naming `R1`, and `R1`'s component record has the position the KiCad build of the same variant stages it at, converted as `altium-pcb-writer` "PCB document placement" says

#### Scenario: An outline with arcs, no document
- **GIVEN** a blink variant with `board(outline=shape.rect(mm(0), mm(0), mm(50), mm(30), radius=mm(2)))`
- **WHEN** it is built with `--target altium --dry-run --json`
- **THEN** the exit code is 0, no `.PcbDoc` is planned, and `issues` holds `altium.pcbdoc-not-written` naming the arcs

#### Scenario: A round hole becomes a free pad
- **GIVEN** a blink variant with `d.hole("H1", mm(4), mm(4), drill=mm(3.2))`
- **WHEN** it is built with `--target altium --confirm --json` and the PCB document is read back
- **THEN** the exit code is 0, `result.pcb.written` holds `hole` with the count 1, the document holds one free pad with a 3.2 mm hole, plating off and no copper at the placement of `H1`, neither the schematic nor `blink.PcbLib` holds `H1` or a footprint of `Fenolite_Holes`, and no `altium.not-lowered` names `H1`

#### Scenario: A plated hole and a slot are reported
- **GIVEN** a blink variant with `h2 = d.hole("H2", mm(46), mm(4), drill=mm(3.2), pad=mm(6))`, `connect(gnd, h2[1])` and `d.hole("H3", mm(25), mm(4), drill=mm(1), length=mm(3))`
- **WHEN** it is built with `--target altium --dry-run --json`
- **THEN** the exit code is 0, `B/blink.PcbDoc` is planned without them, `result.pcb.not_lowered` holds `hole` with the count 2, and `issues` holds two `altium.not-lowered` infos whose `where` starts with `hole/`: one names `H2`, its copper and the net `GND`, the other names `H3` and its slot

### Requirement: PCB issue codes
`lens.altium.ALTIUM_ISSUE_CODES` SHALL gain these rows. This requirement extends c0032's "Altium build issue codes", whose closed-set rule and scenarios hold for them.

| code | severity | when |
|---|---|---|
| `altium.pcb-too-large` | error | the PCB library or document raises `cfb.CompoundTooLarge` |
| `altium.footprint-unresolved` | warning | a KiCad footprint link does not resolve |
| `altium.footprint-unsupported` | warning | `pcblib.check_footprint` refuses a footprint |
| `altium.footprint-name-collision` | warning | two KiCad footprint links give one storage name |
| `altium.primitive-dropped` | warning | a footprint graphic or pad setting has no written form and is left out |
| `altium.footprint-extras-dropped` | info | a footprint's texts, properties or 3D model links are not written |
| `altium.pcbdoc-not-written` | info | the PCB document's conditions do not hold |
| `altium.pcb-staged` | info | unplaced components are staged beside the outline |
| `altium.pcb-not-in-project` | info | the project file is kept, so the PCB files are not listed in it |

- A footprint name, pad number or description MUST pass `text_problem`; a footprint name or pad number that fails it refuses the footprint (`altium.footprint-unsupported`), a description that fails it is left out.

#### Scenario: Closed set with the PCB rows
- **WHEN** `uv run pytest tests/unit/lens/test_altium_issues.py -k closed_set` runs
- **THEN** every row of this table is produced by at least one test with its severity

#### Scenario: Too large refused
- **GIVEN** `pcblib.write_pcblib` patched in the test process to raise `cfb.CompoundTooLarge`
- **WHEN** `build_altium` runs on the blink model
- **THEN** `files` is empty and `issues` holds `altium.pcb-too-large`

### Requirement: PCB evidence and capabilities
`lens.altium.PCB_BUILD_EVIDENCE` SHALL have the level `INFERRED` and name every `H-A-PCB-*` row, combined (lowest wins) with `pcbrecords.EVIDENCE`, `pcblib.EVIDENCE` and `pcbdoc.EVIDENCE`. This requirement extends c0032's "Altium build evidence" and the `cli-contract` requirement "Experimental features in capabilities".
- `ALTIUM_BUILD_EVIDENCE` MUST also name every `H-A-PCB-*` row, and its level MUST stay `INFERRED`.
- The `capabilities` entry `altium-pcb-writer` MUST list `write_kinds` equal to `lens.altium.PCB_WRITE_KINDS` and the evidence of `PCB_BUILD_EVIDENCE`.
- An `ORACLE-VERIFIED(kicad-cli)` or `ALTIUM-VERIFIED(author-report; …)` fact row never raises the build's level or an entry's level.

#### Scenario: PCB entry in capabilities
- **WHEN** `uv run fenolite capabilities --json --no-tools` runs
- **THEN** the entry `altium-pcb-writer` lists `altium_pcbdoc` and `altium_pcblib`, its `evidence.level` is `INFERRED`, and its `evidence.hypotheses` contains `H-A-PCB-KICAD-LIB` and `H-A-PCB-DOC-LINK`

#### Scenario: Build envelope stays inferred
- **WHEN** the blink example is built with `--target altium --dry-run --json`
- **THEN** `evidence.level` is `INFERRED`, and `evidence.hypotheses` contains `H-A-PCB-ECO` and `H-A-SCH-OPEN`

### Requirement: PCB samples
The KiCad-footprint sample's PCB files SHALL be committed and checked, and the earlier samples SHALL keep their bytes where this change does not touch them.
- The Altium build of `examples/blink_2layer/design.py` (`blink.PrjPcb`, `blink.SchDoc` binary, `blink.SchLib`, `blink.PcbLib`, `blink.PcbDoc`) MUST be committed under `tests/data/altium/blink/` and compared byte for byte with a fresh build by `tests/unit/lens/test_altium_pcb_golden.py`; `FENOLITE_GOLDEN_WRITE=1` MUST rewrite them instead.
- Every committed file of `tests/data/altium/sample/` MUST stay byte-identical: the sample links only Altium footprint libraries.
- c0034's committed example files MUST be rebuilt once: its schematic now names `altium_kicad.PcbLib` in `MODELDATAFILE0`; its library and project file MUST stay byte-identical.
- Every committed file MUST be declared in `tests/data/MANIFEST.toml` with `origin = "authored"`, and `.gitattributes` MUST mark `*.PcbLib` and `*.PcbDoc` as `-text`.

#### Scenario: Golden PCB files
- **WHEN** `uv run pytest tests/unit/lens/test_altium_pcb_golden.py` runs
- **THEN** fresh builds equal the five committed blink files, and `git diff --exit-code tests/data/altium/sample/` exits 0

### Requirement: PCB author reports
`docs/evidence/altium-pcb.md` SHALL hold the protocol by which the maintainer checks the committed blink files, under the rules of c0032's "Altium author reports" and with a licence the maintainer may use for it (`LEGAL.md` block A, P3 and P4). A result obtained with a licence the maintainer may not use for Fenolite, such as an employer's licence, MUST NOT be recorded; the rows it would settle stay `INFERRED` with a result that starts with `pending (author report)`.
- Part P, the free Altium 365 Viewer: P1 upload `blink.PcbDoc` alone and check the outline, the three components, their pads and designators, and `D1` on the bottom (`H-A-PCB-DOC-VIEWER`, `H-A-PCB-PAD`, `H-A-PCB-GRAPHICS`, `H-A-PCB-DOC-BOTTOM`); P2 upload a Zip of the five files and note whether the project, the library and the document are listed.
- Part D, Altium Designer: D1 open the project and `blink.PcbLib`, list the footprints, and check pads, holes and graphics against the page's table (`H-A-PCB-LIB-OPEN`, `H-A-PCB-LIB-NAME` when a keyed footprint is added, `H-A-PCB-PAD`, `H-A-PCB-GRAPHICS`, `H-A-PCB-PRJ`); D2 run "Design » Update PCB Document" from `blink.SchDoc` into a new blank PCB document on a copy: every footprint found (`H-A-PCB-ECO`); D3 open `blink.PcbDoc` on a copy without a repair prompt, then run "Design » Update PCB Document": no component added or removed and no net changed, `D1` on the bottom as in its KiCad build (`H-A-PCB-DOC-OPEN`, `H-A-PCB-DOC-LINK`, `H-A-PCB-DOC-NETS`, `H-A-PCB-DOC-BOTTOM`).
- Each step MUST name the SHA-256 of its files and the hypotheses it settles. The page MUST list the expected pad nets as (ref, pad, net) and the component layers and rotations, and the pad table (number, shape, size, hole) of each footprint.
- A Viewer report MUST be recorded as `ALTIUM-VERIFIED(author-report; A365 Viewer; <YYYY-MM-DD>; no artefact)`, an Altium Designer report as c0032 says. `test_altium_rows.py` MUST check the stem `H-A-PCB-`.

#### Scenario: Protocol names the PCB bytes
- **WHEN** `uv run pytest tests/unit/lens/test_altium_pcb_golden.py -k protocol` reads the page
- **THEN** it names the SHA-256 of every committed blink file, each equal to the file's digest, and its pad-net table equals the model's nets

#### Scenario: Report rows are well formed
- **WHEN** `uv run pytest tests/unit/test_hypotheses_register.py tests/unit/test_altium_rows.py` runs
- **THEN** every `H-A-PCB-*` row is pending, refuted with a successor, `ORACLE-VERIFIED(kicad-cli)` for the two `KICAD` rows, or carries an author-report label of the form this requirement gives

### Requirement: PCB writers are documented
The PCB writers SHALL be documented as c0032's "Building for Altium is documented" requires.
- `docs/formats/altium/pcb-library.md`, `pcb-records.md` and `pcb-document.md` MUST hold the fact rows of the container, the records with their offsets, the layer map, the frame and the oracle observations, in the fact-table form that `tests/unit/test_format_facts.py` checks. A row below `KICAD-VERIFIED` and `CORPUS-VERIFIED` MUST name an `H-A-PCB-*` hypothesis. A row resting on S-0150 MUST say that S-0150 is AltiumSharp version 1 at commit `afe796434b6d2110c745c90abe44a6ddf64f5bca`, and `pcb-library.md` MUST hold a section "Version 2 not used" that lists the facts left out because only version 2 gives them.
- `docs/formats/altium/compound-file.md` MUST gain the empty-stream row.
- `docs/altium.md` MUST describe the two footprint sources, `<name>.PcbLib`, the layer map with its mechanical-layer choice, what is refused and what is dropped, the PCB document's conditions, staging and frame, the change-order and "Update PCB Document" steps, and the two oracles. `docs/cli-contract.md` MUST list the second experimental entry. `PROVENANCE.md` MUST list S-0160 … S-0166 and the PCB files of S-0150.

#### Scenario: Fact pages checked
- **WHEN** `uv run pytest tests/unit/test_format_facts.py tests/unit/test_provenance.py` runs
- **THEN** it checks the three `pcb-*.md` pages and passes

#### Scenario: Steps documented
- **WHEN** `docs/altium.md` is read
- **THEN** it names `.PcbLib`, `.PcbDoc`, "Design » Update PCB Document", the layer table and `altium.pcbdoc-not-written`

### Requirement: No-connect marks in an Altium build
`lens.altium.build_altium` SHALL carry the marks of `Circuit.no_connects` into the schematic as No ERC directives (`altium-schematic-writer`, "No-connect directives on the sheet"), after resolving them with the pins it sets on the components ("Altium build outputs").
- For a component of a KiCad lib id, `lens.altium.kicad_pins` MUST rewrite each mark as it rewrites net members: a pin number stays, a pin name becomes every pin number with that name, and a designator that is neither MUST give `altium.unknown-pin` (error) naming the ref and the designator, with `where` set to the component path.
- For a component of an Altium link, `lens.altium.generic_pins` MUST count a marked designator as a used pin (`altium-schematic-writer`, "Generic component bodies"), so the generic body and the generated library symbol hold it.
- A marked designator MUST pass `ascii.text_problem` like a net member's; otherwise `altium.text-unwritable` (error).
- `Design.validate()` then runs on the model with its pins and rewritten marks, so a pin that is marked and on a net gives `model.no-connect-on-net` (error): the build exits 5 and writes nothing. No `altium.*` code is added.
- `.fenolite/circuit.json` MUST store the rewritten marks, and `summary` MUST also hold `no_connects`, the number of directives written, which `cmd_build` copies into `result`.
- The schematic library symbols of KiCad lib ids, their pin records and pin electrical types, `<name>.PrjPcb`, `<name>.PcbLib` and `<name>.PcbDoc` MUST NOT depend on the marks.
- `docs/altium.md` MUST gain a section on no-connect marks: the DSL call, the directive and its "Suppress All Violations" mode, that a marked pin gets no stub, and that the directive stays at its sheet position when "Tools » Update From Libraries" replaces a body.

#### Scenario: Example builds with three directives
- **WHEN** `fenolite build examples/altium_kicad/no_connect.py --out B --target altium --confirm --json` runs
- **THEN** the exit code is 0, `result.no_connects` is `3`, `result.nets` is `3`, `result.power_ports` is `6`, `result.labels` is `2`, no issue has severity `error`, and `B/.fenolite/circuit.json` holds the marks of `U1` pins `2`, `4` and `8`

#### Scenario: A marked name is rewritten to its number
- **GIVEN** a variant of the example that marks `u1["TP"]` instead of `u1[8]`
- **WHEN** it is built
- **THEN** the schematic bytes equal the example's, and the stored mark is `PinRef(<U1 id>, "8")`

#### Scenario: Marked and connected after resolution
- **GIVEN** a variant of the example with `connect(sig, u1["TP"])` and `no_connect(u1[8])`
- **WHEN** it is built with `--target altium --confirm`
- **THEN** the exit code is 5, `issues` holds `model.no-connect-on-net` whose `where` is `U1-8`, and nothing is written

#### Scenario: Library symbol does not depend on the marks
- **GIVEN** the example and a variant without its `no_connect` call
- **WHEN** both are built
- **THEN** the two `altium_no_connect.SchLib` files and the two `altium_no_connect.PrjPcb` files are equal byte for byte

### Requirement: No-connect sample and author report
`examples/altium_kicad/no_connect.py` (CC0-1.0, authored for Fenolite) SHALL be a design named `altium_no_connect` for the Altium target whose marks can be judged by Altium Designer's compiler, and `docs/evidence/altium-schematic.md` SHALL hold Part N, the protocol of that check.
- The design MUST use the folder's authored `FenoliteDemo.kicad_sym` through its `sym-lib-table`: `J1` (`CONN2`), `R1` (`R_V`) and `U1` (`MCU8`); the nets `VIN` (`J1` 1, `U1` 1 and 6, `R1` 1), `GND` (`J1` 2, `U1` 7) and `OE_N` (`R1` 2, `U1` 5); `Power(VIN, GND)`; `no_connect(u1[2], u1[4], u1[8])`, an input, an output and a passive pin; and `U1` pin `3`, an input, left unconnected and unmarked as the positive control.
- Its built `altium_no_connect.PrjPcb`, `altium_no_connect.SchLib` and binary `altium_no_connect.SchDoc` MUST be committed under `tests/data/altium/no_connect/`, and its ASCII schematic under `tests/data/altium/no_connect/ascii/`, declared in `tests/data/MANIFEST.toml` with `origin = "authored"` together with the script, and compared byte for byte with a fresh build by `tests/unit/lens/test_altium_no_connect_golden.py`. `FENOLITE_GOLDEN_WRITE=1` MUST rewrite them instead.
- Part N MUST name the committed files by their SHA-256 and hold these steps, each with the hypotheses it settles:
  - N1: open the project and the binary schematic in Altium Designer; note any prompt or repair offer, and whether a No ERC directive shows at the ends of `U1` pins `2`, `4` and `8` (`H-A-SCH-NC-RECORD`);
  - N2: compile the project; note every message that names `U1` (`H-A-SCH-NC-ERC`). Expected: none for pins `2`, `4` and `8`, and a floating-input message for pin `3`;
  - N3: repeat N1 and N2 with the ASCII schematic in place of the binary one (`H-A-SCH-NC-RECORD`, `H-A-SCH-NC-ERC`);
  - N4: upload the binary schematic alone to the Altium 365 Viewer; note whether the three directives are drawn (`H-A-SCH-NC-VIEWER`).
- A report follows "Altium author reports": tool as `AD <major>.<minor>` or `A365 Viewer`, the date, one generic outcome per step, no artefact, and only Fenolite's authored files opened or uploaded. A confirmed row gets `ALTIUM-VERIFIED(author-report; AD <major>.<minor or x>; <YYYY-MM-DD>; no artefact)`, or the `A365 Viewer` form for N4.
- `docs/hypotheses.md` MUST register `H-A-SCH-NC-RECORD`, `H-A-SCH-NC-ERC` and `H-A-SCH-NC-VIEWER`, and `docs/evidence/sources.md` MUST register S-0180. `lens.altium.ALTIUM_BUILD_EVIDENCE` MUST name the three hypotheses and MUST stay `INFERRED` after any report ("Altium build evidence").

#### Scenario: Golden files of the example
- **WHEN** `uv run pytest tests/unit/lens/test_altium_no_connect_golden.py` runs
- **THEN** the freshly built files equal the four committed files byte for byte, and Part N names the SHA-256 of each

#### Scenario: Registers hold the new rows
- **WHEN** `grep -cE '^\| H-A-SCH-NC-' docs/hypotheses.md` and `grep -cE '^\| S-0180 ' docs/evidence/sources.md` run
- **THEN** they print `3` and `1`, and `uv run pytest tests/unit/test_hypotheses_register.py tests/unit/test_altium_rows.py` passes

#### Scenario: Envelope evidence
- **WHEN** the example is built with `--target altium --dry-run --json`
- **THEN** `evidence.level` is `INFERRED` and `evidence.hypotheses` contains `H-A-SCH-NC-RECORD`, `H-A-SCH-NC-ERC` and `H-A-SCH-NC-VIEWER`

### Requirement: Altium sheets option
`fenolite build DESIGN.py --out DIR --target altium` SHALL write one schematic sheet by default, and one top sheet plus one sheet per top-level module with `--altium-sheets modules`. This requirement extends "Altium build target", "Altium schematic format option", "Edited Altium outputs are not overwritten" and "Reproducible Altium builds"; their rules hold in both modes except where this requirement says otherwise.
- `--altium-sheets` MUST accept `flat` and `modules`; any other value MUST be a usage error (exit 2, `FEN-2001`). Given with `--target kicad`, explicitly or by default, it MUST be a usage error (exit 2, `FEN-2001`), and nothing is written.
- `cmd_build` MUST pass the mode to `lens.altium.build_altium(…, sheets=…)`. Without the option the mode is `project.DEFAULT_SHEETS`, `flat`.
- In the `flat` mode every planned file outside `.fenolite/` MUST equal, byte for byte, the file the build planned before this change, for a design without a `harness` interface.
- A module sheet MUST have the write kind of the schematic's form (`altium_schdoc_binary` or `altium_schdoc_ascii`), and a harness definition file the write kind `altium_harness`. `project.WRITE_KINDS` and the `capabilities` entry `altium-schematic-writer` MUST gain `altium_harness`.
- Every planned sheet and harness file MUST follow the edited-output rule on its own: a file changed since the build record is refused with `FEN-7001`, and `--discard-layout` replaces it with a `.bak`. A rebuild that only switches the mode MUST replace unchanged files without `--discard-layout`.
- A file of an earlier build that the new plan no longer holds (a module sheet after a module was renamed, or after a switch to `flat`) MUST be left in place and MUST NOT be listed in the new project file or build record.
- `result` and the lens summary MUST hold `sheet_mode` (`flat` or `modules`), `sheets` (the schematic files, the top sheet first), `ports`, `sheet_entries` and `harnesses` (the number of harness types lowered).

#### Scenario: Flat by default
- **GIVEN** an empty folder `B`
- **WHEN** `fenolite build examples/altium_hier/design.py --out B --target altium --dry-run --json` runs
- **THEN** the exit code is 0, `result.sheet_mode` is `flat`, `result.sheets` is `["altium_hier.SchDoc"]`, `result.ports`, `result.sheet_entries` and `result.harnesses` are `0`, and `B` is still empty

#### Scenario: Modules on request
- **WHEN** the same build runs with `--altium-sheets modules --confirm` into an empty folder
- **THEN** the exit code is 0, `result.sheets` is `["altium_hier.SchDoc", "altium_hier_flash.SchDoc", "altium_hier_mcu.SchDoc"]`, `result.ports` is `5`, `result.sheet_entries` is `5`, `result.harnesses` is `1`, and the two `.Harness` files are written with the kind `altium_harness`

#### Scenario: Option without the Altium target
- **WHEN** `fenolite build examples/blink_2layer/design.py --out B --altium-sheets modules --dry-run` runs
- **THEN** the exit code is 2, stderr carries `FEN-2001`, and nothing is written

#### Scenario: Earlier outputs are unchanged
- **WHEN** `uv run pytest tests/unit/lens/test_altium_golden.py tests/unit/lens/test_altium_binary_golden.py tests/unit/lens/test_altium_schlib_golden.py tests/unit/lens/test_altium_pcb_golden.py` runs after this change
- **THEN** every test passes with no golden file rewritten

#### Scenario: Switching the mode is not an edit
- **GIVEN** a confirmed `flat` build of the sample in `B`
- **WHEN** the build runs again with `--altium-sheets modules --confirm`
- **THEN** the exit code is 0 and `B/altium_hier.SchDoc` holds the top sheet of the `modules` build

#### Scenario: Reproducible module sheets
- **WHEN** `uv run pytest tests/unit/lens/test_altium_determinism.py -k hierarchy` builds the sample with `sheets="modules"` in-process and by subprocess with different `PYTHONHASHSEED`, `--seed` and `--timestamp`
- **THEN** every file under `--out` is byte-identical across the builds

### Requirement: Module sheets in an Altium build
`lens.altium.build_altium(…, sheets="modules")` SHALL plan the sheets of `hierarchy.plan_sheets` (`altium-schematic-writer`, "Sheets of a hierarchical project" and "Sheets of a module tree"), their harness definition files and a project file that lists them, and SHALL link the PCB document's components through their sheet symbols.
- `project.write_project(…, sheets=…)` MUST write `<name>.SchDoc` as the top sheet, one `<name>_<module path with "." for "/">.SchDoc` per module at any depth, one `<sheet stem>.Harness` per sheet that holds a harness block, and `<name>.PrjPcb` through `write_prjpcb(…, sheets=…, harnesses=…)`. The libraries MUST NOT depend on the mode.
- `lens.altium.pcb_document` MUST set `PlacedComponent.sheet` to `(unique_id("sheet:<module>"), <module>)` for a component on the sheet of a top-level module, and leave it `None` for a top-sheet component and in the `flat` mode (`altium-pcb-writer`, "PCB document links and nets"). For a module below the first level both items MUST hold one entry per level from the top sheet down, joined by a backslash: the unique ids of the sheet symbols, and their names; the component class of such a sheet is named after its own sheet symbol, the last name (`H-A-SCHX-ECO`).
- A component's `UNIQUEID`, its designator, its library links and the net names MUST NOT depend on the mode, so the engineering change order matches the same components and nets in both modes (`H-A-SCH-HIER-ECO`, `H-A-SCH-HIER-NAMES`).
- A `harness` interface none of whose members crosses a top-level module, any `harness` interface in the `flat` mode, and any in the ASCII form MUST be reported by one `altium.not-lowered` info for the kind, naming the interfaces; their nets are written as plain nets.
- `.fenolite/` MUST NOT depend on the mode, except `.fenolite/build.json`, which records the planned files.
- When `<name>.PrjPcb` exists and is kept, and the plan holds a module sheet or a harness file, the build MUST give one `altium.sheets-not-in-project` info naming them.
- `ALTIUM_BUILD_EVIDENCE` MUST name every `H-A-SCH-HIER-*` and `H-A-SCH-HARN-*` row, and MUST stay `INFERRED`.

#### Scenario: Libraries do not depend on the mode
- **WHEN** the sample is built with `sheets="flat"` and with `sheets="modules"`
- **THEN** both `FenoliteHier.SchLib` files are equal byte for byte, and the six layer files under `.fenolite/` are equal

#### Scenario: Harness not lowered in the flat mode
- **WHEN** the sample is built with the default mode
- **THEN** `issues` holds one `altium.not-lowered` info naming the harness `SPI`, and no file ends with `.Harness`

#### Scenario: Harness not lowered in the ASCII form
- **WHEN** the sample is built with `sheets="modules"` and `form="ascii"`
- **THEN** `issues` holds one `altium.not-lowered` info naming `SPI`, `summary["harnesses"]` is `0`, `summary["ports"]` is `11`, and no file ends with `.Harness`

#### Scenario: Kept project file
- **GIVEN** `project_exists=True`
- **WHEN** the sample is built with `sheets="modules"`
- **THEN** `files` holds no `.PrjPcb`, and `issues` holds one `altium.sheets-not-in-project` info naming the two module sheets and the two harness files

#### Scenario: Envelope evidence
- **WHEN** the sample is built with `--target altium --altium-sheets modules --dry-run --json`
- **THEN** `evidence.level` is `INFERRED` and `evidence.hypotheses` contains `H-A-SCH-HIER-OPEN`, `H-A-SCH-HIER-ECO` and `H-A-SCH-HARN-OPEN`

### Requirement: Hierarchy issue codes
`lens.altium.ALTIUM_ISSUE_CODES` SHALL gain these rows. This requirement extends c0032's "Altium build issue codes", whose closed-set rule and scenarios hold for them. Each is reported in both modes, so a design is refused before its mode is switched.

| code | severity | when |
|---|---|---|
| `altium.sheet-name-collision` | error | two modules, at any depth, give one sheet file name or names that differ only in letter case (the module path with `.` for `/`), so their sheet files would collide |
| `altium.harness-name` | error | a harness type name or entry name holds `=`, `,` or `;`; two type names, or two entry names of one type, differ only in letter case; or a type name equals a net name in any letter case |
| `altium.harness-net-shared` | error | a net is a member of two `harness` interfaces, or twice of one |
| `altium.harness-power-net` | error | a member of a `harness` interface is also a member of a `power` interface |
| `altium.sheets-not-in-project` | info | the project file is kept, so the module sheets and harness files are not listed in it |

- A type name, entry name or module path that `ascii.text_problem` refuses MUST give `altium.text-unwritable`, as any written text.
- `altium.not-lowered` MUST also cover the kind "harnesses" ("Module sheets in an Altium build").
- `altium.unique-id-collision` MUST also cover sheet symbols and ports (`altium-schematic-writer`, "Stable component unique ids").

#### Scenario: Net in two harnesses
- **GIVEN** a variant of the sample with a second harness `DBG` that also holds `SPI_SCK`
- **WHEN** it is built with `--target altium --confirm`
- **THEN** the exit code is 5, `issues` holds `altium.harness-net-shared` naming `SPI_SCK`, `SPI` and `DBG`, and nothing is written

#### Scenario: Power net in a harness
- **GIVEN** a variant whose harness `SPI` also holds `GND`
- **WHEN** it is built
- **THEN** `issues` holds `altium.harness-power-net` naming `GND`

#### Scenario: Separator in an entry name
- **GIVEN** a variant whose harness has an entry named `CS,1`
- **WHEN** it is built
- **THEN** `issues` holds `altium.harness-name` naming the entry

#### Scenario: Module names that differ in case
- **GIVEN** a variant with the top-level modules `mcu` and `MCU`
- **WHEN** it is built
- **THEN** `issues` holds `altium.sheet-name-collision` naming both

### Requirement: Hierarchy sample and author report
`examples/altium_hier/design.py` (CC0-1.0, authored for Fenolite) SHALL be a design named `altium_hier` with a top sheet, two module sheets and one harness, and `docs/evidence/altium-schematic.md` SHALL hold Part H, the protocol of its check in Altium Designer.
- The design MUST use Altium links to `FenoliteHier.SchLib` and `FenoliteHier.PcbLib`, which Fenolite does not ship. Parts: `J1` on the top sheet; `U1` and `C1` in the module `mcu`; `U2`, `C2` and `R1` in the module `flash`. Nets: `VDD` and `GND` (`Power(VDD, GND)`, on all three sheets); `RESET_N` (`J1`, `U1`); `FLASH_WP` (`U1`, `U2`); `SPI_MOSI`, `SPI_MISO`, `SPI_SCK` and `SPI_CS` (`U1`, `U2`), grouped by `Harness("SPI", {"MOSI": …, "MISO": …, "SCK": …, "CS": …})`; and `FLASH_HOLD_N` (`U2`, `R1`), local to `flash`.
- `examples/altium_hier/partial.py` MUST be the same design, named `altium_hier_partial`, with a fifth entry `HOLD` on `FLASH_HOLD_N`.
- `examples/altium_hier_board/design.py` MUST be a design named `altium_hier_board` with the parts, nets, footprints, board and placements of `examples/blink_2layer/design.py`, with `U1` and `R1` in a module `driver` and `D1` in a module `led`, and with library tables that name the same authored libraries under `tests/data/libs/`, so its `modules` build writes a PCB document.
- The `modules` build of `design.py` in the binary form (`altium_hier.PrjPcb`, three `.SchDoc`, two `.Harness`, `FenoliteHier.SchLib`) MUST be committed under `tests/data/altium/hier/`, declared in `tests/data/MANIFEST.toml` with `origin = "authored"` together with the scripts, and compared byte for byte with a fresh build by `tests/unit/lens/test_altium_hier_golden.py`. `FENOLITE_GOLDEN_WRITE=1` MUST rewrite them instead.
- Part H MUST name the committed files by their SHA-256 and hold these steps, each with the hypotheses it settles:
  - H1: open `altium_hier.PrjPcb` and each sheet in Altium Designer; note any prompt or repair offer, and whether the two sheet symbols, their entries and the ports show (`H-A-SCH-HIER-OPEN`, `H-A-SCH-HIER-PRJ`);
  - H2: note whether each harness connector shows with its entries and type, and whether a harness line joins it to its port or sheet entry (`H-A-SCH-HARN-OPEN`, `H-A-SCH-HARN-FILE`);
  - H3: compile the project; note the sheet tree of the Projects panel and every message (`H-A-SCH-HIER-COMPILE`, `H-A-SCH-HARN-FILE`). Expected: `altium_hier.SchDoc` on top with two children, and no message about ports, sheet entries or harnesses;
  - H4: list the nets in the Navigator panel (`H-A-SCH-HIER-NAMES`, `H-A-SCH-HARN-NETS`). Expected: exactly the nine net names of the design, `VDD` and `GND` on all three sheets, each `SPI_*` net with one pin on each module sheet;
  - H5: add a new PCB document and run "Design » Update PCB Document"; note whether the change order adds six components and nine nets and validates (`H-A-SCH-HIER-ECO`);
  - H6: build `partial.py` with `--altium-sheets modules`, open and compile it; note every message that names the entry `HOLD` (`H-A-SCH-HARN-UNUSED`);
  - H7: build `examples/altium_hier_board/design.py` with `--altium-sheets modules`, open its PCB document and run "Design » Update PCB Document"; note whether both module sheets are under the top sheet in the Projects panel after a compile, and whether the change order proposes no component and no net change (`H-A-SCH-HIER-ECO`, `H-A-SCH-HIER-ORDER`).
- A report follows "Altium author reports": tool as `AD <major>.<minor>`, the date, one generic outcome per step, no artefact, and only Fenolite's authored or built files opened. A confirmed row gets `ALTIUM-VERIFIED(author-report; AD <major>.<minor or x>; <YYYY-MM-DD>; no artefact)`.
- `docs/hypotheses.md` MUST register the nine rows `H-A-SCH-HIER-OPEN`, `H-A-SCH-HIER-PRJ`, `H-A-SCH-HIER-COMPILE`, `H-A-SCH-HIER-NAMES`, `H-A-SCH-HIER-ECO`, `H-A-SCH-HARN-OPEN`, `H-A-SCH-HARN-FILE`, `H-A-SCH-HARN-NETS` and `H-A-SCH-HARN-UNUSED`, and, after the maintainer's reports of step H7, `H-A-SCHBIN-MINI` (refuted) with its successor `H-A-SCH-HIER-ORDER`; and `docs/evidence/sources.md` MUST register S-0185 to S-0188. No file of S-0187 or S-0188 enters the repository.

#### Scenario: Golden files of the sample
- **WHEN** `uv run pytest tests/unit/lens/test_altium_hier_golden.py` runs
- **THEN** the freshly built files equal the seven committed files byte for byte, and Part H names the SHA-256 of each

#### Scenario: Sample builds without warnings
- **WHEN** `fenolite build examples/altium_hier/design.py --out B --target altium --altium-sheets modules --confirm --json` runs into an empty folder
- **THEN** the exit code is 0, `result.components` is `6`, `result.nets` is `9`, and no issue has severity `warning` or `error`

#### Scenario: Registers hold the new rows
- **WHEN** `grep -cE '^\| H-A-SCH-(HIER|HARN)-' docs/hypotheses.md` and `grep -cE '^\| S-018[5-8] ' docs/evidence/sources.md` run
- **THEN** they print `9` and `4`, and `uv run pytest tests/unit/test_hypotheses_register.py tests/unit/test_altium_rows.py` passes

#### Scenario: No reference file is committed
- **WHEN** `git ls-files | grep -ciE 'oak-hardware|battman|DM3370'` runs
- **THEN** it prints `0`

### Requirement: Hierarchy is documented
`docs/altium.md` SHALL gain a section "Sheets and harnesses", and the format facts SHALL be recorded before the code that uses them.
- The section MUST state: the option and its default; one sheet per top-level module and the file names; that nested modules are flattened; when a net gets a port and a sheet entry; that power nets are global and get neither; `Harness` and how it is drawn; that the ASCII form writes no harness; the PCB link of a part on a module sheet; and that switching the mode on a design whose PCB was already made in Altium changes the links of the parts on module sheets, which "Project » Component Links" matches again by designator (S-0164).
- `docs/formats/altium/schematic-ascii.md` MUST gain the section "Sheet symbols, sheet entries and ports", `docs/formats/altium/schematic-binary.md` the section "Additional stream and harness records", and `docs/formats/altium/project.md` the rows on module sheets, harness definition files and net scope: one row per fact, with its source, its label and its hypothesis.
- `docs/dsl.md` MUST describe `Harness`, and `docs/cli-contract.md` MUST list `--altium-sheets`, the write kind `altium_harness`, the five codes of "Hierarchy issue codes" and the five new `result` keys.
- `src/fenolite/backends/altium/PROVENANCE.md` MUST gain rows for S-0185 to S-0188, and `LEGAL-ANNEX.md` a session row.

#### Scenario: Pages hold the facts
- **WHEN** `grep -c 'RECORD=15' docs/formats/altium/schematic-ascii.md`, `grep -c 'RECORD=215' docs/formats/altium/schematic-binary.md` and `grep -c 'altium-sheets' docs/altium.md docs/cli-contract.md` run
- **THEN** each prints a non-zero count, and `uv run pytest tests/unit/test_format_facts.py tests/unit/test_provenance.py` passes

### Requirement: Copper in an Altium build
The Altium build SHALL write copper and net classes into the planned `<name>.PcbDoc` from exactly one copper source per build, and it SHALL invent no copper.
- `lens.altium.build_altium(design, …, copper=2, planes=None, copper_source=None)` MUST take the copper layer count of the script (`fenolite.dsl.Design.copper`), its planes ("Internal planes in an Altium build") and at most one `lens.altium.CopperSource(design, origin, where="")`, whose `origin` is `script` or `board`. `cli/cmd_build.py` MUST pass the count and the planes.
- The sources are: **model**, the tracks, arcs, vias and zones of `design.board` itself (tests, and routers that return model copper, c0016 and c0023); **script**, "Script copper in an Altium build"; **board**, "Copper from a routed KiCad board". A `copper_source` given together with copper in `design.board` MUST raise `ValueError`: one source per build.
- The copper layers MUST be the copper layers of `design.board.layers` when it holds any, else `F.Cu`, `B.Cu` for `copper=2` and `F.Cu`, `In1.Cu`, `In2.Cu`, `B.Cu` for `copper=4`. `lens.altium.pcb_document` MUST pass them as `PcbDocSpec.copper_layers`.
- `pcb_document` MUST pass the source's tracks, arcs, vias and zones to the spec, each net id replaced by its net name, and one `pcbdoc.NetClassSpec` per `design.circuit.netclasses` entry with the names of its nets. Net classes always come from `design`, never from a source.
- The stack values MUST come from `design.board.stackup` when it holds one copper layer per copper layer of the board, in order, with exactly one dielectric between neighbours (for four layers the middle one is the `core`, the outer two are `prepreg`); otherwise from `docboard.StackSpec.default`. A stack-up that is present and does not fit MUST give one `altium.not-lowered` info with `where` = `stackup`.
- Coordinates MUST be read in the frame of the placements, the frame in which the KiCad build writes the same script's board.
- The build's `result` MUST gain `copper`, present whenever the PCB document is planned: an object with `source` (`none`, `model`, `script` or `board`), `from` (the path given to `--copper-from`, else `null`), `layers`, `planes` (an object from layer name to net name), `tracks`, `arcs`, `vias`, `zones`, `net_classes` (counts of what is written) and `placements_from_board` (a count).
- When at least one polygon is written, the build MUST give one `altium.zones-unpoured` info that names the count and the Altium command "Tools » Polygon Pours » Repour All".
- A build of a design without copper, planes and net classes MUST give the PCB document bytes of c0035: the four copper storages stay empty.
- The same copper MUST give the same `<name>.PcbDoc` bytes from each of the three sources.

#### Scenario: Routed model
- **GIVEN** the routed sample's model: the blink design with `copper=4`, five tracks (two on `F.Cu`, one on each other copper layer), one arc, three through vias, one `GND` zone on `In1.Cu` and `B.Cu`, and the class `PWR`
- **WHEN** `build_altium` runs on it
- **THEN** `routed.PcbDoc` is planned, its summary `copper` holds `"source": "model"`, `"layers": 4`, `"planes": {}`, `"tracks": 5`, `"arcs": 1`, `"vias": 3`, `"zones": 2` and `"net_classes": 1`, `issues` holds one `altium.zones-unpoured` naming 2 polygons, and no issue is an error

#### Scenario: Layer count from the script
- **GIVEN** a blink variant with `design.board(mm(50), mm(30), copper=4)`
- **WHEN** it is built with `--target altium --dry-run --json`
- **THEN** the exit code is 0, `result.copper.layers` is 4, `result.copper.source` is `none` and every other count but `net_classes` is 0

#### Scenario: Design without copper keeps its document
- **GIVEN** a blink variant without its net class
- **WHEN** it is built with `--target altium`
- **THEN** `Vias6`, `Polygons6`, `Classes6` and `Rules6` of its `blink.PcbDoc` have `Header` 0 and an empty `Data`, and every other stream equals the same stream of the committed `tests/data/altium/blink/blink.PcbDoc`

#### Scenario: Two sources refused
- **WHEN** `build_altium` gets the routed model and a `CopperSource` as well
- **THEN** it raises `ValueError` that names both sources

### Requirement: Internal planes in an Altium build
The Altium build SHALL write each inner layer that the script declares as a plane (`design-dsl`, "Board and placements in the DSL") as an internal plane on its net, and every other inner layer as a signal layer (`altium-pcb-writer`, "Four-layer stack"; `H-A-PCB-CU-PLANE`).
- `build_altium(…, planes=…)` MUST take a mapping from layer name to net name, and `cli/cmd_build.py` MUST pass `dsl.planes(design)`. `pcb_document` MUST give the spec the stack of `pcbrecords.copper_stack(layers, planes)` with the plane nets.
- A plane on a layer that is not an inner copper layer of the board, or on a net that the design does not hold, MUST give `altium.copper-stack`.
- The model is not changed: a plane layer is a `copper` layer of the model, and no `LayerKind` is added.
- A zone layer on a plane whose net is the plane's net MUST NOT be written as a polygon: the plane stands for it. The build MUST give one `altium.plane-zone-merged` info that names those zones and layers. The zone's other layers are written as polygons.
- A track or an arc on a plane layer, or a zone layer on a plane with another net or without a net, MUST give `altium.plane-copper` (error): split planes are not written.
- Through vias and pads cross a plane unchanged; no Plane Connect or Plane Clearance rule is written, so Altium's defaults decide how they join it.

#### Scenario: Ground plane from the script
- **GIVEN** the routed sample's script with `design.board(mm(50), mm(30), copper=4, planes={"In1.Cu": gnd})` and the sample's copper
- **WHEN** `build_altium` runs
- **THEN** `result.copper.planes` is `{"In1.Cu": "GND"}`, the document's chain is 1, 39, 3, 32 with `PLANE1NETNAME=GND`, `Polygons6` holds the `B.Cu` polygon only, and `issues` holds one `altium.plane-zone-merged` naming the `GND` zone on `In1.Cu` and one `altium.plane-copper` error for the sample's track on `In1.Cu`

#### Scenario: Plane variant builds
- **GIVEN** the variant `p0` of "Routed sample and author report" (the sample with the plane above and without its track on `In1.Cu`)
- **WHEN** `build_altium` runs
- **THEN** no issue is an error, `result.copper.tracks` is 4 and `result.copper.zones` is 1

#### Scenario: Plane on an unknown net
- **WHEN** `build_altium` runs on the blink with `copper=4` and `planes={"In1.Cu": "NOPE"}`
- **THEN** `files` is empty and `issues` holds one `altium.copper-stack` naming `In1.Cu` and `NOPE`

### Requirement: Script copper in an Altium build
When the design carries resolved script copper, the Altium build SHALL write it. The design carries it as a `CopperSource` with `origin="script"`, whose `design` is the model that the KiCad build of the same script holds in memory after c0028's copper intents are resolved (`lens.build.build_design(…, copper_intents=…).design`): footprints placed, tracks and vias in the frame of the placements, nets of the script.
- **Hand-over in the build command.** When `dsl.copper(design)` is not empty and `--copper-from` is absent, `cli/cmd_build.py` MUST run `lens.build.build_design` in memory with the script's model, its placement requests, its copper layer count and the intents, for the KiCad target of the context, and MUST pass `CopperSource(<that build's design>, "script")` to `build_altium`. No file of that KiCad build is written or planned, no layout of `--out` is read, and `kicad-cli` is not run. A script without intents MUST build as before, without the in-memory build.
- **Zones.** The model given to `build_altium` MUST then hold no zone: the zones that the script declares (`design-dsl`, "Zones in the DSL") are in the source, which holds them as the KiCad build keeps them, so the build still takes one source.
- **Refusal.** When the in-memory build reports an error or returns no files, the Altium build MUST plan no file and exit 5 with those errors unchanged (`kicad.copper.*`, `kicad.frame.*`, `build.*`); `result.copper` and `result.pcb_document` are `null`. `lens.altium.refused_altium(design, *, name, issues, project_exists=False, form=…, sheets=…)` MUST give that output: no file, the given issues and the summary of a refused Altium build.
- **Nothing silent.** The warnings and infos of the in-memory build whose code starts with `kicad.copper.` or `kicad.frame.`, and its `layout.unplaced` warnings, MUST pass into `issues` unchanged, before the issues of the Altium build. So an intent that creates nothing (`kicad.copper.end-unplaced`, `kicad.copper.stitch-empty`) and dropped stitch candidates (`kicad.copper.stitch-skipped`) are reported. Its other warnings and infos concern KiCad files that are not written and MUST NOT pass.
- **Both sources.** With `--copper-from` the board wins ("Copper from a routed KiCad board"): the intents MUST NOT be resolved, and the build MUST give one `altium.not-lowered` info whose `where` is the path as given and whose message names the count and the keys of the intents. The kind "copper intents" extends the list of c0032's `altium.not-lowered` row.
- **Evidence.** With a script source the envelope MUST also combine `backends.kicad.copper.EVIDENCE` and `backends.kicad.frame.EVIDENCE`, lowest wins; the level stays `INFERRED` and the build stays experimental.
- The build MUST check a script source as "Copper from a routed KiCad board" checks a board (components, footprints, pad nets, outline, copper nets), so a source built from another script is refused. It MUST take the source's placements and give no `altium.placement-from-board` for this origin.
- The lens MUST NOT import `fenolite.dsl` or resolve intents itself: `lens.altium` receives a model (`package-layering`).
- Via types, layers and planes follow "Copper issue codes" and "Internal planes in an Altium build".
- `result.copper.source` MUST be `script`.

#### Scenario: Script source equals the committed sample
- **GIVEN** the KiCad build of the routed sample's script in memory, with the sample's copper put into its model
- **WHEN** `build_altium` runs on the script's model with that design as a `CopperSource` of origin `script`
- **THEN** `result.copper.source` is `script`, no issue is an error, and `routed.PcbDoc` equals the committed `tests/data/altium/routed/routed.PcbDoc` byte for byte

#### Scenario: Source of another script refused
- **GIVEN** the same source, and a script whose `R1` has another footprint
- **WHEN** `build_altium` runs
- **THEN** `files` is empty and `issues` holds one `altium.copper-board-mismatch` whose `where` is `R1`

#### Scenario: Routed blink built for Altium
- **WHEN** `fenolite build examples/blink_routed/design.py --out B --target altium --confirm --json` runs
- **THEN** the exit code is 0, `result.copper` holds `"source": "script"`, `"from": null`, `"tracks": 11`, `"arcs": 0`, `"vias": 7` and `"placements_from_board": 0`, `evidence.hypotheses` contains `H-G-FRAME-ROUTE`, `B` holds no `.kicad_pcb`, and `B/blink_routed.PcbDoc` read back holds 11 tracks and 7 vias on the nets `LED_DRV`, `LED_A` and `GND`

#### Scenario: Script source and board source give the same bytes
- **GIVEN** a confirmed KiCad build of `examples/blink_routed/design.py` in `K`
- **WHEN** the script is built with `--target altium` into `A`, and into `B` with `--copper-from K/blink_routed.kicad_pcb`
- **THEN** `A/blink_routed.PcbDoc` equals `B/blink_routed.PcbDoc` byte for byte, the second build reports `"source": "board"` and one `altium.not-lowered` info that names 4 copper intents and the board's path, and the first reports no such info

#### Scenario: Intent error refuses the Altium build
- **GIVEN** a variant of the routed blink whose track `led_drv` ends at `D1` pad `2` instead of `R1` pad `1`
- **WHEN** it is built with `--target altium --confirm --json`
- **THEN** the exit code is 5, `issues` holds `kicad.copper.net-conflict`, `result.copper` is `null` and nothing is written

#### Scenario: Intent to a staged part is reported
- **GIVEN** a variant of the routed blink without `d1.place(…)`
- **WHEN** it is built with `--target altium --dry-run --json`
- **THEN** the exit code is 0, `issues` holds one `layout.unplaced` naming `D1` and two `kicad.copper.end-unplaced` (the keys `gnd` and `led_a`), and `result.copper` holds `"tracks": 4` and `"vias": 5`

#### Scenario: Zone and intents in one script
- **GIVEN** a variant of the routed blink with `design.zone(gnd, layers=("B.Cu",), clearance=mm(0.3))`
- **WHEN** it is built with `--target altium --dry-run --json`
- **THEN** the exit code is 0 and `result.copper` holds `"source": "script"`, `"tracks": 11`, `"vias": 7` and `"zones": 1`

#### Scenario: Script without intents is unchanged
- **WHEN** `fenolite build examples/blink_2layer/design.py --out B --target altium --dry-run --json` runs
- **THEN** `result.copper.source` is `none`, and the planned `blink.PcbDoc` equals the committed `tests/data/altium/blink/blink.PcbDoc`

### Requirement: Copper from a routed KiCad board
`fenolite build DESIGN.py --out DIR --target altium --copper-from BOARD.kicad_pcb` SHALL copy the tracks, arcs, vias and zones of a routed KiCad board of the same design into `<name>.PcbDoc`, after checking that the board matches the design. This requirement extends "Altium build target" and `design-dsl` "Build command".
- `--copper-from` MUST take one path. Without `--target altium` it MUST be a usage error (exit 2, `FEN-2001`); a path that is not a file MUST be a usage error too. `cmd_build` MUST read the board with `fenolite.backends.kicad.pcb.read_board` in the same process: a board the reader refuses exits 3 with the reader's `FEN-3xxx` code, and the reader's warnings and infos pass into `issues` unchanged. `kicad-cli` is not run. `cmd_build` MUST pass `CopperSource(<the read design>, "board", <the path as given>)`, and `--copper-from` wins over any other source.
- **Components.** Each design component with a footprint link MUST match exactly one footprint of the board: by the `fenolite.path` property when the board's footprint holds it, else by reference. A component without a match, a board footprint without a component, or two footprints for one component MUST give `altium.copper-board-mismatch` with `where` = the component path or the board reference.
- **Footprints.** A matched footprint MUST have the component's footprint link as its `lib_ref`, and the same pad numbers at the same positions in the footprint's own frame as the definition written to `<name>.PcbLib`; else `altium.copper-board-mismatch` with `where` = the component path.
- **Placements.** The board's placements win: every matched component MUST be written at the board footprint's position, rotation, side and lock, and none is staged. The copper is only right relative to the footprints as the board places them, and the exported tool project is the source of truth for layout (`design-model`, "Layout authority"). When a placement differs from the script's request, or the script requests none, the build MUST give one `altium.placement-from-board` info that names the refs.
- **Outline.** The bounding box of the board's `Edge.Cuts` graphics (or of its `Board.outline`) MUST equal the bounding box of the design's outline; else `altium.copper-board-mismatch` with `where` = `outline`.
- **Nets.** Every pad of a matched footprint MUST be on the net of the same name as the design puts its pin on, or on none in both; else `altium.copper-board-mismatch` with `where` = `<ref>.<pad number>`. A net of the board whose name starts with `unconnected-(` and that holds one pad counts as no net: a board built beside a schematic names the pad of each unconnected pin as KiCad does (`design-dsl`, "Board follows the schematic"). A track, arc, via or zone on a net whose name the design does not hold MUST give one `altium.copper-net-missing` per net name, naming the count of items and the layer and position of the first. Copper without a net is copied without a net.
- **Copper.** Via types, layers and planes follow "Copper issue codes" and "Internal planes in an Altium build"; a zone's `fills` are not copied. Keep-outs, texts, graphics and holes of the board are not copied and give one `altium.not-lowered` info per kind with `where` = the path.
- Every issue of this requirement MUST name the path, and an issue about a copper item MUST name its layer and its position in millimetres from the outline's corner.
- A copper source given while the PCB document is not planned MUST give `altium.copper-no-document` (error).
- `result.copper.source` MUST be `board`, `result.copper.from` the path as given, and `result.copper.placements_from_board` the number of components placed from the board. The result MUST also hold `copper_input`, the board's `path` (as given), `sha256`, the kind `kicad-board` and its `format_version`: the envelope's `input` is one object in contract v0 (`schemas/fenolite.envelope.v0.json`) and stays the script.
- The bytes MUST NOT depend on the ids or uuids of the board's items, on `--seed`, `--timestamp` or `PYTHONHASHSEED`.

#### Scenario: Copper copied from the board
- **GIVEN** `routed.kicad_pcb`, the KiCad build of the routed sample's script with the sample's copper, written by a test helper into a temporary folder beside the script `design.py`
- **WHEN** `fenolite build design.py --out B --target altium --copper-from routed.kicad_pcb --confirm --json` runs
- **THEN** the exit code is 0, `result.copper` holds `"source": "board"`, `"tracks": 5`, `"arcs": 1`, `"vias": 3`, `"zones": 2` and `"placements_from_board": 3`, no `altium.placement-from-board` is given, and `B/routed.PcbDoc` equals the committed `tests/data/altium/routed/routed.PcbDoc` byte for byte

#### Scenario: Moved part follows the board
- **GIVEN** the same board with `R1` moved by 1 mm, together with the track ends on its pads
- **WHEN** the build runs with `--copper-from`
- **THEN** the exit code is 0, `R1`'s component record is at the board's position, and `issues` holds one `altium.placement-from-board` naming `R1`

#### Scenario: Mismatches are located
- **GIVEN** boards derived from `routed.kicad_pcb`: one without `D1`, one whose `R1` has another footprint, one whose `R1` pad `2` is on `GND`, one with a track on a net `EXTRA`, and one with a blind via; and the unchanged board given to a variant of the script with `copper=2`
- **WHEN** each is given to `--copper-from` with `--dry-run --json`
- **THEN** each build exits 5 with no planned file; the first five give one error each, `altium.copper-board-mismatch` with `where` `D1`, `R1` and `R1.2`, `altium.copper-net-missing` naming `EXTRA` and `altium.via-unsupported`; the last gives `altium.copper-layer` errors that name `In1.Cu` and `In2.Cu`; and every message names the board's path

#### Scenario: Option without the Altium target
- **WHEN** `fenolite build examples/blink_2layer/design.py --out B --copper-from x.kicad_pcb --dry-run` runs
- **THEN** the exit code is 2, stderr carries `FEN-2001`, and nothing is written

#### Scenario: Board built beside a schematic
- **GIVEN** the blink built for KiCad with its schematic, so the pads of its 29 unconnected pins are on `unconnected-(…)` nets
- **WHEN** `fenolite build examples/blink_2layer/design.py --out A --target altium --copper-from <that board> --dry-run --json` runs
- **THEN** the exit code is 0 and `issues` holds no `altium.copper-board-mismatch`

### Requirement: Copper round trip oracle
`tests/kicad/altium/test_copper_from_oracle.py` SHALL prove with `kicad-cli` that copper copied by `--copper-from` survives the way back (S-0161, S-0166, S-0020; `H-A-PCB-CU-ROUNDTRIP`).
- The test MUST write the routed sample's KiCad board (`lens.build.build_design` and the sample's copper) to a temporary folder, build the Altium project from it with `--copper-from`, import the written `routed.PcbDoc` with `kicad-cli pcb import --format altium`, and read both boards with `fenolite.backends.kicad.pcb.read_board`.
- Relative to each board's outline corner and within 10 nm, the imported board MUST hold every track, arc and via of the source board with its layer, net name, geometry, width or sizes, and every zone layer with its net and outline; and it MUST hold no other track, arc, via or zone. Every footprint MUST be at the source's position, rotation and side.
- Zone fills, net classes and uuids are not compared, and the test MUST say why.
- The test MUST be skipped on `kicad-cli` 9.x and required in the `kicad-10` job. A pass on 10.0.6 gives `H-A-PCB-CU-ROUNDTRIP` the level `ORACLE-VERIFIED(kicad-cli)`; it settles no Altium row.

#### Scenario: Board to Altium and back
- **WHEN** `uv run pytest tests/kicad/altium/test_copper_from_oracle.py` runs with `kicad-cli` 10.0.6
- **THEN** the imported board's copper equals the source board's copper item for item, on four copper layers, with no error in the report

### Requirement: Copper issue codes
`lens.altium.ALTIUM_ISSUE_CODES` SHALL gain these rows. This requirement extends c0032's "Altium build issue codes", whose closed-set rule and scenarios hold for them. The lens MUST find each case before `write_pcbdoc` runs, so no `ValueError` of the writer reaches the user. The rows apply to copper of every source.

| code | severity | when |
|---|---|---|
| `altium.copper-stack` | error | the count of the board's copper layers differs from `copper`, a copper layer is named twice, or a plane names a layer that is not an inner layer or a net the design does not hold |
| `altium.copper-layer` | error | a track, arc, via or zone names a layer outside the board's copper layers |
| `altium.via-unsupported` | warning | a via is a micro via; it is not written and the build goes on (change c0085) |
| `altium.zone-unsupported` | error | a zone has fewer than three outline points (an outline kept as an opaque slot) |
| `altium.copper-invalid` | error | a track of zero length, a width of 0 or less, a drill not below its diameter, a via that does not span two different copper layers, or a net id that names no net |
| `altium.plane-copper` | error | a track or arc lies on a plane layer, or a zone on a plane layer has another net than the plane |
| `altium.copper-board-mismatch` | error | a copper source does not match the design: a component, a footprint, a pad net or the outline |
| `altium.copper-net-missing` | error | copper of a source is on a net whose name the design does not hold |
| `altium.copper-no-document` | error | a copper source is given and the PCB document is not planned |
| `altium.zones-unpoured` | info | polygons are written without poured copper |
| `altium.plane-zone-merged` | info | a zone on a plane layer with the plane's net is left to the plane |
| `altium.placement-from-board` | info | components are placed as the board of `--copper-from` places them, not as the script requests |

- One issue MUST be given per entity (per net name for `altium.copper-net-missing`), with the entity id, component path or net name in `where` and the layer or via type in the message.
- With an error the build MUST write no file, as c0032 rules. Nothing is dropped to make a document fit; a micro via is the one item left out, with its warning, whose `where` is `via/<id>`.

#### Scenario: Closed set with the copper rows
- **WHEN** `uv run pytest tests/unit/lens/test_altium_issues.py -k closed_set` runs
- **THEN** every row of this table is produced by at least one test with its severity

#### Scenario: Micro via left out
- **GIVEN** the routed model with one more via of `via_type="micro"` between `F.Cu` and `In1.Cu`
- **WHEN** `build_altium` runs
- **THEN** the files are written, `issues` holds one `altium.via-unsupported` warning whose `where` is `via/<id>`, and `result.pcb.not_lowered` is `{"via": 1}`

#### Scenario: Blind via refused
- **GIVEN** the routed model with one more via of `via_type="blind"` whose two layers are both `F.Cu` (a blind via with a span of two different copper layers is written since this change)
- **WHEN** `build_altium` runs
- **THEN** `files` is empty and `issues` holds one `altium.copper-invalid` error whose `where` is the via's id

#### Scenario: Copper on a missing layer
- **GIVEN** the routed model built with `copper=2`
- **WHEN** `build_altium` runs
- **THEN** `files` is empty and `issues` holds three `altium.copper-layer` errors: the track on `In1.Cu`, the track on `In2.Cu` and the zone

#### Scenario: Three copper layers refused
- **GIVEN** a model whose `board.layers` holds the copper layers `F.Cu`, `In1.Cu` and `B.Cu`
- **WHEN** `build_altium` runs
- **THEN** with `copper=4` `files` is empty and `issues` holds one `altium.copper-stack` that names the three layers

#### Scenario: Source without a document
- **GIVEN** a blink variant without `design.board(...)` and a `CopperSource`
- **WHEN** `build_altium` runs
- **THEN** `files` is empty and `issues` holds `altium.copper-no-document`

### Requirement: Copper evidence
`pcbdoc.EVIDENCE` SHALL also name `H-A-PCB-CU-KICAD`, `H-A-PCB-CU-ROUNDTRIP`, `H-A-PCB-CU-TRACK`, `H-A-PCB-CU-VIA`, `H-A-PCB-CU-STACK`, `H-A-PCB-CU-PLANE`, `H-A-PCB-CU-REPOUR`, `H-A-PCB-CU-CLASS`, `H-A-PCB-CU-RULES` and `H-A-PCB-CU-VIEWER`, so `PCB_BUILD_EVIDENCE` and `ALTIUM_BUILD_EVIDENCE` name them under c0035's "PCB evidence and capabilities".
- The levels MUST stay `INFERRED`. `H-A-PCB-CU-KICAD` or `H-A-PCB-CU-ROUNDTRIP` at `ORACLE-VERIFIED(kicad-cli)`, or an author-report row, never raises the build's level.
- With `--copper-from`, the envelope MUST also combine the evidence of the KiCad board reader, lowest wins.
- `docs/hypotheses.md` MUST register the ten rows with backend `altium`, and `tests/unit/test_altium_rows.py` MUST check them.

#### Scenario: Copper rows in the envelope
- **WHEN** the routed model is built
- **THEN** `evidence.level` is `INFERRED` and `evidence.hypotheses` contains `H-A-PCB-CU-REPOUR`, `H-A-PCB-CU-STACK` and `H-A-PCB-CU-PLANE`

#### Scenario: Copper rows registered
- **WHEN** `grep -cE '^\| H-A-PCB-CU-' docs/hypotheses.md` runs
- **THEN** it prints `10`

### Requirement: Routed sample and author report
The routed sample SHALL be committed, checked and handed to the maintainer with a protocol.
- `tests/_altium_copper.py` MUST build the sample's model from data authored for Fenolite: the blink design named `routed` with `copper=4`, plus the copper of "Copper in an Altium build", scenario "Routed model". It MUST also give the same sample as a KiCad-built model and as a written `.kicad_pcb` text, for the script and board sources. No value comes from another project.
- The five files of its Altium build MUST be committed under `tests/data/altium/routed/`, declared in `tests/data/MANIFEST.toml` with `origin = "authored"`, and compared byte for byte with a fresh build by `tests/unit/lens/test_altium_copper_golden.py`; `FENOLITE_GOLDEN_WRITE=1` rewrites them.
- The blink golden files of c0035 MUST be rebuilt once: `blink.PcbDoc` now holds the class `PWR` and its rules. The other four blink files and every file of `tests/data/altium/sample/` MUST keep their bytes.
- With `FENOLITE_ALTIUM_VARIANTS=<folder>`, the golden test MUST also write the bisection variants there, never into the repository: `c0` two layers with tracks and an arc; `c1` adds vias; `c2` the stack of four signal layers with inner tracks; `c3` adds the polygons; `c4` adds the net class; `c5` adds the rules (the committed sample); and `p0`, the sample with `In1.Cu` as a plane on `GND` and without its track on `In1.Cu`.
- `docs/evidence/altium-pcb.md` MUST gain Part C, under the rules of c0035's "PCB author reports":
  - C1 open `routed.PcbDoc` in Altium Designer without a repair prompt; the tracks, the arc and the vias show with their nets, and routed nets show no connection line (`H-A-PCB-CU-TRACK`, `H-A-PCB-CU-VIA`);
  - C2 the Layer Stack Manager lists Top Layer, Mid-Layer 1, Mid-Layer 2 and Bottom Layer as signal layers with three dielectrics (`H-A-PCB-CU-STACK`);
  - C3 the two polygons show as outlines; "Repour All" fills them, and the `GND` pads connect (`H-A-PCB-CU-REPOUR`);
  - C4 the class `PWR` lists `GND` and `VIN`, and the rules editor shows the five rules (`H-A-PCB-CU-CLASS`, `H-A-PCB-CU-RULES`);
  - C5 the Altium 365 Viewer shows the copper on four layers (`H-A-PCB-CU-VIEWER`);
  - C6 open `p0/routed.PcbDoc`: the Layer Stack Manager lists Internal Plane 1 between Top Layer and Mid-Layer 2, the plane is on `GND`, and the `GND` pads and vias that cross it show no connection line (`H-A-PCB-CU-PLANE`).
  - When a step fails, the page tells the maintainer to open `c0` to `c5` in order and report the first that fails.
- Each step MUST name the SHA-256 of its files (for C6 the SHA-256 of `p0/routed.PcbDoc`, which the test rebuilds), and the page MUST list the expected tracks, vias and polygons as (layer, net, geometry in mm).

#### Scenario: Golden routed files
- **WHEN** `uv run pytest tests/unit/lens/test_altium_copper_golden.py tests/unit/lens/test_altium_pcb_golden.py` runs
- **THEN** fresh builds equal the five routed files and the five blink files, and `git diff --exit-code tests/data/altium/sample/` exits 0

#### Scenario: Variants stay outside the repository
- **WHEN** the golden test runs with `FENOLITE_ALTIUM_VARIANTS` set to an empty temporary folder
- **THEN** the folder holds `c0` to `c5` and `p0`, each with a `routed.PcbDoc`, `c5/routed.PcbDoc` equals the committed one, and `git status --short` lists no new file

#### Scenario: Protocol names the routed bytes
- **WHEN** `uv run pytest tests/unit/lens/test_altium_copper_golden.py -k protocol` reads the page
- **THEN** Part C names the SHA-256 of every committed routed file and of `p0/routed.PcbDoc`, and its copper table equals the sample model's copper

### Requirement: Copper is documented
The copper of the PCB document SHALL be documented as c0035's "PCB writers are documented" requires.
- `docs/formats/altium/pcb-copper.md` MUST hold, in the fact-table form that `tests/unit/test_format_facts.py` checks: the routed track and arc rows, the via record with its offsets, the polygon keys and the unpoured state, the stack keys of a signal mid layer and of an internal plane, the plane net key and what a saved plane holds besides, the class and rule records, the oracle observations, and "Fenolite's choices". A row below `ORACLE-VERIFIED(kicad-cli)` MUST name an `H-A-PCB-CU-*` hypothesis. A row resting on S-0150 MUST name version 1 and its commit. A row that rests on the Altium-saved documents (S-0172, S-0174, S-0175, S-0176, S-0199, S-0200) MUST say that the files stay outside the repository.
- `docs/formats/altium/pcb-document.md` MUST move `Vias6`, `Polygons6`, `Classes6` and `Rules6` out of its list of empty storages and drop "No routing, vias, zones, rules, classes or polygons".
- `docs/altium.md` MUST gain a section "Copper": what is written, the layer table with signal layers and planes, the unpoured polygons and the repour step, the refusals, and the three routes by which copper reaches the document (script copper with c0028, `--copper-from`, and routers with c0016 and c0023), with the checks of `--copper-from` and the rule that the board's placements win. `docs/cli-contract.md` MUST list `--copper-from`, `result.copper` and the twelve codes. `PROVENANCE.md` and `docs/evidence/sources.md` MUST list S-0195 to S-0200.

#### Scenario: Copper fact page checked
- **WHEN** `uv run pytest tests/unit/test_format_facts.py tests/unit/test_provenance.py` runs
- **THEN** it checks `pcb-copper.md` and passes

#### Scenario: Copper routes documented
- **WHEN** `docs/altium.md` is read
- **THEN** it names "Repour All", `Mid-Layer 1`, `Internal Plane 1`, `--copper-from`, `altium.via-unsupported`, `altium.copper-board-mismatch` and `altium.zones-unpoured`

### Requirement: Classes in an Altium build
`lens.altium.build_altium` SHALL write the net classes of the design into the schematic and the project file, and the component classes of the module sheets into the PCB document, so that "Design » Update PCB Document" proposes no class change (`H-A-ECO-NETCLASS`, `H-A-ECO-COMPCLASS`, `H-A-ECO-ROOMS`).
- A design with a net class MUST get the directives of "Net class directives on the sheet" on every sheet, in both sheet modes and in both schematic forms, with or without a PCB document, and the `[PrjClassGen]` section of "Class generation keys of the project file".
- A build that writes a PCB document or module sheets MUST get the three class keys in the section of every schematic document, and a PCB document MUST hold the records of "Component class records": one class per sheet that holds a component, in both sheet modes.
- The net classes of the schematic and of the PCB document MUST agree: each class of `Classes6` with `KIND=0` holds exactly the nets that carry a directive of that class, for every net that has a pin.
- A net class name that the schematic cannot hold MUST give the issue `altium.text-unwritable` with severity `error`, whether or not a PCB document is planned, and no file.
- Without a PCB document, the issue `altium.not-lowered` for net classes MUST say that their rule values are kept in the model only: the members are in the schematic.
- A design without a net class, built with the single sheet and without a PCB document, MUST keep every byte it had before this change.
- No room and no "Supply Nets" rule is written (`H-A-ECO-SUPPLY`; "Change order differences are documented").

#### Scenario: Board example
- **WHEN** `fenolite build examples/altium_hier_board/design.py --out B --target altium --altium-sheets modules --confirm --json` runs into an empty folder
- **THEN** the exit code is 0; the sheets read back hold `GND` and `VIN` in the class `PWR`; `altium_hier_board.PrjPcb` ends with the `[PrjClassGen]` section and holds `ClassGenCCAutoRoomEnabled=0` three times; and `Classes6` of the PCB document holds `PWR`, `driver` and `led`

#### Scenario: Flat routed sample
- **WHEN** the routed sample is built with the single sheet
- **THEN** `routed.SchDoc` holds two directives of the class `PWR`; `routed.PrjPcb` holds the three class keys once, in the section of `routed.SchDoc`, and ends with the `[PrjClassGen]` section; and `Classes6` of `routed.PcbDoc` holds the net class `PWR` and the component class `routed` with `D1`, `R1` and `U1`

#### Scenario: Net class name the schematic cannot hold
- **WHEN** a design whose net class is named `=PWR` is built without a board
- **THEN** the build reports `altium.text-unwritable` naming the class and writes no file

#### Scenario: Design without a class keeps its bytes
- **WHEN** `uv run pytest tests/unit/lens/test_altium_golden.py tests/unit/lens/test_altium_binary_golden.py tests/unit/lens/test_altium_schlib_golden.py tests/unit/lens/test_altium_no_connect_golden.py` runs
- **THEN** it passes without any golden file of those samples being rewritten

### Requirement: Change order sample and author report
The golden files SHALL be rebuilt, and `docs/evidence/altium-pcb.md` SHALL hold Part E, the protocol of the change order in Altium Designer.
- The golden files whose design holds a net class, module sheets or a board MUST be rebuilt with `FENOLITE_GOLDEN_WRITE=1`: the schematic, the project file and the document of the blink and routed samples, and `altium_hier.PrjPcb`. Every other golden file MUST keep its bytes, and the pages that name a SHA-256 of a rebuilt file, or of the plane variant `p0`, MUST name the new one. A sentence of an earlier report keeps the digest it reported.
- `tests/unit/lens/test_altium_eco.py` MUST build the board example with module sheets and the routed sample, and check the scenarios of "Classes in an Altium build" on the files read back.
- Part E MUST hold these steps, each with the hypotheses it settles, on a fresh copy of each sample:
  - E1: open the project of the board example and run "Project » Validate PCB Project"; both module sheets are under the top sheet (`H-A-ECO-PRJ-KEYS`, `H-A-SCH-HIER-ORDER`);
  - E2: "Project » Project Options", tab "Class Generation": "Generate Net Classes" under "User-Defined Classes" is ticked, and each sheet has "Component Classes" ticked and "Generate Rooms" unticked (`H-A-ECO-PRJ-KEYS`);
  - E3: from the top sheet run "Design » Update PCB Document"; the change order proposes no removal of a net class, no component class and no room (`H-A-ECO-NETCLASS`, `H-A-ECO-COMPCLASS`, `H-A-ECO-ROOMS`); note every group it still proposes, the "Supply Nets" rules included (`H-A-ECO-SUPPLY`);
  - E4: the same three steps on the routed sample, a single sheet: no net class change, no component class and no room (`H-A-ECO-NETCLASS`, `H-A-ECO-SHEETCLASS`).
- A report follows "PCB author reports" of c0035: tool as `AD <major>.<minor>`, the date, one generic outcome per step, no artefact, and only Fenolite's built files opened.
- The report of 2026-10-04 (AD 26.5) MUST be recorded under "Reports": the change order of the board example lists only two "Supply Nets" rules; that of the routed sample, then without class key and component class, lists the component class `routed`, a room and two "Supply Nets" rules, and no net class removal.
- `docs/hypotheses.md` MUST register the six rows `H-A-ECO-NETCLASS`, `H-A-ECO-PRJ-KEYS`, `H-A-ECO-COMPCLASS`, `H-A-ECO-ROOMS`, `H-A-ECO-SUPPLY` and, after that report, `H-A-ECO-SHEETCLASS`; the first five carry the report's label and the sixth stays pending until step E4 is repeated. `docs/evidence/sources.md` MUST register S-0310 to S-0313. The project file of S-0313 and the files of S-0187, S-0188, S-0172, S-0175, S-0199 and S-0200 never enter the repository.

#### Scenario: Golden files after the rebuild
- **WHEN** `uv run pytest tests/unit/lens -k "golden"` runs
- **THEN** every fresh build equals its committed files, and `git diff --stat HEAD~ -- tests/data/altium/sample tests/data/altium/no_connect tests/data/altium/kicad_example` lists no file

#### Scenario: Registers hold the new rows
- **WHEN** `grep -cE '^\| H-A-ECO-' docs/hypotheses.md` and `grep -cE '^\| S-031[0-3] ' docs/evidence/sources.md` run
- **THEN** they print `6` and `4`, and `uv run pytest tests/unit/test_hypotheses_register.py tests/unit/test_altium_rows.py` passes

#### Scenario: Protocol names the steps
- **WHEN** `grep -cE '^- \*\*E[1-4]' docs/evidence/altium-pcb.md` runs
- **THEN** it prints `4`

### Requirement: Change order differences are documented
`docs/altium.md` SHALL hold a section "Change order" that says what the build writes for it and what Altium may still propose.
- It MUST say that a net class is declared by a directive on each of its nets and by the project option, and that every sheet with a part gives a component class in the PCB document, named after the module or after the sheet.
- It MUST list the remaining differences with their reason: the "Supply Nets" rules, which Altium suggests for each net with a power port when its advanced setting `Schematic.AutoGenerateSupplyNetsRule` is on (S-0185, S-0312), which only add rules, and which Fenolite does not write because no permitted source holds the record; rooms, which the project key turns off and which Fenolite does not write; and the component class and room of a flat build, pending the repeat of step E4.
- It MUST say that an existing `<name>.PrjPcb` is kept, so the class keys reach only a project file that the build writes.
- The row `altium.not-lowered` of the issue table MUST match the new message for net classes.

#### Scenario: Section exists
- **WHEN** `grep -c "^## Change order" docs/altium.md` and `grep -c "AutoGenerateSupplyNetsRule" docs/altium.md` run
- **THEN** each prints `1` or more

### Requirement: Script copper oracle
`tests/kicad/altium/test_script_copper_oracle.py` SHALL prove with `kicad-cli` that the copper a script declares reaches the Altium document (S-0161, S-0166; `H-A-PCB-CU-KICAD`).
- The test MUST build `examples/blink_routed/design.py` with `fenolite build --target altium --confirm`, import the written `blink_routed.PcbDoc` with `kicad-cli pcb import --format altium`, and read the imported board with `fenolite.backends.kicad.pcb.read_board`.
- The expected copper MUST be the tracks and vias of `lens.build.build_design(…, copper_intents=dsl.copper(design)).design`, the script's intents resolved, never the Altium document read by Fenolite.
- Relative to each board's outline corner and within 10 nm, the imported board MUST hold every expected track with its layer, net name, end points and width, and every expected via with its position, net name, diameter, drill and through span, and MUST hold no other track, arc, via or zone. Every footprint MUST be at the script's position, rotation and side.
- Net classes and uuids are not compared, and the test MUST say why.
- The test MUST be skipped on `kicad-cli` 9.x (no `pcb import`, S-0166) and carries the `needs_kicad` marker. A pass settles no Altium row.

#### Scenario: Script to Altium and back
- **WHEN** `uv run pytest tests/kicad/altium/test_script_copper_oracle.py` runs with `kicad-cli` 10.0.6
- **THEN** the import exits 0 with no error in its report, and the imported board holds the 11 tracks and 7 vias of the script, item for item, and the three footprints at their placements

### Requirement: Script copper sample and author report
`docs/evidence/altium-pcb.md` SHALL gain step C7 in Part C, under the rules of c0035's "PCB author reports", so the maintainer can check a document whose copper comes from a script.
- **C7** MUST name the build command of `examples/blink_routed/design.py` for the Altium target, the SHA-256 of the `blink_routed.PcbDoc` it gives, and the expected result in Altium Designer: no repair prompt; 11 tracks and 7 through vias on two copper layers, on the nets `LED_DRV`, `LED_A` and `GND`; no connection line on those three nets. It names `H-A-PCB-CU-TRACK` and `H-A-PCB-CU-VIA` and MUST say that it registers no new row and stays pending until reported.
- The sample is built outside the repository; no file of it is committed.
- `docs/altium.md`, section "Copper", MUST describe route 1 as it works: the script's `track`, `via` and `stitch` calls reach the document with `--target altium`, the refusal on an intent error, and the rule that `--copper-from` wins. It MUST NOT say that script copper waits for another change. `docs/cli-contract.md` MUST say the same for `result.copper.source` `script`.

#### Scenario: Protocol names the script copper bytes
- **WHEN** `uv run pytest tests/unit/cli/test_build_altium_script_copper.py -k protocol` builds the routed blink for Altium and reads the page
- **THEN** step C7 names the SHA-256 of the fresh `blink_routed.PcbDoc`

#### Scenario: Route 1 is documented as working
- **WHEN** `docs/altium.md` is read
- **THEN** its section "Copper" names `Design.track`, `examples/blink_routed` and `kicad.copper.`, and `grep -c "when it lands" docs/altium.md` prints `0`

### Requirement: Rule minimums in an Altium build
The Altium build SHALL write the rules of `design.rules` into the PCB document where Altium has an exact rule for them ("Rules in an Altium build"), and it SHALL report the others instead of dropping them silently.
- For each rule of `design.rules` that is not written, `lens.altium.build_altium` MUST add exactly one `altium.not-lowered` warning with `where` = `design-rules/<kind>`, whose message names the rule by `Rule.name` with its selector and the reason. A `clearance` or `edge_clearance` minimum is written; a `track_width`, `via_diameter`, `via_drill` or `hole_size` minimum gives `value-unsupported`, because Altium's record also holds a maximum (and a preferred value).
- The warnings MUST be given with and without a planned PCB document: the filter that removes the `board`, `placements` and `rules` kinds when the document is written ("Copper in an Altium build") MUST NOT remove them. Without a document every rule is reported, with the reason `no-document` where the rule would have been written.
- Every written file except `.fenolite/rules.json`, which holds the rules, the PCB document, whose `Rules6` holds the written ones, and `.fenolite/build.json`, which lists the document's hash, MUST be byte-identical with and without them.
- A design without rules MUST give no such issue.

#### Scenario: Minimums are written or reported
- **GIVEN** a design with a class `PWR`, `design.rules.minimum(clearance=mm(0.15))` and `design.rules.minimum(track_width=mm(0.5), netclass="PWR")`
- **WHEN** `uv run pytest tests/unit/lens/test_build_minimums.py -k altium` builds it for Altium as the blink with its PCB document
- **THEN** the build has one `altium.not-lowered` warning, with `where == "design-rules/track_width"`, naming `min_track_width_PWR` and `value-unsupported`, and only `blink.PcbDoc`, `.fenolite/build.json` and `.fenolite/rules.json` differ from the same build without the two `minimum()` calls

#### Scenario: Minimums are reported, not written
- **GIVEN** the same design without a PCB document
- **WHEN** `uv run pytest tests/unit/lens/test_build_minimums.py -k altium` builds it for Altium
- **THEN** the build has the warning of `min_track_width_PWR` and one with `where == "design-rules/clearance"` naming `min_clearance` and `no-document`, no rule is written, and only `.fenolite/rules.json` differs from the same build without the two `minimum()` calls

#### Scenario: No rules, no report
- **GIVEN** the blink design as committed
- **WHEN** it is built with `--target altium`
- **THEN** no issue has a `where` that starts with `design-rules`

### Requirement: Typed interfaces in an Altium build
An Altium build SHALL keep interfaces of the kinds `i2c`, `spi`, `uart` and `usb2` (`design-dsl`, "Typed interfaces in the DSL") in the model only, and SHALL report them with the `altium.not-lowered` info that names the design's diff pairs.
- The info for the kind `interfaces` MUST name every `diff_pair`, `i2c`, `spi`, `uart` and `usb2` interface, sorted by name; with none of them, no such info is given.
- Their nets MUST be written as plain nets; harness lowering MUST NOT take them, and every planned file outside `.fenolite/` MUST equal, byte for byte, the file of the same design without them; `.fenolite/circuit.json` holds the interfaces.

#### Scenario: I2C in an Altium build
- **GIVEN** `examples/altium_sample/design.py` and a variant that adds `I2C(sda, scl)` on two of its signal nets
- **WHEN** both are built with `--target altium --dry-run --json`
- **THEN** the variant's planned files outside `.fenolite/` equal the example's byte for byte, and its `issues` hold one `altium.not-lowered` info for `interfaces` naming the I2C interface

### Requirement: Pin maps in an Altium build
An Altium build SHALL apply `Component.pin_pad_map` to the PCB document and write it to the schematic: a pad of a placed component MUST carry the net of the pin that the map names for it, a pin outside the map naming the pad of its own number, and the schematic MUST hold the map ("Pin map records of a footprint model" of `altium-schematic-writer`). Before this requirement a pad carried the net of the pin of its own number, whatever the map said, which the requirement "Per-component pin-to-pad mapping" of `design-dsl` did not allow.
- **Copper.** The check of a copper source (script copper and `--copper-from`) MUST read the wanted net of each pad through the same map (`altium_copper.pad_net_names`, which the PCB document reads too): a design with a map and tracks on its mapped part builds; the KiCad board of the same script is accepted as copper source; a board that was routed for another assignment of the pads is refused with `altium.copper-board-mismatch`, whose message names the net the design puts on the pad.
- **Issue code.** `altium.pin-pad-map-invalid` (error) joins the closed table `lens.altium.ALTIUM_ISSUE_CODES`: one issue for each pair of a map that names a pin the component does not hold, for each pair that names a pad the resolved footprint does not hold, and for each pad of two pins (below), with `where` set to the component's path. A build with this issue MUST exit 5 and write nothing.
- **A pad of two pins.** A pad that two pins of the component stand for, one by the map and one by its own number (`pad_map={"1": "2"}` on a part that has a pin `2`, and its mirror `{"2": "1"}`), MUST give one `altium.pin-pad-map-invalid` that names the pad and both pins, also when both pins are on one net. This keeps the two targets alike: "Per-component pin-to-pad mapping" of `design-dsl` refuses a "duplicate physical target", and the KiCad build refuses such a map with `build.pin-pad-map-invalid` in both cases (measured at the tag `v0.2.0`). The release 0.2.0 built such a script for Altium, ignoring the map. The form in which the map itself lists one pad for two pins never reaches a build: `Part` raises `DslError` for it. A pin number that a component lists twice is one pin.
- For a part of an Altium link the pins are the designators its nets and marks use, so the symbol is not known: a pair whose pin no net uses MUST NOT be reported as a pin the symbol lacks, and gets no record.
- A footprint that is not resolved gives `altium.footprint-unresolved` as before; its pads are not checked.
- A design in which no component holds a map MUST build the files it built before, byte for byte.
- `docs/altium.md` and `src/fenolite/cli/data/explain.toml` MUST list the code.
- **What `check` says.** `fenolite check` of this release on a project built from a script with a renaming map compares the schematic by pin number and the board by pad number, so it reports `netlist.assignment-differs` and exits 5 although the files are right; `docs/altium.md` and the changelog MUST say so.

#### Scenario: Net on the mapped pads
- **GIVEN** the blink with `pad_map={"1": "2", "2": "1"}` on its `D1`, whose pin `1` is on `GND`
- **WHEN** `uv run pytest tests/unit/lens/test_altium_pad_map.py -k "renaming_map or both_targets"` builds it with `--target altium`, reads the written PCB document, and builds the same script for KiCad
- **THEN** the pad `2` of `D1` is on `GND` and its pad `1` is not (the releases 0.1.0 and 0.2.0 wrote the opposite), and the KiCad board has the same nets on the two pads

#### Scenario: Copper on a mapped part
- **GIVEN** the routed blink with the same map on `D1` and its two tracks ending on the mapped pads, with and without a zone, and the KiCad boards built from the routed blink with and without the map
- **WHEN** `uv run pytest tests/unit/lens/test_altium_pad_map_copper.py` builds each script for Altium, alone and with `--copper-from` each board
- **THEN** the script with the map builds with its tracks and with its zone, with the nets of `D1` equal to those of its KiCad board; `--copper-from` its own board is accepted; and `--copper-from` the board of the other script is refused with `altium.copper-board-mismatch` saying "pad 1 of D1 is on GND there, the design puts it on LED_A", nothing written

#### Scenario: Map that names a missing pad
- **GIVEN** the blink whose `D1` has `pad_map={"1": "TAB"}`, a pad its footprint lacks, and the blink whose `D1` has `pad_map={"9": "1"}`, a pin its symbol lacks
- **WHEN** `uv run pytest tests/unit/lens/test_altium_pad_map.py -k missing` builds each with `--target altium --confirm --json`
- **THEN** the exit code is 5, `issues` holds `altium.pin-pad-map-invalid` naming `TAB` or the pin `9` with `where` `D1`, and the output folder is not created

#### Scenario: Pad that two pins stand for
- **GIVEN** the blink whose two-pin `D1` has `pad_map={"1": "2"}`, and the one with `pad_map={"2": "1"}`, each once with its pins on two nets and once with both pins on `GND`
- **WHEN** `uv run pytest tests/unit/lens/test_altium_pad_map.py -k "two_pins or repeated_pin"` builds each for the Altium target and for KiCad
- **THEN** the Altium build exits 5 with one `altium.pin-pad-map-invalid` that names the pad and the pins `1` and `2`, and creates no output folder; the KiCad build exits 5 with `build.pin-pad-map-invalid`; `Part(..., pad_map={"1": "3", "2": "3"})` raises `DslError`; a component that lists a pin number twice gives no issue; and a part of an Altium link with a mapped pin that no net uses gives none

#### Scenario: Check of a built project with a map
- **GIVEN** the Altium build of the blink with `pad_map={"1": "2", "2": "1"}` on `D1`, and the build of the blink without a map
- **WHEN** `uv run pytest tests/unit/lens/test_altium_pad_map.py -k check_still` runs `fenolite check` on each
- **THEN** the first exits 5 with `netlist.assignment-differs` for `D1-1`, none of it between the model and the PCB document, and the second exits 0

#### Scenario: Closed set still closed
- **WHEN** `uv run pytest tests/unit/lens/test_altium_issues.py -k closed_set` collects the codes the Altium build tests produce
- **THEN** `altium.pin-pad-map-invalid` is a key of `ALTIUM_ISSUE_CODES` with the severity `error` and is produced by a test

### Requirement: Bottom-side footprints of a copper source
The check of a copper source SHALL compare the pads of a footprint with its definition in the definition's frame: for a bottom footprint, stored mirrored about local X (`H-G-BOTTOM-STORE`), with each stored Y negated (`library_pad_positions`), at any rotation; for a top one as stored. A bottom footprint stored unmirrored MUST give `altium.copper-board-mismatch`. No written byte changes. This extends "Copper from a routed KiCad board" and "Script copper in an Altium build".

#### Scenario: Bottom part with pads off its axis
- **GIVEN** the blink with `U1` (`Mini:Mini_QFP-32_7x7mm_P0.8mm`) placed on the bottom at 0° or at 90°, with or without `pad_map={"1": "2", "2": "1"}`, and the KiCad board of the same script written by `fenolite build`
- **WHEN** `fenolite build design.py --out A --target altium --copper-from <that board> --confirm --json` runs
- **THEN** the exit code is 0, no error is given, and every pad of `A/blink.PcbDoc` is where the KiCad board has it, up to one shift of the frame, within 2 nm

#### Scenario: Board of the other map
- **GIVEN** the bottom `U1` at 90° and a board built with the other choice of the map
- **WHEN** the build runs with `--copper-from`
- **THEN** the exit code is 5 and the errors are `altium.copper-board-mismatch` at `U1.1` and `U1.2`, none about the pad positions

#### Scenario: Bottom part stored unmirrored
- **GIVEN** the board of the bottom `U1` with its pads written as the library has them
- **WHEN** the build runs with `--copper-from`
- **THEN** the exit code is 5 and the one error is `altium.copper-board-mismatch` at `U1`, "the pads of Mini:Mini_QFP-32_7x7mm_P0.8mm differ from the footprint the design resolves"

#### Scenario: Script copper on a bottom part
- **GIVEN** the bottom `U1` at 90° and a track from its pad 1 on `B.Cu` through a via to `R1`'s pad 1
- **WHEN** the script is built for Altium without and with `--copper-from` its own KiCad board
- **THEN** both builds exit 0 and their `PcbDoc` files are equal byte for byte

#### Scenario: Back from Altium
- **GIVEN** `kicad-cli` 10.x
- **WHEN** `tests/kicad/altium/test_copper_from_bottom_oracle.py` imports the document of the first scenario at 0° and 90° with `kicad-cli pcb import --format altium`
- **THEN** every pad of the imported board is where the source board has it relative to the outline corner within 10 nm, `U1` is on the bottom at the source's rotation, and its stored pads with Y negated are the definition's

### Requirement: Script layer counts in an Altium build
The Altium build SHALL write the PCB document of a script declared with any count of `fenolite.dsl.design.COPPER_COUNTS` (`design-dsl`, "Board and placements in the DSL"), 6 and 8 included, with the stack of `altium-pcb-writer`, "Layer stacks of any even count", and SHALL NOT refuse a script for its count.
- When `design.board` names no copper layer, `lens.altium_copper.board_layers(design, copper)` MUST give `F.Cu`, `In1.Cu` … `In<copper − 2>.Cu`, `B.Cu` (`layer_names(copper)`) and no issue for every count of `COPPER_COUNTS`. These are the names of `Design.copper_layers`, so a zone, a plane or script copper on an inner layer of the script lies on a layer of the document. This extends the layer sentence of "Copper in an Altium build", which names the lists of `copper=2` and `copper=4`.
- A plane on any inner layer of the count MUST be written as an internal plane on its net ("Internal planes in an Altium build"), and a zone or script copper on any copper layer of the count as "Copper in an Altium build" and "Script copper in an Altium build" state. The in-memory KiCad build of script copper MUST run with the script's count (`design-dsl`, "Copper layer counts in a build").
- `altium.copper-stack` keeps its rows ("Copper issue codes"): a board whose own copper layers repeat or differ in count from the script's, and a plane on a wrong layer or net. It MUST NOT be given for a count of `COPPER_COUNTS` as such. `lens.altium_copper.STACK_HINT` MUST read "make design.board(..., copper=…) equal to the board's copper layer count, or give the board its copper layers", and MUST NOT name 2 and 4 as the only counts.
- This requirement adds no record, layer id or format fact: the stack, its layer map and its evidence are those of "Layer stacks of any even count", and the evidence of the build does not change.

#### Scenario: Six layers with a plane and a zone
- **GIVEN** a blink variant declared with `design.board(mm(50), mm(30), copper=6, planes={"In4.Cu": gnd})` and `d.zone(vin, layers=("In3.Cu",))`
- **WHEN** it is built with `--target altium --dry-run --json`
- **THEN** the exit code is 0, the PCB document is planned, `result.copper.layers` is 6, `result.copper.planes` is `{"In4.Cu": "GND"}`, `result.copper.zones` is 1, and `issues` holds no `altium.copper-stack` and no `altium.not-lowered` whose `where` is `stackup`

#### Scenario: Eight layers read back
- **GIVEN** a blink variant declared with `copper=8` and no copper intent
- **WHEN** `build_altium` runs on its model with `copper=8` and the planned PCB document is read back
- **THEN** the board holds the eight copper layers `F.Cu`, `In1.Cu` to `In6.Cu` and `B.Cu` in that order, and no issue is an error

#### Scenario: Hint without the old counts
- **GIVEN** a model whose `board.layers` holds the copper layers `F.Cu`, `In1.Cu`, `In2.Cu` and `B.Cu`
- **WHEN** `build_altium` runs with `copper=6`
- **THEN** `files` is empty and `issues` holds one `altium.copper-stack` that names 4 and 6, whose hint holds neither "copper=2" nor "copper=4"

### Requirement: Rules in an Altium build
`fenolite build --target altium` SHALL write every rule of the design that `rulemap.lower` lowers into `<name>.PcbDoc`, and SHALL report each rule that is not written with one `altium.not-lowered` (warning) whose `where` is `design-rules/<kind>` and whose message holds the rule's name, its selector and the reason.
- `result.rules` MUST hold `written` and `not_lowered`, each a list of `{kind, selector}`; an entry of `written` also holds `rule`, the name of the Altium rule, and an entry of `not_lowered` holds `reason`. `result.rules` is `null` only when the build is refused before the PCB document is planned.
- The reasons are those of `rulemap.NOT_LOWERED_REASONS` and, when the build plans no PCB document, `no-document` for every rule that would otherwise be written.
- No issue with `where` `design-rules` alone MAY be reported.
- A design without rules MUST get the rules the build wrote before this change (the rules of the net classes and the `All` defaults), byte for byte.
- The build's evidence MUST name the hypotheses of `rulemap.EVIDENCE` whenever it names those of the PCB writer.
- A script whose copper intents are resolved through the KiCad build in memory ("Script copper in an Altium build") is still judged by that build: a rule that the KiCad lowering refuses (for example a `via_drill` rule with `opt`) refuses the Altium build as before.

#### Scenario: Edge clearance reaches the board
- **GIVEN** the blink script with `design.rules.minimum(edge_clearance=mm(0.5))`
- **WHEN** it is built for Altium and the PCB document is read back
- **THEN** the board's rules hold that edge clearance, and `result.rules.written` lists the kind `edge_clearance` with the rule `BoardOutlineClearance`

#### Scenario: A kind without a counterpart
- **GIVEN** the same script with a `silk_clearance` rule and a `creepage` rule
- **WHEN** it is built
- **THEN** one `altium.not-lowered` warning per rule has `where` `design-rules/silk_clearance` and `design-rules/creepage`, and `result.rules.not_lowered` holds both with the reason `no-counterpart`

#### Scenario: Read back equal
- **WHEN** `uv run pytest tests/unit/lens/test_altium_rules.py -k readback` builds the blink with one rule of every `exact` kind, the example scripts and generated rule sets, and maps the rule records of each PCB document with `read.rules.map_rules`
- **THEN** every record maps, and the rules read under the names of `result.rules.written` equal the lowered rules of the design within 2 nm (`H-A-RULE-READBACK`)

### Requirement: Output job in an Altium build
`fenolite build --target altium` SHALL write `<name>.OutJob` with `backends.altium.outjob.write_outjob(from_preset(preset, name=<name>, copper=<stack>))` when the build writes a PCB document, where `<stack>` is `StackSpec.copper` of that document (the Altium ids of its copper layers from top to bottom), and SHALL list it in the project file it writes, as the document after the PCB document.
- `--altium-outjob on|off` (default `on`) MUST select it, and `--altium-outjob-preset FILE` MUST name the export preset (`fenolite.export-preset.v0`, the file that `fenolite export --preset` reads); without it the preset is the default one. Both options MUST be a usage error (exit 2, `FEN-2001`) with `--target kicad`, and `--altium-outjob-preset` MUST be one with `--altium-outjob off`. A preset that cannot be read or is malformed MUST fail as it does for `export`.
- A build that writes no PCB document MUST write no output job, and `result.outjob` MUST be `null`.
- The Gerber output of the job MUST carry the complete settings record ("Output job written"), with the plotted layers of the board that the build writes and the decimals of the preset. No other output of the job MUST carry a settings record. Every output of the job MUST carry `OutputDefault<i>=0` ("Output job written").
- An output job that exists and differs from the one the build would write MUST be handled by the rule of every other planned file: when the state of the output folder (`.fenolite/build.json`) records the digest of the job as it stands, the build MUST replace it and keep the old bytes as `<name>.OutJob.bak`; when the job was edited since the build that the state records, or the state is missing, the build MUST refuse it as an edited output (exit 7, `FEN-7001`, nothing written), and `--discard-layout` MUST replace it with the same backup. So a job that a build before change c0138 wrote is replaced by a rebuild into its folder, and refused only when it was edited or its state is lost.
- When the project file exists and does not list `<name>.OutJob`, the build MUST write the project file again with the job listed when the file is as a build wrote it ("Edited Altium outputs are not overwritten": `project_digest`), and otherwise MUST keep it and report `altium.outjob-not-listed` (info), with a hint that says how to get the job listed. A kept project file that lists the job MUST give no such issue.
- `result.outjob` MUST hold, in this order, `file` (under `--out`), `media` (name and type of each container), `outputs` (per output its `kind`, `type`, `name`, `category`, `document`, `enabled` and the name of its container, in the order of `OUTPUT_KINDS`), `gerber`, `defaults` and `preset` (`null`, or the file as given and its SHA-256).
- `result.outjob.gerber` MUST hold, in this order, `unit` (`"Metric"`), `decimals` (the integer written), `layers` and `outline`. `layers` MUST hold one object per entry of the record's `Plot.Set`, in its order, with `id` (the long layer id) and `name` (the layer's name as `pcbrecords.LAYER_NAMES` gives it).
- `result.outjob.gerber.outline` MUST be the object `{"plotted": false, "reason": outjob.OUTLINE_REASON}`, and `OUTLINE_REASON` MUST be the text `the PCB document holds the board outline as the board shape and on no layer, and no public source gives the entry of the board shape among the plotted layers; turn the outline on in the Gerber setup in Altium`. The Gerber set of the written job holds no plot of the board outline, and `docs/altium.md` MUST say so beside the description of the job.
- `result.outjob.defaults` MUST hold the options that the preset sets and the writer has no key for, as sorted `table.key` texts; `gerbers.precision` is not among them.
- With `--altium-outjob off`, and for every file other than `<name>.OutJob`, the bytes MUST be those of the build before change c0138.
- The evidence of a build with a job MUST name `H-A-OUTJOB-READBACK`, `H-A-OUTJOB-OPEN`, `H-A-OUTJOB-RUN-2`, `H-A-OUTJOB-GERBER-RECORD`, `H-A-OUTJOB-GERBER-ACCEPT` and `H-A-OUTJOB-GERBER-LAYERS`, and the level stays `INFERRED`.

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
- **THEN** `blink.PrjPcb` is written again and lists `blink.OutJob`, `blink.PrjPcb.bak` holds the earlier bytes, and `altium.outjob-not-listed` is not reported; with a line appended to the project file before the second build, `blink.PrjPcb` keeps its bytes and `altium.outjob-not-listed` is reported

#### Scenario: The job of an earlier build is replaced
- **GIVEN** an output folder that holds the `blink.OutJob` of a build before change c0138 and the state that records its digest
- **WHEN** the build runs into that folder
- **THEN** the exit code is 0, `blink.OutJob` holds the Gerber record, and `blink.OutJob.bak` holds the bytes of the earlier job

#### Scenario: A job without its state is refused
- **GIVEN** the same folder without its `.fenolite` folder
- **WHEN** the build runs into it
- **THEN** the exit code is 7 with `FEN-7001`, the error names `blink.OutJob` and no other file, its hint names `--discard-layout`, nothing is written, and the same build with `--discard-layout` replaces the job and writes `blink.OutJob.bak`

#### Scenario: The Gerber record of the built job
- **WHEN** the routed blink is built for Altium and `blink.OutJob` is read with `read_outjob`
- **THEN** the Gerber output holds one setting of 44 fields, no other output holds a setting, `result.outjob.gerber.unit` is `Metric`, `result.outjob.gerber.decimals` is 4, and `result.outjob.gerber.layers` names Top Overlay, Top Paste, Top Solder, Top Layer, Bottom Layer, Bottom Solder, Bottom Paste, Bottom Overlay and Mechanical 13 to 16, with the ids of the record's `Plot.Set` in the same order, and no entry of `layers` is an outline

#### Scenario: The preset's precision is carried
- **GIVEN** a preset file with `[gerbers]` `precision = 6`
- **WHEN** the build runs with `--altium-outjob-preset` naming it
- **THEN** `result.outjob.gerber.decimals` is 6 and `result.outjob.defaults` is empty

#### Scenario: The set holds no outline
- **WHEN** the routed blink is built for Altium with `--json`
- **THEN** `result.outjob.gerber.outline.plotted` is `false`, `result.outjob.gerber.outline.reason` is the text of `outjob.OUTLINE_REASON`, the keys of `result.outjob.gerber` are `unit`, `decimals`, `layers` and `outline`, in that order, and the keys of `result.outjob` are `file`, `media`, `outputs`, `gerber`, `defaults` and `preset`, in that order

#### Scenario: Only the job changes
- **WHEN** the routed blink is built for Altium at this change and at the commit before it
- **THEN** `blink.OutJob` differs by eight inserted lines, `OutputDefault<i>=0` for each of its six outputs and the two configuration lines of the Gerber output, and every other written file has equal bytes in both builds

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

### Requirement: Copper guard in an Altium build
`fenolite build --target altium` SHALL judge the copper of the PCB document it is about to write with `fenolite.checks.copper.check_copper`, in `cmd_build.altium_copper_guard`, after `lens.altium.build_altium` returns its files and before `cmd_build` calls `check_existing` and returns its plan, on `--dry-run` and `--confirm` alike. The guard lives in `cli` because `lens` may not import `checks` (`package-layering`).
- **What is judged.** The planned bytes of `<name>.PcbDoc` MUST be read back with the Altium reader and adapter (`AltiumBackend.board_from_bytes`), the rules MUST be those of that document (`AltiumBackend.rules_from_bytes`, "Clearance rules of a PCB document" of `altium-verification`), and the pads MUST come from the Altium board frame. The guard MUST read and write no file. A build that plans no PCB document, or that was refused, MUST NOT be judged (`ran` false).
- **Modes.** The option is `--copper-check refuse|warn` of the KiCad target (`design-dsl`, "Copper guard before writing"), default `refuse`. With `refuse` a `copper.short` MUST keep its severity, so the build returns no planned write and exits 5. Every other copper issue of severity `error` MUST be reported with severity `warning` and ` (reported, not refused: the Altium copper guard refuses shorts)` appended to its message, and MUST NOT stop the build. With `warn` the short MUST be a warning too, with ` (copper guard in warn mode)` appended, and the build MUST plan its writes. There is no way to switch the guard off.
- **Result.** `result.copper_check` MUST hold `mode`, `ran`, `shorts`, `clearance`, `unpoured` (the zones without a fill), `rules` and `evidence`, and MUST stand after `copper` in the result. The evidence MUST be `UNVERIFIED` when `unpoured` is not 0 or an issue lowers it.

#### Scenario: Short refused
- **GIVEN** the routed blink whose script holds one more track of `LED_A` that crosses the track of `LED_DRV` on `F.Cu`
- **WHEN** it is built for Altium with `--confirm`
- **THEN** the exit code is 5, `copper.short` names the two nets, and the output folder holds no file

#### Scenario: Warn mode and clearance findings write
- **WHEN** `uv run pytest tests/unit/cli/test_build_altium_guard.py` builds that script with `--copper-check warn`, and a script whose extra track ends 0.15 mm from another net's track
- **THEN** both builds exit 0 and write the PCB document, the short is a warning that ends with `(copper guard in warn mode)`, and the clearance finding is a warning

### Requirement: Assembly and test features in an Altium build
An Altium build SHALL write the parts of `test_point()` as ordinary parts, SHALL leave the parts of `fiducial()` out of the schematic and of the PCB library and document, because the PCB library writer refuses their footprints, and SHALL write the parts of `tooling_hole()` as the holes of `hole()` ("PCB document output", c0102).
- **Test points.** A test-point part MUST be planned like any part with an authored definition: its symbol in the schematic library and on its sheet, its footprint in the PCB library, and its component in the PCB document with pad `1` on the part's net. Its footprint holds one numbered pad with copper, which `pcblib.check_footprint` accepts.
- **Marks.** `Pad.fab_property` MUST NOT be written to any Altium record: no public source yet says how a pad record holds a test-point, fiducial or other fabrication mark. Every footprint that is written and holds a marked pad (the test points, and an authored footprint with `fab_property=`) MUST be named by one `altium.not-lowered` info of the kind "pad properties".
- **Fiducials.** Their parts MUST be left out before the footprint check, so that they give no `altium.footprint-unsupported` and never make the build withhold the PCB document (`altium.pcbdoc-not-written`), and MUST be named by one `altium.not-lowered` info of the kind "assembly features". Their keep-outs are board keep-outs and are reported as "PCB document output" reports every keep-out.
- **Tooling holes.** A tooling-hole part has the symbol `Fenolite_Holes:Hole`, so it is a hole part of "PCB document output": it is no component, and its round hole that is not plated is written as a board hole of the PCB document. Its courtyard is not written, as for every hole part.
- These two kinds extend the list of c0032's `altium.not-lowered` row, as the kinds of "PCB document output" do.
- Every other file and item MUST be planned as for the same design without the fiducials.

#### Scenario: Test point written, fiducial left out
- **GIVEN** a variant of `examples/blink_2layer/design.py` with `d.fiducial("FID1", mm(3), mm(3), copper=mm(1), mask=mm(2))`, `d.tooling_hole("TH1", mm(46), mm(4), drill=mm(3))` and `d.test_point("TP1", led_a, mm(30), mm(12), size=mm(1.5))`
- **WHEN** `uv run pytest tests/unit/lens/test_build_assembly.py -k altium` builds it with `--target altium --dry-run --json`, and then with `--confirm`
- **THEN** the exit code is 0; the PCB document is planned and holds the component `TP1` with its pad on `LED_A`; no written document holds `FID1` or `TH1`; the stored board holds a board hole of 3 mm; and `issues` holds one `altium.not-lowered` info of the kind "assembly features" naming `FID1`, one of the kind "pad properties" naming the test-point footprint, and neither `altium.footprint-unsupported` nor `altium.pcbdoc-not-written`

### Requirement: Stack-ups with masks, sheets and kinds in an Altium build
The Altium build SHALL take the stack values of the PCB document from a `Board.stackup` that holds the entries and fields of `design-model`, "Stack-up in the board model" (solder mask, silkscreen and paste entries, sheets, `dielectric_kind`, `color`, `impedance_controlled`), by the rules below, and SHALL name every value that the document does not hold. The rules apply alike to `lens.altium_copper.stack_from_stackup` (a build, "Copper in an Altium build") and to `backends.altium.lower.stack_from_stackup` (the write of a model), which reports through its account where the build gives an issue.
- Entries of kind `soldermask`, `silkscreen` and `solderpaste` MUST be passed over: the stack of the document holds the copper layers and the dielectrics between them (`altium-pcb-writer`, "Layer stacks of any even count").
- A dielectric entry whose `dielectric_kind` is set MUST be written with that kind: `DIELTYPE` 1 for `core` and 2 for `prepreg`, the values recorded in `docs/formats/altium/pcb-copper.md` ("Layer stack"). An entry without one MUST take the kind of `dielectric_kinds(count)` as before. A stack-up that holds none of the new fields MUST therefore give the document it gave before this requirement, byte for byte.
- A gap between two copper entries that holds two or more dielectric entries (the sheets of one dielectric) does not fit the document, which holds one dielectric per gap. The build MUST then write Fenolite's default stack values and give one `altium.not-lowered` info with `where` `stackup` whose message names the gap, as "Copper in an Altium build" rules for a stack-up that does not fit. Sheets MUST NOT be merged, dropped or averaged.
- When the stack-up fits and holds a value for which the document has no recorded key (a solder mask entry of thickness above 0, a non-empty `color`, a non-empty `finish`, or `impedance_controlled` true), the build MUST give one `altium.not-lowered` info with `where` `stackup` that lists the kinds of value left out; the copper and dielectric values MUST be written. A stack-up without such a value MUST give no issue.
- The Altium import MUST NOT fill `dielectric_kind`, `color` or `impedance_controlled` through this requirement: an imported stack-up keeps the defaults, and the round trips of `altium-verification` compare the models they compared before.
- This requirement adds no record, key or format fact and no issue code, and the evidence of the build does not change.

#### Scenario: Script stack-up with masks and stated kinds
- **GIVEN** a four-layer blink variant whose `design.stackup(...)` lists a 10 µm mask, 35 µm copper, a 0.2 mm prepreg, 17.5 µm copper, a 1.2 mm core, 17.5 µm copper, a 0.2 mm prepreg, 35 µm copper and a 10 µm mask, without a colour and without a finish
- **WHEN** it is built with `--target altium` and the PCB document is read back
- **THEN** the board has four copper layers with those copper thicknesses, the three dielectrics are a prepreg, a core and a prepreg with those heights within 2 nm, and `issues` holds one `altium.not-lowered` info with `where` `stackup` that names the solder mask thickness and nothing else

#### Scenario: A core where the table says prepreg
- **GIVEN** a two-layer model whose stack-up holds `F.Cu`, one dielectric entry with `dielectric_kind == "prepreg"` and `B.Cu`
- **WHEN** `build_altium` runs and the document is read back
- **THEN** the one dielectric has `DIELTYPE` 2, where the same model without `dielectric_kind` gives 1, and `issues` holds no `altium.not-lowered` with `where` `stackup`

#### Scenario: Two sheets in one gap
- **GIVEN** the four-layer board of `kicad-file-backend`, "Four-layer node projected" (`tests/data/kicad/board/stackup_four.kicad_pcb`), whose core between `In1.Cu` and `In2.Cu` holds two sheets
- **WHEN** its model is written as an Altium PCB document
- **THEN** the document holds the default stack values, and exactly one `altium.not-lowered` (or one skipped `stackup` entry of the account) names the gap between `In1.Cu` and `In2.Cu`

#### Scenario: Stack-ups without the new fields keep their bytes
- **WHEN** `uv run pytest tests/unit/lens/test_altium_pcb_complete.py tests/unit/lens/test_altium_pcb_golden.py tests/unit/lens/test_altium_copper_golden.py` builds the committed Altium samples
- **THEN** every file equals the committed one

### Requirement: Rule areas, board items and area rules in an Altium build
The Altium build SHALL treat the rule areas, texts, graphics and dimensions that a script declares (`design-dsl`, "Rule areas in the DSL", "Board drawings in the DSL") as the board items they are in the model: written to a planned PCB document where `altium-pcb-writer` has a record for them ("Board text records", "Board graphics and keep-out records"), and reported item by item where it has none ("Complete board in an Altium build"). This requirement adds no record, key or format fact.
- **Rule areas.** A keep-out that sets at least one of `no_tracks`, `no_vias`, `no_pads` and `no_copper_pour` MUST be written with those restrictions. `Keepout.name` has no recorded key in the keep-out record: it MUST NOT be written, and each named keep-out MUST give one `altium.not-lowered` info whose `where` is `keepout/<id>` and whose message names the name that is lost. A rule area that forbids nothing, a named area for rules only, has no record, as any keep-out without a restriction: it MUST give one `altium.not-lowered` with `where` `keepout/<id>` and MUST be counted under `keep-out` of `result.pcb.not_lowered`.
- **Texts.** A board text whose `h_justify` and `v_justify` are both `center` MUST be written as before. Another justification has no recorded key in the text record: the text MUST NOT be written at a guessed position, and MUST give one `altium.not-lowered` with `where` `text/<id>` that names the justification.
- **Dimensions.** `lens.altium_copper.KINDS`, the kinds of "Written items are accounted", MUST gain `dimension`. No dimension record is written: each `Dimension` of the board MUST give one `altium.not-lowered` with `where` `dimension/<id>`, and `result.pcb.not_lowered` MUST hold `dimension` with their count. `lens.altium_copper.BOARD_KINDS` MUST gain the row `("dimensions", "dimensions")`, so that a build without a PCB document reports the dimensions with one info, as it reports keep-outs, texts, graphics and holes.
- **Area rules.** A rule whose selector holds an `area` leaf (`rules-model`, "Closed selector grammar") has no scope in the closed scope grammar of the rule records. `backends.altium.rulemap.lower` MUST give it the reason `scope-unsupported`, for that rule only ("Scoped rule records"), and the build MUST report it with the `altium.not-lowered` warning of "Rules in an Altium build" (`where` `design-rules/<kind>`) and list it under `result.rules.not_lowered`. `rulemap.TABLE` gains no row: `area` is a selector, not a rule kind. `build.area-unknown` (`design-dsl`, "Board items in a build") stays a check of the KiCad build and of the in-memory KiCad build that resolves script copper ("Script copper in an Altium build").
- **Copper guard.** The copper guard of an Altium build ("Copper guard in an Altium build") judges the document it reads back with the same `check_copper`, so it can find `copper.keepout` (`copper-check`, "Keep-out findings") for the keep-outs that the document holds. As that requirement rules for every copper error other than a short, the finding MUST be reported with severity `warning` and the guard's suffix, and MUST NOT stop the build. Area rules are not in the document, so the guard does not apply them.
- A design without rule areas, justified texts, dimensions and area rules MUST give the files and the issues it gave before this requirement.

#### Scenario: Script items in an Altium build
- **GIVEN** the blink variant of `design-dsl`, "Blink with a keep-out, a label and a dimension": `d.rule_area("ANT", …, forbid=("tracks", "vias"))`, `d.text("rev", "REV A", (mm(2), mm(2)))` and `d.dimension("width", (mm(0), mm(0)), (mm(40), mm(0)), offset=mm(-3))`
- **WHEN** it is built with `--target altium --dry-run --json`
- **THEN** the exit code is 0, `result.pcb.written` holds `keep-out` 1 and `text` 1, `result.pcb.not_lowered` holds `dimension` 1, and the `altium.not-lowered` issues for these items are exactly two infos: one with `where` `keepout/<id>` that names `ANT`, and one with `where` `dimension/<id>`

#### Scenario: A rules-only area and a justified text
- **GIVEN** a blink variant with `d.rule_area("HV", …)` without `forbid` and one text declared with a `justify` other than the centred default
- **WHEN** it is built with `--target altium --dry-run --json`
- **THEN** the exit code is 0, `result.pcb.not_lowered` holds `keep-out` 1 and `text` 1, and `issues` holds one `altium.not-lowered` with `where` `keepout/<id>` and one with `where` `text/<id>` that names the justification

#### Scenario: An area rule is not lowered
- **GIVEN** a blink variant with the rule area `HV` and a `clearance` rule `hv` whose `selector_a` is `area HV` and whose `min` is 2 mm
- **WHEN** it is built with `--target altium --dry-run --json`
- **THEN** the exit code is 0, `issues` holds one `altium.not-lowered` warning with `where` `design-rules/clearance` that names `hv` and `scope-unsupported`, `result.rules.not_lowered` lists the rule with that reason, and every other rule of the design is written as before

#### Scenario: Dimensions without a document
- **GIVEN** a model without a board outline whose board holds one `Dimension`
- **WHEN** `build_altium` runs
- **THEN** no `.PcbDoc` is planned, and `issues` holds one `altium.not-lowered` info with `where` `dimensions` that names the count 1

#### Scenario: No new item, no new issue
- **WHEN** `uv run pytest tests/unit/lens/test_altium_pcb_complete.py tests/unit/lens/test_altium_pcb_golden.py tests/unit/lens/test_altium_rules.py` builds the committed samples
- **THEN** every file equals the committed one, and no `altium.not-lowered` names a dimension, a name or a justification

### Requirement: Complete board in an Altium build
`fenolite build --target altium` SHALL write the stack, vias, texts, graphics, keep-outs, holes, bodies and polygons of the design as `altium-pcb-writer` requires, and `result.pcb` SHALL hold `written` and `not_lowered`, each mapping a kind to a count.
- An item that is not written MUST give one `altium.not-lowered` (info, the severity the code has) whose `where` is `<kind>/<id>`, or `stackup`; a micro via gives `altium.via-unsupported` (warning) with `where` `via/<id>` instead. Without a PCB document the items stay in the model with one `altium.not-lowered` per kind, as before this change, and `result.pcb` is `null`.
- A design that uses none of the new items MUST give the files it gave before this change, byte for byte.

#### Scenario: Six-layer sample
- **WHEN** `uv run pytest tests/unit/lens/test_altium_pcb_complete.py -k board6` builds the sample
- **THEN** `result.pcb.not_lowered` is empty, and the committed `tests/data/altium/board6/board6.PcbDoc` equals the built one

#### Scenario: Old samples unchanged
- **WHEN** `uv run pytest tests/unit/lens -k "altium and samples"` builds the committed samples of earlier changes
- **THEN** every file equals the committed one

### Requirement: Readable schematic in an Altium build
`fenolite build --target altium` SHALL write symbol graphics, the module tree, directions, buses, parameters and texts as `altium-schematic-writer` requires, and the nets and designators of a design MUST be the ones the build gave before this change.
- `--altium-symbols generic|graphics` (default `graphics`, by the maintainer's decision of 2026-10-06; `build_altium(…, symbol_bodies=…)`) MUST select how a resolved symbol is drawn: `graphics` draws its own graphics where "Symbol graphics in libraries and bodies" allows, `generic` one rectangle per part. With `generic`, the files of a build MUST be byte for byte those of the build before this change: the committed copies under `tests/data/altium/generic/` are the form of the samples `blink`, `kicad_example`, `no_connect` and `routed` that the maintainer's author reports of 2026-10-02 and 2026-10-03 covered. The `graphics` form of those samples is not covered by any author report until Part Y is reported.
- `--altium-directions on|off` (default `on`; `build_altium(…, directions=…)`) MUST select the directions. `--altium-sheets flat|modules` keeps its meaning and its default `flat`, and a `flat` build of a design with Altium links only keeps its bytes. Each of the two new options without `--target altium`, or with another value, is a usage error (`FEN-2001`, exit 2).
- `build_altium(…, authored_symbols=…)` MUST take the symbols that the script authored or took from the catalog, by lib id, and write them like resolved KiCad symbols without reading a library; the command MUST pass them, and the authored and catalog footprints, as a KiCad build does.
- `result.schematic` MUST hold `sheets`, `symbols` (`graphics` or `generic`), `symbols_drawn` (library symbols drawn from their graphics), `symbols_simplified` (those drawn as rectangles), `buses` (bus blocks), `parameters` (hidden parameters written), `directions` (`on` or `off`) and `directed` (ports and sheet entries with an I/O type); it is `null` for a refused build.
- `lens.altium.ALTIUM_ISSUE_CODES` MUST gain `altium.bus-flattened` (info): a bus of the design is drawn as its nets, with the reason. This extends c0032's "Altium build issue codes", whose closed-set rule holds for it.
- A comment in the binary form may hold Windows-1252 characters; in the ASCII form, and for a character no form carries, the build MUST give `altium.text-unwritable`, whose message names the character and says whether the binary form carries it. A property that cannot be written as a parameter MUST be kept in the model and named by one `altium.not-lowered` info (`where` = `parameters`). The PCB document's texts stay 7-bit: a comment with another character is written there as the symbol name, with one `altium.not-lowered` info (`where` = `pcb-comments`).
- `ALTIUM_BUILD_EVIDENCE` MUST name the seven `H-A-SCHX-*` rows and MUST stay `INFERRED`.

#### Scenario: Nets unchanged
- **WHEN** `uv run pytest tests/unit/lens/test_altium_schematic_complete.py -k nets_unchanged` reads every committed sample project
- **THEN** the netlist and the designators read from each equal the ones recorded in `tests/data/altium/nets_before_c0086.json` from the files of commit 6cdf0aea

#### Scenario: Tree sample
- **WHEN** `uv run pytest tests/unit/lens/test_altium_schematic_complete.py -k tree` builds the sample
- **THEN** the built files equal the committed `tests/data/altium/tree/`, `result.schematic.sheets` is 4, `symbols_drawn` is 8 and `symbols_simplified` is 0

#### Scenario: Generic form kept
- **WHEN** `uv run pytest tests/unit/lens/test_altium_schematic_complete.py -k generic` builds `blink`, `kicad_example`, `no_connect` and `routed` with `symbol_bodies="generic"`
- **THEN** each schematic and each schematic library equals its copy under `tests/data/altium/generic/`, and every other file of the sample equals the one of the default build

#### Scenario: Readback
- **WHEN** `uv run pytest tests/unit/lens/test_altium_schematic_complete.py -k readback` builds the tree sample and every example script, in both forms and with both symbol bodies
- **THEN** each project read with `AltiumBackend` gives the nets and designators it was written from, and the tree sample also its modules, its bus, its values and its parameters

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

### Requirement: Component bodies in an Altium build
`fenolite build --target altium` SHALL accept `--altium-bodies off|extruded` (default `extruded`, since change c0155), and with `extruded` SHALL write the component bodies of the board's footprints as `altium-pcb-writer` requires ("Component bodies are reported", "Extruded component body records", "Component bodies of a library footprint").
- `lens.altium.build_altium`, `lens.altium.write_model`, `lower.from_design`, `lower.write_design` and `AltiumBackend.write` MUST take the same choice as `bodies="off" | "extruded"`. Another value MUST exit 2 on the command line and raise `ValueError` in the library. The default of `lens.altium.build_altium` MUST be `extruded`, as the command's; `lens.altium.write_model`, `lower.from_design`, `lower.write_design`, `AltiumBackend.write` and `AltiumBackend.model_roundtrip` MUST keep `off` as their default (the rewrite of a read document and the round trips).
- The option MUST be refused with exit 2 and `FEN-2001` for another target, as the other `--altium-…` options are.
- The result of the command MUST hold `pcb` (the accounting that change c0085 specified and that only the library's build summary held until change c0121: `null` without a PCB document), after `copper`, and `result.pcb` MUST hold `bodies` (the value used) after its other keys; `result.pcb.written.body` MUST count the bodies written and `result.pcb.not_lowered.body` the bodies not written, and their sum MUST be the number of bodies of the board's footprints.
- With `off`, every file of the build MUST equal the file built before change c0121, byte for byte, and each body is reported with the option named in the message. With `extruded`, the default, a design whose footprints hold no extruded body with an outline MUST also give those bytes.
- Every issue of a body MUST be `altium.not-lowered` (info) with `where` `body/<id>`; no issue code is added. `docs/cli-contract.md` MUST list the option, its default and `result.pcb.bodies`, and `docs/altium.md` MUST say what is written of a body, what is not, that the option is on by default since the maintainer's decision of 2026-10-09, on the author report of step X8 (`H-A-PCBX-BODY-OPEN`), and that `off` gives the earlier files.
- The bodies written are those of the model: a build MUST NOT add a body to a footprint that has none.

#### Scenario: Without the option
- **WHEN** `uv run pytest tests/unit/lens -k "altium and samples"` builds the committed samples of earlier changes, `board6` among them, without the option
- **THEN** every file equals the committed one (their footprints hold no extruded body with an outline), and `result.pcb.bodies` is `extruded`

#### Scenario: Off on the command line
- **GIVEN** the script `examples/blink_2layer/design.py`, whose footprints hold no body
- **WHEN** `uv run pytest tests/unit/cli/test_build_altium.py -k bodies_option` builds it for Altium without the option, with `--altium-bodies off` and with `--altium-bodies extruded`
- **THEN** `result.pcb.bodies` is `extruded` without the option and the value given otherwise, no body is counted, and the three builds give the same five files

#### Scenario: Sample with bodies
- **WHEN** `uv run pytest tests/unit/lens/test_altium_bodies.py -k body2` builds the sample without the option and with `--altium-bodies extruded`
- **THEN** every built file equals the committed file under `tests/data/altium/body2/`, `result.pcb.written.body` is 3, `result.pcb.not_lowered.body` is 1, and the one `altium.not-lowered` of a body names the body of kind `model`

#### Scenario: Refused for another target
- **WHEN** `fenolite build examples/blink_2layer/design.py --target kicad --altium-bodies extruded --dry-run --json` runs
- **THEN** the exit code is 2 and the error code is `FEN-2001`
