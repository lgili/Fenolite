## MODIFIED Requirements

### Requirement: Projects carry the drawing sheet and text variables
`fenolite.backends.kicad.pro.apply_sheet_keys(project_text, design, *, schematic=False, allow_lossy=False, issues=None)` SHALL return the project text with `pcbnew.page_layout_descr_file` (`pro.PAGE_LAYOUT_POINTER`) and `text_variables` set from the design, and `triad.write_triad` SHALL run it on the project text after `synthesize_project` or `update_project`. The three codes below are rows of the closed table of "Project issue codes".
- When `Board.sheet.drawing_sheet` is not `None`, `pcbnew.page_layout_descr_file` MUST be set to it verbatim; otherwise the existing value MUST be kept. With `schematic=True`, which the build passes when it writes a schematic, `schematic.page_layout_descr_file` MUST be set to the same value (`H-K-PRO-WKS-SCH`); otherwise it MUST NOT be touched.
- Each key of `TitleBlock.params` MUST add or replace one member of `text_variables`. New members MUST be appended after the existing ones, sorted by name, and no member MUST be deleted. The key paths `pro.SHEET_KEY_PATHS` (`/text_variables/*`) MUST be the only paths that `write_triad` adds beyond the template's and `pro.PATTERN_ENTRY_PATHS`.
- A name in `wks.RESERVED_VARIABLES` MUST give the error `kicad.project.reserved-variable` and raise `LossyWriteError` (`FEN-7001`, `droppable=True`); with `allow_lossy=True` the variable MUST be left out with the warning `kicad.project.dropped-variable`.
- When the design sets neither key (no `Board.sheet.drawing_sheet` and no parameter), the text MUST come back unchanged, so every c0010 scenario holds byte for byte.
- `read_project` MUST fill `ProjectInfo.drawing_sheet` (`None` for an absent or empty value) and `ProjectInfo.text_variables` (name and value pairs in file order; a member whose value is not a string gives the info `kicad.project.unread-variable` and is skipped, so c0010's `kicad.project.unread-entry` keeps its meaning). `apply_project` MUST copy the first into `Board.sheet.drawing_sheet` when `Board.sheet` is not `None`, and the second into `TitleBlock.params`, creating `TitleBlock(params=…)` when `Board.title_block` is `None` and there are variables.
- A triad written by `write_triad` without `existing_project` MUST read back with `sheet` and `title_block` equal to the design's in normal form (`H-K-PRO-WKS`): `Board.sheet = None` reads back as `SheetFrameRef("A4")`, the `(paper "A4")` of a created board, and a `TitleBlock` whose seven fields are empty and which has no parameter reads back as `None`, because no `title_block` is written for it.

| code | severity |
|---|---|
| `kicad.project.reserved-variable` | error |
| `kicad.project.dropped-variable` | warning |
| `kicad.project.unread-variable` | info |

#### Scenario: Nothing to set
- **GIVEN** a design whose board has no `sheet` and no `title_block`
- **WHEN** `write_triad(design, name="b", target=10)` is called
- **THEN** `b.kicad_pro` equals `synthesize_project(design, target=10, board_name="b")` byte for byte

#### Scenario: Both keys written and read back
- **GIVEN** a design whose board has `sheet = SheetFrameRef("A3", drawing_sheet="frame.kicad_wks")` and `title_block = TitleBlock(title="Bench", params={"LOT": "7"})`
- **WHEN** the triad is written for target 10, then read with `read_board`, `read_project` and `apply_project`
- **THEN** the project has `pcbnew.page_layout_descr_file == "frame.kicad_wks"` and `text_variables == {"LOT": "7"}`, and the read board's `sheet` and `title_block` equal the design's

#### Scenario: Default presentation reads back in normal form
- **GIVEN** a design whose board has no `sheet` and `title_block = TitleBlock()`
- **WHEN** the triad is written for target 10, then read with `read_board`, `read_project` and `apply_project`
- **THEN** the read board has `sheet == SheetFrameRef("A4")` and `title_block is None`

#### Scenario: Existing variables kept
- **GIVEN** an existing project text whose `text_variables` is `{"ZZ": "1", "LOT": "6"}`, and a design with params `{"LOT": "7", "AA": "2"}`
- **WHEN** `write_triad(design, name="b", target=10, existing_project=text)` is called
- **THEN** `text_variables` is `{"ZZ": "1", "LOT": "7", "AA": "2"}`, in that order

#### Scenario: Reserved variable refused
- **GIVEN** a design with params `{"TITLE": "x"}`
- **WHEN** `write_triad(design, name="b", target=10)` is called, then again with `allow_lossy=True` and an `issues` list
- **THEN** the first call raises `LossyWriteError` with `kicad.project.reserved-variable`; the second writes no `TITLE` member and `issues` holds `kicad.project.dropped-variable`

#### Scenario: Schematic key with a schematic
- **GIVEN** a design whose `Board.sheet.drawing_sheet` is `blink.kicad_wks`
- **WHEN** `apply_sheet_keys` runs on a template project text with `schematic=True`, and again with `schematic=False`
- **THEN** the first text holds `blink.kicad_wks` under both `pcbnew.page_layout_descr_file` and `schematic.page_layout_descr_file`, and the second only under `pcbnew`

### Requirement: Board outline as rings
`fenolite.backends.kicad.outline.board_outline(design) -> BoardOutline` SHALL give the board outline as closed rings in the board frame, joining edge endpoints closer than `outline.CHAIN_GAP` (10 000 nm) as KiCad does (`H-K-OUTLINE-CHAIN`):
- from `Board.outline.points`, followed by each ring of `Board.outline.cutouts`, when the model has an outline (`source == "model"`);
- otherwise from the root graphics on the layer of kind `edge` and the edge items of footprints that `frame.footprint_edges` gives in the board frame (`fp_line`, `fp_arc`, `fp_circle`, `fp_rect` and `fp_poly`; `H-K-OUTLINE-FPEDGE`), chained by `geometry.assemble_rings` (`source == "edge"`); circles and closed footprint polygons are rings by themselves;
- before chaining, endpoints whose squared distance is below `CHAIN_GAP` squared MUST be joined into the smallest point of their group, decided with integers; a group with more than two piece ends stays a `branching-contour`, and `joined` MUST count the groups that were joined;
- `rings[0]` MUST be the ring of largest area, and the others its cut-outs;
- when no ring closes, `rings` MUST be empty and `problem` MUST be one of `open-contour`, `branching-contour` and `no-edge-content`;
- `exact` MUST be false when an arc was approximated.

`H-G-PLACE-OUTLINE` MUST be measured over the readable non-heavy demo boards and its counts recorded.

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
