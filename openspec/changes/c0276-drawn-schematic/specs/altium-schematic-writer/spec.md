## ADDED Requirements

### Requirement: Drawn sheets in Altium
`fenolite.backends.altium.drawn.lower_drawn` SHALL write one sheet per drawn sheet instance: wires and buses as polylines, junctions, local labels as net labels, hierarchical labels as ports, references as sheet symbols with sheet entries, power symbols and global labels as power ports of their text, bus entries and no-connect directives. A repeated sheet MUST be written once per instance with `drawn.altium-repeat-flattened` (info).

#### Scenario: Drawn example in Altium
- **WHEN** `uv run pytest tests/unit/backends/altium/test_drawn_altium.py` builds `examples/drawn/design.py` with `--target altium` and reads the sheets back with the Altium reader
- **THEN** the read circuit has the nets of code, and the sheet holds one wire record per drawn polyline and one junction per drawn junction

#### Scenario: Kit case
- **WHEN** the maintainer's kit compiles the drawn example (`H-A-DRAWN-WRITE`)
- **THEN** the report lists the nets of code and no connectivity message; until then the evidence stays `INFERRED`

### Requirement: Drawn items Altium cannot carry
A drawn coordinate with no exact form in Altium's units SHALL be a lossy write: refused with `FEN-7001` (exit 7) unless `--allow-lossy`, which rounds it and reports each rounding as a warning. An opaque item without an `altium` text MUST be dropped with `drawn.opaque-dropped` (info).

#### Scenario: Off-grid point
- **GIVEN** a drawn wire point at `[0.0001, 0]`
- **WHEN** the example is built with `--target altium`, and again with `--allow-lossy`
- **THEN** the first exits 7 with `FEN-7001` naming the point, and the second writes the sheet with one rounding warning

#### Scenario: Text dropped
- **GIVEN** a drawn sheet with one opaque `text` item
- **WHEN** it is built with `--target altium`
- **THEN** `issues` holds one `drawn.opaque-dropped` info naming the item
