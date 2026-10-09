## ADDED Requirements

### Requirement: Full-stack pad records
A pad whose per-layer stack gives every copper layer a circle, an oval, a rectangle or a rounded rectangle with its corner ratio SHALL be written with stack mode 1 when the inner layers share one shape and size, and with stack mode 2 otherwise, by the write rows of `docs/formats/altium/pcb-library.md` that restate the read rows of `import.md`, "Pads and padstacks". A stack with a custom shape on any layer MUST stay a lost `pad` with its reason.

#### Scenario: Per-layer stack read back
- **GIVEN** a footprint with one pad of 1.6 mm round on top and bottom and 1.2 mm round on the inner layers of a 4-layer board
- **WHEN** `uv run pytest tests/unit/backends/altium/test_pcblib_stacks.py` writes it and reads the document back
- **THEN** the pad has stack mode 1, and its shape and size per copper layer equal the model's

### Requirement: Connector and free pads
A pad of kind `connect` SHALL be written as a surface pad whose paste and solder-mask expansions remove both openings. A pad without a number inside a footprint SHALL be written as a pad of that footprint with an empty designator when `pcb-library.md` holds a row with a public source that allows it, and otherwise as a free pad at its board position, counted `changed` under `pad` with that reason.

#### Scenario: Connector pad
- **GIVEN** a footprint with one `connect` pad
- **WHEN** the board is written and read back
- **THEN** the pad is a surface pad on its copper layer with no paste and no mask opening, and the report has no lost `pad`

### Requirement: Mechanical layers of KiCad drawings
`lower.KICAD_MECHANICAL` SHALL map `User.1` to `User.8` to Mechanical 1 to 8, `Dwgs.User` to Mechanical 9, `Cmts.User` to Mechanical 10, and `Eco1.User` and `Eco2.User` to Mechanical 11 and 12; the fabrication and courtyard layers keep Mechanical 13 to 16. A graphic or text on a mapped layer MUST be written there and the document MUST name the layer after its KiCad name. A text on a copper layer MUST be written as a text record on that copper layer. A layer outside the map MUST stay a reported loss.

#### Scenario: Drawing on Dwgs.User
- **GIVEN** a board with one line on `Dwgs.User` and one text on `F.Cu`
- **WHEN** it is written and read back
- **THEN** the line is on Mechanical 9, the text on the top copper layer, and the report loses neither

### Requirement: Derived PCB library
A conversion to Altium SHALL write `<name>.PcbLib` with one footprint per distinct footprint name of the board (the part of `lib_ref` after its last `:`), built from the first instance in reference order in the footprint's frame, and every component of the document MUST link that library. An instance whose pads or graphics differ from its library footprint MUST be counted `changed` under `footprint` with the reason "differs from the library footprint"; the document keeps the instance as it is.

#### Scenario: Two instances, one edited
- **GIVEN** a board with `R1` and `R2` of footprint `R_0603`, and `R2` with one pad moved by 0.1 mm
- **WHEN** it is converted to Altium
- **THEN** the library holds one footprint `R_0603` with the pads of `R1`, both components link it, and the report counts one `changed` footprint
