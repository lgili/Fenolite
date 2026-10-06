## ADDED Requirements

### Requirement: Symbol graphics in libraries and bodies
`backends.altium.altsym.from_symbol_def` SHALL map the graphics of body style 1 of a `SymbolDef` to schematic records of their kind (line, rectangle, polyline, polygon, arc, ellipse, text), in the symbol's frame, for the library and for the body on the sheet alike.
- `GRAPHIC_KINDS` MUST list the model graphic kinds that have a record. A part with a graphic outside it, or without graphics, MUST get the synthesised rectangle and one `altium.symbol-simplified` (info) per symbol.
- A coordinate that the record needs on the 10 mil grid and that is off it MUST be rounded to the grid, with one `altium.symbol-simplified` per symbol.
- Pins MUST stay as written before this change. The pin ends MUST touch the graphics as they do in the symbol, within the rounding.

#### Scenario: Resistor symbol
- **GIVEN** the catalog resistor symbol, whose body is one rectangle
- **WHEN** it is written to a schematic library and read back
- **THEN** the component holds one rectangle record of the symbol's size and two pins, and no synthesised rectangle

#### Scenario: Symbol with a curve the writer lacks
- **GIVEN** a symbol with one Bézier graphic
- **WHEN** it is written
- **THEN** its part holds the synthesised rectangle, and `altium.symbol-simplified` names the symbol

### Requirement: Sheets of a module tree
With hierarchy selected, the writer SHALL write one schematic document per module of the design at any depth: the root holds one sheet symbol per child module, and a module's sheet holds its components and one sheet symbol per child of its own.
- File names, sheet names and their order in the project file MUST follow the rule of `kicad-schematic` ("Hierarchical sheets of a design"), with the extension `.SchDoc`.
- A net that crosses a sheet boundary MUST have a port on the child sheet and a sheet entry of the same name on its sheet symbol; a net that crosses two levels MUST be passed through the sheet between.
- The unique ids of sheet symbols MUST be stable across builds.

#### Scenario: Two levels
- **GIVEN** the authored design `tree` with the modules `power`, `io` and `io/leds`
- **WHEN** it is built with `--altium-sheets modules` and read back
- **THEN** four schematic documents exist, the sheet of `io` holds a sheet symbol for `leds`, and the netlist of the read project equals the design's

### Requirement: Port and sheet-entry directions
Each port and sheet entry SHALL carry the I/O type that `hierarchy.direction(net, sheet)` gives, from the pin types on the net inside the sheet, by the closed table `DIRECTIONS`: output, input, bidirectional or unspecified.
- The port and the sheet entry of one crossing MUST carry the same type.
- With `--altium-directions off`, every type MUST be unspecified.

#### Scenario: A driven net
- **GIVEN** a module whose net `CLK` has one output pin inside and input pins outside
- **WHEN** it is built
- **THEN** the port `CLK` of the module's sheet and its sheet entry are outputs

#### Scenario: Passive net
- **GIVEN** a net that holds only passive pins
- **WHEN** it is built
- **THEN** its port and sheet entry are unspecified

### Requirement: Bus records
A `Bus` of the model whose members are a common stem followed by consecutive integers SHALL be drawn as a bus line with the label `<stem>[<first>..<last>]`, one bus entry and one net label per member; where it crosses a sheet, as a bus port and a bus sheet entry.
- A bus with other member names MUST be drawn as its nets, with `altium.bus-flattened` (info) naming it.
- The nets of the members MUST keep the names of the model.

#### Scenario: Four-bit bus
- **GIVEN** a design with the bus `D` of the nets `D0` to `D3`
- **WHEN** it is built and read back
- **THEN** the sheet holds one bus labelled `D[0..3]`, and the read netlist holds the nets `D0` to `D3` with their pins

### Requirement: Text outside ASCII
`text_problem(text, *, form, parameter=False)` SHALL accept, for the binary form, every character of the document's code page, written with the UTF-8 companion field that `altium-schematic-reader` ("Text decoding") reads; and for the ASCII form, the characters that `docs/formats/altium/schematic-ascii.md` records as carried.
- `|`, a line end, an empty text and a leading or trailing space MUST stay refused.
- A refused text MUST give `altium.text-unsupported` naming the first character refused and the form that would carry it, if any.

#### Scenario: Accented value in the binary form
- **GIVEN** a part whose value is `Indutância 10 µH`
- **WHEN** the design is built in the binary form and read back
- **THEN** the comment of the component returns that string

### Requirement: Component parameters
Each property of a part that the writer does not already write as a field SHALL be written as a hidden parameter record of its component, in name order, with the text rules of the form.

#### Scenario: Manufacturer part number
- **GIVEN** a part with the property `MPN` = `X-1`
- **WHEN** the design is built and read back
- **THEN** the component holds a hidden parameter `MPN` with the value `X-1`
