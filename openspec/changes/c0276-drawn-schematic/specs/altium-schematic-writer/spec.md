## ADDED Requirements

### Requirement: Automatic global scope of drawn Altium sheets
The drawn writer SHALL retain Automatic mode 0. Only when Automatic selects Global, it MUST qualify local names shared by several native sheets and report each change, so repeated sheets keep separate partitions. Unique names, Hierarchical names and Flat names MUST remain unchanged. Readback MUST still refuse a partition difference; qualification MUST NOT imply drawing identity or native acceptance.

#### Scenario: Repeated local labels without ports
- **GIVEN** two repeated sheet instances with a local `FB` label and no top sheet entry or port
- **WHEN** the writer emits and reads back the native files
- **THEN** the qualified local labels remain separate, every name change is reported, and the partition equals code

### Requirement: Drawn sheets in Altium
`fenolite.backends.altium.drawn.lower_drawn` SHALL write one sheet per drawn sheet instance: wires and buses as polylines, junctions, local labels as net labels, hierarchical labels as ports, references as sheet symbols with sheet entries, power symbols and global labels as power ports of their text, bus entries and no-connect directives. A repeated sheet MUST be written once per instance with `drawn.altium-repeat-flattened` (info).

#### Scenario: Drawn example in Altium
- **WHEN** `uv run pytest tests/unit/backends/altium/test_drawn_altium.py` builds `examples/drawn/design.py` with `--target altium` and reads the sheets back with the Altium reader
- **THEN** the read circuit has the nets of code, and the sheet holds one wire record per drawn polyline and one junction per drawn junction

#### Scenario: Kit case
- **WHEN** the maintainer's kit compiles the drawn example (`H-A-DRAWN-WRITE`)
- **THEN** the report lists the nets of code and no connectivity message; until then the evidence stays `INFERRED`

### Requirement: Drawn items Altium cannot carry
A drawn coordinate with no exact form in Altium's units SHALL be a lossy write: refused with `FEN-7001` (exit 7) unless `--allow-lossy`, which rounds it and reports each point as `drawn.coordinate-rounded` (warning). An opaque item without an `altium` text MUST be dropped with `drawn.opaque-dropped` (info). Native-record readback MUST refuse a connectivity difference before any write.

#### Scenario: Off-grid point
- **GIVEN** a drawn wire point at `[0.0001, 0]`
- **WHEN** the example is built with `--target altium`, and again with `--allow-lossy`
- **THEN** the first exits 7 with `FEN-7001` naming the point, and the second writes the sheet with one rounding warning

#### Scenario: Text dropped
- **GIVEN** a drawn sheet with one opaque `text` item
- **WHEN** it is built with `--target altium`
- **THEN** `issues` holds one `drawn.opaque-dropped` info naming the item

### Requirement: Bounded opaque Altium graphics
Opaque Altium text SHALL contain valid root graphics only. Invalid fields, duplicate keys, owner references, headers, components, pins or other electrical/framework-owned records MUST raise `FormatError` before staging. Unreadable written records MUST fail the native readback guard, never bypass the code-owned connectivity check.

#### Scenario: Opaque component refused
- **GIVEN** an opaque item whose Altium text contains a component record
- **WHEN** the drawing is built
- **THEN** the build exits 3 with `FEN-3004` naming the opaque item and plans no output

### Requirement: Native drawing coverage guard
Before returning bytes, the Altium builder SHALL match the intended documents, component units, shown logical pin tables and physical pin maps against the native readback. It MUST compare actual logical-pin partitions with code and repeat the guard after templates. Missing, extra, duplicate or unreadable native content MUST plan no write, including unconnected components and pins.

#### Scenario: An unconnected native part disappears
- **GIVEN** the native producer drops a drawn unit whose pins are all unconnected
- **WHEN** the drawing is built
- **THEN** the build reports `build.schematic-netlist-differs` and stages no file
