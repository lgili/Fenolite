## ADDED Requirements

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

## MODIFIED Requirements

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

### Requirement: Generic component bodies
Each component whose lib id is an Altium link (`altium-build`, "Altium symbol sources") SHALL be written as a component record with one rectangle and one pin per pin of `Component.pins`; `lens.altium.generic_pins` gives every component of one lib id one pin per designator that the nets or the no-connect marks (`Circuit.no_connects`) name on any component of that lib id, so that components sharing a lib id share one body, which is also their library component ("Generic library symbols") (`altium-build`, "Altium build outputs").
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
