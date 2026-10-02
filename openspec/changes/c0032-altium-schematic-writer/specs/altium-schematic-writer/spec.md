## ADDED Requirements

### Requirement: Altium writer package
`fenolite.backends.altium` SHALL provide `project.write_project(design, *, name, project=True, issues=None) -> dict[str, bytes]`, which returns `<name>.SchDoc` and, when `project` is true, `<name>.PrjPcb` for a model `Design` whose components hold their pins, and writes no file.
- The package MUST import only `fenolite.core` and `fenolite.model`, and MUST NOT open a file, start a process or read the environment.
- It MUST NOT be registered in `fenolite.backends.registry`.
- `src/fenolite/backends/altium/PROVENANCE.md` MUST hold the provenance table of `docs/provenance.md`, one row per fact area, each citing `docs/evidence/sources.md` ids.
- Every format fact the package relies on MUST be a row of `docs/formats/altium/schematic-ascii.md` or `docs/formats/altium/project.md`, with its source, its label and an `H-A-SCH-*` or `H-A-PRJ-*` hypothesis.
- `write_project` MUST raise `ValueError` for a net member whose pin the component does not hold, and for a text that `ascii.text_problem` refuses; the build checks both first (`altium-build`, "Altium build issue codes").

#### Scenario: Files of the sample
- **GIVEN** the model of `examples/altium_sample/design.py` with generic pins
- **WHEN** `write_project(model, name="altium_sample")` and `write_project(model, name="altium_sample", project=False)` are called
- **THEN** the first returns the keys `altium_sample.PrjPcb` and `altium_sample.SchDoc`, and the second only `altium_sample.SchDoc`

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
- Lengths are integers in units of 10 mil, and X grows rightwards and Y upwards from the sheet's bottom-left corner (S-0130, S-0131). The writer works on a 100-mil grid, so it MUST write no `_FRAC` key.

#### Scenario: Header and first record of the sample
- **WHEN** the sample's `altium_sample.SchDoc` is split into lines
- **THEN** it has 123 lines, the first is `|HEADER=Protel for Windows - Schematic Capture Ascii File Version 5.0|WEIGHT=122`, and the second starts with `|RECORD=31|`

#### Scenario: Line ends and bytes
- **WHEN** the bytes of the sample's schematic are read
- **THEN** every line ends with CR LF, every other byte lies between 0x20 and 0x7E, and no line ends with `|>`

#### Scenario: Units
- **WHEN** `coord_fields("LOCATION", 1000, 500)` is called with a point 1000 mil right of and 500 mil above the sheet origin
- **THEN** it returns the fields `LOCATION.X=100` and `LOCATION.Y=50`, and a length that is not a multiple of 100 mil raises `ValueError`

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
Each component SHALL be written as a component record with one rectangle and one pin per pin of `Component.pins`; `lens.altium.generic_pins` gives a component one pin per designator that its nets name (`altium-build`, "Altium build outputs").
- Pins MUST be in natural order: designators split into runs of digits and other characters, digit runs compared as integers and before letters, so `1`, `2`, `10`, `A1`, `B` is the order. The first ⌈n/2⌉ pins go on the left edge from top to bottom, the rest on the right edge from top to bottom.
- Geometry (mils, Fenolite choices): pins 200 long and 100 apart, the first 100 below the top edge; body width `max(600, 100 · ⌈(100 + 2 · 70 · L) / 100⌉)` for the longest shown pin name of `L` characters; body height `100 · (rows + 1)`, at least 200.
- Component record: `RECORD=1`, `LIBREFERENCE`, `DESIGNITEMID`, `SOURCELIBRARYNAME`, `PARTCOUNT=2`, `DISPLAYMODECOUNT=1`, `CURRENTPARTID=1`, `OWNERPARTID=-1`, `LOCATION.X`, `LOCATION.Y` (the body's top-left corner), `UNIQUEID`, `COLOR=128`, `AREACOLOR=11599871`; no orientation and no mirror (S-0130, S-0131, S-0137).
- Rectangle record: `RECORD=14`, `OWNERINDEX`, `OWNERPARTID=1`, `LOCATION.X`, `LOCATION.Y` (bottom-left), `CORNER.X`, `CORNER.Y` (top-right), `LINEWIDTH=1`, `COLOR=128`, `AREACOLOR=11599871`, `ISSOLID=T` (S-0130, S-0131).
- Pin record: `RECORD=2`, `OWNERINDEX`, `OWNERPARTID=1`, `FORMALTYPE=1`, `ELECTRICAL=4` (passive), `PINCONGLOMERATE`, `PINLENGTH=20`, `LOCATION.X`, `LOCATION.Y`, `NAME`, `DESIGNATOR` (S-0130, S-0131).
  - `LOCATION` MUST be the pin's body end on the body edge. `PINCONGLOMERATE` MUST be the direction (2 leftwards for left pins, 0 rightwards for right pins) plus 0x10 (number shown), plus 0x08 (name shown) only when the name differs from the designator.
  - The electrical hot end is `LOCATION` plus `PINLENGTH` in the pin's direction, away from the body (S-0130, S-0131, S-0140).
- Children carry absolute sheet coordinates (S-0131).

#### Scenario: Natural order
- **WHEN** `generic_symbol([("10", "10"), ("B", "B"), ("2", "2"), ("A1", "A1"), ("1", "1")])` is called
- **THEN** its pins are in the order `1`, `2`, `10`, `A1`, `B`, with `1`, `2` and `10` on the left and `A1` and `B` on the right

#### Scenario: Four-pin part of the sample
- **WHEN** the records of the sample's `U2` are read
- **THEN** its rectangle is 600 × 300 mil, pins `1` and `2` are on its left edge with `PINCONGLOMERATE=18`, pins `3` and `4` are on its right edge with `PINCONGLOMERATE=16`, every pin has `PINLENGTH=20`, `ELECTRICAL=4` and `OWNERINDEX` equal to the record number of `U2`

#### Scenario: A part without connected pins
- **GIVEN** a component that no net names
- **WHEN** it is written
- **THEN** it has a component record, a 600 × 200 mil rectangle, a designator and a comment, and no pin record

### Requirement: Designator, comment and links
Each component SHALL carry its designator, its comment, its library link and, when it has one, its footprint link.
- Designator record: `RECORD=34`, `OWNERINDEX`, `OWNERPARTID=-1`, `NAME=Designator`, `TEXT=<ref>`, `LOCATION.X`, `LOCATION.Y` (100 mil above the body's top-left corner), `FONTID=1`, `COLOR=8388608` (S-0130, S-0131).
- Comment record: `RECORD=41` with the same keys, `NAME=Comment` and `TEXT=<value>`, 200 mil below the body's bottom-left corner. An empty value MUST give the symbol name as the comment (S-0130, S-0137).
- Library link: `lib_id` `<library>:<name>` MUST give `LIBREFERENCE=<name>`, `DESIGNITEMID=<name>` and `SOURCELIBRARYNAME=<library>` (S-0002, S-0130, S-0137). That "Tools » Update From Libraries" follows these keys is `H-A-SCH-UPDATE`.
- Footprint link: `footprint` `<library>:<name>` MUST give, after the component's other children, `RECORD=44` (`OWNERINDEX` = the component), then `RECORD=45` (`OWNERINDEX` = the record 44, `MODELNAME=<name>`, `MODELTYPE=PCBLIB`, `DATAFILECOUNT=1`, `MODELDATAFILEENTITY0=<name>`, `MODELDATAFILEKIND0=PCBLIB`, `MODELDATAFILE0=<library>`, `ISCURRENT=T`), then `RECORD=46` and `RECORD=48`, each with `OWNERINDEX` = the record 45 (S-0130, S-0131, S-0135, S-0142, S-0144). That Altium reads `MODELDATAFILE0` as the "Library name" mode is `H-A-SCH-LINK`.
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

### Requirement: Connectivity on the sheet
Every pin SHALL get one wire stub from its hot end outward, ended by a power port when its net is a member of a `power` interface, and carrying a net label otherwise (S-0130, S-0131, S-0140).
- Wire record: `RECORD=27`, `OWNERPARTID=-1`, `LINEWIDTH=1`, `COLOR=8388608`, `LOCATIONCOUNT=2`, `X1`, `Y1` (the pin's hot end), `X2`, `Y2` (the stub's outer end). Stubs are horizontal: `max(300, 100 · ⌈(70 · L + 150) / 100⌉)` mil for a label of `L` characters; for a port, 200 mil, except for the second, fourth, … port of a run of ports on adjacent pins of one edge: its stub is `200 + 100 · ⌈(100 + 70 · M + 100) / 100⌉` mil, `M` being the longest net name of the ports one row above and one row below it, so ports of adjacent pins alternate between short and long stubs and never overlap.
- Net label record: `RECORD=25`, `OWNERPARTID=-1`, `LOCATION.X`, `LOCATION.Y`, `TEXT=<net name>`, `FONTID=1`, `COLOR=8388608`. Its location, the label's lower-left hotspot, MUST lie on its stub: at the outer end for a left pin, 100 mil from the hot end for a right pin (S-0140).
- Power port record: `RECORD=17`, `OWNERPARTID=-1`, `LOCATION.X`, `LOCATION.Y` (the stub's outer end), `STYLE`, `ORIENTATION` (2 for a left pin, 0 for a right pin, pointing away from the body), `SHOWNETNAME=T`, `TEXT=<net name>`, `FONTID=1`, `COLOR=8388608`. `STYLE` MUST be 4 (power ground) for a net that is only ever the `lv` member of power interfaces, and 2 (bar) otherwise (S-0131, S-0140).
- A net MUST NOT get both labels and ports. No junction record is written: no two stubs touch.
- Sheet-level records follow every component block: for each component in path order and each of its pins in natural order, the stub, then its label or port.

#### Scenario: Ports and labels of the sample
- **WHEN** the sample's schematic is written
- **THEN** it has 19 wire records, 13 power ports (6 with `STYLE=4` and `TEXT=GND`, 3 with `STYLE=2` and `TEXT=VIN`, 4 with `STYLE=2` and `TEXT=+5V`), 6 net labels (two each for `EN`, `LED_DRV` and `LED_A`), and no `RECORD=29`

#### Scenario: A net that is high in one supply and low in another
- **GIVEN** a variant with `Power(VMID, GND)` and `Power(VCC, VMID)`
- **WHEN** it is written
- **THEN** the ports of `VMID` have `STYLE=2` and the ports of `GND` have `STYLE=4`

#### Scenario: Ports on adjacent pins
- **WHEN** the stubs of the sample's `power/U1` pins 1 (`VIN`) and 2 (`GND`), 100 mil apart on the left edge, are read
- **THEN** the stub of pin 1 is 200 mil long, the stub of pin 2 is 700 mil long, and the port of pin 2 lies at least 100 mil past the port of pin 1 and its text

#### Scenario: Label on its stub
- **WHEN** the label of the sample's `U2` pin 3 and the stub of that pin are read
- **THEN** the label's location lies on the stub, 100 mil from the pin's hot end, and not on any other wire or pin end

### Requirement: Deterministic sheet layout
`backends.altium.layout.layout_sheet(parts)` SHALL place components in component-path order, in rows of cells, on the first sheet that holds them.
- A cell holds the body, its pins, stubs, labels, ports and texts, plus 200 mil on each side; a port takes 100 mil plus 70 mil per character of its net name beyond its stub (Fenolite estimates for the 10-point font).
- Cells MUST be packed left to right and top to bottom inside the drawing area less 500 mil on each side; a row is as high as its tallest cell. Every coordinate MUST be a multiple of 100 mil.
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
- Records other than components MUST carry no `UNIQUEID`.

#### Scenario: Form
- **WHEN** `unique_id` is called on 1000 different keys
- **THEN** every result matches `^[A-Y]{8}$`, and the same key always gives the same result

#### Scenario: Pinned value
- **WHEN** `unique_id("cmp_00000000-0000-0000-0000-000000000000")` is called
- **THEN** it returns the value pinned in `tests/unit/backends/altium/test_project.py`, computed once by the rule above

### Requirement: Project file
`backends.altium.prjpcb.write_prjpcb(*, schematic)` SHALL return the bytes of the lines `[Design]`, `Version=1.0`, an empty line, `[Document1]` and `DocumentPath=<schematic>`, each ending with CR LF, in 7-bit ASCII and without a byte-order mark (S-0132, S-0134, S-0142, S-0143).
- `<schematic>` is the bare file name, because the schematic sits beside the project (S-0132, S-0142).
- That Altium opens this file, takes defaults for every other key, and needs no byte-order mark is `H-A-PRJ-OPEN`.

#### Scenario: Project of the sample
- **WHEN** `write_prjpcb(schematic="altium_sample.SchDoc")` is called
- **THEN** it returns `b"[Design]\r\nVersion=1.0\r\n\r\n[Document1]\r\nDocumentPath=altium_sample.SchDoc\r\n"`

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
