## ADDED Requirements

### Requirement: Via protection on boards
`fenolite.backends.kicad.via_protection` SHALL read and write the protection children of a via, and `read_board` and `write_board` SHALL use it for `Via.protection`: the reader in the form of the board's major (`pcb.form_major` of its version), the writer in the form of the target (`H-K-VIAPROT-FORMS`, `H-K-VIAPROT-NINE`, `H-K-VIAPROT-UPGRADE`).
- **10.0 form** (major 10). The children are `(tenting (front V) (back V))`, `(capping V)`, `(covering (front V) (back V))`, `(plugging (front V) (back V))` and `(filling V)`, V being `yes` (`True`), `no` (`False`) or `none` (`None`); a missing side or child reads as `None`. The writer MUST write a child exactly when one of its values is not `None`, with both sides for the first three, in the order `tenting`, `capping`, `covering`, `plugging`, `filling`, which `pcb.CANONICAL_ORDER["via"]` places between `layers` and `net`. A child that the source holds with `none` values only MUST be named in the pair `protection_none` of the via's `kicad` bag (heads separated by spaces), and the writer MUST write it again in that form while its values stay `None`.
- **9.0 form** (major 9). One child `(tenting …)` whose atoms are `front`, `back`, both, `none`, or none at all. Read from a board of major 9, the named sides MUST be `True` and the others `False`, `none` and no atom MUST give both `False`, and no child gives both `None`. Read from a board of major 10, the named sides MUST be `True` and the others `None`, as 10.0.6 reads them. For target 9 the writer MUST write `(tenting front back)`, `(tenting front)`, `(tenting back)` or `(tenting none)` when both tenting fields are booleans, no child when both are `None`, and, when exactly one is `None`, that side's value in `effective_default(Board.via_protection)` ("Via protection defaults on boards"), so that 9.0.9 plots what the model means.
- **Support per major.** `via_protection.SUPPORT` MUST map `tenting` to `{9, 10}` and `covering`, `plugging`, `capping` and `filling` to `{10}`. For target 9, a via whose `covering_front`, `covering_back`, `plugging_front`, `plugging_back`, `capping` or `filling` is `True` MUST raise `LossyWriteError` with `droppable = False`, carrying one `kicad.board.via-protection-too-new` (error) per via that names its locator, those fields and KiCad 10; `allow_lossy` MUST NOT drop it, and its hint MUST NOT name `--allow-lossy`. `False` and `None` of those fields MUST write nothing for target 9. The code MUST join `pcb.WRITE_ISSUE_CODES`.
- **Reproducibility.** A child that the emitter for the board's major does not reproduce tree-equal (a 9.0 child in a board of major 10, a 10.0 child in a board of major 9, `(tenting)`, a two-sided child with one side) MUST stay an opaque projected slot under "Modelled children are reproducible". A child that none of these forms reads MUST give `None` for its fields and stay opaque, with `kicad.board.kept-opaque`.
- RT1 of "Same-version rebuild" MUST hold on every readable corpus board with no protection child kept opaque, and `tests/corpus/test_board_census.py` MUST write the count of each form per origin to `docs/evidence/kicad-board-read.md`.

#### Scenario: Protection read in the 10.0 form
- **GIVEN** a board of format 20260206 whose via holds `(tenting (front no) (back none)) (filling yes)`
- **WHEN** it is read
- **THEN** the via's `protection` equals `ViaProtection(tenting_front=False, filling=True)`, and both children are `Modeled` slots

#### Scenario: Written for target 10
- **GIVEN** a created design whose via has `ViaProtection(tenting_front=False, tenting_back=False, capping=True, filling=True)`
- **WHEN** it is written for target 10 and the text is parsed
- **THEN** the via's children are, in order, `at`, `size`, `drill`, `layers`, `(tenting (front no) (back no))`, `(capping yes)`, `(filling yes)`, `net` and `uuid`

#### Scenario: All-none children kept
- **GIVEN** a board of format 20250513 whose via holds `(tenting (front none) (back none)) (capping none) (covering (front none) (back none)) (plugging (front none) (back none)) (filling none)`
- **WHEN** it is read and rebuilt with `rebuild_board`
- **THEN** the via's `protection` equals `ViaProtection()`, its `kicad` bag holds `protection_none` naming the five heads, the rebuilt via is tree-equal to the source, and no `kicad.board.kept-opaque` is reported

#### Scenario: The 9.0 form by major
- **GIVEN** a board of format 20241229 and a board of format 20260206, each with a via holding `(tenting front)`
- **WHEN** both are read
- **THEN** the first via has `tenting_front == True` and `tenting_back == False` with a `Modeled` child, and the second has `tenting_front == True` and `tenting_back is None` with the child kept as an opaque projected slot

#### Scenario: Written for target 9
- **GIVEN** a created design without a board default and three vias with `ViaProtection(tenting_front=True)`, `ViaProtection(tenting_front=False, tenting_back=False)` and `ViaProtection(capping=False)`
- **WHEN** it is written for target 9
- **THEN** the first via holds `(tenting front back)`, the second `(tenting none)`, and the third no protection child

#### Scenario: A 10.0 feature refused for target 9
- **GIVEN** a created design whose via has `ViaProtection(plugging_front=True)`
- **WHEN** it is written for target 9 with `allow_lossy=True`
- **THEN** `LossyWriteError` is raised with `droppable == False` and one `kicad.board.via-protection-too-new` naming the via's locator, `plugging_front` and KiCad 10

#### Scenario: Corpus forms
- **WHEN** `uv run pytest tests/corpus/test_board_census.py -k via_protection tests/corpus/test_board_rt1.py` runs with the corpus cached (`needs_corpus`)
- **THEN** RT1 holds on every readable board, no protection child is an opaque slot, and the census counts 444 vias with all-`none` children, 6 with the four `no` children and 2 with `(tenting front back)` (census of 2026-10-05)

### Requirement: Via protection defaults on boards
`via_protection.project_setup(setup, *, major) -> ViaProtection | None` SHALL project the protection children of a board's `setup` node, and `read_board` SHALL set `Board.via_protection` to it. `setup` MUST stay an opaque root slot, so `opaque_count` and RT1 are unchanged.
- **Forms.** For major 10: `(tenting (front V) (back V))`, `(covering (front V) (back V))`, `(plugging (front V) (back V))`, `(capping V)` and `(filling V)`, V being `yes` or `no`. For major 9: the 9.0 `tenting` child of "Via protection on boards", whose named sides are `True` and the others `False`, in boards of either major (`H-K-VIAPROT-NINE`). An absent child gives `None` for its fields; a `setup` without any of them, or no `setup`, gives `None`.
- **KiCad's default.** `via_protection.KICAD_DEFAULT` MUST be `ViaProtection(True, True, False, False, False, False, False, False)`, the values that both majors give absent children (`H-K-VIAPROT-FORMS`, `H-K-VIAPROT-NINE`). `effective_default(default)` MUST replace `None`, whole or per field, by `KICAD_DEFAULT`, and `effective(protection, default)` MUST replace each `None` field of a via's protection by that field of `effective_default(default)`.
- **Created boards.** When `Board.via_protection` is not `None`, `setup` MUST hold `via_protection.setup_children(default, major=target)` right after `pad_to_mask_clearance`: for target 10 the five children `tenting`, `covering`, `plugging`, `capping` and `filling`, in that order, with the values of `effective_default` written `yes` or `no`; for target 9 the 9.0 `tenting` child of `effective_default` (`(tenting none)` when neither side is tented), and the refusal of "Via protection on boards", with the locator `setup`, when one of the other four fields is `True`.
- **Read boards.** When `effective_default(Board.via_protection)` equals `effective_default` of the projection, the `setup` fragment MUST be kept. Otherwise `rewrite_setup` MUST replace the protection children of `setup` in place by `setup_children` of the model's value for the target, inserting them after `allow_soldermask_bridges_in_footprints`, else after `pad_to_mask_clearance`, else first, when the fragment has none; a `Board.via_protection` of `None` MUST remove them. Every other child of `setup` MUST stay tree-equal at its place.
- The facts, with their sources and labels, MUST be in `docs/formats/kicad/board.md`, section "Via protection" (S-0020, S-0029, S-0058).

#### Scenario: A 10.0 default projected
- **GIVEN** a board of format 20260206 whose `setup` holds `(tenting (front yes) (back no)) (covering (front no) (back no)) (plugging (front no) (back no)) (capping no) (filling yes)`
- **WHEN** it is read
- **THEN** `board.via_protection == ViaProtection(True, False, False, False, False, False, False, True)`, and `setup` is an `Opaque` root slot

#### Scenario: A 9.0 default projected
- **GIVEN** a copy of `tests/data/kicad/board/two_layer.kicad_pcb` whose `setup` holds `(tenting front)` after `pad_to_mask_clearance`
- **WHEN** it is read
- **THEN** `board.via_protection == ViaProtection(tenting_front=True, tenting_back=False)`, and `effective(ViaProtection(), board.via_protection)` has `tenting_back == False` and `filling == False`

#### Scenario: Created defaults on both targets
- **GIVEN** a created two-layer design with `Board.via_protection = ViaProtection(tenting_front=False, tenting_back=False)`
- **WHEN** it is written for target 10 and for target 9
- **THEN** the target-10 `setup` holds `(pad_to_mask_clearance 0)`, `(tenting (front no) (back no))`, `(covering (front no) (back no))`, `(plugging (front no) (back no))`, `(capping no)` and `(filling no)` in that order, and the target-9 `setup` holds `(pad_to_mask_clearance 0)` and `(tenting none)`

#### Scenario: A default edited on a read board
- **GIVEN** the board of "A 10.0 default projected", read, with its `via_protection.filling` set to `False`
- **WHEN** it is written for target 10
- **THEN** the `filling` child of `setup` is `(filling no)` at its source index, and every other child of `setup` is tree-equal to the source

#### Scenario: A default refused for target 9
- **GIVEN** a created design with `Board.via_protection = ViaProtection(filling=True)`
- **WHEN** it is written for target 9
- **THEN** `LossyWriteError` is raised with `droppable == False` and one `kicad.board.via-protection-too-new` whose locator is `setup` and which names `filling`

## MODIFIED Requirements

### Requirement: Modelled board content
The reader SHALL model exactly these root children and leave every other one as an opaque slot:
- the header (`version`, `generator`, `generator_version`), whose values are kept in `Board.ext["kicad"]` as the pairs `version`, `generator` and `generator_version`;
- `layers`, and the net table rows with N ≥ 1;
- `footprint` → `FootprintInstance`, `segment` → `Track`, `arc` → `Arc`, `via` → `Via`;
- `zone` → `Zone`, or `Keepout` for a rule area; a teardrop zone (an `attr` child holding `teardrop`) MUST stay an opaque root slot;
- `gr_line`, `gr_arc`, `gr_circle`, `gr_rect` and `gr_poly` → `Graphic` of kind `line`, `arc`, `circle`, `rect` and `polygon`, with the c0008 rules for points, fill and stroke;
- `gr_text` → `Text`, with `size` and `thickness` projected from `effects/font`. A `gr_text` without a font size or thickness MUST stay opaque.

Via fields MUST be `position`, `diameter` (from `size`), `drill`, `layers`, `net_id`, `via_type` from the leading atom (`blind`, `buried` or `micro`; `through` when absent), and `protection` from the children of "Via protection on boards". Any other leading atom MUST raise `FormatError`. `Board.outline` and `Board.stackup` MUST be `None` on import. `Board.via_protection` MUST be the projection of the opaque `setup` child that "Via protection defaults on boards" states; the projection adds no child to the list above. Edge.Cuts content MUST stay ordinary `Graphic`s on layer `Edge.Cuts`.

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

#### Scenario: Protected via and board default
- **GIVEN** a copy of the authored board whose via holds `(tenting front)` and whose `setup` holds `(tenting front back)`
- **WHEN** it is read
- **THEN** the via has `protection == ViaProtection(tenting_front=True, tenting_back=False)`, `board.via_protection == ViaProtection(tenting_front=True, tenting_back=True)`, and `setup` is an `Opaque` root slot

### Requirement: Created board header
For a created design, `write_board` SHALL emit exactly the root head set of c0007's `tests/data/kicad/tokens/skeleton.kicad_pcb`, plus `title_block` when one of the seven fields of `Board.title_block` is non-empty:
- `version`, `generator` and `generator_version`;
- `(general (thickness T) (legacy_teardrops no))`, where T is the sum of the `Board.stackup` layer thicknesses, or 1.6 mm without a stack-up;
- `paper`, written by `pcb.paper_node(Board.sheet)`, which gives `(paper "A4")` when `Board.sheet` is `None` ("Paper and title block on boards");
- `title_block`, written by `pcb.title_block_node(Board.title_block)` right after `paper`, only when one of its seven fields is non-empty;
- `layers`, from `Board.layers` and each layer's `kicad` bag;
- `(setup (pad_to_mask_clearance 0))`, followed inside `setup` by the children of "Via protection defaults on boards" when `Board.via_protection` is not `None`;
- for target 9 only, the net table.

The content follows in `CANONICAL_ORDER`. `pcb.CREATED_ROOT_HEADS` MUST stay the head set of a created board without a title block; `pcb.CANONICAL_ORDER["kicad_pcb"]` MUST hold `title_block` right after `paper`, and `pcb.CANONICAL_ORDER["title_block"]` MUST be `("title", "date", "rev", "company", "comment")`. `fenolite.backends.kicad.layers.created_layers(copper)` MUST return the 2- and 4-copper-layer sets recorded in `docs/formats/kicad/board.md`, numbered in the 9.0 scheme (`F.Cu` 0, `B.Cu` 2, `In1.Cu` 4, `In2.Cu` 6, `Edge.Cuts` 25), with the KiCad number, type and user name in each layer's `kicad` bag. Any other `copper` value MUST raise `ValueError`. Every head and field name the writer can create MUST match a row of the token inventory, appear in c0007's skeleton, or be listed in `pcb.FLOOR_HEADS`: a closed tuple of names that the 8.0 board format already has, each recorded in `docs/formats/kicad/board.md` with its source and written by the created test board that the triad oracle loads on both majors. `FLOOR_HEADS` MUST include `title_block`, `title`, `date`, `rev`, `company` and `comment` (S-0001; S-0033 at tag 8.0.0), and `tests/_boards.py::created_board()` MUST set `SheetFrameRef("A4")` and a `TitleBlock` whose seven fields are non-empty, so the created test board writes them.

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

#### Scenario: Created tokens are known
- **WHEN** `uv run pytest tests/unit/backends/kicad/test_pcb_write.py -k created_tokens` runs
- **THEN** every head and field in `CANONICAL_ORDER` and in the created header is found in the skeleton, is in `FLOOR_HEADS`, or matches an inventory row, and every name of `FLOOR_HEADS` occurs in the parsed text of the created test board written for target 9

#### Scenario: Created board with a Tabloid sheet
- **GIVEN** a created design whose board has `created_layers(2)`, `sheet = SheetFrameRef("Tabloid")` and `title_block = TitleBlock(title="Bench")`
- **WHEN** it is written for target 10
- **THEN** the root's child heads are `version`, `generator`, `generator_version`, `general`, `paper`, `title_block`, `layers`, `setup`, and the `paper` child is `(paper "User" 431.8 279.4)`

#### Scenario: Created board with a via protection default
- **GIVEN** a created design whose board has `created_layers(2)` and `via_protection = ViaProtection(tenting_front=True, tenting_back=False)`
- **WHEN** it is written for target 10
- **THEN** the root's child heads are those of "No net table for target 10", and `setup` holds `pad_to_mask_clearance`, `tenting`, `covering`, `plugging`, `capping` and `filling`, in that order

### Requirement: Projected fields on write
Before re-emitting an opaque fragment that a reader projected into a model field, `write_board` SHALL project the fragment again with the reader's function and compare the result with the model.
- When `Component.ref` or `Component.value` differs, the writer MUST rewrite only the value atom of the `(property "Reference" …)` or `(property "Value" …)` fragment; every other atom and child of that fragment MUST stay tree-equal.
- When a modelled field kept as an `Opaque` projected slot by the reader's reproducibility check differs, the writer MUST emit that field from the model if the fragment differs from the emitter's output for the old value only in spelling (same heads and atom count, numbers equal as decimals, strings equal as text, a zero angle written or omitted); otherwise it MUST give `kicad.board.projection-read-only`. An unchanged value MUST keep its fragment.
- When `Board.sheet` differs from `pcb.project_paper` of the root `paper` fragment, the writer MUST re-emit that fragment whole with `pcb.paper_node`. When `Board.title_block` differs from `pcb.project_title_block` of the root `title_block` fragment, the writer MUST rewrite that fragment in place, or insert it, as "Paper and title block on boards" states. Both projections are editable, and an unchanged value MUST keep its fragment.
- When `Board.via_protection` differs from `via_protection.project_setup` of the root `setup` fragment, compared by `effective_default`, the writer MUST rewrite the protection children of that fragment as "Via protection defaults on boards" states. When `Via.protection` differs from the projection of a protection child that the reader kept as an opaque projected slot, the writer MUST replace that child by the form of "Via protection on boards" for the target, or remove it when the child's values are all `None`. Both projections are editable, and an unchanged value MUST keep its fragments.
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

#### Scenario: Via protection default added to a read board
- **GIVEN** `two_layer.kicad_pcb` read with `read_board`, and its board given `via_protection = ViaProtection(tenting_front=False, tenting_back=False)`
- **WHEN** the design is written for target 9
- **THEN** no issue is raised, `setup` holds `(pad_to_mask_clearance 0)` and then `(tenting none)`, and every other child of the board is tree-equal to the source

#### Scenario: A projected via child edited
- **GIVEN** a board of format 20260206 whose via holds the 9.0 child `(tenting front)`, read with `read_board` so the child is an opaque projected slot, and the via's protection then set to `ViaProtection(tenting_front=True, tenting_back=False)`
- **WHEN** the design is written for target 10
- **THEN** no issue is raised, and the via holds `(tenting (front yes) (back no))` at the position of the source child
