## MODIFIED Requirements

### Requirement: Symbol graphics in libraries and bodies
`backends.altium.altsym.from_symbol_def(symbol, *, lib_ref, footprint, issues, unmodelled=(), bodies="graphics", parents=())` SHALL, with `bodies="graphics"`, map the graphics of a `SymbolDef` to schematic records of their kind, in the symbol's frame, for the library and for the body on the sheet alike. `altsym.SymbolBodies` is `Literal["generic", "graphics"]` and `altsym.DEFAULT_BODIES` is `"graphics"` (decision of the maintainer, 2026-10-06).
- `GRAPHIC_KINDS` MUST be the kinds of `model.library.SymbolGraphic`, which all have a record: `line` (record 13), `rect` (record 14), `polygon` (record 7, closed) and `circle` (record 8, an ellipse of two equal radii). The fill is kept as a flag (`ISSOLID=T` when filled), never as a colour; every graphic holds `LINEWIDTH=1`, `COLOR=128` and, when it can be filled, `AREACOLOR=11599871`, in the key order of `docs/formats/altium/schematic-records.md` ("Graphics the writer draws").
- Graphic coordinates MUST keep the model's value: a coordinate that is no whole unit of 10 mil is written with its `_FRAC` key (1/100 000 unit, 2.54 nm), rounded half up to that step, the integer and the fraction with the same sign, and a `_FRAC` of zero left out. Only pins need the 10-mil grid.
- The graphics MUST be drawn only when the symbol holds at least one graphic, every graphic is of a kind of `GRAPHIC_KINDS`, and `unmodelled` is empty. A symbol of one unit and one body style draws every graphic on part 1. A symbol of several units or body styles (change c0261) draws each graphic of body style 0 or 1 on the part of its `SymbolGraphic.unit`, unit 0 on Part Zero (`OWNERPARTID=0`), drops the graphics of other body styles with `altium.symbol-simplified`, and is drawn as rectangles when a part has no graphic of its own and no common graphic exists.
- A derived symbol (`extends` set) MUST be flattened onto the symbols of `parents` first (`altsym.flatten`): the body of the root of its chain and the properties of the chain, the nearest first; the Altium library has no derivation, so it is written flat under its own lib ref. A missing parent MUST raise `ValueError`. `unmodelled` names the graphic kinds of the library symbol that the model does not hold; `lens.altium.unmodelled_graphics(symbol)` gives them for a symbol read from a KiCad library (`arc`, `bezier`, `text`, `text_box`).
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
- **GIVEN** a symbol of two units whose graphics are common (unit 0), and the same symbol whose graphics all belong to unit 1
- **WHEN** each is mapped
- **THEN** the first draws its graphics on Part Zero, holds one bounding rectangle per part and reports nothing; the second has one rectangle per part and no graphic, and `altium.symbol-simplified` says that a part draws no graphic of its own unit

#### Scenario: Graphics per unit and a derived symbol
- **GIVEN** a symbol of two units with graphics of unit 1 and unit 2 and one graphic of body style 2, and a derived symbol of a single-unit base
- **WHEN** they are mapped, the derived one with its base in `parents`
- **THEN** each kept graphic is on the part of its unit, the graphic of body style 2 is dropped with `altium.symbol-simplified`, and the derived symbol has the base's pins and its own comment

#### Scenario: Generic bodies on request
- **WHEN** the catalog resistor is mapped with `bodies="generic"`
- **THEN** it holds one rectangle and no graphic, and the info reads `Fenolite:Resistor: its graphics became one rectangle per part`
