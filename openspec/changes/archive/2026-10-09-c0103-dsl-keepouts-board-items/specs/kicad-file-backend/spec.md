## ADDED Requirements

### Requirement: Board items of a script are written
`fenolite.backends.kicad.boarditems` SHALL give the rule areas, texts, graphics and dimensions of a script their KiCad uuids, and `write_board` SHALL write created rule areas with their names, created texts with their justification, and created dimensions.
- `item_uuid(entity_id) -> str` MUST return a version-8 uuid (RFC 9562, S-0110) whose 48-bit `custom_a` field is the marker `ITEM_MARKER`, the ASCII bytes of `fenitm`, and whose `custom_b` and `custom_c` fields hold the first 74 bits of the SHA-256 of `kicad-item:<entity_id>`, as `copper_uuid` builds its uuids. `is_item_uuid(text)` MUST be true exactly for a canonical uuid with that marker, version 8 and the RFC variant; a copper uuid MUST NOT be an item uuid.
- `mark_items(design) -> Design` MUST set `native_ids["kicad"]` of every keep-out, text, graphic and dimension of the board to `item_uuid(<its id>)` and change nothing else; `pcb.kicad_uuid` then returns that uuid.
- **Rule areas.** A created rule area MUST write `(name "<name>")` right after its `uuid` when `Keepout.name` is not empty, and nothing else beyond what "Board writing per target" writes for it today (`H-K-AREA-NAME`).
- **Texts.** A created text MUST write `(justify …)` in its `effects`, holding `left` or `right`, then `top` or `bottom`, then `mirror` on a back layer, each only when set, and no `justify` child when none is set.
- **Dimensions.** A created dimension MUST write, in this order: `(type aligned|orthogonal)`, `layer`, `uuid`, `(pts (xy …) (xy …))`, `(height <offset>)`, `(orientation 0|1)` for an orthogonal one only, `(format (prefix "") (suffix "") (units 2|0) (units_format 1) (precision P))`, `(style (thickness W) (arrow_length 1.27) (text_position_mode 0) (arrow_direction outward) (extension_height 0.58642) (extension_offset 0.5) (keep_text_aligned yes))` and a `gr_text` with the cache value, at the midpoint of `start` and `end` (rounded down to the nanometre), angle 0, on the dimension's layer, with the dimension's uuid and `(effects (font (size H H) (thickness T)))`. `W` is `width`, else 0.1 mm; `H` and `T` are `size` and `thickness`, else 1 mm and 0.15 mm.
- **Cache value.** The length that the dimension measures (the distance between the points for `aligned`, the absolute difference in x for `horizontal` and in y for `vertical`), in millimetres or inches, rounded half away from zero to `precision` decimals with integer arithmetic only, followed by ` mm` or ` in`. KiCad recomputes the value, the position and the angle of this text on load (`H-K-DIM`), so the written text is a cache.
- `pcb.CANONICAL_ORDER` MUST place `dimension` after `gr_text` among the root children, as KiCad 10.0.6 writes them (`board.md`), and every name a dimension writes MUST pass `check_emittable` for targets 9 and 10, through `pcb.FLOOR_HEADS` or a row of the token inventory.

#### Scenario: Created rule area with a name
- **GIVEN** a created board holding `Keepout(name="ANT", layers=("F.Cu",), no_tracks=True, …)` marked by `mark_items`
- **WHEN** it is written for target 9 and for target 10 and read back with `read_board`
- **THEN** both texts hold `(name "ANT")` as the next child after the area's `uuid`, the uuid is `item_uuid` of the keep-out's id, and the read keep-out has `name == "ANT"` and `no_tracks` true

#### Scenario: Justified text
- **GIVEN** created texts on `F.SilkS` with `h_justify="left"` and `v_justify="bottom"`, and on `B.SilkS` with `h_justify="right"`
- **WHEN** the board is written for target 10
- **THEN** the effects hold `(justify left bottom)` and `(justify right mirror)`

#### Scenario: Created dimensions
- **GIVEN** an aligned dimension from (10 mm, 3 mm) to (30 mm, 3 mm) with `offset == -2_000_000`, and an orthogonal one from (10 mm, 50 mm) to (35.5 mm, 55 mm) with `direction == "horizontal"`, `precision == 2` and `offset == 4_000_000`
- **WHEN** the board is written for target 10
- **THEN** the first node holds `(height -2)`, `(units 2)`, `(precision 4)` and `(gr_text "20.0000 mm" (at 20 3 0) …)`, and the second `(orientation 0)` and `(gr_text "25.50 mm" …)`

#### Scenario: Cache value of an oblique dimension
- **GIVEN** an aligned dimension from (0, 0) to (1 mm, 1 mm) with `precision == 4`, and the same in inches
- **WHEN** its cache value is computed
- **THEN** it is `1.4142 mm`, and `0.0557 in`

#### Scenario: Item uuids are marked
- **WHEN** `item_uuid(derived_id("txt", "dsl", "text:rev"))` is computed twice, and `is_item_uuid` is called on it, on a `copper_uuid` and on a version-4 uuid
- **THEN** both values are equal, and the three calls give true, false and false

#### Scenario: Emit check is clean for both targets
- **GIVEN** a created board with a named rule area, a justified text, an aligned and an orthogonal dimension
- **WHEN** it is written for targets 9 and 10 and `check_emittable` runs on each parsed text with the same target
- **THEN** both calls return no issue at all

## MODIFIED Requirements

### Requirement: Modelled board content
The reader SHALL model exactly these root children and leave every other one as an opaque slot:
- the header (`version`, `generator`, `generator_version`), whose values are kept in `Board.ext["kicad"]` as the pairs `version`, `generator` and `generator_version`;
- `layers`, and the net table rows with N ≥ 1;
- `footprint` → `FootprintInstance`, `segment` → `Track`, `arc` → `Arc`, `via` → `Via`;
- `zone` → `Zone`, or `Keepout` for a rule area, whose `name` child gives `Keepout.name`; a teardrop zone (an `attr` child holding `teardrop`) MUST stay an opaque root slot;
- `gr_line`, `gr_arc`, `gr_circle`, `gr_rect` and `gr_poly` → `Graphic` of kind `line`, `arc`, `circle`, `rect` and `polygon`, with the c0008 rules for points, fill and stroke;
- `gr_text` → `Text`, with `size` and `thickness` projected from `effects/font`, and `h_justify` and `v_justify` from the `left`, `right`, `top` and `bottom` atoms of `effects/justify` (`center` when absent). A `gr_text` without a font size or thickness MUST stay opaque;
- `dimension` whose `type` is `aligned` or `orthogonal` → `Dimension`, with `layer`, `start` and `end` from the two `xy` of `pts`, `offset` from `height`, and, for `orthogonal`, `direction` from `orientation` (0 `horizontal`, 1 `vertical`). Its `format`, `style` and `gr_text` children MUST be projected `Opaque` slots: `units` from `format/units` (2 `mm`, 0 `in`), `precision` from `format/precision` when it is 0 to 4, `width` from `style/thickness`, and `size` and `thickness` from the font of the `gr_text`; a value outside these keeps the field's default. The `gr_text` of a dimension belongs to it: its uuid MUST NOT give `kicad.board.duplicate-uuid`. A dimension of another type, one whose `pts` does not hold exactly two points, and an `orthogonal` one without `orientation` MUST stay opaque root slots.

Via fields MUST be `position`, `diameter` (from `size`), `drill`, `layers`, `net_id`, `via_type` from the leading atom (`blind`, `buried` or `micro`; `through` when absent), and `protection` from the children of "Via protection on boards". Any other leading atom MUST raise `FormatError`. `Board.outline` MUST be `None` on import. `Board.stackup` MUST be the projection of the opaque `setup` child that "Stack-up on boards" states; the projection adds no child to the list above. `Board.via_protection` MUST be the projection of the same opaque `setup` child that "Via protection defaults on boards" states; it adds no child to the list above either. Edge.Cuts content MUST stay ordinary `Graphic`s on layer `Edge.Cuts`.

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

#### Scenario: Protected via and board default
- **GIVEN** a copy of the authored board whose via holds `(tenting front)` and whose `setup` holds `(tenting front back)`
- **WHEN** it is read
- **THEN** the via has `protection == ViaProtection(tenting_front=True, tenting_back=False)`, `board.via_protection == ViaProtection(tenting_front=True, tenting_back=True)`, and `setup` is an `Opaque` root slot

#### Scenario: Named rule area
- **GIVEN** a board holding a rule area with `(name "ANT")` after its `uuid` and `(tracks not_allowed)`
- **WHEN** it is read
- **THEN** its `Keepout` has `name == "ANT"` and `no_tracks` true, and its `name` child is a `Modeled` slot

#### Scenario: Justified text
- **GIVEN** a board holding `(gr_text "L" (at 5 40 0) (layer "F.SilkS") (uuid "…") (effects (font (size 1 1) (thickness 0.15)) (justify left bottom)))`
- **WHEN** it is read
- **THEN** the `Text` has `h_justify == "left"` and `v_justify == "bottom"`

#### Scenario: Dimension saved by KiCad
- **GIVEN** an aligned dimension as `kicad-cli` 10.0.6 saves it, with `(units 3)` and the text "20.0000 mm" sharing the dimension's uuid
- **WHEN** it is read with an `issues` list
- **THEN** the board holds one `Dimension` of kind `aligned` with its points and `offset`, `units == "mm"` (the default, since 3 is outside the model), its `format` child is an `Opaque` slot, and `issues` holds no `kicad.board.duplicate-uuid`

#### Scenario: Other dimension types stay opaque
- **GIVEN** a board holding `(dimension (type leader) …)`
- **WHEN** it is read
- **THEN** no `Dimension` is created, and the node is an `Opaque` slot of the board at its position
