## MODIFIED Requirements

### Requirement: Outline shape checks
`fenolite.backends.kicad.outline.check_outline(design) -> tuple[Issue, ...]` SHALL judge the model outline of a design before it is written, with the codes of the closed table `outline.CHECK_ISSUE_CODES`. They are `kicad.*` codes, so they pass `lens.build.BUILD_ISSUE_CODES` unchanged (`design-dsl`, "Build issue codes").
- An outline that breaks a rule of `design-model`, "Board outline arcs" or "Board slots", MUST give `kicad.outline.invalid` naming the ring and the edge, or the slot.
- The rings are those of `lowered_outline(outline)` ("Slots and merged rings in the board file"), taken by `board_outline` (`tol` = `DEFAULT_TOL`). Cut-outs and slots whose areas overlap are merged first; each merged group MUST give one `kicad.outline.merged` naming its items (`slot <name>`, `cut-out <k>`). Without the `geo` extra each group MUST instead give one `kicad.outline.overlap` naming its items, with the hint `pip install 'fenolite[geo]'`, and the build stops as for `kicad.outline.invalid`.
- On those rings, each of these MUST give one `kicad.outline.invalid` naming the rings concerned, `board`, `cut-out <k>` or `slot <name>`: two edges of one ring that cross or touch, other than consecutive edges at their common vertex; two rings that cross or touch without a merged area; a cut-out or slot with a point outside the board ring or touching it; a cut-out inside another cut-out. The first two are what 10.0.6 reports as `invalid_outline`, a cut-out that touches the edge at one point included; 9.0.9 reports only the overlap (`H-K-OUTLINE-INVALID`), and one verdict serves both targets. A cut-out inside a cut-out loads in KiCad as a further piece of board; it and a cut-out outside the board ring are refused because `board_outline` takes every ring after the first for a cut-out.
- When `outline_box(design)` ("Board outline as rings") exceeds the box of the board ring's vertices and arc mid points, the box that a zone declared without an outline takes (`design-dsl`, "Zones in the DSL"), `kicad.outline.zone-short` MUST name each zone of the design whose outline is that box.
- A design without a model outline gives no issue.

| code | severity | when |
|---|---|---|
| `kicad.outline.invalid` | error | the outline breaks the model's form, or its rings cross, touch, lie outside the board or inside a cut-out |
| `kicad.outline.zone-short` | warning | an arc of the board ring bulges beyond the box that a zone without an outline takes |
| `kicad.outline.merged` | info | overlapping cut-outs and slots are written as one ring |
| `kicad.outline.overlap` | error | cut-outs and slots overlap and the `geo` extra that merges them is not installed |

#### Scenario: A clean outline
- **GIVEN** the model of a script with `board(outline=shape.rect(mm(0), mm(0), mm(60), mm(40), radius=mm(3)))`, `d.cutout(shape.circle(mm(10), mm(10), mm(3.2)))` and `d.cutout(shape.slot((mm(19), mm(30)), (mm(31), mm(30)), mm(2)))`
- **WHEN** `uv run pytest tests/unit/backends/kicad/test_outline.py -k check` calls `check_outline`
- **THEN** it returns no issue

#### Scenario: Rings that cross, touch or nest
- **GIVEN** five models with `board(mm(40), mm(30))` and, in turn, a round cut-out of 4 mm centred at (39 mm, 15 mm), the same at (38 mm, 15 mm), two round cut-outs of 4 mm at (18 mm, 15 mm) and (22 mm, 15 mm), which touch at one point, a round cut-out of 2 mm inside one of 6 mm both centred at (20 mm, 15 mm), and a round cut-out of 4 mm at (20 mm, 15 mm)
- **WHEN** `check_outline` runs on each
- **THEN** the first four give one `kicad.outline.invalid` each, the first two naming `board` and `cut-out 1`, and the fifth gives none

#### Scenario: A zone short of an arc
- **GIVEN** a model of `board(outline=((mm(0), mm(0)), (mm(40), mm(0)), arc_to((mm(45), mm(25)), (mm(40), mm(30))), (mm(0), mm(30))))`, whose arc reaches x = 48.03 mm beyond its mid at 45 mm, and `d.zone(gnd, layers=("B.Cu",))`
- **WHEN** `check_outline` runs
- **THEN** it returns one `kicad.outline.zone-short` naming the zone `GND`

#### Scenario: Overlapping slots merged or refused
- **GIVEN** `board(mm(40), mm(30))`, `d.slot(mm(15), mm(10), length=mm(12), width=mm(2), name="A")` and `d.slot(mm(20), mm(15), length=mm(12), width=mm(2), rot=90, name="B")`
- **WHEN** `uv run pytest tests/unit/backends/kicad/test_slots_outline.py -k overlap` calls `check_outline` with the `geo` extra and with `pyclipper` hidden
- **THEN** the first gives one `kicad.outline.merged` naming `slot A` and `slot B`, and the second one `kicad.outline.overlap` naming both with the hint `pip install 'fenolite[geo]'`; two round cut-outs of 4 mm at (18 mm, 15 mm) and (21 mm, 15 mm), which overlap, give one `kicad.outline.merged` naming `cut-out 1` and `cut-out 2`

## ADDED Requirements

### Requirement: Slots and merged rings in the board file
`outline.lowered_outline(outline)` SHALL return the outline a KiCad board holds: the board ring, the cut-outs, then each slot's stadium, every overlapping group replaced by its `merge_rings` result, and no slots. The writer, the edge signature, `board_outline`, `outline_box`, `check_outline` and `fill_inputs_digest` MUST read it. `write_board` MUST refuse a group it cannot merge with `kicad.board.outline-overlap`.

#### Scenario: A lone slot as a stadium
- **GIVEN** the model of `board(mm(40), mm(30))` and `d.slot(mm(15), mm(10), length=mm(12), width=mm(2))`
- **WHEN** it is written for targets 9 and 10
- **THEN** `Edge.Cuts` holds two `gr_line` from (110, 109) to (120, 109) mm and from (120, 111) to (110, 111) mm and two `gr_arc` through (121, 110) mm and (109, 110) mm, besides the four lines of the board

#### Scenario: Overlap through the model API
- **GIVEN** a model with the two overlapping slots of "Overlapping slots merged or refused" and `pyclipper` hidden
- **WHEN** `write_board` runs
- **THEN** it raises `LossyWriteError` whose issue is `kicad.board.outline-overlap` naming both slots

### Requirement: Outline read back from the edges
`outline.edge_outline(design)` SHALL return a board's edge rings as an `Outline` with exact lines and arcs, ring 0 the board, or `None` when `board_outline` gives a problem. `outline.slots_of(outline)` SHALL return the cut-outs that are stadiums within 1 nm as `OutlineSlot`s with content ids. A read board's `Board.outline` stays `None`.

#### Scenario: Slots read back
- **GIVEN** the shared fixture `tests/data/slots/design.py` built for target 10 and read with `read_board`
- **WHEN** `uv run pytest tests/unit/backends/kicad/test_slots_outline.py -k read_back` calls `edge_outline` and `slots_of`
- **THEN** the lone slot is returned with its centre, length, width and rotation within 1 µm, the merged L is a cut-out of seven vertices with three arcs, and the rounded cut-out keeps its four arcs

### Requirement: Free holes refused by name
`write_board` SHALL refuse a board whose `Board.holes` is not empty with the writer error `kicad.board.free-hole` (`LossyWriteError`) naming each hole's id, with the hint "declare a hole with design.hole(), or place a board-only footprint with an unnumbered np_thru_hole pad".

#### Scenario: A model hole
- **GIVEN** a model board with one `Hole` of 3.2 mm
- **WHEN** `write_board` runs
- **THEN** it raises `LossyWriteError` with `kicad.board.free-hole` and that hint, and no `ValueError`
