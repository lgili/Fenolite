## ADDED Requirements

### Requirement: Panel scripts
`fenolite.dsl.panel.Panel(name, board)` SHALL declare a panel of the built board file `board` (relative to the script), with `grid`, `fit`, `rails`, `separate`, `tabs`, `vscore`, `fiducial(s)` and `tooling_hole(s)` in panel coordinates (origin top-left, Y down). A script MUST bind `panel`; a bad value MUST raise `DslError` at the call, naming the argument, and record nothing.

#### Scenario: A 2 × 2 grid
- **GIVEN** `panel = Panel("p", board="board.kicad_pcb")`
- **WHEN** `panel.grid(2, 2, gap=mm(2))` and `panel.separate("tabs", between="columns")` are called
- **THEN** `to_model(panel).array` has rows 2, cols 2, `gap_x` 2 000 000 and the separation `columns` → `tabs`

#### Scenario: Refused panel calls
- **WHEN** `panel.grid(0, 2)`, `panel.grid(2, 2, rot=45)`, `panel.separate("laser", between="rows")` and `panel.tabs(drill=mm(0))` are called
- **THEN** each raises `DslError`, naming `rows`, `rot`, `method` and `drill`

### Requirement: Panel fit rule
`Panel.fit(width, height, *, gap=None, rot=0)` SHALL choose `cols = ⌊(U + g) / (b + g)⌋` and rows likewise, U the width inside the rails and their gaps, b the board's box after the turn, g the gap of that axis; `rot="auto"` SHALL take the quarter turn that gives more copies, 0° on a tie. Zero copies MUST be `panel.no-fit`.

#### Scenario: Fit to a panel size
- **GIVEN** the 40 × 30 mm fixture, rails of 5 mm top and bottom, tabs everywhere with 2 mm gaps
- **WHEN** `panel.fit(mm(100), mm(100), rot="auto")` is laid out
- **THEN** the panel holds 3 columns and 2 rows of the board turned 90° (6 copies, where 0° gives 4), its size is 94 × 96 mm, and `result.panel.unused` is 6 mm × 4 mm
