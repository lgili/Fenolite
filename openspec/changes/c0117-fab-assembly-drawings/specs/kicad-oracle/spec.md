## ADDED Requirements

### Requirement: Drawing facts are probed
`tests/kicad/drawings/` SHALL settle `H-K-DRAW-ITEMS`, `H-K-DRAW-TEXT`, `H-K-DRAW-PAGE`, `H-K-DRAW-SHEET`, `H-K-DRAW-DRILL`, `H-K-DRAW-ASSEMBLY`, `H-K-DRAW-REPEAT` and `H-K-DRAW-LAYER` with probes registered in `tests/kicad/_probes.py` and recorded in `docs/evidence/kicad/probes/<version>.json` for 9.0.9 and 10.0.6.
- The bench `tests/kicad/drawings/_drawbench.py` MUST be authored for Fenolite: a four-layer board, written by `write_board` for each target, with through, blind and micro vias, plated, unplated and slotted holes, parts on both sides, one do-not-populate part, one catalog footprint and one footprint that shows `${REFERENCE}`, and a stack-up.
- The probes MUST be: `draw-table`, `draw-textbox`, `draw-dimension`, `draw-vars`, `draw-defvar-board`, `draw-defvar-sheet` (items); `draw-wrap-overflow`, `draw-pitch`, `draw-glyph-bound` (text); `draw-page-position`, `draw-mirror`, `draw-no-holes` and the help rows of `--scale` (page); `draw-default-sheet-<paper>` for A4, A3, A2, A1 and A0 (sheet); `draw-drill-files`, `draw-drill-counts` (drill); `draw-dnp-crossout`, `draw-dnp-hide`, `draw-values`, `draw-pads`, `draw-bottom-designator` (assembly); `draw-repeat-pdf`, `draw-repeat-report` (repeat); `draw-layer-added` (layer).
- Each probe MUST read the searchable SVG texts or the PDF of its run through the runner, and MUST have a control that gives the other outcome: the same plot without the item, the option or the variable.
- `tests/kicad/drawings/test_drawing_oracle.py` MUST export both drawing kinds of the bench on each major and check that the drill check passes, that an SVG plot of each page's copy shows every block's texts inside its block and no block text inside the board box or an obstacle, and that two exports give equal `content_sha256` for every drawing artefact.
- A probe that records another outcome than its hypothesis states MUST stop the part it settles, and the register row MUST record what KiCad showed.

#### Scenario: Items are drawn on both majors
- **WHEN** `uv run pytest tests/kicad/drawings/test_drawing_probes.py -k items -rA` runs on the local `kicad-cli` 10.0.6 and in the pinned 9.0.9 image
- **THEN** `draw-table`, `draw-textbox`, `draw-dimension`, `draw-vars`, `draw-defvar-board` and `draw-defvar-sheet` are `present` in both probe files, and each control is `absent`

#### Scenario: Drill counts agree
- **WHEN** `uv run pytest tests/kicad/drawings/test_drawing_probes.py -k drill -rA` runs on both majors
- **THEN** `draw-drill-counts` is `equal`: per drill file and diameter, the report's count equals that of `drill_rows` for the bench's plated, unplated, slotted and blind holes

#### Scenario: Default sheet boxes
- **WHEN** `uv run pytest tests/kicad/drawings/test_drawing_probes.py -k default_sheet -rA` plots an empty copy of the bench on A4 to A0 with no project sheet
- **THEN** each `draw-default-sheet-<paper>` is `equal`: the plotted borders and title block lie where `default_sheet_obstacles` puts them, within 0.01 mm

#### Scenario: Drawings are repeatable
- **WHEN** `uv run pytest tests/kicad/drawings/test_drawing_oracle.py -k repeat` exports the bench's drawings twice on one major
- **THEN** every drawing artefact has equal `content_sha256` in both exports
