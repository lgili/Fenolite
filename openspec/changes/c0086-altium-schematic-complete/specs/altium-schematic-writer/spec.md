## ADDED Requirements

### Requirement: Symbol graphics in libraries and bodies
`backends.altium.altsym.from_symbol_def(symbol, *, lib_ref, footprint, issues, unmodelled=(), bodies="graphics")` SHALL, with `bodies="graphics"`, map the graphics of a `SymbolDef` to schematic records of their kind, in the symbol's frame, for the library and for the body on the sheet alike. `altsym.SymbolBodies` is `Literal["generic", "graphics"]` and `altsym.DEFAULT_BODIES` is `"graphics"` (decision of the maintainer, 2026-10-06).
- `GRAPHIC_KINDS` MUST be the kinds of `model.library.SymbolGraphic`, which all have a record: `line` (record 13), `rect` (record 14), `polygon` (record 7, closed) and `circle` (record 8, an ellipse of two equal radii). The fill is kept as a flag (`ISSOLID=T` when filled), never as a colour; every graphic holds `LINEWIDTH=1`, `COLOR=128` and, when it can be filled, `AREACOLOR=11599871`, in the key order of `docs/formats/altium/schematic-records.md` ("Graphics the writer draws").
- Graphic coordinates MUST keep the model's value: a coordinate that is no whole unit of 10 mil is written with its `_FRAC` key (1/100 000 unit, 2.54 nm), rounded half up to that step, the integer and the fraction with the same sign, and a `_FRAC` of zero left out. Only pins need the 10-mil grid.
- The graphics MUST be drawn only when the symbol has one unit and one body style, holds at least one graphic, every graphic is of a kind of `GRAPHIC_KINDS`, and `unmodelled` is empty. `SymbolGraphic` names neither a unit nor a body style, so the graphics of a symbol of several cannot be given to a part. `unmodelled` names the graphic kinds of the library symbol that the model does not hold; `lens.altium.unmodelled_graphics(symbol)` gives them for a symbol read from a KiCad library (`arc`, `bezier`, `text`, `text_box`).
- Any other symbol, and every symbol with `bodies="generic"`, MUST get the synthesised rectangle of "Library symbols from KiCad symbols" per part. One `altium.symbol-simplified` (info) per symbol MUST say why, and name dropped pins and alternates; a symbol drawn from its graphics with every pin kept gives none. With `bodies="generic"` the mapping, its info and the written bytes MUST be those of change c0034.
- A drawn symbol MUST hold no rectangle record that its graphics do not hold. `AltiumSymbol.rectangles` then holds, per part, the box of its graphics and of the body ends of its pins, rounded outwards to 10 mil, which the layout and the designator and comment positions use.
- Pins MUST stay as written before this change, so the pin ends touch the graphics as they do in the symbol.
- On the sheet, each graphic MUST be the library record moved by the component's location, a child of the component record (`OWNERINDEX`) with its `OWNERPARTID`, written after the component record and before its pins.
- That Altium draws these records as the source symbol draws them is `H-A-SCHX-GRAPHICS`; that they read back is `H-A-SCHX-READBACK`.

#### Scenario: Resistor symbol
- **GIVEN** the catalog resistor symbol `Fenolite:Resistor`, whose body is eight lines
- **WHEN** it is mapped, written to a schematic library and read back with `read.schlib.read_schlib`
- **THEN** the component holds eight line records with the symbol's coordinates and two pins, no rectangle, and no `altium.symbol-simplified` is reported

#### Scenario: Symbol with a graphic the writer lacks
- **GIVEN** a symbol with one graphic of the kind `bezier`, and a symbol whose `unmodelled` is `("arc",)`
- **WHEN** each is mapped and written
- **THEN** its part holds the synthesised rectangle and no other graphic, and one `altium.symbol-simplified` names the symbol and says that the kind has no record

#### Scenario: Symbol of two units
- **GIVEN** a symbol with graphics and two units
- **WHEN** it is mapped
- **THEN** it has one rectangle per part and no graphic, and `altium.symbol-simplified` says that the model does not name the unit of a graphic

#### Scenario: Generic bodies on request
- **WHEN** the catalog resistor is mapped with `bodies="generic"`
- **THEN** it holds one rectangle and no graphic, and the info reads `Fenolite:Resistor: its graphics became one rectangle per part`

### Requirement: Sheets of a module tree
With `sheets="modules"`, the writer SHALL write one schematic document per module of the design at any depth: the top sheet holds one sheet symbol per top-level module, and a module's sheet holds its own components and one sheet symbol per module directly below it.
- `hierarchy.sheet_tree(design)` MUST give every module that holds a component, directly or below it, depth first with siblings in natural order, the order of `kicad-schematic` ("Hierarchical sheets of a design"). The module of a component is its component path without the last segment (`hierarchy.module_of`).
- A module's file MUST be `<name>_<module path with "." for "/">.SchDoc` beside the project (`hierarchy.sheet_file`), so a top-level module keeps the name of change c0037; the sheet symbol's name (record 32) MUST be the last segment of the module path, and its file name (record 33) the module's file. The project file MUST list the top sheet and then the module sheets in tree order.
- A net that is not a member of a `power` interface **crosses** a module when it has a pin on the module's sheet or on a sheet below it, and a pin on any other sheet. Each crossing MUST give a port on the module's sheet and a sheet entry of the same name on its sheet symbol, so a net that crosses two levels is passed through the sheet between: that sheet holds a port and, on the symbol of the module below, a sheet entry.
- A `harness` interface MUST cross only a top-level module, in the binary form, as in "Sheets of a hierarchical project"; below the first level its member nets cross as nets.
- The unique ids of sheet symbols and ports MUST be `unique_id("sheet:<module path>")` and `unique_id("port:<module path>:<name>")`, stable across builds.
- That Altium compiles such a project and shows the tree is `H-A-SCHX-TREE`.

#### Scenario: Two levels
- **GIVEN** the authored design `tree` (`tests/data/altium/tree/design.py`) with the modules `power`, `io` and `io/leds`
- **WHEN** it is built with `sheets="modules"`, in each form, and read back
- **THEN** four schematic documents exist (`tree.SchDoc`, `tree_io.SchDoc`, `tree_io.leds.SchDoc`, `tree_power.SchDoc`), the sheet of `io` holds a sheet symbol named `leds` whose file name is `tree_io.leds.SchDoc`, and the netlist of the read project equals the design's

#### Scenario: Passed through the sheet between
- **WHEN** the crossings of `tree` are read
- **THEN** `io` crosses `ALARM`, `D[0..3]`, `SENSE` and `SENSE_IN`, `io/leds` crosses `D[0..3]` and `LED_K`, and `power` crosses nothing; the sheet of `io` holds the port `D[0..3]` and, on the symbol of `leds`, the sheet entry `D[0..3]`

### Requirement: Port and sheet-entry directions
Each port and sheet entry of a net crossing SHALL carry the I/O type that `hierarchy.direction(design, net, module)` gives, by the closed table `hierarchy.DIRECTIONS`: `output`, `input`, `bidirectional` or `unspecified`.
- `hierarchy.pin_class(types)` MUST class a set of pin types as `bidirectional` when one is bidirectional, else `driver` when one is `output`, `tri_state`, `open_collector`, `open_emitter` or `power_out`, else `input` when one is `input` or `power_in`, else `passive`.
- `DIRECTIONS` MUST map (the class of the net's pins on the module's sheet and below it, the class of its pins on every other sheet) to a direction, for the sixteen pairs of the four classes: `bidirectional` when either side is bidirectional or both are drivers; `output` for a driver inside and no driver outside; `input` for an input inside without a driver inside; `unspecified` for passive pins inside.
- The port and the sheet entry of one crossing MUST carry the same type. `IOTYPE` MUST be 1 for output, 2 for input, 3 for bidirectional, and MUST be left out for unspecified (`schdoc.IO_TYPES`), written right after `OWNERPARTID`. A harness crossing and a bus crossing MUST stay unspecified.
- With `directions=False` (`--altium-directions off`), every type MUST be unspecified.
- That the compiler accepts these types is `H-A-SCHX-DIR`.

#### Scenario: A driven net
- **GIVEN** the module `io` of `tree`, whose net `SENSE` has an output pin inside and an input pin on the top sheet
- **WHEN** it is built
- **THEN** the port `SENSE` of the module's sheet and its sheet entry hold `IOTYPE=1`; `ALARM`, driven from the top sheet into an input, holds `IOTYPE=2` on both

#### Scenario: Passive net
- **GIVEN** the net `LED_K` of `tree`, which holds only passive pins
- **WHEN** it is built
- **THEN** its port and its sheet entry hold no `IOTYPE`

#### Scenario: Directions off
- **WHEN** `tree` is built with `directions=False`
- **THEN** no port and no sheet entry holds `IOTYPE`

### Requirement: Bus records
A `Bus` of the model whose member nets are one stem followed by consecutive integers SHALL be drawn as a bus block: a bus line (record 26) with the net label `<stem>[<first>..<last>]` on it, and per member one bus entry (record 37) and one labelled wire; where it crosses a module, as one port and one sheet entry of that name, each with a bus block.
- `project.bus_identifier(names)` MUST give `<stem>[<first>..<last>]` for names of one non-empty stem and integers that rise or fall by one, written without leading zeros, and `None` otherwise and for fewer than two names (`docs/formats/altium/connectivity.md`, "Buses and harnesses").
- `project.lowered_buses(design)` MUST give the buses that are drawn and, for every other bus, its name and the reason: its nets have no bus identifier, one of them is a net of a `power` or a `harness` interface, or one is a member of a bus drawn before it. Such a bus MUST be drawn as its nets, with one `altium.bus-flattened` (info) naming it.
- A bus block (`layout.bus_block`) MUST start at the right end of its port, at the connection point of its sheet entry, or in a cell of its own on a sheet that holds a pin of a member and neither a port nor an entry of the bus: the line runs 200 mil right and then 100 mil down per member; the label lies at its start; member `k` has a bus entry from the line to the point 100 mil right and 100 mil lower, where its wire and net label start.
- A drawn bus MUST cross a module when one of its member nets does, as one crossing that replaces the crossings of its members there.
- The nets of the members MUST keep the names of the model. A sheet that passes a bus through draws it twice, at its port and at the sheet entry below; Fenolite's importer reads those as two buses of the same nets.
- No corpus sheet holds a bus, so the key order of records 26 and 37 is the writer's own; that Altium reads these buses is `H-A-SCHX-BUS`.

#### Scenario: Four-bit bus
- **GIVEN** the design `tree` with the bus `D` of the nets `D0` to `D3`, built as one sheet
- **WHEN** it is built in each form and read back
- **THEN** the sheet holds one bus line, one net label `D[0..3]` at its start and four bus entries, and the read netlist holds the nets `D0` to `D3` with their pins

#### Scenario: Bus through two levels
- **WHEN** `tree` is built with `sheets="modules"` and read back
- **THEN** the sheets of `io` and `io/leds` each hold a port `D[0..3]` and no port `D0`, and the read buses hold the nets `D0` to `D3` in order

### Requirement: Text outside ASCII
`ascii.text_problem(text, *, form="ascii", parameter=False)` SHALL accept, for `form="binary"`, every printable character of Windows-1252 (`ascii.CODE_PAGE`), and for `form="ascii"` printable 7-bit ASCII only.
- `|`, a line end or any control character, an empty text and a leading or trailing space MUST stay refused in both forms.
- The reason of a refused character MUST name it and its code point, and say whether the binary form carries it (a Windows-1252 character refused by the ASCII form) or no form does.
- `ascii.record_bytes(fields)` MUST write a field whose value holds a character outside 7-bit ASCII as `|%UTF8%<KEY>=<value in UTF-8>` followed by `|<KEY>=<value in Windows-1252>`, the order of saved files, and a 7-bit field as `ascii.format_record` writes it; `binary.frame_record` MUST frame its bytes. `ascii.format_record` and the ASCII form MUST refuse such a value.
- The texts that may hold such characters are the comment of a component and the value of a parameter, in a build of the binary form. Every other text (design name, refs, net names, pin texts, library, symbol, footprint, module, harness, net class and parameter names) MUST stay printable 7-bit ASCII: they are also file names, storage names, binary pin strings or PCB net names.
- The ASCII form stays 7-bit because the encoding of an ASCII schematic depends on the version that reads it (S-0133).
- That Altium shows such a value unchanged is `H-A-SCHX-TEXT`.

#### Scenario: Accented value in the binary form
- **GIVEN** a part whose value is `Indutância 10 µH`
- **WHEN** the design is built in the binary form and read back
- **THEN** the comment of the component returns that string, and its record holds `%UTF8%TEXT` before `TEXT`

#### Scenario: Refused in the ASCII form
- **WHEN** `text_problem("Indutância 10 µH", form="ascii")` and `text_problem("1 kΩ", form="binary")` are called
- **THEN** the first names `â` (U+00E2) and says that the binary form carries it, and the second names U+03A9 and says that no form carries it

### Requirement: Component parameters
Each property of a part that the writer does not already write as a record of its own SHALL be written as a hidden parameter record of its component, in code-point order of the names.
- `project.parameters_of(component, *, form)` MUST give the parameters: every property with a value, except those whose name starts with `fenolite.` and the names `Comment`, `Designator`, `Footprint`, `Reference` and `Value` in any letter case.
- A parameter MUST be `RECORD=41`, `OWNERINDEX=<its component>`, `OWNERPARTID=-1`, `LOCATION.X`, `LOCATION.Y` (the component's location), `COLOR=8388608`, `FONTID=1`, `ISHIDDEN=T`, `TEXT=<value>`, `NAME=<name>`, `UNIQUEID=<unique_id("<component id>:parameter:<name>")>`, written after the comment and before the footprint chain.
- A property whose name is not 7-bit text, whose value the form cannot carry ("Text outside ASCII", a parameter text), or whose name differs only in letter case from a parameter before it MUST NOT be written: `parameters_of` gives it with the reason, and the build keeps it in the model and reports it (`altium-build`, "Readable schematic in an Altium build"). A property is no part of the circuit, so it never refuses a build.
- A design without such a property MUST keep its bytes.

#### Scenario: Manufacturer part number
- **GIVEN** a part with the property `MPN` = `X-1`
- **WHEN** the design is built in each form and read back
- **THEN** the component holds a hidden parameter `MPN` with the value `X-1`, and the read component holds the property

## MODIFIED Requirements

### Requirement: Text the ASCII form cannot carry
`backends.altium.ascii.text_problem(text, *, form="ascii", parameter=False)` SHALL return the reason why `text` cannot be written, or `None` when it can. With the default `form="ascii"` it is the check of change c0032; "Text outside ASCII" (change c0086) gives the binary form.
- Every character MUST be printable 7-bit ASCII (0x20 to 0x7E) other than `|`: no source documents an escape for `|` or a line end inside a value (S-0131), and other characters depend on the version's code page (S-0130, S-0133).
- The text MUST NOT be empty and MUST NOT start or end with a space, because readers trim values (S-0131).
- A parameter text (`parameter=True`, used for the comment and for parameter values) MUST NOT start with `=`, which Altium reads as a reference to another parameter (S-0130).
- The texts checked are the design name, refs, comments, net names, library names, symbol and footprint names, and pin designators.

#### Scenario: Pipe in a net name
- **WHEN** `text_problem("A|B")` is called
- **THEN** it returns a reason that names the character `|`

#### Scenario: Non-ASCII value
- **WHEN** `text_problem("10µF", parameter=True)` is called
- **THEN** it returns a reason that names the character `µ`

#### Scenario: Comment starting with an equals sign
- **WHEN** `text_problem("=Value", parameter=True)` and `text_problem("=Value")` are called
- **THEN** the first returns a reason and the second returns `None`

#### Scenario: Ordinary texts
- **WHEN** `text_problem` is called on `R1`, `+5V`, `10k`, `LED_DRV`, `FenoliteSample.SchLib` and `My Parts.PcbLib`
- **THEN** each call returns `None`

### Requirement: Library component records
The `Data` stream of a symbol SHALL be a sequence of framed records owned by its first record, the component, in this order: the component, the pins, the symbol's own graphics or else one rectangle per part ("Symbol graphics in libraries and bodies"), the designator, the comment and, when the symbol has a footprint, the footprint chain (S-0131, S-0150).
- Text records MUST be framed as in c0033's "Binary schematic form", and MUST carry no `OWNERINDEX`: every record after the first belongs to it (`H-A-SCHLIB-OPEN`). Coordinates MUST be symbol-relative, in units of 10 mil, with Y upwards. Pins, rectangles, the designator and the comment MUST carry no `_FRAC` key; a graphic of the symbol carries one where its coordinate is no whole unit.
- Component: `RECORD=1`, `LIBREFERENCE`, `COMPONENTDESCRIPTION` (only when not empty), `PARTCOUNT=<parts + 1>`, `DISPLAYMODECOUNT=1`, `OWNERPARTID=-1`, `CURRENTPARTID=1`, `UNIQUEID=<project.unique_id("schlib:<library>:<lib ref>")>`, `DESIGNITEMID=<lib ref>`, `COLOR=128`, `AREACOLOR=11599871`.
- Rectangle of part k, for a symbol that is not drawn from its graphics: `RECORD=14`, `OWNERPARTID=<k>`, `LOCATION.X`, `LOCATION.Y` (bottom-left), `CORNER.X`, `CORNER.Y` (top-right), `LINEWIDTH=1`, `COLOR=128`, `AREACOLOR=11599871`, `ISSOLID=T`.
- Designator: `RECORD=34`, `OWNERPARTID=-1`, `NAME=Designator`, `TEXT=<prefix>?`, the location 100 mil above part 1's top-left corner, `FONTID=1`, `COLOR=8388608`. Comment: `RECORD=41` with the same keys, `NAME=Comment`, `TEXT=<comment>`, 200 mil below part 1's bottom-left corner. For a drawn symbol the corners are those of the box of `AltiumSymbol.rectangles`.
- Footprint chain: `RECORD=44`; `RECORD=45` with the keys and values of c0032's chain ("Designator, comment and links"); `RECORD=46`; `RECORD=48`; none with `OWNERINDEX`. The data file index stays 0-based as in c0032 (`H-A-SCHLIB-IMPLIDX`).
- Pins MUST be binary records ("Binary pin record"), ordered by part, then by designator in natural order.

#### Scenario: Records of RES
- **WHEN** the `RES/Data` stream of the sample's library is de-framed
- **THEN** it holds, in order, a `RECORD=1` with `LIBREFERENCE=RES` and `PARTCOUNT=2`, two binary pins `1` and `2`, one `RECORD=14` with `OWNERPARTID=1`, a `RECORD=34` with `TEXT=R?`, a `RECORD=41` with `NAME=Comment`, and the records 44, 45 (`MODELNAME=R0603`), 46 and 48, and no field `OWNERINDEX`

### Requirement: Library symbols from KiCad symbols
`backends.altium.altsym.from_symbol_def(symbol, *, lib_ref, footprint, issues, unmodelled=(), bodies="graphics")` SHALL map a resolved `SymbolDef` to an `AltiumSymbol` (S-0131 for the importer's reverse mapping, `docs/formats/altium/schematic-library.md`).
- Body style 1 and common pins (body style 0) MUST be kept. Pins of other body styles and pin alternates MUST be dropped with one `altium.symbol-simplified` info per symbol. The symbol's own graphics are in the model (`SymbolGraphic`, changes c0058 and c0060) and are drawn as "Symbol graphics in libraries and bodies" requires; a symbol that is not drawn from them gets a synthesised rectangle per part, as below.
- Parts MUST be the units 1 … `unit_count`. A pin of unit 0 MUST get `OWNERPARTID=0` (Part Zero); others keep their unit.
- A pin's hot end is `SymbolPin.position` and its rotation gives the direction: 0 → 2 (left), 90 → 3 (down), 180 → 0 (right), 270 → 1 (up). The body end MUST be the hot end moved by the length against the direction. Positions and lengths MUST be multiples of 254 000 nm (10 mil); otherwise `ValueError`, which the build reports as `altium.symbol-off-grid` first.
- Electrical type MUST map: input 0, bidirectional 1, output 2, open_collector 3, passive 4, tri_state 5, open_emitter 6, power_in 7. `power_out` gives 7, and `free`, `unspecified` and `no_connect` give 4, each with an `altium.pin-lossy` warning.
- Shape MUST map to edge codes: line none; inverted outer edge 1; clock inner edge 3; inverted_clock outer edge 1 and inner edge 3; input_low outer edge 4; output_low outer edge 17; clock_low inner edge 3 and outer edge 4. `edge_clock_high` and `non_logic` give none with an `altium.pin-lossy` warning.
- The name MUST be shown unless `pin_names_hidden` or the name is empty or `~`, the number unless `pin_numbers_hidden`. A hidden pin MUST set 0x04. A KiCad overbar `~{…}` MUST be written as each character followed by `\`.
- The synthesised rectangle of part k MUST be the bounding box of the body ends of its pins and the Part Zero pins; a side shorter than 200 mil MUST grow to 200 mil around its centre, rounded outwards to 10 mil. A part without pins gets the square from (-100, -100) to (100, 100) mil.
- The designator prefix MUST be the symbol's `Reference` property, or `U` when it is empty. The comment MUST be the `Value` property, or the symbol name. The description MUST be the `Description` property.

#### Scenario: Resistor turned upright
- **GIVEN** a symbol without graphics, with pins `1` at (0, 150) mil rotation 270 and `2` at (0, -150) mil rotation 90, both 50 mil long
- **WHEN** it is mapped
- **THEN** pin `1` has direction 1 and body end (0, 100) mil, pin `2` direction 3 and body end (0, -100) mil, and the rectangle is (-100, -100) to (100, 100) mil

#### Scenario: Dual unit with common power pins
- **GIVEN** a symbol with units 1 and 2 of three pins each and two power_in pins of unit 0
- **WHEN** it is mapped
- **THEN** the symbol has 2 parts, `PARTCOUNT` is 3, the power pins have part 0 and electrical type 7, and each part's rectangle encloses its own pins and the power pins

#### Scenario: Off-grid pin refused
- **GIVEN** a pin at x = 1.27 mm + 1 µm
- **WHEN** it is mapped
- **THEN** `ValueError` is raised, naming the pin

### Requirement: Sheets of a hierarchical project
`backends.altium.hierarchy.plan_sheets(design, *, name, sheets, form, symbols=None, directions=True)` SHALL split a design into one top sheet and one sheet per module of `hierarchy.sheet_tree` when `sheets` is `"modules"` ("Sheets of a module tree"), and SHALL return the single sheet of c0032 when `sheets` is `"flat"`. `project.SheetMode` is `Literal["flat", "modules"]` and `project.DEFAULT_SHEETS` is `"flat"`.
- A component's sheet is the sheet of its module: its component path (`fenolite.path`) without the last segment, and the top sheet for a path without a `/`. So a part outside any module is on the top sheet, and a part of a nested module (`power/ldo/U1`) is on the sheet of that module (`power/ldo`): a module at any depth has a sheet of its own.
- The top sheet's file is `<name>.SchDoc`. A module's file is `<name>_<module path with "." for "/">.SchDoc`, which is `<name>_<module>.SchDoc` for a top-level module. All files sit beside the project.
- The top sheet holds one sheet symbol per top-level module and a module's sheet one per module directly below it, in tree order. No sheet is repeated.
- A net **crosses** a module when it is not a member of a `power` interface, the module's sheet or a sheet below it holds at least one of its pins, and another sheet holds at least one of its pins. A net of a `power` interface never crosses: its power ports are global (S-0185, `H-A-SCH-HIER-NAMES`).
- A harness interface **crosses** a top-level module when `form` is `"binary"` and at least one of its member nets crosses that module. Its member nets that cross the module then travel in the harness and get no port or sheet entry of their own there. Below the first level, and in the ASCII form, no harness crosses, and its member nets cross as plain nets (S-0131: the ASCII place of harness records is not documented).
- The **crossings** of a module are its crossing harnesses, its crossing buses ("Bus records") and its other crossing nets, each named by the harness type name, the bus identifier or the net name, in code-point order of those names. Each crossing gives one port on the module's sheet and one sheet entry on its sheet symbol, with that name (S-0185: a port joins the sheet entry of the same name).
- Every pin keeps the stub, label or power port of "Connectivity on the sheet" on its own sheet, and every component keeps its `UNIQUEID`, so the component records of a `modules` build equal those of the `flat` build except for their positions and `OWNERINDEX` values.
- The result MUST name, for every sheet, its file, its `layout.SheetPlan` and, for a module sheet, the module path and the sheet symbol's unique id. A design without a module MUST give the same top-sheet plan in both modes.
- That Altium Designer opens these sheets, builds the hierarchy from them and picks the hierarchical net scope without a project key are `H-A-SCH-HIER-OPEN` and `H-A-SCH-HIER-COMPILE` for one level, and `H-A-SCHX-TREE` below it.

#### Scenario: Sheets of the hierarchy sample
- **WHEN** `plan_sheets` runs on the model of `examples/altium_hier/design.py` with `name="altium_hier"`, `sheets="modules"` and `form="binary"`
- **THEN** the sheets are `altium_hier.SchDoc` (holding `J1`), `altium_hier_flash.SchDoc` (`C2`, `R1`, `U2`) and `altium_hier_mcu.SchDoc` (`C1`, `U1`); the crossings of `flash` are `FLASH_WP` and the harness `SPI`; the crossings of `mcu` are `FLASH_WP`, `RESET_N` and the harness `SPI`; and `VDD`, `GND` and `FLASH_HOLD_N` cross nothing

#### Scenario: Nested module has its own sheet
- **GIVEN** a variant of the sample whose `C1` is in a module `decoupling` inside `mcu`
- **WHEN** `plan_sheets` runs with `sheets="modules"`
- **THEN** `C1` (path `mcu/decoupling/C1`) is on `altium_hier_mcu.decoupling.SchDoc`, the sheet of `mcu` holds `U1` and a sheet symbol named `decoupling`, and the sheet of `decoupling` holds no port, because `C1` is on power nets only

#### Scenario: Harness members cross as nets in the ASCII form
- **WHEN** `plan_sheets` runs on the sample with `sheets="modules"` and `form="ascii"`
- **THEN** the crossings of `flash` are the nets `FLASH_WP`, `SPI_CS`, `SPI_MISO`, `SPI_MOSI` and `SPI_SCK`, and no plan holds a harness block

#### Scenario: Flat mode is c0032's sheet
- **WHEN** `plan_sheets` runs on the sample with `sheets="flat"`
- **THEN** it returns one sheet, `altium_hier.SchDoc`, whose plan equals `project.plan_sheet(design, name="altium_hier")`

### Requirement: Sheet symbols and sheet entries
A sheet of a `modules` build that has a module directly below it SHALL hold, right after the sheet record and before the first component, one block of records per such module: the sheet symbol, its sheet entries in crossing order, the sheet name and the file name (S-0130, S-0131, S-0187, S-0188).
- Sheet symbol: `RECORD=15`, `OWNERPARTID=-1`, `LOCATION.X`, `LOCATION.Y` (the **top-left** corner), `XSIZE`, `YSIZE`, `COLOR=128`, `AREACOLOR=8454016`, `ISSOLID=T`, `UNIQUEID` ("Stable component unique ids"), `SYMBOLTYPE=Normal`.
- Sheet entry: `RECORD=16`, `OWNERINDEX=<index of its sheet symbol>`, `OWNERPARTID=-1`, then `IOTYPE=<1, 2 or 3>` only for a net crossing with a direction ("Port and sheet-entry directions"), `SIDE=1` (the right side; no `SIDE` key for an entry on the left side, which only "Harness lines between sheet symbols" places), `DISTANCEFROMTOP=<k>`, `COLOR=128`, `AREACOLOR=8454143`, `TEXTCOLOR=128`, `TEXTFONTID=1`, `TEXTSTYLE=Full`, `NAME=<crossing name>`, then `HARNESSTYPE=<type name>` for a harness crossing only, then `ARROWKIND=Block & Triangle`. Its connection point is on the symbol's edge of that side, `k` × 100 mil below the top-left corner.
- Sheet name: `RECORD=32`, `OWNERINDEX`, `OWNERPARTID=-1`, `LOCATION.X`, `LOCATION.Y`, `COLOR=8388608`, `FONTID=1`, `TEXT=<last segment of the module path>`, 100 mil above the top-left corner. File name: `RECORD=33` with the same keys, `TEXT=<the module's file>`, at the top-left corner.
- A sheet entry of a net crossing MUST get a wire stub from its connection point rightwards and a net label with the net name, by the stub and label rules of "Connectivity on the sheet" for a right pin. Labels join it to the other entries, to the ports and to the sheet's parts on that net; no wire runs between two sheet symbols.
- A sheet entry of a harness crossing MUST get a harness block ("Harness records") whose signal harness line starts at its connection point, unless a signal harness line joins it to the sheet entry of another sheet symbol ("Harness lines between sheet symbols"): it then gets no block, no wire and no label. A sheet entry of a bus crossing MUST get a bus block ("Bus records") that starts at its connection point, and takes one slot per member below its own.
- These stubs and labels MUST follow the last component record and precede the first pin stub, per sheet symbol and per entry in order.
- No `INDEXINSHEET` is written, as on every Fenolite record.

#### Scenario: Symbols of the hierarchy sample
- **WHEN** the top sheet of the sample (`sheets="modules"`) is read
- **THEN** it holds 2 records 15, 5 records 16 (3 without and 2 with `HARNESSTYPE=SPI`), 2 records 32 with `TEXT=flash` and `TEXT=mcu`, 2 records 33 with `TEXT=altium_hier_flash.SchDoc` and `TEXT=altium_hier_mcu.SchDoc`, 6 wire records, 4 net labels (none of them an `SPI_*` net) and 2 power ports; the entry `SPI` of `mcu` holds no `SIDE` key; and no entry holds `IOTYPE`, because the sample's generic pins are passive

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
- Port: `RECORD=18`, `OWNERPARTID=-1`, then `IOTYPE=<1, 2 or 3>` only for a net crossing with a direction ("Port and sheet-entry directions"), `WIDTH`, `LOCATION.X`, `LOCATION.Y` (its left end), `COLOR=128`, `FONTID=1`, `AREACOLOR=8454143`, `TEXTCOLOR=128`, `NAME=<crossing name>`, then `HARNESSTYPE=<type name>` for a harness crossing only, then `UNIQUEID` ("Stable component unique ids") and `HEIGHT=10`. No `STYLE` or `ALIGNMENT` is written.
- `WIDTH` MUST be `max(300, 100 · ⌈(70 · L + 150) / 100⌉)` mil for a name of `L` characters, written in units of 10 mil.
- A port's name MUST equal the name of its sheet entry on the sheet above, in the same letter case.
- A port of a net crossing MUST be followed by a wire stub from its right end (location plus width) rightwards and a net label with the net name, as for a right pin. A port of a harness crossing MUST get a harness block whose signal harness line starts at its right end. A port of a bus crossing MUST get a bus block ("Bus records") that starts at its right end.
- A module without a crossing MUST get no port; its sheet symbol then has no entry.

#### Scenario: Ports of the hierarchy sample
- **WHEN** the sheets `altium_hier_mcu.SchDoc` and `altium_hier_flash.SchDoc` of the sample are read
- **THEN** the first holds the ports `FLASH_WP`, `RESET_N` and `SPI` (the last with `HARNESSTYPE=SPI`), 16 wire records, 12 net labels and 4 power ports; the second holds the ports `FLASH_WP` and `SPI`, 17 wire records, 12 net labels and 5 power ports

#### Scenario: Port and entry names match
- **WHEN** every port of the sample's module sheets and every sheet entry of its top sheet are read
- **THEN** each module's set of port names equals the set of entry names of its sheet symbol
