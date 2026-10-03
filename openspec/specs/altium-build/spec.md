# altium-build Specification

## Purpose
Build a design script into an experimental Altium project with `fenolite build --target altium`: which files are written, the issues the build reports, when an edited output is refused, how builds stay reproducible, and the evidence the outputs carry. The committed samples and the protocol of the maintainer's author reports belong here; the bytes of each file belong to the writer capabilities.
## Requirements
### Requirement: Altium build target
`fenolite build DESIGN.py --out DIR --target altium` SHALL build the design into an experimental Altium project instead of a KiCad project. This requirement adds the option `--target` to the `design-dsl` requirement "Build command", whose rules hold unchanged for `--target kicad`, the default.
- `--target` MUST accept `kicad` and `altium`. Any other value MUST be a usage error (exit 2, `FEN-2001`).
- With `--target altium`, `cmd_build` MUST run the script, convert it with `to_model` and `placements` (a `DslError` of either becoming `DesignScriptError`, `FEN-3004`, as for KiCad), build it with `lens.altium.build_altium(model, name=<design name>, placed=<placed component paths>, project_exists=<DIR/<name>.PrjPcb is a file>, form=<form>, resolver=<resolver>)`, where `<resolver>` is a `LibraryResolver` built as for `--target kicad` (`LibraryConfig(target_major=<--kicad-version>, project_dir=<the script's folder>)`) when `lens.altium.kicad_lib_ids(model)` is not empty, and `None` otherwise, read the record once with `lens.build.read_record(DIR)`, call `lens.build.check_existing` with every planned file before it returns the plan, and return every file of the `BuildOutput` as a planned write under `DIR`, sorted by path.
- It MUST read only the symbol libraries of KiCad lib ids, through that resolver (`altium-build`, "Altium symbol sources"). It MUST NOT open a footprint library, parse an Altium file or start an external tool. `check_existing` only compares the bytes and hashes of existing outputs.
- The `--out` rule, `input`, `script_output`, the mutation protocol, `--seed`, `--timestamp`, `--no-backup` and `--discard-layout` MUST behave as for `--target kicad`. `--kicad-version` MUST change planned bytes only through the library configuration it selects for KiCad lib ids, and `--allow-lossy` MUST NOT change any planned byte.
- `result` MUST hold `design` (the name), `target` (the string `altium`), `out`, `files` (the planned paths), `components`, `nets`, `labels` and `power_ports` (counts), `sheet` (the sheet size name, or `custom`), `schematic_format`, `libraries` (the planned library paths), `symbols` (the number of library components), `kept` (output paths that exist and are not planned), `experimental` (`true`) and `script_output`, plus the dispatcher's `plan`.
- Planned writes MUST have the kinds `altium_prjpcb`, `altium_schdoc_binary` or `altium_schdoc_ascii` (c0033), `altium_schlib` and `fenolite` (files under `.fenolite/`).

#### Scenario: Dry run of the sample
- **GIVEN** an empty folder `B`
- **WHEN** `fenolite build examples/altium_sample/design.py --out B --target altium --dry-run --json` runs
- **THEN** the exit code is 0, `result.plan` lists `B/altium_sample.PrjPcb`, `B/altium_sample.SchDoc`, `B/FenoliteSample.SchLib` and seven files under `B/.fenolite/`, `result.target` is `altium`, `result.experimental` is `true`, and `B` is still empty

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
- **THEN** the exit code is 0, no resolver is built, and no issue code starts with `kicad.lib.`

### Requirement: Altium build outputs
`lens.altium.build_altium(design, *, name, placed=(), project_exists=False, form=DEFAULT_FORM, resolver=None) -> BuildOutput` SHALL return every file of an Altium project for `design` as bytes, and SHALL return no file when any issue has severity `error`. `BuildOutput` is c0011's `lens.build.BuildOutput`.
- The steps MUST run in this order: the build checks of "Altium build issue codes"; the symbol of every lib id and the pins of every component ("Altium symbol sources": generic pins for Altium links, the symbol's pins for KiCad lib ids) set as `Component.pins`; `Design.validate()`; `backends.altium.project.write_project(model, name=name, project=not project_exists, issues=…, form=form, symbols=…)`; the `.fenolite/` texts and record; evidence.
- An issue of severity `error` before the writer MUST give a `BuildOutput` with its issues and empty `files`.
- The layout MUST be `<name>.PrjPcb` (only when `project_exists` is false), `<name>.SchDoc`, every planned `<library>.SchLib` ("Schematic library outputs"), the six layer files under `.fenolite/` and `.fenolite/build.json`, with the design name as stem.
- The layer texts MUST come from `canonical.dump_texts` of the model with its pins and rewritten net members, with an empty `findings.json`.
- `.fenolite/build.json` MUST be `{"design": <name>, "files": {<path>: <sha256>, …}, "schema": "fenolite.build-record.v0", "target": "altium"}` with sorted keys, no date and a final newline, and MUST record the SHA-256 of every planned file outside `.fenolite/`.
- The build MUST NOT write a PCB library, a PCB document, a project structure file, a date or an absolute path.
- `summary` MUST hold `components`, `nets`, `labels`, `power_ports`, `sheet`, `schematic_format`, `libraries`, `symbols`, `kept` (paths relative to `--out`) and `experimental`, which `cmd_build` copies into `result`, with `kept` under `--out`.

#### Scenario: Files of the sample
- **WHEN** `build_altium` runs on the model of `examples/altium_sample/design.py` with `project_exists=False`
- **THEN** `files` holds exactly `altium_sample.PrjPcb`, `altium_sample.SchDoc`, `FenoliteSample.SchLib`, the six layer files under `.fenolite/` and `.fenolite/build.json`, and `issues` holds no issue of severity `warning` or `error`

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
- A lib id whose library part ends with `.SchLib` in any letter case is an Altium link (`altium`). Its symbol is generic: c0032's body over the union of the designators that the nets name on the components of that lib id (`altium-schematic-writer`, "Generic library symbols"). No library is opened for it.
- Every other lib id is a KiCad lib id (`kicad`). Its symbol MUST be resolved with c0011's `LibraryResolver.symbol` and mapped with `altsym.from_symbol_def`. A lib id that does not resolve MUST raise c0011's `UnresolvedLibrariesError` (`FEN-3001`) with its `kicad.lib.*` issues, which pass through like `model.*` codes, and nothing is written.
- A component of a KiCad lib id MUST get one pin per pin number of body style 1 and the common style, over units 1 … n in order, with the pin's name and electrical type, ids keyed `pin:<path>:<number>`. A net member that names a pin number MUST stay; one that names a pin name MUST be rewritten to every pin number with that name; one that names neither MUST give `altium.unknown-pin`.
- A component of a KiCad lib id without `footprint` MUST take the symbol's `Footprint` property, which then follows c0032's footprint-form check. Footprint libraries are never opened.
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

