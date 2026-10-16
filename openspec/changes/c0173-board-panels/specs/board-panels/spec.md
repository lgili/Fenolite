## ADDED Requirements

### Requirement: Panel layout
`panel.layout(panel, board) -> PanelLayout` SHALL place `rows × cols` copies of the board's outline box with the array's gaps and quarter turn inside the rails, and SHALL give the frame ring, the gap rings, the tabs with their holes, the score lines, the fiducials and the tooling holes in integer nanometres, each with an id derived from its key. It MUST NOT round: a copy is an integer translation and a quarter turn.

#### Scenario: A 2 × 2 tabbed panel
- **GIVEN** the 40 × 30 mm fixture board, `grid(2, 2)`, `rails(top=mm(5), bottom=mm(5))` and `separate("tabs", between=…)` for columns, rows and rails
- **WHEN** `uv run pytest tests/unit/panel/test_layout.py -k grid` runs `layout`
- **THEN** the panel is 82 × 76 mm, copy (1, 1) has its origin at (0, 7 mm), copy (2, 2) at (42 mm, 39 mm), and every tab between two copies holds two rows of five 0.6 mm holes

#### Scenario: Copy ids are stable
- **WHEN** the same panel is laid out twice, once after changing `--seed`
- **THEN** every id of the two layouts is equal, and copy (1, 2) has the id `derived_id("pcy", "panel", "copy:1.2")`

### Requirement: Panel separations
A V-scored edge set SHALL have no gap and one straight score line per boundary from panel edge to panel edge; a tabbed edge set SHALL have its gap and `max(1, ⌈L / pitch⌉)` tabs per edge of length L, evenly spaced, with a row of holes at each board edge of a tab and none on a rail's side. Holes are tangent to the board edge outside it unless `inset` is set.

#### Scenario: Mixed separations
- **GIVEN** the fixture with `grid(2, 4)`, `separate("vscore", between="rows")` and `separate("tabs", between="columns")`
- **WHEN** `layout` runs
- **THEN** the gap between rows is 0, there is one horizontal score line between the rows that spans the panel's width, and each column boundary holds tabs and no score line

### Requirement: Panel checks
`panel.checks.check_panel(panel, layout, board)` SHALL give the findings of design Decision 6 of change c0173 (`panel.vscore-copper`, `panel.vscore-shape`, `panel.vscore-spacing`, `panel.vscore-thickness`, `panel.tab-copper`, `panel.gap`, `panel.tab-count`, `panel.tab-spacing`, `panel.fiducial-place`, `panel.tooling-place`, `panel.size` and the structural errors), each naming the copy, edge or item.

#### Scenario: Copper near a score line
- **GIVEN** `tests/data/panels/vscore.py`, whose board has a track 0.3 mm from its right edge, scored between columns
- **WHEN** `uv run pytest tests/unit/panel/test_checks.py -k vscore` runs the checks
- **THEN** there is one `panel.vscore-copper` error per scored copy edge that the track faces, naming the copy and the 0.3 mm

#### Scenario: A gap too narrow
- **WHEN** the tabbed panel is laid out with `gap=mm(1)`
- **THEN** `panel.gap` is an error naming 1 mm and the 1.2 mm limit

### Requirement: Panel limits cite their sources
Every default of `panel.limits.DEFAULTS` SHALL name the fact row of `docs/formats/kicad/panel.md` whose figure it equals, and `Panel(limits=…)` SHALL replace any default by the user's value; a value that is not a length or a count MUST raise `DslError`.

#### Scenario: Every default cites its row
- **WHEN** `uv run pytest tests/unit/panel/test_limits.py` reads `DEFAULTS` and `panel.md`
- **THEN** each default names a registered source of a row of `panel.md` and equals a figure of that row

### Requirement: Panel evidence
A KiCad panel board SHALL be `KICAD-VERIFIED (9.0.x, 10.0.x)` only through `H-K-PANEL-LOAD`, `H-K-PANEL-DRILL` and `H-K-PANEL-NETS`, a flattened Altium panel `ORACLE-VERIFIED(kicad-cli)` through `H-A-PANEL-FLAT`, and an Embedded Board Array `ALTIUM-VERIFIED(kit)` only through `H-A-PANEL-KIT`; each reply MUST carry the level of its form.

#### Scenario: Levels of a reply
- **WHEN** `fenolite panel tests/data/panels/tabs.py --out P --target altium --dry-run --json` runs with the gate off
- **THEN** `result.panel.form` is `flat` and `evidence.level` is that of `H-A-PANEL-FLAT`
