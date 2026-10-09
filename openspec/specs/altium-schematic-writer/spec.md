# altium-schematic-writer Specification

## Purpose
Write Altium schematic files from a model `Design` as pure functions that return bytes: the records and keys of a sheet, the component bodies, designators and library links, the connectivity drawn on the sheet, the deterministic layout, the stable unique ids and the project file. Every fact comes from public sources recorded in `docs/formats/altium/`; the writer opens no file and starts no process.

## Requirements

### Requirement: Altium writer package
`fenolite.backends.altium` SHALL provide `project.write_project(design, *, name, project=True, issues=None, form=DEFAULT_FORM, symbols=None) -> dict[str, bytes]`, which returns `<name>.SchDoc`, one `<library>.SchLib` per library that the components' lib ids name ("Schematic library file") and, when `project` is true, `<name>.PrjPcb`, for a model `Design` whose components hold their pins, and writes no file. `symbols` maps each lib id of the design to its `altsym.AltiumSymbol`; a lib id missing from it, or `symbols=None`, gets its generic symbol ("Generic library symbols").
- The package MUST import only `fenolite.core` and `fenolite.model`, and MUST NOT open a file, start a process or read the environment. It MUST NOT resolve a library: `lens.altium` passes the resolved symbols in.
- It MUST NOT be registered in `fenolite.backends.registry`.
- `src/fenolite/backends/altium/PROVENANCE.md` MUST hold the provenance table of `docs/provenance.md`, one row per fact area, each citing `docs/evidence/sources.md` ids.
- Every format fact the package relies on MUST be a row of a page under `docs/formats/altium/` (`schematic-ascii.md`, `project.md`, `compound-file.md`, `schematic-binary.md` or `schematic-library.md`), with its source, its label and an `H-A-SCH-*`, `H-A-SCHBIN-*`, `H-A-SCHLIB-*` or `H-A-PRJ-*` hypothesis.
- `write_project` MUST raise `ValueError` for a net member whose pin the component does not hold, and for a text that `ascii.text_problem` refuses; the build checks both first (`altium-build`, "Altium build issue codes").

#### Scenario: Files of the sample
- **GIVEN** the model of `examples/altium_sample/design.py` with generic pins
- **WHEN** `write_project(model, name="altium_sample")` and `write_project(model, name="altium_sample", project=False)` are called
- **THEN** the first returns the keys `altium_sample.PrjPcb`, `altium_sample.SchDoc` and `FenoliteSample.SchLib`, and the second only `altium_sample.SchDoc` and `FenoliteSample.SchLib`

#### Scenario: Not a registered backend
- **WHEN** `registry.all_backends()` is called after `fenolite.backends.altium.project` is imported
- **THEN** no backend is named `altium`

#### Scenario: Layering and provenance
- **WHEN** `uv run pytest tests/unit/test_import_graph.py tests/unit/test_provenance.py` runs
- **THEN** it passes, with `backends.altium` checked against the `backends.<x>` row and its `PROVENANCE.md` table found

### Requirement: ASCII schematic form
`backends.altium.ascii.encode_records(records)` SHALL write the ASCII form of a schematic (S-0002, S-0130, S-0131, S-0133):
- The first line MUST be the header record `|HEADER=Protel for Windows - Schematic Capture Ascii File Version 5.0|WEIGHT=<n>`, where `<n>` is the number of records after it.
- Every other record MUST be one line of fields `|KEY=VALUE`, starting with `|` and without a trailing `|`, with its keys in the order this capability lists them. A boolean MUST be written `T` and only when true.
- Every line, the last one included, MUST end with CR LF (S-0142, S-0143; `H-A-SCH-LINEEND`).
- The bytes MUST be printable 7-bit ASCII apart from the line ends.
- Records after the header are numbered from 0 in file order. Record 0 MUST be the sheet record `RECORD=31`. Every `OWNERINDEX` MUST name an earlier record, so every owner precedes its children.
- A line MUST NOT end with `|>`, and the file MUST hold no second header and no embedded file.
- Lengths are integers in units of 10 mil, and X grows rightwards and Y upwards from the sheet's bottom-left corner (S-0130, S-0131). The writer works on a 10-mil grid (library pins may sit on a 50-mil grid; component origins stay on the 100-mil grid of "Deterministic sheet layout"), so it MUST write no `_FRAC` key.

#### Scenario: Header and first record of the sample
- **WHEN** the sample's `altium_sample.SchDoc` is split into lines
- **THEN** it has 123 lines, the first is `|HEADER=Protel for Windows - Schematic Capture Ascii File Version 5.0|WEIGHT=122`, and the second starts with `|RECORD=31|`

#### Scenario: Line ends and bytes
- **WHEN** the bytes of the sample's schematic are read
- **THEN** every line ends with CR LF, every other byte lies between 0x20 and 0x7E, and no line ends with `|>`

#### Scenario: Units
- **WHEN** `coord_fields("LOCATION", 1000, 500)` is called with a point 1000 mil right of and 500 mil above the sheet origin
- **THEN** it returns the fields `LOCATION.X=100` and `LOCATION.Y=50`, `coord_fields("LOCATION", 1050, 500)` returns `LOCATION.X=105`, and a length that is not a multiple of 10 mil raises `ValueError`

### Requirement: Text the ASCII form cannot carry
`backends.altium.ascii.text_problem(text, *, parameter=False)` SHALL return the reason why `text` cannot be written, or `None` when it can.
- Every character MUST be printable 7-bit ASCII (0x20 to 0x7E) other than `|`: no source documents an escape for `|` or a line end inside a value (S-0131), and other characters depend on the version's code page (S-0130, S-0133).
- The text MUST NOT be empty and MUST NOT start or end with a space, because readers trim values (S-0131).
- A parameter text (`parameter=True`, used for the comment) MUST NOT start with `=`, which Altium reads as a reference to another parameter (S-0130).
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

### Requirement: Sheet record
The sheet record SHALL be `RECORD=31` with, in this order, `FONTIDCOUNT=1`, `SIZE1=10`, `FONTNAME1=Times New Roman`, `SYSTEMFONT=1`, `BORDERON=T`, `SNAPGRIDON=T`, `SNAPGRIDSIZE=10`, `VISIBLEGRIDON=T`, `VISIBLEGRIDSIZE=10`, `HOTSPOTGRIDON=T`, `HOTSPOTGRIDSIZE=4`, `DISPLAY_UNIT=4`, `AREACOLOR=16317695`, and then either `SHEETSTYLE=<s>` or `USECUSTOMSHEET=T`, `CUSTOMX=<w>`, `CUSTOMY=<h>` (S-0002, S-0130, S-0131).
- `SHEETSTYLE` values 0 to 4 MUST be the ISO sizes A4, A3, A2, A1 and A0, landscape, whose drawing areas are 1150 × 760, 1550 × 1110, 2230 × 1570, 3150 × 2230 and 4460 × 3150 units (S-0002, S-0130, S-0131).
- The record MUST hold no title-block key, so the sheet has no title block; the font name is a Fenolite choice; every text record MUST use `FONTID=1`.

#### Scenario: Sheet record of the sample
- **WHEN** the second line of the sample's schematic is read
- **THEN** it is `|RECORD=31|FONTIDCOUNT=1|SIZE1=10|FONTNAME1=Times New Roman|SYSTEMFONT=1|BORDERON=T|SNAPGRIDON=T|SNAPGRIDSIZE=10|VISIBLEGRIDON=T|VISIBLEGRIDSIZE=10|HOTSPOTGRIDON=T|HOTSPOTGRIDSIZE=4|DISPLAY_UNIT=4|AREACOLOR=16317695|SHEETSTYLE=0`

#### Scenario: Custom sheet
- **GIVEN** a layout that does not fit A0
- **WHEN** its sheet record is written
- **THEN** it ends with `|USECUSTOMSHEET=T|CUSTOMX=<w>|CUSTOMY=<h>` with the custom size in units, and holds no `SHEETSTYLE`

### Requirement: Generic component bodies
Each component whose lib id is an Altium link (`altium-build`, "Altium symbol sources") SHALL be written as a component record with one rectangle and one pin per pin of `Component.pins`; `lens.altium.generic_pins` gives every component of one lib id one pin per designator that the nets or the no-connect marks (`Circuit.no_connects`) name on any component of that lib id, so that components sharing a lib id share one body, which is also their library component ("Generic library symbols") (`altium-build`, "Altium build outputs").
- Pins MUST be in natural order: designators split into runs of digits and other characters, digit runs compared as integers and before letters, so `1`, `2`, `10`, `A1`, `B` is the order. The first ⌈n/2⌉ pins go on the left edge from top to bottom, the rest on the right edge from top to bottom.
- Geometry (mils, Fenolite choices): pins 200 long and 100 apart, the first 100 below the top edge; body width `max(600, 100 · ⌈(100 + 2 · 70 · L) / 100⌉)` for the longest shown pin name of `L` characters; body height `100 · (rows + 1)`, at least 200.
- Component record: `RECORD=1`, `LIBREFERENCE`, `DESIGNITEMID`, `SOURCELIBRARYNAME`, `PARTCOUNT=2`, `DISPLAYMODECOUNT=1`, `CURRENTPARTID=1`, `OWNERPARTID=-1`, `LOCATION.X`, `LOCATION.Y` (the body's top-left corner), `UNIQUEID`, `COLOR=128`, `AREACOLOR=11599871`; no orientation and no mirror (S-0130, S-0131, S-0137).
- Rectangle record: `RECORD=14`, `OWNERINDEX`, `OWNERPARTID=1`, `LOCATION.X`, `LOCATION.Y` (bottom-left), `CORNER.X`, `CORNER.Y` (top-right), `LINEWIDTH=1`, `COLOR=128`, `AREACOLOR=11599871`, `ISSOLID=T` (S-0130, S-0131).
- Pin record: `RECORD=2`, `OWNERINDEX`, `OWNERPARTID=1`, `FORMALTYPE=1`, `ELECTRICAL=4` (passive), `PINCONGLOMERATE`, `PINLENGTH=20`, `LOCATION.X`, `LOCATION.Y`, `NAME`, `DESIGNATOR` (S-0130, S-0131).
  - `LOCATION` MUST be the pin's body end on the body edge. `PINCONGLOMERATE` MUST be the direction (2 leftwards for left pins, 0 rightwards for right pins) plus 0x20, plus 0x10 (number shown), plus 0x08 (name shown) only when the name differs from the designator ("Binary pin record" for the meaning of the bits).
  - The electrical hot end is `LOCATION` plus `PINLENGTH` in the pin's direction, away from the body (S-0130, S-0131, S-0140).
- Children carry absolute sheet coordinates (S-0131).

#### Scenario: Natural order
- **WHEN** `generic_symbol([("10", "10"), ("B", "B"), ("2", "2"), ("A1", "A1"), ("1", "1")])` is called
- **THEN** its pins are in the order `1`, `2`, `10`, `A1`, `B`, with `1`, `2` and `10` on the left and `A1` and `B` on the right

#### Scenario: Four-pin part of the sample
- **WHEN** the records of the sample's `U2` are read
- **THEN** its rectangle is 600 × 300 mil, pins `1` and `2` are on its left edge with `PINCONGLOMERATE=50`, pins `3` and `4` are on its right edge with `PINCONGLOMERATE=48`, every pin has `PINLENGTH=20`, `ELECTRICAL=4` and `OWNERINDEX` equal to the record number of `U2`

#### Scenario: A part without connected pins
- **GIVEN** a component that no net names, and whose lib id no other component uses
- **WHEN** it is written
- **THEN** it has a component record, a 600 × 200 mil rectangle, a designator and a comment, and no pin record

#### Scenario: Components sharing a lib id share a body
- **GIVEN** a variant where `R1` uses pins `1` and `2` and `R2`, with the same lib id, uses only pin `1`
- **WHEN** it is written
- **THEN** both components have pins `1` and `2` and the same rectangle, and only pin `1` of `R2` has a stub

#### Scenario: A marked pin joins the generic body
- **GIVEN** a variant of the sample where `no_connect(u2[5])` marks a designator of `U2` that no net names
- **WHEN** it is written
- **THEN** the body of `U2` holds the pins `1`, `2`, `3`, `4` and `5`, pin `5` has no stub, and the generic library symbol of its lib id holds the same five pins

### Requirement: Designator, comment and links
Each component SHALL carry its designator, its comment, its library link and, when it has one, its footprint link.
- Designator record: `RECORD=34`, `OWNERINDEX`, `OWNERPARTID=-1`, `NAME=Designator`, `TEXT=<ref>`, `LOCATION.X`, `LOCATION.Y` (100 mil above the body's top-left corner), `FONTID=1`, `COLOR=8388608` (S-0130, S-0131).
- Comment record: `RECORD=41` with the same keys, `NAME=Comment` and `TEXT=<value>`, 200 mil below the body's bottom-left corner. An empty value MUST give the symbol name as the comment (S-0130, S-0137).
- Library link: `lib_id` `<library>:<name>` MUST give `LIBREFERENCE=<name>`, `DESIGNITEMID=<name>` and `SOURCELIBRARYNAME=<project.schlib_name(lib_id, design=<design name>)>`: the library itself for an Altium link, and `<design name>.SchLib` for a KiCad lib id, the library file that the build writes (S-0002, S-0130, S-0137; "Library and storage names"). That "Tools » Update From Libraries" follows these keys is `H-A-SCH-UPDATE`.
- Footprint link: the component's footprint link `<library>:<name>` (its `footprint`, or the symbol's `Footprint` property, `altium-build` "Altium symbol sources") MUST give, after the component's other children, `RECORD=44` (`OWNERINDEX` = the component), then `RECORD=45` (`OWNERINDEX` = the record 44, `MODELNAME=<name>`, `MODELTYPE=PCBLIB`, `DATAFILECOUNT=1`, `MODELDATAFILEENTITY0=<name>`, `MODELDATAFILEKIND0=PCBLIB`, `MODELDATAFILE0=<project.pcblib_name(link, design=<design name>)>`, `ISCURRENT=T`), then `RECORD=46` and `RECORD=48`, each with `OWNERINDEX` = the record 45 (S-0130, S-0131, S-0135, S-0144, S-0150). That Altium reads `MODELDATAFILE0` as the "Library name" mode is `H-A-SCH-LINK`.
- `MODELDATAFILE0` MUST follow the link's form, not the build's outcome: the library itself for an Altium link (`.PcbLib` in any letter case), and `<design name>.PcbLib` for a KiCad footprint link, whether or not that footprint is written (`altium-pcb-writer`, "PCB library name"). The schematic bytes therefore never depend on the content of a footprint library.
- A component without footprint MUST have no record 44, 45, 46 or 48.

#### Scenario: Links of the sample's J1
- **WHEN** the records of the sample's `J1` are read
- **THEN** its component record holds `LIBREFERENCE=HDR2`, `DESIGNITEMID=HDR2` and `SOURCELIBRARYNAME=FenoliteSample.SchLib`, and its record 45 holds `MODELNAME=HDR1X2`, `MODELTYPE=PCBLIB`, `DATAFILECOUNT=1`, `MODELDATAFILEENTITY0=HDR1X2`, `MODELDATAFILEKIND0=PCBLIB`, `MODELDATAFILE0=FenoliteSample.PcbLib` and `ISCURRENT=T`

#### Scenario: Ownership chain
- **WHEN** the owners of the sample's records 44, 45, 46 and 48 are followed
- **THEN** every record 44 is owned by a component, every record 45 by the record 44 just before it, and every record 46 and 48 by that record 45

#### Scenario: Empty value and no footprint
- **GIVEN** a part `X1` with `lib_id="L.SchLib:SYM"`, no value and no footprint
- **WHEN** it is written
- **THEN** its comment record holds `TEXT=SYM`, and no record 44 is owned by it

#### Scenario: Links of a KiCad lib id
- **GIVEN** a part with `lib_id="Device:R"` in a design named `board`
- **WHEN** it is written
- **THEN** its component record holds `LIBREFERENCE=R`, `DESIGNITEMID=R` and `SOURCELIBRARYNAME=board.SchLib`

#### Scenario: Links of a KiCad footprint
- **GIVEN** the part `R1` of `examples/blink_2layer/design.py`, with `footprint="Mini:Mini_R_0603"`, in the design `blink`
- **WHEN** it is written
- **THEN** its record 45 holds `MODELNAME=Mini_R_0603`, `MODELDATAFILEENTITY0=Mini_R_0603` and `MODELDATAFILE0=blink.PcbLib`

#### Scenario: Unresolved KiCad footprint keeps its link
- **GIVEN** a part with `footprint="Nowhere:X"` in a design named `board`, whose library does not resolve
- **WHEN** it is written
- **THEN** its record 45 holds `MODELNAME=X` and `MODELDATAFILE0=board.PcbLib`

### Requirement: Connectivity on the sheet
Every pin drawn on a placed part, which is each pin of that part and, on part 1 only, each Part Zero pin ("Schematic bodies from the library symbol"), and that a net lists SHALL get one wire stub from its hot end outward in the pin's direction, ended by a power port when its net is a member of a `power` interface, and carrying a net label otherwise (S-0130, S-0131, S-0140).
- Wire record: `RECORD=27`, `OWNERPARTID=-1`, `LINEWIDTH=1`, `COLOR=8388608`, `LOCATIONCOUNT=2`, `X1`, `Y1` (the pin's hot end), `X2`, `Y2` (the stub's outer end). Stubs of left and right pins are horizontal, stubs of up and down pins vertical: 200 mil long for a port, `max(300, 100 · ⌈(70 · L + 150) / 100⌉)` mil for a label of `L` characters.
- Net label record: `RECORD=25`, `OWNERPARTID=-1`, `LOCATION.X`, `LOCATION.Y`, `TEXT=<net name>`, `FONTID=1`, `COLOR=8388608`. Its location, the label's lower-left hotspot, MUST lie on its stub: at the outer end for a left pin, 100 mil from the hot end for a right pin (S-0140). On a vertical stub the record MUST add `ORIENTATION=1` after `LOCATION.Y`, and its location MUST be the outer end for a down pin and 100 mil from the hot end for an up pin, so the text runs upwards along the stub (S-0130, S-0131).
- Power port record: `RECORD=17`, `OWNERPARTID=-1`, `LOCATION.X`, `LOCATION.Y` (the stub's outer end), `STYLE`, `ORIENTATION` (2 for a left pin, 0 for a right pin, 1 for an up pin, 3 for a down pin, pointing away from the body), `SHOWNETNAME=T`, `TEXT=<net name>`, `FONTID=1`, `COLOR=8388608`. `STYLE` MUST be 4 (power ground) for a net that is only ever the `lv` member of power interfaces, and 2 (bar) otherwise (S-0131, S-0140).
- A net MUST NOT get both labels and ports. No junction record is written: no two stubs touch.
- A drawn pin that no net lists MUST get no stub, no label and no port. When `Circuit.no_connects` lists it, it gets a No ERC directive instead ("No-connect directives on the sheet").
- Sheet-level records follow every component block: for each component in path order, each of its parts in order and each pin drawn on that part, by part and then in natural order, the stub, then its label or port. The No ERC directives follow the last of these records ("No-connect directives on the sheet"), so a design without marks is written byte for byte as before.

#### Scenario: Ports and labels of the sample
- **WHEN** the sample's schematic is written
- **THEN** it has 19 wire records, 13 power ports (6 with `STYLE=4` and `TEXT=GND`, 3 with `STYLE=2` and `TEXT=VIN`, 4 with `STYLE=2` and `TEXT=+5V`), 6 net labels (two each for `EN`, `LED_DRV` and `LED_A`), and no `RECORD=29`

#### Scenario: A net that is high in one supply and low in another
- **GIVEN** a variant with `Power(VMID, GND)` and `Power(VCC, VMID)`
- **WHEN** it is written
- **THEN** the ports of `VMID` have `STYLE=2` and the ports of `GND` have `STYLE=4`

#### Scenario: Label on its stub
- **WHEN** the label of the sample's `U2` pin 3 and the stub of that pin are read
- **THEN** the label's location lies on the stub, 100 mil from the pin's hot end, and not on any other wire or pin end

#### Scenario: Vertical stubs of the example
- **WHEN** the schematic of `examples/altium_kicad/design.py` is written
- **THEN** every up or down pin has a vertical stub, each of its labels carries `ORIENTATION=1` and lies on that stub, and the nets read back equal the model's nets

#### Scenario: Unlisted pin has no stub
- **WHEN** the schematic of `examples/altium_kicad/no_connect.py` is written
- **THEN** no wire record starts at the hot end of `U1` pin `2`, `3`, `4` or `8`, and the schematic has 8 wire records, 6 power ports and 2 net labels

### Requirement: Deterministic sheet layout
`backends.altium.layout.layout_sheet(parts)` SHALL place components in component-path order, in rows of cells, on the first sheet that holds them.
- A component of n parts takes n consecutive cells, one per part in part order. A cell holds the part's body, its pins, stubs, labels, ports and texts, plus 200 mil on each side; a port takes 100 mil plus 70 mil per character of its net name beyond its stub (Fenolite estimates for the 10-point font).
- Cells MUST be packed left to right and top to bottom inside the drawing area less 500 mil on each side; a row is as high as its tallest cell. Every cell corner and component origin MUST be a multiple of 100 mil, and every written point a multiple of 10 mil.
- The sheet MUST be the first of A4, A3, A2, A1 and A0 whose drawing area holds the packing. Otherwise the sheet MUST be custom, with the A0 width (or the widest cell plus the margins, when larger) and the needed height rounded up to 1000 mil, and `write_project` MUST append the warning `altium.sheet-custom`.
- `SheetPlan.size.name` MUST be the sheet name (`A4` … `A0`, or `custom`); `lens.altium` reports it as `result.sheet`.

#### Scenario: Sample on A4
- **WHEN** the sample is laid out
- **THEN** the sheet is `A4`, no two cells overlap, every written point lies inside the drawing area less 500 mil, and the components appear left to right and top to bottom in the order `J1`, `R2`, `U2`, `led/D1`, `led/R1`, `power/C1`, `power/C2`, `power/U1`

#### Scenario: Larger sheet when needed
- **GIVEN** a variant with 120 two-pin parts on two nets
- **WHEN** it is laid out
- **THEN** the sheet is the first ISO size whose drawing area holds the packing, and the packing does not fit the size before it

#### Scenario: Custom sheet
- **GIVEN** a variant whose packing exceeds the A0 drawing area
- **WHEN** `write_project` runs with an `issues` list
- **THEN** the sheet record uses `USECUSTOMSHEET=T`, and `issues` holds one `altium.sheet-custom` warning

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

### Requirement: Project file
`backends.altium.prjpcb.write_prjpcb(*, schematic, pcb=None, libraries=())` SHALL return the bytes of the lines `[Design]`, `Version=1.0`, an empty line, `[Document1]` and `DocumentPath=<schematic>`; then, when `pcb` is given, an empty line, `[Document2]` and `DocumentPath=<pcb>`; then for each library, i from the next free number, an empty line, `[Document<i>]` and `DocumentPath=<library>`, each line ending with CR LF, in 7-bit ASCII and without a byte-order mark (S-0132, S-0134, S-0143).
- `<schematic>`, `<pcb>` and each `<library>` are bare file names, because the files sit beside the project (S-0132). Libraries, schematic (`.SchLib`) and PCB (`.PcbLib`) alike, MUST be in the MS-CFB order of their names (`cfb.name_key`), and a name holding `/` or `\` MUST raise `ValueError`.
- That Altium takes a listed `.SchLib` as a project library, which "Tools » Update From Libraries" searches, is `H-A-SCHLIB-PRJ`. That it shows a listed `.PcbLib` and `.PcbDoc` as project documents, and that the change order finds footprints in the listed `.PcbLib`, are `H-A-PCB-PRJ` and `H-A-PCB-ECO`.
- That Altium opens this file, takes defaults for every other key, and needs no byte-order mark is `H-A-PRJ-OPEN`.
- With `pcb` given, the section of the schematic also holds the three class keys of "Class generation keys of the project file" (change c0048), after its `DocumentPath`.

#### Scenario: Project of the sample
- **WHEN** `write_prjpcb(schematic="altium_sample.SchDoc")` is called
- **THEN** it returns `b"[Design]\r\nVersion=1.0\r\n\r\n[Document1]\r\nDocumentPath=altium_sample.SchDoc\r\n"`

#### Scenario: Project with a library
- **WHEN** `write_prjpcb(schematic="altium_sample.SchDoc", libraries=("FenoliteSample.SchLib",))` is called
- **THEN** it returns `b"[Design]\r\nVersion=1.0\r\n\r\n[Document1]\r\nDocumentPath=altium_sample.SchDoc\r\n\r\n[Document2]\r\nDocumentPath=FenoliteSample.SchLib\r\n"`

#### Scenario: Project with a PCB document and two libraries
- **WHEN** `write_prjpcb(schematic="blink.SchDoc", pcb="blink.PcbDoc", libraries=("blink.SchLib", "blink.PcbLib"))` is called
- **THEN** it returns `b"[Design]\r\nVersion=1.0\r\n\r\n[Document1]\r\nDocumentPath=blink.SchDoc\r\nClassGenCCAutoEnabled=1\r\nClassGenCCAutoRoomEnabled=0\r\nClassGenNCAutoScope=None\r\n\r\n[Document2]\r\nDocumentPath=blink.PcbDoc\r\n\r\n[Document3]\r\nDocumentPath=blink.PcbLib\r\n\r\n[Document4]\r\nDocumentPath=blink.SchLib\r\n"`

### Requirement: Written records read back
`tests/_altium_read.py` SHALL read the records that Fenolite writes, as test code that the product never imports, and rebuild the nets from geometry: a pin's hot end, the stub that starts there, the label whose location lies on that stub, the port at its outer end, and labels or ports of one name joined into one net. `tests/unit/backends/altium/test_readback.py` SHALL compare the result with the model.
- The read nets MUST equal the model's nets: for each net name, the set of (designator of the owning component, pin designator).
- The reader MUST check that `WEIGHT` equals the number of records, that every `OWNERINDEX` names an earlier record, and that no line ends with `|>`.

#### Scenario: Sample reads back
- **WHEN** `uv run pytest tests/unit/backends/altium/test_readback.py` reads the sample's schematic
- **THEN** the six nets read back hold exactly the model's (ref, pin) pairs, for example `LED_A` holds (`R1`, `2`) and (`D1`, `2`)

#### Scenario: A label off its stub is caught
- **GIVEN** the sample's schematic with the location of one `LED_A` label moved by 10 mil off its stub
- **WHEN** the reader rebuilds the nets
- **THEN** the comparison fails and names the net `LED_A`

### Requirement: Compound file container
`backends.altium.cfb.write_compound(streams)` SHALL return the bytes of an MS-CFB version 3 compound file whose root storage holds exactly the given streams, in Fenolite's fixed layout (S-0145, `docs/formats/altium/compound-file.md`). `streams` is a sequence of `(name, data)` pairs. The function writes no file. c0034's "Compound file storages" extends it to storages.
- Integers MUST be little-endian. The 512-byte header MUST hold the signature `D0 CF 11 E0 A1 B1 1A E1`, a zero header CLSID, minor version `0x003E`, major version `0x0003`, byte order `0xFFFE`, sector shift 9, mini sector shift 6, zero reserved bytes, 0 directory sectors, the FAT sector count, the first directory sector, transaction signature 0, mini stream cutoff 4096, the first mini FAT sector (ENDOFCHAIN when there is none), the mini FAT sector count, first DIFAT sector ENDOFCHAIN, 0 DIFAT sectors, and the FAT sector numbers in the header DIFAT, FREESECT after them.
- The sectors after the header MUST be, in this order: the FAT sectors, the directory sectors, the mini FAT sectors, the sectors of the mini stream, then each stream of 4096 bytes or more in the given order. Every chain MUST run through consecutive sectors and end with ENDOFCHAIN. FAT sectors MUST be marked FATSECT, and FAT entries past the last used sector FREESECT. The FAT sector count MUST cover the FAT's own sectors.
- A stream under 4096 bytes MUST be stored in the mini stream as consecutive 64-byte mini sectors, chained in the mini FAT. A stream of 4096 bytes or more MUST be stored in regular sectors. The unused tail of every last sector or mini sector MUST be zero.
- Directory: entry 0 MUST be `Root Entry` (type 5), whose starting sector and size name the mini stream (size = 64 × mini sectors in use; ENDOFCHAIN and 0 when no stream is small). Entries 1 … n MUST be the streams in the given order (type 2, child NOSTREAM). Unused entries MUST fill the last directory sector, all zero except the three links, which are NOSTREAM.
- Every entry MUST be black and carry a zero CLSID, zero state bits and zero timestamps. The root's child MUST be the top of a binary search tree of the streams under the MS-CFB order (shorter name first, then the upper-cased UTF-16 code units), built by taking the element at index `len // 2` of each sorted run as its top.
- A name MUST hold 1 to 31 characters without `/`, `\`, `:` or `!`, and names MUST be unique under that order; otherwise `ValueError`. An empty stream (0 bytes) MUST be written with a directory entry of size 0 and starting sector ENDOFCHAIN, and MUST take no sector and no mini sector; the PCB library and document need empty `Data` streams (S-0145, `compound-file.md`; that Altium accepts it is `H-A-PCB-DOC-OPEN`).
- When the FAT needs more than `cfb.MAX_FAT_SECTORS` sectors (109, the number the header can list), `write_compound` MUST raise `cfb.CompoundTooLarge` (a `ValueError`), because the writer writes no DIFAT sector.
- The bytes MUST depend only on `streams`.

#### Scenario: The two streams of a schematic
- **WHEN** `write_compound([("FileHeader", b"x" * 5000), ("Storage", b"y" * 25)])` is read with `tests/_cfb_read.py`
- **THEN** the reader reports no violation, `FileHeader` lies in 10 regular sectors, `Storage` in one mini sector, the root entry's size is 64, the root's child is `FileHeader` with `Storage` as its left sibling, and both streams read back byte for byte

#### Scenario: Cutoff boundary
- **WHEN** streams of 1, 64, 65, 4095, 4096 and 4097 bytes are written, one container each
- **THEN** each reads back byte for byte, the streams of 4095 bytes or less lie in the mini stream, and those of 4096 and 4097 bytes in regular sectors

#### Scenario: Several FAT sectors
- **WHEN** a stream of 200 000 bytes is written
- **THEN** the header lists 4 FAT sectors, each marked FATSECT, and the stream reads back byte for byte

#### Scenario: Too large
- **WHEN** a stream of 8 000 000 bytes is written
- **THEN** `CompoundTooLarge` is raised

#### Scenario: Invalid names
- **WHEN** `write_compound` gets a name of 32 characters, a name holding `/`, or the names `Storage` and `STORAGE`
- **THEN** each call raises `ValueError`

#### Scenario: Empty streams
- **WHEN** `write_compound([("Header", b"\x00\x00\x00\x00"), ("Data", b"")])` is read with `tests/_cfb_read.py`
- **THEN** the reader reports no violation, `Data` has size 0 and starting sector ENDOFCHAIN, the mini stream holds one mini sector, and both streams read back byte for byte

#### Scenario: Schematic bytes unchanged
- **WHEN** the sample's binary schematic is built after this change
- **THEN** it equals `tests/data/altium/sample/binary/altium_sample.SchDoc` byte for byte

### Requirement: Binary schematic form
`backends.altium.binary.write_schdoc_binary(plan)` SHALL return the binary form of the schematic of `plan`: a compound file (`write_compound`) with the streams `FileHeader` and then `Storage`, then `Additional` only when the plan holds harness records ("Harness records"), and no other stream (S-0002, S-0130, S-0131, S-0142, S-0147, S-0187, S-0188). This requirement extends c0032's "ASCII schematic form": the records, their keys, their order and every value are those of `schdoc.schdoc_records(plan)`, and only the header text and the framing differ.
- `FileHeader` MUST be the header record `|HEADER=Protel for Windows - Schematic Capture Binary File Version 5.0|WEIGHT=<n>`, with `<n>` the number of records after it, followed by every record of `schdoc_records(plan)`. A sheet whose stream is under 4096 bytes is written as it is, in the compound file's mini stream: Altium Designer 26.5 reads it, and the hidden sheet parameter that padded such a sheet after the first report of step H7 is removed (`H-A-SCHBIN-MINI`, refuted by the second report of 2026-10-03).
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

#### Scenario: Small sheet is not padded
- **WHEN** `examples/altium_hier_board/design.py` is built with `sheets="modules"` and its three sheets are read with `tests/_altium_read.py`
- **THEN** no sheet holds a record named `FenoliteNote`, and in each sheet `WEIGHT` equals the number of records after the header

#### Scenario: No Additional stream without harnesses
- **WHEN** the sample's binary schematic and the binary top sheet of `examples/altium_hier/design.py` built with `sheets="flat"` are read with `tests/_cfb_read.py`
- **THEN** each holds exactly the streams `FileHeader` and `Storage`

#### Scenario: Additional stream of the hierarchy sample
- **WHEN** the `Additional` stream of the top sheet of `examples/altium_hier/design.py` built with `sheets="modules"` is de-framed
- **THEN** it holds 2 records, the first payload is `|HEADER=Protel for Windows - Schematic Capture Binary File Version 5.0|WEIGHT=1` followed by a NUL, and the other is one `RECORD=218`; the `Additional` stream of `altium_hier_mcu.SchDoc` holds 8 records with `WEIGHT=7`: one `RECORD=215`, 4 of `RECORD=216`, one `RECORD=217` and one `RECORD=218`

### Requirement: Compound files read back
`tests/_cfb_read.py` SHALL read a compound file as test code that the product never imports, written from `docs/formats/altium/compound-file.md` and not from `cfb.py`. `read_compound(data)` returns every stream by its path (storage names and the stream name joined by `/`) and raises `CfbError` naming the first violated rule.
- It MUST check: the signature, header CLSID, versions, byte order, both shifts, the reserved bytes and the cutoff; that the header DIFAT lists exactly the sectors marked FATSECT; that every chain ends with ENDOFCHAIN, has no cycle, shares no sector and has `ceil(size / sector size)` sectors; that every stream under 4096 bytes is in the mini stream and every other in regular sectors; the root entry's name, type and size; the name-length field; zero CLSIDs and timestamps of streams; unused entries zero with NOSTREAM links; that the sibling tree is a binary search tree under the MS-CFB order and holds every stream once; and that the file holds exactly its sectors.
- `tests/unit/backends/altium/test_cfb_reader.py` MUST rebuild the worked example of MS-CFB section 3 from the field values of its tables (not from its hex dump) and read it, and MUST hold one negative control per rule.
- The de-framing helper MUST return the records of a `FileHeader` stream as lists of fields, and MUST reject a record without its final NUL or with a non-zero type byte.

#### Scenario: Spec example
- **WHEN** the reader reads the rebuilt MS-CFB example
- **THEN** it returns one stream, named `Stream 1` inside a storage, of 544 bytes, and the root entry's size is 576

#### Scenario: Broken chain caught
- **GIVEN** the sample's binary schematic with the FAT entry of one `FileHeader` sector set to point at the first FAT sector
- **WHEN** `read_compound` reads it
- **THEN** it raises `CfbError` naming the chain of `FileHeader`

#### Scenario: Round trip of the sample
- **WHEN** the sample's binary schematic is read by `read_compound` and its `FileHeader` is de-framed
- **THEN** the root holds exactly `FileHeader` and `Storage`, and the records after the header equal `schdoc_records(plan_sheet(model))` field for field

### Requirement: Compound file storages
`backends.altium.cfb.write_compound(entries)` SHALL also accept storages: each item of `entries` is a stream `(name, data)` or a `cfb.Storage(name, entries)`, whose `entries` follow the same rule at any depth. This requirement extends c0033's "Compound file container", whose rules hold for every storage as they hold for the root.
- `cfb.Storage` MUST be a frozen dataclass with the fields `name: str` and `entries: tuple[cfb.Entry, ...]`, where `cfb.Entry` is `tuple[str, bytes] | Storage`. Both are public and are the API that c0035 uses for PCB documents and libraries.
- Directory entries MUST be numbered in pre-order: the root's items in the given order, each storage followed at once by its own items. Large streams MUST take their sectors in that order, and small streams their mini sectors in that order.
- A storage entry MUST have type 1, black, a zero CLSID, zero state bits, zero timestamps, starting sector 0 and size 0. Its child MUST be the top of the binary search tree of its own items, built as for the root.
- Names MUST follow the rules of c0033 among siblings: the same name may appear in two different storages. A storage without items MUST raise `ValueError`.
- A call whose items are all streams MUST return the bytes that c0033's writer returns for them.
- `cfb.storage_from_paths(mapping)` MUST turn `{"A/B/Data": b"…", …}` into entries, storages and streams in first-seen order, and MUST raise `ValueError` when one path is both a stream and a storage.

#### Scenario: A library-shaped container
- **WHEN** `write_compound([("FileHeader", h), ("Storage", s), Storage("RES", (("Data", d),)), Storage("CAP", (("Data", e),))])` is read with `tests/_cfb_read.py`
- **THEN** the reader reports no violation and returns the paths `FileHeader`, `Storage`, `RES/Data` and `CAP/Data` with their bytes, and the entries are numbered root, `FileHeader`, `Storage`, `RES`, `RES/Data`, `CAP`, `CAP/Data`

#### Scenario: Streams-only calls keep their bytes
- **WHEN** the sample's binary schematic is built after this change
- **THEN** it equals `tests/data/altium/sample/binary/altium_sample.SchDoc` byte for byte

#### Scenario: Two levels and a large stream
- **WHEN** a storage `A` holds a storage `B` that holds a stream `Data` of 10 000 bytes, beside a root stream `X` of 10 bytes
- **THEN** `A/B/Data` lies in regular sectors, `X` in the mini stream, and both read back byte for byte

#### Scenario: Invalid storages
- **WHEN** `write_compound` gets an empty storage, or a storage holding the names `Data` and `DATA`
- **THEN** each call raises `ValueError`

### Requirement: Schematic library file
`backends.altium.schlib.write_schlib(symbols, *, library)` SHALL return the bytes of the schematic library file `library` holding the given `altsym.AltiumSymbol` values, as a compound file (S-0002, S-0131, S-0148, S-0150, S-0151, S-0152).
- The root MUST hold, in this order: the stream `FileHeader`, the stream `Storage`, the stream `SectionKeys` only when some symbol has a section key ("Library and storage names"), then one storage per symbol, named by its storage name and holding exactly one stream `Data`. Symbols MUST be in the MS-CFB order of their storage names.
- `FileHeader` MUST be one property record, framed as in c0033's "Binary schematic form", with the fields `HEADER=Protel for Windows - Schematic Library Editor Binary File Version 5.0`, `WEIGHT=<w>`, `FONTIDCOUNT=1`, `SIZE1=10`, `FONTNAME1=Times New Roman`, `COMPCOUNT=<n>`, then for each symbol i from 0 `LIBREF<i>=<lib ref>`, `COMPDESCR<i>=<description>` (only when not empty) and `PARTCOUNT<i>=<parts + 1>`. `<w>` is the number of records in all `Data` streams plus 1 (S-0150). Nothing follows the record (`H-A-SCHLIB-OPEN`).
- `Storage` MUST be c0033's `binary.storage_stream()`.
- `SectionKeys` MUST be one property record `KEYCOUNT=<k>`, then for each keyed symbol `LIBREF<i>=<lib ref>` and `SECTIONKEY<i>=<storage name>`, i from 0 in symbol order (S-0150, S-0151).
- No other stream is written: no `PinFrac`, `PinWideText`, `PinTextData` or `PinSymbolLineWidth` (S-0150, S-0152).
- The bytes MUST depend only on `symbols` and `library`.

#### Scenario: Library of the sample
- **WHEN** the sample's `FenoliteSample.SchLib` is read with `tests/_cfb_read.py`
- **THEN** its paths are `FileHeader`, `Storage` and `<name>/Data` for `CAP`, `DRV4`, `HDR2`, `LDO3`, `LED` and `RES`, its header record holds `COMPCOUNT=6`, and no `SectionKeys` stream exists

#### Scenario: Header keys
- **WHEN** the `FileHeader` of the sample's library is de-framed
- **THEN** it holds one record, which starts with `|HEADER=Protel for Windows - Schematic Library Editor Binary File Version 5.0|WEIGHT=`, and whose `LIBREF<i>` values equal the storage names in order

### Requirement: Library component records
The `Data` stream of a symbol SHALL be a sequence of framed records owned by its first record, the component, in this order: the component, the pins, one rectangle per part, the designator, the comment and, when the symbol has a footprint, the footprint chain (S-0131, S-0150).
- Text records MUST be framed as in c0033's "Binary schematic form", and MUST carry no `OWNERINDEX`: every record after the first belongs to it (`H-A-SCHLIB-OPEN`). Coordinates MUST be symbol-relative, in units of 10 mil, with Y upwards, and MUST carry no `_FRAC` key.
- Component: `RECORD=1`, `LIBREFERENCE`, `COMPONENTDESCRIPTION` (only when not empty), `PARTCOUNT=<parts + 1>`, `DISPLAYMODECOUNT=1`, `OWNERPARTID=-1`, `CURRENTPARTID=1`, `UNIQUEID=<project.unique_id("schlib:<library>:<lib ref>")>`, `DESIGNITEMID=<lib ref>`, `COLOR=128`, `AREACOLOR=11599871`.
- Rectangle of part k: `RECORD=14`, `OWNERPARTID=<k>`, `LOCATION.X`, `LOCATION.Y` (bottom-left), `CORNER.X`, `CORNER.Y` (top-right), `LINEWIDTH=1`, `COLOR=128`, `AREACOLOR=11599871`, `ISSOLID=T`.
- Designator: `RECORD=34`, `OWNERPARTID=-1`, `NAME=Designator`, `TEXT=<prefix>?`, the location 100 mil above part 1's top-left corner, `FONTID=1`, `COLOR=8388608`. Comment: `RECORD=41` with the same keys, `NAME=Comment`, `TEXT=<comment>`, 200 mil below part 1's bottom-left corner.
- Footprint chain: `RECORD=44`; `RECORD=45` with the keys and values of c0032's chain ("Designator, comment and links"); `RECORD=46`; `RECORD=48`; none with `OWNERINDEX`. The data file index stays 0-based as in c0032 (`H-A-SCHLIB-IMPLIDX`).
- Pins MUST be binary records ("Binary pin record"), ordered by part, then by designator in natural order.

#### Scenario: Records of RES
- **WHEN** the `RES/Data` stream of the sample's library is de-framed
- **THEN** it holds, in order, a `RECORD=1` with `LIBREFERENCE=RES` and `PARTCOUNT=2`, two binary pins `1` and `2`, one `RECORD=14` with `OWNERPARTID=1`, a `RECORD=34` with `TEXT=R?`, a `RECORD=41` with `NAME=Comment`, and the records 44, 45 (`MODELNAME=R0603`), 46 and 48, and no field `OWNERINDEX`

### Requirement: Binary pin record
`backends.altium.schlib.pin_record(pin)` SHALL return one framed binary record for an `altsym.AltiumPin`: a 32-bit little-endian word `(1 << 24) | <payload length>`, then the payload, without a NUL (S-0131, S-0148, S-0150).
- The payload MUST be, little-endian: record id 2 (4 bytes); byte 0; `OWNERPARTID` (2 bytes, signed); display mode 0 (1 byte); the inner-edge, outer-edge, inside and outside symbol codes (1 byte each); the description as a short string; `FORMALTYPE` 1 (1 byte); the electrical type (1 byte); `PINCONGLOMERATE` (1 byte); the pin length, `LOCATION.X` and `LOCATION.Y` of the body end (2 bytes each, signed, 10-mil units); the colour 0 (4 bytes); then the short strings name, designator, swap group, part-and-sequence and default value.
- A short string MUST be one length byte and that many ASCII bytes. Description, swap group, part-and-sequence and default value MUST be empty.
- `PINCONGLOMERATE` MUST be the direction (0 right, 1 up, 2 left, 3 down, from the body end to the hot end), plus 0x20 on every pin, plus 0x04 when hidden, 0x08 when the name is shown, 0x10 when the number is shown (`altsym.AltiumPin.conglomerate`, the one place of this choice).
- With 0x20 set, 0x08 shows the name and 0x10 the number: every pin Altium saves holds 0x20 (the corpus, S-0614), and Altium Designer 26.5.0 drew the four combinations of the check project `tests/data/altium/pinbits/` as written (S-0613). Without 0x20 Altium Designer 26 reads the two bits as hide flags (S-0612), so a pin without it MUST NOT be written; `H-A-SCHLIB-PINBITS`.
- A name or designator over 255 bytes, a value outside the signed 16-bit range, or a code outside 0 … 255 MUST raise `ValueError`.
- That two public implementations agree on this layout is recorded in the fact page; that Altium shows such pins as written is `H-A-SCHLIB-PIN`. The `FORMALTYPE` byte is 1 here and 0 in S-0150; the page records the difference.

#### Scenario: Worked pin
- **WHEN** `pin_record` is called on pin `1` named `IN`, passive, leftwards, name and number shown, length 20 units, body end (-30, 10) units, part 1
- **THEN** it returns the hex bytes `22000001` `02000000` `00` `0100` `00` `00000000` `00` `01` `04` `3a` `1400` `e2ff` `0a00` `00000000` `02494e` `0131` `00` `00` `00`

#### Scenario: Too long a name
- **WHEN** `pin_record` is called on a pin whose name has 256 characters
- **THEN** it raises `ValueError`

#### Scenario: Name hidden, number shown
- **WHEN** `pin_record` is called on a leftwards pin whose name is hidden and whose number is shown
- **THEN** its `PINCONGLOMERATE` byte is 0x32: 0x20 and 0x10 set, 0x08 clear

#### Scenario: Name shown, number hidden
- **WHEN** `pin_record` is called on a leftwards pin whose name is shown and whose number is hidden
- **THEN** its `PINCONGLOMERATE` byte is 0x2A: 0x20 and 0x08 set, 0x10 clear

### Requirement: Library symbols from KiCad symbols
`backends.altium.altsym.from_symbol_def(symbol, *, lib_ref, footprint, issues)` SHALL map a resolved `SymbolDef` to an `AltiumSymbol` (S-0131 for the importer's reverse mapping, `docs/formats/altium/schematic-library.md`).
- Body style 1 and common pins (body style 0) MUST be kept. Pins of other body styles and pin alternates MUST be dropped with one `altium.symbol-simplified` info per symbol. The symbol's own graphics are not in the model; each part gets a synthesised rectangle.
- Parts MUST be the units 1 … `unit_count`. A pin of unit 0 MUST get `OWNERPARTID=0` (Part Zero); others keep their unit.
- A pin's hot end is `SymbolPin.position` and its rotation gives the direction: 0 → 2 (left), 90 → 3 (down), 180 → 0 (right), 270 → 1 (up). The body end MUST be the hot end moved by the length against the direction. Positions and lengths MUST be multiples of 254 000 nm (10 mil); otherwise `ValueError`, which the build reports as `altium.symbol-off-grid` first.
- Electrical type MUST map: input 0, bidirectional 1, output 2, open_collector 3, passive 4, tri_state 5, open_emitter 6, power_in 7. `power_out` gives 7, and `free`, `unspecified` and `no_connect` give 4, each with an `altium.pin-lossy` warning.
- Shape MUST map to edge codes: line none; inverted outer edge 1; clock inner edge 3; inverted_clock outer edge 1 and inner edge 3; input_low outer edge 4; output_low outer edge 17; clock_low inner edge 3 and outer edge 4. `edge_clock_high` and `non_logic` give none with an `altium.pin-lossy` warning.
- The name MUST be shown unless `pin_names_hidden` or the name is empty or `~`, the number unless `pin_numbers_hidden`. A hidden pin MUST set 0x04. A KiCad overbar `~{…}` MUST be written as each character followed by `\`.
- Part k's rectangle MUST be the bounding box of the body ends of its pins and the Part Zero pins; a side shorter than 200 mil MUST grow to 200 mil around its centre, rounded outwards to 10 mil. A part without pins gets the square from (-100, -100) to (100, 100) mil.
- The designator prefix MUST be the symbol's `Reference` property, or `U` when it is empty. The comment MUST be the `Value` property, or the symbol name. The description MUST be the `Description` property.

#### Scenario: Resistor turned upright
- **GIVEN** a symbol with pins `1` at (0, 150) mil rotation 270 and `2` at (0, -150) mil rotation 90, both 50 mil long
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

### Requirement: Generic library symbols
`backends.altium.altsym.from_generic(body, *, lib_ref, prefix, comment, footprint)` SHALL give c0032's generic body (`symbols.GenericSymbol`) as an `AltiumSymbol` of one part whose origin is the body's top-left corner.
- The rectangle MUST be (0, -height) to (width, 0); a left pin of row r MUST have its body end at (0, -100 · (r + 1)) mil and direction 2, a right pin at (width, -100 · (r + 1)) mil and direction 0; every pin is passive, 200 mil long, part 1, and shows its name only when the name differs from the designator.
- The prefix MUST be the leading letters of the first ref in component-path order among the parts that share the lib id, or `U` when there are none. The footprint MUST be the parts' common footprint, or none when they differ.
- Placed at a component's location, this symbol MUST give exactly the pins and rectangle that c0032 writes for the generic body.

#### Scenario: Generic resistor of the sample
- **WHEN** the generic symbol of `FenoliteSample.SchLib:RES` is built
- **THEN** it has pins `1` (left, body end (0, -100) mil) and `2` (right, body end (600, -100) mil), the rectangle (0, -200) to (600, 0) mil, the prefix `R` and the footprint `FenoliteSample.PcbLib:R0603`

### Requirement: Library and storage names
`backends.altium.project.schlib_name(lib_id, *, design)` and `project.storage_name(lib_ref)` SHALL give the library file of a lib id and the storage name of a symbol.
- `schlib_name` MUST return the lib id's library part when it ends with `.SchLib` in any letter case (an Altium link), and `<design>.SchLib` otherwise (a KiCad lib id), where `<design>` is the design name. All KiCad symbols of a design therefore share one library, as c0035 puts all KiCad footprints in `<design>.PcbLib`.
- `storage_name` MUST return the lib ref when it holds 1 to 31 characters and none of `/ \ : !`. Otherwise it MUST return a section key: `/` replaced by `_`, cut to 31 characters (S-0150, S-0152); a key that still holds `\`, `:` or `!` MUST raise `ValueError`. That Altium finds a symbol by its section key is `H-A-SCHLIB-SECTIONKEY`.
- Within one library, two symbols whose storage names are equal under the MS-CFB order MUST raise `ValueError` in `write_schlib`; the build reports `altium.symbol-name-collision` first.

#### Scenario: Names
- **WHEN** `schlib_name("Device:R", design="board")`, `schlib_name("My.schlib:R", design="board")` and `storage_name("A" * 40)` are called
- **THEN** they return `board.SchLib`, `My.schlib` and 31 `A` characters

### Requirement: Schematic libraries read back
`tests/_altium_read.py` SHALL read a schematic library, as test code that the product never imports, written from `docs/formats/altium/schematic-library.md`: `read_schlib(data)` returns, per storage, the de-framed records, with every binary pin decoded field by field.
- It MUST check: the header text; `COMPCOUNT` and the `LIBREF<i>` keys against the storages; `WEIGHT`; that each storage holds `Data` and nothing else; that the first record is `RECORD=1`; that the stream is consumed exactly; and that every binary record has record id 2 and all five short strings.
- `tests/_cfb_read.py` MUST check that a storage entry has starting sector 0 and size 0.
- `tests/unit/backends/altium/test_schlib.py` MUST hold one negative control per check.

#### Scenario: Round trip of a mapped symbol
- **WHEN** the dual-unit symbol of "Library symbols from KiCad symbols" is written and read back
- **THEN** every pin field equals the mapped `AltiumPin`, and the records follow the order of "Library component records"

#### Scenario: Stray byte caught
- **GIVEN** the sample's library with one byte appended to `RES/Data`, rebuilt with `write_compound`
- **WHEN** `read_schlib` reads it
- **THEN** it fails and names `RES/Data`

### Requirement: Schematic library oracle
`tests/kicad/altium/test_schlib_oracle.py` SHALL convert written libraries with `kicad-cli sym upgrade <X>.SchLib -o <Y>.kicad_sym`, read the result with `backends.kicad.sym.read_symbol_library`, and compare it with the source (S-0131, S-0153).
- For the library of `examples/altium_kicad/`, each symbol MUST have the source `SymbolDef`'s unit count and, per pin of body style 1 or 0: number; name after the overbar mapping; electrical type after the lossy mapping; hot-end position; rotation; length; unit; hidden. The `Reference` and `Footprint` properties MUST be the prefix and the footprint name.
- For the sample's library, each symbol MUST have the generic pins.
- Negative controls, written by the test from the writer's records: another header text, a `Data` that does not start with the component, a stray byte at the end of `Data`, and a pin without its last two strings. Each MUST make `kicad-cli` exit non-zero. A storage without `Data` crashes kicad-cli 10.0.6 and MUST NOT be run.
- The test MUST skip without kicad-cli, and fail when `FENOLITE_REQUIRE` lists `kicad`. It runs in the `kicad-10` and `kicad-9` jobs. When kicad-cli 9 cannot read a library that 10.0.6 reads, the test MUST be marked expected-to-fail on major 9, with the observed message recorded on the fact page (`H-A-SCHLIB-KICAD9`).
- A pass on 10.0.6 gives `ORACLE-VERIFIED(kicad-cli)` to the facts that KiCad's importer reads (`H-A-SCHLIB-KICAD`), and to no Altium-only fact.

#### Scenario: Example library converts
- **WHEN** `FENOLITE_REQUIRE=kicad uv run pytest tests/kicad/altium/test_schlib_oracle.py` runs with kicad-cli 10.0.6
- **THEN** it passes: every symbol of the example converts with the source's pins and units, and every negative control exits non-zero

### Requirement: Schematic bodies from the library symbol
The schematic SHALL draw each component from the `AltiumSymbol` of its lib id, placed with the symbol's origin at the component's `LOCATION`, so that the schematic and the library hold the same pins at the same places (`H-A-SCHLIB-UPDATE`, `H-A-SCHLIB-SCHDOC`).
- A symbol of one part MUST give one component record with `CURRENTPARTID=1`, its rectangle and its pins as text records `RECORD=2`, with the keys of "Generic component bodies", plus `SYMBOL_INNEREDGE` and `SYMBOL_OUTEREDGE` when not 0, and the electrical type and direction of the symbol.
- A symbol of n > 1 parts MUST give n component records, parts 1 … n, each with `CURRENTPARTID=<k>`, `PARTCOUNT=<n + 1>`, the ref as designator, the comment, the footprint chain and every rectangle and pin of the symbol with its `OWNERPARTID`. Part 1's `UNIQUEID` is `unique_id(<component id>)`; part k > 1 gets `unique_id("<component id>#<k>")` (`H-A-SCHLIB-MULTIPART`).
- Stubs MUST be drawn for the pins of part k on part k, and for Part Zero pins on part 1 only ("Connectivity on the sheet").
- A design whose lib ids are all Altium links MUST give the same schematic bytes as c0033, in both forms.

#### Scenario: Sample schematic unchanged
- **WHEN** the sample is built in both forms after this change
- **THEN** both schematics equal the committed `altium_sample.SchDoc` files byte for byte

#### Scenario: Dual unit placed twice
- **WHEN** the example's `U1` (two units and common power pins) is written
- **THEN** it gives two component records with designator `U1`, `CURRENTPARTID` 1 and 2 and different unique ids, and the power pins get stubs on part 1 only

#### Scenario: Pins at the library positions
- **WHEN** the example's schematic is read back with `tests/_altium_read.py`
- **THEN** each pin's location minus its component's location equals the pin's body end in the example's library, and the nets read back equal the model's nets

### Requirement: No-connect directives on the sheet
Each pin drawn on a placed part that `Circuit.no_connects` lists SHALL get one No ERC directive at its electrical hot end, written by `backends.altium.schdoc` from `SheetPlan.no_connects`, in the ASCII and in the binary form (S-0130, S-0131, S-0180; `H-A-SCH-NC-RECORD`, `H-A-SCH-NC-ERC`).
- `backends.altium.layout` MUST define the frozen `NoConnectMark(key, designator, at)`, where `key` is the component path and `at` the pin's hot end in the layout frame, `PartSpec.no_connects: frozenset[str]` (pin designators, empty by default) and `SheetPlan.no_connects: tuple[NoConnectMark, ...]` (empty by default). `layout.part_marks(spec, x, y, part=1)` MUST return the marks of the marked pins drawn on that part, in the pin order of `layout.part_stubs`.
- Directive record: `RECORD=22`, `OWNERPARTID=-1`, `LOCATION.X`, `LOCATION.Y` (the pin's hot end), `COLOR=255`, `ISACTIVE=T`, `SUPPRESSALL=T`, `SYMBOL=Thin Cross`, in this key order. No `ORIENTATION`, no `UNIQUEID` and no `INDEXINSHEET` is written (Fenolite choices; S-0130 lists them as optional).
- A marked pin MUST get no wire, no label and no port, and its cell is the cell of an unconnected pin ("Deterministic sheet layout" is unchanged).
- The directives MUST be the last records of the schematic: for each component in path order, each of its parts in order and each marked pin drawn on that part, in the pin order of the stubs ("Connectivity on the sheet"). A multi-part component's Part Zero pin is marked on part 1 only.
- `schdoc.schdoc_records(plan)` MUST return these records, so "Binary schematic form" frames them unchanged: both forms hold the same directive payloads.
- `project.part_specs` MUST fill `PartSpec.no_connects` from `Circuit.no_connects`, and MUST raise `ValueError` for a mark whose component is unknown, whose pin the component does not hold, or whose pin a net also lists; the build checks all three first (`altium-build`, "No-connect marks in an Altium build").
- `docs/formats/altium/schematic-ascii.md` MUST hold a section "No ERC directive" with one row per fact of the record (number, keys, defaults a reader assumes, the two modes of the directive), each with its source, the label `INFERRED` and an `H-A-SCH-NC-*` hypothesis, and "Fenolite's choices" MUST name the written keys and their order. `schematic-binary.md` MUST say that the record is framed as any other property list.
- A design without marks MUST be written byte for byte as before this change.

#### Scenario: Directive record of the example
- **GIVEN** the model of `examples/altium_kicad/no_connect.py`, which marks `U1` pins `2`, `4` and `8`
- **WHEN** its ASCII schematic is written
- **THEN** its last three lines are `RECORD=22` records with the fields `OWNERPARTID=-1`, `LOCATION.X`, `LOCATION.Y`, `COLOR=255`, `ISACTIVE=T`, `SUPPRESSALL=T` and `SYMBOL=Thin Cross` in this order, their locations are the hot ends of `U1` pins `2`, `4` and `8` in this order, and `WEIGHT` counts them

#### Scenario: Same directives in the binary form
- **WHEN** the `FileHeader` stream of the example's binary schematic is de-framed
- **THEN** its last three payloads, without their NUL, equal the last three lines of the ASCII form without their line ends

#### Scenario: Bytes without marks are unchanged
- **WHEN** `uv run pytest tests/unit/lens/test_altium_golden.py tests/unit/lens/test_altium_binary_golden.py tests/unit/lens/test_altium_schlib_golden.py` runs after this change, with no golden file rewritten
- **THEN** it passes

#### Scenario: Mark on a connected pin is refused by the writer
- **GIVEN** a model whose `Circuit.no_connects` lists a pin that a net lists
- **WHEN** `project.part_specs(model)` is called
- **THEN** it raises `ValueError` naming the ref and the pin

#### Scenario: Fact rows are labelled
- **WHEN** `uv run pytest tests/unit/test_format_facts.py` runs
- **THEN** it passes, and every row of the section "No ERC directive" has a source id, a valid label and an `H-A-SCH-NC-*` hypothesis

### Requirement: No-connect directives read back
`tests/_altium_read.py` SHALL read the No ERC directives that Fenolite writes and rebuild the marked pins from geometry: `read_no_connects(records)` returns the set of (designator of the owning component, pin designator) whose hot end equals the location of a `RECORD=22` record. `tests/unit/backends/altium/test_readback.py` SHALL compare the result with the model in both forms.
- The read set MUST equal the model's marks: for each `PinRef` of `Circuit.no_connects`, (ref, pin number).
- The reader MUST fail when a directive's location is no pin's hot end, when it lies on a wire, a label hotspot or a port, and when two directives share a location.
- The nets read back ("Written records read back") MUST still equal the model's nets, so no marked pin is in a net.

#### Scenario: Example reads back in both forms
- **WHEN** `uv run pytest tests/unit/backends/altium/test_readback.py -k no_connect` reads the ASCII and the de-framed binary schematic of `examples/altium_kicad/no_connect.py`
- **THEN** both give the marks {(`U1`, `2`), (`U1`, `4`), (`U1`, `8`)} and the three nets of the model, and (`U1`, `3`) is in neither

#### Scenario: A directive off its pin is caught
- **GIVEN** the example's ASCII schematic with the location of one directive moved by 10 mil
- **WHEN** the reader rebuilds the marks
- **THEN** it fails and names the location

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
`backends.altium.prjpcb.write_prjpcb(*, schematic, pcb=None, libraries=(), sheets=(), harnesses=(), net_classes=False)` SHALL list every document in its own section, an empty line, `[Document<i>]` and `DocumentPath=<file>`, numbered from 1 without a gap, in this order: the top sheet `schematic`, each module sheet of `sheets`, the PCB document `pcb` when given, the libraries, and each harness definition file of `harnesses` (S-0132, S-0134, S-0187, S-0188). This requirement extends "Project file", whose rules hold.
- `sheets` MUST be written in the order given (module-name order). The libraries and `harnesses` MUST each be written in the MS-CFB order of their names (`cfb.name_key`). A name holding `/` or `\` MUST raise `ValueError`.
- Every schematic document MUST precede every other document, and the top sheet MUST be `[Document1]`. With the minimal project file, Altium Designer 26.5 took only the first module sheet into the hierarchy when the PCB document and the libraries stood between the top sheet and the module sheets, and took both with the schematic documents listed first (variant l of step H7 of the report of 2026-10-03; `H-A-SCH-HIER-ORDER`).
- With `sheets` and `harnesses` empty, the bytes MUST equal those of "Project file": `[Document1]` is the schematic and `[Document2]` the PCB document when there is one.
- The order holds for a file that is written. An existing `<name>.PrjPcb` is kept as it is (`altium-build`, "Edited Altium outputs are not overwritten").
- With `sheets` not empty or `pcb` given, each schematic section also holds the three class keys of "Class generation keys of the project file" (change c0048); the `DocumentPath` lines and their order do not change.
- No key names the top sheet or the net scope: Altium finds the top sheet from the sheet symbols and takes its default scope (S-0185, S-0187, S-0188; `H-A-SCH-HIER-PRJ`, `H-A-SCH-HIER-COMPILE`).

#### Scenario: Project with a module sheet and a harness file
- **WHEN** `write_prjpcb(schematic="a.SchDoc", sheets=("a_x.SchDoc",), harnesses=("a.Harness",))` is called
- **THEN** it returns `b"[Design]\r\nVersion=1.0\r\n\r\n[Document1]\r\nDocumentPath=a.SchDoc\r\nClassGenCCAutoEnabled=1\r\nClassGenCCAutoRoomEnabled=0\r\nClassGenNCAutoScope=None\r\n\r\n[Document2]\r\nDocumentPath=a_x.SchDoc\r\nClassGenCCAutoEnabled=1\r\nClassGenCCAutoRoomEnabled=0\r\nClassGenNCAutoScope=None\r\n\r\n[Document3]\r\nDocumentPath=a.Harness\r\n"`: each schematic section holds the three class keys of "Class generation keys of the project file"

#### Scenario: Unchanged without sheets
- **WHEN** `write_prjpcb(schematic="blink.SchDoc", pcb="blink.PcbDoc", libraries=("blink.SchLib", "blink.PcbLib"))` is called
- **THEN** it returns the bytes of the scenario "Project with a PCB document and two libraries" of "Project file"

#### Scenario: Project of the hierarchy sample
- **WHEN** `altium_hier.PrjPcb` of the sample's `modules` build is read
- **THEN** its `DocumentPath` lines are, in order, `altium_hier.SchDoc`, `altium_hier_flash.SchDoc`, `altium_hier_mcu.SchDoc`, `FenoliteHier.SchLib`, `altium_hier_mcu.Harness` and `altium_hier_flash.Harness`

#### Scenario: Project of the board example
- **WHEN** `examples/altium_hier_board/design.py` is built with `sheets="modules"` and its project file is read
- **THEN** its `DocumentPath` lines are, in order, `altium_hier_board.SchDoc`, `altium_hier_board_driver.SchDoc`, `altium_hier_board_led.SchDoc`, `altium_hier_board.PcbDoc`, `altium_hier_board.PcbLib` and `altium_hier_board.SchLib`, so every `.SchDoc` precedes every other document

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

### Requirement: Net class directives on the sheet
`backends.altium.schdoc.schdoc_records` SHALL write one Parameter Set directive with a `ClassName` parameter for each `layout.ClassMark` of `SheetPlan.class_marks`, so that the schematic declares the net classes of the design (S-0310, S-0311, S-0187; `H-A-ECO-NETCLASS`).
- `project.net_class_names(design)` MUST return net name → class name for every net whose `netclass_id` names a net class of the design.
- `project.class_marks(plan, classes, sheet)` MUST return one `ClassMark` per net of `classes` that has a stub on the sheet, in code-point order of the net names. The stub is the first stub of that net in write order (`plan.links`, then `plan.stubs`). A net without a stub on the sheet gets no mark there.
- The mark's point MUST lie on the stub, 200 mil from its start when the stub is 300 mil long or longer, and 100 mil from its start otherwise, so it is never an end of the wire and never the hotspot of a net label.
- `project.plan_sheet` and `hierarchy.plan_sheets` MUST fill `class_marks` on every sheet they plan, the single sheet, the top sheet and each module sheet alike. `sheet` is the sheet's file name.
- Per mark, two records MUST be written, after the No ERC directives and in mark order:
  - the directive, with the keys in this order: `RECORD=43`, `OWNERPARTID=-1`, `LOCATION.X`, `LOCATION.Y` (the mark's point), `COLOR=255`, `ORIENTATION=3` for a horizontal stub and no `ORIENTATION` for a vertical stub, `NAME=Parameter Set` and `UNIQUEID` = `unique_id("netclass:<sheet>:<net>")`;
  - its parameter, with the keys in this order: `RECORD=41`, `OWNERINDEX` (the index of the directive), `OWNERPARTID=-1`, `LOCATION.X`, `LOCATION.Y` (the same point), `COLOR=8388608`, `FONTID=1`, `ISHIDDEN=T`, `TEXT` (the class name), `NAME=ClassName` and `UNIQUEID` = `unique_id("netclass:<sheet>:<net>:name")`.
- Both forms, ASCII and binary, MUST hold the same records. A plan without a mark MUST keep the bytes it had before this change.
- A class name that fails `ascii.text_problem(name, parameter=True)` MUST raise `ValueError`.

#### Scenario: Directive of the blink sample
- **WHEN** the single sheet of the blink sample, whose class `PWR` holds `GND` and `VIN`, is written and its records are read
- **THEN** its last four records are a record 43 at a point of a `GND` stub, a record 41 with `NAME=ClassName`, `TEXT=PWR` and `ISHIDDEN=T` owned by it, and the same pair for `VIN`

#### Scenario: One directive per sheet and net
- **WHEN** `examples/altium_hier_board/design.py` is planned with `sheets="modules"`
- **THEN** the sheet `driver` holds two marks, `GND` and `VIN`, the sheet `led` holds one mark, `GND`, and the top sheet holds none

#### Scenario: Sheet without a net class
- **WHEN** the sample of c0032, which holds no net class, is written in either form
- **THEN** the bytes equal the committed golden files of `tests/data/altium/sample/`

#### Scenario: Class name that a parameter cannot hold
- **WHEN** `project.class_marks` is given the class name `=PWR`
- **THEN** it raises `ValueError` naming the class

### Requirement: Class generation keys of the project file
`backends.altium.prjpcb.write_prjpcb(*, schematic, pcb=None, libraries=(), sheets=(), harnesses=(), net_classes=False)` SHALL write the class generation options that a clean change order needs (S-0310, S-0187, S-0188, S-0313; `H-A-ECO-PRJ-KEYS`, `H-A-ECO-ROOMS`). This requirement extends "Project file" and "Project file of a multi-sheet project", whose rules hold.
- With `sheets` not empty or with `pcb` given, the section of every schematic document, the single or top sheet and each module sheet, MUST hold three more lines after `DocumentPath`, in this order: `ClassGenCCAutoEnabled=1`, `ClassGenCCAutoRoomEnabled=0` and `ClassGenNCAutoScope=None`. The sections of the other documents MUST hold `DocumentPath` alone. A flat project needs the keys too: without them the change order of Altium Designer 26.5 proposed a room for the single sheet (report of Part E, 2026-10-04; `H-A-ECO-SHEETCLASS`).
- With `net_classes` true, the file MUST end with an empty line, `[PrjClassGen]` and the seven lines `CompClassManualEnabled=0`, `CompClassManualRoomEnabled=0`, `NetClassAutoBusEnabled=1`, `NetClassAutoCompEnabled=0`, `NetClassAutoNamedHarnessEnabled=0`, `NetClassManualEnabled=1` and `NetClassSeparateForBusSections=0`, in this order.
- With `sheets` empty, `pcb` not given and `net_classes` false, the bytes MUST hold `DocumentPath` lines only, as before this change.
- `project.write_project` MUST pass `net_classes=True` exactly when the design holds a net class.
- That Altium reads these keys from a file that holds no other option, and still takes every module sheet into the hierarchy (`H-A-SCH-HIER-ORDER`), is `H-A-ECO-PRJ-KEYS`.

#### Scenario: Project of a flat design with a net class
- **WHEN** `write_prjpcb(schematic="a.SchDoc", net_classes=True)` is called
- **THEN** it returns `b"[Design]\r\nVersion=1.0\r\n\r\n[Document1]\r\nDocumentPath=a.SchDoc\r\n\r\n[PrjClassGen]\r\nCompClassManualEnabled=0\r\nCompClassManualRoomEnabled=0\r\nNetClassAutoBusEnabled=1\r\nNetClassAutoCompEnabled=0\r\nNetClassAutoNamedHarnessEnabled=0\r\nNetClassManualEnabled=1\r\nNetClassSeparateForBusSections=0\r\n"`

#### Scenario: Project with a module sheet
- **WHEN** `write_prjpcb(schematic="a.SchDoc", sheets=("a_x.SchDoc",), pcb="a.PcbDoc")` is called
- **THEN** it returns `b"[Design]\r\nVersion=1.0\r\n\r\n[Document1]\r\nDocumentPath=a.SchDoc\r\nClassGenCCAutoEnabled=1\r\nClassGenCCAutoRoomEnabled=0\r\nClassGenNCAutoScope=None\r\n\r\n[Document2]\r\nDocumentPath=a_x.SchDoc\r\nClassGenCCAutoEnabled=1\r\nClassGenCCAutoRoomEnabled=0\r\nClassGenNCAutoScope=None\r\n\r\n[Document3]\r\nDocumentPath=a.PcbDoc\r\n"`

#### Scenario: Flat project with a PCB document
- **WHEN** `write_prjpcb(schematic="x.SchDoc", pcb="x.PcbDoc")` is called
- **THEN** it returns `b"[Design]\r\nVersion=1.0\r\n\r\n[Document1]\r\nDocumentPath=x.SchDoc\r\nClassGenCCAutoEnabled=1\r\nClassGenCCAutoRoomEnabled=0\r\nClassGenNCAutoScope=None\r\n\r\n[Document2]\r\nDocumentPath=x.PcbDoc\r\n"`

#### Scenario: Unchanged without classes and sheets
- **WHEN** `write_prjpcb(schematic="altium_sample.SchDoc", libraries=("FenoliteSample.SchLib",))` is called
- **THEN** it returns the bytes of the scenario "Project with a library" of "Project file"

### Requirement: Net class directives read back
The test reader `tests/_altium_read.py` SHALL rebuild the net classes of a written sheet from its records alone, written from `docs/formats/altium/schematic-ascii.md` without importing the product's writers.
- `net_classes_from_sheet(records)` MUST return net name → class name: for each record 43 that owns a record 41 named `ClassName`, the net is the name of the net label or power port on the wire that holds the directive's location.
- A directive whose location lies on no wire, or on a wire end, or on a wire without a name, and a net that two directives put in two classes, MUST raise `ReadError`.

#### Scenario: Classes of the built samples
- **WHEN** every sheet of the built blink sample and of the built board example is read in both forms
- **THEN** the union of `net_classes_from_sheet` over the sheets of each project equals `project.net_class_names` of its design: `GND` and `VIN` in `PWR`

#### Scenario: Directive off its wire
- **WHEN** the location of a directive is moved 10 mil off its stub and the sheet is read
- **THEN** `net_classes_from_sheet` raises `ReadError`

### Requirement: Pin map records of a footprint model
The schematic document writer, in both forms, and the schematic library writer SHALL write the pin map of a component whose `pin_pad_map` renames a pad as `MapDefiner` records (record 47) of its footprint model, directly after the `MapDefinerList` (record 46) of that model (`H-A-SCHX-PINMAP`; `docs/formats/altium/schematic-records.md`, records 46 and 47). In a schematic document each record names record 46 as its owner (`OWNERINDEX`); in a library no record carries an owner key, and the record belongs to the component it follows.
- One record MUST be written for each pin of the component whose pad differs from what a reader assumes without a record, the pad of the pin's own designator: `DESINTF` the pin's designator, `DESIMPCOUNT` `1`, and `DESIMP0` the pad that `pin_pad_map` gives the pin. A pin outside the map, and a pin that the map leaves on the pad of its own designator, gets no record. This is the form that Altium saves (`H-A-SCHX-PINMAP-FORM`: of 295 footprint models of four public project sets, 293 hold no record, one holds a record for each of its 6 pins and one holds 1 record for 8 pins, and no record names the pin's own pad alone); the count says what Altium writes, not that Altium applies a record Fenolite writes.
- The records MUST be in the order of the pins of the symbol, whatever the order of the pairs of the map.
- A component without such a pin MUST get record 46 without a record 47, as before this requirement, so the files of a design without a renaming map have the bytes they had.
- A component without a footprint model has no record 46 and writes no map.
- The schematic library MUST write the map of a library component only when every component of the design that uses its symbol links the footprint that the library's footprint model names (record 45) and has the same pad for every pin; otherwise the library component holds no record 47. A map is a map onto one footprint: a part that links another footprint than its symbol's own gets its map on the sheet alone. The schematic document carries the map of each component in every case.
- A pad name of a map that `text_problem` refuses MUST give `altium.text-unwritable` (error, nothing written), as any written text does.
- `docs/formats/altium/connectivity.md` ("Component link") MUST state the numbering of `DESIMP<i>` and which pins of a footprint model hold a record, with the counts of the public sets, under `H-A-SCHX-PINMAP-FORM`, and what Fenolite writes under `H-A-SCHX-PINMAP`.

#### Scenario: Map written and read back
- **GIVEN** the blink with `pad_map={"1": "2", "2": "1"}` on its `D1`, which links the footprint its symbol names
- **WHEN** `uv run pytest tests/unit/lens/test_altium_pad_map.py -k hold_the_map` builds it for the Altium target in the ASCII and in the binary form and reads the written sheet and library with Fenolite's readers
- **THEN** the footprint model of `D1` on the sheet, and the library component `Mini_LED`, each hold two records 47, of the pins `1` and `2` with the pads `2` and `1`

#### Scenario: Records of one map
- **GIVEN** the blink with its `R1` on a 32-pad footprint, which is not the footprint its symbol names, and `pad_map={"1": "1", "2": "3"}`
- **WHEN** `uv run pytest tests/unit/lens/test_altium_pad_map.py -k renamed_pin` builds it
- **THEN** the sheet holds one record 47, of pin `2` with `DESIMP0` `3`, and none for pin `1`; and the library component `Mini_R`, whose footprint model names the symbol's own footprint, holds none

#### Scenario: Order of the records
- **GIVEN** the blink whose `D1` has `pad_map={"2": "1", "1": "2"}`
- **WHEN** `uv run pytest tests/unit/lens/test_altium_pad_map.py -k follow_the_pins` builds it and reads the sheet and the library
- **THEN** the records of `D1` name the pins `1` and `2` in that order in both files

#### Scenario: Users of one symbol that differ
- **GIVEN** the blink with a second LED `D2` of the same symbol and footprint without a map, and `pad_map={"1": "2", "2": "1"}` on `D1`
- **WHEN** `uv run pytest tests/unit/lens/test_altium_pad_map.py -k users_of_a_symbol_differ` builds it
- **THEN** the library component `Mini_LED` holds no record 47, and the sheet holds the two records of `D1`

#### Scenario: No map, same bytes
- **WHEN** `uv run pytest tests/unit/lens/test_altium_golden.py tests/unit/lens/test_altium_binary_golden.py tests/unit/lens/test_altium_schlib_golden.py tests/unit/lens/test_altium_hier_golden.py tests/unit/lens/test_altium_no_connect_golden.py tests/unit/lens/test_altium_pad_map.py -k "golden or no_record"` runs after this change
- **THEN** every golden file under `tests/data/altium` is compared unchanged, and the blink without a `pad_map` holds no record 47 in either form

#### Scenario: A design without a board
- **GIVEN** the blink without its board and with `pad_map={"1": "2", "2": "1"}` on its `D1`
- **WHEN** `uv run pytest tests/unit/lens/test_altium_pad_map.py -k without_a_board` builds it in both forms
- **THEN** no PCB document is written, and the sheet and the library hold the two records

#### Scenario: Pad name that no record holds
- **GIVEN** the blink whose `D1` has `pad_map={"1": "A|B"}`
- **WHEN** `uv run pytest tests/unit/lens/test_altium_issues.py -k "pad-name or closed_set"` builds it for the Altium target
- **THEN** the build reports `altium.text-unwritable` as an error and writes nothing

#### Scenario: The form the public sets hold
- **WHEN** `FENOLITE_REQUIRE=corpus uv run pytest tests/corpus/test_altium_map_records.py` counts the map records of the footprint models of `altium-set:02` to `altium-set:05`
- **THEN** 295 models hold 7 records: 293 hold none, one holds 6 for its 6 pins and one holds 1 for its 8 pins; no record names the pin's own pad alone, and every record numbers its pads from 0 without a gap
