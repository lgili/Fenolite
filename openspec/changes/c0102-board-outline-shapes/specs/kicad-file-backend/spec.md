## ADDED Requirements

### Requirement: Outline shape checks
`fenolite.backends.kicad.outline.check_outline(design) -> tuple[Issue, ...]` SHALL judge the model outline of a design before it is written, with the codes of the closed table `outline.CHECK_ISSUE_CODES`. They are `kicad.*` codes, so they pass `lens.build.BUILD_ISSUE_CODES` unchanged (`design-dsl`, "Build issue codes").
- An outline that breaks a rule of `design-model`, "Board outline arcs", MUST give `kicad.outline.invalid` naming the ring and the edge.
- On the rings of `board_outline` (`tol` = `DEFAULT_TOL`), each of these MUST give one `kicad.outline.invalid` naming the rings concerned, `board` or `cut-out <k>`: two edges of one ring that cross or touch, other than consecutive edges at their common vertex; two rings that cross or touch; a cut-out with a point outside the board ring; a cut-out inside another cut-out. The first two are what 10.0.6 reports as `invalid_outline`, a cut-out that touches the edge at one point included; 9.0.9 reports only the overlap and the crossing ring (`H-K-OUTLINE-INVALID`), and one verdict serves both targets. A cut-out inside a cut-out loads in KiCad as a further piece of board; it and a cut-out outside the board ring are refused because `board_outline` takes every ring after the first for a cut-out.
- When `outline_box(design)` ("Board outline as rings") exceeds the box of the board ring's vertices and arc mid points, the box that a zone declared without an outline takes (`design-dsl`, "Zones in the DSL"), `kicad.outline.zone-short` MUST name each zone of the design whose outline is that box.
- A design without a model outline gives no issue.

| code | severity | when |
|---|---|---|
| `kicad.outline.invalid` | error | the outline breaks the model's form, or its rings cross, touch, lie outside the board or inside a cut-out |
| `kicad.outline.zone-short` | warning | an arc of the board ring bulges beyond the box that a zone without an outline takes |

#### Scenario: A clean outline
- **GIVEN** the model of a script with `board(outline=shape.rect(mm(0), mm(0), mm(60), mm(40), radius=mm(3)))`, `d.cutout(shape.circle(mm(10), mm(10), mm(3.2)))` and `d.cutout(shape.slot((mm(19), mm(30)), (mm(31), mm(30)), mm(2)))`
- **WHEN** `uv run pytest tests/unit/backends/kicad/test_outline.py -k check` calls `check_outline`
- **THEN** it returns no issue

#### Scenario: Rings that cross, touch or nest
- **GIVEN** five models with `board(mm(40), mm(30))` and, in turn, a round cut-out of 4 mm centred at (39 mm, 15 mm), the same at (38 mm, 15 mm), two round cut-outs of 4 mm at (18 mm, 15 mm) and (21 mm, 15 mm), a round cut-out of 2 mm inside one of 6 mm both centred at (20 mm, 15 mm), and a round cut-out of 4 mm at (20 mm, 15 mm)
- **WHEN** `check_outline` runs on each
- **THEN** the first four give one `kicad.outline.invalid` each, the first two naming `board` and `cut-out 1`, and the fifth gives none

#### Scenario: A zone short of an arc
- **GIVEN** a model of `board(outline=((mm(0), mm(0)), (mm(40), mm(0)), arc_to((mm(45), mm(25)), (mm(40), mm(30))), (mm(0), mm(30))))`, whose arc reaches x = 48.03 mm beyond its mid at 45 mm, and `d.zone(gnd, layers=("B.Cu",))`
- **WHEN** `check_outline` runs
- **THEN** it returns one `kicad.outline.zone-short` naming the zone `GND`

## MODIFIED Requirements

### Requirement: Outline lowering
For any board whose `Board.outline` has points, created or read and then given an outline, `write_board` SHALL emit one item on `Edge.Cuts` per edge of the outer ring and of each cutout, closing every ring, with stroke width 0.1 mm and type `solid`: a `gr_arc` for an edge that `Outline.arcs` makes an arc (`design-model`, "Board outline arcs"), and a `gr_line` for every other edge. The items are created entities. A board with no outline, or an outline without points, MUST emit none. A board with both a non-empty outline and a `Graphic` on a layer of kind `edge` MUST give `kicad.board.outline-conflict`.
- A `gr_arc` MUST be written with `start`, `mid` and `end` such that `orient2d(start, mid, end)` is positive: an arc whose edge runs the other way is written from its second vertex to its first, the same points, so that KiCad's re-save keeps it unchanged (`H-G-ARC-DIR`, `H-K-OUTLINE-ARCS`).
- `outline.edge_texts(outline) -> tuple[str, ...]` MUST give one text per edge, `line X1 Y1 X2 Y2` or `arc X1 Y1 X2 Y2 XM YM`, integers in nanometres, the two vertices in increasing `(x, y)` order, so that the text does not depend on the direction of the edge. `outline.outline_digest(texts) -> str` MUST be the first 16 hexadecimal digits of the SHA-256 of the texts in sorted order, each followed by `\n`, in UTF-8.
- Each item's uuid MUST be `pcb.kicad_uuid(outline, "outline:<digest>:<edge text>")`, an edge being a part of its outline ("KiCad uuids on write"). Equal outlines therefore give equal uuids, and a change of any edge changes every uuid ("Outline changes across rebuilds" of `layout-lens` reads them back).

#### Scenario: Rectangle outline
- **GIVEN** a created board whose outline has the points (0, 0), (50 mm, 0), (50 mm, 30 mm), (0, 30 mm)
- **WHEN** it is written
- **THEN** the text holds four `gr_line` nodes on `Edge.Cuts`, the last ending at (0, 0), and the uuid of each is `kicad_uuid(outline, "outline:<digest>:<its edge text>")`, the digest being that of the four edge texts

#### Scenario: Outline and edge graphics
- **GIVEN** a created board with that outline and a `Graphic` on `Edge.Cuts`
- **WHEN** it is written
- **THEN** `LossyWriteError` is raised with an issue `kicad.board.outline-conflict`

#### Scenario: Outline set on a read board
- **GIVEN** `tests/data/kicad/tokens/skeleton.kicad_pcb` read with `read_board`, given the rectangle outline, once with its `Edge.Cuts` `gr_rect` and once with that `Graphic` removed from the model
- **WHEN** each design is written for target 9
- **THEN** the first raises `LossyWriteError` with an issue `kicad.board.outline-conflict`, and the second text holds four `gr_line` nodes on `Edge.Cuts` and no `gr_rect`

#### Scenario: Arcs written with a positive orientation
- **GIVEN** a created board with the rectangle outline and one cut-out whose vertices are (11.6 mm, 10 mm) and (8.4 mm, 10 mm), whose two edges are the arcs through (10 mm, 8.4 mm) and through (10 mm, 11.6 mm)
- **WHEN** it is written for target 9 and for target 10
- **THEN** each text holds four `gr_line` and two `gr_arc`, and the first `gr_arc` runs from (8.4 mm, 10 mm) through (10 mm, 8.4 mm) to (11.6 mm, 10 mm), each arc with a positive `orient2d`

#### Scenario: One moved vertex changes every uuid
- **GIVEN** the rectangle outline, and the same outline with (50 mm, 30 mm) moved to (51 mm, 30 mm)
- **WHEN** both boards are written
- **THEN** the two texts share no `uuid` of an `Edge.Cuts` item, and writing the first again gives its uuids back

### Requirement: Board outline as rings
`fenolite.backends.kicad.outline.board_outline(design) -> BoardOutline` SHALL give the board outline as closed rings in the board frame, joining edge endpoints closer than `outline.CHAIN_GAP` (10 000 nm) as KiCad does (`H-K-OUTLINE-CHAIN`):
- from `Board.outline`, when the model has an outline (`source == "model"`): the board ring of `Board.outline.points` and then each ring of `Board.outline.cutouts`, each a closed path of segments and of the arcs that `Outline.arcs` holds for it (`design-model`, "Board outline arcs"), the arcs polygonised at `tol`;
- otherwise from the root graphics on the layer of kind `edge` and the edge items of footprints that `frame.footprint_edges` gives in the board frame (`fp_line`, `fp_arc`, `fp_circle`, `fp_rect` and `fp_poly`; `H-K-OUTLINE-FPEDGE`), chained by `geometry.assemble_rings` (`source == "edge"`); circles and closed footprint polygons are rings by themselves;
- before chaining, endpoints whose squared distance is below `CHAIN_GAP` squared MUST be joined into the smallest point of their group, decided with integers; a group with more than two piece ends stays a `branching-contour`, and `joined` MUST count the groups that were joined;
- `rings[0]` MUST be the ring of largest area, and the others its cut-outs;
- when no ring closes, `rings` MUST be empty and `problem` MUST be one of `open-contour`, `branching-contour` and `no-edge-content`;
- `exact` MUST be false when an arc was approximated, of the model's outline or of the edge content.

`H-G-PLACE-OUTLINE` MUST be measured over the readable non-heavy demo boards and its counts recorded.

`outline.outline_box(design) -> tuple[int, int, int, int] | None` SHALL give the smallest box `(x0, y0, x1, y1)` that holds every ring of the model outline, each arc by `Arc.bbox`, or, without a model outline, every ring of `board_outline`; it is `None` when there is no ring. The staging row of the build and the off-board test of the lens read this box (`layout-lens`, "Placement precedence").

#### Scenario: Model outline
- **GIVEN** a built blink model
- **WHEN** `uv run pytest tests/unit/backends/kicad/test_outline.py -k model` calls `board_outline`
- **THEN** `source` is `model` and the ring holds the outline's points

#### Scenario: Edge graphics with a cut-out
- **GIVEN** an authored board with four `gr_line` items forming a rectangle and a `gr_circle` inside it, all on `Edge.Cuts`
- **WHEN** `board_outline` runs
- **THEN** `source` is `edge`, `rings[0]` is the rectangle and `rings[1]` the circle's ring

#### Scenario: Open contour named
- **GIVEN** the same board with one line removed
- **WHEN** `board_outline` runs
- **THEN** `rings` is empty and `problem` is `open-contour`

#### Scenario: Demo outlines counted
- **WHEN** `uv run pytest tests/corpus/test_outline_corpus.py` runs over the cached readable non-heavy demo boards
- **THEN** no call raises, every board gives at least one ring, and the counts of `model`, `edge`, each `problem` and the boards with `joined` above 0 are recorded for `H-G-PLACE-OUTLINE`

#### Scenario: Gap below the chaining distance
- **GIVEN** the authored rectangle of "Edge graphics with a cut-out" whose last line stops 9 999 nm short of its first corner, and the same with 10 000 nm
- **WHEN** `board_outline` runs on each
- **THEN** the first has one ring and `joined` 1, and the second has the problem `open-contour`

#### Scenario: Edge closed by a footprint
- **GIVEN** an authored board whose edge lines leave a 5 mm opening that the `fp_line` items of one placed footprint on `Edge.Cuts` close
- **WHEN** `board_outline` runs
- **THEN** `rings[0]` holds the footprint's edge points in the board frame

#### Scenario: Model outline with arcs
- **GIVEN** the model of `board(outline=shape.rect(mm(0), mm(0), mm(60), mm(40), radius=mm(3)))` with `d.cutout(shape.circle(mm(10), mm(10), mm(3.2)))`
- **WHEN** `board_outline` runs
- **THEN** `source` is `model`, `exact` is false, `rings` holds two rings, and every vertex of the second lies within 5 µm of the circle of radius 1.6 mm centred at (110 mm, 110 mm)

#### Scenario: Box of a round board
- **GIVEN** the model of `board(outline=shape.circle(mm(20), mm(20), mm(40)))`
- **WHEN** `outline_box` runs
- **THEN** it returns (100 mm, 100 mm, 140 mm, 140 mm), where the box of `Outline.points` alone would be (100 mm, 120 mm, 140 mm, 120 mm)
