## ADDED Requirements

### Requirement: Render page of a board outside the sheet
`fenolite render --svg` SHALL plot the board area without the drawing sheet when the board does not lie inside the sheet, and SHALL take `--page sheet|board|auto` (default `auto`) to choose (change c0409, B11).

#### Scenario: A board at negative coordinates
- **GIVEN** the authored project, once with its page shrunk below its outline, and authored outlines at negative Y or past the page edge
- **WHEN** `uv run pytest tests/unit/backends/kicad/test_plot_page.py -q` renders it against the fake `kicad-cli`
- **THEN** a board outside its page is plotted with `--exclude-drawing-sheet --page-size-mode 2` and `result.svg_page` `board`, a board inside it without them, and `--page sheet` or `--page board` overrides the choice

#### Scenario: The board-area page on KiCad
- **GIVEN** an authored 50 mm by 40 mm board at negative Y on an A4 page
- **WHEN** `uv run pytest tests/kicad/export/test_svg_page.py -q` plots it on 9.0.9 and 10.0.6
- **THEN** the sheet plot is the 297 mm by 210 mm page, and both board-area plots are 50 mm by 40 mm
