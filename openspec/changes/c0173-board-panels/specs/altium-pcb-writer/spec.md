## ADDED Requirements

### Requirement: Embedded board array records
`pcbrecords.embedded_board_array(...)` SHALL write an Embedded Board Array in the form that Part Q measured (`docs/formats/altium/pcb-document.md`, "Embedded board arrays"), naming the referenced document by its path relative to the panel document, never an absolute one. While `pcbdoc.EMBEDDED_ARRAYS` is false no build writes one; it MUST be set only by a Part Q report of Q7, Q8 and Q9 as passed.

#### Scenario: Array record read back
- **GIVEN** a panel of 2 × 2 copies of `board.PcbDoc` with spacing 42 and 32 mm
- **WHEN** `uv run pytest tests/unit/backends/altium/test_embedded_array.py` writes the record and reads it back
- **THEN** the counts, spacing, location and rotation equal the written ones, and the stored document name is `../board/board.PcbDoc`

#### Scenario: Gate off
- **WHEN** `EMBEDDED_ARRAYS` is false and a panel is written with `--altium-panel auto`
- **THEN** `EmbeddedBoards6` has `Header` 0 and an empty `Data`, and the document is the flattened panel

### Requirement: Flattened panel documents
A flattened Altium panel SHALL be written from the panel's model through the lowering of a model: the board shape is the frame's rectangle, gap rings are tracks and arcs on a mechanical layer named `Route Tool Path`, score lines tracks on one named `V-Cut`, mouse-bite and tooling holes free round non-plated pads, fiducials free round copper pads.

#### Scenario: Flattened panel document
- **GIVEN** `tests/data/panels/tabs.py` written with `--target altium`
- **WHEN** `uv run pytest tests/unit/panel/test_altium_flat.py` reads the document back
- **THEN** it holds 8 copies of each component, the board shape is the frame's rectangle, the two named mechanical layers hold the gap rings and no score line (the fixture is tabbed), and each mouse-bite hole is a free pad with plating off and no copper
