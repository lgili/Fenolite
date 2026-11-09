## ADDED Requirements

### Requirement: Drawn content of read Altium sheets

The Altium extractor SHALL turn the read sheets of an Altium project or document into a drawn schematic, through
`fenolite.backends.altium.drawn_read.extract(sheets, *, components=None) -> tuple[DrawnSchematic, tuple[Issue, ...]]`,
where `sheets` are the read documents that `adapter.netlist.resolve` takes and `components` maps a designator
to its component path.
It SHALL map:

- each component part to a symbol pose, with its part, mirror and display mode;
- wires and buses to polylines;
- junctions, net labels, ports, power ports, sheet symbols with their entries, bus entries and no-ERC
  markers to their drawn items;
- every other record (harness connector, harness entry, signal harness, parameter set, directive, note,
  text frame, graphic, image) to a typed opaque item that keeps its record fields.

The sheet's size, orientation, border and title-block fields SHALL become the drawn sheet's `paper` and
`title_block`. Every item MUST have its pin points, so that `drawn_connect.resolve` gives its nets.

A point is converted at 127/50 nm per Altium fraction unit, with Y down from the top of the sheet's drawing
area. A length that is not a whole number of nanometres MUST be rounded to the nearest and counted, per
sheet, by `altium.import.inexact`; an opaque item keeps its exact record text. A record the extractor cannot represent MUST give
an `error` issue naming the record. The extractor reads no file.

#### Scenario: Authored flat sheet

- **GIVEN** the authored fixture `tests/data/altium/blink/blink.SchDoc`
- **WHEN** `uv run pytest tests/unit/backends/altium/test_drawn_read.py -k blink` extracts it
- **THEN** every component of the sheet gives one symbol pose at its record position, and every wire,
  junction, net label and power port gives one item
- **AND** the nets resolved from the drawing equal the nets of `altium-import` for the same sheet

#### Scenario: Hierarchy and harnesses

- **GIVEN** the authored project `tests/data/altium/hier/altium_hier.PrjPcb`
- **WHEN** it is extracted
- **THEN** each sheet symbol gives one sheet reference with its entries as pins
- **AND** each harness record is a typed opaque item, with its record fields unchanged

#### Scenario: Public documents read without error

- **WHEN** `uv run pytest tests/corpus/test_altium_drawn_read.py -rA` extracts the public rows
  `altium-third-party-schdoc-01` to `-17`
- **THEN** no row gives an `error` issue, and the count of items per kind of each row equals the counts in
  `docs/evidence/conversion.md`

### Requirement: Altium drawing written back

A drawing extracted from Altium sheets and written again by `backends/altium/drawn.py` SHALL read back
to an equal drawing: level S of `design-equivalence` finds no difference, the typed opaque items included.

#### Scenario: Write and extract again

- **GIVEN** the drawing extracted from each authored Altium fixture
- **WHEN** it is written as Altium sheets, read, and extracted again
- **THEN** the second drawing equals the first at level S
