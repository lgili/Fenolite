## ADDED Requirements

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
  - H7: build `examples/altium_hier_board/design.py` with `--altium-sheets modules`, open its PCB document and run "Design » Update PCB Document"; note whether the change order proposes no component and no net change (`H-A-SCH-HIER-ECO`).
- A report follows "Altium author reports": tool as `AD <major>.<minor>`, the date, one generic outcome per step, no artefact, and only Fenolite's authored or built files opened. A confirmed row gets `ALTIUM-VERIFIED(author-report; AD <major>.<minor or x>; <YYYY-MM-DD>; no artefact)`.
- `docs/hypotheses.md` MUST register the nine rows `H-A-SCH-HIER-OPEN`, `H-A-SCH-HIER-PRJ`, `H-A-SCH-HIER-COMPILE`, `H-A-SCH-HIER-NAMES`, `H-A-SCH-HIER-ECO`, `H-A-SCH-HARN-OPEN`, `H-A-SCH-HARN-FILE`, `H-A-SCH-HARN-NETS` and `H-A-SCH-HARN-UNUSED`, and `docs/evidence/sources.md` MUST register S-0185 to S-0188. No file of S-0187 or S-0188 enters the repository.

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

## MODIFIED Requirements

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
