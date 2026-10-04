## ADDED Requirements

### Requirement: Footprint fields on boards
`read_board` SHALL map every placed `property` child of a board footprint to a `FootprintField` of `FootprintInstance.fields`, in file order, and SHALL keep the property's value in the component (`design-model`, "Footprint fields").
- A property is placed when it holds a name atom, a value atom, `at`, `layer` and an `effects` whose `font` holds `size`. Only the first property of a name in one footprint is a field. A later property with the same name MUST stay an `Opaque` slot of the footprint, with the info `kicad.board.kept-opaque`.
- The values MUST come from the node:
  - `name` from its first atom; `position` from the X and Y of `at`; `rotation = pad_angle_from_board(stored, instance.rotation)`, `stored` being the angle of `at`, or 0 when it is absent;
  - `layer` from the first atom of `layer`;
  - `visible` false for a `hide` child other than `(hide no)`, in the node or in its `effects`, and for a bare `hide` atom in the node or in its `effects`, and true otherwise; a `hide` inside `effects` keeps that `effects` a projected slot;
  - `size = Size(W, H)` from the font's `(size H W)`, and `thickness` from the font's `thickness`, or `None` when it is absent;
  - `h_justify`, `v_justify` and `mirrored` from the atoms `left`, `right`, `top`, `bottom` and `mirror` of `effects/justify`.
- The footprint's slot for the node MUST be `Modeled("fields")`. The field MUST carry its own slot list in `ext["kicad"]`: the name atom, `at`, `layer`, `hide`, `uuid` and `effects` modelled; the value atom an `Opaque` slot whose value is projected into the component; every other child, such as `unlocked`, opaque at its position. The modelled children follow "Modelled children are reproducible", so an `effects` that the emitter does not reproduce, for example one with `bold` or a font `face`, stays a projected slot.
- The field's id MUST be `derived_id("fld", "kicad", "<key>:field:<name>")`, `<key>` being the native id from which the footprint's pad ids derive, and `native_ids["kicad"]` MUST be the property's uuid.
- A property that is not placed, and every `fp_text`, MUST be read as before this change. A property whose `at` or font holds a length or angle that is not a whole number of nm or µdeg MUST stay a projected slot of the footprint, with the info `kicad.board.inexact-length` or `kicad.board.inexact-angle` ("Exact numbers on boards").
- `rebuild_board` MUST rebuild each field from its slot list, so that RT1 ("Same-version rebuild") keeps holding.

#### Scenario: Reference of a rotated top footprint
- **WHEN** `tests/data/kicad/board/two_layer.kicad_pcb` is read
- **THEN** `R1` has the fields `Reference` and `Value`, in that order; `Reference` has `position == Point(0, -1_430_000)`, `rotation == 0`, layer `F.SilkS`, `visible`, `size == Size(1_000_000, 1_000_000)`, `thickness == 150_000`, both justifications `center` and `mirrored == False`; its slot list holds the value atom `"R1"` as an `Opaque` slot; and the component of `R1` has `ref == "R1"`

#### Scenario: Field of a bottom footprint
- **WHEN** the same board is read
- **THEN** the `Reference` field of `D1` has `position == Point(1_270_000, 2_960_000)`, `rotation == 0` (stored 30° minus the footprint's 30°), layer `B.SilkS` and `mirrored == True`

#### Scenario: Hidden field with justification
- **GIVEN** a copy of the authored board, built in the test, whose `Value` property of `R1` holds `(hide yes)` after its `layer` and `(justify left bottom)` in its `effects`
- **WHEN** it is read
- **THEN** that field has `visible == False`, `h_justify == "left"` and `v_justify == "bottom"`, and its `hide` and `effects` children are `Modeled` slots

#### Scenario: Eight-format hidden field
- **GIVEN** a board with header `20240108`, built in the test, whose only footprint holds `(property "Value" "X" (at 0 1 0) (layer "F.Fab") hide (uuid "…") (effects (font (size 1 1) (thickness 0.15))))`
- **WHEN** it is read with an `issues` list
- **THEN** no issue has severity `error`, the `Value` field has `visible == False`, and the `hide` atom is an `Opaque` slot of the field

#### Scenario: Bare and repeated properties
- **GIVEN** a copy of the authored board, built in the test, whose `R1` holds `(property ki_fp_filters "R_*")` and two placed properties named `MPN`
- **WHEN** it is read with an `issues` list
- **THEN** `R1` has the fields `Reference`, `Value` and `MPN` only; the bare property and the second `MPN` are `Opaque` slots of the footprint; `issues` holds one info `kicad.board.kept-opaque` locating the second `MPN`; and the component's `properties` map `ki_fp_filters` to `R_*`

#### Scenario: Round trip with fields
- **GIVEN** the authored board and the fetched corpus
- **WHEN** `uv run pytest tests/unit/backends/kicad/test_pcb_rebuild.py -k rt1 tests/corpus/test_board_rt1.py tests/corpus/test_board_fields.py` runs
- **THEN** RT1 holds for every board, and every `Reference` and `Value` property of the 21 corpus boards is a field

### Requirement: Footprint fields are written
`write_board` SHALL write each `FootprintField` of a footprint as a `property` node from the model.
- The node MUST hold the name atom, the value atom, `(at X Y A)` with the field's position and the board angle `A = pad_angle_to_board(rotation, footprint rotation)`, written also when it is 0, `(layer "L")`, `(hide yes)` only when the field is not visible, `(uuid "U")`, and `(effects (font (size H W) (thickness T)) (justify …))`. `thickness` is left out when it is `None`. `justify` holds `left` or `right`, then `top` or `bottom`, then `mirror`, each only when set, and is left out when none is.
- A read field MUST be rebuilt from its slot list: unchanged modelled children keep their text, opaque children stay at their positions, and a child new to the field follows "Canonical insertion of new fields" with `CANONICAL_ORDER["property"]`, which MUST be `name`, `value`, `at`, `layer`, `hide`, `uuid`, `effects`. `pcb.FLOOR_HEADS` MUST include `hide`.
- The value atom MUST follow "Projected fields on write": it takes the component's `ref` or `value` for `Reference` and `Value`, and any other changed value gives `kicad.board.projection-read-only`.
- A child that the reader kept as a projected slot MUST keep its fragment while the model agrees with it; an `at` whose angle lies outside [0°, 360°), such as the `-90` that KiCad writes for some fields, agrees with the model when it is equal modulo 360°. A changed value of such a child MUST give `kicad.board.projection-read-only`, unless the child differs from the emitter's output for the old value only in spelling; a `(hide no)` child and an `at` with plain numbers count as spellings. A bare `hide` atom cannot be removed: showing such a field gives `kicad.board.projection-read-only`.
- A created footprint MUST take the placement of each property that the writer creates from the field of the same name, when `fields` holds one; the property's uuid is then `kicad_uuid(field)`.
- A field without a slot list on a read footprint, a field of a created footprint whose name the component lacks, and a second field with the name of another field of the same footprint MUST raise `ValueError` naming the field. A read field removed from the model leaves its node out, and the component's property then gives `kicad.board.projection-read-only`; for `Reference` and `Value`, whose values "Projected fields on write" does not compare, this holds when the footprint has more field nodes than fields and no node holds the name.

#### Scenario: Field moved and turned on a read board
- **GIVEN** the authored board read with `read_board`, whose `R1` `Reference` field is given `position = Point(0, -2_000_000)` and `rotation = 90_000_000`
- **WHEN** the design is written for target 9 and the text is parsed
- **THEN** that property node holds `(at 0 -2 180)` and is otherwise tree-equal to the source node

#### Scenario: Hidden, resized and justified
- **GIVEN** the authored board read, whose `R1` `Value` field is given `visible = False`, `size = Size(800_000, 800_000)`, `thickness = 120_000` and `h_justify = "left"`
- **WHEN** the design is written for target 10 and the text is read again
- **THEN** the node holds `(hide yes)` between `layer` and `uuid`, `(font (size 0.8 0.8) (thickness 0.12))` and `(justify left)`, and the re-read field equals the model's

#### Scenario: Bottom field justified
- **GIVEN** the authored board read, whose `D1` `Reference` field is given `h_justify = "right"`
- **WHEN** it is written for target 9
- **THEN** that node's `effects` holds `(justify right mirror)`

#### Scenario: Unchanged fields
- **GIVEN** the authored board read with `read_board`
- **WHEN** it is written for target 9
- **THEN** every `property` node of the text is tree-equal to its source node

#### Scenario: Created footprint with fields
- **GIVEN** `tests/_boards.py::created_board()`, whose footprint has a `Reference` field at `Point(0, -1_500_000)` and a hidden `Value` field
- **WHEN** it is written for targets 9 and 10 and each text is read with `read_board`
- **THEN** the re-read fields equal the model's, and `uv run pytest tests/unit/backends/kicad/test_pcb_write.py -k created_tokens` passes with `hide` in `FLOOR_HEADS`

#### Scenario: Field added to a read footprint
- **GIVEN** the authored board read, with a new field `MPN` without slots appended to `R1`
- **WHEN** `write_board` is called
- **THEN** a `ValueError` naming `MPN` is raised

### Requirement: Footprint field helpers
The module `fenolite.backends.kicad.fields` SHALL convert fields between the model frame and the board frame, and SHALL place a field beside its footprint's courtyard.
- `field_anchor(fp, field) -> Point` MUST equal `Transform.placement(fp.position, fp.rotation).apply(field.position)`, and `field_angle(fp, field) -> Udeg` MUST equal `(field.rotation + fp.rotation) mod 360°`.
- `set_field(fp, name, *, anchor=None, angle=None, layer=None, visible=None, size=None, thickness=None, justify=None, mirrored=None) -> FootprintInstance` MUST return a copy of `fp` whose field `name` takes every given value. `anchor` and `angle` are board-frame values. The field keeps its position when `field_anchor` already gives `anchor`, and otherwise stores `Transform.placement(fp.position, fp.rotation).inverse().apply(anchor)`; it stores `pad_angle_from_board(angle, fp.rotation)` as its rotation. `justify` is a pair `(h_justify, v_justify)`. Every other field and value MUST stay unchanged, and an unknown name MUST raise `KeyError` naming it.
- `place_outside(fp, name, *, side, gap=DEFAULT_GAP) -> FootprintInstance` MUST take `B`, the bounding box of the points of `placed_extent(fp).own` (c0028's `fenolite.backends.kicad.frame`, its pad fallback included), or the point box at `fp.position` when it holds no ring. It MUST then set through `set_field` the board angle 0 and, with `(cx, cy)` the centre of `B` rounded half to even and `d = gap + t // 2`, `t` being the field's thickness or 0:
  - `side="top"`: anchor `(cx, B.y0 − d)`, `v_justify = "bottom"`, `h_justify = "center"`;
  - `side="bottom"`: anchor `(cx, B.y1 + d)`, `v_justify = "top"`, `h_justify = "center"`;
  - `side="left"`: anchor `(B.x0 − d, cy)`, `h_justify = "right"`, or `"left"` when the field is mirrored, and `v_justify = "center"`;
  - `side="right"`: anchor `(B.x1 + d, cy)`, `h_justify = "left"`, or `"right"` when the field is mirrored, and `v_justify = "center"`.
- `DEFAULT_GAP` MUST be 250 000 nm, a Fenolite choice. A negative `gap` MUST raise `ValueError`.
- `fields.EVIDENCE` MUST be `INFERRED` with the hypotheses `H-K-FIELD-FRAME`, `H-K-FIELD-JUSTIFY` and `H-K-FIELD-OUTSIDE`, and MUST stay `INFERRED`, because the bench does not cover every string.

#### Scenario: Anchor and angle of a rotated field
- **GIVEN** the authored board read with `read_board`
- **WHEN** `field_anchor` and `field_angle` are called for the `Reference` field of `R1` (footprint at 20 mm, 15 mm and 90°)
- **THEN** they return `Point(18_570_000, 15_000_000)` and `90_000_000`

#### Scenario: Board-frame round trip
- **GIVEN** `Mini_R_0603` placed with `place_footprint` at 0°, 30° and 90° on the top and at 30° on the bottom
- **WHEN** `set_field(fp, "Reference", anchor=field_anchor(fp, f), angle=field_angle(fp, f))` is called with its `Reference` field `f`
- **THEN** the returned footprint equals `fp`

#### Scenario: Outside on top of a rotated part
- **GIVEN** the authored board read, whose `R1` courtyard box on the board is (19.27 mm, 13.52 mm) to (20.73 mm, 16.48 mm)
- **WHEN** `place_outside(r1, "Reference", side="top")` is called
- **THEN** the field's anchor is `Point(20_000_000, 13_195_000)`, its board angle 0, `v_justify == "bottom"` and `h_justify == "center"`, so it stores `position == Point(1_805_000, 0)` and `rotation == 270_000_000`

#### Scenario: Mirrored field on the left
- **GIVEN** the authored board read
- **WHEN** `place_outside(d1, "Reference", side="left")` is called
- **THEN** the field has `h_justify == "left"` and `mirrored == True`, and its anchor's X is the left edge of `D1`'s box minus 325 000 nm

#### Scenario: Negative gap
- **WHEN** `place_outside(r1, "Reference", side="top", gap=-1)` is called
- **THEN** a `ValueError` is raised

## MODIFIED Requirements

### Requirement: Unmodelled board content is kept as slots
The reader MUST record the slot list of the board root in `Board.ext["kicad"]`, and the slot list of every modelled item (footprint, pad, footprint field, track, arc, via, zone, keepout, graphic, text) in its own `ext["kicad"]`, using the encoding of `kicad-slots`.
- Every child of a modelled item that is not modelled MUST be an `Opaque` slot at its position.
- A projected child MUST be an `Opaque` slot whose value is also copied into the model. This covers, among others, the properties that are not footprint fields ("Footprint fields on boards"), the value atom of a footprint field, the `effects` of a footprint field that the emitter does not reproduce, the footprint lock, wildcard pad, zone and rule-area layers, padstacks, offset drills, strokes, text effects of `gr_text`, `pinfunction` and `pintype`.
- Opaque fragments MUST carry the minimum version that `_libread.Context.min_version` gives for root chain `("kicad_pcb", …)`, and the file version when the inventory has no row for the fragment's head.

#### Scenario: Unknown root child survives in place
- **GIVEN** the authored board with `(frobnicate 1)` inserted as the fifth child of the root
- **WHEN** it is read and `slots.from_ext(board.ext["kicad"])` is inspected
- **THEN** the fifth slot is `Opaque("(frobnicate 1)", "20241229")`

#### Scenario: Footprint property is a field
- **WHEN** the authored board is read
- **THEN** the component of `R1` has `ref == "R1"`, the `property "Reference"` child of the footprint is a `Modeled("fields")` slot, and the slot list of that field holds the value atom `"R1"` as an `Opaque` slot

#### Scenario: Bare property is projected
- **GIVEN** a copy of the authored board, built in the test, whose `R1` footprint holds `(property ki_fp_filters "R_*")` after its `Value` property
- **WHEN** it is read
- **THEN** that child is an `Opaque` slot of the footprint, and the component's `properties` map `ki_fp_filters` to `R_*`
