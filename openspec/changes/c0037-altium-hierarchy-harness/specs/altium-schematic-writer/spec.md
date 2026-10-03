## ADDED Requirements

### Requirement: Sheets of a hierarchical project
`backends.altium.hierarchy.plan_sheets(design, *, name, sheets, form, symbols=None)` SHALL split a design into one top sheet and one sheet per top-level module when `sheets` is `"modules"`, and SHALL return the single sheet of c0032 when `sheets` is `"flat"`. `project.SheetMode` is `Literal["flat", "modules"]` and `project.DEFAULT_SHEETS` is `"flat"`.
- A component's sheet is the first segment of its component path (`fenolite.path`) when the path holds a `/`, and the top sheet otherwise. So a part outside any module is on the top sheet, and a part of a nested module (`power/ldo/U1`) is on the sheet of its top-level module (`power`): deeper modules are flattened.
- The top sheet's file is `<name>.SchDoc`. A module's file is `<name>_<module>.SchDoc`. All files sit beside the project.
- The hierarchy has one level: the top sheet holds one sheet symbol per module, in module-name order, and no module sheet holds a sheet symbol. No sheet is repeated.
- A net **crosses** a module when it is not a member of a `power` interface, the module's sheet holds at least one of its pins, and another sheet holds at least one of its pins. A net of a `power` interface never crosses: its power ports are global (S-0185, `H-A-SCH-HIER-NAMES`).
- A harness interface **crosses** a module when `form` is `"binary"` and at least one of its member nets crosses that module. Its member nets that cross the module then travel in the harness and get no port or sheet entry of their own there. In the ASCII form no harness crosses, and its member nets cross as plain nets (S-0131: the ASCII place of harness records is not documented).
- The **crossings** of a module are its crossing harnesses and its other crossing nets, each named by the harness type name or the net name, in code-point order of those names. Each crossing gives one port on the module's sheet and one sheet entry on its sheet symbol, with that name (S-0185: a port joins the sheet entry of the same name).
- Every pin keeps the stub, label or power port of "Connectivity on the sheet" on its own sheet, and every component keeps its `UNIQUEID`, so the component records of a `modules` build equal those of the `flat` build except for their positions and `OWNERINDEX` values.
- The result MUST name, for every sheet, its file, its `layout.SheetPlan` and, for a module sheet, the module name and the sheet symbol's unique id. A design without a module MUST give the same top-sheet plan in both modes.
- That Altium Designer opens these sheets, builds the hierarchy from them and picks the hierarchical net scope without a project key are `H-A-SCH-HIER-OPEN` and `H-A-SCH-HIER-COMPILE`.

#### Scenario: Sheets of the hierarchy sample
- **WHEN** `plan_sheets` runs on the model of `examples/altium_hier/design.py` with `name="altium_hier"`, `sheets="modules"` and `form="binary"`
- **THEN** the sheets are `altium_hier.SchDoc` (holding `J1`), `altium_hier_flash.SchDoc` (`C2`, `R1`, `U2`) and `altium_hier_mcu.SchDoc` (`C1`, `U1`); the crossings of `flash` are `FLASH_WP` and the harness `SPI`; the crossings of `mcu` are `FLASH_WP`, `RESET_N` and the harness `SPI`; and `VDD`, `GND` and `FLASH_HOLD_N` cross nothing

#### Scenario: Nested module is flattened
- **GIVEN** a variant of the sample whose `C1` is in a module `decoupling` inside `mcu`
- **WHEN** `plan_sheets` runs with `sheets="modules"`
- **THEN** `C1` (path `mcu/decoupling/C1`) is on `altium_hier_mcu.SchDoc`, and no file is named after `decoupling`

#### Scenario: Harness members cross as nets in the ASCII form
- **WHEN** `plan_sheets` runs on the sample with `sheets="modules"` and `form="ascii"`
- **THEN** the crossings of `flash` are the nets `FLASH_WP`, `SPI_CS`, `SPI_MISO`, `SPI_MOSI` and `SPI_SCK`, and no plan holds a harness block

#### Scenario: Flat mode is c0032's sheet
- **WHEN** `plan_sheets` runs on the sample with `sheets="flat"`
- **THEN** it returns one sheet, `altium_hier.SchDoc`, whose plan equals `project.plan_sheet(design, name="altium_hier")`

### Requirement: Sheet symbols and sheet entries
The top sheet of a `modules` build SHALL hold, right after the sheet record and before the first component, one block of records per module: the sheet symbol, its sheet entries in crossing order, the sheet name and the file name (S-0130, S-0131, S-0187, S-0188).
- Sheet symbol: `RECORD=15`, `OWNERPARTID=-1`, `LOCATION.X`, `LOCATION.Y` (the **top-left** corner), `XSIZE`, `YSIZE`, `COLOR=128`, `AREACOLOR=8454016`, `ISSOLID=T`, `UNIQUEID` ("Stable component unique ids"), `SYMBOLTYPE=Normal`.
- Sheet entry: `RECORD=16`, `OWNERINDEX=<index of its sheet symbol>`, `OWNERPARTID=-1`, `SIDE=1` (the right side; no `SIDE` key for an entry on the left side, which only "Harness lines between sheet symbols" places), `DISTANCEFROMTOP=<k>`, `COLOR=128`, `AREACOLOR=8454143`, `TEXTCOLOR=128`, `TEXTFONTID=1`, `TEXTSTYLE=Full`, `NAME=<crossing name>`, then `HARNESSTYPE=<type name>` for a harness crossing only, then `ARROWKIND=Block & Triangle`. Its connection point is on the symbol's edge of that side, `k` × 100 mil below the top-left corner. No `IOTYPE` is written (unspecified).
- Sheet name: `RECORD=32`, `OWNERINDEX`, `OWNERPARTID=-1`, `LOCATION.X`, `LOCATION.Y`, `COLOR=8388608`, `FONTID=1`, `TEXT=<module name>`, 100 mil above the top-left corner. File name: `RECORD=33` with the same keys, `TEXT=<name>_<module>.SchDoc`, at the top-left corner.
- A sheet entry of a net crossing MUST get a wire stub from its connection point rightwards and a net label with the net name, by the stub and label rules of "Connectivity on the sheet" for a right pin. Labels join it to the other entries and to the top sheet's parts on that net; no wire runs between two sheet symbols.
- A sheet entry of a harness crossing MUST get a harness block ("Harness records") whose signal harness line starts at its connection point, unless a signal harness line joins it to the sheet entry of another sheet symbol ("Harness lines between sheet symbols"): it then gets no block, no wire and no label.
- These stubs and labels MUST follow the last component record and precede the first pin stub, per sheet symbol and per entry in order.
- No `INDEXINSHEET` is written, as on every Fenolite record.

#### Scenario: Symbols of the hierarchy sample
- **WHEN** the top sheet of the sample (`sheets="modules"`) is read
- **THEN** it holds 2 records 15, 5 records 16 (3 without and 2 with `HARNESSTYPE=SPI`), 2 records 32 with `TEXT=flash` and `TEXT=mcu`, 2 records 33 with `TEXT=altium_hier_flash.SchDoc` and `TEXT=altium_hier_mcu.SchDoc`, 6 wire records, 4 net labels (none of them an `SPI_*` net) and 2 power ports; the entry `SPI` of `mcu` holds no `SIDE` key

#### Scenario: Entry on the edge
- **WHEN** the entry `RESET_N` of the symbol `mcu` and its stub are read
- **THEN** the stub starts at the point `XSIZE` right of and `DISTANCEFROMTOP` × 100 mil below the symbol's top-left corner, and its label lies on the stub

#### Scenario: No symbol in the flat mode
- **WHEN** `examples/altium_sample/design.py`, which has two modules, is built with `sheets="flat"`
- **THEN** its one sheet holds no record 15, 16, 18, 32 or 33

#### Scenario: No symbol without modules
- **WHEN** `examples/altium_kicad/design.py`, which has no module, is built with `sheets="modules"`
- **THEN** its one sheet holds no record 15, 16, 18, 32 or 33, and equals the sheet of its `flat` build byte for byte

### Requirement: Ports on module sheets
A module sheet SHALL hold one port per crossing, in crossing order, after the last component record and before the first pin stub (S-0130, S-0131, S-0187, S-0188).
- Port: `RECORD=18`, `OWNERPARTID=-1`, `WIDTH`, `LOCATION.X`, `LOCATION.Y` (its left end), `COLOR=128`, `FONTID=1`, `AREACOLOR=8454143`, `TEXTCOLOR=128`, `NAME=<crossing name>`, then `HARNESSTYPE=<type name>` for a harness crossing only, then `UNIQUEID` ("Stable component unique ids") and `HEIGHT=10`. No `STYLE`, `IOTYPE` or `ALIGNMENT` is written.
- `WIDTH` MUST be `max(300, 100 · ⌈(70 · L + 150) / 100⌉)` mil for a name of `L` characters, written in units of 10 mil.
- A port's name MUST equal the name of its sheet entry on the top sheet, in the same letter case.
- A port of a net crossing MUST be followed by a wire stub from its right end (location plus width) rightwards and a net label with the net name, as for a right pin. A port of a harness crossing MUST get a harness block whose signal harness line starts at its right end.
- A module without a crossing MUST get no port; its sheet symbol then has no entry.

#### Scenario: Ports of the hierarchy sample
- **WHEN** the sheets `altium_hier_mcu.SchDoc` and `altium_hier_flash.SchDoc` of the sample are read
- **THEN** the first holds the ports `FLASH_WP`, `RESET_N` and `SPI` (the last with `HARNESSTYPE=SPI`), 16 wire records, 12 net labels and 4 power ports; the second holds the ports `FLASH_WP` and `SPI`, 17 wire records, 12 net labels and 5 power ports

#### Scenario: Port and entry names match
- **WHEN** every port of the sample's module sheets and every sheet entry of its top sheet are read
- **THEN** each module's set of port names equals the set of entry names of its sheet symbol

### Requirement: Harness records
A harness crossing SHALL be drawn on the module sheet, and on the top sheet unless "Harness lines between sheet symbols" joins its two sheet entries by a line, as one harness block: a signal harness line, a harness connector with one harness entry per entry of the type, the type record, and a labelled wire stub on each entry whose net crosses that module. `schdoc.additional_records(plan)` SHALL return the block records of a sheet in block order: the connector, its entries in code-point order of their names, the type, then the line; and after the blocks one record 218 per line of `plan.lines` (S-0130, S-0131, S-0186, S-0187, S-0188).
- Harness connector: `RECORD=215`, `OWNERPARTID=-1`, `LOCATION.X`, `LOCATION.Y` (the top-left corner), `XSIZE`, `YSIZE`, `LINEWIDTH=1`, `COLOR=13213327`, `AREACOLOR=16511725`, `PRIMARYCONNECTIONPOSITION=<p>`. Its connection point is on its left edge, `p` units of 10 mil below the top-left corner; no `HARNESSCONNECTORSIDE` is written.
- Harness entry: `RECORD=216`, `OWNERINDEX=<index of its connector in this list>` (omitted when 0), `OWNERINDEXADDITIONALLIST=T`, `OWNERPARTID=-1`, `SIDE=1`, `DISTANCEFROMTOP=<k>`, `COLOR=7354880`, `AREACOLOR=8454143`, `TEXTCOLOR=7354880`, `TEXTFONTID=1`, `TEXTSTYLE=Full`, `NAME=<entry name>`. Its connection point is on the connector's right edge, `k` × 100 mil below the top-left corner. The connector of a type with `m` entries is `(m + 1)` × 100 mil high, with the entries at `k` = 1 … `m`.
- Harness type: `RECORD=217`, `OWNERINDEX` (as the entries), `OWNERINDEXADDITIONALLIST=T`, `OWNERPARTID=-1`, `LOCATION.X`, `LOCATION.Y` (the connector's top-left corner), `COLOR=8388608`, `FONTID=1`, `TEXT=<type name>`.
- Signal harness: `RECORD=218`, `OWNERPARTID=-1`, `LINEWIDTH=2`, `COLOR=15187117`, `LOCATIONCOUNT=2`, `X1`, `Y1` (the port's right end or the sheet entry's connection point), `X2`, `Y2` (the connector's connection point), 200 mil apart on one horizontal line.
- Every block of a type MUST hold all the type's entries, on every sheet, so the drawn definitions never differ. An entry whose net crosses the block's module MUST get a wire stub rightwards and a net label with the **net** name, as for a right pin, written in `FileHeader` ("Sheet symbols and sheet entries", "Ports on module sheets"). An entry whose net does not cross that module MUST get no wire and no label, on every sheet (`H-A-SCH-HARN-UNUSED`; Altium Designer 26.5 reports such an entry as the warning "Unconnected Harness Entry", maintainer's report of 2026-10-03).
- The net keeps its own name on every sheet: the label names it, not the harness (S-0131, S-0187; `H-A-SCH-HARN-NETS`).
- A plan with a harness block or a line of `plan.lines` MUST be refused by `schdoc.write_schdoc` (the ASCII form) with `ValueError`; `plan_sheets` never makes one for that form.
- No block is written in the `flat` mode.

#### Scenario: Block of the flash sheet
- **WHEN** `additional_records` runs on the plan of `altium_hier_flash.SchDoc`
- **THEN** it returns 7 records: one 215, four 216 named `CS`, `MISO`, `MOSI` and `SCK` with `DISTANCEFROMTOP` 1 to 4 and no `OWNERINDEX`, one 217 with `TEXT=SPI`, and one 218 with `LOCATIONCOUNT=2`

#### Scenario: Line joins port and connector
- **WHEN** the port `SPI`, the record 218 and the record 215 of that sheet are read
- **THEN** the line's first point is the port's location plus its width, and its second point is `PRIMARYCONNECTIONPOSITION` units below the connector's top-left corner on its left edge

#### Scenario: Entry stubs carry net names
- **WHEN** the wires that start on the connector's right edge are read
- **THEN** there are four, at the four entries' connection points, and their labels read `SPI_CS`, `SPI_MISO`, `SPI_MOSI` and `SPI_SCK`

#### Scenario: Entry of a net that does not cross
- **WHEN** `examples/altium_hier/partial.py` (a fifth entry `HOLD` on the net `FLASH_HOLD_N`, which only the `flash` sheet uses) is written
- **THEN** each module sheet holds one block, every block holds five records 216, and no wire starts at the connection point of any `HOLD` entry

#### Scenario: Second connector names its index
- **GIVEN** a variant of the sample with a second harness `DBG` that crosses `mcu`
- **WHEN** `additional_records` runs on the plan of `altium_hier_mcu.SchDoc`
- **THEN** the entries and the type of the first block carry no `OWNERINDEX`, and those of the second block carry the index of their own record 215; on the top sheet's plan it returns the block of `DBG` and then the line of `SPI`

#### Scenario: ASCII writer refuses a block
- **WHEN** `schdoc.write_schdoc` is called on the binary-form plan of `altium_hier_flash.SchDoc`
- **THEN** it raises `ValueError` naming the harness

### Requirement: Harness lines between sheet symbols
`backends.altium.hierarchy.harness_lines(design, crossings)` SHALL name the harnesses whose two sheet entries the top sheet joins by one signal harness line, and `plan_sheets` SHALL draw that line instead of two harness blocks (S-0186, S-0187, S-0188: saved top sheets hold harness lines between sheet entries and no connector). This is the answer to step H3 of the maintainer's report of 2026-10-03: with a labelled block beside each sheet entry, Altium Designer 26.5 warned that each member net had multiple names (the net label and the names the sheet entries give it).
- A harness is joined by a line when it crosses exactly two modules, those two are neighbours in module-name order, both crossings hold the same entries wired to the same nets, and every pin of those nets is on one of the two module sheets.
- The entry on the first module's symbol MUST be on its right side and take one slot; the entry on the second module's symbol MUST be on its left side, in the same `DISTANCEFROMTOP` slot, so the line is horizontal: `RECORD=218` with `LOCATIONCOUNT=2`, from the first entry's connection point to the second's. The left side of a symbol counts its slots apart from the right side; the symbol is 100 mil higher than its lowest entry.
- The top sheet MUST then hold no connector, no wire and no net label for that harness, and no `.Harness` file is planned for a top sheet without a block. Each member net keeps the name its labels give it on the module sheets.
- When the two sheet symbols do not land side by side in one row of the top sheet (`layout.SplitLine`), or a condition above fails, the harness MUST keep a labelled harness block beside each sheet entry, as "Harness records" draws it.
- That Altium Designer then gives no "multiple names" warning, joins the members and keeps the net names is `H-A-SCH-HIER-COMPILE`, `H-A-SCH-HARN-NETS` and `H-A-SCH-HIER-NAMES`, to be checked again on the rebuilt sample.

#### Scenario: Line between two sheet symbols
- **WHEN** the top sheet of the sample (`sheets="modules"`, binary form) is read
- **THEN** its `Additional` stream holds one record 218 and no record 215, 216 or 217; the line runs from the connection point of the entry `SPI` on the right edge of the symbol `flash` to that of the entry `SPI` on the left edge of the symbol `mcu`, at one height

#### Scenario: Three modules keep their blocks
- **GIVEN** a variant of the sample with a third module whose part is on `SPI_CS`
- **WHEN** `plan_sheets` runs with `sheets="modules"` and `form="binary"`
- **THEN** `harness_lines` is empty, and the top sheet holds three harness blocks and no line

#### Scenario: A pin on the top sheet keeps the blocks
- **GIVEN** a variant of the sample with a top-sheet part on `SPI_CS`
- **WHEN** `harness_lines` runs
- **THEN** it is empty

#### Scenario: Symbols in two rows keep their blocks
- **GIVEN** a variant of the sample with three more modules, so that the symbol of `mcu` starts a second row
- **WHEN** `plan_sheets` runs with `sheets="modules"` and `form="binary"`
- **THEN** the top sheet holds two harness blocks and no line, and every sheet entry is on the right side

### Requirement: Harness definition files
`backends.altium.hierarchy.write_harness(types)` SHALL return the bytes of a harness definition file: one line `<type name>=<entry>,<entry>,…` per type, the types and the entries in code-point order, each line ending with CR LF, in 7-bit ASCII without a byte-order mark (S-0186, S-0187, S-0188).
- A sheet that holds a harness block MUST get the file `<sheet file stem>.Harness` with the types of its blocks, beside the sheet, as Altium names the files it generates (S-0187, S-0188). A sheet without a block gets none; a top sheet that only holds signal harness lines has no block.
- A type name or entry name that holds `=`, `,` or `;`, or that `ascii.text_problem` refuses, MUST raise `ValueError`.
- That Altium accepts a listed file and reports no conflicting definition is `H-A-SCH-HARN-FILE`.

#### Scenario: File of the sample
- **WHEN** `write_harness({"SPI": ("MOSI", "MISO", "SCK", "CS")})` is called
- **THEN** it returns `b"SPI=CS,MISO,MOSI,SCK\r\n"`

#### Scenario: Two files of the sample
- **WHEN** the sample is built with `sheets="modules"`
- **THEN** `altium_hier_flash.Harness` and `altium_hier_mcu.Harness` are equal, and no other `.Harness` file is planned

#### Scenario: Separator in a name
- **WHEN** `write_harness({"A=B": ("X",)})` is called
- **THEN** it raises `ValueError`

### Requirement: Project file of a multi-sheet project
`backends.altium.prjpcb.write_prjpcb(*, schematic, pcb=None, libraries=(), sheets=(), harnesses=())` SHALL list, after the documents of "Project file", each module sheet and then each harness definition file in its own section, numbered from the next free number: an empty line, `[Document<i>]` and `DocumentPath=<file>` (S-0132, S-0187, S-0188). This requirement extends "Project file", whose rules hold.
- `sheets` MUST be written in the order given (module-name order). `harnesses` MUST be written in the MS-CFB order of their names (`cfb.name_key`). A name holding `/` or `\` MUST raise `ValueError`.
- With both empty, the bytes MUST equal those of "Project file", so `[Document1]` stays the top sheet and `[Document2]` the PCB document when there is one.
- No key names the top sheet or the net scope: Altium finds the top sheet from the sheet symbols and takes its default scope (S-0185, S-0187, S-0188; `H-A-SCH-HIER-PRJ`, `H-A-SCH-HIER-COMPILE`).

#### Scenario: Project with a module sheet and a harness file
- **WHEN** `write_prjpcb(schematic="a.SchDoc", sheets=("a_x.SchDoc",), harnesses=("a.Harness",))` is called
- **THEN** it returns `b"[Design]\r\nVersion=1.0\r\n\r\n[Document1]\r\nDocumentPath=a.SchDoc\r\n\r\n[Document2]\r\nDocumentPath=a_x.SchDoc\r\n\r\n[Document3]\r\nDocumentPath=a.Harness\r\n"`

#### Scenario: Unchanged without sheets
- **WHEN** `write_prjpcb(schematic="blink.SchDoc", pcb="blink.PcbDoc", libraries=("blink.SchLib", "blink.PcbLib"))` is called
- **THEN** it returns the bytes of the scenario "Project with a PCB document and two libraries" of "Project file"

#### Scenario: Project of the hierarchy sample
- **WHEN** `altium_hier.PrjPcb` of the sample's `modules` build is read
- **THEN** its `DocumentPath` lines are, in order, `altium_hier.SchDoc`, `FenoliteHier.SchLib`, `altium_hier_flash.SchDoc`, `altium_hier_mcu.SchDoc`, `altium_hier_mcu.Harness` and `altium_hier_flash.Harness`

### Requirement: Hierarchical sheet layout
`backends.altium.layout.layout_sheet(parts, *, symbols=(), ports=())` SHALL place the sheet symbols of a top sheet and the ports of a module sheet as cells of the same packing as the components, before them. This requirement extends "Deterministic sheet layout", whose rules hold for every sheet.
- Cells MUST be, in order: one per sheet symbol (top sheet), one per port (module sheet), then the component cells of "Deterministic sheet layout".
- A sheet-symbol cell holds the symbol, its name and file-name texts, and to its right every entry stub with its label and every harness block. The symbol is at least 1500 mil wide and wide enough for its longest text; each net entry takes one 100 mil step of its right side and each harness entry `m + 2` steps for a type of `m` entries, so no two blocks touch. A harness entry that starts a line of "Harness lines between sheet symbols" takes one step and 200 mil of room to its right; the line then crosses the margins of the two cells.
- A port cell holds the port and, to its right, its stub and label or its harness block.
- `layout_sheet(parts)` without symbols and ports MUST return the plan it returns today. `SheetPlan` gains `symbols`, `ports`, `harnesses` and `lines`, each empty by default.
- Every written point MUST be a multiple of 10 mil; every cell corner, port location, sheet-symbol corner and connector corner a multiple of 100 mil. No two cells overlap. Each sheet picks its own size by the rule of "Deterministic sheet layout", and `altium.sheet-custom` names the sheet's file.

#### Scenario: Top sheet of the sample
- **WHEN** the top sheet of the sample (`sheets="modules"`) is laid out
- **THEN** its cells are, in order, the symbols `flash` and `mcu` and the part `J1`; no two cells overlap; every written point lies inside the drawing area less 500 mil; and the sheet is `A4` or the first larger ISO size that holds the packing

#### Scenario: Plan without symbols is unchanged
- **WHEN** `layout_sheet(parts)` and `layout_sheet(parts, symbols=(), ports=())` run on the part specs of `examples/altium_sample/design.py`
- **THEN** both plans are equal, and equal to the plan of the committed golden schematic

### Requirement: Hierarchy read back
The test suite SHALL read a written multi-sheet project back with a reader that shares no code with the writer, and SHALL find the model's nets. `tests/_altium_read.py` gains `nets_from_project(sheets, top)`, where `sheets` maps a file name to its records, `FileHeader` and `Additional` alike.
- On each sheet the reader MUST join pins, wires, net labels and power ports as `nets_from_sheet` does, and MUST also take as wire ends: both ends of a port, the connection point of a sheet entry, the connection point of a harness connector, and the connection point of a harness entry, each computed from the record's own keys.
- Across sheets it MUST apply the hierarchical scope (S-0185): a net label is local to its sheet; a power port joins its name on every sheet; a port joins the sheet entry of the same name on the sheet symbol whose record 33 names the port's file; nothing else joins two sheets.
- Through a harness it MUST join, for a port and its sheet entry of one type, the wire on entry `e` of the connector reached from the port by a record 218 with the wire on entry `e` of the connector reached from the sheet entry. When a record 218 runs from the sheet entry to another sheet entry of the same type, it MUST instead join entry `e` of the connectors beside the two ports. An entry without a wire joins nothing.
- The reader MUST fail when a port has no sheet entry of its name or a sheet entry no port, when a record 33 names a file that is not in `sheets`, when a record 218 end touches neither a port, a sheet entry nor a connector's connection point, when a harness sheet entry has neither a connector nor a line to a sheet entry of its type, or when two blocks of one type differ in their entry names.
- The nets it returns, as sets of `(designator, pin)`, MUST equal the model's nets, and each net MUST have exactly one name over all its labels and power ports.
- This readback is Fenolite's own check. It raises no evidence label: Altium Designer's behaviour stays under the `H-A-SCH-HIER-*` and `H-A-SCH-HARN-*` rows.

#### Scenario: Sample reads back in both forms
- **WHEN** `uv run pytest tests/unit/backends/altium/test_readback.py -k hierarchy` reads the sample's `modules` builds in the binary and the ASCII form
- **THEN** in both, the nets read back equal the model's nine nets, and each has one name

#### Scenario: Reader does not import the writer
- **WHEN** `git grep -n "fenolite.backends.altium" tests/_altium_read.py` runs
- **THEN** it prints nothing

#### Scenario: A renamed port is caught
- **GIVEN** the sample's module sheet `mcu` with the `NAME` of its port `RESET_N` changed to `RESET`
- **WHEN** `nets_from_project` runs
- **THEN** it fails, naming the port and the sheet symbol `mcu`

#### Scenario: Unwired entry joins nothing
- **WHEN** the `modules` build of `examples/altium_hier/partial.py` is read back
- **THEN** the net `FLASH_HOLD_N` holds only the pins of the `flash` sheet, and the nets equal the model's

## MODIFIED Requirements

### Requirement: Binary schematic form
`backends.altium.binary.write_schdoc_binary(plan)` SHALL return the binary form of the schematic of `plan`: a compound file (`write_compound`) with the streams `FileHeader` and then `Storage`, then `Additional` only when the plan holds harness records ("Harness records"), and no other stream (S-0002, S-0130, S-0131, S-0142, S-0147, S-0187, S-0188). This requirement extends c0032's "ASCII schematic form": the records, their keys, their order and every value are those of `schdoc.schdoc_records(plan)`, and only the header text, the framing and, on a small sheet, one last record differ.
- `FileHeader` MUST be the header record `|HEADER=Protel for Windows - Schematic Capture Binary File Version 5.0|WEIGHT=<n>`, with `<n>` the number of records after it, followed by every record of `binary.padded_records(schdoc_records(plan))`.
- `binary.padded_records(records)` MUST return `records` unchanged when their `FileHeader` stream is 4096 bytes (`binary.MINI_CUTOFF`) or more. Otherwise it MUST append one hidden sheet parameter, `RECORD=41`, `OWNERPARTID=-1`, `COLOR=8388608`, `FONTID=1`, `ISHIDDEN=T`, `TEXT`, `NAME=FenoliteNote` (the keys of a saved sheet parameter; S-0130, S-0188), whose text is `binary.NOTE_TEXT` followed by as many `.` as bring the stream to exactly 4096 bytes, or by none when the sentence alone takes it past 4096. So `FileHeader` is never stored in the compound file's mini stream, as in every sheet Altium saves (S-0187, S-0188). A module sheet whose `FileHeader` lay in the mini stream was left outside the hierarchy by Altium Designer 26.5 (step H7 of the report of 2026-10-03); that the size is the cause is `H-A-SCHBIN-MINI`.
- Every record MUST be framed as a 32-bit little-endian word whose low 24 bits are the payload length and whose top byte is 0 (a property list), followed by the payload: the record's `ascii.format_record` text, then one NUL byte, counted in the length (S-0130, S-0147, S-0148). A payload of 65 536 bytes or more MUST raise `ValueError`.
- Payload text MUST follow the byte rules of "ASCII schematic form" and "Text the ASCII form cannot carry": printable 7-bit ASCII and no `|` inside a value. No CR or LF is written in a binary schematic.
- Pins MUST stay text records (`RECORD=2`), as in the ASCII form. No record of type 1 is written (S-0131, S-0142).
- `Additional`, when written, MUST be the header record `|HEADER=Protel for Windows - Schematic Capture Binary File Version 5.0|WEIGHT=<m>`, with `<m>` the number of records after it, followed by every record of `schdoc.additional_records(plan)`, framed as the records of `FileHeader`. A plan without harness records MUST give no `Additional` stream, so its bytes are those of c0033 (`H-A-SCH-HARN-OPEN`).
- `Storage` MUST be exactly one framed record with the payload `|HEADER=Icon storage` and its NUL, 25 bytes in all, with no weight key (S-0130, S-0131, S-0142).
- `project.write_project(design, *, name, project=True, issues=None, form=DEFAULT_FORM)` MUST return this form for `form="binary"` and c0032's ASCII bytes for `form="ascii"`. `project.SchematicForm` is `Literal["binary", "ascii"]` and `project.DEFAULT_FORM` is `"binary"`. `<name>.PrjPcb` is the same in both forms.

#### Scenario: Header record of the binary sample
- **WHEN** the `FileHeader` stream of the sample's binary schematic is de-framed
- **THEN** it holds 123 records, the first payload is `|HEADER=Protel for Windows - Schematic Capture Binary File Version 5.0|WEIGHT=122` followed by a NUL, and the second starts with `|RECORD=31|`

#### Scenario: Same records in both forms
- **GIVEN** the sample's model with generic pins
- **WHEN** both forms are written and each binary payload after the header, without its NUL, is followed by CR LF
- **THEN** the joined payloads equal the ASCII file without its first line

#### Scenario: Storage stream
- **WHEN** the `Storage` stream of the sample's binary schematic is read
- **THEN** it is 25 bytes: the little-endian word 21, then `|HEADER=Icon storage` and one NUL

#### Scenario: Forms of write_project
- **WHEN** `write_project(model, name="altium_sample")` and `write_project(model, name="altium_sample", form="ascii")` are called on the sample's model with generic pins
- **THEN** the first `altium_sample.SchDoc` starts with the CFB signature, the second starts with `|HEADER=`, and both `altium_sample.PrjPcb` values are equal

#### Scenario: Small sheet is padded
- **WHEN** `examples/altium_hier_board/design.py` is built with `sheets="modules"` and its three sheets are read with `tests/_cfb_read.py`
- **THEN** the `FileHeader` stream of the top sheet and of the sheet `led` is exactly 4096 bytes, stored in regular sectors, and ends with one record 41 named `FenoliteNote`; the sheet `driver` holds no such record; and in each sheet `WEIGHT` equals the number of records after the header

#### Scenario: Large sheet is unchanged
- **WHEN** `padded_records` runs on the records of the sample's schematic
- **THEN** it returns them unchanged, and the golden files of c0033 keep their bytes

#### Scenario: No Additional stream without harnesses
- **WHEN** the sample's binary schematic and the binary top sheet of `examples/altium_hier/design.py` built with `sheets="flat"` are read with `tests/_cfb_read.py`
- **THEN** each holds exactly the streams `FileHeader` and `Storage`

#### Scenario: Additional stream of the hierarchy sample
- **WHEN** the `Additional` stream of the top sheet of `examples/altium_hier/design.py` built with `sheets="modules"` is de-framed
- **THEN** it holds 2 records, the first payload is `|HEADER=Protel for Windows - Schematic Capture Binary File Version 5.0|WEIGHT=1` followed by a NUL, and the other is one `RECORD=218`; the `Additional` stream of `altium_hier_mcu.SchDoc` holds 8 records with `WEIGHT=7`: one `RECORD=215`, 4 of `RECORD=216`, one `RECORD=217` and one `RECORD=218`

### Requirement: Stable component unique ids
`backends.altium.project.unique_id(key)` SHALL return eight letters from `A` to `Y`: the SHA-256 of `fenolite.altium.uniqueid:<key>` read as a big-endian integer, written as its eight lowest base-25 digits, least significant first, with `A` for 0 and `Y` for 24 (form: S-0130).
- A component's `UNIQUEID` MUST be `unique_id(<component id>)`. DSL component ids are keyed by component path (c0011), so the unique id depends only on the path.
- Altium links a schematic component to its PCB component by this id, and falls back on designators (S-0139); it does not repair duplicate component ids (S-0139). `lens.altium` MUST refuse two components with one unique id (`altium.unique-id-collision`).
- A sheet symbol's `UNIQUEID` MUST be `unique_id("sheet:<module path>")` and a port's MUST be `unique_id("port:<module path>:<port name>")`, so both depend only on names ("Sheet symbols and sheet entries", "Ports on module sheets"; S-0139, S-0187, S-0188). Sheet symbols carry an id because the PCB link of a part on a module sheet names it (`altium-pcb-writer`, "PCB document links and nets").
- `lens.altium` MUST refuse two of these ids that are equal, among components, sheet symbols and ports alike, with `altium.unique-id-collision`.
- Records other than components, sheet symbols and ports MUST carry no `UNIQUEID`.

#### Scenario: Form
- **WHEN** `unique_id` is called on 1000 different keys
- **THEN** every result matches `^[A-Y]{8}$`, and the same key always gives the same result

#### Scenario: Pinned value
- **WHEN** `unique_id("cmp_00000000-0000-0000-0000-000000000000")` is called
- **THEN** it returns the value pinned in `tests/unit/backends/altium/test_project.py`, computed once by the rule above

#### Scenario: Ids of the hierarchy sample
- **WHEN** `examples/altium_hier/design.py` is built with `sheets="modules"` and its sheets are read
- **THEN** the sheet symbols carry `unique_id("sheet:flash")` and `unique_id("sheet:mcu")`, every port carries `unique_id("port:<module>:<name>")`, every component carries the `UNIQUEID` it has in the `sheets="flat"` build, and no other record holds `UNIQUEID`
