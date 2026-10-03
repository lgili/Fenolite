# altium-build Specification

## Purpose
Build a design script into an experimental Altium project with `fenolite build --target altium`: which files are written, the issues the build reports, when an edited output is refused, how builds stay reproducible, and the evidence the outputs carry. The committed samples and the protocol of the maintainer's author reports belong here; the bytes of each file belong to the writer capabilities.
## Requirements
### Requirement: Altium build target
`fenolite build DESIGN.py --out DIR --target altium` SHALL build the design into an experimental Altium project instead of a KiCad project. This requirement adds the option `--target` to the `design-dsl` requirement "Build command", whose rules hold unchanged for `--target kicad`, the default.
- `--target` MUST accept `kicad` and `altium`. Any other value MUST be a usage error (exit 2, `FEN-2001`).
- With `--target altium`, `cmd_build` MUST run the script, convert it with `to_model` and `placements` (a `DslError` of either becoming `DesignScriptError`, `FEN-3004`, as for KiCad), build it with `lens.altium.build_altium(model, name=<design name>, placed=<placed component paths>, project_exists=<DIR/<name>.PrjPcb is a file>)`, read the record once with `lens.build.read_record(DIR)`, call `lens.build.check_existing` with every planned file before it returns the plan, and return every file of the `BuildOutput` as a planned write under `DIR`, sorted by path.
- It MUST NOT build a `LibraryResolver`, open any library, parse a KiCad or Altium file, or start an external tool. `check_existing` only compares the bytes and hashes of existing outputs.
- The `--out` rule, `input`, `script_output`, the mutation protocol, `--seed`, `--timestamp`, `--no-backup` and `--discard-layout` MUST behave as for `--target kicad`. `--kicad-version` and `--allow-lossy` MUST NOT change any planned byte.
- `result` MUST hold `design` (the name), `target` (the string `altium`), `out`, `files` (the planned paths), `components`, `nets`, `labels` and `power_ports` (counts), `sheet` (the sheet size name, or `custom`), `kept` (output paths that exist and are not planned), `experimental` (`true`) and `script_output`, plus the dispatcher's `plan`.
- Planned writes MUST have the kinds `altium_prjpcb`, `altium_schdoc_ascii` and `fenolite` (files under `.fenolite/`).

#### Scenario: Dry run of the sample
- **GIVEN** an empty folder `B`
- **WHEN** `fenolite build examples/altium_sample/design.py --out B --target altium --dry-run --json` runs
- **THEN** the exit code is 0, `result.plan` lists `B/altium_sample.PrjPcb`, `B/altium_sample.SchDoc` and seven files under `B/.fenolite/`, `result.target` is `altium`, `result.experimental` is `true`, and `B` is still empty

#### Scenario: Confirmed build
- **WHEN** the same command runs with `--confirm` instead of `--dry-run`
- **THEN** the exit code is 0 and `receipt.written` lists the nine planned files with their SHA-256

#### Scenario: Unknown target
- **WHEN** `fenolite build examples/altium_sample/design.py --out B --target eagle --dry-run` runs
- **THEN** the exit code is 2, stderr carries `FEN-2001`, and nothing is written

#### Scenario: Default target unchanged
- **WHEN** `fenolite build examples/blink_2layer/design.py --out B --dry-run --json` runs with and without `--target kicad`
- **THEN** both `result` objects are equal, `result.target` is `10`, and no planned path ends in `.SchDoc` or `.PrjPcb`

#### Scenario: No library is read
- **GIVEN** `KICAD_CONFIG_HOME` set to an empty folder and the sample, whose libraries exist nowhere on the machine
- **WHEN** it is built with `--target altium --dry-run --json`
- **THEN** the exit code is 0, and no issue code starts with `kicad.lib.`

### Requirement: Altium build outputs
`lens.altium.build_altium(design, *, name, placed=(), project_exists=False) -> BuildOutput` SHALL return every file of an Altium project for `design` as bytes, and SHALL return no file when any issue has severity `error`. `BuildOutput` is c0011's `lens.build.BuildOutput`.
- The steps MUST run in this order: the build checks of "Altium build issue codes"; generic pins (`altium-schematic-writer`, "Generic component bodies") set as `Component.pins`; `Design.validate()`; `backends.altium.project.write_project(model, name=name, project=not project_exists, issues=…)`; the `.fenolite/` texts and record; evidence.
- An issue of severity `error` before the writer MUST give a `BuildOutput` with its issues and empty `files`.
- The layout MUST be `<name>.PrjPcb` (only when `project_exists` is false), `<name>.SchDoc`, the six layer files under `.fenolite/` and `.fenolite/build.json`, with the design name as stem.
- The layer texts MUST come from `canonical.dump_texts` of the model with generic pins, with an empty `findings.json`.
- `.fenolite/build.json` MUST be `{"design": <name>, "files": {<path>: <sha256>, …}, "schema": "fenolite.build-record.v0", "target": "altium"}` with sorted keys, no date and a final newline, and MUST record the SHA-256 of every planned file outside `.fenolite/`.
- The build MUST NOT write a library, a PCB document, a project structure file, a date or an absolute path.
- `summary` MUST hold `components`, `nets`, `labels`, `power_ports`, `sheet`, `kept` (paths relative to `--out`) and `experimental`, which `cmd_build` copies into `result`, with `kept` under `--out`.

#### Scenario: Files of the sample
- **WHEN** `build_altium` runs on the model of `examples/altium_sample/design.py` with `project_exists=False`
- **THEN** `files` holds exactly `altium_sample.PrjPcb`, `altium_sample.SchDoc`, the six layer files under `.fenolite/` and `.fenolite/build.json`, and `issues` holds no issue of severity `warning` or `error`

#### Scenario: Build record
- **WHEN** `.fenolite/build.json` of the sample build is read
- **THEN** its `schema` is `fenolite.build-record.v0`, its `target` is `altium`, it holds no date, and it maps `altium_sample.PrjPcb` and `altium_sample.SchDoc` to their SHA-256

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

