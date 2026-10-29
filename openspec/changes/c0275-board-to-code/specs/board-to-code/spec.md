## ADDED Requirements

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
