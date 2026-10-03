## ADDED Requirements

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
- A placed component MUST take its DSL placement. An unplaced component MUST be staged right of the outline as the KiCad build stages it (`lens.build.STAGING_OFFSET`, `STAGING_GAP`, top side, angle 0), and the build MUST give one `altium.pcb-staged` info naming the staged refs.
- When the PCB document is planned, the board and the placements MUST NOT be reported by `altium.not-lowered`; net classes and differential pairs still are.
- The planned write MUST have the kind `altium_pcbdoc`, and the project file MUST list it as `[Document2]`.
- The document MUST follow c0032's edited-output rule: a document changed in Altium is refused with `FEN-7001`, and `--discard-layout` replaces it with a `.bak`. Fenolite never merges an edited document.

#### Scenario: Document of the KiCad-footprint sample
- **WHEN** `examples/blink_2layer/design.py` is built with `--target altium --confirm --json` into an empty folder `B`
- **THEN** the exit code is 0, `B/blink.PcbDoc` is written with the kind `altium_pcbdoc`, `result.pcb_document` is `B/blink.PcbDoc`, `B/blink.PrjPcb` lists it as `[Document2]`, and `issues` holds one `altium.not-lowered` (the net class `PWR`) and no `altium.pcb-staged`

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

## MODIFIED Requirements

### Requirement: Altium symbol sources
The Altium build SHALL take each lib id's symbol from one of two sources, chosen by the lib id's form; `lens.altium.symbol_source(lib_id)` returns `altium` or `kicad`.
- A lib id whose library part ends with `.SchLib` in any letter case is an Altium link (`altium`). Its symbol is generic: c0032's body over the union of the designators that the nets name on the components of that lib id (`altium-schematic-writer`, "Generic library symbols"). No library is opened for it.
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
`lens.altium.build_altium(design, *, name, placed=(), placements=None, project_exists=False, form=DEFAULT_FORM, resolver=None) -> BuildOutput` SHALL return every file of an Altium project for `design` as bytes, and SHALL return no file when any issue has severity `error`. `BuildOutput` is c0011's `lens.build.BuildOutput`.
- The steps MUST run in this order: the build checks of "Altium build issue codes"; the symbol of every lib id and the pins of every component ("Altium symbol sources": generic pins for Altium links, the symbol's pins for KiCad lib ids) set as `Component.pins`; `Design.validate()`; the footprint of every footprint link, its checks and `lens.altium.pad_extras` ("Altium footprint sources", "PCB library outputs"); the PCB document's conditions and placements ("PCB document output"); `backends.altium.project.write_project(model, name=name, project=not project_exists, issues=…, form=form, symbols=…, footprints=…, pcb=…)`, where `footprints` are the `pcblib.LibFootprint` values to write and `pcb` is a `pcbdoc.PcbDocSpec` or `None`; the `.fenolite/` texts and record; evidence.
- An issue of severity `error` before the writer MUST give a `BuildOutput` with its issues and empty `files`.
- The layout MUST be `<name>.PrjPcb` (only when `project_exists` is false), `<name>.SchDoc`, every planned `<library>.SchLib` ("Schematic library outputs"), `<name>.PcbLib` when it holds a footprint ("PCB library outputs"), `<name>.PcbDoc` when its conditions hold ("PCB document output"), the six layer files under `.fenolite/` and `.fenolite/build.json`, with the design name as stem.
- The layer texts MUST come from `canonical.dump_texts` of the model with its pins and rewritten net members, with an empty `findings.json`.
- `.fenolite/build.json` MUST be `{"design": <name>, "files": {<path>: <sha256>, …}, "schema": "fenolite.build-record.v0", "target": "altium"}` with sorted keys, no date and a final newline, and MUST record the SHA-256 of every planned file outside `.fenolite/`.
- The build MUST NOT write a project structure file, a date or an absolute path, and MUST NOT write a PCB library or PCB document other than these two.
- `summary` MUST hold `components`, `nets`, `labels`, `power_ports`, `sheet`, `schematic_format`, `libraries`, `symbols`, `footprints`, `pcb_document`, `kept` (paths relative to `--out`) and `experimental`, which `cmd_build` copies into `result`, with `kept` under `--out`.

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
