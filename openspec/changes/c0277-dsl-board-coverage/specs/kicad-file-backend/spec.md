## ADDED Requirements

### Requirement: Coverage items written to boards
`write_board` SHALL write the items of change c0277 with the tokens recorded in `docs/formats/kicad/board.md` from the KiCad file-format documentation (S-0001): copper texts with `knockout`, graphics with a net, pad trapezoid deltas, chamfers, custom primitives and teardrops, via teardrops, groups, images, radial, leader and centre dimensions, zone arcs, footprint-level overrides, field fonts and model references.

#### Scenario: Read back what was written
- **GIVEN** the authored design `tests/_boards.py::coverage_board()` holding one of each item
- **WHEN** it is written for targets 9 and 10 and read with `read_board`
- **THEN** each modelled item reads back equal, and each item the reader keeps opaque is present once in the text with the written tokens

### Requirement: Coverage tokens are gated by target
Every token the coverage writer emits SHALL match a row of the token inventory with the majors that know it, and `check_emittable` SHALL refuse a token a target does not know: in modelled content with `LossyWriteError`, never dropped.

#### Scenario: Created coverage tokens are known
- **WHEN** `uv run pytest tests/unit/backends/kicad/test_pcb_write.py -k coverage_tokens` runs
- **THEN** every head and field the coverage writer can create matches an inventory row, is in `FLOOR_HEADS`, or is in the skeleton

## MODIFIED Requirements

### Requirement: Created board header
For a created design, `write_board` SHALL emit exactly the root head set of c0007's `tests/data/kicad/tokens/skeleton.kicad_pcb`, plus `title_block` when one of the seven fields of `Board.title_block` is non-empty:
- `version`, `generator` and `generator_version`;
- `(general (thickness T) (legacy_teardrops no))`, where T is `Stackup.thickness()` of the stack-up that "Stack-up written to boards" completes, or 1.6 mm without a stack-up;
- `paper`, written by `pcb.paper_node(Board.sheet)`, which gives `(paper "A4")` when `Board.sheet` is `None` ("Paper and title block on boards");
- `title_block`, written by `pcb.title_block_node(Board.title_block)` right after `paper`, only when one of its seven fields is non-empty;
- `layers`, from `Board.layers` and each layer's `kicad` bag;
- `(setup (pad_to_mask_clearance 0))`, with the node of "Stack-up written to boards" as the first child of `setup` when `Board.stackup` is set, and followed inside `setup`, after `pad_to_mask_clearance`, by the children of "Via protection defaults on boards" when `Board.via_protection` is not `None`;
- for target 9 only, the net table.

The content follows in `CANONICAL_ORDER`. `pcb.CREATED_ROOT_HEADS` MUST stay the head set of a created board without a title block; `pcb.CANONICAL_ORDER["kicad_pcb"]` MUST hold `title_block` right after `paper`, and `pcb.CANONICAL_ORDER["title_block"]` MUST be `("title", "date", "rev", "company", "comment")`. `fenolite.backends.kicad.layers.CREATED_COPPER_COUNTS` MUST hold every even count from 2 to 32 (change c0277), and 1 exactly when `H-K-PCB-ONE-COPPER` records that both majors load a one-copper table; the table of 1 is the two-copper table without the `B.Cu` row. For each of these counts, `fenolite.backends.kicad.layers.created_layers(copper)` MUST return the two-copper-layer set recorded in `docs/formats/kicad/board.md` with the rows of `layers.inner_rows(copper)` inserted right after `F.Cu`: one row `(2k + 2, "In<k>.Cu", signal)` without a user name for each inner layer k = 1 … copper − 2, in that order. The numbers are those of the 9.0 scheme (`F.Cu` 0, `B.Cu` 2, `In<k>.Cu` 2k + 2, `Edge.Cuts` 25), the rows are the same for targets 9 and 10 (`H-K-PCB-LAYERS`), and each layer's `kicad` bag holds the KiCad number, type and user name. Any other `copper` value, an odd count included, MUST raise `ValueError` naming the counts. `layers.created_count(names)` MUST return the count whose created table has exactly the copper layer names `names`, in table order, and `None` when no count of `CREATED_COPPER_COUNTS` has them. Every head and field name the writer can create MUST match a row of the token inventory, appear in c0007's skeleton, or be listed in `pcb.FLOOR_HEADS`: a closed tuple of names that the 8.0 board format already has, each recorded in `docs/formats/kicad/board.md` with its source and written by the created test board that the triad oracle loads on both majors. `FLOOR_HEADS` MUST include `title_block`, `title`, `date`, `rev`, `company` and `comment` (S-0001; S-0033 at tag 8.0.0), and `stackup`, `color`, `material`, `epsilon_r`, `loss_tangent`, `copper_finish` and `dielectric_constraints` (S-0021, S-0058); `type` is not listed, because the skeleton holds it already and `FLOOR_HEADS` is disjoint from the skeleton. `tests/_boards.py::created_board()` MUST set `SheetFrameRef("A4")`, a `TitleBlock` whose seven fields are non-empty, and, for every created copper count, a `Stackup` with a dielectric of two sheets, a colour, a material and both decimals, so the created test board writes them.

#### Scenario: Head set of a created 2-layer board
- **GIVEN** a created design whose board has `created_layers(2)` and no content
- **WHEN** it is written for target 9
- **THEN** the root's child heads are, in order, `version`, `generator`, `generator_version`, `general`, `paper`, `layers`, `setup`, `net`

#### Scenario: No net table for target 10
- **GIVEN** the same design
- **WHEN** it is written for target 10
- **THEN** the root's child heads are `version`, `generator`, `generator_version`, `general`, `paper`, `layers`, `setup`, and no child is headed `net`

#### Scenario: Four copper layers
- **WHEN** `created_layers(4)` is called
- **THEN** the copper layers are `F.Cu`, `In1.Cu`, `In2.Cu` and `B.Cu` with KiCad numbers 0, 4, 6 and 2

#### Scenario: Six and eight copper layers
- **WHEN** `created_layers(6)` and `created_layers(8)` are called
- **THEN** the copper layers of the first are `F.Cu`, `In1.Cu`, `In2.Cu`, `In3.Cu`, `In4.Cu` and `B.Cu` with KiCad numbers 0, 4, 6, 8, 10 and 2 and the type `signal`, the second adds `In5.Cu` (12) and `In6.Cu` (14) before `B.Cu`, every other row equals the row of `created_layers(2)`, and `created_count` of each table's copper names gives 6 and 8

#### Scenario: Counts outside the table
- **WHEN** `created_layers(c)` is called for `c` equal to 0, 3, 34 and `True`, and `created_count(("F.Cu", "In1.Cu", "B.Cu"))` is called
- **THEN** each `created_layers` call raises `ValueError` naming the even counts 2 to 32, and `created_count` returns `None`

#### Scenario: Thirty-two copper layers
- **WHEN** `created_layers(32)` is called
- **THEN** the copper layers are `F.Cu` (0), `In1.Cu` (4) to `In30.Cu` (62) and `B.Cu` (2), each `In<k>.Cu` numbered 2k + 2 with the type `signal`, every other row equals the row of `created_layers(2)`, and `created_count` of its copper names gives 32

#### Scenario: Created tokens are known
- **WHEN** `uv run pytest tests/unit/backends/kicad/test_pcb_write.py -k created_tokens` runs
- **THEN** every head and field in `CANONICAL_ORDER` and in the created header is found in the skeleton, is in `FLOOR_HEADS`, or matches an inventory row, and every name of `FLOOR_HEADS` occurs in the parsed text of the created test board written for target 9

#### Scenario: Created board with a Tabloid sheet
- **GIVEN** a created design whose board has `created_layers(2)`, `sheet = SheetFrameRef("Tabloid")` and `title_block = TitleBlock(title="Bench")`
- **WHEN** it is written for target 10
- **THEN** the root's child heads are `version`, `generator`, `generator_version`, `general`, `paper`, `title_block`, `layers`, `setup`, and the `paper` child is `(paper "User" 431.8 279.4)`

#### Scenario: Created board with a stack-up
- **GIVEN** a created design whose board has `created_layers(2)` and a two-layer stack-up
- **WHEN** it is written for target 10
- **THEN** the root's child heads are those of "No net table for target 10", and `setup` holds `stackup` and then `(pad_to_mask_clearance 0)`

#### Scenario: Created board with a via protection default
- **GIVEN** a created design whose board has `created_layers(2)` and `via_protection = ViaProtection(tenting_front=True, tenting_back=False)`
- **WHEN** it is written for target 10
- **THEN** the root's child heads are those of "No net table for target 10", and `setup` holds `pad_to_mask_clearance`, `tenting`, `covering`, `plugging`, `capping` and `filling`, in that order
