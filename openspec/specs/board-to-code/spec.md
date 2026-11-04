# board-to-code Specification

## Purpose
TBD - created by archiving change c0345-custom-footprint-field-poses. Update Purpose after archive.
## Requirements
### Requirement: Explicitly preserve custom footprint property presentation
Board import SHALL preserve representable custom property poses using typed
field requests for properties declared by that part. Unsupported source poses
SHALL refuse before staging rather than silently lowering presentation.

#### Scenario: A rotated footprint has a hidden custom property
- **WHEN** a source footprint has a custom property whose board angle differs from its body angle
- **THEN** import and fresh build retain its complete typed field pose and value
- **AND** strict geometry and rendering comparisons remain active

#### Scenario: A property pose is not representable by the public API
- **WHEN** a custom property has unsupported size, layer or an inexact board-frame anchor
- **THEN** import refuses with a located error before planning writes

#### Scenario: Unknown field name
- **WHEN** a script requests placement of a field that is neither conventional nor a declared user property
- **THEN** the DSL rejects that request

### Requirement: Current import coverage observations
Current corpus coverage expectations SHALL be measured from the same reader and complete emission ledger as `fenolite import`, with date, input SHA-256 and measurement SHA-256. They MUST be separate from historical conversion proofs. The helper MUST match full CLI results on authored and public inputs. Full corpus imports MUST still independently require exit 0 and equivalent=true, including heavy rows.

#### Scenario: DSL coverage changes
- **WHEN** the emitter gains support for a formerly unexpressed item
- **THEN** current observations change through measurement while historical equivalence and elapsed-time records remain intact

### Requirement: Teardrops in an import
`fenolite import --to python` SHALL read a via's opaque `teardrops` child and write it as `teardrop=teardrop(...)` on its via table, grouping vias by settings too. Unreadable settings MUST be counted as `teardrop-setting`, and that via MUST be written without settings.

#### Scenario: Settings kept and zones regenerated
- **GIVEN** the authored two-sheet board with the demo teardrop settings on its via at (110, 133) and one `padvia` teardrop zone (`tests/_importcode.py::teardropped`)
- **WHEN** it is imported with `--confirm` and the code is built
- **THEN** `copper.py` holds `teardrop=teardrop(` in the table of that via, `issues` hold `import.teardrops-regenerated`, `result.unexpressed` holds no teardrop kind, and the built via holds a `teardrops` child of nine children

#### Scenario: Settings lost
- **GIVEN** the same board whose via holds `(teardrops (enabled maybe))`
- **WHEN** it is imported with `--allow-lossy --dry-run`
- **THEN** `result.unexpressed` holds `teardrop` (1) and `teardrop-setting` (1), and no `import.teardrops-regenerated`

### Requirement: Blind vias over the board in an import
A blind via whose two layers are the outer copper layers SHALL be written as a row of a via table with `kind="blind"` and those layers ("Blind vias over the board in via tables"), not left out as `via-span`.

#### Scenario: Demo vias kept
- **GIVEN** the two-sheet board whose via at (130, 133) is `(via blind … (layers "F.Cu" "B.Cu"))`
- **WHEN** it is imported and built
- **THEN** the table `GND/via/1` holds that row with `kind="blind"`, `result.unexpressed` holds no `via-span`, and the built via is blind on both layers

### Requirement: Parts not populated and net ties in an import
The import SHALL write a part whose component is not populated as `Part(..., dnp=True)`, and MUST NOT count it as unexpressed. A footprint's net-tie pad groups SHALL come back with its vendored footprint and MUST NOT be counted as unexpressed.

#### Scenario: One part not populated, one net tie
- **GIVEN** the two-sheet board with R101's attribute `(attr smd dnp)` and R201 holding `(net_tie_pad_groups "1, 2")` (`tests/_importcode.py::unfitted`)
- **WHEN** it is imported with `--confirm` and the code is built
- **THEN** `result.unexpressed` is empty, `design.py` holds one `dnp=True`, and the built board holds `(attr smd dnp)` for R101 and the net-tie groups for R201

### Requirement: Groups in an import
The import SHALL write a group of the board whose members it all writes (parts, drawings, zones, rule areas and groups) as `design.group()` after the drawings, an inner group before the group that holds it, with the source name as name and key when the key pattern takes it and `key="group/<n>"` otherwise, and `locked=True` for a locked group. A group holding an item the code does not write MUST be the unexpressed kind `group`.

#### Scenario: Nested groups
- **GIVEN** the `drawn` board with a locked group `logo` of J1, a text and a dimension, an unnamed group of `logo` and a text, and a group `lost` of the hidden text (`tests/_importcode.py::drawn_grouped`)
- **WHEN** it is imported with `--allow-lossy --confirm` and built
- **THEN** `result.unexpressed` holds `group` (`lost`), `design.py` holds two `design.group()` calls, and the built board holds `logo`, locked, with the uuids of J1's footprint, the text and the dimension, and the unnamed group with the uuids of `logo` and the text

### Requirement: Board-only parts in an import
The import SHALL write footprints with shared or unnameable references (including empty and `REF**`), and footprints already marked board-only, as `Part(ref, ..., name=key, board_only=True)`. Their key MUST be the reference cut to the path alphabet (`fp` when empty), then the lowest unused `_<n>`, assigned in placement order. They MUST NOT be unexpressed or gain a lock entry.

#### Scenario: Two footprints of one reference and a REF**
- **GIVEN** the two-sheet board with R201 renamed R101 and J1 renamed `REF**` (`tests/_importcode.py::shared`)
- **WHEN** it is imported with `--confirm` and built
- **THEN** `result.unexpressed` is empty, `import.board-only` names 3 footprints of which 3 gain the attribute, `design.py` holds three `board_only=True`, and the built board holds two footprints `R101` and one `REF**`, each with `board_only`

### Requirement: Board items in an import
The import SHALL keep user layers through the highest `User.<n>` and their names; copper-graphic nets (resolving target-9 numbers); filled strokes of -1 nm as `width=None`; free vias grouped by `free`; zone smoothing and radius; mils/automatic dimension units; and silkscreen material. A dashed copper graphic or one naming an undeclared net MUST be unexpressed as `drawing`.

#### Scenario: Items of change c0277
- **GIVEN** the two-sheet board with user layers `User.1` and `User.2` (`notes`), a copper rectangle of `GND`, a filled polygon of stroke −1 nm, a text on `User.2`, a dimension in automatic units, its via at (110, 133) free and its GND zone smoothed with fillets of 0.5 mm (`tests/_importcode.py::itemized`)
- **WHEN** it is imported with `--confirm` and built
- **THEN** `result.unexpressed` is empty, the code holds each call, and the built board holds the user layers, `(net "GND")` on the rectangle, `(width -0.000001)`, `(units 3)` and one free via at (110, 133)

### Requirement: Verbatim items in an import
The import SHALL write permitted opaque root items with no DSL call as `design.verbatim("<head>/<n>", text)`, keyed in file order. Numeric nets MUST resolve through the source table and copper `members` UUIDs through their emitted table rows. A reference to omitted copper or an unknown net MUST be unexpressed by its head. Groups MAY name verbatim items by key.

#### Scenario: A tuning pattern in a group
- **GIVEN** the two-sheet board with a `generated` tuning pattern over its first track, a group `tuned` holding it, and a placement area of `/CH1/` (`tests/_importcode.py::tuned`)
- **WHEN** it is imported with `--confirm` and built
- **THEN** `result.unexpressed` is empty, `design.py` holds `design.verbatim("generated/1", …)`, `design.group("tuned", "generated/1")` and `placement="/CH1/"`, and the built board's `generated` names a track of the board in `members`, inside the group `tuned`

### Requirement: Zone arcs in an import
The import SHALL write a zone outline that the reader keeps in the zone's slots because it holds an arc — one `polygon` of `xy` and `arc` items — as `outline=` with `arc_to` steps (change c0277); another kept outline (several polygons, an unknown item) MUST stay `zone-outline`.

#### Scenario: A rounded pour
- **GIVEN** the two-sheet board whose GND zone has an arc edge through (157, 120) (`tests/_importcode.py::rounded`)
- **WHEN** it is imported with `--confirm` and built
- **THEN** `result.unexpressed` is empty, `design.py` holds `arc_to((mm("57"), mm("20")), (mm("55"), mm("28")))`, and the built zone's `pts` hold `(arc (start 155 112) (mid 157 120) (end 155 128))`

### Requirement: Outlines closed by a footprint in an import
When the root edge graphics of a source board do not close an outline and the `Edge.Cuts` of its footprints close it (change c0277), the import SHALL declare the closed outline, and the KiCad writer SHALL NOT write an edge of a created outline that the `Edge.Cuts` of a footprint of the board draws, in either direction.

#### Scenario: A notch drawn by a footprint
- **GIVEN** the two-sheet board whose left edge is an `Edge.Cuts` line of D101 instead of a root line (`tests/_importcode.py::notched`)
- **WHEN** it is imported with `--confirm` and built
- **THEN** `result.unexpressed` is empty, `design.py` holds `design.board(mm("60"), mm("40"))`, and the built board holds three root `Edge.Cuts` lines, none from (100, 140)

### Requirement: Texts and dimensions in an import
The import SHALL write supported board texts, including copper, with their preserved `knockout`, `bold`, `italic`, `face`, paired size, multiline and empty text. Hidden texts and mirrors inconsistent with the layer side MUST be unexpressed as `text`. Supported dimensions MUST preserve every representable field; unsupported styles MUST be reported without silent loss.

#### Scenario: Styled texts and an older dimension
- **GIVEN** the two-sheet board with a knocked-out bold text of size 2 × 1.25 mm, a text of two lines, an empty text, a copper text, a text with a face and italic, a hidden text, an aligned dimension with extension offset 0 and one with a prefix (`tests/_importcode.py::drawn`)
- **WHEN** it is imported with `--allow-lossy --confirm` and built
- **THEN** `result.unexpressed` is `text` (1, the hidden one) and `dimension-style` (1), `design.py` holds the five texts and `extension_offset=mm("0")`, and the built board holds `(layer "F.SilkS" knockout)` and `(font (size 2 1.25) (thickness 0.275) (bold yes))`

### Requirement: Regenerated teardrops in an import
Only `padvia` teardrop zones whose settings survive SHALL be omitted as regenerated, reported once by `import.teardrops-regenerated` (info). Pad settings remain in vendored footprints. Other teardrop types, unreadable via settings, or omitted vias/footprints holding settings MUST make every affected zone unexpressed as `teardrop`.

#### Scenario: Lost settings prevent regeneration
- **GIVEN** a source with padvia zones and a via whose settings are unreadable
- **WHEN** it is imported with loss allowed
- **THEN** `teardrop` and `teardrop-setting` are reported, with no regeneration finding

### Requirement: Board-only import accounting
The import SHALL report board-only footprints once as `import.board-only` (info), including how many gain the native attribute. Its self-check MUST pair their shared references by placement as Level 1 specifies.

#### Scenario: Already marked footprint
- **GIVEN** an already-board-only source footprint
- **WHEN** it is imported
- **THEN** it stays board-only, counts in the finding, and does not count as gaining the attribute

### Requirement: Imported placement areas and pad geometry
The import SHALL keep placement areas as `placement=` and preserve bottom-footprint chamfers and pads of one number assigned to distinct unconnected nets. A disabled placement without a sheet SHALL mean no placement; another unsupported placement MUST be `rule-area-placement`.

#### Scenario: Supported native placements
- **GIVEN** the authored tuned board and its `/CH1/` placement area
- **WHEN** it is imported and rebuilt
- **THEN** the placement sheet name and supported pad geometry survive

### Requirement: Imported dimension style coverage
Aligned and orthogonal dimensions SHALL use `design.dimension()` when their format/style matches a created dimension, preserving line width and `extension_offset`. Another format/style MUST be `dimension-style`; an unrepresented dimension kind MUST be `dimension`. Other supported kinds SHALL use their corresponding DSL calls.

#### Scenario: Prefix cannot be represented
- **GIVEN** an aligned dimension with a prefix
- **WHEN** it is imported
- **THEN** `dimension-style` reports the unsupported prefix rather than silently dropping it

### Requirement: Import to code
`fenolite import PATH --to python --out DIR` SHALL write a Fenolite project folder whose `design.py` rebuilds the board read from `PATH`, under the mutation protocol, all files or none. It MUST run no subprocess other than the `kicad-cli` upgrade of "Old KiCad inputs upgraded on copies", open no network connection and write nothing outside `DIR`.

#### Scenario: Plan of an authored board
- **WHEN** `fenolite import tests/data/import_python/two_sheet/two_sheet.kicad_pro --to python --out out --dry-run --json` runs
- **THEN** the exit code is 0, `result.plan` lists `out/design.py`, `out/copper.py`, `out/design.lock`, `out/fp-lib-table`, `out/sym-lib-table`, `out/PROVENANCE.json` and files under `out/sheets/` and `out/lib/`, and no file exists under `out`

#### Scenario: Confirmed import
- **WHEN** the same command runs with `--confirm --plan <plan_id>`
- **THEN** the exit code is 0, every planned file exists with the SHA-256 of the receipt, and nothing else was written

### Requirement: Import inputs
The import SHALL accept a KiCad `.kicad_pro`, `.kicad_pcb` or `.kicad_sch` (its project beside it) of a readable or upgradable version, and an Altium `.PrjPcb` or `.PcbDoc`. Any other input MUST exit 2 with `FEN-2001` naming the file kind. A board without a schematic MUST import, with parts from footprints and nets from pad nets. `--out` that is the source folder or holds it MUST exit 2 with `FEN-2001`.

#### Scenario: Eagle board refused
- **WHEN** `fenolite import board.brd --to python --out out --dry-run` runs
- **THEN** the exit code is 2, stderr carries `FEN-2001` naming the kind, and nothing is planned

#### Scenario: Output over the source refused
- **WHEN** the import runs with `--out` equal to the folder of `PATH`
- **THEN** the exit code is 2 with `FEN-2001` and nothing is planned

#### Scenario: Board without a schematic
- **GIVEN** an authored `.kicad_pcb` with no schematic beside it
- **WHEN** it is imported with `--confirm` and the emitted code is built
- **THEN** the built board has the source's references, footprints and pad nets

### Requirement: Emitted design content
`design.py` SHALL hold, in this order: the provenance header, imports, the design, board and outline, cut-outs and slots, stack-up, nets, net classes, pairs, rules, sheet calls, top-level parts with placements, zones, rule areas, drawings and the copper call. Coordinates MUST be the source points minus `BOARD_ORIGIN`, lengths exact decimals of `mm()`, and the source lock flags kept.

#### Scenario: Positions survive exactly
- **GIVEN** an authored board whose part `J1` sits at (102.54 mm, 110 mm), rotation 90, locked
- **WHEN** it is imported and the emitted code is built
- **THEN** `design.py` holds `place(mm("2.54"), mm("10"), rot=90, locked=True)` and the built footprint `J1` is at (102 540 000 nm, 110 000 000 nm)

#### Scenario: Net classes and pairs kept
- **GIVEN** an authored project with the net class `Power` and the pair `USB_D`
- **WHEN** it is imported and built
- **THEN** the built project holds the class with its lengths and members and the pair with its two nets

### Requirement: Modules per sheet
Each source sheet SHALL become `sheets/<module>.py` with one function `sheet(design, *, path, refs=None, **nets)`; a repeated sheet SHALL be one file called once per instance. Nets MUST keep their source names, be created in the deepest sheet holding all their pins, and cross sheets as keyword arguments. A single-sheet source MUST write no `sheets/` folder.

#### Scenario: Repeated sheet
- **GIVEN** an authored project whose sheet `channel` is used twice, with refs `R101` and `R201` for one resistor
- **WHEN** it is imported
- **THEN** `sheets/channel.py` exists once, `design.py` calls it for both instances with `refs` mapping `R101` to each instance's ref, and the built components are `ch1/R101` (ref `R101`) and `ch2/R101` (ref `R201`)

#### Scenario: Sheet name sanitized
- **GIVEN** a sheet file `Power Supply.kicad_sch`
- **WHEN** it is imported
- **THEN** the module is `sheets/power_supply.py` and `import.sheet-renamed` (info) names both

### Requirement: Keys and lock of imported code
Every part SHALL have an explicit ref and a c0249 key, every copper item, zone, rule area and drawing a key, and `design.lock` SHALL record every key and ref. Building the emitted code with `--frozen` MUST change no lock entry. Keys MUST come from names, paths and sorted coordinates only.

#### Scenario: Frozen build of the import
- **GIVEN** a confirmed import of the authored two-sheet project
- **WHEN** `fenolite build out/design.py --out built --frozen --dry-run --json` runs
- **THEN** the exit code is not 7 and `result.lock.changes` is empty

### Requirement: Copper as tables
`copper.py` SHALL write the tracks, arcs and vias of the source as `track_table`, `arc_table` and `via_table` calls ("Copper tables in the DSL"), one table per group of equal net, layer, width or via sizes, kind, layers, protection and lock flag, keyed `<net>/<layer>/<n>`, rows sorted by coordinates.

#### Scenario: Every segment once
- **GIVEN** an authored board with 40 track segments, 3 arcs and 6 vias on two nets
- **WHEN** it is imported and the code is built
- **THEN** the built board holds the same 40 segments, 3 arcs and 6 vias with equal geometry, nets, layers, widths and lock flags, and no table row is repeated

### Requirement: Vendored library of an import
The import SHALL write the footprints of the board under `lib/<nickname>.pretty/` through the model form of the library derive, the symbols under `lib/<nickname>.kicad_sym`, and project tables `fp-lib-table` and `sym-lib-table` naming `${KIPRJMOD}/lib/…`. A differing instance MUST be written as `<name>_2` with `import.footprint-variant` (info).

#### Scenario: Build uses only the vendored library
- **GIVEN** a confirmed import and an empty `KICAD_CONFIG_HOME` with no library install
- **WHEN** the emitted code is built
- **THEN** every lib id resolves from a `project` row and the build exits 0

#### Scenario: Edited instance
- **GIVEN** an authored board with two `R_0603` instances, one with a pad moved
- **WHEN** it is imported
- **THEN** `lib/` holds `R_0603.kicad_mod` and `R_0603_2.kicad_mod`, the second part names `R_0603_2`, and one `import.footprint-variant` is reported

### Requirement: Provenance of an import
Every emitted `.py` SHALL start with the lines `SPDX-License-Identifier`, `SPDX-FileCopyrightText`, `Converted from <URL>@<REV> by Fenolite <version> on <date>;` and the modification note. `PROVENANCE.json` (`fenolite.import-provenance.v0`, canonical JSON) MUST record inputs with SHA-256, upgrades, tool versions, findings and the self-check. Files of `--licence-file` MUST be copied unchanged.

#### Scenario: Header and record
- **WHEN** the authored project is imported with `--licence CC0-1.0 --source https://example.invalid/b.git --revision abc123 --timestamp 2026-10-30T00:00:00Z`
- **THEN** each emitted `.py` starts with `# SPDX-License-Identifier: CC0-1.0` and holds `Converted from https://example.invalid/b.git@abc123`, and `PROVENANCE.json` lists every input with its SHA-256

#### Scenario: Missing licence
- **WHEN** the import runs without `--licence`
- **THEN** the header holds `NOASSERTION` and `import.provenance-missing` (warning) is reported

### Requirement: Unexpressed items need consent
An item of the source that no DSL call expresses SHALL be listed in `result.unexpressed`. Without `--allow-lossy` the import MUST exit 7 with `FEN-7001`, one issue per kind, and write nothing. With it, each item MUST be written as a verbatim item when the DSL has one, else left out with `import.item-unexpressed` (warning) per kind; never silently.

#### Scenario: Group refused without consent
- **GIVEN** an authored board holding a `group` and a DSL without groups
- **WHEN** it is imported with `--dry-run`
- **THEN** the exit code is 7, stderr carries `FEN-7001`, and `issues` names the kind `group`

#### Scenario: Group reported with consent
- **WHEN** the same import runs with `--allow-lossy`
- **THEN** the plan is made and `import.item-unexpressed` names `group` with its count

### Requirement: Self-check of an import
Unless `--no-verify`, the import SHALL build the emitted code in a private temporary folder and compare the result with the source through `fenolite.api.equivalent` at levels 1 to 5 under the profile `import`. A difference not explained by `result.unexpressed` MUST give `import.unequal` (error), exit 5, and write nothing.

#### Scenario: Equal at five levels
- **WHEN** the authored two-sheet project is imported with `--dry-run --json`
- **THEN** `result.equivalence` is `{"levels": [1, 2, 3, 4, 5], "equivalent": true}`

#### Scenario: Emitter bug caught
- **GIVEN** a test emitter that drops one via
- **WHEN** the import runs
- **THEN** the exit code is 5, `import.unequal` names level 5 and the net, and nothing is planned

### Requirement: Old KiCad inputs upgraded on copies
A KiCad board or schematic below the read floor SHALL be copied with its project files into a private temporary folder and upgraded there by `KicadCli.upgrade_board` or `upgrade_schematic`; the source MUST stay unchanged. Each upgrade MUST be recorded with the tool version, versions and SHA-256 before and after, and `import.upgraded` (info). `--no-upgrade` MUST exit 3 with `FEN-3003`.

#### Scenario: KiCad 7 board
- **GIVEN** `kicad-cli` 10.0.6 and an authored board with `(version 20221018)`
- **WHEN** it is imported with `--confirm`
- **THEN** the exit code is 0, `result.upgrade` holds one row with `from_version` 20221018 and both digests, and the source file's bytes are unchanged

#### Scenario: No kicad-cli
- **GIVEN** the same board and no `kicad-cli` on the path
- **WHEN** it is imported
- **THEN** the exit code is 6 with `FEN-6001`, and the hint names `--no-upgrade`

### Requirement: Altium inputs of an import
An Altium project or PCB document SHALL be read by Fenolite's Altium reader and emitted by the same emitter. Records the model keeps opaque MUST count as unexpressed items. An Altium symbol MUST be written from its pins by the symbol generator with `import.symbol-regenerated` (info).

#### Scenario: Fenolite-written Altium document
- **GIVEN** the PCB document that `fenolite build --target altium` writes for the blink example
- **WHEN** it is imported with `--confirm` and the code is built for KiCad
- **THEN** `equivalent` at levels 1 to 4 against the Altium source reports no difference

### Requirement: Deterministic imports
Two imports of the same inputs with the same flags and `--timestamp` SHALL write the same bytes, whatever `--seed`, `PYTHONHASHSEED`, platform or working directory. No emitted file MUST hold an absolute path. Every emitted `.py` MUST be left unchanged by `ruff format` at line length 110.

#### Scenario: Same bytes twice
- **WHEN** `uv run pytest tests/unit/importer/test_determinism.py -q` imports the authored project twice with different `PYTHONHASHSEED` values and working directories
- **THEN** every file has the same SHA-256 in both runs and `ruff format --check` passes on the emitted code

### Requirement: Import result and codes
The `result` of `fenolite import` (schema `fenolite.import.v0`) SHALL hold `source`, `out`, `files`, `modules`, `counts`, `unexpressed`, `upgrade`, `equivalence`, `provenance` and `adopted`; `files` and `unexpressed` MUST be paged by `--limit`. The `import.*` codes MUST be listed in `explain.toml` and `docs/import.md`.

#### Scenario: Schema and explain
- **WHEN** `uv run pytest tests/consistency -q` runs and `fenolite explain import.unequal` is called
- **THEN** the import's result validates against `fenolite.import.v0.json` and the explanation names the self-check

### Requirement: Corpus measurement records
The corpus proof SHALL write an aggregate JSON measurement per temporary test case before asserting success. CI MUST retain these records on failure. Records MUST contain counts and verdicts only, without source payloads. Exit-code, equivalence and omission-count assertions MUST remain enforced.

#### Scenario: A stale census remains diagnosable
- **WHEN** the corpus job finds an omission count unlike its recorded row
- **THEN** the job fails and retains its measured counts for reviewed table regeneration

### Requirement: Active schematic symbols beside native board-only metadata
An import with a unique physical reference and an active matching source schematic symbol MUST retain that symbol as a normal code part while preserving the native PCB `board_only` attribute. The attribute alone MUST NOT erase the drawing. Unmatched, duplicate or invalid physical references MUST retain existing board-only/keyed behavior and strict electrical checks.

#### Scenario: Native flag and actual source symbol
- **WHEN** an authored project has a netted schematic symbol and its PCB footprint carries `board_only`
- **THEN** strict import/build compares all nine levels equal, the symbol survives, the native attribute remains and duplicate/unmatched cases retain their guards

### Requirement: Embedded source aliases
An unqualified embedded `lib_name` alias SHALL be vendored under the namespace of its instance's original library id, using `_Source` only when that id is also unqualified. Its native body and poses MUST survive. Extraction and lowering MUST use the same canonical identity; conflicting bodies under that identity MUST still refuse before staging.

#### Scenario: Local embedded copies
- **WHEN** authored ordinary and power symbols use bare embedded aliases and are strictly imported and built
- **THEN** the project libraries are valid, all nine fidelity levels compare equal, and every original input byte remains unchanged

### Requirement: Source drawings in KiCad project imports
A KiCad project import SHALL emit `schematic.toml` and `load_schematic`, preserving source drawing items, embedded symbol slots, power definitions and instance references. It MUST self-check the written drawing before staging. Conflicting definitions, missing symbols or unsupported poses MUST refuse explicitly. Board-only inputs MUST keep their bytes; source files MUST remain unchanged.

#### Scenario: Drawn project survives import
- **WHEN** an authored project with junctions, buses or repeated sheets is imported, confirmed and built
- **THEN** the source drawing and symbol geometry survive, the drawn connectivity guard runs, and every input byte remains unchanged

#### Scenario: Written connectivity defect
- **GIVEN** the drawn writer is patched to move a connected wire
- **WHEN** an import self-check builds the emitted project
- **THEN** the import reports failure and plans no output writes

#### Scenario: Source symbol conflict
- **GIVEN** two source sheets embed different bodies under one library id
- **WHEN** the project is imported
- **THEN** the import refuses with the conflicting id and source sheet named, before any file is staged

### Requirement: Import record marks a copy
`PROVENANCE.json` written by the import SHALL hold `"copy": true`. `fenolite.importer.provenance.copy_mode(data)` SHALL return whether a provenance value marks a copy: an import record (`schema` `fenolite.import-provenance.v0`), or a record whose member `import` is one, whose `copy` is not `false`. A record without the member counts as a copy.

#### Scenario: Written and read
- **WHEN** `uv run pytest tests/unit/importer/test_copy_mode.py` imports the authored two-sheet project
- **THEN** the planned `PROVENANCE.json` holds `copy` `true`, `copy_mode` of it is true, of a library record holding it as `import` true, of a record with `copy` `false` false, and of a provenance file without an import record false

### Requirement: Pads on no net in the vendored symbols
The symbol drawn for a vendored footprint SHALL have no pin for a pad number that is on no net in every instance of that footprint in the source, so the build leaves those pads on no net; a number on a net in any instance keeps its pin.

#### Scenario: Shield pads stay on no net
- **GIVEN** an authored board whose connector has two pads `0` on no net beside numbered pads on nets
- **WHEN** `uv run pytest tests/unit/importer/test_no_net_pads.py` imports it and builds the emitted code with its schematic
- **THEN** the symbol has no pin `0`, both pads `0` of the built board are on no net, and level 2 against the source reports no difference

### Requirement: Outline width and layer table reported
The import SHALL report `outline-width` for root `Edge.Cuts` strokes it cannot represent, and `layer-table` when the source's non-copper layer names differ from the created table. A uniform nonnegative width MUST be preserved through `outline_width=` (c0317); mixed or negative widths MUST remain reported. Strict import MUST refuse any remaining unexpressed content.

#### Scenario: Mixed outline widths and short layer table
- **GIVEN** an authored board whose outline uses two stroke widths and whose layer table has no `Eco1.User` and `Eco2.User`
- **WHEN** `uv run pytest tests/unit/importer/test_unexpressed_c0281.py` imports it with `--allow-lossy --dry-run`
- **THEN** `result.unexpressed` holds `outline-width` with the count of outline items and `layer-table` naming the missing layers, and without `--allow-lossy` the exit code is 7

### Requirement: Uniform outline strokes in an import
The import SHALL preserve a uniform nonnegative root `Edge.Cuts` width through `outline_width=` when it differs from the default. Mixed or negative root widths MUST remain `outline-width` findings and refuse strict import. `layer-table` MUST still report source non-copper names differing from the created table. Other unexpressed content MUST remain refused.

#### Scenario: Wide outline and short layer table
- **GIVEN** an authored board with one nondefault outline width and no `Eco1.User` or `Eco2.User`
- **WHEN** it is imported
- **THEN** the width is emitted, only the missing layers are reported, and strict import refuses them

#### Scenario: Mixed stroke widths
- **GIVEN** an authored board whose root edges use two widths
- **WHEN** it is imported without lossy permission
- **THEN** it exits 7 with located `outline-width` findings and writes nothing

### Requirement: Import supported technical layer tables exactly
Strict import SHALL emit technical_layers only when a supported source table differs from the default. Rebuilding the reviewed script MUST preserve the source technical names exactly. Unknown names, missing Edge.Cuts and unrelated unsupported content MUST remain explicit refusals; layer equivalence and acceptance policies MUST remain unchanged.

#### Scenario: Source omits both Eco rows
- **GIVEN** an authored source board omitting unused Eco1.User and Eco2.User
- **WHEN** strict import-copy and an explicit build run
- **THEN** no layer-table loss is reported and the rebuilt technical rows equal the source

#### Scenario: Other unsupported source content
- **WHEN** a source combines a supported short table with mixed outline widths or unknown layers
- **THEN** only concretely represented rows leave the ledger and unsupported content still refuses import

### Requirement: Strict imported drawn effects
Import SHALL preserve supported drawn effects through the actual written-byte self-check and reviewed replay. Unrepresentable effects MUST refuse before staging. Original source bytes, existing loss policy and accepted-difference records MUST remain unchanged by the font repair.

#### Scenario: Reviewed font conversion
- **GIVEN** an original authored project with styled fields and routed copper
- **WHEN** strict import, reviewed confirmation and verify-source run
- **THEN** all nine levels are equal with zero accepted differences and unchanged source bytes

#### Scenario: Unsupported font has no plan
- **WHEN** a source typed item has an unsupported native effect
- **THEN** strict import refuses before offering a write plan

