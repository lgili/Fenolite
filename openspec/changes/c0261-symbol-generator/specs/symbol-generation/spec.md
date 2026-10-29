## ADDED Requirements

### Requirement: Pin table records
`fenolite.catalog.pins.parse_pins(text, *, file)` SHALL read one TOML record of schema `fenolite.pins.v0` into a `PinTable` of `PinRow` values. Each row MUST hold `number`, `name` and `type`, and MAY hold `group`, `side`, `bus`, `unit`, `shape`, `hidden`, `stacked` and `alternates`. Another key, a missing key or a wrong type MUST raise `FormatError` (`FEN-3004`) naming the file, the row and the key; a newer schema MUST give `FEN-3002`.

#### Scenario: A pin table is read
- **GIVEN** the authored file `tests/data/pins/example_buck.toml` with six rows and one `stacked` number
- **WHEN** `uv run pytest tests/unit/catalog/test_pins.py -k read` parses it
- **THEN** a `PinTable` with six rows is returned, the `GND` row has `stacked == ("7",)`, and no field holds a float

#### Scenario: Refused rows
- **WHEN** tables are parsed that repeat a number across `number` and `stacked`, give `type = "power"`, give `unit` on some rows only, or hold the row key `colour`
- **THEN** each raises `FormatError` with code `FEN-3004`, naming the row and the key

### Requirement: Canonical pin table text
`fenolite.catalog.pins.pins_text(table)` SHALL give the canonical TOML of a pin table: fixed key order, rows in table order, LF line ends and one final newline. `parse_pins(pins_text(t)) == t` MUST hold for every table.

#### Scenario: Round trip
- **WHEN** every table under `tests/data/pins` is written with `pins_text` and parsed again
- **THEN** each equals the one read, and writing it twice gives identical bytes

### Requirement: Pin sides from groups
The generator SHALL place `supply` rows on top, `ground` at the bottom, `input`, `control` and `passive` on the left, and `output`, `io` and `nc` on the right, in that group order per side, with one empty slot between groups. A row without `group` MUST take the default group of its type (design decision 2); an explicit `side` MUST win. Within a group, rows MUST keep table order.

#### Scenario: Regulator sides
- **GIVEN** the example table with `VIN` supply, `GND` ground, `EN` control, `FB` input, `SW` power_out and `BST` with `side = "right"`
- **WHEN** `generate_symbol` runs
- **THEN** `VIN` is on top, `GND` at the bottom, `FB` then a gap then `EN` on the left, and `SW` then `BST` on the right

### Requirement: Buses kept together
Rows with one `bus` value SHALL form one block at the position of the first of them, in natural order of their names. With `auto_bus`, rows of one group and side whose names share a prefix before a trailing number, at least two, MUST form an implicit bus. A bus that skips an index MUST give `symbol.bus-gap` (info).

#### Scenario: Interleaved data pins
- **GIVEN** left-side rows in table order `D10`, `CLK`, `D2`, `D1`, all of group `input`
- **WHEN** the symbol is generated
- **THEN** the left side reads `D1`, `D2`, `D10`, `CLK`, and one `symbol.bus-gap` names `D` and the missing indices

### Requirement: Generated geometry on grid
Every connection point, pin length and body corner of a generated symbol SHALL be a multiple of 2 540 000 nm. Body width and height MUST follow the formulas of design decision 4 with the constants of `docs/formats/library/symbols.md`, each at least four grid steps. Generation MUST be pure: the same table and arguments give equal definitions.

#### Scenario: Grid property
- **WHEN** `uv run pytest tests/unit/catalog/test_symbol_generate.py -k grid` generates symbols from random valid tables
- **THEN** every point, length and corner is a multiple of 2 540 000 nm, and two runs give equal canonical JSON

#### Scenario: A one-pin edit stays local
- **GIVEN** a table and a copy with one `output` row appended
- **WHEN** both are generated
- **THEN** no pin of the left, top or bottom side moves, unless the body height grew, in which case every pin moves by the same offset

### Requirement: Automatic unit split
When no row has `unit` and the visible rows exceed `split_above` (default 100), the generator SHALL make signal units first, by packing group runs and buses in table order into units of at most `unit_pins` (default 48) rows, then power units of the `supply` and `ground` rows. It MUST report `symbol.units-split` (info), and `symbol.bus-split` (warning) for a bus cut across units.

#### Scenario: A 120-pin part
- **GIVEN** an authored table of 120 rows: 12 supply, 12 ground, 64 `io` pins in four buses of 16, and 32 other inputs
- **WHEN** the symbol is generated with the defaults
- **THEN** it has signal units holding whole buses, each of at most 48 rows, then one power unit of 24 rows, and one `symbol.units-split`

#### Scenario: Explicit units win
- **GIVEN** a table of 150 rows that all carry `unit`
- **WHEN** the symbol is generated
- **THEN** the units are those of the table, unit 0 rows appear in every unit, and no `symbol.units-split` is reported

### Requirement: Graphics per unit
`SymbolGraphic` SHALL carry `unit` and `body_style`, both 0 by default (common). A generated symbol MUST draw one body rectangle per unit, owned by that unit. A definition read or authored without units MUST keep unit 0 and its canonical JSON.

#### Scenario: Two bodies
- **WHEN** a two-unit symbol is generated
- **THEN** it holds two rectangles, of unit 1 and unit 2, each enclosing the body ends of its unit's pins

#### Scenario: Old canonical JSON unchanged
- **WHEN** the shipped catalog symbols are serialized after the change
- **THEN** their canonical JSON equals the JSON before the change

### Requirement: Hidden and stacked pins
A `stacked` number SHALL give a further pin at the connection point of its row, hidden, of `symembed.STACKED_TYPE`, without alternates, taking no slot. A `hidden` row MUST keep its own slot. `hidden = true` on a `power_in` row MUST raise `FormatError` (`FEN-3004`).

#### Scenario: Exposed pad stacked on ground
- **WHEN** the example table is generated
- **THEN** pin `7` has the connection point of pin `2`, is hidden and of type `passive`

#### Scenario: Hidden power refused
- **WHEN** a table with `type = "power_in"` and `hidden = true` on one row is parsed
- **THEN** `FormatError` with code `FEN-3004` is raised, naming `hidden`

### Requirement: Derived symbols from variants
Each `[[variant]]` row SHALL give a `SymbolDef` with `extends` set to the base name, the base's library, its own properties only, and no pins, units or graphics. `sym.resolve_extends` MUST give it the base's pins.

#### Scenario: Ordering variant
- **WHEN** the example table with variant `EXB6202DR` is generated
- **THEN** two definitions are returned, and the second has `extends == "EXB6202"`, `value == "EXB6202DR"` and no pins

### Requirement: KiCad symbols with units, alternates and derivation
`backends.kicad.sym.write_symbol_library` SHALL write unit 0 items in `<name>_0_1` and unit u items in `<name>_<u>_1`, `unit_name` for a named unit, `(hide yes)` on a hidden pin, one `alternate` per alternate in order, and a derived symbol as `extends` with its own properties, after its base. A one-unit symbol without these features MUST keep today's bytes.

#### Scenario: Read back
- **WHEN** a generated two-unit symbol with an alternate, a hidden pin and one variant is written and read with `read_symbol_library`
- **THEN** units, unit names, pins, alternates, hidden flags, per-unit graphics and `extends` equal the written definitions

#### Scenario: Existing libraries unchanged
- **WHEN** the authored-symbol examples are built
- **THEN** their `lib/*.kicad_sym` bytes equal those of the base commit

### Requirement: KiCad oracle for generated symbols
`tests/kicad/library/test_symbol_generate_oracle.py` SHALL export every symbol of a generated library with `kicad-cli sym export svg` and convert it with `kicad-cli sym upgrade`. It MUST skip without kicad-cli and fail when `FENOLITE_REQUIRE` lists `kicad`. A pass on 9.0.x and 10.0.x settles `H-K-SYM-UNITS-WRITE`.

#### Scenario: Multi-unit library exports
- **WHEN** the oracle runs on the library of `examples/symbols/`
- **THEN** kicad-cli exits 0, writes one SVG per unit of every symbol, and the upgraded library reads back with the same units, pins and `extends`

### Requirement: Altium symbols from generated definitions
`altsym.from_symbol_def` SHALL give a graphic of unit u `OWNERPARTID=u`, flatten a derived symbol with `resolve_extends` before mapping, and keep dropping alternates with `altium.symbol-simplified`. A generated symbol MUST never raise `altium.symbol-off-grid`.

#### Scenario: Generated MCU to SchLib
- **WHEN** the 120-pin example is generated and written with `write_schlib`
- **THEN** the library reads back with `tests/_altium_read.py` with one part per unit, Part Zero for unit 0 pins, one rectangle per part, and no `_FRAC` key
