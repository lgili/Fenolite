## ADDED Requirements

### Requirement: Stack-up on boards
`fenolite.backends.kicad.stackup.project_stackup(setup, layers, *, issues=None) -> Stackup | None` SHALL project the `stackup` child of a board's `setup` node into a `Stackup`, and `read_board` SHALL set `Board.stackup` to it, passing the board's `Layer` entities and its own `issues`. `setup` MUST stay an opaque root slot, so "Modelled board content", every `opaque_count` and RT1 are unchanged. The facts, with their sources and labels, MUST be in `docs/formats/kicad/board.md`, section "Stack-up" (S-0021, S-0058, S-0020, S-0029).
- **Rows.** A `layer` row whose name is a layer of the board's table is that layer's row: `F.SilkS` and `B.SilkS` (types `Top Silk Screen` and `Bottom Silk Screen`) give kind `silkscreen`, `F.Paste` and `B.Paste` (`Top Solder Paste`, `Bottom Solder Paste`) `solderpaste`, `F.Mask` and `B.Mask` (`Top Solder Mask`, `Bottom Solder Mask`) `soldermask`, and a copper layer (type `copper`) `copper`; `stackup.TYPES` MUST hold these pairs. Every other row is a dielectric row: kind `dielectric`, with `dielectric_kind` `core` or `prepreg` from its type and `None` for another type or none; another type's text MUST be kept as the pair `type` of the entry's `kicad` bag.
- **Values.** `thickness` comes from the row's `thickness` child, and is 0 for a silkscreen or paste row without one; `material`, `epsilon_r`, `loss_tangent` and `color` are kept as written. The `addsublayer` atoms of a dielectric row MUST split it into consecutive entries, one per sheet, each with the row's name and `dielectric_kind` and with the children that follow its atom. The silkscreen, paste and mask entries of each side MUST be ordered silkscreen, paste, mask from the outside in, whatever their row order. `Stackup.finish` is the `copper_finish` text, `""` for `None` or without the child; `impedance_controlled` is true for `(dielectric_constraints yes)`. `edge_connector`, `castellated_pads`, `edge_plating` and unknown children stay in the fragment only.
- **Complete nodes only** (`H-K-STACKUP-COMPLETE`). The projection MUST be `None`, with one `kicad.board.stackup-unused` (warning) naming the first difference, when the rows named after layers are not exactly the table's silkscreen, paste and mask layers and all its copper layers, when such a row has a type other than its layer's, when the copper rows are not in table order, or when the rows between two neighbouring copper rows are not exactly one dielectric row. Its hint MUST say that KiCad's job file states no thickness for such a board.
- **Exact values.** The projection MUST be `None`, with one `kicad.board.stackup-unmodelled` (info), for a complete node that holds a thickness that is not a whole number of nanometres, a copper, dielectric or mask row without `thickness`, an `epsilon_r` that is not a plain decimal above 0, a `loss_tangent` that is not a plain decimal (0 is kept: KiCad writes it for a solder mask), or a dielectric row above the first copper row or below the last.
- **Thickness.** When the projection is not `None` and the root `general` thickness differs from `Stackup.thickness()`, one `kicad.board.stackup-thickness` (warning) MUST name both values and say that KiCad's job file states the first and its IPC-2581 export the second (`H-K-STACKUP-JOB`, `H-K-STACKUP-RESAVE`). The model keeps the sum.
- **Ids.** The stack-up MUST have the id `derived_id("stk", "kicad", "stackup")` and its k-th entry, k from 0, `derived_id("sly", "kicad", "stack:<k>")`.
- The three codes MUST join `pcb.ISSUE_CODES`. A board whose `setup` holds no `stackup` has `Board.stackup = None` and gets none of them.

#### Scenario: Four-layer node projected
- **GIVEN** the authored `tests/data/kicad/board/stackup_four.kicad_pcb`: four copper layers, masks of 0.01 mm (the top one `Green`), a prepreg, a core holding a second sheet of 0.3 mm of the material `Laminate B` and a prepreg, `(copper_finish "ENIG")`, `(dielectric_constraints yes)`, and a `general` thickness equal to the sum of its rows
- **WHEN** it is read with an `issues` list
- **THEN** `board.stackup` holds 14 entries from `F.SilkS` to `B.SilkS`, the core's two sheets consecutive, both named `dielectric 2` with `dielectric_kind == "core"`; `finish == "ENIG"`; `impedance_controlled` is true; `thickness() == 2_025_000`; the issues hold no `kicad.board.stackup-*` code; and the `setup` child is an `Opaque` slot

#### Scenario: A node KiCad ignores
- **GIVEN** the same board with its four silkscreen and paste rows removed by token edit
- **WHEN** it is read and written again for its own target
- **THEN** `board.stackup is None`, the issues hold one `kicad.board.stackup-unused`, and the written `setup` child is tree-equal to the source's

#### Scenario: Total thickness that differs from the rows
- **GIVEN** the authored four-layer board with its `general` thickness changed to 1.6 by token edit
- **WHEN** it is read
- **THEN** `board.stackup.thickness() == 2_025_000`, and one `kicad.board.stackup-thickness` warning names 1.6 mm and 2.025 mm

#### Scenario: Board without a node
- **WHEN** `tests/data/kicad/board/two_layer.kicad_pcb` is read
- **THEN** `board.stackup is None`, and the issues hold no `kicad.board.stackup-*` code

#### Scenario: Corpus census
- **WHEN** `uv run pytest tests/corpus/test_stackup_census.py` runs (`needs_corpus`)
- **THEN** every cached board whose `setup` holds a node gets a stack-up (18 boards at the census of 2026-10-05; 17 of the 21 boards read on 2026-10-07), the counts are written to `docs/evidence/kicad-stackup.md`, and `tests/corpus/test_board_rt1.py` passes with every `opaque_count` unchanged

### Requirement: Stack-up written to boards
`write_board` SHALL write `Board.stackup` as the `stackup` child of `setup` through `fenolite.backends.kicad.stackup.complete(stackup, layers) -> Stackup` and `stackup_node(stackup, layers) -> Node`, in the same form for targets 9 and 10 (`H-K-STACKUP-JOB`).
- **Completion.** `complete` MUST add one entry of thickness 0 for each silkscreen, paste and mask layer of the table that the stack-up lacks, named after its layer and placed as "Stack-up on boards" orders them, and MUST change nothing else; a stack-up that lacks none is returned unchanged.
- **Node.** `stackup_node` MUST write one `layer` row per entry of the completed stack-up, except that consecutive dielectric entries between two copper entries MUST form one row: the first entry's children, then for each further entry the atom `addsublayer` and that entry's children. A row holds, in this order: the entry's name; `(type "<t>")`, with `t` from `stackup.TYPES`, the `dielectric_kind`, or the `type` pair of a dielectric's `kicad` bag, and no `type` child for a dielectric that has neither; `(color "<c>")` when set; `(thickness T)` for copper, dielectric and mask entries, also when T is 0; `(material "<m>")`, `(epsilon_r E)` and `(loss_tangent L)` when set. The children after `addsublayer` follow the same order from `color` on. The rows are followed by `(copper_finish "<f>")`, with `"None"` for an empty finish, and `(dielectric_constraints yes|no)`.
- **Created boards.** For a created design whose `Board.stackup` is set, the node MUST be the first child of `setup`, and the `general` thickness MUST be `Stackup.thickness()` of the completed stack-up ("Created board header").
- **Read boards.** When `Board.stackup` equals the projection of the `setup` slot, compared by `stackup.values`, which leaves out ids, provenance and every bag pair but `type`, the `setup` and `general` fragments MUST be kept. Otherwise the writer MUST replace the `stackup` child of `setup` by the node, or insert the node as the first child of `setup`, keep every other child of `setup` tree-equal at its place, keep the `edge_connector`, `castellated_pads` and `edge_plating` children of a replaced node after `dielectric_constraints`, and rewrite only the `thickness` of `general`, to the new sum. One `kicad.board.stackup-rewritten` (info) MUST name the children of replaced rows that the model does not hold, when there are any. A `Board.stackup` of `None` on a board whose `setup` holds a projected node MUST remove the `stackup` child and keep `general`.
- **Refusal.** A stack-up that would give a `model.stackup-*` finding, or whose copper entries are not the table's copper layers in table order, MUST raise `LossyWriteError` with `kicad.board.stackup-invalid` (error), which `allow_lossy` MUST NOT drop. The two codes MUST join `pcb.WRITE_ISSUE_CODES`.
- Read back with `read_board`, a written node MUST project to `complete` of the written stack-up, compared by `stackup.values`.

#### Scenario: Created four-layer board
- **GIVEN** `created_board(4)` given the stack-up of `stackup_four.kicad_pcb` without its silkscreen and paste entries: two masks, four copper entries, a prepreg, a core of two sheets and a prepreg, finish `ENIG` and `impedance_controlled`
- **WHEN** it is written for targets 9 and 10
- **THEN** the two `setup` nodes are tree-equal and hold `stackup` and then `pad_to_mask_clearance`; the node holds 13 rows from `F.SilkS` to `B.SilkS`, the core row holding one `addsublayer`, and ends with `(copper_finish "ENIG") (dielectric_constraints yes)`; and `general` holds `(thickness 2.025)`

#### Scenario: Masks the stack-up omits
- **GIVEN** a created two-layer board whose stack-up is copper 35 µm, a core of 1.5 mm and copper 35 µm
- **WHEN** it is written for target 10
- **THEN** the `F.Mask` and `B.Mask` rows hold `(thickness 0)`, the silkscreen and paste rows hold no thickness, and `general` holds `(thickness 1.57)`

#### Scenario: Stack-up edited on a read board
- **GIVEN** `stackup_four.kicad_pcb` read with `read_board`, and the thickness of its first prepreg changed to 150 000 nm
- **WHEN** the design is written for its own target
- **THEN** the `stackup` child is `stackup_node` of the changed model, every other child of `setup` is tree-equal to the source's, `general` holds `(thickness 1.975)`, and no warning or error is raised

#### Scenario: Copper entries that do not fit the table
- **GIVEN** a created design whose board has `created_layers(4)` and a stack-up whose copper entries are only `F.Cu` and `B.Cu`
- **WHEN** it is written with `allow_lossy=True`
- **THEN** `LossyWriteError` is raised with an issue `kicad.board.stackup-invalid`

#### Scenario: Written nodes read back
- **WHEN** `uv run pytest tests/unit/backends/kicad/test_stackup_write.py -k roundtrip` writes the stack-ups of its cases (every copper count that `created_layers` gives: 2 and 4, and 6 and 8 with `board-layer-count`; sheets, colours, an empty finish) and reads each board back
- **THEN** each projection equals `complete` of the written stack-up by `stackup.values`, and writing the read board again gives the same text

## MODIFIED Requirements

### Requirement: Modelled board content
The reader SHALL model exactly these root children and leave every other one as an opaque slot:
- the header (`version`, `generator`, `generator_version`), whose values are kept in `Board.ext["kicad"]` as the pairs `version`, `generator` and `generator_version`;
- `layers`, and the net table rows with N ≥ 1;
- `footprint` → `FootprintInstance`, `segment` → `Track`, `arc` → `Arc`, `via` → `Via`;
- `zone` → `Zone`, or `Keepout` for a rule area; a teardrop zone (an `attr` child holding `teardrop`) MUST stay an opaque root slot;
- `gr_line`, `gr_arc`, `gr_circle`, `gr_rect` and `gr_poly` → `Graphic` of kind `line`, `arc`, `circle`, `rect` and `polygon`, with the c0008 rules for points, fill and stroke;
- `gr_text` → `Text`, with `size` and `thickness` projected from `effects/font`. A `gr_text` without a font size or thickness MUST stay opaque.

Via fields MUST be `position`, `diameter` (from `size`), `drill`, `layers`, `net_id`, and `via_type` from the leading atom (`blind`, `buried` or `micro`; `through` when absent). Any other leading atom MUST raise `FormatError`. `Board.outline` MUST be `None` on import. `Board.stackup` MUST be the projection of the opaque `setup` child that "Stack-up on boards" states; the projection adds no child to the list above. Edge.Cuts content MUST stay ordinary `Graphic`s on layer `Edge.Cuts`.

#### Scenario: Copper items of the authored board
- **WHEN** the authored board is read
- **THEN** it has 3 `Track`s, 1 `Arc` and 1 `Via` with `via_type == "through"`, `layers == ("F.Cu", "B.Cu")` and the net GND

#### Scenario: Blind via
- **GIVEN** a board holding `(via blind (at 1 1) (size 0.6) (drill 0.3) (layers "F.Cu" "In1.Cu") (net 1) (uuid "…"))`
- **WHEN** it is read
- **THEN** the via has `via_type == "blind"` and `layers == ("F.Cu", "In1.Cu")`

#### Scenario: Edge graphics are authoritative
- **WHEN** the authored board is read
- **THEN** `board.outline is None` and exactly four `Graphic`s of kind `line` are on layer `Edge.Cuts`

#### Scenario: Text from gr_text
- **WHEN** the authored board is read
- **THEN** its single `Text` has `text == "FENOLITE"`, layer `F.SilkS`, and integer `size` and `thickness` from the font

#### Scenario: Teardrop zone stays opaque
- **GIVEN** a board holding a zone with `(attr (teardrop (type padvia)))`
- **WHEN** it is read
- **THEN** no `Zone` is created for it, and the zone is an `Opaque` slot of the board at its position

#### Scenario: Stack-up projected from an opaque setup
- **WHEN** `tests/data/kicad/board/stackup_four.kicad_pcb` is read
- **THEN** `board.stackup` is not `None`, the `setup` child is an `Opaque` root slot, and `pcb.opaque_count` counts it as it counts the `setup` of `two_layer.kicad_pcb`

### Requirement: Created board header
For a created design, `write_board` SHALL emit exactly the root head set of c0007's `tests/data/kicad/tokens/skeleton.kicad_pcb`, plus `title_block` when one of the seven fields of `Board.title_block` is non-empty:
- `version`, `generator` and `generator_version`;
- `(general (thickness T) (legacy_teardrops no))`, where T is `Stackup.thickness()` of the stack-up that "Stack-up written to boards" completes, or 1.6 mm without a stack-up;
- `paper`, written by `pcb.paper_node(Board.sheet)`, which gives `(paper "A4")` when `Board.sheet` is `None` ("Paper and title block on boards");
- `title_block`, written by `pcb.title_block_node(Board.title_block)` right after `paper`, only when one of its seven fields is non-empty;
- `layers`, from `Board.layers` and each layer's `kicad` bag;
- `(setup (pad_to_mask_clearance 0))`, with the node of "Stack-up written to boards" as the first child of `setup` when `Board.stackup` is set;
- for target 9 only, the net table.

The content follows in `CANONICAL_ORDER`. `pcb.CREATED_ROOT_HEADS` MUST stay the head set of a created board without a title block; `pcb.CANONICAL_ORDER["kicad_pcb"]` MUST hold `title_block` right after `paper`, and `pcb.CANONICAL_ORDER["title_block"]` MUST be `("title", "date", "rev", "company", "comment")`. `fenolite.backends.kicad.layers.CREATED_COPPER_COUNTS` MUST be `(2, 4, 6, 8)`. For each of these counts, `fenolite.backends.kicad.layers.created_layers(copper)` MUST return the two-copper-layer set recorded in `docs/formats/kicad/board.md` with the rows of `layers.inner_rows(copper)` inserted right after `F.Cu`: one row `(2k + 2, "In<k>.Cu", signal)` without a user name for each inner layer k = 1 … copper − 2, in that order. The numbers are those of the 9.0 scheme (`F.Cu` 0, `B.Cu` 2, `In<k>.Cu` 2k + 2, `Edge.Cuts` 25), the rows are the same for targets 9 and 10 (`H-K-PCB-LAYERS`), and each layer's `kicad` bag holds the KiCad number, type and user name. Any other `copper` value, an odd count included, MUST raise `ValueError` naming the counts. `layers.created_count(names)` MUST return the count whose created table has exactly the copper layer names `names`, in table order, and `None` when no count of `CREATED_COPPER_COUNTS` has them. Every head and field name the writer can create MUST match a row of the token inventory, appear in c0007's skeleton, or be listed in `pcb.FLOOR_HEADS`: a closed tuple of names that the 8.0 board format already has, each recorded in `docs/formats/kicad/board.md` with its source and written by the created test board that the triad oracle loads on both majors. `FLOOR_HEADS` MUST include `title_block`, `title`, `date`, `rev`, `company` and `comment` (S-0001; S-0033 at tag 8.0.0), and `stackup`, `color`, `material`, `epsilon_r`, `loss_tangent`, `copper_finish` and `dielectric_constraints` (S-0021, S-0058); `type` is not listed, because the skeleton holds it already and `FLOOR_HEADS` is disjoint from the skeleton. `tests/_boards.py::created_board()` MUST set `SheetFrameRef("A4")`, a `TitleBlock` whose seven fields are non-empty, and, for every created copper count, a `Stackup` with a dielectric of two sheets, a colour, a material and both decimals, so the created test board writes them.

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
- **WHEN** `created_layers(c)` is called for `c` equal to 0, 3, 10 and `True`, and `created_count(("F.Cu", "In1.Cu", "B.Cu"))` is called
- **THEN** each `created_layers` call raises `ValueError` naming 2, 4, 6 and 8, and `created_count` returns `None`

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

### Requirement: Projected fields on write
Before re-emitting an opaque fragment that a reader projected into a model field, `write_board` SHALL project the fragment again with the reader's function and compare the result with the model.
- When `Component.ref` or `Component.value` differs, the writer MUST rewrite only the value atom of the `(property "Reference" …)` or `(property "Value" …)` fragment; every other atom and child of that fragment MUST stay tree-equal.
- When a modelled field kept as an `Opaque` projected slot by the reader's reproducibility check differs, the writer MUST emit that field from the model if the fragment differs from the emitter's output for the old value only in spelling (same heads and atom count, numbers equal as decimals, strings equal as text, a zero angle written or omitted); otherwise it MUST give `kicad.board.projection-read-only`. An unchanged value MUST keep its fragment.
- When `Board.sheet` differs from `pcb.project_paper` of the root `paper` fragment, the writer MUST re-emit that fragment whole with `pcb.paper_node`. When `Board.title_block` differs from `pcb.project_title_block` of the root `title_block` fragment, the writer MUST rewrite that fragment in place, or insert it, as "Paper and title block on boards" states. Both projections are editable, and an unchanged value MUST keep its fragment.
- When `Board.stackup` differs from `stackup.project_stackup` of the root `setup` fragment, compared by `stackup.values`, the writer MUST rewrite the `setup` fragment and the `thickness` of the root `general` fragment as "Stack-up written to boards" states. This projection is editable, and an unchanged value MUST keep both fragments.
- When any other projection differs (`Component.properties` other than Reference and Value, `Graphic.width` from a `stroke`, `Pad.padstack`), the writer MUST give `kicad.board.projection-read-only`, naming the field and the locator.

#### Scenario: Reference renamed
- **GIVEN** `two_layer.kicad_pcb` read with `read_board`, and its resistor component's `ref` changed to `R9`
- **WHEN** the design is written for target 9 and the text is parsed
- **THEN** that footprint's `property "Reference"` node has value `"R9"` and is otherwise tree-equal to the source node

#### Scenario: Spelling-only projection re-emitted
- **GIVEN** a copy of `two_layer.kicad_pcb`, built in the test, whose first `segment` holds `(width 0.250000)`, read with `read_board`, so the reader keeps that `width` as a projected slot, and the track's width then changed to 300 000 nm
- **WHEN** the design is written for target 9 and the text is parsed
- **THEN** that segment holds `(width 0.3)` at the position of the source `width`, and no issue is raised

#### Scenario: Read-only projection edited
- **GIVEN** the same board with the resistor's `properties["Datasheet"]` changed
- **WHEN** it is written
- **THEN** `LossyWriteError` is raised with an issue `kicad.board.projection-read-only` naming `properties` and the footprint's locator

#### Scenario: Paper edited on a read board
- **GIVEN** `two_layer.kicad_pcb` read with `read_board`, and its board's `sheet` changed to `SheetFrameRef("A3")`
- **WHEN** the design is written for target 9
- **THEN** no issue is raised, and the `paper` child is `(paper "A3")` at its source index

#### Scenario: Stack-up added to a read board
- **GIVEN** `two_layer.kicad_pcb` read with `read_board`, and its board given a two-layer stack-up of 35 µm copper, a 1.5 mm core and 10 µm masks
- **WHEN** the design is written for target 9
- **THEN** no warning or error is raised, `setup` holds the stack-up node and then `(pad_to_mask_clearance 0)`, and `general` holds `(thickness 1.59)` and `(legacy_teardrops no)`
