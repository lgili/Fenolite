## ADDED Requirements

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

## MODIFIED Requirements

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
