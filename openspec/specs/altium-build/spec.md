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
`lens.altium.build_altium(design, *, name, placed=(), placements=None, project_exists=False, form=DEFAULT_FORM, resolver=None, sheets=DEFAULT_SHEETS) -> BuildOutput` SHALL return every file of an Altium project for `design` as bytes, and SHALL return no file when any issue has severity `error`. `BuildOutput` is c0011's `lens.build.BuildOutput`.
- The steps MUST run in this order: the build checks of "Altium build issue codes" and "Hierarchy issue codes"; the symbol of every lib id and the pins of every component ("Altium symbol sources": generic pins for Altium links, the symbol's pins for KiCad lib ids) set as `Component.pins`; `Design.validate()`; the footprint of every footprint link, its checks and `lens.altium.pad_extras` ("Altium footprint sources", "PCB library outputs"); the PCB document's conditions and placements ("PCB document output"); `backends.altium.project.write_project(model, name=name, project=not project_exists, issues=…, form=form, symbols=…, footprints=…, pcb=…, sheets=sheets)`, where `footprints` are the `pcblib.LibFootprint` values to write and `pcb` is a `pcbdoc.PcbDocSpec` or `None`; the `.fenolite/` texts and record; evidence.
- An issue of severity `error` before the writer MUST give a `BuildOutput` with its issues and empty `files`.
- The layout MUST be `<name>.PrjPcb` (only when `project_exists` is false), `<name>.SchDoc`, every planned `<library>.SchLib` ("Schematic library outputs"), `<name>.PcbLib` when it holds a footprint ("PCB library outputs"), `<name>.PcbDoc` when its conditions hold ("PCB document output"), with `sheets="modules"` one `<name>_<module>.SchDoc` per top-level module and the planned `.Harness` files ("Module sheets in an Altium build"), the six layer files under `.fenolite/` and `.fenolite/build.json`, with the design name as stem.
- The layer texts MUST come from `canonical.dump_texts` of the model with its pins and rewritten net members, with an empty `findings.json`.
- `.fenolite/build.json` MUST be `{"design": <name>, "files": {<path>: <sha256>, …}, "schema": "fenolite.build-record.v0", "target": "altium"}` with sorted keys, no date and a final newline, and MUST record the SHA-256 of every planned file outside `.fenolite/`.
- The build MUST NOT write a project structure file, a date or an absolute path, and MUST NOT write a PCB library or PCB document other than these two.
- `summary` MUST hold `components`, `nets`, `labels`, `power_ports`, `sheet`, `schematic_format`, `libraries`, `symbols`, `footprints`, `pcb_document`, `sheet_mode`, `sheets`, `ports`, `sheet_entries`, `harnesses`, `kept` (paths relative to `--out`) and `experimental`, which `cmd_build` copies into `result`, with `kept` under `--out`.

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
- `<name>.PrjPcb` MUST be planned only when it does not exist in `--out`. An existing project file MUST be kept, whatever its content and whatever `--discard-layout`, and MUST be listed in `result.kept` with the info `altium.project-kept`.
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
The Altium build SHALL plan an experimental `<name>.PcbDoc` from `pcbdoc.write_pcbdoc` when the design has a board outline without cutouts and every component that has a footprint link has a `kicad` link whose footprint is in the planned `<name>.PcbLib`. Otherwise it MUST give one `altium.pcbdoc-not-written` info that names the reason (no board, cutouts, Altium footprint links, or the footprints not written) and the components concerned.
- Components without a footprint link MUST be left off the board, as Altium's change order would leave them.
- A placed component MUST take its DSL placement. An unplaced component MUST be staged right of the outline as the KiCad build stages it (`lens.build.STAGING_OFFSET`, `STAGING_GAP`, top side, angle 0), and the build MUST give one `altium.pcb-staged` info naming the staged refs. With a copper source, a component takes the source's placement instead, and none is staged ("Copper from a routed KiCad board").
- When the PCB document is planned, the board, the placements and the net classes MUST NOT be reported by `altium.not-lowered`: the document holds them ("Copper in an Altium build"). Differential pairs still are, and so are a board's keep-outs, texts, graphics and holes, one issue per kind; these kinds extend the list of c0032's `altium.not-lowered` row.
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
`lens.altium.build_altium(…, sheets="modules")` SHALL plan the sheets of `hierarchy.plan_sheets` (`altium-schematic-writer`, "Sheets of a hierarchical project"), their harness definition files and a project file that lists them, and SHALL link the PCB document's components through their sheet symbols.
- `project.write_project(…, sheets=…)` MUST write `<name>.SchDoc` as the top sheet, one `<name>_<module>.SchDoc` per top-level module, one `<sheet stem>.Harness` per sheet that holds a harness block, and `<name>.PrjPcb` through `write_prjpcb(…, sheets=…, harnesses=…)`. The libraries MUST NOT depend on the mode.
- `lens.altium.pcb_document` MUST set `PlacedComponent.sheet` to `(unique_id("sheet:<module>"), <module>)` for a component on a module sheet, and leave it `None` for a top-sheet component and in the `flat` mode (`altium-pcb-writer`, "PCB document links and nets").
- A component's `UNIQUEID`, its designator, its library links and the net names MUST NOT depend on the mode, so the engineering change order matches the same components and nets in both modes (`H-A-SCH-HIER-ECO`, `H-A-SCH-HIER-NAMES`).
- A `harness` interface none of whose members crosses a module, any `harness` interface in the `flat` mode, and any in the ASCII form MUST be reported by one `altium.not-lowered` info for the kind, naming the interfaces; their nets are written as plain nets.
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
| `altium.sheet-name-collision` | error | two top-level module names differ only in letter case, so their sheet files would collide |
| `altium.harness-name` | error | a harness type name or entry name holds `=`, `,` or `;`; two type names, or two entry names of one type, differ only in letter case; or a type name equals a net name in any letter case |
| `altium.harness-net-shared` | error | a net is a member of two `harness` interfaces, or twice of one |
| `altium.harness-power-net` | error | a member of a `harness` interface is also a member of a `power` interface |
| `altium.sheets-not-in-project` | info | the project file is kept, so the module sheets and harness files are not listed in it |

- A type name, entry name or module name that `ascii.text_problem` refuses MUST give `altium.text-unwritable`, as any written text.
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
- This requirement is implemented and tested now. Until c0028 exists, no build of the CLI passes such a source; tests build the KiCad model with `lens.build.build_design` and put the sample's copper into it. c0028 then passes its resolved model, with no change to this requirement.
- The build MUST check a script source as "Copper from a routed KiCad board" checks a board (components, footprints, pad nets, outline, copper nets), so a source built from another script is refused. It MUST take the source's placements and give no `altium.placement-from-board` for this origin.
- The build MUST NOT import `fenolite.dsl` or resolve intents itself: `lens` receives a model (`package-layering`).
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

### Requirement: Copper from a routed KiCad board
`fenolite build DESIGN.py --out DIR --target altium --copper-from BOARD.kicad_pcb` SHALL copy the tracks, arcs, vias and zones of a routed KiCad board of the same design into `<name>.PcbDoc`, after checking that the board matches the design. This requirement extends "Altium build target" and `design-dsl` "Build command".
- `--copper-from` MUST take one path. Without `--target altium` it MUST be a usage error (exit 2, `FEN-2001`); a path that is not a file MUST be a usage error too. `cmd_build` MUST read the board with `fenolite.backends.kicad.pcb.read_board` in the same process: a board the reader refuses exits 3 with the reader's `FEN-3xxx` code, and the reader's warnings and infos pass into `issues` unchanged. `kicad-cli` is not run. `cmd_build` MUST pass `CopperSource(<the read design>, "board", <the path as given>)`, and `--copper-from` wins over any other source.
- **Components.** Each design component with a footprint link MUST match exactly one footprint of the board: by the `fenolite.path` property when the board's footprint holds it, else by reference. A component without a match, a board footprint without a component, or two footprints for one component MUST give `altium.copper-board-mismatch` with `where` = the component path or the board reference.
- **Footprints.** A matched footprint MUST have the component's footprint link as its `lib_ref`, and the same pad numbers at the same positions in the footprint's own frame as the definition written to `<name>.PcbLib`; else `altium.copper-board-mismatch` with `where` = the component path.
- **Placements.** The board's placements win: every matched component MUST be written at the board footprint's position, rotation, side and lock, and none is staged. The copper is only right relative to the footprints as the board places them, and the exported tool project is the source of truth for layout (`design-model`, "Layout authority"). When a placement differs from the script's request, or the script requests none, the build MUST give one `altium.placement-from-board` info that names the refs.
- **Outline.** The bounding box of the board's `Edge.Cuts` graphics (or of its `Board.outline`) MUST equal the bounding box of the design's outline; else `altium.copper-board-mismatch` with `where` = `outline`.
- **Nets.** Every pad of a matched footprint MUST be on the net of the same name as the design puts its pin on, or on none in both; else `altium.copper-board-mismatch` with `where` = `<ref>.<pad number>`. A track, arc, via or zone on a net whose name the design does not hold MUST give one `altium.copper-net-missing` per net name, naming the count of items and the layer and position of the first. Copper without a net is copied without a net.
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
| `altium.copper-stack` | error | the board's copper layers are not `F.Cu`, `B.Cu` or `F.Cu`, `In1.Cu`, `In2.Cu`, `B.Cu`, their count differs from `copper`, or a plane names a layer that is not an inner layer or a net the design does not hold |
| `altium.copper-layer` | error | a track, arc, via or zone names a layer outside the board's copper layers |
| `altium.via-unsupported` | error | a via is blind, buried or micro, or does not span the top and the bottom layer |
| `altium.zone-unsupported` | error | a zone has fewer than three outline points (an outline kept as an opaque slot) |
| `altium.copper-invalid` | error | a track of zero length, a width of 0 or less, a drill not below its diameter, or a net id that names no net |
| `altium.plane-copper` | error | a track or arc lies on a plane layer, or a zone on a plane layer has another net than the plane |
| `altium.copper-board-mismatch` | error | a copper source does not match the design: a component, a footprint, a pad net or the outline |
| `altium.copper-net-missing` | error | copper of a source is on a net whose name the design does not hold |
| `altium.copper-no-document` | error | a copper source is given and the PCB document is not planned |
| `altium.zones-unpoured` | info | polygons are written without poured copper |
| `altium.plane-zone-merged` | info | a zone on a plane layer with the plane's net is left to the plane |
| `altium.placement-from-board` | info | components are placed as the board of `--copper-from` places them, not as the script requests |

- One issue MUST be given per entity (per net name for `altium.copper-net-missing`), with the entity id, component path or net name in `where` and the layer or via type in the message.
- With an error the build MUST write no file, as c0032 rules. Nothing is dropped to make a document fit.

#### Scenario: Closed set with the copper rows
- **WHEN** `uv run pytest tests/unit/lens/test_altium_issues.py -k closed_set` runs
- **THEN** every row of this table is produced by at least one test with its severity

#### Scenario: Blind via refused
- **GIVEN** the routed model with one more via of `via_type="blind"` between `F.Cu` and `In1.Cu`
- **WHEN** `build_altium` runs
- **THEN** `files` is empty and `issues` holds one `altium.via-unsupported` whose `where` is the via's id

#### Scenario: Copper on a missing layer
- **GIVEN** the routed model built with `copper=2`
- **WHEN** `build_altium` runs
- **THEN** `files` is empty and `issues` holds three `altium.copper-layer` errors: the track on `In1.Cu`, the track on `In2.Cu` and the zone

#### Scenario: Three copper layers refused
- **GIVEN** a model whose `board.layers` holds the copper layers `F.Cu`, `In1.Cu` and `B.Cu`
- **WHEN** `build_altium` runs
- **THEN** `files` is empty and `issues` holds one `altium.copper-stack` that names the three layers

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

