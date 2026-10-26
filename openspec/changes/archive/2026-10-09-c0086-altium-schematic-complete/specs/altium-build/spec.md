## ADDED Requirements

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

## MODIFIED Requirements

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
